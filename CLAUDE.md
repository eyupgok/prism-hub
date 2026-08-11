# PRISM — Kişisel AI Asistan Hub

Eyüp'ün kişisel asistan projesi. Telegram üzerinden doğal Türkçe dille kontrol edilir.
Oracle Cloud Always Free VM'de kendi kendine barındırılan, SQLite tabanlı, modüler FastAPI uygulaması.

## Stack

- **Backend:** Python 3.11 + FastAPI
- **AI:** Groq API — `llama-3.3-70b-versatile` (NLP parsing) + `whisper-large-v3` (ses transkripsiyon) + `qwen/qwen3.6-27b` (görsel analiz).
  Üçü de env'den değiştirilebilir (`GROQ_MODEL`, `GROQ_WHISPER_MODEL`, `GROQ_VISION_MODEL`) —
  Groq model emekliye ayırdığında (`model_not_found`) kod değil `.env` güncellenir.
- **DB:** SQLite (WAL mode) — `prism.db`
- **Zamanlayıcı:** APScheduler (AsyncIOScheduler)
- **Deploy:** Oracle Cloud VM (Ubuntu 24.04) — systemd servisi `prism.service` + Caddy ters vekil (HTTPS).
  `Procfile` duruyor ama kullanılmıyor (Railway kalıntısı).
- **Hava durumu:** Open-Meteo API (kayıt gerektirmez)
- **Telegram:** Webhook tabanlı (`/webhook` POST endpoint)

## Dosya Yapısı

```
main.py              → FastAPI app, lifespan, tüm router'lar, CORS (CORS_ORIGINS env),
                       /health (veritabanı + zamanlayıcı + hatırlatıcı döngüsü
                       kalp atışı; herhangi biri bozuksa 503 — dışarıdaki izleme
                       servisi bunu alarm sayıyor)
logging_setup.py     → Tek yerden loglama. `print()` KULLANMA — `get_logger(__name__)`.
                       httpx/apscheduler gürültüsü kısılmış. LOG_LEVEL env ile ayarlanır.
groq_client.py       → Groq çağrıları için ortak sarmalayıcı: JSON modu
                       (response_format) + ana model başarısızsa GROQ_FALLBACK_MODEL
backup.py            → SQLite backup API ile tutarlı kopya → gzip → Telegram'a dosya
confirm.py           → Onay bekleyen yıkıcı işlemler (AI ile silme). Bellekte, 5 dk ömürlü.
                       REST/panel silmeleri bu akıştan geçmez — orada kullanıcı zaten
                       hangi satıra bastığını görüyor.
auth.py              → İki yollu doğrulama: X-API-Key başlığı (Android) VEYA prism_session
                       çerezi (web paneli). Oturum bileti HMAC imzalı + son kullanma tarihli,
                       sunucuda saklanmaz. İmza anahtarı API_KEY'den türetilir — API_KEY
                       değişirse tüm oturumlar düşer. Parola denemesi 8'de bir 15 dk kilitlenir.
                       API_KEY boşsa doğrulama tamamen devre dışı (lokal geliştirme).
database.py          → SQLite bağlantı, get_db() context manager, konuşma geçmişi + temizlik
ai_router.py         → Groq NLP parsing, JSON dispatch, route_message(), _esc() HTML escape
telegram_bot.py      → /webhook (secret token doğrulama + BackgroundTasks), hızlı komutlar,
                       ses transkripsiyon, fotoğraf → vision analizi, callback
scheduler.py         → Her 1 dk hatırlatıcı kontrolü, 08:00 sabah özeti, 03:00 konuşma temizliği
requirements.txt
Procfile
.env.example

modules/
  auth/
    routes.py   → /api/auth/me, /login, /logout — KORUMASIZ eklenir (main.py),
                   giriş yapabilmek için giriş yapmış olmak gerekemez
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
    ingest.py   → Banka bildirimi → Groq → harcama kaydı + Telegram bildirimi
                   (ham metin DB'ye yazılmaz, sadece SHA-256 özeti; OTP metinleri elenir)
    routes.py   → router (/api/expenses/*, POST /ingest dahil) + budget_router (/api/budget/*)
  weather/
    service.py  → Open-Meteo API, WMO kod → Türkçe, format fonksiyonu
    routes.py
  summary/
    service.py  → Hava + görevler + harcama + notlar birleştirme
    routes.py

frontend/            → React 18 + Vite + Tailwind web panel (aynı domainin kökünde yayında)
  src/index.css      → TASARIM SİSTEMİ. Renkler `:root` altında CSS değişkeni; tema
                       değiştirmek için sadece burayı düzenle, bileşenlere dokunma.
                       Animasyonlar (fadeUp/fadeIn/scaleIn/pulseGlow/float), .glass,
                       .nav-item, .btn-primary, .input-field hep burada tanımlı.
                       Ortak yumuşatma eğrisi: var(--ease) = cubic-bezier(.16,1,.3,1)
                       ⚠️ `:root { color-scheme: dark }` SİLME. Tarayıcının kendi
                       çizdiği parçalar (açılır liste kutusu, tarih seçici) bunu
                       görmezse işletim sisteminin açık temasıyla çizilir —
                       beyaz zemine beyaz yazı çıkar, seçenekler okunmaz.
                       `select option` kuralları da aynı sorunun Windows yedeği.
  src/api/client.js  → fetch sarmalayıcı, X-API-Key header (VITE_API_KEY)
  src/pages/         → Dashboard, Reminders, Notes, Expenses, Settings, Login
                       Bütçenin ayrı sayfası YOK — Harcamalar sayfasındaki
                       "Bütçe" sekmesi (components/BudgetPanel.jsx). Limit koymak
                       harcamaya bakarken akla gelen bir iş, menüde ayrı durunca
                       kopuk kalıyordu.
  src/components/ErrorBoundary.jsx
                     → Render hatasında beyaz ekran yerine sebebi gösterir
                       (React'te hata sınırı yalnızca sınıf bileşeniyle yazılabiliyor)

mobileapp/           → Android uygulaması (Jetpack Compose, minSdk 26)
  data/SettingsStore.kt      → sunucu URL + API anahtarı + yakalama ayarları (DataStore)
  data/InstalledApps.kt      → kurulu uygulama listesi (banka olanlar başta sıralanır)
  data/PendingQueue.kt       → çevrimdışıyken biriken bildirimler (JSON dosya, filesDir)
  data/CaptureLog.kt         → son 40 bildirimin SONUCU (metin değil) — Ayarlar'da
                               "Son Yakalananlar" listesi; Logcat'siz teşhis için
  data/ListenerState.kt      → dinleyicinin canlılık kaydı: bağlı mı + EN SON ne zaman
                               herhangi bir bildirim gördü (SharedPreferences)
  data/api/                  → Retrofit client (X-API-Key interceptor), modeller
  service/ExpenseNotificationListener.kt
                             → banka bildirimlerini yakalar → /api/expenses/ingest
  service/CaptureSelfTest.kt → "Test bildirimi gönder" (uygulama kendine bildirim atar,
                               dinleyici görürse zincir sağlam) + requestListenerRebind()
  service/CaptureSyncWorker.kt
                             → WorkManager: internet gelince kuyruğu boşaltır
  ui/screens/                → Chat, Reminders, Notes, Expenses, Settings
                               (+ ExpenseCaptureSection: izin + uygulama seçici +
                                dinleyici durum kartı)
  MainActivity.kt            → alt gezinme + sekme yönetimi
```

## Veritabanı Tabloları

```sql
reminders    (id, title, due_datetime, priority[1-3], is_completed, last_notified_at,
              snooze_count, recurrence[none|daily|weekly|monthly], created_at)

notes        (id, title, content, category[iş|kişisel|genel|ders|fikir], created_at)

expenses     (id, amount ← NEGATİF = İADE, category[yemek|ulaşım|eğlence|fatura|alışveriş|diğer],
              description, expense_date, created_at,
              source[manual|notification|sms|receipt], source_hash, source_at)
              → UNIQUE INDEX idx_expenses_source_hash (source_hash) WHERE source_hash IS NOT NULL
              → source_at = bildirimin TELEFONA DÜŞTÜĞÜ an (kayıt anı değil). Çevrimdışı
                kuyruk yüzünden kayıt saatlerce sonra gelebiliyor; çift kayıt kontrolü
                buna bakmalı, created_at'e değil.
              → Bu sütunlar sonradan eklendi; models.py:_migrate_expenses() ALTER TABLE ile
                mevcut veritabanlarına ekler (idempotent, her init_db()'de güvenle çalışır)

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

**Çoklu komut:** Tek mesajda birden fazla iş varsa Groq `{"commands": [ {...}, {...} ]}`
döndürür; `dispatch()` diziyi görürse hepsini sırayla çalıştırıp yanıtları birleştirir
(en fazla `MAX_COMMANDS`=5). Tek iş varsa eski tekil biçim aynen çalışır.

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
- `expdel_{id}` → bildirimden kaydedilen harcamayı sil
- `expcat_{id}` → kategori seçim butonlarını göster
- `expset_{id}_{index}` → kategoriyi değiştir (index → `ingest.CATEGORY_ORDER`;
  callback data 64 bayt sınırlı olduğu için kategori adı değil sırası gönderilir)
- `dupadd_{token}` → çift sanılıp elenen kaydı yine de ekle (token bellekte, 1 saat ömürlü)
- `delok_{token}` / `delno_{token}` → AI ile istenen silmeyi onayla / vazgeç (`confirm.py`)

## Banka Bildiriminden Otomatik Harcama

Telefondaki `ExpenseNotificationListener` (Android `NotificationListenerService`) kullanıcının
seçtiği bankacılık uygulamalarının bildirimlerini yakalar → `POST /api/expenses/ingest` →
`modules/expenses/ingest.py` metni Groq'a okutur → harcamaysa kaydeder → Telegram'dan
`[🏷 Kategori] [🗑 Sil]` butonlarıyla haber verir.

**Gizlilik kararları (bilinçli, değiştirirken dikkat):**
- Ham bildirim metni **hiçbir yerde saklanmaz** — DB'ye sadece SHA-256 özeti yazılır
- OTP/şifre metinleri iki kez elenir: telefonda (`looksLikeSecret`, hiç gönderilmez) ve
  sunucuda (Groq'a bile gitmez). İki regex birbirinin aynası — birini değiştirirsen diğerini de değiştir
- Log'lara metin basılmaz, sadece paket adı ve sonuç
**İki katmanlı çift kayıt koruması:**
1. `source_hash = sha256(paket|metin|dakika)` — **aynı** bildirimin yeniden gönderimi
   (DB'de UNIQUE index)
2. `service.find_duplicate()` — **farklı** kaynaklardan gelen aynı alışveriş. Aynı tutar +
   zaman yakınlığı. İki kıyaslama seviyesi var:
   - **dakika**: iki kaydın da `source_at`'i varsa, fark ≤ `EXPENSE_DUPLICATE_WINDOW_MINUTES`
     (varsayılan 5). Bildirim/SMS yolu bunu kullanır (`day_level=False`).
   - **gün** (`day_level=True`): saat bilinmiyorsa aynı gün + aynı tutar yeterli.
     Fiş fotoğrafı yolu bunu kullanır, çünkü fişte saat okunamayabiliyor.

   `AUTO_SOURCES = (notification, sms, receipt)` — bu üçü birbiriyle karşılaştırılır.
   Aynı alışveriş hem banka bildiriminden, hem SMS'ten, hem de fiş fotoğrafından girilebiliyor;
   metinleri farklı olduğu için 1. katman bunları eşleştiremez.

Elle girilen (`source='manual'`) kayıtlara karışılmaz — kullanıcı bilerek aynı tutarı iki kez
girmiş olabilir.

**Fiş fotoğrafı yolu:** `ai_router` system prompt'u fiş görselinde `from_receipt: true` ve
mümkünse `expense_time` istiyor. `_check_receipt_duplicate()` kaydetmeden önce kontrol eder;
çift çıkarsa kaydetmez, Telegram'a `[➕ Yine de kaydet]` butonlu not düşer. Kaydedilirse
`source='receipt'` ve `source_at` (fişteki an) yazılır — sonraki kontroller bunu görür. Elenen kayıt sessizce yutulmaz: Telegram'a `[➕ Yine de kaydet]` butonlu bir
not düşer (token bellekte, 1 saat ömürlü). Aynı bildirim tekrar gelirse ikinci not gönderilmez
(`_suppressed_hashes`).

**Çevrimdışı kuyruk (telefon tarafı):** gönderim başarısızsa bildirim `data/PendingQueue.kt`
ile diske yazılır, `service/CaptureSyncWorker.kt` (WorkManager, `NetworkType.CONNECTED`
koşullu, üstel geri çekilme) internet gelince gönderir. Uygulama açılışında da denenir
(`MainActivity`). 7 günden eski kayıtlar atılır, kuyruk 300 kayıtla sınırlı. `postedAt`
kuyrukta korunduğu için harcama doğru tarihe yazılır. Kalıcı hatalarda (400/422) kayıt atılır,
geçici olanlarda (401/403/429/5xx) tekrar denenir.

**Harcama değilse** (bakiye, iade, kampanya, şifre) endpoint 200 + `recorded: false` döner —
telefon bunu hata saymaz, tekrar denemez.

### "Bildirim geldi ama hiçbir şey olmadı" — teşhis sırası

Ayarlar → Otomatik Harcama Yakalama'daki durum kartı sırayla şunu söyler:

1. **"Son gördüğü bildirim" boşsa** → sorun banka uygulamasında ya da paket seçiminde
   DEĞİL. Dinleyici hiçbir şey almıyor demektir, çünkü seçili olmayan uygulamaların
   bildirimleri de "dinlenmiyor" olarak kayda geçiyor. **Test bildirimi gönder** →
   görülmezse **Yeniden bağla** → olmazsa sistem ayarlarından bildirim erişimini kapat-aç.
2. **Dinleyici görüyor ama banka satırı yoksa** → uygulamanın paketi seçili değil.
   Uygulama seç listesinde ara (paket adı satırın altında yazıyor).
3. **Satır var ama "harcama değil" diyorsa** → metin sunucuya ulaştı, Groq harcama
   saymadı. Genelde bakiye/kampanya bildirimidir.

⚠️ **İzin verilmiş görünmesi servisin bağlı olduğu anlamına gelmiyor.** Android, uygulama
güncellendikten sonra dinleyiciyi geri bağlamayabiliyor; ayar ekranı yeşil kalırken hiçbir
bildirim gelmez. `requestListenerRebind()` bunun yazılımla yapılan karşılığı — açılışta
(`MainActivity`) ve bağlantı koptuğunda (`onListenerDisconnected`) kendiliğinden çağrılır.

Dinleyicinin sessizce elediği durumlar (kalıcı bildirim, grup başlığı, metin okunamadı)
artık **seçili uygulamalar için** kayda düşüyor — eskiden hiçbir iz bırakmadan atlanıyordu.
Metin çıkarımı da tek alana bakmıyor: `EXTRA_BIG_TEXT`, `EXTRA_TEXT`, `EXTRA_TEXT_LINES`
(InboxStyle), `EXTRA_SUMMARY_TEXT` ve `tickerText` toplanıp en uzunu seçiliyor.

## İadeler

**Negatif `amount` = iade.** Ayrı tablo/sütun yok; aylık toplam ve bütçe uyarısı zaten
`SUM(amount)` olduğu için iade kendiliğinden düşülür. `service.validate_amount()` sıfırı
ve `MAX_ABS_AMOUNT` üstünü reddeder (fişteki "1.234,56"nın 123456 okunmasını yakalamak için),
negatifi serbest bırakır. Panel ve Android iadeyi yeşil `+` ile gösterir.

Banka "iade edildi" bildirimi ve "200 TL iade aldım" cümlesi de eksi kaydedilir —
ingest ve ai_router prompt'larında açıkça yazılı.

Çift kayıt kontrolü iadeyi orijinal harcamayla eşleştirmez (+273.90 ile −273.90 arası fark
547.80, eşik 0.005).

## Zamanlayıcı (scheduler.py)

- **Her 1 dakika:** `check_reminders()` → önce `reschedule_overdue_recurring()` ile bildirim
  penceresinden düşmüş (60 dk'dan fazla gecikmiş) tekrarlayanları ileri sarar, sonra bildirim
  zamanı gelenleri Telegram'a gönderir ve `last_notified_at` günceller.
  ⚠️ Süpürme şart: `get_reminders_to_notify()` 60 dk'dan fazla gecikmişleri listeden çıkarıyor,
  öteleme de eskiden sadece o döngüde yapılıyordu — sunucu 1 saatten uzun kapalı kalırsa
  tekrarlayan hatırlatıcı sessizce ölüyordu.
- **Her gün 08:00 (Europe/Istanbul):** `send_morning_summary()` → hava + görevler + harcama + notlar özetini Telegram'a gönderir.
- **Her gece 03:00:** `cleanup_conversations()` → 30 günden eski konuşma kayıtlarını siler.
- **Her akşam 21:00:** `send_evening_summary()` → bugün tamamlanan görevler, kalanlar,
  günün harcaması (iade sayısı dahil), yarının görevleri. `/aksam` ile elle çağrılır.
- **Her pazar 20:00:** `send_weekly_report()` → tamamlanan görev sayısı, haftalık harcama,
  geçen haftayla kıyas, günlük dağılım (metin çubuğu), kategori kırılımı. `/hafta` ile elle çağrılır.
- **Her gece 04:00:** `nightly_backup()` → `backup.py` SQLite backup API ile tutarlı kopya alır,
  gzip'ler, Telegram'a dosya olarak gönderir. `/yedek` komutuyla elle de tetiklenir.
  Sunucu tamamen kaybolsa bile yedek Telegram sohbetinde durur.

## Testler

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/` — harcama doğrulaması ve iadeler, çift kayıt tespiti, hatırlatıcı öteleme/erteleme
mantığı, yedeğin geri yüklenebilirliği. Her test geçici veritabanı kullanır (`conftest.py`),
gerçek `prism.db`'ye dokunulmaz.

**Öncelik bazlı bildirim sıklığı** (`get_notification_interval()`):
- Kritik (1): son 1 saatte 15 dk'da bir, 1-3 saatte 30 dk'da bir...
- Önemli (2): son 30 dk'da 15 dk'da bir, 30-180 dk'da saatte bir...
- Normal (3): son 2 saatte saatte bir, 2-24 saatte 12 saatte bir

## Environment Variables

```
TELEGRAM_TOKEN           → Bot token
TELEGRAM_CHAT_ID         → Yetkili kullanıcı chat ID (güvenlik için zorunlu)
TELEGRAM_WEBHOOK_SECRET  → Webhook imza doğrulaması (boşsa devre dışı)
GROQ_API_KEY             → Groq API key (LLM + Whisper + Vision)
GROQ_MODEL               → Metin/komut modeli (varsayılan: llama-3.3-70b-versatile)
GROQ_FALLBACK_MODEL      → Ana model hata verirse düşülecek model (varsayılan: llama-3.1-8b-instant)
LOG_LEVEL                → DEBUG|INFO|WARNING|ERROR (varsayılan: INFO)
GROQ_WHISPER_MODEL       → Ses transkripsiyon modeli (varsayılan: whisper-large-v3)
GROQ_VISION_MODEL        → Görsel analiz modeli (varsayılan: qwen/qwen3.6-27b)
API_KEY                  → REST API anahtarı (X-API-Key header; boşsa auth devre dışı — sadece lokal)
PANEL_PASSWORD           → Web paneline giriş parolası (boşsa panele giriş yapılamaz)
EXPENSE_DUPLICATE_WINDOW_MINUTES → Aynı tutarlı ikinci bildirimin çift sayılacağı aralık (varsayılan 5)
WEBHOOK_URL              → Genel HTTPS adresi (Telegram webhook için: https://kendi-alan-adin.example.com)
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

Sunucu: Oracle Cloud Always Free VM (`<sunucu-ip>`, Ubuntu 24.04, Frankfurt).
Kod GitHub'dan **salt-okunur deploy key** ile iner — sunucuda geliştirme yapılmaz.

```bash
# 1) Yerelde geliştir, commit'le, push'la
git push

# 2) Sunucuda güncelle
ssh -i prism.key ubuntu@<sunucu-ip>
cd ~/prism && git pull
source venv/bin/activate && pip install -r requirements.txt   # bağımlılık değiştiyse
sudo systemctl restart prism
sudo journalctl -u prism -n 30 --no-pager                     # doğrula
```

**Mimari:** İnternet → Caddy (443, Let's Encrypt otomatik) → `127.0.0.1:8000` uvicorn (dışarıya kapalı).
Systemd `Restart=always` ile çöktüğünde ve yeniden başlatmada otomatik ayağa kalkar.

**Sunucudaki yollar:** kod `/home/ubuntu/prism`, venv `/home/ubuntu/prism/venv`,
gizli ayarlar `/home/ubuntu/prism/.env` (chmod 600, repoda yok), DB `/home/ubuntu/prism/prism.db`,
servis `/etc/systemd/system/prism.service`, vekil `/etc/caddy/Caddyfile`.

**Güvenlik duvarı iki katmanlı:** OCI Security List **ve** sunucunun `iptables`'ı — port açarken
ikisinde de açman gerekir (`iptables` değişikliği sonrası `sudo netfilter-persistent save`).

### Dışarıdan izleme (uptime)

`https://kendi-alan-adin.example.com/health` ücretsiz bir izleme servisi (UptimeRobot vb.)
tarafından 5 dakikada bir yoklanır. Kimlik doğrulaması yok — çıktısı sır içermiyor.

Endpoint üç şeye bakar ve **herhangi biri bozuksa 200 yerine 503** döner:

| Kontrol | Ne yakalar |
|---|---|
| `database` | SQLite okunamıyor (disk doldu, dosya bozuldu, kilit) |
| `scheduler` | APScheduler durmuş |
| `reminder_loop` | Zamanlayıcı ayakta ama dakikalık iş tur atmıyor |

Üçüncüsü asıl önemli olan: `scheduler.running` yalnızca "başlatıldı" demek. İş her
turda çöküyorsa ya da bir yerde takıldıysa bayrak yeşil kalır, hatırlatıcılar
sessizce gelmez. `scheduler.check_reminders()` her turun **sonunda**
`last_reminder_check` damgasını günceller; 5 dakika (`REMINDER_HEARTBEAT_TIMEOUT_SECONDS`)
haber çıkmazsa takılmış sayılır.

⚠️ İzleme servisini kurarken **"200 dışındaki kodda alarm ver"** ayarını seç. Sadece
"site açılıyor mu" bakan bir kontrol 503'ü de başarı sayabilir — o zaman bu iş boşa gider.

### Web paneli (aynı domain, kökte)

Caddy tek site bloğunda yolları ayırır:

| Yol | Koruma | Nereye |
|---|---|---|
| `/webhook*` | Telegram imzası | backend |
| `/api/auth/*` | yok (giriş uçları) | backend |
| `/api/*` | `X-API-Key` **veya** `prism_session` çerezi | backend |
| `/health` | yok | backend |
| diğer her şey | yok — panel kabuğu sır içermez | `/var/www/prism-panel/dist` statik dosyalar |

Panel gizli anahtar **taşımaz**: `frontend/.env`'de `VITE_API_URL` boş (istekler göreli yoldan
aynı sunucuya gider), `VITE_API_KEY` diye bir değişken yok. Kullanıcı `PANEL_PASSWORD` ile giriş
yapar, HttpOnly çerez alır. Derleme sonrası `dist/` içinde `X-API-Key` geçmemeli — kontrol et.

Panel güncelleme: PC'de `npm run build` → `scp -r frontend\dist ...:/var/www/prism-panel/` →
sunucuda **`chmod -R a+rX /var/www/prism-panel`** (scp Windows'tan kısıtlı izinle geldiği için şart).

Lokal geliştirme: `npm run dev` — `vite.config.js` içindeki proxy `/api` ve `/health`
isteklerini `127.0.0.1:8000`'e yönlendirir, böylece `VITE_API_URL` boşken de çalışır.

⚠️ **Tailwind dinamik sınıf adlarını göremez.** `` className={`stagger-${i}`} `` yazarsan
o kurallar derlemede silinir; sabit liste kullan (`STAGGER[i]` — Sidebar/Dashboard'da örneği var).

Uygulama açılışta `set_webhook()` çağırır, Telegram webhook otomatik ayarlanır.
Lokal test için `WEBHOOK_URL` boş bırakılabilir — webhook kurulmaz, bot Telegram'dan mesaj almaz ama API endpoint'leri çalışır.
