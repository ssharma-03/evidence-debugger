from __future__ import annotations

import ast
import unittest
from pathlib import Path

from support import ROOT

FORBIDDEN_MODS = {
    "socket",
    "urllib",
    "http",
    "requests",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
}
FORBIDDEN_ATTR = {
    ("asyncio", "open_connection"),
}

SKILL = ROOT / "evidence-debugger"


class NoNetworkTests(unittest.TestCase):
    def test_scan_skill_python(self):
        files = list(SKILL.rglob("*.py"))
        self.assertTrue(files)
        problems = []
        for path in files:
            if "__pycache__" in path.parts:
                continue
            src = path.read_text(encoding="utf-8", errors="replace")
            if "shell=True" in src:
                problems.append("%s: shell=True" % path)
            if "os.system" in src:
                problems.append("%s: os.system" % path)
            if "pickle" in src:
                problems.append("%s: pickle" % path)
            try:
                tree = ast.parse(src, filename=str(path), feature_version=(3, 8))
            except SyntaxError as exc:
                problems.append("%s: syntax %s" % (path, exc))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top in FORBIDDEN_MODS:
                            problems.append("%s: import %s" % (path, alias.name))
                if isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if top in FORBIDDEN_MODS:
                        problems.append("%s: from %s" % (path, node.module))
                    for alias in node.names:
                        if (node.module, alias.name) in FORBIDDEN_ATTR:
                            problems.append("%s: %s.%s" % (path, node.module, alias.name))
                if isinstance(node, ast.Call):
                    func = node.func
                    name = ""
                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr
                    if name in ("eval", "exec"):
                        problems.append("%s: %s()" % (path, name))
                    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                        if func.value.id == "os" and func.attr == "system":
                            problems.append("%s: os.system" % path)
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            problems.append("%s: shell=True" % path)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
