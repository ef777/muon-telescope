# RUNLOG

Her gercek kosu: tarih, cihazlar, dizilim, sure, sicaklik, olay sayilari, notlar.

## 2026-11-24 — EMÜLATÖR SİMÜLASYONU (gerçek ölçüm DEĞİL)
- Cihaz: Android emülatörü (Pixel 6 profili, API 35, x86_64). Kamera kullanılmadı: `CaptureService` simülasyon modu (sentetik gürültü + 5 sıcak piksel + enjekte edilmiş iz/nokta, olasılık 0,15/kare).
- Ayarlar: 320x240, 5 fps, 10 sn karanlık kalibrasyon (50 kare), k=6, sunucu `10.0.2.2:8765`.
- Sonuç (~100 sn): kalibrasyon bitti, tetikleme devrede, 0 taşma karesi; NTP-benzeri senkron başarılı (ofset = sunucu UTC − elapsedRealtime); 38 olay sunucuya ulaştı, 26'sı "iz" sınıfı; 64x64 int16 .npy kırpmalar numpy ile okunuyor.
- Doğrulanan: yakalama → tetikleme → senkron → spool → /ingest → /stats hattı. **Doğrulanmayan:** gerçek kamera, RAW, 8 saat kararlılık, ısı, cihazlar arası <5 ms.
- Yetenek taraması: `docs/devices/emulator_pixel6_api35.json` (emülatör; hedef telefon DEĞİL).

## 2026-11-24 — EMÜLATÖR SİMÜLASYONU #2 (gerçek ölçüm DEĞİL)
- Yeni APK: RAW16 yolu, ivmeölçer dokunma tespiti, GNSS çifti toplama, kırpma yükleme. Aynı sim ayarları (320x240, 5 fps, 10 sn kalibrasyon).
- **Emülatör bir hata yakaladı:** `HIGH_SAMPLING_RATE_SENSORS` izni eksikti, servis çöküyordu (API 31+). İzin eklendi.
- Sonuç (~75 sn): 38 olay ve 38 kırpma sunucuda; emülatöre enjekte edilen 2 sallamadan 4 dokunma kenarı `/tap`'a ulaştı; `/gnss` isteği alındı; ofset yine doğru.
- `/stability` kısa koşuda NaN yüzünden 500 veriyordu; düzeltildi ve test eklendi.
- Doğrulanmayan: RAW16 yolu (emülatör sanal kamerası kullanılmadı), gerçek kamera, GNSS gerçek fix, gerçek dokunma doğruluğu.
