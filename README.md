# PRISM — Kişisel AI Asistan

Telegram ve web panelinden doğal Türkçe ile kullanılan, kendi sunucusunda
barındırılan kişisel asistan. Python/FastAPI + SQLite; Oracle Cloud'un ücretsiz
katmanındaki **954 MB RAM**'li bir sanal makinede çalışıyor.

Hatırlatıcı, not, harcama, bütçe, hava durumu ve günlük özet — hepsi konuşma
diliyle: *"yarın 14:30'da doktor randevusu, kritik"*, *"bugün 85 TL yemek
harcadım"*, *"bu ayın özetini ver"*.

> Bu bir ürün değil, günlük kullandığım bir sistem. Kodun ilginç yanı özellik
> listesi değil, **hangi kararın neden verildiği**; onu `CLAUDE.md` anlatıyor
> (mimari notlar, ~1.500 satır).

## Öne çıkan iki tasarım kararı

### 1. Kendiliğinden konuşan asistan — ama uydurmayan

Çoğu asistan yalnız sorulunca cevap verir. PRISM'in ikinci bir döngüsü var
(`modules/gozlem/`): iki saatte bir "söylenmeye değer bir şey var mı?" diye
bakıyor ve varsa kendisi yazıyor — *"yarın 09:00–12:00 arası yağış bekleniyor"*,
*"telefondaki harcama dinleyicisi üç gündür sessiz"*.

Buradaki asıl mesele halüsinasyon. Kendiliğinden gelen bir mesajdaki uydurma
bilgi, sorulunca gelendekinden çok daha zararlı: kullanıcı onu beklemiyordu,
bağlamı yok, doğruluğunu kontrol etmek için sebebi yok. Çözüm bir kural:

> **Olguyu kod bulur** (SQL + aritmetik, `sinyaller.py`).
> **Model yalnızca** "bu söylenmeye değer mi ve nasıl söylenir" sorusunu
> cevaplar.

Model eline yalnız hazır kanıt metinleri geçiyor; sayı, tarih, isim
üretemiyor. Susmak varsayılan, konuşmak istisna — yedi kapılı bir susma
bütçesi var ve turların çoğu modele hiç uğramadan bitiyor. Testlerin çoğu
asistanın **konuşmadığını** doğruluyor.

Bu katmanın gelişimi sırasında öğrenilen bir şey CLAUDE.md'de ayrıca yazılı:
*bir yargıyı modele bırakmak, o yargının ölçütünü yönergeye yazmadıkça
bırakılmış sayılmıyor.*

### 2. Banka bildiriminden otomatik harcama kaydı

`mobileapp/` — Android'de `NotificationListenerService` ile banka
bildirimlerini okuyup sunucuya gönderen küçük bir uygulama. Web'de karşılığı
yok: tarayıcı bildirim *gösterebiliyor* ama başkasının bildirimini
*okuyamıyor*.

Gizlilik kararları bilinçli:

- Ham bildirim metni **hiçbir yerde saklanmıyor** — veritabanına yalnız
  SHA-256 özeti yazılıyor.
- OTP/şifre mesajları **iki kez** eleniyor: telefonda (hiç gönderilmiyor) ve
  sunucuda (modele bile gitmiyor).
- Loglara metin basılmıyor, yalnız paket adı ve sonuç.

Uygulamanın geri kalanı bilerek **silindi** (kodun %42'si): panel aynı işi daha
iyi yapıyor ve telefonda PWA olarak kurulabiliyor. Geriye yalnız yerli kodun
zorunlu olduğu tek yetenek kaldı.

## Mimari

```
Telegram ⇄ /webhook ┐
                    ├→ ai_router (Groq → JSON komut) → modüller → SQLite
Web panel (PWA)  ───┘                                     ↑
                                              APScheduler ─┘
                              (hatırlatıcı · özetler · gözlem turu · yedek)
```

| Katman | Seçim | Neden |
|---|---|---|
| LLM | Groq — Llama 3.3 70B | Ücretsiz katman, düşük gecikme; model adı env'den (Groq model emekliye ayırınca kod değişmiyor) |
| Ses → yazı | Groq Whisper | Telegram ve panel aynı motoru kullanıyor |
| Yazı → ses | ElevenLabs | Groq TTS Türkçe bilmiyor; yerel model 954 MB'a sığmıyor |
| Veritabanı | SQLite (WAL) | Tek sunucu, tek yazar; Postgres'in işletme yükü karşılıksız |
| Panel | React + Vite, PWA | Ana ekrana eklenince uygulama gibi açılıyor |
| Sunucu | systemd + Caddy | `Restart=always`, otomatik HTTPS |

Ayrıntılar ve her kararın gerekçesi → **[`CLAUDE.md`](CLAUDE.md)**.

## Dikkat çeken ayrıntılar

- **Sağlık kontrolü yalan söylemiyor.** `/health` yalnız "servis ayakta" demiyor;
  zamanlayıcının dakikalık işinin gerçekten tur attığını da kontrol ediyor
  (kalp atışı damgası). İş sessizce takılırsa 503 dönüyor — `scheduler.running`
  tek başına yeşil kalabiliyor.
- **Hatırlatıcı önceliği = kaç bildirim.** "Kalan süreye göre tekrarla" yaklaşımı
  bir hafta önceden kurulan tek bir kritik kayıt için 34 bildirim üretiyordu;
  yerine sabit bildirim noktaları geldi. Varsayılan en sessiz seviye.
- **İki kullanıcı, tek kural:** okuma serbest, yazma yalnız kendi kaydına.
  `owner_id` her zaman oturumdan gelir, istekten alınmaz.
- **Her gece Telegram'a yedek.** SQLite backup API ile tutarlı kopya → gzip →
  bota dosya olarak. Sunucu tamamen kaybolsa bile yedek sohbet geçmişinde.
- **Türkçeye özgü tuzaklar:** `"İ".lower()` fazladan bir birleşen nokta üretiyor
  ve isim eşleştirmeyi bozuyordu; emoji filtresi U+FE0F varyasyon seçicisini
  kaçırıp seslendirmede boşluk bırakıyordu. İkisi de testle kilitli.

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env          # doldur: TELEGRAM_TOKEN, GROQ_API_KEY, ...
uvicorn main:app --reload
```

Panel:

```bash
cd frontend && npm install && npm run dev
```

Kullanıcı eklemek (parola ve chat ID `.env`'e yazılmıyor — veritabanında,
parolalar scrypt karması olarak):

```bash
python kullanici.py ekle "Adınız"
python kullanici.py chat-id "Adınız" 123456789
```

Ortam değişkenlerinin tamamı `.env.example` içinde açıklamalı.
Yayına alma adımları → `CLAUDE.md` → **Deploy**.

## Testler

```bash
pip install -r requirements-dev.txt
pytest
```

218 test. Ağırlık doğru çalışmada değil, **yanlış çalışmama**da: başkasının
kaydını değiştirme denemesi 403 alıyor mu, kendiliğinden konuşma kapalıyken
gerçekten susuyor mu, ileti yanlış kişiye gidebilir mi, yedek geri
yüklenebiliyor mu. Her test geçici veritabanı kullanıyor.

## Lisans

MIT — bkz. [`LICENSE`](LICENSE).
