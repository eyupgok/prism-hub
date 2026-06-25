# PRISM — Kişisel AI Asistan Hub

Telegram + Web panel üzerinden yönetilen, modüler Python/FastAPI tabanlı kişisel asistan.

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env
# .env dosyasını doldurun
uvicorn main:app --reload
```

## Ortam Değişkenleri

| Değişken | Açıklama |
|---|---|
| `TELEGRAM_TOKEN` | BotFather'dan alınan bot token |
| `TELEGRAM_CHAT_ID` | Kendi chat ID'niz (`@userinfobot`'tan öğrenebilirsiniz) |
| `GROQ_API_KEY` | Groq API anahtarı (LLM + Whisper) |
| `WEBHOOK_URL` | Railway deploy URL'si (ör: `https://app.railway.app`) |
| `WEATHER_CITY` | Şehir adı (görüntüleme için) |
| `WEATHER_LAT` | Enlem |
| `WEATHER_LON` | Boylam |

## Railway Deploy

1. Bu repoyu GitHub'a push edin
2. Railway'de yeni proje oluşturun, GitHub repo'nuzu bağlayın
3. Environment Variables'a `.env` içeriğini girin
4. `WEBHOOK_URL` = Railway'in size verdiği URL

## Modüller

- **reminders** — Öncelik tabanlı hatırlatıcı sistemi (Telegram inline butonları ile)
- **notes** — Başlık/içerik/kategori bazlı not alma
- **expenses** — Harcama takibi ve aylık kategori özeti
- **weather** — Open-Meteo ücretsiz API (kayıt gerekmez)
- **summary** — Sabah 08:00 otomatik günlük özet

## Telegram Komutları (Doğal Dil)

```
Yarın saat 14:30'da doktor randevusu hatırlatıcısı ekle, kritik
Bugün 85 TL yemek harcadım, restoran
İş notlarıma bak
Proje fikirleri başlıklı bir not oluştur: ...
Hava nasıl?
Bu ayın harcama özetini ver
```
