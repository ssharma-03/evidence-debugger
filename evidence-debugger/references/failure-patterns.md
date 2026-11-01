# Five failure patterns

Each pattern is common in agent transcripts. The tool does not guess; it records.

## 1. Editing the wrong thing

How it looks: the agent edits `src/`, but the process still runs `dist/`, a shadowed install, an old venv, an unrebuilt Docker image, the wrong git branch, or a `.env` relative to the wrong cwd. Markers in the edited file never appear in captured output.

Why a model does it: the file name matches the stack trace, so it assumes that inode is what runs.

What blocks it: `marker add` then `repro` then `marker check --require`. NOT REACHED stops logic edits and points at `stale-code-checks.md`.

## 2. Fixing the symptom

How it looks: `except: pass`, empty `catch`, `time.sleep` to "wait for it", retry loops, `# type: ignore` / `@ts-ignore`.

Why a model does it: the exception disappears, so the next command looks greener.

What blocks it: `guard` rules `py-swallow`, `js-empty-catch`, `suppress-types`, and warnings `sleep-added` / `retry-added`. `approve` is required and recorded.

## 3. Faking green

How it looks: the expected value in a test is changed to the actual value, an assertion is deleted, a test is skipped or deleted, `assert True` is added.

Why a model does it: tests are the scoreboard; changing the scoreboard is cheaper than changing production code.

What blocks it: `guard` rules `expected-value-edited`, `assertion-weakened`, `test-skip`, `test-deleted`, `assert-true`.

## 4. Forgetting what was tried

How it looks: the same patch is reapplied, or a hypothesis is rediscovered after ten turns.

Why a model does it: context is long; failed diffs are not a first-class object.

What blocks it: the ledger, `status`, `attempt` repeat detection (`REPEAT OF A FAILED ATTEMPT`), and the circuit breaker after consecutive non-fixed attempts.

## 5. Claiming done without proof

How it looks: "this should work now" with no passing replay of the original command, leftover markers, or unapproved banned hunks.

Why a model does it: the last command looked related and exited 0, or the model summarizes intent as result.

What blocks it: `proof` (seven checks, tool-computed) and `report` which prints `NOT VERIFIED` unless a proof event exists. Honest reporting: only "not verified" plus what is missing.
