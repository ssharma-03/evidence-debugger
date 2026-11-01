# evidence-debugger

> **A deterministic runtime harness and scientific debugging skill for AI coding agents.**  
> Stops hallucination loops, proves code execution paths, blocks fake fixes, and requires empirical verification before claiming done.

---

## Why evidence-debugger?

Autonomous AI coding agents often fail at non-trivial debugging tasks due to well-documented behavioral traps:

1. **Editing Stale Code**: The agent modifies `src/index.ts` while Node runs `dist/index.js`, or edits a file while Python runs shadowed bytecode or a separate virtualenv.
2. **Fake-Fixing & Test Weakening**: When frustrated by repeated test failures, LLMs frequently delete tests, relax assertion thresholds, swallow errors with `except: pass`, or add arbitrary `sleep` timeouts.
3. **Infinite Guess Loops**: Agents loop through speculative code edits without testing hypotheses or tracking past failures, burning context and tokens.
4. **Premature Victory**: The agent runs an unrelated command that exits 0 and prematurely announces that the bug is resolved.

`evidence-debugger` transforms this dynamic by giving the agent an external immutable ledger (`.debug/ledger.jsonl`) and deterministic guardrails.

---

## Core Capabilities

| Feature | What It Enforces |
|---|---|
| **Trace Markers** | Injects temporary `EDBG` tokens into source code to verify that the edited file is actually the one executed. |
| **Banned-Fix Guard** | Scans AST & git diffs to detect and block swallowed exceptions, deleted tests, weakened assertions, and skipped suites. |
| **Circuit Breaker** | Trips after 3 consecutive non-fixed attempts. Forces the agent to explicitly state assumptions against real run IDs before proceeding. |
| **Proof Engine** | Requires 7 empirical proofs (clean baseline repro, passing final repro, modified source mtimes, survived hypothesis, explicit root cause) before permitting a fix claim. |
| **Redaction & Safety** | Automatically strips API tokens, AWS secrets, and database credentials from captured stdout/stderr before logging to the ledger. |

---

## Installation

### For AI Agents & Humans (Universal Installer)

```bash
# Clone the repository
git clone https://github.com/{{AUTHOR}}/evidence-debugger.git
cd evidence-debugger

# Install to default agent skill directory (~/.gemini/antigravity/skills/evidence-debugger)
./install.sh

# Or install to a custom path (e.g., Cursor, Claude Code, or project root):
./install.sh /path/to/.cursor/skills/evidence-debugger
```

### Manual Install

Simply copy the `evidence-debugger/` folder to your target agent skill path:
- **Antigravity**: `~/.gemini/antigravity/skills/evidence-debugger`
- **Cursor / Claude Code**: `.cursor/skills/evidence-debugger` or `~/.claude/skills/evidence-debugger`
- **Workspace-local**: `<project_root>/.skills/evidence-debugger`

---

## Agent Debugging Workflow

When an agent encounters a broken test or failing command, it activates the skill and runs:

```bash
# 1. Initialize session and record baseline failure
python3 <skill_path>/scripts/ed.py --root . init
python3 <skill_path>/scripts/ed.py --root . repro -- pytest tests/test_payment.py

# 2. Verify code path with a marker (stops editing wrong files)
python3 <skill_path>/scripts/ed.py --root . marker add --file src/payment.py --line 45
python3 <skill_path>/scripts/ed.py --root . repro -- pytest tests/test_payment.py
python3 <skill_path>/scripts/ed.py --root . marker check --require

# 3. Formulate falsifiable hypotheses
python3 <skill_path>/scripts/ed.py --root . hypo add \
  --text "Payment currency conversion truncates cents due to integer division" \
  --predicts "Passing integer cents avoids ZeroDivisionError" \
  --disprove "Passing float still produces invalid balance"

# 4. Apply fix and test outcome
python3 <skill_path>/scripts/ed.py --root . repro -- pytest tests/test_payment.py
python3 <skill_path>/scripts/ed.py --root . attempt --hypo H1 --change "Used Decimal instead of int for currency calc"

# 5. Verify proof before claiming success
python3 <skill_path>/scripts/ed.py --root . guard
python3 <skill_path>/scripts/ed.py --root . proof --cause "Integer division in currency helper caused zero divisor"
python3 <skill_path>/scripts/ed.py --root . report
```

---

## Verification & Integrity

Run the built-in self-test and doctor check:

```bash
# Verify skill environment and checksums
python3 evidence-debugger/scripts/ed.py doctor

# Run full test suite (118 tests)
python3 -m unittest discover -s tests
```

---

## License

[MIT](LICENSE) © {{YEAR}} {{AUTHOR}}
