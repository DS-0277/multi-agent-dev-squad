"""Product & Requirements Engineer agent."""
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.schemas import SpecArtifact

load_dotenv()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "You are a Product Spec Agent. Turn the user's request into a technical "
    "specification. Focus strictly on edge cases, assertions and architecture. "
    "Reply with JSON having keys: feature_name (str), requirements (list[str]), "
    "test_cases (list[str]), interfaces (str)."
)


def run_spec_agent(user_request: str) -> SpecArtifact:
    client = OpenAI()
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ],
    )
    return SpecArtifact.model_validate_json(resp.choices[0].message.content)
