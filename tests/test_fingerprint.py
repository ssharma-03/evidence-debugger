from __future__ import annotations

import unittest

from edlib.fingerprint import extract_error_line, fingerprint, normalize_line


PY_TB = """\
Traceback (most recent call last):
  File "/tmp/proj/app.py", line 12, in <module>
    main()
  File "/tmp/proj/app.py", line 8, in main
    raise ValueError("boom 42")
ValueError: boom 42
"""

PYTEST = """\
    def test_x():
>       assert 1 == 2
E       AssertionError: assert 1 == 2
"""

NODE = """\
Error: fail at /app/src/index.js:10:5
    at Object.<anonymous> (/app/src/index.js:10:5)
"""

TS = "src/app.ts(12,5): error TS2322: Type 'string' is not assignable to type 'number'."

GO = "panic: runtime error: invalid memory address or nil pointer dereference"

RUST = "thread 'main' panicked at 'assertion failed: x', src/main.rs:4:5"

JAVA = "Exception in thread \"main\" java.lang.NullPointerException"

MAKE = "make: *** [all] Error 1"


class FingerprintTests(unittest.TestCase):
    def test_python(self):
        line = extract_error_line("", PY_TB)
        self.assertIn("ValueError", line)
        fp = fingerprint("", PY_TB, 1)
        self.assertEqual(len(fp), 12)

    def test_pytest(self):
        line = extract_error_line(PYTEST, "")
        self.assertTrue("assert" in line.lower() or "assertion" in line.lower() or "Error" in line)

    def test_node(self):
        line = extract_error_line("", NODE)
        self.assertIn("Error", line)

    def test_typescript(self):
        line = extract_error_line("", TS)
        self.assertIn("TS2322", line)

    def test_go(self):
        self.assertIn("panic", extract_error_line("", GO).lower())

    def test_rust(self):
        self.assertIn("panic", extract_error_line("", RUST).lower())

    def test_java(self):
        self.assertIn("Exception", extract_error_line("", JAVA))

    def test_make(self):
        line = extract_error_line("", MAKE)
        self.assertIn("Error", line)

    def test_same_after_number_and_path_change(self):
        a = fingerprint("", "Error: fail in /tmp/a/foo.py:12 value 99", 1)
        b = fingerprint("", "Error: fail in /var/b/foo.py:44 value 12", 1)
        self.assertEqual(a, b)

    def test_different_message(self):
        a = fingerprint("", "Error: not found", 1)
        b = fingerprint("", "Error: permission denied", 1)
        self.assertNotEqual(a, b)

    def test_normalize_uuid_hex_ts(self):
        n = normalize_line("err 550e8400-e29b-41d4-a716-446655440000 at 0x7fffdeadbeef 2020-01-01T00:00:00Z")
        self.assertIn("uuid", n)
        self.assertIn("0xx", n)
        self.assertIn("ts", n)


if __name__ == "__main__":
    unittest.main()
