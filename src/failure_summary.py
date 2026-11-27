"""Condense raw pytest output into a short "error diff" for the Coder Agent."""
import re

MAX_SUMMARY_CHARS = 2500
UNKNOWN_FAILURE = "<run error before tests could execute>"

_VERBOSE_FAIL = re.compile(r"test_solution\.py::(\S+)\s+(?:FAILED|ERROR)")
_SUMMARY_FAIL = re.compile(r"^(?:FAILED|ERROR) test_solution\.py::(\S+)")


def failing_tests(output: str) -> list[str]:
    """Names of failing tests found in pytest output (sorted, de-duplicated)."""
    names: set[str] = set()
    for line in output.splitlines():
        for pattern in (_VERBOSE_FAIL, _SUMMARY_FAIL):
            match = pattern.search(line)
            if match:
                names.add(match.group(1))
    return sorted(names)


def summarize_failures(output: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    """Keep only what the Coder needs: failing tests and their error lines."""
    kept: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if (
            line.startswith(("FAILED ", "ERROR "))
            or line.startswith("E ")
            or "timed out" in stripped
            or "Error" in stripped and stripped.startswith(("File", "SyntaxError"))
        ):
            kept.append(line.rstrip())
    text = "\n".join(kept) if kept else output[-max_chars:]
    return text[:max_chars]
