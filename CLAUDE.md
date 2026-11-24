# Proje: Telefon CMOS Müon Çakışma Teleskobu

> Bu dosya Claude Code'a verilecek ana görev tanımıdır. Repo kök dizinine `CLAUDE.md` adıyla koy ya da ilk mesaj olarak yapıştır.
> Dil: dokümantasyon Türkçe, kod/değişken/commit mesajları İngilizce.

---

## 0. Senin rolün ve çalışma kuralların (Claude Code için)

Sen bu projede fizik + yazılım mühendisi olarak çalışıyorsun. Kullanıcı (Efe) fizik öğrencisi ve kıdemli mobil geliştirici; Kotlin/Flutter, FastAPI ve Python biliyor. Ona temel şeyleri anlatma, kararlarının gerekçesini kısa yaz.

Kurallar:

1. **Faz faz ilerle.** Aşağıdaki fazları sırayla yap. Bir fazın kabul kriterleri sağlanmadan bir sonrakine geçme. Her fazın başında `docs/PLAN.md` içine kısa bir plan yaz, sonunda ne yaptığını ve neyin test edildiğini ekle.
2. **Donanım hakkında uydurma.** Telefonların hangi özellikleri desteklediğini (RAW, timestamp kaynağı, sıcak piksel modu, ISO aralığı vb.) tahmin etme. Faz 0'daki yetenek taramasını yaz, kullanıcıdan gerçek cihazlarda çalıştırıp çıktıyı yapıştırmasını iste, kararları o çıktıya göre ver.
3. **Fiziksel sonuç uydurma.** "Müon algılandı" demek için çakışma analizi ve rastlantısal arka plan tahmini şart. Tek telefondaki parlak çizgi "müon adayı"dır, müon değil.
4. **Önce simülasyon, sonra ölçüm.** Beklenen oranları Monte Carlo ile ölçümden önce hesapla. Ölçüm sonuçlarını hep beklentiyle karşılaştır.
5. **Test et.** Analiz kodunun her parçası sentetik veriyle test edilsin (pytest). Android tetikleme algoritması sentetik karelerle (gürültü + yapay iz) birim testinden geçsin.
6. **Küçük commit'ler.** Her mantıklı adımda commit at. Büyük mimari değişiklikten önce kullanıcıya sor.
7. **Deney günlüğü.** Her gerçek ölçüm koşusu `docs/RUNLOG.md` içine tarih, cihazlar, dizilim, süre, sıcaklık, olay sayıları ve notlarla yazılsın.
8. Birimler SI; zaman damgaları nanosaniye (int64); uzunluklar mm (geometri) ve piksel (sensör içi).

---

## 1. Amaç

Üç Android telefonun kamera sensörlerini (lensleri ışık geçirmez şekilde kapatılmış) üst üste dizip **kozmik ışın müonlarını çakışma (coincidence) yöntemiyle** algılayan, izlerini 3B olarak yeniden oluşturan ve ölçülebilir fizik sonuçları üreten bir sistem.

### Ölçülecek fizik çıktıları (projenin asıl değeri)

1. **Müon zenit açısı dağılımı** ve beklenen `I(θ) ∝ cos²θ` ile karşılaştırma (kabul açısı düzeltmesi Monte Carlo ile).
2. **Her telefonun sensör aktif (tükenim) katman kalınlığı H**: iz uzunluğu dağılımından (DECO yöntemi) ve çakışmadan bilinen açıya sahip izlerden doğrudan kalibrasyonla.
3. **Rastlantısal çakışma oranının zaman penceresine bağımlılığı** (senkronizasyonun çalıştığının kanıtı).
4. **Sensör hizalamasının izlerden çözülmesi** (track-based alignment).
5. *(Opsiyonel)* Çatı ve bodrum katta akı karşılaştırması: beton kalınlığına bağlı zayıflama.

### Kapsam dışı (bilerek yapılmayacak)

- **Müonla konum bulma / navigasyon.** Telefon kamerasının zaman çözünürlüğü kare süresi kadardır (onlarca–yüzlerce ms). Tokyo'nun muPS/MuWNS sistemi nanosaniye düzeyinde uçuş süresi ölçer; bu donanımla imkânsız. Akı haritasıyla konum ise nokta başına onlarca–yüzlerce saat ölçüm ister.
- **"Gerçek zamanlı" gösteri.** Üçlü çakışma birkaç saatte bir gelir. Arayüz canlıdır ama veri yavaş birikir; bunu uzun pozlama gibi düşün.

---

## 2. Fiziksel temel ve beklenen oranlar

### 2.1 Müon akısı ve açı dağılımı
- Deniz seviyesinde yatay bir yüzeyden geçen müon akısı ≈ **1 müon / cm² / dakika** (Konya ~1000 m rakımda biraz daha yüksek).
- Yoğunluk açı dağılımı: `I(θ) ∝ cos²θ`. Yatay düzlemden geçen akı için örnekleme: `cosθ = (1 − u)^(1/4)`, `u ~ U(0,1)` (yani pdf ∝ cos³θ sinθ).
- Müonlar minimum iyonlaştırıcı parçacıktır (MIP); silisyumda yaklaşık 80 elektron-boşluk çifti/µm üretir.

### 2.2 CMOS sensörde iz geometrisi
- Sensör aktif katman kalınlığı `H` (piksel biriminde), iz uzunluğu `L` (piksel): `L = H · tanθ`.
- Kozmik müon açı dağılımı altında iz uzunluğu dağılımı (DECO, Vandenbroucke ve ark.):

  `dN/dL ∝ L · H⁴ / (L² + H²)³`

- Bu formül tek telefondaki müon adaylarından `H`'yi uydurmak (fit) için kullanılır.

### 2.3 Sensör verimi (literatür)
- Swaney ve ark. (2021) telefon CMOS'larının müon verimini sintilatör çakışmasıyla ölçtü: iyi sensörlerde ε ≈ 0,7–0,87; ama **dinamik sıcak piksel düzeltmesi** açık olan bir sensörde ε ≈ 0,27 çıktı (ISP müon izlerini sıcak piksel sanıp siliyor). Bu yüzden Faz 0'da `HOT_PIXEL_MODE_OFF` desteği kritik.

### 2.4 Beklenen oranlar (ön tahmin — Faz 3'te kendi MC'nle yeniden hesapla)
Varsayımlar: üst sensör ~7,6 × 5,7 mm (1/1.67"), alt sensörler ~6,4 × 4,8 mm (1/2"), sensörler arası ~9 mm, ε = 0,7, çalışma oranı (duty cycle) %90, deniz seviyesi akısı.

| Büyüklük | Tahmin |
|---|---|
| Üst telefon tek başına müon | ~16 / saat |
| Üstten geçenin ortadakine de çarpma olasılığı | ~%17 |
| Üstten geçenin üçüne de çarpma olasılığı | ~%3–5 |
| İkili çakışma (üst+orta) | ~1,7 / saat |
| Üçlü çakışma | ~0,25 / saat (≈ 4 saatte bir) |
| ε = 0,3 olan bir telefon varsa üçlü | günde birkaç |

### 2.5 Rastlantısal (accidental) çakışma
İki cihaz, olay oranları R₁, R₂ ve pozlama süreleri T₁, T₂ ise yaklaşık:

`R_acc ≈ R₁ · R₂ · (T₁ + T₂)`

Arka plan (gama "nokta", beta "solucan", gürültü) oranları müondan yüksek olabilir; bu yüzden rastlantısal oran **zaman kaydırma yöntemiyle** ölçülecek (bir cihazın zaman eksenini ±k saniye kaydırıp çakışma say; sıfır gecikmedeki fazlalık = gerçek çakışma).

---

## 3. Donanım düzeneği

- Cihazlar: **Redmi Note 13, Galaxy A37, Galaxy A12** (farklıysa `config/devices.yaml` içinden değiştir).
- Lensler siyah elektrik bandı + üstüne alüminyum folyo ile kapatılır; ekranlar kapalı; düzenek karanlık bir kutuda.
- Telefonlar, kamera modülleri dikey eksende üst üste gelecek şekilde, aralarında ince sabit ara parçalarla dizilir (3B baskı veya karton kalıp). Sensör konumları cetvelle ölçülüp `config/geometry.yaml`'a yazılır; kesin değerler Faz 6'da izlerden hizalanır.
- Şarjda çalışır; ısı izlenir. Pil sıcaklığı 42 °C'yi geçerse çekim otomatik durur, soğuyunca devam eder.

---

## 4. Mimari

```
muon-telescope/
├── CLAUDE.md                 # bu dosya
├── android/                  # Kotlin, Camera2, foreground service
│   └── app/
├── server/                   # Python 3.11+, FastAPI: senkron, veri alımı, analiz API
│   ├── muon/
│   │   ├── ingest.py
│   │   ├── timesync.py
│   │   ├── coincidence.py
│   │   ├── classify.py
│   │   ├── tracks.py         # iz parametreleri, 3B fit
│   │   ├── alignment.py
│   │   └── depletion.py      # H fit
│   └── tests/
├── sim/                      # Monte Carlo: kabul açısı, beklenen oranlar, sentetik veri
├── dashboard/                # statik web: Plotly + Three.js, FastAPI'den servis edilir
├── config/
│   ├── devices.yaml
│   └── geometry.yaml
├── data/                     # .gitignore — ham olaylar, koşular
└── docs/
    ├── PLAN.md
    ├── RUNLOG.md
    └── RESULTS.md
```

### 4.1 Android uygulaması (Kotlin, native)
Kamera çekirdeği **native Kotlin + Camera2** olmalı (Flutter kamera eklentisi manuel sensör kontrolü vermez). Arayüz minimal Jetpack Compose. İstenirse ileride Flutter UI, MethodChannel ile bu çekirdeği kullanabilir; ama çekim her durumda native kalır.

Bileşenler:
- `CapabilityProbe`: Faz 0 raporu.
- `CaptureService` (foreground service, wake lock): sürekli çekim.
- `FrameProcessor`: karanlık kalibrasyon, sıcak piksel maskesi, tetikleme, kırpma.
- `TimeSync`: zaman damgası eşleme (bkz. 4.3).
- `Uploader`: olayları LAN üzerinden sunucuya gönderir; bağlantı yoksa yerelde tutar, sonra gönderir (offline-first).

### 4.2 Kamera ayarları (Faz 0 sonucuna göre uygulanır)
- `CONTROL_MODE = OFF`, `CONTROL_AE_MODE = OFF`, `CONTROL_AF_MODE = OFF`
- `NOISE_REDUCTION_MODE = OFF`, `EDGE_MODE = OFF`, `HOT_PIXEL_MODE = OFF` (destekleniyorsa), `SHADING_MODE = OFF` (destekleniyorsa)
- Maksimum analog ISO (`SENSOR_SENSITIVITY`), pozlama süresi ≈ kare süresi (çalışma oranını maksimize et; ör. 5–10 fps, 100–200 ms pozlama).
- Tercih sırası: RAW_SENSOR → YUV_420_888 (yalnızca Y düzlemi). JPEG kullanma.
- Çözünürlük: tam çözünürlük tercih; performans yetmezse binning'li mod, ama piksel boyutu buna göre metadata'ya yazılsın.

### 4.3 Zaman senkronizasyonu (en az ikisi birlikte, karşılaştırmalı)
Hedef: cihazlar arası ofset < 5 ms (kare süresi ≥ 100 ms olduğu için bu fazlasıyla yeterli).

1. **Kamera zaman damgası tabanı:** `SENSOR_INFO_TIMESTAMP_SOURCE == REALTIME` ise `SENSOR_TIMESTAMP`, `SystemClock.elapsedRealtimeNanos()` ile aynı tabandadır. `UNKNOWN` ise kamera callback'lerindeki zamanlarla ampirik eşleme yap ve bunu belirsizlik olarak raporla.
2. **GNSS:** `Location.getElapsedRealtimeNanos()` + `Location.getTime()` (UTC) ile elapsedRealtime → UTC eşlemesi (ms düzeyi). Mümkünse `GnssClock` (API 29+, `getElapsedRealtimeNanos()`) ile daha hassas eşleme.
3. **LAN NTP benzeri:** Sunucuyla WebSocket/UDP üzerinden t1–t4 değiş tokuşu; en düşük gidiş-dönüş süreli örneklerle ofset ve sürüklenme (drift) tahmini.
4. **Dokunma senkronu (doğrulama):** Telefonlar üst üste dururken yığına bir kez vurulur; ivmeölçerdeki ortak darbe zamanları karşılaştırılarak 1–3 yönteminin doğruluğu ölçülür.

Her olay hem ham `sensor_ts_ns` hem de hesaplanmış `utc_ns` ve `utc_uncertainty_ns` ile kaydedilir.

### 4.4 Cihaz üstü olay tespiti
1. **Karanlık kalibrasyon (60 s):** piksel başına ortalama ve standart sapma; sürekli parlak pikseller sıcak piksel maskesine.
2. **Tetikleme:** maskelenmiş karede `x > μ + k·σ` (k ≈ 5–8, ayarlanabilir) olan pikseller → 8-komşuluk bağlı bileşenler.
3. **Kayıt:** her küme için 64×64 kırpma (ham değerler, 16 bit) + metadata. Kare başına üst sınır (ör. 10 küme) koy; aşılırsa kareyi "ışık sızıntısı/gürültü" olarak işaretle.
4. Performans: önce saf Kotlin; profil sonucu yetmezse sıcak döngüyü NDK/C++'a taşı. Tam kareyi asla diske yazma.

### 4.5 Olay veri modeli (JSONL + kırpma dosyası)
```json
{
  "device_id": "redmi_note13",
  "run_id": "2026-11-25T21-00Z_stackA",
  "frame_idx": 123456,
  "sensor_ts_ns": 0,
  "exposure_ns": 150000000,
  "frame_duration_ns": 200000000,
  "utc_ns": 0,
  "utc_uncertainty_ns": 0,
  "iso": 0,
  "cluster": {
    "x_px": 0, "y_px": 0,
    "n_pix": 0, "sum_adu": 0, "max_adu": 0,
    "length_px": 0.0, "width_px": 0.0, "angle_rad": 0.0, "eccentricity": 0.0
  },
  "crop_file": "crops/redmi_note13/123456_0.npy",
  "battery_temp_c": 0.0,
  "orientation_quat": [0, 0, 0, 1]
}
```

### 4.6 Sunucu (FastAPI)
- `/sync`: zaman senkron uç noktası.
- `/ingest`: olay toplu yükleme (idempotent; `device_id + frame_idx + cluster index` tekil anahtar).
- `/runs`, `/events`, `/coincidences`, `/stats`: analiz sonuçları.
- Analiz modülleri sunucu çalışmadan da CLI olarak çalışabilmeli (`python -m muon.coincidence --run ...`).

### 4.7 Dashboard
- Cihaz başına canlı olay oranı (saatlik), sıcaklık, çalışma oranı.
- Olay galerisi (kırpmalar, sınıf etiketiyle).
- Çakışma listesi ve **3B görünüm** (Three.js): sensör yığını ölçekli, yeniden oluşturulan izler doğru olarak; yeni çakışma gelince eklenir.
- Grafikler: zenit histogramı + MC beklentisi, iz uzunluğu dağılımı + H fit'i, gecikme (lag) taramasında çakışma sayısı.

---

## 5. Fazlar ve kabul kriterleri

### Faz 0 — Yetenek taraması
Her telefonda çalışan küçük bir ekran/uygulama: tüm kameraları listeler ve her biri için şunları JSON olarak verir: `SENSOR_INFO_PHYSICAL_SIZE`, `SENSOR_INFO_PIXEL_ARRAY_SIZE`, `SENSOR_INFO_ACTIVE_ARRAY_SIZE`, RAW desteği, `SENSOR_INFO_TIMESTAMP_SOURCE`, ISO ve pozlama aralıkları, `HOT_PIXEL_AVAILABLE_HOT_PIXEL_MODES`, `NOISE_REDUCTION_AVAILABLE_NOISE_REDUCTION_MODES`, `INFO_SUPPORTED_HARDWARE_LEVEL`, desteklenen YUV/RAW boyutları ve min. kare süreleri.
**Kabul:** üç telefonun raporu `docs/devices/` altına kaydedildi; her telefon için hangi kameranın ve hangi modun kullanılacağı `config/devices.yaml`'da gerekçesiyle yazıldı.

### Faz 1 — Tek telefon çekim ve olay kaydı
**Kabul:** kesintisiz 8 saat çalışma; sıcak piksel maskesi üretiliyor; olay oranı zamanla kararlı (±%20); kırpmalarda nokta/solucan/çizgi tipleri görülüyor; tetikleme sentetik kare testlerinden geçiyor (yapay iz bulma oranı > %95, saf gürültüde yanlış alarm < 1/saat ölçeğinde).

### Faz 2 — Zaman senkronu ve sunucuya veri alımı
**Kabul:** dokunma testiyle ölçülen cihazlar arası ofset < 5 ms; 3 telefonun verisi sunucuda tek zaman ekseninde; bağlantı kopunca veri kaybolmuyor.

### Faz 3 — Monte Carlo
`sim/` içinde: sensör boyutları + yığın geometrisi + cos²θ + verim + çalışma oranı → tekil/ikili/üçlü beklenen oranlar; ayrıca analiz kodunu test etmek için sentetik olay akışı üreteci (gerçek müonlar + arka plan + zaman gürültüsü).
**Kabul:** Bölüm 2.4'teki tahminler bağımsız olarak yeniden üretildi; analiz hattı sentetik veride bilinen çakışmaları geri buluyor.

### Faz 4 — Çakışma analizi
Pozlama aralıkları örtüşen olayları eşle (aralık birleşimi + küçük güvenlik payı); gecikme taraması (±60 s, adım = kare süresi) ile rastlantısal arka planı ölç; sıfır gecikmede fazlalığın Poisson anlamlılığını hesapla.
**Kabul:** gerçek veride sıfır gecikmede anlamlı fazlalık (≥ 5σ hedef; olmuyorsa neden olmadığını raporla); oranlar MC ile karşılaştırıldı.

### Faz 5 — Sınıflandırma
Önce kural tabanlı (iz uzunluğu, eksantriklik, toplam yük); çakışmayla doğrulanmış izler "kesin müon" etiketi olarak kullanılsın. Yeterli etiket birikirse (yüzlerce) küçük bir CNN dene; yoksa CNN'e zorlama.
**Kabul:** çakışmalı izlerde sınıflandırıcı "müon" oranı raporlandı; karışıklık matrisi sentetik veride hesaplandı.

### Faz 6 — 3B yeniden oluşturma ve hizalama
Piksel → mm (piksel aralığı), sensör → yığın koordinatı (`geometry.yaml`). Üçlülerde doğru fiti; ikililerde iki vuruş noktası + sensör içi iz yönü. Üçlülerin artıklarını (residual) en aza indirerek her sensörün (dx, dy, dönme) hizasını çöz.
**Kabul:** hizalama sonrası artıklar hizalama öncesine göre belirgin azaldı; 3B dashboard çalışıyor.

### Faz 7 — Fizik sonuçları
`docs/RESULTS.md`: zenit dağılımı vs cos²θ (MC kabul düzeltmeli, χ²), her telefon için H (DECO fiti ve çakışma kalibrasyonu, belirsizlikleriyle), rastlantısal oran vs pencere, (opsiyonel) çatı/bodrum karşılaştırması. Tüm grafikler `docs/figures/` altında üretilebilir script'lerle.

---

## 6. Kod kalitesi

- Python: `ruff` + `mypy` (gevşek mod), `pytest`; analiz fonksiyonları saf ve test edilebilir.
- Kotlin: tetikleme ve küme çıkarma mantığı Android'den bağımsız saf Kotlin modülünde, JVM birim testleriyle.
- Konfigürasyon YAML'da; sabitler koda gömülmesin.
- Her script `--help` versin; tekrar üretilebilirlik için rastgelelik tohumlu.

---

## 7. Kaynaklar

- DECO: *Detecting particles with cell phones: the Distributed Electronic Cosmic-ray Observatory*, arXiv:1510.07665
- Vandenbroucke ve ark., *Measurement of camera image sensor depletion thickness with cosmic rays*, JINST 11 (2016) P04019, arXiv:1511.00660
- Swaney ve ark., *Measurement of Smartphone Sensor Efficiency to Cosmic Ray Muons*, arXiv:2107.06332
- CREDO projesi, arXiv:2009.12314
- Android Camera2 API: `CameraCharacteristics`, `CaptureRequest`, `CaptureResult.SENSOR_TIMESTAMP`; GNSS: `GnssClock`, `Location.getElapsedRealtimeNanos()`

---

## 8. İlk görev

Faz 0'dan başla:
1. Repo iskeletini oluştur (Bölüm 4 yapısı, boş modüller, `.gitignore`, `README.md`).
2. Android `CapabilityProbe` ekranını yaz; çıktıyı JSON olarak paylaşılabilir/kopyalanabilir yap.
3. Kullanıcıdan üç telefonda çalıştırıp çıktıları yapıştırmasını iste. O çıktıları görmeden Faz 1'in kamera ayarlarını kesinleştirme.
