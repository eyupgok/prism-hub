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
| `API_KEY` | REST API koruması (`X-API-Key` header). Boş bırakılırsa doğrulama devre dışı — sadece lokal |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook imza doğrulaması (boşsa devre dışı) |
| `WEBHOOK_URL` | Genel HTTPS adresi (ör: `https://kendi-alan-adin.example.com`). Boşsa webhook kurulmaz |
| `WEATHER_CITY` | Şehir adı (görüntüleme için) |
| `WEATHER_LAT` | Enlem |
| `WEATHER_LON` | Boylam |

## Deploy

Kendi sunucunda (VPS / Oracle Cloud gibi) çalışır. Özet:

1. Sunucuya kodu indir, `python3 -m venv venv && venv/bin/pip install -r requirements.txt`
2. `.env` dosyasını oluştur (`chmod 600`)
3. uvicorn'u systemd servisi yap — sadece `127.0.0.1:8000` dinlesin
4. Önüne Caddy (veya Nginx) koy — HTTPS sertifikasını o halletsin
5. `WEBHOOK_URL` = alan adın; uygulama açılışta Telegram webhook'unu kendisi kurar

Ayrıntılı kurulum notları ve sunucudaki yollar için `CLAUDE.md` → **Deploy** bölümüne bak.

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
