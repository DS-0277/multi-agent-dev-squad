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

_To be filled in during Step 3 (before/after for each audit area)._
