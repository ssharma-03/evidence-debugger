from __future__ import annotations

import unittest
from pathlib import Path

from support import git_commit_all, git_init, run_ed, tmp_dir, write

from edlib.guard import RULES, analyze_hunks, parse_unified_hunks


def hunk(path, added=None, removed=None):
    return {path: {"added": added or [], "removed": removed or []}}


class GuardRuleTests(unittest.TestCase):
    def test_rules_are_data(self):
        ids = [r["id"] for r in RULES]
        self.assertIn("py-swallow", ids)
        for r in RULES:
            self.assertIn("severity", r)
            self.assertIn("description", r)

    def test_py_swallow_pos(self):
        f = analyze_hunks(hunk("a.py", added=["try:", "    x=1", "except Exception:", "    pass"]))
        self.assertTrue(any(x.rule_id == "py-swallow" for x in f))

    def test_py_swallow_neg(self):
        f = analyze_hunks(hunk("a.py", added=["try:", "    x=1", "except KeyError as e:", "    raise"]))
        self.assertFalse(any(x.rule_id == "py-swallow" for x in f))

    def test_js_empty_catch_pos(self):
        f = analyze_hunks(hunk("a.js", added=["try { f() } catch (e) {}"]))
        self.assertTrue(any(x.rule_id == "js-empty-catch" for x in f))

    def test_js_empty_catch_neg(self):
        f = analyze_hunks(hunk("a.js", added=["try { f() } catch (e) { log(e) }"]))
        self.assertFalse(any(x.rule_id == "js-empty-catch" for x in f))

    def test_test_skip_pos(self):
        f = analyze_hunks(hunk("tests/test_a.py", added=["@pytest.mark.skip", "def test_a():", "    pass"]))
        self.assertTrue(any(x.rule_id == "test-skip" for x in f))

    def test_test_skip_neg(self):
        f = analyze_hunks(hunk("tests/test_a.py", added=["def test_a():", "    assert 1"]))
        self.assertFalse(any(x.rule_id == "test-skip" for x in f))

    def test_suppress_types_pos(self):
        f = analyze_hunks(hunk("a.py", added=["x = 1  # type: ignore"]))
        self.assertTrue(any(x.rule_id == "suppress-types" for x in f))

    def test_suppress_types_neg(self):
        f = analyze_hunks(hunk("a.py", added=["x = 1  # helpful comment"]))
        self.assertFalse(any(x.rule_id == "suppress-types" for x in f))

    def test_test_deleted_pos(self):
        f = analyze_hunks({}, deleted_paths=["tests/test_gone.py"])
        self.assertTrue(any(x.rule_id == "test-deleted" for x in f))

    def test_test_deleted_neg(self):
        f = analyze_hunks({}, deleted_paths=["src/app.py"])
        self.assertFalse(any(x.rule_id == "test-deleted" for x in f))

    def test_assertion_weakened_pos(self):
        f = analyze_hunks(hunk("tests/test_a.py", added=["x = 1"], removed=["assert result == 10"]))
        self.assertTrue(any(x.rule_id == "assertion-weakened" for x in f))

    def test_assertion_weakened_neg(self):
        f = analyze_hunks(
            hunk("tests/test_a.py", added=["assert result == 10"], removed=["assert result == 9"])
        )
        self.assertFalse(any(x.rule_id == "assertion-weakened" for x in f))

    def test_expected_value_edited_pos(self):
        f = analyze_hunks(
            hunk("tests/test_a.py", added=["assert n == 9"], removed=["assert n == 10"])
        )
        self.assertTrue(any(x.rule_id == "expected-value-edited" for x in f))

    def test_expected_value_edited_neg(self):
        f = analyze_hunks(
            hunk("tests/test_a.py", added=["assert name == 'b'"], removed=["assert n == 10"])
        )
        self.assertFalse(any(x.rule_id == "expected-value-edited" for x in f))

    def test_assert_true_pos(self):
        f = analyze_hunks(hunk("tests/test_a.py", added=["assert True"]))
        self.assertTrue(any(x.rule_id == "assert-true" for x in f))

    def test_assert_true_neg(self):
        f = analyze_hunks(hunk("tests/test_a.py", added=["assert value is True"]))
        self.assertFalse(any(x.rule_id == "assert-true" for x in f))

    def test_sleep_added_pos(self):
        f = analyze_hunks(hunk("a.py", added=["time.sleep(1)"]))
        self.assertTrue(any(x.rule_id == "sleep-added" for x in f))

    def test_sleep_added_neg(self):
        f = analyze_hunks(hunk("a.py", added=["elapsed = 1"]))
        self.assertFalse(any(x.rule_id == "sleep-added" for x in f))

    def test_retry_added_pos(self):
        f = analyze_hunks(hunk("a.py", added=["retries = 3"]))
        self.assertTrue(any(x.rule_id == "retry-added" for x in f))

    def test_retry_added_neg(self):
        f = analyze_hunks(hunk("a.py", added=["count = 3"]))
        self.assertFalse(any(x.rule_id == "retry-added" for x in f))

    def test_dependency_pinned_pos(self):
        f = analyze_hunks(hunk("requirements.txt", added=["foo==1.0"], removed=["foo==2.0"]))
        self.assertTrue(any(x.rule_id == "dependency-pinned" for x in f))

    def test_dependency_pinned_neg(self):
        f = analyze_hunks(hunk("readme.txt", added=["foo==1.0"]))
        self.assertFalse(any(x.rule_id == "dependency-pinned" for x in f))

    def test_hardcoded_literal_pos(self):
        f = analyze_hunks(
            hunk(
                "tests/test_a.py",
                added=["assert n == 10", "    return 10"],
                removed=["assert n == 10"],
            )
        )
        self.assertTrue(any(x.rule_id == "hardcoded-literal" for x in f))

    def test_hardcoded_literal_neg(self):
        f = analyze_hunks(hunk("tests/test_a.py", added=["assert n == 10"]))
        self.assertFalse(any(x.rule_id == "hardcoded-literal" for x in f))


class GuardFlowTests(unittest.TestCase):
    def test_approval_flow(self):
        with tmp_dir() as td:
            root = Path(td)
            write(root / "app.py", "print(1)\n")
            git_init(root)
            git_commit_all(root)
            c, o, e = run_ed(root, ["init"])
            self.assertEqual(c, 0, e)
            write(root / "app.py", "try:\n    x=1\nexcept Exception:\n    pass\n")
            c, o, e = run_ed(root, ["guard"])
            self.assertEqual(c, 4)
            self.assertIn("py-swallow", o + e)
            c, o, e = run_ed(root, ["approve", "--rule", "py-swallow", "--reason", "user said: keep this"])
            self.assertEqual(c, 0, e)
            c, o, e = run_ed(root, ["guard"])
            self.assertEqual(c, 0, e)
            self.assertIn("APPROVED", o)

    def test_nongit_snapshot(self):
        with tmp_dir() as td:
            root = Path(td)
            write(root / "app.py", "print(1)\n")
            c, o, e = run_ed(root, ["init"])
            self.assertEqual(c, 0, e)
            write(root / "app.py", "try:\n  x=1\nexcept:\n  pass\n")
            c, o, e = run_ed(root, ["guard"])
            self.assertEqual(c, 4)
            self.assertIn("py-swallow", o)


if __name__ == "__main__":
    unittest.main()
