"""Orchestration tests: convergence, iteration bounds. Agents are mocked (no API calls)."""
from src.orchestrator import MAX_ITERATIONS, run_squad
from src.schemas import CodeArtifact, QAReport, SpecArtifact


class FakeSquad:
    """Scripted agents that count how often each one is called."""

    def __init__(self, passes_on: int | None):
        self.passes_on = passes_on  # iteration that passes, or None = never
        self.spec_calls = 0
        self.coder_calls = 0
        self.qa_calls = 0

    def spec(self, request: str) -> SpecArtifact:
        self.spec_calls += 1
        return SpecArtifact(
            feature_name="Fake", requirements=["r"], test_cases=["t"], interfaces="i"
        )

    def coder(self, spec, iteration, previous_code=None, previous_report=None) -> CodeArtifact:
        self.coder_calls += 1
        return CodeArtifact(implementation_code="x", test_code="y", iteration=iteration)

    def qa(self, code: CodeArtifact) -> QAReport:
        self.qa_calls += 1
        passed = self.passes_on is not None and code.iteration >= self.passes_on
        return QAReport(
            tests_passed=passed,
            total_tests=1,
            failed_tests=0 if passed else 1,
            execution_output="ok" if passed else "boom",
            review_feedback=[],
            status="PASSED" if passed else "NEEDS_REVISION",
        )


def run_with(fake: FakeSquad, **kwargs):
    return run_squad(
        "build something",
        spec_fn=fake.spec,
        coder_fn=fake.coder,
        qa_fn=fake.qa,
        **kwargs,
    )


# ---------- Test 5: clean convergence ----------
def test_clean_convergence_halts_after_first_pass():
    fake = FakeSquad(passes_on=1)
    final = run_with(fake)
    assert final["report"].status == "PASSED"
    assert final["iteration"] == 1
    assert (fake.spec_calls, fake.coder_calls, fake.qa_calls) == (1, 1, 1)


# ---------- Test 6: iteration boundary enforcement ----------
def test_continuous_failure_stops_at_exactly_four_iterations():
    fake = FakeSquad(passes_on=None)
    final = run_with(fake)
    assert MAX_ITERATIONS == 4
    assert final["report"].status == "MAX_CYCLES_EXCEEDED"
    assert final["iteration"] == 4
    assert fake.coder_calls == 4
    assert fake.qa_calls == 4


# ---------- Bonus: loop behaviour ----------
def test_recovers_after_failures_and_stops_when_tests_pass():
    fake = FakeSquad(passes_on=3)
    final = run_with(fake)
    assert final["report"].status == "PASSED"
    assert final["iteration"] == 3
    assert fake.coder_calls == 3


def test_custom_iteration_ceiling_is_respected():
    fake = FakeSquad(passes_on=None)
    final = run_with(fake, max_iterations=2)
    assert final["iteration"] == 2
    assert final["report"].status == "MAX_CYCLES_EXCEEDED"


def test_bug_injection_only_touches_first_iteration():
    fake = FakeSquad(passes_on=2)
    injected_on = []

    def injector(code):
        injected_on.append(code.iteration)
        return code, "fake bug"

    final = run_with(fake, inject_bug=True, bug_injector=injector)
    assert injected_on == [1]
    assert final["injected_bug"] == "fake bug"
    assert final["report"].status == "PASSED"


# ---------- Bonus: every agent asks the LLM for low-randomness output ----------
def test_agents_request_low_temperature_from_the_llm():
    import json
    from unittest.mock import MagicMock, patch

    from src.agents import coder_agent, reviewer_agent, spec_agent

    def fake_client(content: dict) -> MagicMock:
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=json.dumps(content)))
        ]
        return client

    spec_json = {"feature_name": "F", "requirements": [], "test_cases": [], "interfaces": ""}
    code_json = {"implementation_code": "x = 1", "test_code": "def test_x(): pass"}
    qa_json = {"review_feedback": []}
    spec = SpecArtifact(**spec_json)
    code = CodeArtifact(implementation_code="x = 1", test_code="def test_x(): pass", iteration=1)

    for module, call, content in [
        (spec_agent, lambda: spec_agent.run_spec_agent("req"), spec_json),
        (coder_agent, lambda: coder_agent.run_coder_agent(spec, 1), code_json),
        (reviewer_agent, lambda: reviewer_agent.run_reviewer_agent(code), qa_json),
    ]:
        client = fake_client(content)
        with patch.object(module, "OpenAI", return_value=client):
            call()
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["temperature"] <= 0.3, module.__name__


# ---------- Bonus: focused repair feedback and stuck detection ----------
SAMPLE_OUTPUT = """\
===== test session starts =====
platform linux -- Python 3.11.18 -- NOISE-BANNER
test_solution.py::test_ok PASSED                                  [ 50%]
test_solution.py::test_refill FAILED                              [100%]
=========== FAILURES ===========
E       assert True is False
E        +  where True = allow(1)
=========== short test summary info ===========
FAILED test_solution.py::test_refill - assert True is False
"""


def test_failing_tests_are_extracted_from_pytest_output():
    from src.failure_summary import failing_tests

    assert failing_tests(SAMPLE_OUTPUT) == ["test_refill"]


def test_summary_keeps_error_lines_and_drops_noise():
    from src.failure_summary import summarize_failures

    summary = summarize_failures(SAMPLE_OUTPUT)
    assert "assert True is False" in summary
    assert "NOISE-BANNER" not in summary
    assert "test_ok" not in summary


def test_coder_receives_focused_error_diff_not_raw_output():
    import json
    from unittest.mock import MagicMock, patch

    from src.agents import coder_agent

    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps(
            {"implementation_code": "x = 1", "test_code": "def test_x(): pass"}
        )))
    ]
    spec = SpecArtifact(feature_name="F", requirements=[], test_cases=[], interfaces="")
    code = CodeArtifact(implementation_code="x = 0", test_code="def test_x(): pass", iteration=1)
    report = QAReport(
        tests_passed=False, total_tests=2, failed_tests=1, execution_output=SAMPLE_OUTPUT,
        review_feedback=["note one"], status="NEEDS_REVISION",
    )
    with patch.object(coder_agent, "OpenAI", return_value=client):
        coder_agent.run_coder_agent(spec, 2, code, report)
    prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "test_refill" in prompt
    assert "assert True is False" in prompt
    assert "note one" in prompt
    assert "NOISE-BANNER" not in prompt


def test_stuck_note_added_when_same_tests_fail_twice_in_a_row():
    seen_feedback = {}

    class Fake(FakeSquad):
        def coder(self, spec, iteration, previous_code=None, previous_report=None):
            seen_feedback[iteration] = (
                previous_report.review_feedback if previous_report else None
            )
            return super().coder(spec, iteration, previous_code, previous_report)

        def qa(self, code):
            report = super().qa(code)
            return report.model_copy(update={
                "execution_output": "FAILED test_solution.py::test_same - boom"
            })

    run_with(Fake(passes_on=None))
    assert seen_feedback[1] is None
    assert not any("STUCK" in f for f in seen_feedback[2])  # first failure
    assert seen_feedback[3][0].startswith("STUCK")          # same test failed twice
    assert "test_same" in seen_feedback[3][0]
