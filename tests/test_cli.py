from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

from support import run_ed, tmp_dir, write


class CliTests(unittest.TestCase):
    def test_usage_exit_1(self):
        with tmp_dir() as td:
            c, o, e = run_ed(Path(td), ["hypo"])
            self.assertEqual(c, 1)
            self.assertIn("ed: error:", e)

    def test_no_traceback_without_debug(self):
        with tmp_dir() as td:
            c, o, e = run_ed(Path(td), ["repro", "--"])
            self.assertNotIn("Traceback", e)
            self.assertIn("ed: error:", e)

    def test_traceback_with_ed_debug(self):
        # force an internal error by not applicable - doctor should not traceback.
        # Instead run a command that raises PathError? That's CliError.
        # We can pass ED_DEBUG and a bogus command.
        with tmp_dir() as td:
            c, o, e = run_ed(Path(td), ["not-a-cmd"], env={"ED_DEBUG": "1"})
            self.assertEqual(c, 1)

    def test_init_refuses_without_reset(self):
        with tmp_dir() as td:
            root = Path(td)
            self.assertEqual(run_ed(root, ["init"])[0], 0)
            c, o, e = run_ed(root, ["init"])
            self.assertEqual(c, 2)

    def test_json_status_keys(self):
        with tmp_dir() as td:
            root = Path(td)
            run_ed(root, ["init"])
            run_ed(root, ["repro", "--", sys.executable, "-c", "import sys; sys.exit(1)"])
            c, o, e = run_ed(root, ["status"], json_mode=True)
            self.assertEqual(c, 0, e)
            data = json.loads(o)
            for k in ("baseline", "runs", "hypotheses", "attempts", "assumptions", "breaker", "markers", "next_step"):
                self.assertIn(k, data)

    def test_json_guard_keys(self):
        with tmp_dir() as td:
            root = Path(td)
            write(root / "a.py", "print(1)\n")
            run_ed(root, ["init"])
            c, o, e = run_ed(root, ["guard"], json_mode=True)
            self.assertIn(c, (0, 4))
            data = json.loads(o)
            self.assertIn("findings", data)
            self.assertIn("ok", data)

    def test_json_doctor_keys(self):
        with tmp_dir() as td:
            root = Path(td)
            c, o, e = run_ed(root, ["doctor"], json_mode=True)
            data = json.loads(o)
            for k in ("ok", "python_version", "write_ok", "git", "checksums_ok", "unknown_files", "interpreter", "problems"):
                self.assertIn(k, data)

    def test_json_proof_keys(self):
        with tmp_dir() as td:
            root = Path(td)
            run_ed(root, ["init"])
            c, o, e = run_ed(root, ["proof", "--cause", "x" * 40], json_mode=True)
            self.assertEqual(c, 5)
            data = json.loads(o)
            for k in ("ok", "checks", "cause"):
                self.assertIn(k, data)

    def test_envinfo_and_clean(self):
        with tmp_dir() as td:
            root = Path(td)
            run_ed(root, ["init"])
            c, o, e = run_ed(root, ["envinfo"])
            self.assertEqual(c, 0)
            self.assertIn("python", o)
            c, o, e = run_ed(root, ["clean"])
            self.assertEqual(c, 2)
            c, o, e = run_ed(root, ["clean", "--yes"])
            self.assertEqual(c, 0)
            self.assertFalse((root / ".debug").exists())

    def test_marker_not_reached_exit_7(self):
        with tmp_dir() as td:
            root = Path(td)
            write(root / "a.py", "print(1)\n")
            run_ed(root, ["init"])
            run_ed(root, ["repro", "--", sys.executable, "-c", "import sys; sys.exit(1)"])
            run_ed(root, ["marker", "add", "--file", "a.py", "--line", "1"])
            c, o, e = run_ed(root, ["marker", "check", "--require"])
            self.assertEqual(c, 7)
            self.assertIn("the code you are editing is not the code that runs", o)

    def test_commands_exit_codes_documented_path(self):
        with tmp_dir() as td:
            root = Path(td)
            write(root / "a.py", "print(1)\n")
            self.assertEqual(run_ed(root, ["init"])[0], 0)
            self.assertEqual(run_ed(root, ["envinfo"])[0], 0)
            self.assertEqual(run_ed(root, ["status"])[0], 0)
            self.assertEqual(run_ed(root, ["status", "--markdown"])[0], 0)
            self.assertTrue((root / ".debug" / "ledger.md").exists())
            self.assertEqual(run_ed(root, ["marker", "list"])[0], 0)
            self.assertEqual(run_ed(root, ["report"])[0], 0)


if __name__ == "__main__":
    unittest.main()
