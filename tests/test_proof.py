from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

from support import run_ed, tmp_dir, write


FAIL = [sys.executable, "-c", "import sys; sys.exit(1)"]
PASS = [sys.executable, "-c", "print('ok')"]
CAUSE = "root cause is the demo command exits 1 until switched to print ok"


def prepare(root, survive=True, baseline=True, fix_pass=False):
    c, o, e = run_ed(root, ["init"])
    assert c == 0, e
    if baseline:
        c, o, e = run_ed(root, ["repro", "--name", "base", "--"] + FAIL)
        assert c == 0, e + o
    if survive and baseline:
        run_ed(
            root,
            [
                "hypo",
                "add",
                "--text",
                "the command is written to fail on purpose",
                "--predicts",
                "nonzero exit continues until command changes",
                "--disprove",
                "a passing python -c print would show it can pass",
            ],
        )
        run_ed(root, ["hypo", "resolve", "H1", "--status", "survived", "--run", "R1", "--evidence", "R1 failed matching the hypothesis"])
        write(root / "app.py", "print('fixed')\n")
        if fix_pass:
            c, o, e = run_ed(root, ["repro", "--"] + PASS)
            assert c == 0, e
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "switched repro command to passing print"])
            # outcome may be different_failure/PASSING computed as different because argv != baseline
            # For fixed outcome we need same argv as baseline with exit 0.
        return c if fix_pass else 0
    return 0


class ProofTests(unittest.TestCase):
    def test_fail_no_baseline(self):
        with tmp_dir() as td:
            root = Path(td)
            run_ed(root, ["init"])
            c, o, e = run_ed(root, ["proof", "--cause", CAUSE])
            self.assertEqual(c, 5)
            self.assertIn("not verified:", o)

    def test_fail_latest_not_passing(self):
        with tmp_dir() as td:
            root = Path(td)
            prepare(root, survive=True, fix_pass=False)
            c, o, e = run_ed(root, ["proof", "--cause", CAUSE])
            self.assertEqual(c, 5)
            self.assertIn("not verified:", o)

    def test_fail_also(self):
        with tmp_dir() as td:
            root = Path(td)
            self._happy_setup(root, passing=True)
            c, o, e = run_ed(root, ["proof", "--cause", CAUSE, "--also", "%s -c \"import sys; sys.exit(2)\"" % sys.executable])
            self.assertEqual(c, 5)

    def test_fail_markers(self):
        with tmp_dir() as td:
            root = Path(td)
            self._happy_setup(root, passing=True)
            write(root / "m.py", "x = 1\n")
            c, o, e = run_ed(root, ["marker", "add", "--file", "m.py", "--line", "1"])
            self.assertEqual(c, 0, e)
            c, o, e = run_ed(root, ["proof", "--cause", CAUSE])
            self.assertEqual(c, 5)

    def test_fail_guard(self):
        with tmp_dir() as td:
            root = Path(td)
            self._happy_setup(root, passing=True)
            write(root / "bad.py", "try:\n    x=1\nexcept Exception:\n    pass\n")
            c, o, e = run_ed(root, ["proof", "--cause", CAUSE])
            self.assertEqual(c, 5)

    def test_fail_no_survived_hypo(self):
        with tmp_dir() as td:
            root = Path(td)
            run_ed(root, ["init"])
            run_ed(root, ["repro", "--"] + FAIL)
            write(root / "app.py", "print(1)\n")
            # make a passing run of same command? can't with FAIL argv.
            # without hypo, proof fails check 6
            c, o, e = run_ed(root, ["proof", "--cause", CAUSE])
            self.assertEqual(c, 5)

    def test_fail_short_cause(self):
        with tmp_dir() as td:
            root = Path(td)
            self._happy_setup(root, passing=True)
            c, o, e = run_ed(root, ["proof", "--cause", "too short"])
            self.assertEqual(c, 5)

    def test_fail_cause_equals_change(self):
        with tmp_dir() as td:
            root = Path(td)
            change = "switched the failing demo command over to a passing print"
            self._happy_setup(root, passing=True, change=change)
            c, o, e = run_ed(root, ["proof", "--cause", change])
            self.assertEqual(c, 5)

    def test_stale_mtime(self):
        with tmp_dir() as td:
            root = Path(td)
            self._happy_setup(root, passing=True)
            app = root / "app.py"
            time.sleep(0.05)
            now = time.time() + 5
            os.utime(str(app), (now, now))
            c, o, e = run_ed(root, ["proof", "--cause", CAUSE])
            self.assertEqual(c, 5)

    def test_success(self):
        with tmp_dir() as td:
            root = Path(td)
            self._happy_setup(root, passing=True)
            c, o, e = run_ed(root, ["proof", "--cause", CAUSE, "--also", "%s -c \"print(0)\"" % sys.executable])
            self.assertEqual(c, 0, o + e)
            self.assertIn("PASS", o)

    def _happy_setup(self, root, passing=True, change="edited app.py to document the fix path"):
        write(root / "app.py", "raise SystemExit(1)\n")
        c, o, e = run_ed(root, ["init"])
        self.assertEqual(c, 0, e)
        c, o, e = run_ed(root, ["repro", "--", sys.executable, str(root / "app.py")])
        self.assertEqual(c, 0, e + o)
        run_ed(
            root,
            [
                "hypo",
                "add",
                "--text",
                "app.py exits 1 because it raises SystemExit",
                "--predicts",
                "repro of app.py keeps failing until SystemExit is removed",
                "--disprove",
                "if app.py printed ok it would pass showing exit was the bug",
            ],
        )
        run_ed(root, ["hypo", "resolve", "H1", "--status", "survived", "--run", "R1", "--evidence", "R1 failed with SystemExit as predicted"])
        if passing:
            write(root / "app.py", "print('ok')\n")
            c, o, e = run_ed(root, ["repro", "--", sys.executable, str(root / "app.py")])
            self.assertEqual(c, 0, e)
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", change])
            self.assertEqual(c, 0, e)
            self.assertIn("fixed", o)


if __name__ == "__main__":
    unittest.main()
