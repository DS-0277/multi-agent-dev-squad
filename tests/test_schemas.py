"""Schema serialization and validation tests."""
import pytest
from pydantic import ValidationError

from src.schemas import CodeArtifact, QAReport, SpecArtifact


def valid_spec() -> dict:
    return {
        "feature_name": "TokenBucket",
        "requirements": ["thread-safe"],
        "test_cases": ["burst exhaustion"],
        "interfaces": "class TokenBucket: ...",
    }


def valid_report() -> dict:
    return {
        "tests_passed": True,
        "total_tests": 3,
        "failed_tests": 0,
        "execution_output": "3 passed",
        "review_feedback": [],
        "status": "PASSED",
    }


# ---------- Test 4: schema serialization and validation ----------
def test_valid_artifacts_round_trip_through_json():
    spec = SpecArtifact(**valid_spec())
    code = CodeArtifact(implementation_code="x = 1", test_code="def test(): pass", iteration=1)
    report = QAReport(**valid_report())
    for artifact in (spec, code, report):
        clone = type(artifact).model_validate_json(artifact.model_dump_json())
        assert clone == artifact


def test_spec_rejects_missing_field():
    data = valid_spec()
    del data["interfaces"]
    with pytest.raises(ValidationError):
        SpecArtifact(**data)


def test_spec_rejects_wrong_type():
    data = valid_spec()
    data["requirements"] = "not a list"
    with pytest.raises(ValidationError):
        SpecArtifact(**data)


def test_code_artifact_rejects_non_integer_iteration():
    with pytest.raises(ValidationError):
        CodeArtifact(implementation_code="x", test_code="y", iteration="first")


def test_qa_report_rejects_unknown_status():
    data = valid_report()
    data["status"] = "LOOKS_GOOD"
    with pytest.raises(ValidationError):
        QAReport(**data)


@pytest.mark.parametrize("status", ["PASSED", "NEEDS_REVISION", "MAX_CYCLES_EXCEEDED"])
def test_qa_report_accepts_each_allowed_status(status):
    data = valid_report()
    data["status"] = status
    assert QAReport(**data).status == status
