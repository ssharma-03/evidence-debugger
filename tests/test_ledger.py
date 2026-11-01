from __future__ import annotations

import json
import os
import threading
import unittest
from multiprocessing import Process, Queue
from pathlib import Path

from support import tmp_dir

from edlib.ledger import Ledger


def _worker_append(path_str, n, q):
    led = Ledger(Path(path_str))
    seqs = []
    for i in range(n):
        ev = led.append("note", {"i": i, "pid": os.getpid()})
        seqs.append(ev["seq"])
    q.put(seqs)


class LedgerTests(unittest.TestCase):
    def test_append_and_read(self):
        with tmp_dir() as td:
            p = Path(td) / "ledger.jsonl"
            led = Ledger(p)
            a = led.append("init", {"k": "v"})
            b = led.append("note", {"n": 1})
            self.assertEqual(a["seq"], 1)
            self.assertEqual(b["seq"], 2)
            evs = led.read_events()
            self.assertEqual(len(evs), 2)
            self.assertEqual(evs[0]["type"], "init")
            self.assertIn("ts", evs[0])

    def test_corrupted_last_line(self):
        with tmp_dir() as td:
            p = Path(td) / "ledger.jsonl"
            led = Ledger(p)
            led.append("init", {})
            with open(str(p), "a", encoding="utf-8") as fp:
                fp.write("{not json")
            warns = []
            evs = led.read_events(warn=lambda m: warns.append(m))
            self.assertEqual(len(evs), 1)
            self.assertTrue(warns)

    def test_posix_mode_600(self):
        if os.name != "posix":
            self.skipTest("POSIX only")
        with tmp_dir() as td:
            p = Path(td) / "ledger.jsonl"
            led = Ledger(p)
            led.append("init", {})
            mode = p.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_threads_unique_seq(self):
        with tmp_dir() as td:
            p = Path(td) / "ledger.jsonl"
            led = Ledger(p)
            errors = []

            def work():
                try:
                    for _i in range(10):
                        led.append("note", {"t": threading.get_ident()})
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=work) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertFalse(errors)
            evs = led.read_events()
            self.assertEqual(len(evs), 200)
            seqs = [e["seq"] for e in evs]
            self.assertEqual(seqs, list(range(1, 201)))
            # unique increasing
            self.assertEqual(len(set(seqs)), 200)

    def test_processes_unique_seq(self):
        with tmp_dir() as td:
            p = Path(td) / "ledger.jsonl"
            Ledger(p).append("init", {})
            q = Queue()
            procs = [Process(target=_worker_append, args=(str(p), 5, q)) for _ in range(20)]
            for pr in procs:
                pr.start()
            for pr in procs:
                pr.join(timeout=30)
            all_seqs = []
            while not q.empty():
                all_seqs.extend(q.get())
            evs = Ledger(p).read_events()
            seqs = [e["seq"] for e in evs]
            self.assertEqual(len(seqs), len(set(seqs)))
            self.assertEqual(sorted(seqs), list(range(1, len(seqs) + 1)))
            self.assertGreaterEqual(len(seqs), 1 + 20 * 5)


if __name__ == "__main__":
    unittest.main()
