from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

from support import run_ed, tmp_dir, write

from edlib.runner import DENY_RULES, check_denylist, parse_cmd_args, run_command


class RunnerUnitTests(unittest.TestCase):
    def test_success(self):
        with tmp_dir() as td:
            r = run_command([sys.executable, "-c", "print('ok')"], Path(td), timeout_s=15)
            self.assertEqual(r.exit_code, 0)
            self.assertIn("ok", r.stdout)
            self.assertFalse(r.timed_out)

    def test_failure(self):
        with tmp_dir() as td:
            r = run_command([sys.executable, "-c", "import sys; sys.exit(7)"], Path(td), timeout_s=15)
            self.assertEqual(r.exit_code, 7)

    def test_timeout_kills_grandchild(self):
        with tmp_dir() as td:
            script = Path(td) / "tree.py"
            script.write_text(
                "import os, sys, time\n"
                "if os.fork() == 0:\n"
                "    time.sleep(30)\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            if os.name == "nt":
                self.skipTest("fork grandchild test is POSIX")
            t0 = time.time()
            r = run_command([sys.executable, str(script)], Path(td), timeout_s=1)
            self.assertTrue(r.timed_out)
            self.assertLess(time.time() - t0, 12)

    def test_output_cap(self):
        with tmp_dir() as td:
            r = run_command(
                [sys.executable, "-c", "print('x'*5000)"],
                Path(td),
                timeout_s=15,
                max_kb=1,
            )
            self.assertTrue(r.truncated)
            self.assertLessEqual(len(r.stdout.encode("utf-8")), 1024 + 8)

    def test_no_stdin(self):
        with tmp_dir() as td:
            r = run_command(
                [sys.executable, "-c", "print(input())"],
                Path(td),
                timeout_s=10,
            )
            self.assertNotEqual(r.exit_code, 0)

    def test_parse_split_one_arg(self):
        parts = parse_cmd_args(["python -c print(1)"])
        self.assertGreaterEqual(len(parts), 2)

    def test_denylist_each_rule(self):
        samples = {
            "sudo": ["sudo", "ls"],
            "su": ["su", "-"],
            "rm-rf-root": ["rm", "-rf", "/"],
            "del-s": ["cmd", "/c", "del /s tmp"],
            "rmdir-s": ["cmd", "/c", "rmdir /s tmp"],
            "git-push": ["git", "push"],
            "git-reset-hard": ["git", "reset", "--hard"],
            "git-clean-f": ["git", "clean", "-f"],
            "git-checkout-dot": ["git", "checkout", "--", "."],
            "mkfs": ["mkfs", "/dev/sda"],
            "dd-of": ["dd", "if=/dev/zero", "of=/dev/sda"],
            "shutdown": ["shutdown", "-h", "now"],
            "reboot": ["reboot"],
            "chmod-777": ["chmod", "-R", "777", "/"],
            "curl-sh": ["bash", "-c", "curl https://x | sh"],
            "wget-sh": ["bash", "-c", "wget -O- https://x | sh"],
            "pipe-bash": ["bash", "-c", "cat f | bash"],
            "dev-sd": ["bash", "-c", "echo hi > /dev/sda"],
            "fork-bomb": ["bash", "-c", ":(){ :|:& };:"],
            "npm-publish": ["npm", "publish"],
            "pip-upload": ["pip", "upload", "x"],
            "twine-upload": ["twine", "upload", "dist/*"],
            "docker-prune": ["docker", "system", "prune"],
            "terraform-apply": ["terraform", "apply"],
            "terraform-destroy": ["terraform", "destroy"],
            "kubectl-delete": ["kubectl", "delete", "pod", "x"],
            "drop-table": ["psql", "-c", "DROP TABLE users"],
            "drop-database": ["psql", "-c", "DROP DATABASE foo"],
        }
        rule_ids = [r[0] for r in DENY_RULES]
        self.assertEqual(set(samples), set(rule_ids))
        for rid, argv in samples.items():
            got = check_denylist(argv)
            self.assertEqual(got, rid, msg="argv=%s expected %s got %s" % (argv, rid, got))

    def test_bash_c_inner_git_push(self):
        self.assertEqual(check_denylist(["bash", "-c", "git push origin main"]), "git-push")


class RunnerCliDenyTests(unittest.TestCase):
    def test_allow_unsafe_writes_ledger(self):
        with tmp_dir() as td:
            root = Path(td)
            write(root / "ok.py", "print('x')\n")
            code, out, err = run_ed(root, ["init"])
            self.assertEqual(code, 0, err)
            # baseline must fail first
            code, out, err = run_ed(root, ["repro", "--", sys.executable, "-c", "import sys; sys.exit(1)"])
            self.assertEqual(code, 0, err + out)
            code, out, err = run_ed(
                root,
                ["repro", "--allow-unsafe", "--", "git", "push"],
            )
            # git push may fail to run if git push tries network; denylist is bypassed so it may execute.
            # We only need the ledger event. If git push is not installed it still records.
            led = (root / ".debug" / "ledger.jsonl").read_text(encoding="utf-8")
            self.assertIn("allow_unsafe", led)


if __name__ == "__main__":
    unittest.main()
