from __future__ import annotations

import sys
import unittest
from pathlib import Path

from support import run_ed, tmp_dir, write


FAIL = [sys.executable, "-c", "import sys; sys.exit(1)"]
PASS = [sys.executable, "-c", "print('ok')"]


def setup_survived(root):
    c, o, e = run_ed(root, ["init"])
    assert c == 0, e
    c, o, e = run_ed(root, ["repro", "--"] + FAIL)
    assert c == 0, e + o
    c, o, e = run_ed(
        root,
        [
            "hypo",
            "add",
            "--text",
            "the script exits nonzero always",
            "--predicts",
            "repro keeps failing until we print ok",
            "--disprove",
            "run a command that should pass if theory is wrong",
        ],
    )
    assert c == 0, e
    c, o, e = run_ed(root, ["hypo", "resolve", "H1", "--status", "survived", "--run", "R1", "--evidence", "R1 failed as predicted by H1 here"])
    assert c == 0, e


class AttemptBreakerTests(unittest.TestCase):
    def test_refuse_before_hypo_survives(self):
        with tmp_dir() as td:
            root = Path(td)
            write(root / "a.py", "print(1)\n")
            run_ed(root, ["init"])
            run_ed(root, ["repro", "--"] + FAIL)
            run_ed(
                root,
                [
                    "hypo",
                    "add",
                    "--text",
                    "open hypothesis text here",
                    "--predicts",
                    "it will still fail now",
                    "--disprove",
                    "run passing command maybe",
                ],
            )
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "tweaked a.py"])
            self.assertEqual(c, 2)
            self.assertIn("no fixing before a hypothesis survives", e)

    def test_refuse_without_new_repro(self):
        with tmp_dir() as td:
            root = Path(td)
            setup_survived(root)
            write(root / "a.py", "print(1)\n")
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "first change here"])
            self.assertEqual(c, 0, e)
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "second change no repro"])
            self.assertEqual(c, 2)
            self.assertIn("run repro first", e)

    def test_computed_outcome_and_repeat(self):
        with tmp_dir() as td:
            root = Path(td)
            setup_survived(root)
            write(root / "a.py", "print('one')\n")
            c, o, e = run_ed(root, ["repro", "--"] + FAIL)
            self.assertEqual(c, 0, e)
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "wrote a.py v1"])
            self.assertEqual(c, 0, e)
            self.assertIn("same_failure", o)
            # same files+diff without editing -> need new repro then same content
            c, o, e = run_ed(root, ["repro", "--"] + FAIL)
            self.assertEqual(c, 0)
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "wrote a.py v1 again"])
            self.assertEqual(c, 2)
            self.assertIn("REPEAT OF A FAILED ATTEMPT", e)

    def test_breaker_trips_and_release(self):
        with tmp_dir() as td:
            root = Path(td)
            c, o, e = run_ed(root, ["init", "--breaker-limit", "3"])
            self.assertEqual(c, 0, e)
            run_ed(root, ["repro", "--"] + FAIL)
            run_ed(
                root,
                [
                    "hypo",
                    "add",
                    "--text",
                    "always fails until we change strategy",
                    "--predicts",
                    "exit code stays nonzero on repro",
                    "--disprove",
                    "a passing python print would disprove",
                ],
            )
            run_ed(root, ["hypo", "resolve", "H1", "--status", "survived", "--run", "R1", "--evidence", "baseline R1 failed matching H1"])
            for i in range(3):
                write(root / "a.py", "print(%d)\n" % i)
                c, o, e = run_ed(root, ["repro", "--"] + FAIL)
                self.assertEqual(c, 0, e)
                c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "edit number %d uniquely" % i])
                self.assertEqual(c, 0, e + o)
            # fourth attempt refused
            write(root / "a.py", "print(99)\n")
            run_ed(root, ["repro", "--"] + FAIL)
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "after trip"])
            self.assertEqual(c, 3, e)
            self.assertIn("BREAKER TRIPPED", e)
            c, o, e = run_ed(root, ["status"])
            self.assertIn("BREAKER TRIPPED", e)
            c, o, e = run_ed(root, ["breaker", "show"])
            self.assertEqual(c, 0, e)
            self.assertIn("BASELINE", o)
            c, o, e = run_ed(root, ["assumption", "add", "--text", "maybe the command is always failing", "--check-run", "R1"])
            self.assertEqual(c, 0, e)
            c, o, e = run_ed(root, ["assumption", "add", "--text", "environment is not the issue here", "--check-run", "R2"])
            self.assertEqual(c, 0, e)
            c, o, e = run_ed(root, ["breaker", "ack"])
            self.assertEqual(c, 0, e)
            write(root / "a.py", "print(100)\n")
            run_ed(root, ["repro", "--"] + FAIL)
            c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "post ack edit"])
            self.assertEqual(c, 0, e)

    def test_escalate_after_second_trip(self):
        with tmp_dir() as td:
            root = Path(td)
            run_ed(root, ["init", "--breaker-limit", "3"])
            run_ed(root, ["repro", "--"] + FAIL)
            run_ed(
                root,
                [
                    "hypo",
                    "add",
                    "--text",
                    "always fails until we change strategy",
                    "--predicts",
                    "exit code stays nonzero on repro",
                    "--disprove",
                    "a passing python print would disprove",
                ],
            )
            run_ed(root, ["hypo", "resolve", "H1", "--status", "survived", "--run", "R1", "--evidence", "baseline R1 failed matching H1"])
            n = 0
            for trip in range(2):
                for i in range(3):
                    n += 1
                    write(root / ("f%d.py" % n), "print(%d)\n" % n)
                    run_ed(root, ["repro", "--"] + FAIL)
                    c, o, e = run_ed(root, ["attempt", "--hypo", "H1", "--change", "unique change %d" % n])
                    self.assertEqual(c, 0, e + o)
                if trip == 0:
                    run_ed(root, ["breaker", "show"])
                    run_ed(root, ["assumption", "add", "--text", "assumption one about the environment x", "--check-run", "R1"])
                    run_ed(root, ["assumption", "add", "--text", "assumption two about the command line y", "--check-run", "R2"])
                    c, o, e = run_ed(root, ["breaker", "ack"])
                    self.assertEqual(c, 0, e)
            c, o, e = run_ed(root, ["escalate"])
            self.assertEqual(c, 0, e)
            self.assertIn("one thing needed from user", o)


if __name__ == "__main__":
    unittest.main()
