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
