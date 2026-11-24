# PLAN

## Faz 0 — Yetenek taraması
Plan: repo iskeleti; Android `CapabilityProbe` (tüm kameralar + fiziksel alt kameralar → JSON; kopyala/paylaş/dosyaya kaydet).
Sonra: kullanıcı 3 telefonda çalıştırıp JSON'u `docs/devices/<cihaz>.json` olarak kaydeder → `config/devices.yaml` doldurulur.

Durum: kod yazıldı; **cihaz çıktıları bekleniyor**. Faz 1 kamera ayarları bu çıktılar görülmeden kesinleştirilmeyecek.

## Faz 3 — Monte Carlo (donanım verisinden bağımsız kısım, erken başlandı)
`sim/mc.py` (`python sim/mc.py --help`), testler `server/tests/test_mc.py`.
Varsayımlar: 7,6x5,7 mm üst; 6,4x4,8 mm orta/alt; 9 mm aralık; eps=0,7; duty=0,9; 1 müon/cm²/dk; cos²θ.
Sonuç (2M müon, tohum 1): üst tekil 16,4/sa; P(orta|üst)=%16,6 (doküman ~%17 ✓); P(üçü|üst)=%5,3; ikili 1,91/sa; **üçlü 0,43/sa** (~2,3 saatte bir).
Not: doküman 2.4'teki üçlü ~0,25/sa, %3 geometrik vuruşa dayanıyor; MC %5,3 buluyor (belgenin kendi %3–5 aralığının üstü). Doküman tahmini düşük kalmış; MC değeri esas alınmalı. Gerçek sensör boyutları Faz 0'dan gelince yeniden koşulacak.
Eksik: sentetik olay akışı üreteci (Faz 4 testleri için), kabul açısı düzeltmesi tablosu.

## Durum özeti (yazılım tarafı)
| Faz | Durum |
|---|---|
| 0 Yetenek taraması | Kod hazır, APK derlendi. **Kabul: 3 telefon JSON'u bekleniyor** (`docs/devices/`, `config/devices.yaml`). |
| 1 Tek telefon çekim | `CaptureService`/`FrameTrigger`/`DarkCalibration` yazıldı. Tetikleme JVM testleri geçti (yapay iz bulma >%95, saf gürültüde yanlış alarm ≈0). **8 saatlik cihaz testi yapılmadı.** YUV Y düzlemi 8-bit kullanıyor; RAW16 yolu Faz 0 çıktısına göre eklenecek. Bellek: tam çözünürlükte `DarkCalibration` büyük (çift hassasiyet) → profil sonrası NDK/Float'a geçilecek. |
| 2 Zaman senkronu + alım | `server/muon/timesync.py` (NTP+drift, GNSS eşleme, dokunma testi) testli; Android `TimeSync`/`Uploader` yazıldı, derleniyor. **Dokunma testiyle <5 ms doğrulaması cihazlarda yapılmadı.** Sunucu: `/sync /ingest /runs /events /coincidences /stats`, idempotent ingest testli. |
| 3 Monte Carlo | Bitti (oranlar + sentetik akış üreteci). Kabul açısı: `mc.accepted_zenith`. |
| 4 Çakışma | Kod + sentetik test tamam. **Gerçek veride ≥5σ yok (veri yok).** |
| 5 Sınıflandırma | Kural tabanlı + karışıklık matrisi (sentetik). CNN: etiket yok, denenmedi (kurala uygun). |
| 6 3B + hizalama | İz fit, hizalama (orta sensör dx,dy,rot) testli; dashboard `dashboard/index.html` (Plotly + Three.js; tarayıcıda denenmedi). |
| 7 Fizik sonuçları | `scripts/make_results.py` hazır; **gerçek sonuç yok**, RESULTS.md sentetik. |

Bilinen sınırlar: hizalama yalnızca orta sensörü çözer (üst/alt referans); üçlü sayısı arttıkça tüm sensörler için genişletilebilir.
