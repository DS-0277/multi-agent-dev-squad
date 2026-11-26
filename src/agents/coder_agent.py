"""Implementation & test suite generator agent."""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.schemas import CodeArtifact, QAReport, SpecArtifact

load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "You are a Coder Agent. Write clean, modular Python 3.11 code for the spec. "
    "Produce solution.py and test_solution.py (pytest; import from solution). "
    "Reply with JSON having keys: implementation_code (str), test_code (str). "
    "If a previous QA report is given, fix the reported problems."
)


def run_coder_agent(
    spec: SpecArtifact,
    iteration: int,
    previous_code: CodeArtifact | None = None,
    previous_report: QAReport | None = None,
) -> CodeArtifact:
    user_content = f"Spec:\n{spec.model_dump_json(indent=2)}"
    if previous_code and previous_report:
        user_content += (
            f"\n\nPrevious code:\n{previous_code.implementation_code}"
            f"\n\nPrevious tests:\n{previous_code.test_code}"
            f"\n\nQA report:\n{previous_report.model_dump_json(indent=2)}"
        )
    client = OpenAI()
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    data = json.loads(resp.choices[0].message.content)
    return CodeArtifact(
        implementation_code=data["implementation_code"],
        test_code=data["test_code"],
        iteration=iteration,
    )
