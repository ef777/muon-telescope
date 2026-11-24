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
