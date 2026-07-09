# PRISM — Kişisel AI Asistan Hub

Eyüp'ün kişisel asistan projesi. Telegram üzerinden doğal Türkçe dille kontrol edilir.
Railway'de deploy edilmiş, SQLite tabanlı, modüler FastAPI uygulaması.

## Stack

- **Backend:** Python 3.11 + FastAPI
- **AI:** Groq API — `llama-3.3-70b-versatile` (NLP parsing) + `whisper-large-v3-turbo` (ses transkripsiyon) + `meta-llama/llama-4-scout-17b-16e-instruct` (görsel analiz)
- **DB:** SQLite (WAL mode) — `prism.db`
- **Zamanlayıcı:** APScheduler (AsyncIOScheduler)
- **Deploy:** Railway — `Procfile` ile `uvicorn main:app`
- **Hava durumu:** Open-Meteo API (kayıt gerektirmez)
- **Telegram:** Webhook tabanlı (`/webhook` POST endpoint)

## Dosya Yapısı

```
main.py              → FastAPI app, lifespan, tüm router'lar, CORS (CORS_ORIGINS env)
auth.py              → X-API-Key doğrulama (tüm /api/* rotaları korur; API_KEY boşsa devre dışı)
database.py          → SQLite bağlantı, get_db() context manager, konuşma geçmişi + temizlik
ai_router.py         → Groq NLP parsing, JSON dispatch, route_message(), _esc() HTML escape
telegram_bot.py      → /webhook (secret token doğrulama + BackgroundTasks), hızlı komutlar,
                       ses transkripsiyon, fotoğraf → vision analizi, callback
scheduler.py         → Her 1 dk hatırlatıcı kontrolü, 08:00 sabah özeti, 03:00 konuşma temizliği
requirements.txt
Procfile
.env.example

modules/
  chat/
    service.py  → Groq Whisper transkripsiyon + describe_image() vision analizi
                   (Telegram + REST ortak kullanır)
    routes.py   → POST /api/chat (metin), /api/chat/voice (ses), /api/chat/image (görsel)
  reminders/
    models.py   → CREATE TABLE reminders (id, title, due_datetime, priority,
                   is_completed, last_notified_at, snooze_count, recurrence, created_at)
    service.py  → CRUD + öncelik bazlı bildirim + snooze + tekrarlayan
                   (complete_reminder tekrarlayanı öldürmez, sonraki periyoda öteler)
    routes.py   → FastAPI router (/api/reminders/*, PUT update dahil)
  notes/
    models.py   → CREATE TABLE notes (id, title, content, category, created_at)
    service.py  → CRUD + update + search (kategori filtreli)
    routes.py
  expenses/
    models.py   → CREATE TABLE expenses + budgets (id, category, monthly_limit, created_at)
    service.py  → CRUD + aylık özet + bütçe limiti + uyarı sistemi
    routes.py   → router (/api/expenses/*) + budget_router (/api/budget/*)
  weather/
    service.py  → Open-Meteo API, WMO kod → Türkçe, format fonksiyonu
    routes.py
  summary/
    service.py  → Hava + görevler + harcama + notlar birleştirme
    routes.py

frontend/            → React 18 + Vite + Tailwind web panel (ayrı Railway servisi)
  src/api/client.js  → fetch sarmalayıcı, X-API-Key header (VITE_API_KEY)
  src/pages/         → Dashboard, Reminders, Notes, Expenses, Settings

mobileapp/           → Android Studio şablonu (Jetpack Compose, henüz kodlanmadı)
```

## Veritabanı Tabloları

```sql
reminders    (id, title, due_datetime, priority[1-3], is_completed, last_notified_at,
              snooze_count, recurrence[none|daily|weekly|monthly], created_at)

notes        (id, title, content, category[iş|kişisel|genel|ders|fikir], created_at)

expenses     (id, amount, category[yemek|ulaşım|eğlence|fatura|alışveriş|diğer],
              description, expense_date, created_at)

budgets      (id, category UNIQUE, monthly_limit, created_at)

conversations (id, chat_id, role[user|assistant], content, created_at)
              → INDEX: idx_conv_chat(chat_id)
```

## AI Routing Sistemi

`ai_router.py` — her Telegram mesajı şu pipeline'dan geçer:

1. `route_message(user_message, chat_id)` çağrılır
2. `get_recent_messages(chat_id, limit=10)` → SQLite'tan konuşma geçmişi alınır
3. `parse_message(user_message, history)` → Groq'a system prompt + geçmiş + mesaj gönderilir
4. Groq saf JSON döner: `{"module": "...", "action": "...", "params": {...}}`
5. `dispatch(parsed)` → ilgili `_handle_*` fonksiyonuna yönlendirir
6. Kullanıcı mesajı ve Groq'un JSON yanıtı `conversations` tablosuna kaydedilir

**Modüller ve aksiyonlar:**
```
reminders.create / list / update / complete / delete   (update recurrence destekler)
notes.create / read / list / search / update / delete
expenses.create / list / summary / delete              (create expense_date destekler — "dün")
budget.set / list / delete
weather.get
summary.get
chat.respond
```

**Görsel mesajlar:** Fotoğraf geldiğinde önce `describe_image()` (vision modeli) Türkçe analiz üretir;
analiz `[Görsel analizi]: ...` bloğu olarak kullanıcı mesajına eklenip normal pipeline'a girer.
Fiş/fatura ise router harcama kaydeder, soru sorulmuşsa chat modunda yanıtlar.

**Önemli:** `dispatch()` içindeki `chat` modülü Groq'tan gelen serbest metin yanıtını doğrudan döner.
Hiçbir kategoriye girmeyen mesajlar için PRISM sohbet moduna geçer.

## Telegram Bot Akışı

`telegram_bot.py` — `/webhook` önce `X-Telegram-Bot-Api-Secret-Token` header'ını doğrular
(`TELEGRAM_WEBHOOK_SECRET` boşsa atlanır), update'i `BackgroundTasks`'e atıp hemen 200 döner
(Telegram retry → çift işlem riski yok). `_handle_message()` sırası:

1. Güvenlik: sadece `TELEGRAM_CHAT_ID`'e eşit chat_id kabul edilir
2. Hızlı komutlar kontrol edilir (Groq bypass): `/start /hava /ozet /liste /hatirlaticilar /notlar /butce`
3. Ses mesajı varsa: `_transcribe_voice(file_id)` → Groq Whisper → metin
4. Fotoğraf varsa: en büyük boyut indirilir → `describe_image()` → `[Görsel analizi]: ...` metni
5. "⏳ İşleniyor..." mesajı gönderilir, mesaj ID'si alınır
6. `route_message(text, chat_id)` çağrılır
7. Sonuç `edit_message()` ile "⏳ İşleniyor..." üzerine yazılır

Kullanıcı içeriği Telegram HTML parse_mode'a `html.escape()` ile gider (ai_router `_esc()`).

Callback handler (`_handle_callback_query`): inline button data formatı:
- `complete_{id}` → hatırlatıcıyı tamamla
- `snooze_{minutes}_{id}` → ertele (15 dk veya 60 dk)

## Zamanlayıcı (scheduler.py)

- **Her 1 dakika:** `check_reminders()` → bildirim zamanı gelen hatırlatıcıları bulur, Telegram'a gönderir, `last_notified_at` günceller. Tekrarlayan hatırlatıcı vadesi geçtiyse `reschedule_recurring()` ile bir sonraki periyoda öteler.
- **Her gün 08:00 (Europe/Istanbul):** `send_morning_summary()` → hava + görevler + harcama + notlar özetini Telegram'a gönderir.
- **Her gece 03:00:** `cleanup_conversations()` → 30 günden eski konuşma kayıtlarını siler.

**Öncelik bazlı bildirim sıklığı** (`get_notification_interval()`):
- Kritik (1): son 1 saatte 15 dk'da bir, 1-3 saatte 30 dk'da bir...
- Önemli (2): son 30 dk'da 15 dk'da bir, 30-180 dk'da saatte bir...
- Normal (3): son 2 saatte saatte bir, 2-24 saatte 12 saatte bir

## Environment Variables

```
TELEGRAM_TOKEN           → Bot token
TELEGRAM_CHAT_ID         → Yetkili kullanıcı chat ID (güvenlik için zorunlu)
TELEGRAM_WEBHOOK_SECRET  → Webhook imza doğrulaması (boşsa devre dışı; Railway'de ayarla!)
GROQ_API_KEY             → Groq API key (LLM + Whisper + Vision)
GROQ_VISION_MODEL        → Görsel analiz modeli (varsayılan: meta-llama/llama-4-scout-17b-16e-instruct)
API_KEY                  → REST API anahtarı (X-API-Key header; boşsa auth devre dışı — sadece lokal)
WEBHOOK_URL              → Railway app URL (Telegram webhook için, örn: https://xxx.railway.app)
CORS_ORIGINS             → İzin verilen origin'ler, virgülle ayrılır (boşsa hepsi serbest)
WEATHER_CITY             → Elazığ  (varsayılan)
WEATHER_LAT              → 38.6748 (varsayılan)
WEATHER_LON              → 39.2225 (varsayılan)
DATABASE_PATH            → prism.db (varsayılan)
```
## Yeni Modül Eklemek

1. `modules/yenimodul/` dizini aç: `__init__.py`, `models.py`, `routes.py`, `service.py`
2. `models.py`'de tablo oluşturma fonksiyonu yaz
3. `database.py:init_db()`'ye import + çağrı ekle
4. `ai_router.py` system prompt'una aksiyonları ekle
5. `ai_router.py:dispatch()`'e `if module == "yenimodul":` bloğu ekle
6. `main.py`'ye `app.include_router(...)` ekle

## Geliştirme Notları

- `get_db()` bir context manager — `with get_db() as conn:` şeklinde kullan, commit/rollback otomatik
- Tüm datetime'lar `Europe/Istanbul` timezone'unda saklanır (`pytz.timezone("Europe/Istanbul")`)
- `parse_dt()` → ISO string'i timezone-aware datetime'a çevirir (reminders service'de)
- Groq'a gönderilen history: `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "<json>"}]` — assistant tarafı ham JSON string, formatlanmış metin değil
- Tekrarlayan hatırlatıcılarda `reschedule_recurring()` while döngüsüyle due_datetime'ı geçmişte kalmayacak şekilde ilerletir
- `check_budget_alert()` → None döndürürse limit yok veya %80 altı, string döndürürse uyarı mesajı

## Deploy

```
railway up   # ya da git push ile otomatik deploy
```

Railway başlangıçta `set_webhook()` çağrılır, Telegram webhook otomatik ayarlanır.
Lokal test için `WEBHOOK_URL` boş bırakılabilir — webhook kurulmaz, bot Telegram'dan mesaj almaz ama API endpoint'leri çalışır.
