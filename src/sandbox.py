"""Runs generated code and pytest tests in a subprocess."""
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_SECONDS = 10

# Minimal environment for generated code: no API keys or other secrets.
SAFE_ENV = {
    "PATH": "/usr/bin:/bin",
    "PYTHONDONTWRITEBYTECODE": "1",
}


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def run_tests(implementation_code: str, test_code: str) -> SandboxResult:
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "solution.py").write_text(implementation_code)
        Path(tmp, "test_solution.py").write_text(test_code)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "test_solution.py", "-v",
                 "-p", "no:cacheprovider"],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                shell=False,
                env=SAFE_ENV,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(-1, "", "Timed out", timed_out=True)
        return SandboxResult(proc.returncode, proc.stdout, proc.stderr)
