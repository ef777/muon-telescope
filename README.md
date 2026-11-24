# Muon Telescope

Telefon CMOS sensörleriyle müon çakışma teleskobu. Görev tanımı: [CLAUDE.md](CLAUDE.md). Plan/ilerleme: [docs/PLAN.md](docs/PLAN.md).

- `android/` — Kotlin/Camera2 uygulaması (şu an: Faz 0 CapabilityProbe)
- `server/` — FastAPI + analiz (`muon/`)
- `sim/` — Monte Carlo
- `config/` — `devices.yaml`, `geometry.yaml`
- `docs/devices/` — telefonlardan alınan yetenek raporları (JSON)

## Komutlar
```
python -m pytest -q server/tests                       # analiz + sunucu testleri
python sim/mc.py                                       # beklenen oranlar (MC)
python sim/synth.py --hours 48 --out data/synth.jsonl  # sentetik akış
python -m muon.coincidence --run data/synth.jsonl      # (cd server) çakışma + gecikme taraması
python scripts/make_results.py --synthetic             # şekiller + results.json
uvicorn app:app --app-dir server --port 8000           # sunucu + dashboard
cd android && ./gradlew assembleDebug testDebugUnitTest
```
