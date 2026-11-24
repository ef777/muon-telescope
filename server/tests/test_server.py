import importlib

import synth
from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("MUON_DB", str(tmp_path / "t.db"))
    import app as appmod
    importlib.reload(appmod)
    return TestClient(appmod.app)


def test_ingest_idempotent_and_stats(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    recs = synth.generate(synth.default_devices(), 24, 2).records
    for k, r in enumerate(recs):
        r["run_id"] = "t"
    first = c.post("/ingest", json=recs).json()
    again = c.post("/ingest", json=recs).json()          # retry after dropped connection
    assert first["new"] == len(recs) and again["new"] == 0
    assert c.get("/runs").json()[0]["n_events"] == len(recs)
    s = c.get("/stats").json()
    assert s["lag_scan_top_middle"]["significance"] > 3
    assert isinstance(c.get("/coincidences").json(), list)
    t = c.post("/sync", json={"t1": 1}).json()
    assert t["t3"] >= t["t2"]
