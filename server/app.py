"""FastAPI server. Run: uvicorn app:app --app-dir server --port 8000   (from repo root)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
from fastapi import Body, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from muon import classify, coincidence, ingest, stability, timesync, tracks

DB_PATH = os.environ.get("MUON_DB", "data/muon.db")
ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Muon telescope")
con = ingest.connect(DB_PATH)


@app.post("/sync")
def sync(payload: dict = Body(...)):
    """NTP-style exchange: client sends t1 (its clock); server stamps t2 on receipt and t3 just before reply."""
    t2 = time.time_ns()
    return {"t1": payload.get("t1"), "t2": t2, "t3": time.time_ns()}


@app.post("/ingest")
def post_ingest(records: list[dict] = Body(...)):
    return ingest.ingest(con, records)


@app.get("/runs")
def runs():
    return ingest.list_runs(con)


@app.get("/events")
def events(run_id: str | None = None, device: str | None = None, limit: int = 200):
    ev = ingest.load_events(con, run_id)
    if device:
        ev = ev.device_events(device)
    pred = classify.classify(ev) if len(ev) else []
    n = min(limit, len(ev))
    return [dict(device=str(ev.device[i]), utc_ns=int(ev.utc_ns[i]), cls=str(pred[i]),
                 **{k: float(v[i]) for k, v in ev.cols.items()}) for i in range(len(ev) - n, len(ev))]


def _triples(run_id: str | None, order=("top", "middle", "bottom")):
    ev = ingest.load_events(con, run_id)
    a, b, c = (ev.device_events(n) for n in order)
    return ev, (a, b, c), coincidence.match_triples(a, b, c)


@app.get("/coincidences")
def coincidences(run_id: str | None = None, pitch_um: float = 1.0, z_gap_mm: float = 9.0):
    """Triples with straight-line reconstruction in the stack frame (nominal geometry, no alignment)."""
    ev, (a, b, c), tri = _triples(run_id)
    tri = classify.track_triples(tri, a, b, c)     # drop real doubles + noise cluster in 3rd sensor
    out = []
    for i, j, k in tri[-100:]:
        poses = {n: tracks.SensorPose(-z_gap_mm * s, 0, 0, 0, pitch_um, 2 * a.cols["x_px"].max(), 2 * a.cols["y_px"].max())
                 for s, n in enumerate(("top", "middle", "bottom"))}
        pts = np.array([poses[n].to_stack(e.cols["x_px"][q], e.cols["y_px"][q])
                        for n, e, q in (("top", a, i), ("middle", b, j), ("bottom", c, k))])
        cen, d, res = tracks.fit_line(pts)
        out.append(dict(utc_ns=int(a.utc_ns[i]), points=pts.tolist(), zenith=tracks.zenith(d),
                        residual_mm=float(res.max())))
    return out


_taps: dict[str, list[int]] = {}
_gnss: dict[str, list[tuple[int, int]]] = {}


@app.post("/tap")
def post_tap(payload: dict = Body(...)):
    """Accelerometer impulse timestamps (UTC ns, already mapped through the device's TimeSync) for the tap test."""
    _taps.setdefault(payload["device_id"], []).extend(int(t) for t in payload["times_utc_ns"])
    return {"devices": {k: len(v) for k, v in _taps.items()}}


@app.get("/tapsync")
def tapsync(ref: str, other: str):
    """Measured clock offset (other - ref) from common taps; compare with the NTP result to validate < 5 ms."""
    if ref not in _taps or other not in _taps:
        return {"error": "need taps from both devices"}
    return timesync.tap_offset(np.array(_taps[ref]), np.array(_taps[other]))


@app.post("/gnss")
def post_gnss(payload: dict = Body(...)):
    """GNSS fixes: pairs (elapsedRealtimeNanos, utc_ns)."""
    _gnss.setdefault(payload["device_id"], []).extend((int(e), int(u)) for e, u in payload["pairs"])
    return timesync.elapsed_to_utc_offset(_gnss[payload["device_id"]])


@app.put("/crop/{run_id}/{device}/{name}")
async def put_crop(run_id: str, device: str, name: str, request: Request):
    d = Path(DB_PATH).parent / "crops" / run_id / device
    d.mkdir(parents=True, exist_ok=True)
    (d / Path(name).name).write_bytes(await request.body())
    return {"ok": True}


def _num(x: float) -> float | None:
    """JSON has no NaN."""
    return None if x != x else float(x)


@app.get("/stability")
def stability_report(run_id: str | None = None):
    ev = ingest.load_events(con, run_id)
    out = {}
    for d in sorted(set(ev.device.tolist())):
        h = stability.hourly_rates(ev, d)
        out[d] = dict(rate_per_hour=h["rate"].tolist(), stable=h["stable"], max_dev=_num(h["max_dev"]),
                      duty=_num(stability.duty_cycle(ev, d)))
    return out


@app.get("/stats")
def stats(run_id: str | None = None):
    ev = ingest.load_events(con, run_id)
    res: dict = {"n_events": len(ev), "devices": {}}
    for d in sorted(set(ev.device.tolist())):
        e = ev.device_events(d)
        hours = max((e.utc_ns.max() - e.utc_ns.min()) / 3.6e12, 1e-9) if len(e) > 1 else 0
        pred = classify.classify(e)
        res["devices"][d] = dict(n=len(e), rate_per_h=len(e) / hours if hours else None,
                                 n_track=int((pred == "track").sum()))
    if {"top", "middle"} <= set(res["devices"]):
        scan = coincidence.lag_scan(ev.device_events("top"), ev.device_events("middle"), 200_000_000, 60_000_000_000)
        res["lag_scan_top_middle"] = dict(lags_s=(scan["lags_ns"] / 1e9).tolist(), counts=scan["counts"].tolist(),
                                          n_zero=scan["n_zero"], significance=scan["significance"])
    return res


if (ROOT / "dashboard").exists():
    app.mount("/", StaticFiles(directory=ROOT / "dashboard", html=True), name="dashboard")
