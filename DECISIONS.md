# Decisions

Judgement calls made while building evidence-debugger 1.0.0. Safer option chosen when the prompt was ambiguous.

## Process

1. Implement core libraries in prompt order with tests before CLI polish.
2. Treat this workspace `.git` as unrelated; tests create their own temp git repos.
3. LICENSE uses copyright `{{AUTHOR}}` and year `{{YEAR}}` as specified; README documents replacing them before first release.

## Compatibility

1. Target Python 3.8 syntax: `typing.Optional`/`List`/`Dict`/`Tuple`, no `match`, no runtime `X | Y`, no walrus-required logic. `from __future__ import annotations` is used.
2. `Path.is_relative_to` is not used (3.9+). Containment uses `Path.relative_to` in a try/except.
3. `subprocess.run(capture_output=...)` is avoided; stdout/stderr pipes are used so 3.8 stays valid.
4. `compile()` is never called on user strings as code. `py_compile.compile` is used only to verify marker insertion did not break a `.py` file, then the original bytes are restored on failure.



## Paths and filesystem

1. User path arguments are `resolve()`d and must stay inside the project root after symlink follow. `.git/` is never a legal user target. Marker operations also refuse `.debug/`.
2. The tool writes only under `<root>/.debug/` plus its own marker lines in in-root source files. The installer is the only component that writes outside a debug session root.
3. If git is missing, root is cwd (or `--root`). Snapshot-based diffs are used. Missing git never fails init/guard.
4. Python continuation refusal does **not** treat a trailing `:` as a continuation operator, because suite headers (`if`, `def`, `class`) end with `:` and inserting a marker on the next line is valid.
5. Ledger lock: `fcntl.flock` on POSIX, `msvcrt.locking` on Windows, `O_EXCL` lockfile with 30s stale timeout as fallback.
6. Corrupted JSONL: skip any unparsable line; print one warning. If the last line is partial, continue. Safer than aborting the session.
7. Created ledger/lock/log files use mode `0o600` on POSIX. `.debug` directory uses `0o700`.
8. Snapshot skips binaries (NUL in first 8KiB or known binary extensions), `node_modules`, `.venv`, `venv`, `dist`, `build`, `.next`, `target`, `__pycache__`, `.debug`, `.git`. Max 500 files, 256 KiB each; overflow is a warning and partial guard coverage, not a hard fail.



## Runner and safety

1. Git subprocesses (`rev-parse`, `diff`, `status`) are local and allowed. `git push` is denylisted in repro commands.
2. Windows process-tree kill uses `taskkill /T /F /PID` as specified (not network).
3. Denylist matches argv tokens and, for `bash/sh/zsh/cmd/powershell/pwsh -c`, the inner string. Error text names the matched rule id.
4. `--allow-unsafe` is recorded on the ledger. The skill tells the agent not to pass it without user approval; the tool cannot cryptographically prove approval for this flag, so it records use (visibility).
5. Timeout is never recorded as success. Kill SIGTERM then wait 3s then SIGKILL on POSIX.
6. If a single argument after `--` contains spaces, `shlex.split` is used (`posix=False` on Windows) and surrounding quotes are stripped.
7. Repro env inherits the parent and only adds `NO_COLOR=1` and `PYTHONUNBUFFERED=1`. stdin is `DEVNULL`.



## Guard, breaker, proof

1. Guard is a recorded guardrail, not an unbreakable lock. `approve` records user approval. README and SECURITY state this explicitly.
2. `expected-value-edited` compares removed vs added assertion lines after replacing numeric and quoted-string literals with a placeholder.
3. `assertion-weakened` fires when a test file loses an assertion-like line and no equivalent assertion-like line is added in the same file hunk.
4. Circuit breaker counts consecutive attempts whose computed outcome is not `fixed`. Default limit 3. After ack, the consecutive counter resets but a trip counter remains so a second trip (6 non-fixed attempts) enables `escalate` as the only productive next step.
5. `breaker ack` requires: `breaker show` has been run since the current trip, and at least two `assumption add` events exist that reference real run ids.
6. Proof check 2 uses filesystem mtimes of files recorded on attempts plus git/snapshot changed files vs the latest passing baseline-command run.
7. `--cause` must be >= 30 characters and must not equal any attempt `--change` text (stripped case-sensitive).
8. `--also` values are command strings split with `shlex` and executed with the same denylist as repro.



## Installer, doctor, packaging

1. Doctor allows `.installed-by.json` in an installed skill copy (installer artifact) and ignores `__pycache__`. Any other extra file is a problem.
2. Dest directory name must be `evidence-debugger`. Identical install is a no-op exit 0.
3. Zip timestamps are 2020-01-01 00:00:00 UTC, entries sorted, Unix perms 0644/0755 for `scripts/ed.py`.
4. Workflow third-party actions use version tags plus the only allowed TODO: `# TODO(pin-sha): replace tag with full commit SHA before first release`.
5. `which -a` on POSIX and `where` on Windows for envinfo; missing tools are omitted, not errors.
6. Color is ASCII-only and used only when stdout is a TTY and `NO_COLOR` is unset. CI and `--json` stay uncolored.
7. Untrusted captured output is never parsed as commands. Injection test asserts the payload is only printed between delimiters.
8. `status --markdown` writes `.debug/ledger.md` from JSONL and does not read that markdown back.
9. Marker `register` records a manually placed token so `check`/`proof` can track it; remove still only deletes exact generated lines.
10. Tests add `evidence-debugger/scripts` to `sys.path` and import `edlib`; they never import the hyphenated folder as a package.
11. Eval 05 is skipped in e2e with a clear message if `node` is not on PATH.
12. Network scan flags forbidden imports and `shell=True` / `eval(` / `exec(` / `os.system` / `pickle` in `evidence-debugger/` only (repo tests and installer may use `unittest` subprocess, not those modules).
13. `install.sh` is a quoted POSIX wrapper; shellcheck is run if the binary exists, otherwise documented as not run.
14. Root LICENSE and skill LICENSE are both MIT with `{{AUTHOR}}` / `{{YEAR}}`.
15. Human errors always start with `ed: error:` . Tracebacks only when `ED_DEBUG=1`.
16. Baseline is the first recorded failing repro after init. A passing first repro is not recorded (exit 2).
17. Repeat-attempt detection hashes the sorted changed-file set plus unified diff text of that attempt.
18. Proof failure prints exactly `not verified:`  plus comma-separated failed check names.
19. No telemetry, hooks, or editor settings files are written.
20. When a prompt rule could be implemented as either a hard fail or a warning, BLOCK is used only for the listed banned-fix rules; everything else prefers refuse-with-exit-2 over silent continue.

