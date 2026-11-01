from __future__ import annotations

import os
import unittest
from pathlib import Path

from support import git_commit_all, git_init, tmp_dir

import edlib.paths as paths


class PathTests(unittest.TestCase):
    def test_non_git_root_is_cwd(self):
        with tmp_dir() as td:
            root = Path(td)
            got = paths.resolve_root(cwd=root)
            self.assertEqual(got, root.resolve())

    def test_git_root_detection(self):
        with tmp_dir() as td:
            root = Path(td)
            git_init(root)
            (root / "a.txt").write_text("x\n", encoding="utf-8")
            git_commit_all(root)
            sub = root / "sub"
            sub.mkdir()
            got = paths.resolve_root(cwd=sub)
            self.assertEqual(got, root.resolve())

    def test_explicit_root(self):
        with tmp_dir() as td:
            root = Path(td)
            got = paths.resolve_root(explicit=str(root))
            self.assertEqual(got, root.resolve())

    def test_dotdot_escape_rejected(self):
        with tmp_dir() as td:
            root = Path(td) / "proj"
            root.mkdir()
            with self.assertRaises(paths.PathError):
                paths.confine(Path("../secret"), root)

    def test_git_dir_rejected(self):
        with tmp_dir() as td:
            root = Path(td)
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("x", encoding="utf-8")
            with self.assertRaises(paths.PathError):
                paths.confine(Path(".git/config"), root)

    def test_debug_rejected_for_user_paths(self):
        with tmp_dir() as td:
            root = Path(td)
            (root / ".debug").mkdir()
            (root / ".debug" / "x").write_text("x", encoding="utf-8")
            with self.assertRaises(paths.PathError):
                paths.confine(Path(".debug/x"), root)

    def test_symlink_escape_rejected(self):
        if os.name == "nt":
            self.skipTest("symlink skip on Windows by default")
        with tmp_dir() as td:
            root = Path(td) / "proj"
            root.mkdir()
            outside = Path(td) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            link = root / "link"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink not permitted")
            with self.assertRaises(paths.PathError):
                paths.confine(Path("link"), root)


if __name__ == "__main__":
    unittest.main()
