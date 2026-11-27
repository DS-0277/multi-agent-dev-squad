"""Auditor & pytest execution evaluator agent."""
import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from src.sandbox import run_tests
from src.schemas import CodeArtifact, QAReport

load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

SYSTEM_PROMPT = (
    "You are a Reviewer/QA Agent. Given code and the pytest output, audit the code "
    "for logic bugs and security flaws. You do NOT decide whether tests passed; "
    "the test runner's exit code does. Reply with JSON having one key: "
    "review_feedback (list[str])."
)


def run_reviewer_agent(code: CodeArtifact) -> QAReport:
    result = run_tests(code.implementation_code, code.test_code)
    output = result.stdout + result.stderr

    client = OpenAI()
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Code:\n{code.implementation_code}\n\nTests:\n{code.test_code}\n\nPytest output:\n{output}",
            },
        ],
    )
    verdict = json.loads(resp.choices[0].message.content)

    passed_count = len(re.findall(r" PASSED", output))
    failed_count = len(re.findall(r" FAILED", output))
    # Deterministic: only the real pytest exit code decides pass/fail.
    tests_passed = result.exit_code == 0 and not result.timed_out

    return QAReport(
        tests_passed=tests_passed,
        total_tests=passed_count + failed_count,
        failed_tests=failed_count,
        execution_output=output,
        review_feedback=verdict.get("review_feedback", []),
        status="PASSED" if tests_passed else "NEEDS_REVISION",
    )
