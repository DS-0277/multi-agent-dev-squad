"""Sandbox tests: timeout, error capture, isolation. No OpenAI calls."""
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from src.agents import reviewer_agent
from src.bug_injector import inject_logic_bug
from src.sandbox import SandboxTimeoutError, run_python, run_tests
from src.schemas import CodeArtifact

GOOD_CODE = "def add(a, b):\n    return a + b\n"
GOOD_TEST = "from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
FAIL_TEST = "def test_fail():\n    assert 1 == 2\n"


def fake_llm(content: dict) -> MagicMock:
    """A stand-in OpenAI client that returns a scripted JSON answer."""
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps(content)))
    ]
    return client


def review(code: CodeArtifact, llm_answer: dict):
    with patch.object(reviewer_agent, "OpenAI", return_value=fake_llm(llm_answer)):
        return reviewer_agent.run_reviewer_agent(code)


# ---------- Test 1: passing execution ----------
def test_passing_execution():
    result = run_tests(GOOD_CODE, GOOD_TEST)
    assert result.exit_code == 0
    assert not result.timed_out

    report = review(
        CodeArtifact(implementation_code=GOOD_CODE, test_code=GOOD_TEST, iteration=1),
        {"review_feedback": []},
    )
    assert report.tests_passed is True
    assert report.status == "PASSED"


# ---------- Test 2: failing assertion capture ----------
def test_failing_assertion_capture():
    result = run_tests(GOOD_CODE, FAIL_TEST)
    assert result.exit_code != 0
    assert "assert 1 == 2" in result.stdout + result.stderr

    report = review(
        CodeArtifact(implementation_code=GOOD_CODE, test_code=FAIL_TEST, iteration=1),
        {"review_feedback": ["fails"]},
    )
    assert report.tests_passed is False
    assert "assert 1 == 2" in report.execution_output


# ---------- Test 3: infinite loop timeout ----------
def test_infinite_loop_is_killed_within_timeout():
    start = time.monotonic()
    with pytest.raises(SandboxTimeoutError):
        run_python("while True:\n    pass\n")
    assert time.monotonic() - start < 12  # 10s limit plus process cleanup


def test_run_tests_flags_timeout_instead_of_crashing():
    hang = "def test_hang():\n    while True:\n        pass\n"
    result = run_tests(GOOD_CODE, hang)
    assert result.timed_out is True
    assert result.exit_code != 0
    assert "timed out" in result.stderr


# ---------- Bonus: audit fixes stay fixed ----------
def test_secrets_are_not_visible_inside_sandbox(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-FAKE-for-test")
    result = run_python(
        "import os\nprint('LEAK' if os.environ.get('OPENAI_API_KEY') else 'SAFE')\n"
    )
    assert result.stdout.strip() == "SAFE"


def test_lying_llm_cannot_override_failing_exit_code():
    report = review(
        CodeArtifact(implementation_code=GOOD_CODE, test_code=FAIL_TEST, iteration=1),
        {"tests_passed": True, "review_feedback": ["Looks great!"]},
    )
    assert report.tests_passed is False
    assert report.status == "NEEDS_REVISION"


def test_bug_injector_makes_passing_code_fail():
    code = CodeArtifact(implementation_code=GOOD_CODE, test_code=GOOD_TEST, iteration=1)
    buggy, description = inject_logic_bug(code)
    assert buggy.implementation_code != code.implementation_code
    assert "Flipped" in description
    assert run_tests(buggy.implementation_code, buggy.test_code).exit_code != 0


def test_bug_injector_skips_code_that_already_fails():
    code = CodeArtifact(implementation_code=GOOD_CODE, test_code=FAIL_TEST, iteration=1)
    unchanged, description = inject_logic_bug(code)
    assert unchanged == code
    assert "No bug injected" in description
