# RESULTS

> **Bu dosyadaki sayılar SENTETİK veridir (`sim/synth.py`, 500 saat, tohum 11).** Gerçek ölçüm yoktur; hiçbir fiziksel
> iddia içermez. Amaç: analiz hattının bilinen girdiyi geri bulduğunu göstermek. Gerçek veriyle yeniden üretmek için:
> `python scripts/make_results.py --run data/<kosu>.jsonl` (şekiller `docs/figures/`).

| Test | Girdi (doğru değer) | Hattın bulduğu |
|---|---|---|
| Çakışma, top–middle, sıfır gecikme | – | 800 olay, arka plan 223 → fazlalık 577, **29,8σ** (Li&Ma) |
| Üçlüler | – | 75 ham → 64 (üçü de iz-benzeri) |
| Hizalama (orta sensör) | dx=+0,12 mm, dy=−0,08 mm, rot=0,015 rad | dx=0,118±0,016, dy=−0,082±0,016, rot=0,0147±0,009; medyan artık 0,151 → 0,0026 mm |
| H (DECO MLE, tek telefon, iz adayları) | 25 px | top 24,9±0,2; middle 25,2±0,3; bottom 23,2±0,2 |
| H (çakışma kalibrasyonu, L = H tanθ + l0) | 25 px | 24,2±0,7 (n=64) |
| Zenit (üçlüler, MC kabul düzeltmeli) | cos²θ | en iyi k=0 (χ²=4,5), k=2 için χ²=4,9, ndof=5 → **ayırt edemiyor** |
| Sınıflandırıcı (kural tabanlı) | – | nokta/solucan %100; müon izlerinin 68/16443'ü (kısa, θ≈0) "nokta" sanıldı |

## Dürüst notlar
- **Zenit testi zayıf:** üçlü kabul açısı dar (tanθ ≲ 0,3), n=64 ile cos^k üssü ayırt edilemiyor. Gerçek veride yüzlerce üçlü ve daha geniş açı için ikili çakışmalar gerekir.
- **H kalibrasyonu da aynı nedenle dar kaldıraçlı;** serbest kesişim l0 piksel ayak izini emer.
- **Bottom için H=23,2 (sapma ~7σ):** iz-sınıfı kesmesi ve lmin ile sistematik yanlılık; gerçek veride sistematik belirsizlik ayrıca verilmeli.
- **Sahte üçlüler:** gerçek ikili + üçüncü sensörde gürültü kümesi, ham üçlülerin ~%15–35'ini oluşturur; iz-benzeri kesmesi şart (`classify.track_triples`).
- Rastlantısal oran–pencere grafiği, 200 ms kare adımı ve faz kaymaları nedeniyle basamaklı çıkar (`docs/figures/accidental_vs_window.png`).
- MC beklentisi: üçlü ≈ 0,43/saat (bkz. PLAN.md; belgedeki 0,25'ten yüksek).
- Çatı/bodrum karşılaştırması (opsiyonel Faz 7 maddesi) yapılmadı: ölçüm gerektirir.
