"""Append-only application API. Hash links detect edits, not whole-log replacement."""

import sqlite3
import threading
from pathlib import Path
from .contracts import canonical, digest, strict_json, stamp


class EvidenceError(RuntimeError):
    pass


class EvidenceStore:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY, previous TEXT NOT NULL,
            payload TEXT NOT NULL, hash TEXT NOT NULL)""")
        self.db.commit()
        try:
            self.verify()
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def verify(self, anchor=None):
        with self.lock:
            previous, count = "0" * 64, 0
            for seq, prior, payload, hash_ in self.db.execute("SELECT seq, previous, payload, hash FROM events ORDER BY seq"):
                count += 1
                expected = digest({"seq": seq, "previous": prior, "payload": strict_json(payload)})
                if seq != count or prior != previous or hash_ != expected:
                    raise EvidenceError(f"Evidence chain invalid at event {seq}.")
                previous = hash_
            head = {"events": count, "head": previous}
            if anchor is not None and anchor != head:
                raise EvidenceError("Evidence head does not match the supplied external anchor.")
            return head

    def append(self, run_id, kind, data):
        payload = {"run_id": run_id, "kind": kind, "at": stamp(), "data": data}
        encoded = canonical(payload)
        if len(encoded.encode()) > 262144:
            raise EvidenceError("Evidence event is too large.")
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                head = self.verify()
                seq = head["events"] + 1
                hash_ = digest({"seq": seq, "previous": head["head"], "payload": payload})
                self.db.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (seq, head["head"], encoded, hash_))
                self.db.commit()
                return {"seq": seq, "hash": hash_}
            except Exception as exc:
                self.db.rollback()
                raise EvidenceError("Cannot append verified evidence. No advice released.") from exc

    def export(self):
        with self.lock:
            self.verify()
            return [{"seq": seq, "previous": prior, "payload": strict_json(payload), "hash": hash_}
                    for seq, prior, payload, hash_ in self.db.execute("SELECT seq, previous, payload, hash FROM events ORDER BY seq")]

    def bundle(self):
        """Anchor and events from the same SQLite read transaction."""
        with self.lock:
            try:
                self.db.execute("BEGIN")
                result = {"anchor": self.verify(), "events": self.export()}
                self.db.commit()
                return result
            except Exception:
                self.db.rollback()
                raise
