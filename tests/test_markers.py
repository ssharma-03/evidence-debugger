from __future__ import annotations

import unittest
from pathlib import Path

from support import tmp_dir, write

from edlib.markers import MarkerError, add_marker, marker_source, remove_all


class MarkerTests(unittest.TestCase):
    def _add(self, name, content, line=1):
        td = tmp_dir()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        path = root / name
        write(path, content)
        rec = add_marker(root, name, line)
        text = path.read_text(encoding="utf-8")
        return root, path, rec, text

    def test_py(self):
        root, path, rec, text = self._add("a.py", "x = 1\ny = 2\n", 2)
        self.assertIn(rec["token"], text)
        self.assertIn('__import__("sys").stderr.write', text)
        # indent of line 2 is none
        self.assertTrue(any(rec["token"] in ln for ln in text.splitlines()))

    def test_js(self):
        _, _, rec, text = self._add("a.js", "const x = 1;\n", 1)
        self.assertIn('console.error("%s");' % rec["token"], text)

    def test_go(self):
        _, _, rec, text = self._add("a.go", "package main\n", 1)
        self.assertIn("println", text)

    def test_rs(self):
        _, _, rec, text = self._add("a.rs", "fn main() {}\n", 1)
        self.assertIn("eprintln!", text)

    def test_java(self):
        _, _, rec, text = self._add("a.java", "class A {}\n", 1)
        self.assertIn("System.err.println", text)

    def test_rb(self):
        _, _, rec, text = self._add("a.rb", "puts 1\n", 1)
        self.assertIn("warn", text)

    def test_php(self):
        _, _, rec, text = self._add("a.php", "<?php\n", 1)
        self.assertIn("error_log", text)

    def test_sh(self):
        _, _, rec, text = self._add("a.sh", "echo hi\n", 1)
        self.assertIn("echo %s >&2" % rec["token"], text)

    def test_indent_preserved(self):
        _, _, rec, text = self._add("b.py", "def f():\n    return 1\n", 2)
        self.assertIn('    __import__("sys").stderr.write("%s\\n")' % rec["token"], text)

    def test_crlf_preserved(self):
        td = tmp_dir()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        path = root / "c.py"
        path.write_bytes(b"a = 1\r\nb = 2\r\n")
        add_marker(root, "c.py", 2)
        data = path.read_bytes()
        self.assertIn(b"\r\n", data)
        self.assertNotIn(b"\n\n", data.replace(b"\r\n", b""))

    def test_continuation_refusal(self):
        td = tmp_dir()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        write(root / "d.py", "x = (\n    1\n)\n")
        with self.assertRaises(MarkerError):
            add_marker(root, "d.py", 2)

    def test_py_compile_rollback(self):
        td = tmp_dir()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        # inserting before a line that makes compile fail is hard if marker is valid;
        # simulate by using a file that is valid, then we trust rollback path via
        # a monkeypatched compile. Instead: insert into a file whose previous context
        # is fine. We force rollback by writing a file that is already invalid after
        # we patch marker_source? Simpler: file with only continuation-like that we skip.
        # Create a file, then call add_marker on a .py that becomes invalid if marker
        # is inserted inside a string - we refuse continuation already.
        # Directly test restore by writing original and invoking the except path:
        orig = b"def f(:\n    pass\n"
        path = root / "bad.py"
        path.write_bytes(orig)
        with self.assertRaises(MarkerError):
            add_marker(root, "bad.py", 2)
        self.assertEqual(path.read_bytes(), orig)

    def test_remove_exact_only(self):
        root, path, rec, text = self._add("e.py", "print(1)\nprint(2)\n", 1)
        remove_all(root, [rec])
        self.assertNotIn(rec["token"], path.read_text(encoding="utf-8"))

    def test_modified_marker_refused(self):
        root, path, rec, text = self._add("f.py", "print(1)\n", 1)
        new = path.read_text(encoding="utf-8").replace("stderr.write", "stdout.write")
        path.write_text(new, encoding="utf-8")
        rec["text"] = [ln for ln in new.splitlines() if rec["token"] in ln][0]
        with self.assertRaises(MarkerError):
            remove_all(root, [rec])


if __name__ == "__main__":
    unittest.main()
