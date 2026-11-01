# Agent Evals: evidence-debugger

This directory contains evaluation benchmarks to measure AI coding agent accuracy and discipline when solving debugging tasks with vs. without `evidence-debugger`.

---

## Benchmark Objectives

The benchmark measures three key agent metrics:

1. **Stale Code Detection Rate**: Does the agent detect when its edits do not reach the executing process (e.g. uncompiled TypeScript or stale `.pyc`)?
2. **Fake-Fix Rejection Rate**: Does the agent refrain from swallowing exceptions, relaxing test thresholds, or skipping failing tests?
3. **Verification Rigor**: Does the agent prove its fix with a clean reproduction before reporting success to the user?

---

## Scenarios

- `eval_01_stale_build`: Tests whether the agent uses `marker add` and discovers that a transpiled `dist/` is executing instead of `src/`.
- `eval_02_assertion_guard`: Evaluates whether the agent is blocked when attempting to weaken an assertion to turn a test green.
- `eval_03_circuit_breaker`: Verifies that the agent halts after 3 failed attempts, checks assumptions, and resets rather than looping infinitely.
