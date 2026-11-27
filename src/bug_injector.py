"""Adversarial bug injection: mechanically break the Coder's first-pass code.

Instead of asking an LLM to write a bug (unreliable: the bug may slip past the
tests), flip one operator in the correct code and keep only a flip that makes
the Coder's own tests fail. The first pass is therefore guaranteed to fail.
"""
import ast
import copy

from src.sandbox import run_tests
from src.schemas import CodeArtifact

MAX_ATTEMPTS = 25

_COMPARE_SWAPS = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}
_BINOP_SWAPS = {ast.Add: ast.Sub, ast.Sub: ast.Add}
_SYMBOLS = {
    ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==",
    ast.NotEq: "!=", ast.Add: "+", ast.Sub: "-",
}


def _sites(tree: ast.AST) -> list[ast.AST]:
    nodes = list(ast.walk(tree))
    compares = [n for n in nodes
                if isinstance(n, ast.Compare) and type(n.ops[0]) in _COMPARE_SWAPS]
    binops = [n for n in nodes
              if isinstance(n, ast.BinOp) and type(n.op) in _BINOP_SWAPS]
    return compares + binops


def _mutate(source: str, index: int) -> tuple[str, str] | None:
    tree = ast.parse(source)
    sites = _sites(tree)
    if index >= len(sites):
        return None
    node = sites[index]
    if isinstance(node, ast.Compare):
        old = type(node.ops[0])
        new = _COMPARE_SWAPS[old]
        node.ops[0] = new()
    else:
        old = type(node.op)
        new = _BINOP_SWAPS[old]
        node.op = new()
    description = (
        f"Flipped `{_SYMBOLS[old]}` to `{_SYMBOLS[new]}` on line {node.lineno}"
    )
    return ast.unparse(tree), description


def inject_logic_bug(code: CodeArtifact) -> tuple[CodeArtifact, str]:
    """Return (buggy_code, description). Falls back to unchanged code."""
    try:
        total = len(_sites(ast.parse(code.implementation_code)))
    except SyntaxError:
        return code, "No bug injected (code did not parse)"

    # Baseline: only inject into code that currently passes its own tests,
    # otherwise a failure could come from broken tests rather than our bug.
    baseline = run_tests(code.implementation_code, code.test_code)
    if baseline.exit_code != 0:
        return code, "No bug injected (first pass already fails on its own)"

    for index in range(min(total, MAX_ATTEMPTS)):
        mutated = _mutate(copy.copy(code.implementation_code), index)
        if mutated is None:
            break
        source, description = mutated
        result = run_tests(source, code.test_code)
        if result.exit_code != 0 and not result.timed_out:
            return code.model_copy(update={"implementation_code": source}), description
    return code, "No bug injected (no operator flip was caught by the tests)"
