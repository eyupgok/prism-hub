# PRISM — Kişisel AI Asistan Hub

Eyüp'ün kişisel asistan projesi. Telegram üzerinden doğal Türkçe dille kontrol edilir.
Oracle Cloud Always Free VM'de kendi kendine barındırılan, SQLite tabanlı, modüler FastAPI uygulaması.

**İki kişilik.** Her kaydın bir sahibi var (`owner_id`); ikisi de birbirinin verisini
görebiliyor ama yalnız kendi kaydını değiştirebiliyor. Ayrıntısı → "İki Kullanıcı" bölümü.

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
                       + **token bütçesi yedeği** → "Akıl yürüten modeller" bölümü
ses.py               → Metin → ses (ElevenLabs). Telegram ses notu + panelin
                       "Dinle" düğmesi ortak kullanır → "Sesli Cevap".
                       Sözleşmesi: ASLA hata fırlatmaz, üretemezse None
backup.py            → SQLite backup API ile tutarlı kopya → gzip → Telegram'a dosya
confirm.py           → Onay bekleyen yıkıcı işlemler (AI ile silme). Bellekte, 5 dk ömürlü.
                       REST/panel silmeleri bu akıştan geçmez — orada kullanıcı zaten
                       hangi satıra bastığını görüyor.
auth.py              → İki yollu doğrulama: X-API-Key başlığı (Android) VEYA prism_session
                       çerezi (web paneli). `verify_api_key` artık sadece kapı değil,
                       KİMLİK de döner (dict) — rotalar `user: dict = Depends(...)` yazıyor.
                       Oturum bileti `<kullanıcı>.<son_kullanma>.<imza>`, HMAC imzalı,
                       sunucuda saklanmaz; imza anahtarı SESSION_SECRET (yoksa API_KEY).
                       Parolalar scrypt karması olarak users tablosunda (env'de düz metin
                       DEĞİL — veritabanı her gece Telegram'a yedekleniyor).
                       Parola denemesi 8'de bir 15 dk kilitlenir (sayaç GLOBAL — giriş
                       ekranında isim sorulmadığı için kişiye bağlanamıyor).
                       API_KEY boşsa doğrulama devre dışı, 1. kullanıcı varsayılır (lokal).
yetki.py             → Yetki kuralları: `bakilan_sahip()` (GET'te kimin verisi) +
                       `yazma_izni()` (yazmadan önce sahiplik; yoksa 404, başkasınınsa 403)
kullanici.py         → Komut satırı aracı: kullanıcı ekle / parola değiştir / chat-id ata.
                       Parola ve chat_id koda ya da .env'e yazılmasın diye ayrı komut.
tanitim.py           → Telegram'dan arka arkaya mesaj yollayıp paneli açmaya çağırır
                       (özel sayfa için). Metinler dosyanın başındaki
                       MESAJLAR listesinde; {panel} panel adresine, {parola}
                       alıcının panel parolasına dönüşür. `--liste` hiçbir şey
                       göndermeden önizler, `--kime "<ad>"` gönderir ve önce
                       onay sorar.
                       ⚠️ **Parola dosyada DEĞİL** — çalışırken alınıyor
                       (`--parola`, `TANITIM_PAROLA`, ya da ekrana yazılmayan
                       soru). Dosyaya yazılsaydı git geçmişine ve GitHub'a
                       girer, bir daha silinemezdi. Karma scrypt olduğu için
                       veritabanından okunamaz: bilinmiyorsa önce
                       `kullanici.py parola` ile yenisi konur.
                       ⚠️ Gönderilen mesaj geri alınamaz — sıra: --liste, kendine
                       prova, sonra gerçeği.
gozlem.py            → Gözlem katmanının denetim aracı: asistanın hafızası
                       (`bilgi` / `ekle` / `unut` / `cikar`), sonradan
                       soracakları (`takip` / `takip-cikar` / `takip-unut`),
                       kendiliğinden konuşma kararları (`sinyal` / `tur` /
                       `gunluk`) ve kişi başına günlük mesaj sınırı (`seviye`).
                       `tur` varsayılan olarak GÖNDERMEZ — `--gercek` gerekir.
                       Panelde karşılığı YOK, bilerek → "Gözlem Katmanı".
gecmis.py            → Konuşma geçmişini okur (--kisi / --son / --ara / --ham).
                       Asistan satırındaki ham JSON'u "modül.aksiyon (parametreler)"
                       diye özetler; chat yanıtlarında metnin kendisini basar.
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
    models.py   → CREATE TABLE users + ilk kurulum göçü (env'deki PANEL_PASSWORD ve
                   TELEGRAM_CHAT_ID'den 1 numaralı kullanıcıyı yaratır) +
                   sahiplik_sutunu_ekle() — her modülün models.py'si bunu çağırıp
                   kendi tablosuna owner_id ekliyor
    routes.py   → /api/auth/me, /login, /logout — KORUMASIZ eklenir (main.py),
                   giriş yapabilmek için giriş yapmış olmak gerekemez.
                   /api/auth/konum ise KORUMALI (kendi Depends'i var): panelin
                   tarayıcıdan aldığı konumu kişiye yazar
  chat/
    service.py  → Groq Whisper transkripsiyon + describe_image() vision analizi
                   (Telegram + REST ortak kullanır)
    routes.py   → POST /api/chat (metin), /api/chat/voice (ses → metin),
                   /api/chat/image (görsel), /api/chat/ses (metin → ses, MP3),
                   GET /api/chat/gecmis (panelin okunur sohbet geçmişi)
  reminders/
    models.py   → CREATE TABLE reminders (id, title, due_datetime, priority,
                   is_completed, last_notified_at, snooze_count, recurrence, created_at)
    service.py  → CRUD + snooze + tekrarlayan
                   (complete_reminder tekrarlayanı öldürmez, sonraki periyoda öteler)
                   NOTIFICATION_POINTS = önceliğe göre sabit bildirim anları
                   → "Hatırlatıcı Bildirim Planı" bölümü
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
  gozlem/       → ASİSTANIN İKİNCİ DÖNGÜSÜ (ayrıntı → "Gözlem Katmanı")
    models.py   → hafiza + takipler + gozlem_gunlugu + gozlem_durum tabloları
                   + users.gozlem_sinir göçü (DEFAULT 0 = herkes kapalı)
    sinyaller.py→ Deterministik sinyal üretimi (SQL + aritmetik). Modelin
                   uydurabileceği hiçbir şey yok; eşikler dosyanın başında.
    konusma.py  → Konuşma dökümü okuma — hafıza ve takip çıkarımlarının
                   ortak zemini (kanal çözümü + damga + asistan JSON'u ayıklama).
                   ⚠️ Her satır `[gg.aa ss:dd]` ile başlar; damgayı KALDIRMA
                   → "Gözlem Katmanı / Takip"
    hafiza.py   → Konuşmalardan KALICI bilgi çıkarımı + yönergeye enjeksiyon
    takip.py    → Konuşmalardan SONRADAN SORULACAK olay çıkarımı
                   ("yarın dişçiye gidiyorum" → ertesi akşam "nasıl geçti?")
    service.py  → Gözlem turu: sinyal topla → susma bütçesi → modele sor →
                   gönder → kararı (SUSTUĞU turlar dahil) günlüğe yaz
  iletiler/     → BİR KULLANICIDAN DİĞERİNE SÖZ (ayrıntı → "İletiler")
    models.py   → iletiler tablosu. owner_id YOK: gonderen_id + alici_id,
                   ikisi de gerçek taraf
    service.py  → olustur / bekleyenler / vakti_gelenler / iptal.
                   Engelleri `IletiHatasi` ile bildiriyor, metni doğrudan
                   kullanıcıya gidiyor
  ozel/
    routes.py   → GET /api/ozel/özel sayfa — `ozel-sayfa/index.html`'i servis eder.
                   Statik `dist/`e KONMADI bilerek: orayı Caddy korumasız
                   yayınlıyor, sayfada kişiye özel içerik var.
                   Buradan geçince /api korumasının altına giriyor.

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
  src/api/client.js  → fetch sarmalayıcı (oturum çerezi ile). `setBakilanKisi(id)`
                       ile seçilen kişi YALNIZCA GET'lere `?kisi=` olarak eklenir —
                       yazma her zaman giriş yapanın kendi verisine gider.
  src/kullanici.jsx  → Bağlam: `kullanici` (giriş yapan) vs `bakilan` (kime bakılıyor).
                       İkisi farklıysa `saltOkunur` true → arayüz bütün ekle/düzenle/sil
                       düğmelerini gizler (sunucu zaten 403 döner, bu sadece nezaket)
  src/pages/         → Dashboard, Reminders, Notes, Expenses, Sohbet, Settings, Login
                       Bütçenin ayrı sayfası YOK — Harcamalar sayfasındaki
                       "Bütçe" sekmesi (components/BudgetPanel.jsx). Limit koymak
                       harcamaya bakarken akla gelen bir iş, menüde ayrı durunca
                       kopuk kalıyordu.
                       Sohbet.jsx → panelden AI sohbeti (metin + görsel + ses).
                       iPhone'da Telegram dışında da asistana ulaşılabilsin diye
                       eklendi. Geçmiş sunucudan geliyor → "Panel Sohbeti".
  src/sesKaydi.js    → Tarayıcıdan sesli mesaj kaydı (MediaRecorder).
                       Biçim seçimi + mikrofonu bırakma burada → "Panel Sohbeti".
  src/components/SesAyari.jsx
                     → Ayarlar'daki ses bölümü: ses seçimi, sakinlik/hız
                       kaydırıcıları, Önizle, kalan kota
  src/components/KisiSeridi.jsx
                     → Üstteki kişi geçişi + salt görüntüleme işareti (göz simgesi).
                       Tek kullanıcı varsa hiç çizilmez.
  src/components/OzelKarti.jsx
                     → Dashboard'da selamlamanın altındaki tanıtım kartı →
                       `onNavigate('özel sayfa')`. Rengi panelin morundan değil
                       vurgu tonundan (#F14A6E): diğer kartlara
                       benzerse gözden kaçıyordu.
  src/pages/OzelSayfa.jsx
                     → Tam ekran özel sayfa (`/api/ozel/özel sayfa` çerçeve içinde).
                       `App.jsx`'te kabuğun DIŞINDA çiziliyor — kenar çubuğu
                       ve alt gezinme arasına sıkışırsa etkisi kalmıyor.
                       Yeni sekmede AÇILMIYOR: iPhone'da ana ekrana eklenmiş
                       panel yeni sekmeyi Safari'de açıyor, oturum çerezi
                       orada olmayabiliyor → "giriş yap" ekranına düşerdi.
  src/components/ErrorBoundary.jsx
                     → Render hatasında beyaz ekran yerine sebebi gösterir
                       (React'te hata sınırı yalnızca sınıf bileşeniyle yazılabiliyor)
  public/manifest.webmanifest + icon-*.png
                     → Ana ekrana eklenince uygulama gibi açılır (PWA).
                       **İKİSİNİN DE asıl uygulaması bu** — Android tarafındaki
                       ekranlar buraya devredildi (bkz. "Android: sensör
                       uygulaması"). Chrome, manifest + iki boyutta simge +
                       HTTPS'i görünce kurmayı teklif ediyor ve arka planda
                       küçük bir APK üretip kuruyor (WebAPK); iOS'ta teklif
                       çıkmaz, Paylaş → Ana Ekrana Ekle gerekir (`apple-*`
                       meta etiketleri onun karşılığı).
                       Service worker YOK: çevrimdışı açılmaz, bildirim
                       gönderemez. Hatırlatıcılar bu yüzden Telegram'dan.
                       index.html'de `viewport-fit=cover` ŞART — alt gezinmedeki
                       env(safe-area-inset-bottom) ancak onunla çalışıyor.

ozel-sayfa/         → Korumalı, kişiye özel içerik sayfası.
                       `kaynak.html` + `fontlar/` → `yap.py` → `index.html`
                       (tek dosya, fontlar base64 gömülü, dışarıdan hiçbir şey
                       çekmiyor). Metinleri kaynak.html'deki CONFIG'ten değiştir,
                       sonra `python yap.py` çalıştır — index.html'i ELLE düzenleme.
                       Ayrıntı: `ozel-sayfa/BENIOKU.md`.
                       ⚠️ Dikey ekran için tasarlandı. `.stage`'in min-height'ı
                       540px; ekran ondan kısalınca (telefon yan çevrilince ~390px)
                       altyazılar ve kapanış imzası görünmez oluyordu. Artık
                       "Telefonu dik tut" uyarısı çıkıp önüne geçiyor —
                       eşik (539px) min-height ile aynı sayıya bağlı, birini
                       değiştirirsen diğerini de değiştir.
                       ⚠️ iOS'ta yan taraftaki SESSİZ DÜĞMESİ açıksa müzik hiç
                       çalmaz (Web Audio o anahtara bağlı) — ses tuşuyla ilgisi yok.

mobileapp/           → "PRISM Köprü" — SENSÖR uygulaması (Compose, minSdk 26).
                       Tek işi banka bildirimlerini yakalayıp sunucuya iletmek.
                       Gündelik kullanımda AÇILMAZ → "Android: sensör uygulaması"
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
  service/ListenerWatchdogWorker.kt
                             → WorkManager: yarım saatte bir dinleyici bağlı mı diye
                               bakar, değilse requestRebind(). Süreç öldürüldüğünde
                               onu geri doğuran mekanizma bu
  ui/screens/SettingsScreen.kt
                             → uygulamanın TEK ekranı: sunucu adresi + anahtar,
                               yakalama bölümü, "Hakkında"
  ui/screens/ExpenseCaptureSection.kt
                             → izin + uygulama seçici + dinleyici durum kartı.
                               Uygulamanın asıl yüzü burası
  MainActivity.kt            → tek ekran; açılışta kuyruk gönderimi, dinleyici
                               yeniden bağlama ve bekçi kurulumu
```

### Android: sensör uygulaması

Uygulamanın Chat / Reminders / Notes / Expenses ekranları **silindi** (1.497
satır, kodun %42'si). Sebebi basit: web paneli hepsini daha iyi yapıyor ve
telefonda ana ekrana eklenince zaten uygulama gibi açılıyor (PWA).

Peki uygulama neden hâlâ duruyor? **Bildirim okumak web'de mümkün değil.**
`NotificationListenerService` bir Android sistem yetkisi; yalnız kurulu bir
uygulamaya verilebiliyor ve kullanıcının Ayarlar'dan tek tek onaylaması
gerekiyor. Tarayıcı bildirim *gösterebiliyor* ama başkasının bildirimini
*okuyamıyor* — ikisi ayrı şey. Otomatik harcama yakalama bu yüzden yerli
koda mahkûm.

Sonuçta iş bölümü şöyle:

| | Web paneli (PWA) | PRISM Köprü (Android) |
|---|---|---|
| Ne yapar | bakılan, yazılan her şey | banka bildirimlerini iletir |
| Ne sıklıkla açılır | sürekli | kurulumdan sonra hiç |
| Kimde var | ikisinde de | yalnız Eyüp'te (iOS'ta karşılığı yok) |

⚠️ **Uygulamanın adı `PRISM Köprü`** (`strings.xml`). Panel de ana ekranda
"PRISM" diye duruyor; ikisi aynı adı taşıyınca hangisinin ne olduğu
karışıyordu. Bu ad bildirim erişimi ayarları listesinde de görünüyor.

⚠️ `data/api/` yalnız **iki uç** tanıyor: `health` (bağlantı testi) ve
`expenses/ingest`. Hatırlatıcı/not/harcama uçları ve modelleri kaldırıldı.
Uygulamaya yeni bir özellik eklemek isteyince önce şunu sor: **bu iş panelde
yapılamaz mı?** Yapılabiliyorsa oraya gitmeli — bu uygulamanın büyümemesi
bilinçli bir karar.

⚠️ `IngestResult.expense` **silinemez**: yakalama kaydındaki "273.90 ₺ · yemek"
satırını o besliyor. Sunucu tam kaydı döndürüyor, uygulama `CapturedExpense`
ile yalnız iki alanını okuyor (Gson bilmediği alanları atlıyor).

## Veritabanı Tabloları

```sql
users        (id, ad, hitap, telegram_chat_id UNIQUE, parola_hash, created_at,
              sehir, enlem, boylam, konum_at, gozlem_sinir,
              ses_id, ses_sakinlik, ses_hiz)
              → ses_* = kişiye özel seslendirme tercihi, üçü de NULL olabilir
                (varsayılana düşer). Panelde Ayarlar → Asistanın Sesi.
                Göç: _migrate_ses(), idempotent ALTER TABLE
              → gozlem_sinir = günde en fazla kaç KENDİLİĞİNDEN mesaj.
                **DEFAULT 0 (kapalı)** — kendiliğinden konuşma, asistanın
                istenmemiş bir mesaj gönderebildiği tek mekanizma; açılması
                ayrı bir komuta bağlı: `gozlem.py seviye "<ad>" 3`
              → hitap = "Bey" / "Hanım", NULL olabilir. Asistanın seslenme
                biçimi; addan ÇIKARILMAZ (bkz. "Asistanın Üslubu").
                Göç: _migrate_hitap(), idempotent ALTER TABLE
              → parola_hash = `scrypt$<tuz>$<karma>` (auth.py). Düz metin YOK.
              → telegram_chat_id boşsa o kişi Telegram'dan yazamaz; bildirimleri de
                gidecek yer bulamayıp TELEGRAM_CHAT_ID'e (Eyüp) düşer
              → sehir/enlem/boylam NULL olabilir → env'deki WEATHER_* kullanılır
              → Göç: tablo boşken PANEL_PASSWORD + TELEGRAM_CHAT_ID'den id=1 yaratılır

reminders    (owner_id, id, title, due_datetime, priority[1-4], is_completed,
              last_notified_at, snooze_count, recurrence[none|daily|weekly|monthly], created_at)
              → priority: 1=Kritik 2=Önemli 3=Normal 4=Sessiz (varsayılan).
                Kaç bildirim gideceğini belirler → "Hatırlatıcı Bildirim Planı"
              → last_notified_at hangi bildirim noktasının duyurulduğunu da taşır;
                sıfırlanmaz, ŞU AN'a çekilir (erteleme/tarih düzenlemesi)

notes        (owner_id, id, title, content, category[iş|kişisel|genel|ders|fikir], created_at)

expenses     (owner_id, id, amount ← NEGATİF = İADE, category[yemek|ulaşım|eğlence|fatura|alışveriş|diğer],
              description, expense_date, created_at,
              source[manual|notification|sms|receipt], source_hash, source_at)
              → UNIQUE INDEX idx_expenses_source_hash (source_hash) WHERE source_hash IS NOT NULL
              → source_at = bildirimin TELEFONA DÜŞTÜĞÜ an (kayıt anı değil). Çevrimdışı
                kuyruk yüzünden kayıt saatlerce sonra gelebiliyor; çift kayıt kontrolü
                buna bakmalı, created_at'e değil.
              → Bu sütunlar sonradan eklendi; models.py:_migrate_expenses() ALTER TABLE ile
                mevcut veritabanlarına ekler (idempotent, her init_db()'de güvenle çalışır)

budgets      (owner_id, id, category, monthly_limit, created_at)
              → UNIQUE artık (owner_id, category) — ikisi de "yemek" limiti koyabilsin

hafiza       (owner_id, id, icerik, tur[alışkanlık|tercih|durum|ilişki|olgu],
              kaynak[konuşma|elle], gecerlilik, created_at, son_teyit_at)
              → Asistanın kişi hakkında biriktirdiği KALICI bilgiler. Veritabanında
                zaten olan şeyler (randevu, harcama) buraya YAZILMAZ — gün geçince
                yalan olurlar. Geçici olanlar `gecerlilik` tarihiyle girer.
              → UNIQUE(owner_id, icerik). Panelde görünmez; `gozlem.py bilgi`.

takipler     (owner_id, id, konu, soru, sorulacak_at, soruldu_at, created_at)
              → Kullanıcının ağzından çıkan, sonradan sorulmaya değer olaylar.
                Hatırlatıcı değil (kullanıcı kurmadı), not değil, hafıza da
                değil (tek seferlik). `sorulacak_at`'ten önce sorulmaz, bir kez
                sorulur, `TAKIP_BAYATLAMA_GUNU` (3) geçerse düşer.
              → UNIQUE(owner_id, konu). Kişi başına en fazla AZAMI_ACIK_TAKIP (5).

gozlem_gunlugu (owner_id, id, karar[konustu|sustu], anahtar, mesaj, sebep,
              sinyaller, created_at)
              → Her gözlem turunun kararı. SUSTUĞU turlar da yazılır — eşikleri
                ayarlamanın tek yolu o satırlar (`gozlem.py gunluk`).

gozlem_durum (owner_id, son_hafiza_conv_id, son_takip_conv_id)
              → Çıkarımlar `conversations` tablosunda nereye kadar geldi.
                İki damga ayrı: biri hata verdiğinde diğerinin de o
                konuşmaları atlaması gerekmiyor.

iletiler     (id, gonderen_id, alici_id, mesaj, iletilecek_at, iletildi_at, created_at)
              → "Zeynep'e akşam yedide şunu söyle" → o saatte alıcının
                Telegram'ına düşen mesaj. Hatırlatıcı DEĞİL (alıcı bunu
                görev olarak görmemeli, tamamlayamamalı, sabah özetinde
                çıkmamalı), not değil, takip değil.
              → ⚠️ `owner_id` YOK, bilerek: iki taraf da gerçek.
                `gonderen_id` iptal hakkı kimde, `alici_id` mesaj kime.
              → INDEX: idx_ileti_bekleyen(iletilecek_at) WHERE iletildi_at IS NULL

conversations (id, chat_id, role[user|assistant], content, gorunen, created_at)
              → INDEX: idx_conv_chat(chat_id)
              → owner_id YOK, bilerek: bu tablo sadece Groq'a bağlam vermek için
                okunuyor ve zaten chat_id'ye göre süzülüyor. Telegram'da chat_id
                kişiye özel, panelde `panel:<kullanıcı id>` — bağlamlar en baştan ayrı.
              → **content = MODELİN gördüğü, gorunen = İNSANIN gördüğü.**
                Asistan satırında content ham JSON komut (model bir sonraki turda
                kendi çıktı biçimini görmeli), gorunen ise cevabın kendisi.
                NULL = ikisi aynı (düz yazılan kullanıcı mesajı).
                Göç: _migrate_gorunen(), idempotent ALTER TABLE → "Panel Sohbeti"
```

**owner_id sütunları sonradan eklendi.** `modules/auth/models.py:sahiplik_sutunu_ekle()`
her tabloya `NOT NULL DEFAULT 1` ile ekler; yani tek kişilik dönemden kalan her kayıt
Eyüp'e (id=1) geçer. `REFERENCES users(id)` bilerek yazılmadı — SQLite, yabancı anahtar
açıkken ALTER TABLE ile eklenen REFERENCES'lı sütunun varsayılanının NULL olmasını şart
koşuyor, bize ise DEFAULT 1 lazımdı. Bütünlüğü uygulama katmanı koruyor: `owner_id`
her zaman giriş yapmış kullanıcıdan gelir, istekten alınmaz.

## İki Kullanıcı

Tek kural, her yerde aynı: **okuma serbest, yazma yalnız kendi kaydına.**
İkisi de birbirinin hatırlatıcısını/notunu/harcamasını görebiliyor; değiştirme ve
silme her zaman giriş yapanın kendi kayıtlarıyla sınırlı (`yetki.py`).

**Kimlik nereden geliyor:**

| Yol | Kim olduğunu ne söylüyor |
|---|---|
| Web paneli | `prism_session` çerezindeki kullanıcı numarası (imzalı) |
| Telegram | `users.telegram_chat_id` → mesajın geldiği sohbet |
| Android (`X-API-Key`) | tek env değeri, **her zaman 1 numaralı kullanıcı** |

⚠️ `X-API-Key` kullanıcı başına DEĞİL. Android'i yalnız Eyüp kullanıyor (karşı taraf
iPhone'da, mobil uygulama yok). İkinci bir Android kullanıcısı olursa anahtarların
`users` tablosuna taşınması gerekir — yoksa banka bildiriminden gelen harcamalar
yanlış kişiye yazılır.

**Panelde kişi geçişi:** üstteki şerit (`KisiSeridi.jsx`) kime bakıldığını değiştirir;
seçim `?kisi=<id>` olarak **yalnız GET** isteklerine eklenir. Karşı taraftayken arayüz
yazma düğmelerini gizler, sunucu da yazmayı 403 ile reddeder. Sayfaya `key={bakilan.id}`
veriliyor — geçiş yapılınca bileşen baştan kurulup veriyi yeniden çeksin diye.

**Giriş ekranında kullanıcı adı sorulmuyor:** parolanın kendisi kimin girdiğini söylüyor.
Bunun bedeli, hatalı deneme kilidinin global olması — biri 8 kez yanlış girerse diğeri de
15 dakika giremez. Üçüncü kişi eklenirse giriş ekranına isim alanı koymak gerekir.

**Bildirimler sahibine gider:** hatırlatıcı, harcama haberi, sabah/akşam/hafta özeti —
hepsi `telegram_bot.sahibin_chati(owner_id)` ile kaydın sahibinin sohbetine. chat_id'si
olmayan kişi için `send_message` `TELEGRAM_CHAT_ID`'e düşer, yani haber kaybolmaz.
Özetler kişi başına ayrı üretilir (`scheduler._herkese_ozet`) ve hata tek kişiyle sınırlı
kalır — birinin bozuk verisi diğerinin sabah özetini düşürmez.

**Hava durumu kişiye özel:** panel girişte tarayıcıdan konum alıp `/api/auth/konum`'a
yazar. Şehir adı yalnız kişi gerçekten yer değiştirmişse (>15 km) Nominatim'e sorulur;
çözülemezse eski ad kalır — hava durumu koordinatla çalıştığı için ada bağlı değil.
Konum hiç verilmemişse env'deki `WEATHER_*` (Elazığ) kullanılır.

**Yeni kullanıcı eklemek** → `kullanici.py` (Deploy bölümünde adımları var).

## Asistanın Üslubu

**JARVIS kaydında konuşuyor** (Iron Man): kusursuz nezaket, sakin yetkinlik,
arada kuru bir espri. Kural `ai_router.SYSTEM_PROMPT` → "KİMLİĞİN VE ÜSLUBUN".

- **Daima SİZ.** "dener misin" değil "dener misiniz". İstisnasız.
- Kısa ve kesin: "Kaydedildi." · "Üç göreviniz var." Abartılı heyecan ve ünlem yok.
- Espri kuru ve kısa, asla kaba değil.

⚠️ **Üslup iki yerden birden geliyor** — biri değişip diğeri kalırsa ton ortadan
ikiye bölünür:

| Kaynak | Nerede |
|---|---|
| Modelin ürettiği sohbet | `SYSTEM_PROMPT` (yalnız `chat.respond` metinleri) |
| **Sabit onay/özet metinleri** | `ai_router.dispatch()`, `telegram_bot.py`, `modules/summary/service.py` |
| Kendiliğinden gelen mesajlar | `modules/gozlem/service.py` → `YONERGE` |

İkincisi kullanıcının gördüğünün çoğu ve modelden GEÇMİYOR. Yeni bir yanıt
metni eklerken "sen" kipine kaymamak gerekiyor; `tests/test_uslup.py` bilinen
samimi kalıpları kelime sınırıyla arayıp yakalıyor.

**Olağan sesleniş "efendim"** — kişiden ve cinsiyetten bağımsız, JARVIS'in
"sir"inin karşılığı (`ai_router.OLAGAN_HITAP`). Asistanın ağzından çıkan
seslenişlerin neredeyse tamamı bu.

**Adıyla seslenmek istisna:** `users.hitap` ("Bey" / "Hanım") →
`ai_router.adiyla_hitap()` → "Eyüp Bey". Yönergeye `{adiyla}` yer tutucusuyla
giriyor ve orada **"istisnadır, vurgu gerektiğinde"** diye işaretli. Her
mesajda adı anmak yapmacık duruyor — JARVIS de "Mr. Stark" demiyor, "sir"
diyor.

⚠️ **Hitap ADDAN ÇIKARILMIYOR.** İsme bakıp cinsiyet tahmin etmek yanlış sonuç
verebilen bir iş ve yanlış hitap gerçek bir kişiyi rahatsız eder. Elle ayarlanıyor:

```bash
python kullanici.py hitap "Eyüp" "Bey"
python kullanici.py hitap "Zeynep" "Hanım"
python kullanici.py hitap "Eyüp"            # temizler
```

Boş bırakılırsa adıyla seslendiği o nadir anlarda yalnız adı söyler.
Olağan sesleniş her hâlükârda "efendim" olduğu için hiç doldurulmasa da
üslup bozulmaz.

## Gözlem Katmanı

Asistanın **ikinci döngüsü**. Bu katmandan önce PRISM'in gönderdiği her mesajın
sebebi ya kullanıcının bir cümlesiydi ya da bir saat (08:00 özeti, hatırlatıcı
alarmı). Üçüncü bir sebep yoktu: **fark ettiği için** konuşmak. Bir uşağı komut
yorumlayıcısından ayıran şey tam olarak o üçüncü sebep.

### Temel kural: sinyalleri kod bulur

    Sinyalleri KOD bulur (SQL + aritmetik, `sinyaller.py`).
    Model yalnızca "bu söylenmeye değer mi ve nasıl söylenir" sorusunu cevaplar.

Sebebi: kendiliğinden gelen bir mesajdaki uydurma bilgi, sorulunca gelendekinden
çok daha zararlı — kullanıcı onu beklemiyordu, bağlamı yok, doğruluğunu kontrol
etmek için sebebi yok. Bir kere "bunu uydurdun" dedirtirse kendiliğinden konuşma
hakkı biter. Model elinde yalnız `kanit` metinleriyle cümle kurar; sayı, tarih,
isim uyduramaz.

### Sinyaller (`modules/gozlem/sinyaller.py`)

| Anahtar | Ne yakalar | Ağırlık |
|---|---|---|
| `takip:<id>` | Sorulma vakti gelmiş takip ("dişçi nasıl geçti?") | 3 |
| `harcama_sessizligi` | Telefondaki dinleyici ölmüş (otomatik kayıt akışı kesildi) | 3 |
| `butce_asildi:<kat>` | Aylık limit geçildi | 3 |
| `butce_hizi:<kat>` | Harcama oranı ayın geçen oranını çok aşıyor | 2 |
| `olagandisi_harcama:<gün>` | Bugün, son 14 günün ortalamasının katı | 2 |
| `gorev_yigilmasi:<gün>` | Bir güne yığılmış görevler, komşu günler boş | 2 |
| `gecikmis_gorevler` | Vadesi geçmiş, tamamlanmamış yığın | 2 |
| `inatci_gorev:<id>` | Çok ertelenmiş / uzun süredir duran tek görev (en fazla 2) | 2 |
| `hava_cakismasi:<id>` | Yaklaşan **tek seferlik** görevin saatinde yağış / aşırı sıcak-soğuk | 2 |
| `hava_uyarisi:<gün>` | Görevden bağımsız kayda değer hava (bugün / yarın) — `HABER` | 1–2 |
| `tamamlama_orani` | Kurma hızı bitirme hızını çok aşıyor | 1 |
| `ev_halki:<id>` | Diğer kişinin yaklaşan Kritik/Önemli görevi | 1 |

### Sinyal türü: DURUM / ARIZA / TAKIP / HABER

Her sinyalin bir `kategori`si var ve bu, **modelin susma eşiğini tersine
çevirebiliyor**:

- **`DURUM`** — kullanıcının taraf olduğu bir hâl (bütçe, görev, hava).
  Varsayılan susmak; söylemek için sebep gerekir.
- **`ARIZA`** — bozulmuş ve düzeltilebilir bir şey. Varsayılan **söylemek**.
- **`TAKIP`** — kullanıcının kendi ağzından çıkmış bir olayın sonucu.
  Varsayılan **sormak**: sorulacak şeyi kendisi söylemişti, sormamak
  ilgisizlik olur.
- **`HABER`** — kullanıcının **bilmesine imkân olmayan**, dışarıdan gelen
  bilgi (hava tahmini). Varsayılan **söylemek**, ama tek cümle.

⚠️ Ayrım ilk gerçek turda ortaya çıktı: model `harcama_sessizligi`'ni görüp
*"kullanıcı zaten biliyor olabilir"* diyerek sustu — oysa dinleyici gerçekten
ölmüştü. **Arızanın tanımı gereği kullanıcı bilmiyor**; bilseydi düzeltmişti.
Asistanın kullanıcıdan önce fark etmesi beklenen şey tam olarak buydu.

⚠️ **Ağırlıkla karıştırma.** `butce_asildi` de ağırlık 3 ama `DURUM`:
kullanıcı zaten %80'de uyarı almış oluyor. Ağırlık "ne kadar önemli",
kategori "kullanıcının haberi var mı" sorusunu cevaplıyor.

⚠️ `HABER` de aynı ayrımdan doğdu. `hava_uyarisi` önce `DURUM`du ve model
sustu: *"acil bir durum bulunmuyor."* Kuralı doğru uygulamıştı — DURUM'un
tanımı "bunları kendisi de görebilir"di, oysa **yarının havasını görmesinin
hiçbir yolu yok**. Haberin değeri aciliyetinden değil, kullanıcının onu başka
türlü öğrenememesinden geliyor. Yönergedeki seçim sırası artık:
TAKIP/ARIZA → HABER → DURUM.

Yönergedeki 1. kural da aynı turda sıkılaştırıldı: *"zaten biliyor olabilir"*
susmak için yeterli değil, bildiğini düşünmek için somut bir sebep gerekiyor.

⚠️ `anahtar` **konu kimliği**: aynı anahtar `KONU_BEKLEME_GUNU` (3 gün) tekrar
seçilemiyor. Bu yüzden anahtar sabit olmalı — `gecikmis_gorevler` bilerek sayı
içermiyor; içerseydi sayı her değiştiğinde "yeni konu" sanılıp aynı şey her gün
söylenirdi. Kategoriye/kayda özel olanlar ise bilerek ayrı: yemek bütçesi
hakkında konuşmuş olmak ulaşım bütçesi hakkında susmayı gerektirmez.

### İki hava sinyali ayrı

| | `hava_cakismasi` | `hava_uyarisi` |
|---|---|---|
| Hava neyin nesi | bir **görevin bağlamı** | **haberin kendisi** |
| Hatırlatıcı yoksa | hiç çalışmaz | yine çalışır |
| Tekrarlayan görev | **elenir** | ilgisiz |
| Yağış eşiği | `YAGIS_KODU` (51, çisenti) | `HAVA_UYARI_YAGIS_KODU` (61, düzgün yağmur) |
| Anahtar | `hava_cakismasi:<görev id>` | `hava_uyarisi:<YYYY-MM-DD>` |

Eşikler bilerek farklı: çisenti dışarıda yapılacak bir işin ortasında önemli
olabilir, ama "yarın çiseliyor" diye kendiliğinden mesaj atmak Elazığ kışında
her gün konuşmak demektir. Yarının havası `HAVA_YARIN_SAATI`'nden (15:00)
önce konu edilmiyor — sabah özeti bugünü zaten veriyor, yarın ise akşama
doğru planlanan bir şey. Saatlik tahmin turda **bir kez** çekilip
(`hava_tahmini()`) iki üreticiye de veriliyor.

⚠️ **Tekrarlayan görevler `hava_cakismasi`'nda elenir.** "Akşam Vitamini"
her gün 21:37'de; yağmurlu her günde yeniden sinyal üretip listeyi kirletirdi.
Haber değeri de yok: her gün yapılan bir iş yağmurla onlarca kez çakışmıştır,
kullanıcı o çakışmayı zaten yaşamıştır. Havanın kendisi kaybolmuyor —
`hava_uyarisi` onu görevden bağımsız söylüyor. Burada aranan şey **tek
seferlik** bir planın havayla çakışması: "cuma 14:00 servise bırak".

⚠️ **Kod, görevin dışarıda olup olmadığını bilemez.** Hatırlatıcının metninde
yazmıyor ve "Sabah Vitamini" ile "koşuya çık" arasındaki farkı anlamak bir
yargı işi — aritmetik değil. Bu yüzden `hava_cakismasi` kanıtı soruyu açıkça
**açık bırakıyor** ("dışarıda yapılıp yapılmayacağı BİLİNMİYOR") ve kararı
modele devrediyor.

⚠️ Devretmek yetmedi, kuralı yönergeye yazmak da gerekti. İlk sürümde kanıt
zaten belirsizdi ama `YONERGE`'de karşılığı yoktu; model eline "şu görev şu
saatte, o saatte yağmur var" diye bir kanıt geçince bunu hazır bir uyarı sanıp
aktardı: *"'Sabah Vitamini' göreviniz hafif sağanak bekliyor, planınızı gözden
geçirmenizi öneririm."* Kanıt doğruydu, **seçim** saçmaydı. Kural artık
KURALLAR/8'de. Ders: bir yargıyı modele bırakmak, o yargının ölçütünü
yönergeye yazmadıkça bırakmak sayılmıyor.

### Susma bütçesi (`modules/gozlem/service.py`)

Sırayla uygulanıyor, **model çağrısı en sonda** — turların çoğu Groq'a hiç
uğramadan biter:

1. `users.gozlem_sinir` sıfır mı → çık
2. Sessiz saat mi (23:00–08:00) → sus
3. Günlük sınır doldu mu → sus
4. Son mesajdan `ASGARI_ARA_DAKIKA` (180) geçti mi → geçmediyse sus
5. Sinyal var mı → yoksa sus
6. Bu konular son 3 günde konuşuldu mu → konuşulduysa sus
7. Modele sor: değer mi → değmezse sus
8. Konuş

Tek gerçek tasarım riski **gürültü**: çok konuşan asistan susturulur, susturulan
asistan ölür. O yüzden susmak varsayılan, konuşmak istisna. `tests/test_gozlem.py`
testlerinin çoğu asistanın konuşMAdığını doğruluyor.

⚠️ **Kuru çalıştırma (`gozlem.py tur`) hiçbir bütçe engeline takılmaz** ama
engelleri `uyari` olarak raporlar. Gece yarısı ya da sınır dolmuşken de "ne
derdi" görülebilmeli; ama denemenin gerçekte gönderileceği anlamına gelmediği
de görünmeli.

Model çağrısına giden mesaj Telegram'a `html.escape()` ile gidiyor — modelden
düz metin isteniyor ama garanti değil, kaçırılmış bir `<` mesajı 400 ile
sessizce yutardı.

### Hafıza (`modules/gozlem/hafiza.py`)

Konuşmalardan kalıcı bilgiler süzülüp `hafiza` tablosuna yazılıyor ve her
mesajda `ai_router` yönergesine ekleniyor. Öncesinde asistanın tüm "hafızası"
son 10 mesajdı (`HISTORY_LIMIT`), üstelik `conversations` 30 günde bir
temizleniyor — yani PRISM kullanıcıyı her sabah yeniden tanıyordu.

⚠️ **Hafıza veritabanının kopyası değil.** "Yarın 14:00'te dişçi" bir bilgi
DEĞİL — o zaten `reminders` tablosunda; hafızaya yazılırsa randevu geçtikten
sonra orada yalan olarak kalır. Hafıza yalnız hiçbir tabloya yazılmayan şeyler
için: alışkanlık, tercih, süregelen durum, ilişki. Geçici olanlar `gecerlilik`
tarihiyle girip süresi dolunca siliniyor.

Çıkarım mesajın içinde değil ayrı bir turda (3 saatte bir): her mesaja fazladan
bir Groq çağrısı eklemek cevap süresini iki katına çıkarırdı. Yeni konuşma
satırı yoksa model hiç çağrılmıyor.

**Panelde yok, bilerek.** Kişi hakkında çıkarım içeriyor; görülmesi ve
düzeltilebilmesi şart ama gündelik arayüzde durması gerekmiyor:

```bash
python gozlem.py bilgi                       # kim hakkında ne biliyor
python gozlem.py unut 12                     # yanlış bir bilgiyi sil
python gozlem.py ekle "Eyüp" "..." --tur tercih
```

### Takip (`modules/gozlem/takip.py`)

"Yarın dişçiye gidiyorum" cümlesi hiçbir tabloya girmiyor: hatırlatıcı değil
(kullanıcı kurmadı), not değil, hafıza da değil (kalıcı bir özellik değil,
tek seferlik bir olay — hafızaya yazılsa bir hafta sonra orada yalan olurdu).
Ama bir uşağı asistandan ayıran şey tam da ertesi akşam **"dişçi nasıl
geçti?"** diye sorabilmesi.

Hafıza çıkarımıyla aynı turda, **ayrı bir model çağrısıyla ve ayrı damgayla**
çalışıyor. Tek yönergeye sıkıştırılabilirdi; ayrı tutulmasının sebebi
kuralların gerçekten farklı olması — biri kalıcı özellik arıyor, diğeri
bitecek bir olay. Aynı yönergede ikisi de zayıflıyor.

⚠️ **Soru, sinyal olarak gözlem turundan geçiyor** (`takip:<id>`), yani aynı
susma bütçesine tabi. Ayrı bir gönderme yolu açılsaydı günde 3 mesaj sınırı
sessizce delinirdi.

⚠️ **Bayatlayan takip düşer** (`TAKIP_BAYATLAMA_GUNU` = 3 gün). Geç kalmış
soru sorulmamış sorudan kötü: "geçen hafta dişçi nasıl geçti?" ilgi değil
dalgınlık gösterir.

⚠️ **İşaretleme gönderimden SONRA** (`service.tur`): Telegram'a ulaşılamazsa
soru sorulmamış sayılıp bir sonraki turda yeniden denenmeli.

⚠️ **Döküm satırları zaman damgası taşır** (`konusma.dokum()` → `[gg.aa ss:dd]`).
Damgasız dökümde "yarın randevum var" cümlesinin NE ZAMAN söylendiği belli
olmuyordu; model onu okuduğu ana göre çözüp **üç hafta önce olmuş bitmiş** bir
randevu için ertesi akşama soru kurdu (gerçekten oldu). Yönergedeki "geçmişte
kalmış olayları yazma" kuralı da damgasız uygulanamaz — model neyin geçmişte
kaldığını göremez. Bu, katmanın temel kuralının gereği: **olguyu kod verir**,
modelden cümlenin ne zaman söylendiğini tahmin etmesi istenemez. İki yönerge de
(`takip.py`, `hafiza.py`) damganın nasıl okunacağını ayrıca anlatıyor —
biçim değişirse ikisi de güncellenmeli.

⚠️ **Adı konmamış olay takip olmaz.** İlk gerçek çıkarım turunda model
`konu: "randevu"` üretti — çünkü kullanıcının cümlesi de o kadarını
söylüyordu. Ertesi akşam "Randevu nasıl geçti?" diye sormak ilgi değil
doldurulmuş form gibi durur. Çözüm modelden "daha belirgin ol" istemek
DEĞİL (bu onu uydurmaya iter, mimarinin kaçındığı şey); belirgin bir etiket
kurulamıyorsa olayı hiç yazmamak. Yönergedeki ilk "asla yazmazsın" kuralı bu.

⚠️ `UNIQUE(owner_id, konu)` **sorulmuş takipleri de kapsıyor** — aynı soru iki
gün arayla tekrarlanmasın diye. Bedeli: etiket `temizle()` onu düşürene kadar
(30 gün) kilitli, yani düzenli tekrar eden bir olay ikinci kez alınamaz.
Yanlış bir etiket girdiyse `takip-unut` ile silinmeli, yoksa o kelime bir ay
boyunca kullanılamaz.

```bash
python gozlem.py takip                 # sorulmayı bekleyenler
python gozlem.py takip-cikar "Eyüp"    # çıkarımı elle çalıştır
python gozlem.py takip-unut 3          # gereksiz bir soruyu iptal et
```

### İtiraz

İyi bir asistan her dediğini sorgusuz yapan değil. İki yerden geliyor:

| Nereden | Ne yapar |
|---|---|
| `ai_router._itiraz()` | Hatırlatıcı kurulunca çakışma (±30 dk) ve gün yığılması (5+) tespiti |
| `SYSTEM_PROMPT` → "İTİRAZ HAKKIN" | Sohbet yanıtlarında gerekçeli itiraz |

Çakışma tespiti bilerek **modelde değil kodda**: aritmetik bir iş, modele
bırakılırsa bazen görür bazen görmez — güvenilmez bir uyarı hiç uyarmamaktan
kötüdür. Ayrıca komut yanıtlarını `dispatch` kuruyor, modelin oraya yorum
iliştirme imkânı yok.

⚠️ İtiraz **işi engellemez**. Hatırlatıcı her hâlükârda kurulur, itiraz sadece
altına eklenen bir not. Kullanıcı ne istediğini biliyor olabilir.

### Ayarlama

```bash
python gozlem.py sinyal "Eyüp"        # şu an ne fark ediyor (hiçbir şey göndermez)
python gozlem.py tur "Eyüp"           # tam tur — ne derdi? (GÖNDERMEZ)
python gozlem.py tur "Eyüp" --gercek  # gerçekten gönder (onay sorar)
python gozlem.py gunluk               # konuştuğu VE sustuğu turlar
python gozlem.py seviye "Eyüp" 3      # günde en fazla 3 · 0 = kapalı
```

Eşikler `modules/gozlem/sinyaller.py` ve `service.py` başlarında toplu duruyor.
`gunluk` çıktısındaki "sustu" satırları olmadan hangi eşiğin yanlış olduğunu
anlamanın yolu yok.

## AI Routing Sistemi

`ai_router.py` — her Telegram mesajı şu pipeline'dan geçer:

1. `route_message(user_message, chat_id, owner_id)` çağrılır — `owner_id`
   oluşturulan/silinen her kaydın sahibi olur, `chat_id` yalnız konuşma geçmişinin anahtarı
2. `get_recent_messages(chat_id, limit=10)` → SQLite'tan konuşma geçmişi alınır
3. `parse_message(user_message, history)` → Groq'a system prompt + geçmiş + mesaj gönderilir
4. Groq saf JSON döner: `{"module": "...", "action": "...", "params": {...}}`
5. `dispatch(parsed)` → ilgili `_handle_*` fonksiyonuna yönlendirir
6. Kullanıcı mesajı ve Groq'un JSON yanıtı `conversations` tablosuna kaydedilir.
   Yanıt metni ayrıca `gorunen` sütununa yazılır — paneldeki sohbet geçmişi
   ondan çiziliyor (`route_message`'ın `gorunen` parametresi → "Panel Sohbeti")

**Çoklu komut:** Tek mesajda birden fazla iş varsa Groq `{"commands": [ {...}, {...} ]}`
döndürür; `dispatch()` diziyi görürse hepsini sırayla çalıştırıp yanıtları birleştirir
(en fazla `MAX_COMMANDS`=5). Tek iş varsa eski tekil biçim aynen çalışır.

**Modüller ve aksiyonlar:**
```
reminders.create / list / update / complete / delete   (update recurrence destekler)
ileti.create / list / delete                           (başka kullanıcıya söz iletme)
notes.create / read / list / search / update / delete
expenses.create / list / summary / delete              (create expense_date destekler — "dün")
budget.set / list / delete
weather.get
summary.get
chat.respond
```

**Panel adresi:** `ai_router.panel_adresi()` → `PANEL_URL`, yoksa `WEBHOOK_URL` (panel
webhook ile aynı alan adının kökünde). Adres system prompt'a gömülüyor, böylece
"site linkini ver" gibi cümleler `chat.respond` ile doğru adresi döndürüyor.
Hiç tanımlı değilse `(ayarlanmamış)` gider — boş bırakılsa model adres uydurabilirdi.
Aynı bilgi `/site` hızlı komutuyla Groq'a hiç uğramadan da alınabiliyor.

**Görsel mesajlar:** Fotoğraf geldiğinde önce `describe_image()` (vision modeli) Türkçe analiz üretir;
analiz `[Görsel analizi]: ...` bloğu olarak kullanıcı mesajına eklenip normal pipeline'a girer.
Fiş/fatura ise router harcama kaydeder, soru sorulmuşsa chat modunda yanıtlar.

**Önemli:** `dispatch()` içindeki `chat` modülü Groq'tan gelen serbest metin yanıtını doğrudan döner.
Hiçbir kategoriye girmeyen mesajlar için PRISM sohbet moduna geçer.

## Telegram Bot Akışı

`telegram_bot.py` — `/webhook` önce `X-Telegram-Bot-Api-Secret-Token` header'ını doğrular
(`TELEGRAM_WEBHOOK_SECRET` boşsa atlanır), update'i `BackgroundTasks`'e atıp hemen 200 döner
(Telegram retry → çift işlem riski yok). `_handle_message()` sırası:

1. Güvenlik: chat_id `users` tablosunda kayıtlı olmalı (tek env değeri değil).
   Tanınmayan sohbet "⛔ Yetkisiz" alır ve **chat_id log'a yazılır** — yeni kişi
   eklerken numarasını buradan alıyorsun
2. Hızlı komutlar kontrol edilir (Groq bypass): `/start /site /hava /ozet /liste /hatirlaticilar /notlar /butce`
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

**Bağlanmıyorsa `adb` ile kesin teşhis** (bir kez yaşandı, Redmi Note 13 / HyperOS):

```bash
adb logcat -d | grep -iE "MIUILOG- Reject service|Unable to bind notification"
adb shell dumpsys notification | grep -A 14 "Live notification listeners"   # bağlıysa listede olur
adb shell run-as com.eyup.prism cat shared_prefs/prism_listener_state.xml
adb shell run-as com.eyup.prism cat files/capture_log.json
adb shell cmd notification post -t "Test" testtag "metin"                   # dinleyici görüyor mu
```

İki tuzak vardı:
1. Servis `exported="false"` idi (yukarıdaki manifest notu).
2. **Xiaomi "Otomatik başlatma" izni** — kapalıyken MIUI'nin `AutoStartManagerService`'i
   sistemin bağlanmasını reddediyor. İzni açmak tek başına yetmiyor: Android o noktada
   pes etmiş oluyor, **uygulamayı tamamen kapatıp yeniden açmak** gerekiyor. Ayrıca pil
   kısıtlaması ayrı bir mekanizma — "Kısıtlama yok" yapılmazsa servis birkaç saat sonra
   yine ölür.

Dinleyicinin sessizce elediği durumlar (kalıcı bildirim, grup başlığı, metin okunamadı)
artık **seçili uygulamalar için** kayda düşüyor — eskiden hiçbir iz bırakmadan atlanıyordu.
Metin çıkarımı da tek alana bakmıyor: `EXTRA_BIG_TEXT`, `EXTRA_TEXT`, `EXTRA_TEXT_LINES`
(InboxStyle), `EXTRA_SUMMARY_TEXT` ve `tickerText` toplanıp en uzunu seçiliyor.

### Süreç öldürülünce dinleme durması

Son kullanılanlar ekranındaki **"hepsini kapat"** düğmesi uygulamayı normal kapatmaktan
farklı: süreci komple öldürüyor (aynı düğme Spotify'ın çalan müziğini de susturuyor,
"geri" ile çıkmak susturmuyor). Dinleyici de o süreçte yaşadığı için ölüyor.

Üç katmanlı savunma var, hiçbiri tek başına yeterli değil:

| Katman | Ne yapar | Sınırı |
|---|---|---|
| Son kullanılanlarda **kilitleme** 🔒 | "hepsini kapat" PRISM'i atlar | kullanıcının elle yapması gerekir |
| `ListenerWatchdogWorker` | 30 dk'da bir bağlı mı bakar, değilse `requestRebind()` | uygulama "durduruldu" durumuna sokulursa iş de iptal olur; ayrıca telefon ısınınca ertelenir |
| `catchUpMissed()` | geri bağlanınca panelde bekleyen bildirimleri toplar | bildirim panelden silinmişse kayıp |

`catchUpMissed()` (`onListenerConnected` içinde): ölü geçen sürede düşen bildirimler
`onNotificationPosted`'a hiç uğramıyor, ama çoğu banka bildirimi bildirim panelinde
duruyor. Geri bağlanınca `activeNotifications` okunup `lastSeenAt`'ten yeni olanlar
işleniyor (en fazla 24 saat geriye). Aynı bildirim ikinci kez gitse bile sunucu
`source_hash` ile tanıyıp eliyor — çift kayıt riski yok. `lastSeenAt` hiç yoksa
(ilk kurulum) atlanır, yoksa panelde birikmiş her şey harcamaya dönerdi.

**Ölçüldü (Redmi Note 13 / HyperOS, 12 Ağustos 2026):** süreç beklenmedik şekilde
ölürse sistem dinleyiciyi **2,6 saniyede** kendiliğinden geri bağlıyor —
`Scheduling restart of crashed service ... in 1000ms` → `Start proc ... for service`
→ `notification listener service connected`. Yani asıl korkulacak şey süreç ölümü
değil, uygulamanın **"durduruldu"** durumuna sokulması. Ayrıca dinleyici bağlıyken
`adb shell am kill` süreci öldüremiyor bile: bağlantı süreci canlı tutuyor.

⚠️ Bekçi işi JobScheduler'a bağlı, o da **termal kısıtlamaya** tabi: telefon ısındığında
(`Thermal Status: 2`) iş `STOP ... thermal` ile durduruluyor, yenisi hiç başlatılmıyor.
`adb shell dumpsys jobscheduler | grep -E "START: #u0a382|STOP: #u0a382"` ile görülür.
Bekçiye tek başına güvenilmemesinin sebebi bu — kilitleme asıl çözüm.

⚠️ **Diskteki "bağlı" bilgisi yalan söyleyebilir.** Süreç öldürüldüğünde
`onListenerDisconnected` hiç çağrılmıyor, `prism_listener_state.xml`'de `connected=true`
kalıyor. Gerçeği süreç içindeki `ExpenseNotificationListener.isBound` bayrağı söylüyor
(yeniden doğuşta false başlar); `reconcileListenerState()` ikisini eşitliyor ve hem
bekçi hem ayarlar ekranı bunu çağırıyor. Durum kartı ayrıca **bağlı görünüp 12 saattir
hiçbir şey görmemişse** uyarı basıyor — telefona günde onlarca bildirim düştüğü için
bu sessizlik fiilen ölüm demek.

## İletiler

"Zeynep'e akşam yedide şunu söyle" → o saatte alıcının Telegram'ına asistanın
ağzından düşen mesaj:

> 💬 **Eyüp Bey** şunu iletmemi istedi, efendim:
> *Akşam yemeğe geç kalacağım, beni bekleme.*

Alıcıya kendi hitabıyla ("efendim") sesleniliyor, gönderen adıyla anılıyor
("Eyüp Bey") — `ai_router.adiyla_hitap()` bu ayrımı zaten biliyor.
**Selamlama yok** ("Merhaba"): günde birkaç ileti gidince her seferinde
tekrarlanıp yapmacık duruyor.

### Neden kendi tablosu

| | Neden olmaz |
|---|---|
| `reminders` | Alıcı bunu görev sanır: "tamamla" der, sabah özetinde iş listesinde çıkar |
| `notes` | Kimse bir şey saklamak istemiyor |
| `takipler` | Takip SORMAK için; burada sorulacak değil iletilecek bir şey var |

⚠️ `owner_id` **yok, bilerek.** Projenin geri kalanında `owner_id` "bu kayıt
kimin" demek; burada iki taraf da gerçek. `gonderen_id` iptal hakkının kimde
olduğunu, `alici_id` mesajın kime gideceğini söylüyor. Tek sütunla "Zeynep'e
giden ama Eyüp'ün iptal edebildiği" kayıt ifade edilemezdi.

### Yanlış kişiye gitmeme

Bu, asistanın kullanıcı adına **başka bir insana** mesaj gönderdiği tek
mekanizma. Yanlış kurulan hatırlatıcıyı kullanıcı görüp düzeltir; yanlış
iletilen mesaj geri alınamaz. Korumalar:

⚠️ **chat_id'si olmayan alıcıya ileti açılmıyor.** `telegram_bot.sahibin_chati()`
sahipsiz bildirimleri `TELEGRAM_CHAT_ID`'e düşürüyor — yani ileti sessizce
GÖNDERENİN kendisine giderdi, kullanıcı "iletildi" sanırdı. Baştan reddediliyor.

⚠️ **Onay mesajı iletinin TAM METNİNİ gösteriyor.** Bu komut çoğunlukla sesli
veriliyor ve Whisper bir kelimeyi yanlış duyabiliyor. Zamanlanmışsa iptal
numarası da yazılıyor; hemen gidende en azından hata anında görülüp
düzeltmesi yollanabiliyor.

⚠️ **Türkçe büyük harf tuzağı** (`service.kisiyi_bul`): Python'da
`"İ".lower()` → `"i"` + ayrı bir birleşen nokta (U+0307). Yani "ZEYNEP"
ile "Zeynep" eşleşmiyordu. Küçültmeden önce `İ→i` ve `I→ı` elle eşleniyor.

⚠️ **İşaretleme gönderimden SONRA** (`service.iletildi`): Telegram'a
ulaşılamazsa ileti gönderilmemiş sayılıp bir sonraki turda yeniden denenmeli.

⚠️ **Bayatlayan ileti düşer** (`VAZGECME_DAKIKA` = 60). Sunucu kapalı
kaldıysa dört saat gecikmiş "akşam mesajı" iletmek, iletmemekten kötü —
bağlamı çoktan geçmiş olur.

⚠️ **Kişi başına en fazla `AZAMI_BEKLEYEN` (10) bekleyen ileti.** Alıcı bu
mesajları istemedi; sınır, asistanı mesaj yağdırma aracına çevirmemek için.

### Gözlem bütçesine tabi DEĞİL

Kendiliğinden konuşma sınırı (`users.gozlem_sinir`) buraya işlemiyor. Sebebi:
o bütçe **asistanın kendi inisiyatifini** dizginlemek için. İleti ise
kullanıcının açık talimatı — alıcı açısından nişanlısından gelen bir mesaj,
asistanın gevezeliği değil. Sınır yerine bekleyen sayısı sınırlı.

Zamanlanmış iletide gönderene teslim haberi gidiyor ("✅ ... iletildi"),
hemen gidende gitmiyor: onay mesajını zaten görüyor, ikincisi gürültü olur.

## İadeler

**Negatif `amount` = iade.** Ayrı tablo/sütun yok; aylık toplam ve bütçe uyarısı zaten
`SUM(amount)` olduğu için iade kendiliğinden düşülür. `service.validate_amount()` sıfırı
ve `MAX_ABS_AMOUNT` üstünü reddeder (fişteki "1.234,56"nın 123456 okunmasını yakalamak için),
negatifi serbest bırakır. Panel ve Android iadeyi yeşil `+` ile gösterir.

Banka "iade edildi" bildirimi ve "200 TL iade aldım" cümlesi de eksi kaydedilir —
ingest ve ai_router prompt'larında açıkça yazılı.

Çift kayıt kontrolü iadeyi orijinal harcamayla eşleştirmez (+273.90 ile −273.90 arası fark
547.80, eşik 0.005).

## Sesli Cevap

`ses.py` — metni sese çeviren tek yer. İki müşterisi var: Telegram ses notu ve
panelin baloncuk altındaki **Dinle** düğmesi.

### Ne zaman konuşur

**Kanalı aynalar:** sesli mesaj atana sesli cevap verir, yazana yazar.
Ayrı bir komut ya da ayar yok.

Sebebi: "Kaydedildi." için ses notu göndermek, dokunup dinlemeyi gerektirdiği
için düz yazıdan daha yorucu. Ama ona sesle konuşuyorsan ellerin zaten
meşguldür. Ses metnin YERİNE değil YANINA gidiyor — sayı ve tarih okumak
dinlemekten kolay.

Panelde ise düğmeye basınca, yani istendiğinde.

### Neden ElevenLabs (edge-tts denendi ve elendi)

⚠️ **Groq'un seslendirmesi Türkçe bilmiyor** (yalnız İngilizce ve Arapça).
Whisper (ses → metin) Groq'ta ama tersi başka bir kaynaktan gelmek zorunda.

⚠️ **Yerel model (Piper) bilerek seçilmedi.** Sunucunun 954 MB RAM'i var;
sentez sırasındaki 200-250 MB'lık sıçrama, bellek daralınca çekirdeğin en
şişman süreci öldürmesi demek — o da `prism`'in kendisi olurdu.

⚠️ **Önce `edge-tts` kullanıldı ve ELENDİ.** Bedava ve anahtarsızdı ama
Türkçede yalnız **iki sesi** var (Ahmet, Emel) ve ikisi de "haber spikeri"
karakterinde. Perde/hız ayarı sesin rengini değiştiriyor, **tavrını
değiştirmiyor** — JARVIS'i JARVIS yapan şey ise tam olarak tavır. Kullanıcının
ilk tepkisi net oldu: *"sesi hiç ama hiç beğenmedim, JARVIS'in tonu hiç yok."*
Bir spikere ayar çekerek o ton elde edilmiyor.

ElevenLabs'te ses kütüphaneden seçiliyor ve `stability` / `speed` ile tavır
gerçekten ayarlanabiliyor. Seçilen: **Daniel** (İngiliz, resmî, "steady
broadcaster").

⚠️ **Ücretsiz kademe ayda 10.000 karakter** — ortalama yanıt ~120 karakter,
yani ~80 sesli cevap. Kota bitince API 429 döner, `seslendir()` `None` verir,
asistan yazıyla devam eder. Kalan kota **panelde görünüyor**; görünmezse
kullanıcı sesin neden kesildiğini anlayamaz, arıza sanar.

⚠️ **Yedek motor bilerek YOK.** Kota bitince edge-tts'e düşmek kolaydı;
yapılmadı, çünkü asistanın sesinin bir gün habersizce değişmesi bozulmaktan
daha kafa karıştırıcı. Ses kimliğin parçası: ya o ses, ya sessizlik.

### Ses ayarı: kişiye özel ve PANELDE

`users.ses_id` / `ses_sakinlik` / `ses_hiz` (üçü de NULL olabilir →
`ses.ayar_coz()` varsayılana düşer). Panelde
`frontend/src/components/SesAyari.jsx`, Ayarlar sayfasında.

⚠️ **`.env`'e KONMADI ve Android uygulamasına da konmadı.** Ses kurcalayarak
bulunan bir şey ("biraz daha yavaş, biraz daha düz"): `.env` her deneme için
sunucuya girip servisi yeniden başlatmak, Android ise her deneme için APK
derleyip telefona kurmak demekti. İkisi de o döngüyü öldürürdü. Ayrıca
Android tarafı bilerek sensöre indirgendi (bkz. "Android: sensör uygulaması").

⚠️ **Önizleme KAYDETMEDEN çalışıyor:** `POST /api/chat/ses` gövdesinde
`ses_id`/`ses_sakinlik`/`ses_hiz` gelirse kullanıcının kayıtlı ayarının
üstüne geçici olarak biniyor. Aksi hâlde her deneme "kaydet, dinle, beğenme,
geri al" olurdu.

Uçlar: `GET /api/chat/ses/secenekler` (ses listesi + kota + mevcut ayar) ·
`PUT /api/chat/ses/ayar` (kaydet) · `POST /api/chat/ses` (seslendir).
Ses listesi API'den geliyor, sabit yazılmadı: ElevenLabs'te ses eklenip
çıkarılabiliyor, sabit liste bir gün olmayan bir sesi gösterip 422 aldırır.

### Metin temizliği

Yanıtlar Telegram için HTML taşıyor (`<b>`, `&amp;`) ve emoji içeriyor
(🔹 ☀️ 🟢). Ham okutulursa "küçüktür b büyüktür" duyulur. `ses.temizle()`
etiketleri söküyor, varlıkları çözüyor, emojiyi eliyor.

⚠️ Emoji filtresi tek başına **yetmiyor**: "☀️"nin sonundaki görünmez
varyasyon seçici (U+FE0F) `Mn` kategorisinde, yani simge sayılmıyor ve emojisi
silinince ortada kalıp okunuşta boşluk bırakıyordu. `Mn`'in tamamını elemek
Türkçe için gereksiz risk olduğundan yalnız seçici aralığı ayrıca düşürülüyor.

Elenirse ANLAM kaybedenler ise çevriliyor, atılmıyor: `°C` → "derece",
`₺` → "lira", `&` → "ve", `·` → ",".

Uzun metin sırayla cümle sonundan, olmazsa kelime sonundan kesiliyor —
`AZAMI_KARAKTER` (1200). Kelime yedeği şart: madde madde yazılmış bir özette
ilk yarıda hiç nokta olmayabiliyor ve yarım hece okunuyordu.

## Panel Sohbeti

Panelin `Sohbet` sayfası artık Telegram gibi davranıyor: geçmiş sayfa
yenilenince kaybolmuyor, sesli mesaj atılabiliyor. Başlık **PRISM** —
"Sohbet" yazınca kiminle konuşulduğu belli olmuyordu.

### İki metin, iki okur kitle

Geçmişi gösterebilmenin önündeki tek engel şuydu: `conversations` tablosunda
asistan satırı **ham JSON komut** tutuyor, çünkü model bir sonraki turda kendi
çıktı biçimini görmek zorunda. Ekrana `{"module": "reminders", ...}` basılamaz,
modele de formatlanmış metin verilemez. Çözüm ikinci bir sütun:

| Sütun | Kim okur | Asistan satırında ne var |
|---|---|---|
| `content` | model (`get_recent_messages`) | `{"module": "reminders", ...}` |
| `gorunen` | insan (`get_conversation`) | "Kaydedildi, efendim." |

`gorunen` NULL ise ikisi aynı demektir — düz yazılan kullanıcı mesajı gibi.
Farklı olduğu yerler: sesli mesajda döküm `🎤` ile, görselde kullanıcının
kendi cümlesi `🖼` ile giriyor (`user_message` orada baştan aşağı
`[Görsel analizi]: ...` bloğu — onu kullanıcının cümlesi diye ekrana basmak
yanlış olurdu).

⚠️ **Sütun eklenmeden önce yazılmış asistan satırları panelde GÖRÜNMEZ.**
`get_conversation()` `gorunen`i boş olan asistan satırını eliyor: ham JSON
göstermektense hiç göstermemek doğru. Kullanıcı satırları eskiden de okunur
olduğu için onlar `content`'ten çiziliyor.

### Telegram geçmişi panele karışmıyor

`GET /api/chat/gecmis` yalnız `panel:<id>` kovasını veriyor. Birleştirmek
görsel olarak daha zengin olurdu ama **asistanın hatırladığı şeyle
kullanıcının gördüğü şey ayrışırdı**: Telegram'da söylenen bir cümle ekranda
dururken model onu bağlam olarak almıyor ("ekranda duruyor, neden
hatırlamıyor?"). Kanallar arası süreklilik zaten hafıza katmanında var
(`hafiza` tablosu kanaldan bağımsız).

⚠️ Geçmiş **30 günlük** — `conversations` her gece 03:00'te temizleniyor.

### Sesli mesaj (`frontend/src/sesKaydi.js`)

Kayıt tarayıcıda (`MediaRecorder`), döküm sunucuda (`/api/chat/voice` →
Groq Whisper). Panelin kendi ses tanıması yok; Telegram'la aynı motor.

⚠️ **Uzantı önemli.** Chrome `audio/webm`, Safari (iPhone dahil) `audio/mp4`
üretiyor; Groq ikisini de kabul ediyor ama **dosya adının uzantısına** bakıyor.
`BICIMLER` listesi biçimle uzantıyı birlikte tutuyor, `isTypeSupported`
hiç yoksa Safari varsayılanına (`.m4a`) düşülüyor.

⚠️ **Kayıt bitince `stream.getTracks()` MUTLAKA durdurulmalı.** Durdurulmazsa
sekmedeki kırmızı kayıt göstergesi yanık kalır ve kullanıcı dinlendiğini sanar.
Sayfadan çıkışta da (`useEffect` temizliği) aynı şey yapılıyor.

⚠️ `navigator.mediaDevices` **güvenli bağlam** ister. Panel HTTPS'te ama yerel
ağdan düz http ile açılırsa tanımsız gelir — `sesKaydiDestekli()` o durumda
düğmeyi hiç çizmiyor. Mikrofon düğmesi ayrıca yazı alanı boşken görünür:
yazarken gönder düğmesinin yerini alıp yanlış tuşa bastırıyordu.

Açık unutulmuş mikrofona karşı üst sınır `AZAMI_SANIYE` (120) — süre dolunca
kayıt kendiliğinden gönderilir.

## Zamanlayıcı (scheduler.py)

- **Her 1 dakika:** `check_reminders()` → önce `reschedule_overdue_recurring()` ile bildirim
  penceresinden düşmüş (60 dk'dan fazla gecikmiş) tekrarlayanları ileri sarar, sonra bildirim
  zamanı gelenleri Telegram'a gönderir ve `last_notified_at` günceller.
  ⚠️ Süpürme şart: `get_reminders_to_notify()` 60 dk'dan fazla gecikmişleri listeden çıkarıyor,
  öteleme de eskiden sadece o döngüde yapılıyordu — sunucu 1 saatten uzun kapalı kalırsa
  tekrarlayan hatırlatıcı sessizce ölüyordu.
- **Her 1 dakika:** `bekleyen_iletiler()` → vakti gelen iletileri alıcılarına
  gönderir. `check_reminders`'ın İÇİNE konmadı, ayrı bir iş: hatırlatıcı
  tarafındaki bir hata iletileri de düşürürdü.
- **Her gün 08:00 (Europe/Istanbul):** `send_morning_summary()` → hava + görevler + harcama + notlar özetini Telegram'a gönderir.
- **Her gece 03:00:** `cleanup_conversations()` → 30 günden eski konuşma kayıtlarını siler.
- **Her akşam 21:00:** `send_evening_summary()` → bugün tamamlanan görevler, kalanlar,
  günün harcaması (iade sayısı dahil), yarının görevleri. `/aksam` ile elle çağrılır.
- **Her pazar 20:00:** `send_weekly_report()` → tamamlanan görev sayısı, haftalık harcama,
  geçen haftayla kıyas, günlük dağılım (metin çubuğu), kategori kırılımı. `/hafta` ile elle çağrılır.
- **09:00–21:00 arası iki saatte bir (dakika 15):** `gozlem_turu()` → asistanın
  kendi başına "söylenecek bir şey var mı" diye baktığı tur. Turların çoğu
  sessizce biter; ayrıntı → "Gözlem Katmanı". `users.gozlem_sinir` sıfır olan
  kişi atlanır (varsayılan sıfır — yani bu iş hiç kimseye kendiliğinden mesaj
  yollamadan yayına giriyor). Dakika 15 bilerek: :00'da özetler ve dakikalık
  hatırlatıcı işi dönüyor, iki bildirimin üst üste düşmesi istenmiyor.
- **Her 3 saatte bir (dakika 40):** `hafiza_cikarimi()` → yeni konuşmalardan
  hem kalıcı bilgileri (`hafiza`) hem sonradan sorulacak olayları (`takipler`)
  süzer. İki ayrı model çağrısı, ayrı `try` blokları — biri çökerse diğeri
  yine çalışır. Yeni konuşma satırı yoksa Groq'a hiç uğramaz.
- **Her gece 04:00:** `nightly_backup()` → `backup.py` SQLite backup API ile tutarlı kopya alır,
  gzip'ler, Telegram'a dosya olarak gönderir. `/yedek` komutuyla elle de tetiklenir.
  Sunucu tamamen kaybolsa bile yedek Telegram sohbetinde durur.

## Testler

```bash
pip install -r requirements-dev.txt
pytest
```

`tests/` — harcama doğrulaması ve iadeler, çift kayıt tespiti, hatırlatıcı öteleme/erteleme
mantığı, yedeğin geri yüklenebilirliği, **sahiplik kuralları** (`test_sahiplik.py`:
başkasının kaydını değiştirme denemesi 403, okuma serbest), **konum/hava durumu**
(`test_konum.py`) ve **gözlem katmanı** (`test_gozlem.py`). Her test geçici
veritabanı kullanır (`conftest.py`), gerçek `prism.db`'ye dokunulmaz.

⚠️ `conftest.py`'deki `db` fikstürü işlemi test bitene kadar **commit etmiyor**.
Kendi bağlantısını açan bir şeyi test ediyorsan (`service.tur()`, `auth.*`,
rota testleri) yazmalardan sonra `db.commit()` gerekiyor — yoksa öbür bağlantı
boş bir veritabanı görür ve hata "yok" gibi değil "davranış yanlış" gibi görünür.

## Hatırlatıcı Bildirim Planı

**Öncelik = kaç bildirim geleceği.** Sıklık değil, sabit noktalar
(`service.NOTIFICATION_POINTS`): vadeye kaç dakika kala haber verileceği yazılı,
eksi değer vadeden sonrasını gösterir.

| Öncelik | Bildirim anları | Toplam |
|---|---|---|
| 🔇 Sessiz (4) — **varsayılan** | vade anı | **1** |
| 🟢 Normal (3) | 1 sa kala · vade anı | 2 |
| 🟡 Önemli (2) | 1 gün · 1 sa kala · vade anı · +30 dk | 4 |
| 🔴 Kritik (1) | 1 gün · 3 sa · 1 sa · 15 dk kala · vade anı · +15 · +30 dk | 7 |

⚠️ **Eskiden "kalan süreye göre her N dakikada bir tekrarla" vardı.** Tekrarın sonu
olmadığı için bir hafta önceden kurulan tek bir kritik hatırlatıcı **34 bildirim**
üretiyordu ve "sadece vaktinde bir kez haber ver" diye bir seçenek yazılamıyordu.
Sabit noktalarda üst sınır listenin uzunluğu kadar; `tests/test_reminders.py`
her seviyenin tam olarak kendi listesini ürettiğini kilitliyor.

**Varsayılan neden en sessiz seviye:** hatırlatıcıyı kuran kişi çoğu zaman "sesi ne
kadar çıksın" diye düşünmüyor, sadece unutmak istemiyor. Varsayılan gürültülü olunca
her kayıt bildirim yağmuruna dönüyordu. Gerçekten ısrar edilmesi gereken işi kullanıcı
zaten kendi eliyle yükseltiyor. Varsayılan **dört yerde birden** aynı olmalı:
`service.DEFAULT_PRIORITY`, `routes.ReminderCreate`, `ai_router` yönergesi +
`dispatch()`, ve Android `ReminderCreate`.

**Hangi noktanın duyurulduğu ayrı sütunda tutulmuyor.** `last_notified_at` tek damga
ama yetiyor: damga anındaki kalan süre şu anki noktadan büyükse o nokta henüz
duyurulmamış demektir. Bunun üç sonucu var, üçü de bilinçli:

- **Yeni kayıt hemen bildirim yollamaz.** Damga yoksa `created_at`'e düşülüyor, yani
  kayıt kurulduğunda çoktan içinde olunan nokta "zaten biliniyor" sayılıyor. Olmasaydı
  iki saat sonrasına kurulan kritik bir hatırlatıcı, daha kaydedilir kaydedilmez
  "2 saat kaldı" derdi.
- **Vade anı ve sonrası bu kuralın dışında** — vadesi geçmiş olarak kurulan kayıt
  ("saat 3'e kur" derken 3'ü on dakika geçmişse) yine de haber verir.
- **Erteleme ve tarih düzenlemesi damgayı sıfırlamaz, ŞU AN'a çeker.** Sıfırlasaydı
  yeni vade bir noktanın içine düşer ve bildirim tuşa basıldıktan saniyeler sonra
  geri gelirdi.

Vadesi `GIVE_UP_AFTER_MINUTES` (60 dk) geçen kayıt listeden düşer;
`reschedule_overdue_recurring()` aynı sabiti kullanıyor — ikisi ayrışırsa tekrarlayan
hatırlatıcılar sessizce ölür.

## Environment Variables

```
TELEGRAM_TOKEN           → Bot token
TELEGRAM_CHAT_ID         → 1. kullanıcının chat ID'si. İki işi var: ilk kurulumda
                            users tablosuna yazılır, sonrasında sahipsiz kalan
                            bildirimlerin düştüğü yedek adres. Yetki kontrolü artık
                            buradan DEĞİL users tablosundan yapılıyor.
TELEGRAM_WEBHOOK_SECRET  → Webhook imza doğrulaması (boşsa devre dışı)
GROQ_API_KEY             → Groq API key (LLM + Whisper + Vision)
GROQ_MODEL               → Metin/komut modeli (varsayılan: llama-3.3-70b-versatile)
GROQ_FALLBACK_MODEL      → Ana model hata verirse düşülecek model (varsayılan: llama-3.1-8b-instant)
LOG_LEVEL                → DEBUG|INFO|WARNING|ERROR (varsayılan: INFO)
GROQ_WHISPER_MODEL       → Ses transkripsiyon modeli (varsayılan: whisper-large-v3)
GROQ_VISION_MODEL        → Görsel analiz modeli (varsayılan: qwen/qwen3.6-27b)
API_KEY                  → REST API anahtarı (X-API-Key header; boşsa auth devre dışı — sadece lokal).
                            Bu anahtarla gelen istek her zaman 1. kullanıcı sayılır.
PANEL_PASSWORD           → SADECE İLK KURULUMDA okunur: users tablosu boşken 1. kullanıcı
                            bu parolayla yaratılır. Sonra parolalar veritabanında (scrypt);
                            değiştirmek için `kullanici.py parola "<ad>"`. Env'i değiştirmek
                            girişi etkilemez.
PANEL_USER_NAME          → İlk kullanıcının adı (varsayılan: Eyüp). Sadece ilk kurulumda.
SESSION_SECRET           → Panel oturum biletinin imza anahtarı. Yoksa API_KEY'e düşer
                            (eski davranış). Değişirse açık oturumların hepsi düşer.
ELEVENLABS_API_KEY       → Seslendirme anahtarı. Yoksa ses hiç üretilmez,
                            asistan yazıyla çalışır. Yetkiler: Text to Speech
                            = Access, Voices = Read, User = Access.
TTS_VOICE_ID             → VARSAYILAN ses (Daniel: onwK4e9ZLuTAKqWW03F9).
                            Kişi başına ayar users tablosunda, panelden.
TTS_MODEL                → eleven_multilingual_v2 (turbo/flash telaffuzu düşürür)
TTS_MAX_CHARS            → Seslendirilecek azami karakter (varsayılan 600)
EXPENSE_DUPLICATE_WINDOW_MINUTES → Aynı tutarlı ikinci bildirimin çift sayılacağı aralık (varsayılan 5)
WEBHOOK_URL              → Genel HTTPS adresi (Telegram webhook için: https://kendi-alan-adin.example.com)
PANEL_URL                → Panelin adresi. Yazılmazsa WEBHOOK_URL kullanılır (ikisi aynı
                            alan adı). Yalnız panel başka bir yere taşınırsa gerekir.
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

## Akıl Yürüten Modeller ve Token Bütçesi

`GROQ_MODEL` bir **akıl yürüten** modelse (`openai/gpt-oss-*` ailesi gibi),
model cevabı vermeden önce içeriden düşünme adımları üretiyor ve **o adımlar
da `max_tokens` bütçesinden yiyor.** Bütçe dolunca JSON yarım kalıyor ve Groq
400 döndürüyor:

```
json_validate_failed: max completion tokens reached before generating a valid document
```

⚠️ Bu **sessiz** bir arıza: çağıran taraf sadece "yanıt alınamadı" görüyor,
sebebi görmüyor. Gözlem katmanının ilk gerçek turunda tam olarak bu oldu —
`max_tokens=300` ile hiçbir zaman geçerli JSON üretilemedi, yedek model de
aynı aileden olduğu için o da düştü.

**İki katmanlı savunma:**

1. `groq_client.complete_json()` bu hatayı tanıyıp **aynı modeli**
   `TOKEN_ARTIS_KATI` (3) katı bütçeyle bir kez daha deniyor. Yedek modele
   geçmek işe yaramıyor — o da aynı aileden olabiliyor.
2. Çağrı yerlerindeki taban değerler düşünme payı bırakacak şekilde büyütüldü:
   `parse_message` 900 · gözlem turu 900 · hafıza çıkarımı 900 · ingest 600.

`max_tokens` bir tavan, hedef değil — model işi bitince duruyor, yani geniş
bırakmanın maliyeti yok. Yeni bir Groq çağrısı eklerken dar tutma.

`tests/test_groq_client.py` yeniden deneme mantığını kilitliyor: bütçe hatası
→ aynı model geniş bütçeyle, başka hata → doğrudan yedek modele.

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

### Kullanıcı eklemek / parola değiştirmek

Parola ve chat_id `.env`'e yazılmıyor; ayrı bir komut satırı aracıyla veritabanına giriyor:

```bash
cd ~/prism && source venv/bin/activate
python kullanici.py listele                       # kim var, chat_id'leri ne
python kullanici.py ekle "Ad Soyad"               # parolayı ekranda sormaz (getpass)
python kullanici.py chat-id "Ad Soyad" 123456789  # Telegram'ı bağla
python kullanici.py parola "Ad Soyad"             # parola unutulursa yenisi
python kullanici.py ad "Eski Ad" "Yeni Ad"        # görünen adı değiştir
python kullanici.py hitap "Ad Soyad" "Bey"        # asistan "Ad Soyad Bey" desin
```

Ad değiştirmek zararsız: sahiplik `owner_id` (numara) üzerinden, oturum bileti de
numara taşıyor. Tek kısıt benzersizlik — `ad` sütununda UNIQUE yok ama hem bu araç
hem `gecmis.py --kisi` kişiyi adıyla buluyor, o yüzden çakışma engelleniyor.

**chat_id nasıl öğrenilir:** kişi bota `/start` yazar → sunucu logunda
`Yetkisiz chat: <numara>` satırı çıkar (`sudo journalctl -u prism -n 50 | grep Yetkisiz`).
O numara `chat-id` komutuna verilir; kişi tekrar `/start` yazdığında artık tanınır.

⚠️ Bu araç veritabanını doğrudan açar. Servis çalışırken de güvenli (SQLite WAL),
ama parola değişikliği **açık oturumları düşürmez** — çerez süresi dolana kadar geçerli.

### Kendiliğinden konuşmayı açmak

Gözlem katmanı yayına **kapalı** giriyor (`users.gozlem_sinir` DEFAULT 0), yani
kod sunucuya çıktığında kimseye sürpriz bildirim gitmez. Açmadan önce denemek:

```bash
cd ~/prism && source venv/bin/activate
python gozlem.py sinyal "Eyüp"          # şu an ne fark ediyor
python gozlem.py tur "Eyüp"             # ne derdi? (GÖNDERMEZ)
python gozlem.py seviye "Eyüp" 3        # günde en fazla 3 mesaj
```

Birkaç gün sonra `python gozlem.py gunluk` ile hangi turda ne olduğuna bak;
çok/az konuşuyorsa eşikler `modules/gozlem/` içinde.

### Konuşma geçmişine bakmak

```bash
cd ~/prism && source venv/bin/activate
python gecmis.py                        # son 40 satır, herkes
python gecmis.py --kisi "Zeynep"      # Telegram + panel kanallarını birlikte getirir
python gecmis.py --son 100 --ara dişçi
python gecmis.py --ham                  # Groq'un ürettiği JSON'u olduğu gibi
```

`conversations` **30 günlük** (03:00 temizliği) — eski bir şeyin çıkmaması arıza değil.
Asıl arşiv Telegram'ın kendi sohbeti; buradaki kayıt "bot neyi nasıl anladı"nın izi.

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

Uç hem **GET hem HEAD** kabul eder (`@app.api_route(..., methods=["GET", "HEAD"])`).
Bazı izleme servisleri gövdeyi indirmemek için HEAD atıyor; FastAPI ise Starlette'in
aksine GET rotasına HEAD'i kendiliğinden eklemiyor ve 405 dönüyordu — yukarıdaki
alarm kuralıyla birleşince sürekli yanlış alarm demek. `tests/test_health.py`
HEAD'in hem 200 hem 503 halini ayrıca sınıyor.

### Web paneli (aynı domain, kökte)

Caddy tek site bloğunda yolları ayırır:

| Yol | Koruma | Nereye |
|---|---|---|
| `/webhook*` | Telegram imzası | backend |
| `/api/auth/me,login,logout` | yok (giriş uçları) | backend |
| `/api/auth/konum` | rota kendi `Depends`'ini taşıyor | backend |
| `/api/*` | `X-API-Key` **veya** `prism_session` çerezi | backend |
| `/health` | yok | backend |
| diğer her şey | yok — panel kabuğu sır içermez | `/var/www/prism-panel/dist` statik dosyalar |

Panel gizli anahtar **taşımaz**: `frontend/.env`'de `VITE_API_URL` boş (istekler göreli yoldan
aynı sunucuya gider), `VITE_API_KEY` diye bir değişken yok. Kullanıcı kendi parolasıyla giriş
yapar (users tablosu), HttpOnly çerez alır. Derleme sonrası `dist/` içinde `X-API-Key`
geçmemeli — kontrol et.

**iPhone'da ana ekrana ekleme:** Safari → Paylaş → "Ana Ekrana Ekle". `display: standalone`
olduğu için tarayıcı çubuğu olmadan açılır. Bildirim göndermez — hatırlatıcılar Telegram'dan
gelir, panel yalnızca bakma/yazma yeri.

Panel güncelleme: PC'de `npm run build` → `scp -r frontend\dist ...:/var/www/prism-panel/` →
sunucuda **`chmod -R a+rX /var/www/prism-panel`** (scp Windows'tan kısıtlı izinle geldiği için şart).

Lokal geliştirme: `npm run dev` — `vite.config.js` içindeki proxy `/api` ve `/health`
isteklerini `127.0.0.1:8000`'e yönlendirir, böylece `VITE_API_URL` boşken de çalışır.

⚠️ **Tailwind dinamik sınıf adlarını göremez.** `` className={`stagger-${i}`} `` yazarsan
o kurallar derlemede silinir; sabit liste kullan (`STAGGER[i]` — Sidebar/Dashboard'da örneği var).

Uygulama açılışta `set_webhook()` çağırır, Telegram webhook otomatik ayarlanır.
Lokal test için `WEBHOOK_URL` boş bırakılabilir — webhook kurulmaz, bot Telegram'dan mesaj almaz ama API endpoint'leri çalışır.
