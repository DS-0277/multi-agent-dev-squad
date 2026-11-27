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


class SandboxTimeoutError(Exception):
    """Raised when sandboxed code exceeds the execution time limit."""


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


def _execute(args: list[str], cwd: str, timeout: int = TIMEOUT_SECONDS) -> SandboxResult:
    """Run a command (list form, never a shell) and raise on timeout.

    subprocess.run kills the child process when the timeout expires.
    """
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            env=SAFE_ENV,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxTimeoutError(
            f"Execution timed out after {timeout}s "
            "(possible infinite loop or deadlock)."
        ) from exc
    return SandboxResult(proc.returncode, proc.stdout, proc.stderr)


def run_python(code: str, timeout: int = TIMEOUT_SECONDS) -> SandboxResult:
    """Run a Python snippet in an isolated temp dir. Raises SandboxTimeoutError."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "main.py").write_text(code)
        return _execute([sys.executable, "main.py"], tmp, timeout)


def run_tests(implementation_code: str, test_code: str) -> SandboxResult:
    """Run pytest on generated code. A timeout is returned as a flagged result."""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "solution.py").write_text(implementation_code)
        Path(tmp, "test_solution.py").write_text(test_code)
        try:
            return _execute(
                [sys.executable, "-m", "pytest", "test_solution.py", "-v",
                 "-p", "no:cacheprovider"],
                tmp,
            )
        except SandboxTimeoutError as exc:
            return SandboxResult(-1, "", str(exc), timed_out=True)
