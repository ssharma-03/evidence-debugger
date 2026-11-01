# Hypothesis Playbook

A structured guide for creating, evaluating, and disproving hypotheses during a debugging session.

---

## 1. Principles of Falsifiable Hypotheses

Never fix a bug by guessing. A valid hypothesis must fulfill three criteria:

1. **Concrete Condition**: Identifies the specific trigger or state anomaly.
2. **Specific Prediction**: Predicts exactly what observable behavior changes under test conditions.
3. **Falsification Test**: A command or targeted probe that can definitively prove the hypothesis *wrong*.

### Good vs. Bad Hypotheses

| Bad (Vague / Unfalsifiable) | Good (Falsifiable & Specific) |
|---|---|
| "The database call is broken." | "Query times out when payload exceeds 1MB because socket buffer is 64KB." |
| "Maybe there is a race condition." | "Thread B writes to shared dict before Thread A acquires mutex." |
| "Authentication is failing." | "JWT expiry calculation uses milliseconds instead of seconds, triggering 401." |
| "We should add a sleep to fix it." | "Async event listener is registered after event emitter fires initial ready state." |

---

## 2. Hypothesis Commands

Formulate 2–3 competing hypotheses before altering production code:

```bash
python3 scripts/ed.py hypo add \
  --text "JWT expiry calculation uses milliseconds instead of seconds" \
  --predicts "Decoding token in repro with future epoch will exit 0" \
  --disprove "Passing an unexpired token still returns 401"
```

### Testing and Resolving

Run the disprove probe:
```bash
python3 scripts/ed.py repro -- <probe command>
```

Then resolve the hypothesis based on actual evidence:

```bash
# If the hypothesis was proven false:
python3 scripts/ed.py hypo resolve H1 --status disproved --run R2 --evidence "Passing fresh unexpired token still exited with 401"

# If the hypothesis survived testing:
python3 scripts/ed.py hypo resolve H2 --status survived --run R3 --evidence "Overriding expiry calculation fixed token validation cleanly"
```

---

## 3. The 3-Hypothesis Rule

When faced with an unfamiliar bug, generate at least three distinct possibilities across different layers:

1. **Input / Boundary Layer**: Bad formatting, unexpected types, boundary integers, null/undefined payloads.
2. **State / Timing Layer**: Stale cache, race conditions, unordered async promises, unhandled mutation.
3. **Environment / Configuration Layer**: Missing environment variable, mismatched library version, architecture difference.

Only apply a code change to the codebase after at least one hypothesis has survived its falsification test.
