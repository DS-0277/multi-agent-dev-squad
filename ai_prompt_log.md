# AI Prompt Log

## Step 2: Initial AI Draft

- **Date:** 2026-11-26
- **Tool:** Claude Code (Claude Sonnet 5.5)
- **Approach:** The assignment's sample prompt was used with small adaptations. No extra security or hardening instructions were added, so the draft could be audited honestly in Step 3. The draft was committed unmodified.

### Adaptations to the sample prompt
- Orchestration framework: LangGraph (`StateGraph`).
- API key read from `.env` via `python-dotenv`; model name configurable via `OPENAI_MODEL` (default `gpt-4o-mini`).

### Prompt used

```text
You are a Principal AI Agent Architect specializing in autonomous multi-agent software engineering systems.
Build a production-ready, 3-agent software development squad in Python 3.11+ that iteratively writes, tests, and refines code until test suites pass.

Architecture & Requirements:

1. Structured State & Communication Schemas (src/schemas.py):
   - `SpecArtifact`: feature_name (str), requirements (list[str]), test_cases (list[str]), interfaces (str).
   - `CodeArtifact`: implementation_code (str), test_code (str), iteration: int.
   - `QAReport`: tests_passed (bool), total_tests (int), failed_tests (int), execution_output (str), review_feedback (list[str]), status (Literal["PASSED", "NEEDS_REVISION", "MAX_CYCLES_EXCEEDED"]).

2. The 3 Specialized Agents (src/agents/):
   - Spec Agent: Ingests user request, outputs a strongly typed `SpecArtifact`. Focuses strictly on edge cases, assertions, and architecture.
   - Coder Agent: Ingests `SpecArtifact` and optional previous `QAReport`. Generates `solution.py` and `test_solution.py` as a `CodeArtifact`.
   - Reviewer/QA Agent: Ingests `CodeArtifact`, runs tests via the sandbox runner, inspects syntax, and outputs a `QAReport`.

3. Sandboxed Execution Engine (src/sandbox.py):
   - Safely executes the generated code and pytest test file using an isolated Python `subprocess.run()`.
   - Enforce security constraints: 10-second execution timeout, isolated temporary working directory (`tempfile.TemporaryDirectory`), and capture of stdout, stderr, and exit codes.

4. Orchestration Loop (src/orchestrator.py):
   - Coordinate the agents: Spec Agent -> Coder Agent -> QA Agent -> [If FAIL -> back to Coder Agent with QA feedback].
   - Enforce a strict termination bound: `max_iterations = 4`. If tests do not pass after 4 attempts, terminate with `status="MAX_CYCLES_EXCEEDED"` and log the failure trace.
   - Prevent token bloat: Agents must exchange structured Pydantic summaries, NOT raw cumulative message histories.

Provide clean, modular, typed code split across the designated files.
```

### Files generated (unaudited draft)
`src/schemas.py`, `src/sandbox.py`, `src/agents/spec_agent.py`, `src/agents/coder_agent.py`, `src/agents/reviewer_agent.py`, `src/orchestrator.py`

---

## Step 3: Audit Findings

Draft under audit: commit `6baded5`. Result: **2 defects found and fixed, 2 areas good with no defect.**
Evidence came from a demo script that ran the draft before and after the fixes (a dummy key `sk-FAKE-for-demo` and a mocked LLM were used, so no real key and no API cost).

| # | Audit area | Status |
|---|---|---|
| 1 | Arbitrary code execution & sandbox escapes | Defect found, fixed |
| 2 | Context bloat & scratchpad accumulation | Good, no defect found |
| 3 | Agent collusion / sycophancy trap | Defect found, fixed |
| 4 | Infinite refinement loops | Good, no defect found |

### 1. Arbitrary code execution: DEFECT FOUND, FIXED

**Problem.** The draft already avoided `shell=True`, used a list of arguments, a 10s timeout and a `TemporaryDirectory`. But `subprocess.run` had no `env=` argument, so the child process inherited the parent's full environment. The app loads `.env` with `load_dotenv()`, so `OPENAI_API_KEY` was visible to the AI-generated code. A single `os.environ["OPENAI_API_KEY"]` in generated code could read or leak it.

**Evidence (before).** A sandboxed test asserting the key was invisible failed: the dummy key was readable inside the sandbox.

**Before (`src/sandbox.py`):**
```python
proc = subprocess.run(
    [sys.executable, "-m", "pytest", "test_solution.py", "-v"],
    cwd=tmp, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
)
```

**After:**
```python
SAFE_ENV = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}

proc = subprocess.run(
    [sys.executable, "-m", "pytest", "test_solution.py", "-v",
     "-p", "no:cacheprovider"],
    cwd=tmp, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
    shell=False, env=SAFE_ENV,
)
```

**Evidence (after).** The same check passes: the key is invisible inside the sandbox.

**Known limit.** This hides secrets but is not a full jail: generated code could still read ordinary files or use the network. Full isolation would need containers (Docker); documented as a boundary in the README.

### 2. Context bloat: GOOD, NO DEFECT FOUND

The Coder receives only the `SpecArtifact`, its latest `CodeArtifact`, and the latest `QAReport` (see `coder_agent.py`). Old iterations are never sent to the LLM. The draft's `history` list in the orchestrator state was unused clutter that never reached an LLM; it was removed as housekeeping.

### 3. Sycophancy trap: DEFECT FOUND, FIXED

**Problem.** In `reviewer_agent.py`, `tests_passed` came from the LLM's JSON answer, not from pytest. If the tests failed but the LLM said "looks great", the build was approved.

**Evidence (before).** A mocked LLM replying `tests_passed: true` with a genuinely failing test (`assert f() == 2`) produced `tests_passed = True, status = PASSED`.

**Before:**
```python
tests_passed = bool(verdict["tests_passed"])
```

**After:**
```python
# Deterministic: only the real pytest exit code decides pass/fail.
tests_passed = result.exit_code == 0 and not result.timed_out
```
The reviewer prompt was also changed so the LLM only returns `review_feedback` (critique notes) and never decides pass/fail.

**Evidence (after).** The same mocked lying LLM now yields `tests_passed = False, status = NEEDS_REVISION`.

### 4. Infinite refinement loops: GOOD, NO DEFECT FOUND

The orchestrator increments `iteration` in the coder node, and `qa_node` sets `MAX_CYCLES_EXCEEDED` whenever tests fail at `iteration >= MAX_ITERATIONS` (4), after which the graph routes to `END`. Automated proof (Test 6, exactly 4 iterations) comes in Step 5.
