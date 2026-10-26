# BIST Sabah Taraması

Tam zamanlı çalışıp borsayı sürekli takip edemeyen, sabah **10:30'dan sonra**
BIST'te 1-2 hisseyi kısa vadeli (day-trade) almak isteyenler için basit,
kural tabanlı bir teknik ön-eleme aracı.

> **Bu bir yatırım tavsiyesi değildir.** Araç; trend, momentum ve hacim gibi
> teknik göstergelere göre kural tabanlı bir puanlama yapar. Kâr garantisi
> vermez. Karar ve risk tamamen kullanıcıya aittir. Özellikle küçük
> sermayeyle day-trading, komisyonsuz olsa bile **yüksek risklidir** —
> kaybedebileceğinizden fazlasını asla riske atmayın.

## Ne yapar?

1. `data/bist_tickers.csv` içindeki ~634 BIST hissesinin (İş Yatırım
   verisinden türetilmiştir) güncel verisini Yahoo Finance üzerinden çeker.
2. Her hisse için:
   - Günlük trend (EMA20/EMA50), RSI(14), MACD,
   - Bugünün açılışından (10:00) şu ana kadarki fiyat değişimi,
   - 10:00-10:30 açılış aralığının yukarı kırılıp kırılmadığı,
   - Güne özgü (relatif) işlem hacmi
   gibi göstergeleri hesaplar.
3. Bunları 0-100 arası bir puana çevirir, en likit/en güçlü adayları sıralar.
4. Her aday için ATR bazlı **stop-loss** ve **take-profit** (kâr alma)
   seviyesi önerir — bu seviyeleri MİDAS uygulamasında siz emir olarak
   girersiniz (uygulama MİDAS'a bağlanmaz, otomatik emir göndermez).

## Neden MİDAS'a bağlı değil?

MİDAS'ın (ya da çoğu Türk aracı kurumun) genel kullanıma açık bir "otomatik
emir gönder" API'si yoktur. Bu yüzden araç sadece **öneri** üretir; alım,
stop-loss ve take-profit emirlerini MİDAS uygulamasında siz giriyorsunuz.

## Kurulum (yerel)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub + Streamlit Community Cloud ile yayınlama

1. Bu klasörü kendi GitHub hesabınızda **yeni bir repo**ya yükleyin:
   ```bash
   cd bist-gunluk-tarama
   git init
   git add .
   git commit -m "İlk sürüm"
   git branch -M main
   git remote add origin https://github.com/<kullanici-adiniz>/bist-gunluk-tarama.git
   git push -u origin main
   ```
2. [share.streamlit.io](https://share.streamlit.io) adresine GitHub
   hesabınızla giriş yapın.
3. "New app" → reponuzu seçin → ana dosya olarak `app.py`'yi gösterin →
   Deploy.
4. Her sabah 10:30'dan sonra uygulamanın linkini açıp **"Taramayı Başlat"**
   butonuna basmanız yeterli; uygulama o anki canlı veriyi çeker (sabit/
   zamanlanmış bir görev gerekmez).

## Ayarlanabilir parametreler (sol panel)

- **Taranacak evren**: Tüm BIST (yavaş, ~600+ hisse) ya da en likit N hisse
  (varsayılan ve önerilen — hızlı ve küçük sermaye için daha güvenli, çünkü
  düşük hacimli hisselerde giriş/çıkışta kayma riski yüksektir).
- **Minimum ortalama hacim**: Likidite filtresi.
- **RSI aralığı, açılıştan % değişim aralığı, göreli hacim**: Sinyal
  eşikleri.
- **ATR çarpanı / Risk-Ödül oranı**: Stop-loss mesafesi ve buna göre
  take-profit hesaplanır.

## Veri kaynağı ve sınırlamalar

- Fiyat/hacim verisi **Yahoo Finance** (`yfinance`) üzerinden ücretsiz
  çekilir; gerçek zamanlı olmayabilir, bazı hisselerde birkaç dakika
  gecikmeli veya eksik olabilir.
- `data/bist_tickers.csv` dosyasını periyodik olarak güncellemeniz
  gerekebilir (yeni halka arzlar, kod değişiklikleri vb. için).
- Yahoo Finance aynı anda çok fazla istek atıldığında geçici olarak hız
  sınırlaması uygulayabilir; bu yüzden tarama, hisseleri gruplar halinde
  indirir ve "en likit N hisse" modu varsayılan olarak önerilir.

## Sorumluluk Reddi

Bu yazılım "olduğu gibi" sunulmuştur, herhangi bir yatırım danışmanlığı
teşkil etmez ve Anthropic ya da MİDAS ile bir bağlantısı yoktur. Borsa
yatırımları risk içerir, geçmiş performans gelecekteki sonuçların garantisi
değildir.
