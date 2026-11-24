<div align="center">

# ⚛️ Muon Telescope

**A cosmic-ray muon coincidence telescope built from stacked smartphone camera sensors.**
**Üst üste dizilmiş telefon kamera sensörleriyle kozmik ışın müon çakışma teleskobu.**

[English](#-english) · [Türkçe](#-türkçe)

</div>

---

## 🇬🇧 English

### What is this?
Three Android phones, with their camera lenses sealed light-tight, are stacked so their CMOS sensors line up vertically. A cosmic-ray muon passing through the stack leaves a short ionisation track in each sensor. By matching events across phones in time (**coincidence**), the project reconstructs muon tracks in 3D and measures:

1. the **zenith-angle distribution** vs. the expected `cos²θ` (with Monte Carlo acceptance correction),
2. each sensor's **depletion-layer thickness H** (from track lengths, DECO method, and from coincidence-known angles),
3. the **accidental-coincidence rate** vs. time window (proof that time sync works),
4. **sensor alignment** solved from the tracks themselves,
5. *(optional)* roof vs. basement flux.

Out of scope on purpose: muon-based navigation (phone frame times are tens–hundreds of ms, far too coarse) and "real-time" display (triple coincidences arrive every few hours).

### Status — please read
| Part | State |
|---|---|
| Android capability probe (Phase 0) | ✅ built, **not yet run on the 3 target phones** |
| Android capture + trigger (Phase 1) | ✅ trigger unit-tested on JVM · ⚠️ capture service **not validated on hardware** |
| Time sync + ingest server (Phase 2) | ✅ server and tests · ⚠️ tap-test accuracy (<5 ms) **not measured** |
| Monte Carlo (Phase 3) | ✅ expected triple rate ≈ **0.43 / h** (the original estimate of 0.25 / h was low) |
| Coincidence, classification, 3D, alignment, H fit (Phases 4–7) | ✅ implemented and tested on **synthetic data only** |
| Real physics results | ❌ none yet — `docs/RESULTS.md` is synthetic and says so |

A bright streak on one phone is a *muon candidate*, not a muon. Claiming a detection requires coincidence **and** an accidental-background estimate (time-shift lag scan).

### Repository layout
```
android/    Kotlin + Camera2: CapabilityProbe, CaptureService, FrameTrigger (pure Kotlin), TimeSync, Uploader
server/     Python: FastAPI app + analysis (muon/: coincidence, classify, tracks, alignment, depletion, timesync)
sim/        Monte Carlo (mc.py) and synthetic event generator (synth.py)
dashboard/  Static web UI: Plotly charts + Three.js 3D view
scripts/    make_results.py → figures and results.json
config/     devices.yaml, geometry.yaml
docs/       PLAN.md, RUNLOG.md, RESULTS.md, devices/ (phone reports), figures/
```

### Quick start
```bash
# analysis + server tests (Python 3.11+: numpy scipy fastapi uvicorn pydantic pyyaml httpx matplotlib pytest)
python -m pytest -q server/tests

# expected rates for the default stack
python sim/mc.py

# synthetic run -> coincidence + lag scan -> figures
python sim/synth.py --hours 48 --out data/synth.jsonl
(cd server && python -m muon.coincidence --run ../data/synth.jsonl)
python scripts/make_results.py --synthetic

# server + dashboard at http://localhost:8000
uvicorn app:app --app-dir server --port 8000

# Android (JDK 17 + Android SDK)
cd android && ./gradlew assembleDebug testDebugUnitTest
```

### Hardware setup
- Phones: Redmi Note 13, Galaxy A37, Galaxy A12 (edit `config/devices.yaml` if different).
- Seal lenses with black electrical tape + aluminium foil; screens off; dark box; phones charging, capture pauses above 42 °C battery temperature.
- Measure sensor positions with a ruler into `config/geometry.yaml`; final values come from track-based alignment.
- Run the probe app on each phone, save the JSON to `docs/devices/`, and only then fix camera, format and ISO per phone.

### Method in short
- Camera2 manual sensor: AE/AF/NR/edge/**hot-pixel correction OFF** (dynamic hot-pixel filters can erase muon tracks), max analog ISO, exposure ≈ frame time.
- On-device: 60 s dark calibration → hot-pixel mask → `x > μ + kσ` → 8-connected clusters → 64×64 crops + features.
- Coincidence = overlapping exposure intervals; accidentals from a ±60 s lag scan; significance by Li & Ma.
- `dN/dL ∝ L·H⁴/(L²+H²)³` for H; `I(θ) ∝ cos²θ` expectation from Monte Carlo acceptance.

### References
DECO (arXiv:1510.07665) · Vandenbroucke et al., JINST 11 P04019 (arXiv:1511.00660) · Swaney et al. (arXiv:2107.06332) · CREDO (arXiv:2009.12314)

---

## 🇹🇷 Türkçe

### Bu nedir?
Kamera lensleri ışık geçirmez şekilde kapatılmış üç Android telefon, CMOS sensörleri dikey hizalanacak biçimde üst üste dizilir. Yığından geçen bir kozmik ışın müonu her sensörde kısa bir iyonlaşma izi bırakır. Olaylar telefonlar arasında zamanca eşleştirilerek (**çakışma**) müon izleri 3B yeniden oluşturulur ve şunlar ölçülür:

1. **Zenit açısı dağılımı** ve beklenen `cos²θ` ile karşılaştırma (Monte Carlo kabul düzeltmeli),
2. Her sensörün **tükenim katman kalınlığı H** (iz uzunluğundan, DECO yöntemi; ve çakışmayla bilinen açılardan),
3. **Rastlantısal çakışma oranının** zaman penceresine bağımlılığı (senkronizasyonun çalıştığının kanıtı),
4. İzlerden çözülen **sensör hizalaması**,
5. *(opsiyonel)* çatı ve bodrum akı karşılaştırması.

Bilerek kapsam dışı: müonla konum bulma (telefon kare süreleri onlarca–yüzlerce ms, çok kaba) ve "gerçek zamanlı" gösteri (üçlü çakışma birkaç saatte bir gelir).

### Durum — lütfen oku
| Parça | Durum |
|---|---|
| Android yetenek taraması (Faz 0) | ✅ derlendi, **3 hedef telefonda henüz çalıştırılmadı** |
| Android çekim + tetikleme (Faz 1) | ✅ tetikleme JVM'de birim testli · ⚠️ çekim servisi **donanımda doğrulanmadı** |
| Zaman senkronu + sunucu (Faz 2) | ✅ sunucu ve testler · ⚠️ dokunma testi doğruluğu (<5 ms) **ölçülmedi** |
| Monte Carlo (Faz 3) | ✅ beklenen üçlü oran ≈ **0,43 / saat** (ilk tahmin olan 0,25 / saat düşük kalmıştı) |
| Çakışma, sınıflandırma, 3B, hizalama, H fit'i (Faz 4–7) | ✅ yazıldı, **yalnızca sentetik veride** test edildi |
| Gerçek fizik sonuçları | ❌ henüz yok — `docs/RESULTS.md` sentetiktir ve bunu belirtir |

Tek telefondaki parlak çizgi *müon adayıdır*, müon değildir. "Algılandı" demek için çakışma **ve** rastlantısal arka plan tahmini (zaman kaydırmalı gecikme taraması) şarttır.

### Depo yapısı
```
android/    Kotlin + Camera2: CapabilityProbe, CaptureService, FrameTrigger (saf Kotlin), TimeSync, Uploader
server/     Python: FastAPI uygulaması + analiz (muon/: coincidence, classify, tracks, alignment, depletion, timesync)
sim/        Monte Carlo (mc.py) ve sentetik olay üreteci (synth.py)
dashboard/  Statik web arayüzü: Plotly grafikleri + Three.js 3B görünüm
scripts/    make_results.py → şekiller ve results.json
config/     devices.yaml, geometry.yaml
docs/       PLAN.md, RUNLOG.md, RESULTS.md, devices/ (telefon raporları), figures/
```

### Hızlı başlangıç
```bash
# analiz + sunucu testleri (Python 3.11+: numpy scipy fastapi uvicorn pydantic pyyaml httpx matplotlib pytest)
python -m pytest -q server/tests

# varsayılan yığın için beklenen oranlar
python sim/mc.py

# sentetik koşu -> çakışma + gecikme taraması -> şekiller
python sim/synth.py --hours 48 --out data/synth.jsonl
(cd server && python -m muon.coincidence --run ../data/synth.jsonl)
python scripts/make_results.py --synthetic

# sunucu + dashboard: http://localhost:8000
uvicorn app:app --app-dir server --port 8000

# Android (JDK 17 + Android SDK)
cd android && ./gradlew assembleDebug testDebugUnitTest
```

### Donanım düzeneği
- Telefonlar: Redmi Note 13, Galaxy A37, Galaxy A12 (farklıysa `config/devices.yaml`'ı düzenle).
- Lensleri siyah elektrik bandı + alüminyum folyo ile kapat; ekranlar kapalı; karanlık kutu; telefonlar şarjda, pil sıcaklığı 42 °C'yi geçince çekim durur.
- Sensör konumlarını cetvelle ölçüp `config/geometry.yaml`'a yaz; kesin değerler izlerden hizalamayla bulunur.
- Her telefonda probe uygulamasını çalıştır, JSON'u `docs/devices/` altına kaydet; kamera, format ve ISO kararlarını ancak ondan sonra ver.

### Yöntem özeti
- Camera2 manuel sensör: AE/AF/gürültü azaltma/kenar/**sıcak piksel düzeltmesi KAPALI** (dinamik sıcak piksel filtresi müon izlerini silebilir), maksimum analog ISO, pozlama ≈ kare süresi.
- Cihaz üstünde: 60 sn karanlık kalibrasyon → sıcak piksel maskesi → `x > μ + kσ` → 8-komşuluk kümeler → 64×64 kırpma + özellikler.
- Çakışma = örtüşen pozlama aralıkları; rastlantısal arka plan ±60 sn gecikme taramasıyla; anlamlılık Li & Ma ile.
- H için `dN/dL ∝ L·H⁴/(L²+H²)³`; `I(θ) ∝ cos²θ` beklentisi Monte Carlo kabul düzeltmesiyle.

### Kaynaklar
DECO (arXiv:1510.07665) · Vandenbroucke ve ark., JINST 11 P04019 (arXiv:1511.00660) · Swaney ve ark. (arXiv:2107.06332) · CREDO (arXiv:2009.12314)
