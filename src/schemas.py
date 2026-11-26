"""Structured artifacts exchanged between agents."""
from typing import Literal

from pydantic import BaseModel


class SpecArtifact(BaseModel):
    feature_name: str
    requirements: list[str]
    test_cases: list[str]
    interfaces: str


class CodeArtifact(BaseModel):
    implementation_code: str
    test_code: str
    iteration: int


class QAReport(BaseModel):
    tests_passed: bool
    total_tests: int
    failed_tests: int
    execution_output: str
    review_feedback: list[str]
    status: Literal["PASSED", "NEEDS_REVISION", "MAX_CYCLES_EXCEEDED"]
