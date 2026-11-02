# evidence-debugger

> **A deterministic runtime harness and scientific debugging skill for AI coding agents.**  
> Stops hallucination loops, proves code execution paths, blocks fake fixes, and requires empirical verification before claiming done.

---

## 1. Why evidence-debugger?

Autonomous AI coding agents frequently fail at non-trivial debugging tasks due to four well-documented failure patterns:

1. **Editing Stale Code**: The agent modifies `src/index.ts` while Node executes `dist/index.js`, or edits a module while Python runs cached `.pyc` bytecode or a separate virtual environment.
2. **Fake-Fixing & Scoreboard Tampering**: When frustrated by repeated test failures, LLMs often delete tests, weaken assertions (`assert True`), swallow errors with `except: pass`, or inject arbitrary `time.sleep` statements.
3. **Infinite Guess Loops**: Agents loop through speculative code edits without testing hypotheses or tracking past failures, burning context and tokens.
4. **Premature Victory**: The agent runs an unrelated command that exits 0 and prematurely announces that the bug is resolved.

`evidence-debugger` transforms this dynamic by giving the agent an **external immutable ledger (`.debug/ledger.jsonl`)** and **deterministic guardrails**.

---

## 2. Strengths & Limitations

### Core Strengths (What It Excels At)
- **Zero External Dependencies**: Implemented in 100% standard-library Python (3.8+). No `pip install` required.
- **Physical Code Path Verification**: Marker injection (`marker add` / `marker check`) proves that the edited line is actually hit during execution before touching any logic.
- **Banned-Fix Detection**: Scans AST & unified diffs to block 8 common agent "cheat" patterns (swallowed exceptions, deleted tests, weakened assertions, skipped tests).
- **Token-Saving Circuit Breaker**: Automatically trips after 3 non-fixed attempts, forcing the agent to question assumptions instead of burning context in an infinite loop.
- **Strict Verification Gating**: The agent cannot claim a bug is fixed until 7 rigorous checks pass (reproduced failure baseline, passing final repro, modified source mtimes, survived hypothesis, explicit root cause).
- **Automated Credential Redaction**: Automatically scrubs API keys, AWS tokens, JWTs, and passwords from captured outputs before writing to disk.

### Limitations & When NOT to Use
- **Do NOT use for trivial 1-line syntax errors**: If a compiler error states `SyntaxError: invalid syntax line 4`, using a 5-step evidence debugger adds unnecessary overhead.
- **Interactive commands not supported**: Repro commands execute with `stdin=DEVNULL`. Commands requiring interactive terminal prompts must be non-interactive (e.g. `npm test -- --watchAll=false`).
- **Cannot cryptographically force a human**: The `--allow-unsafe` and `approve` flags are recorded in the ledger for visibility and transparency; they are designed as guardrails for agents, not an OS-level sandbox.

---

## 3. Installation Guide

### Universal Installer (Automated)

```bash
git clone https://github.com/ssharma-03/evidence-debugger.git
cd evidence-debugger

# Install to default agent skill directory (~/.gemini/antigravity/skills/evidence-debugger)
./install.sh

# Or install to a custom target:
./install.sh ~/.cursor/skills/evidence-debugger
# or
./install.sh .skills/evidence-debugger
```

### Installation by Platform

| Environment | Target Directory | How to Install |
|---|---|---|
| **Google Antigravity** | `~/.gemini/antigravity/skills/evidence-debugger` | Run `./install.sh` or copy `evidence-debugger/` |
| **Cursor IDE** | `<project>/.cursor/skills/evidence-debugger` | `./install.sh .cursor/skills/evidence-debugger` |
| **Claude Code** | `~/.claude/skills/evidence-debugger` | `./install.sh ~/.claude/skills/evidence-debugger` |
| **Cline / Roo Code** | `<project>/.skills/evidence-debugger` | Copy `evidence-debugger/` into workspace `.skills/` |
| **CI / Standalone CLI** | Anywhere on `$PATH` | Add `evidence-debugger/scripts` to `PATH` |

---

## 4. Complete Agent Workflow

When an agent encounters a broken test or failing command, it follows this 6-step lifecycle:

```mermaid
flowchart TD
    A["Failing Test / Bug Encountered"] --> B["1. Record Baseline: ed.py init && ed.py repro -- pytest"]
    B --> C["2. Verify Code Path: ed.py marker add && marker check"]
    C -->|Marker NOT REACHED| D["STOP! Check build steps, virtualenvs, or caches"]
    C -->|Marker REACHED| E["3. Formulate Hypotheses: ed.py hypo add"]
    E --> F["4. Apply One Fix & Test: ed.py attempt"]
    F -->|Breaker Trips (3 fails)| G["Halt! Question Assumptions: breaker ack"]
    F -->|Repro Passes| H["5. Verify Proof: ed.py proof --cause ..."]
    H --> I["6. Output Verified Report: ed.py report"]
```

### Command Reference

```bash
# 1. Initialize session and record baseline failure
python3 <skill>/scripts/ed.py --root . init
python3 <skill>/scripts/ed.py --root . repro -- pytest tests/test_payment.py

# 2. Verify code path with a marker (stops editing wrong files)
python3 <skill>/scripts/ed.py --root . marker add --file src/payment.py --line 45
python3 <skill>/scripts/ed.py --root . repro -- pytest tests/test_payment.py
python3 <skill>/scripts/ed.py --root . marker check --require

# 3. Formulate falsifiable hypotheses
python3 <skill>/scripts/ed.py --root . hypo add \
  --text "Currency conversion truncates cents due to integer division" \
  --predicts "Using Decimal avoids ZeroDivisionError" \
  --disprove "Passing float still produces invalid balance"

# Run probe, then resolve:
python3 <skill>/scripts/ed.py --root . hypo resolve H1 --status survived --run R2 --evidence "Decimal calculation resolved truncation"

# 4. Apply fix and test outcome
python3 <skill>/scripts/ed.py --root . repro -- pytest tests/test_payment.py
python3 <skill>/scripts/ed.py --root . attempt --hypo H1 --change "Used Decimal instead of int in currency calc"

# 5. Check guardrails and prove the fix
python3 <skill>/scripts/ed.py --root . guard
python3 <skill>/scripts/ed.py --root . proof --cause "Integer division in currency helper caused zero divisor"
python3 <skill>/scripts/ed.py --root . report
```

---

## 5. Security & Safety Constraints

- **Path Confinement**: All user paths are resolved and confined within the project root. Symlink escapes and access to `.git/` are strictly blocked.
- **Dangerous Command Denylist**: Commands matching destructive patterns (`sudo`, `mkfs`, `shutdown`, `reboot`, `git push`) are blocked by default.
- **Secret Redaction**: Stdout and stderr streams are scanned and redacted before being persisted to the ledger (masks AWS, OpenAI, GitHub, Anthropic, Slack, Stripe tokens, private keys, and URLs with passwords).
- **No Network Telemetry**: `evidence-debugger` makes zero network requests, sends no telemetry, and requires no cloud connection.

---

## 6. Verification & Self-Test

```bash
# Verify skill environment and SHA256 checksums
python3 evidence-debugger/scripts/ed.py doctor

# Run full test suite (118 unit tests)
python3 -m unittest discover -s tests
```

---

## 7. License

[MIT](LICENSE) © 2026 ssharma-03
