"""SQLite event store with idempotent ingest (key: device_id + frame_idx + cluster index)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .events import Events, from_records

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  run_id TEXT NOT NULL, device_id TEXT NOT NULL, frame_idx INTEGER NOT NULL, cluster_idx INTEGER NOT NULL,
  utc_ns INTEGER NOT NULL, record TEXT NOT NULL,
  PRIMARY KEY (run_id, device_id, frame_idx, cluster_idx)
);
CREATE INDEX IF NOT EXISTS ix_events_time ON events (run_id, utc_ns);
"""


def connect(path: str | Path = "data/muon.db") -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.executescript(SCHEMA)
    return con


def ingest(con: sqlite3.Connection, records: list[dict]) -> dict:
    """Insert records; duplicates (same key) are ignored, so retries after a dropped connection are safe."""
    n_new = 0
    for r in records:
        cur = con.execute(
            "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)",
            (r.get("run_id", "default"), r["device_id"], int(r["frame_idx"]), int(r.get("cluster_idx", 0)),
             int(r["utc_ns"]), json.dumps(r)))
        n_new += cur.rowcount
    con.commit()
    return {"received": len(records), "new": n_new, "duplicates": len(records) - n_new}


def load_events(con: sqlite3.Connection, run_id: str | None = None) -> Events:
    q = "SELECT record FROM events" + (" WHERE run_id=?" if run_id else "") + " ORDER BY utc_ns"
    rows = con.execute(q, (run_id,) if run_id else ()).fetchall()
    return from_records([json.loads(r[0]) for r in rows])


def list_runs(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute("SELECT run_id, COUNT(*), MIN(utc_ns), MAX(utc_ns) FROM events GROUP BY run_id").fetchall()
    return [dict(run_id=r[0], n_events=r[1], t_first_ns=r[2], t_last_ns=r[3]) for r in rows]
