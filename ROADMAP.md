# PRISM — Özellik Yol Haritası

Bu doküman PRISM'e eklenebilecek özellikleri kategori ve öncelik bazında listeler.
Öncelikler: 🔴 Kritik · 🟡 Değerli · 🟢 Güzel olur

---

## 1. Güvenlik ve Altyapı (önce bunlar yapılmalı)

| Öncelik | Özellik | Açıklama |
|---|---|---|
| 🔴 | REST API kimlik doğrulama | `/api/*` şu an tamamen açık. Basit bir `X-API-Key` header kontrolü (FastAPI dependency) + frontend'de `VITE_API_KEY` yeterli. |
| 🔴 | Telegram webhook secret token | `setWebhook`'a `secret_token` parametresi ekle, `/webhook`'ta `X-Telegram-Bot-Api-Secret-Token` header'ını doğrula. |
| 🔴 | Webhook'u arka planda işle | FastAPI `BackgroundTasks` ile hemen `200` dön; Groq yavaş kalırsa Telegram update'i tekrar gönderiyor → çift işlem riski. |
| 🟡 | CORS daraltma | `allow_origins=["*"]` + `allow_credentials=True` geçersiz kombinasyon. Frontend Railway domain'ini açıkça yaz. |
| 🟡 | HTML escape | Kullanıcı içeriği (`title`, `content`) Telegram HTML parse_mode'a escape edilmeden gidiyor. `html.escape()` sarmalayıcısı ekle. |
| 🟡 | Gerçek loglama | `print()` yerine `logging` modülü; Railway loglarında seviye/zaman görünür olur. |
| 🟡 | conversations tablosu temizliği | Sınırsız büyüyor. Scheduler'a günlük "30 günden eski kayıtları sil" job'ı ekle. |
| 🟡 | SQLite yedekleme | Scheduler ile günlük yedek alıp Telegram'a dosya olarak gönder (kendi botun sana `sendDocument` ile `prism.db` yollar — bedava offsite backup). |
| 🟢 | Testler + CI | `pytest` ile service katmanı testleri (saf fonksiyonlar, kolay test edilir); GitHub Actions. |
| 🟢 | Groq JSON mode | `response_format={"type": "json_object"}` kullan; ``` bloğu ayıklama kırılganlığı ortadan kalkar. |

## 2. Hatırlatıcılar

| Öncelik | Özellik | Açıklama |
|---|---|---|
| 🔴 | Tekrarlayan hatırlatıcıda "tamamla" düzeltmesi | Şu an tekrarlayan bir hatırlatıcı tamamlanınca kalıcı olarak ölüyor. `complete_reminder` recurrence ≠ none ise `reschedule_recurring` çağırmalı. |
| 🟡 | Ön bildirim ("X dk önce haber ver") | `remind_before` kolonu: "toplantıdan 30 dk önce hatırlat". |
| 🟡 | Gelişmiş tekrarlama | "hafta içi her gün", "2 günde bir", "her ayın 15'i" → `recurrence_rule` (basit RRULE alt kümesi). |
| 🟡 | REST'te update + recurrence | `ReminderCreate`'e `recurrence` ekle; `PUT /api/reminders/{id}` endpoint'i yaz (web panelde düzenleme için şart). |
| 🟢 | Etiket/bağlam | "iş", "ev", "sağlık" etiketleri; "iş hatırlatıcılarımı göster". |
| 🟢 | ICS takvim dışa aktarma | `/api/reminders/calendar.ics` endpoint'i → telefon takvimine abone ol. |
| 🟢 | Alt görevler | Bir hatırlatıcıya checklist bağlama. |

## 3. Notlar

| Öncelik | Özellik | Açıklama |
|---|---|---|
| 🟡 | Not düzenleme | `notes.update` ne AI router'da ne REST'te var. İkisine de ekle. |
| 🟡 | FTS5 tam metin arama | SQLite FTS5 virtual table; `LIKE %q%`'dan çok daha iyi Türkçe arama. |
| 🟢 | Sabitleme (pin) | Önemli notlar listede üste çıksın. |
| 🟢 | AI ile not özetleme | "ders notlarımı özetle" → Groq'a notları verip özet döndür. |
| 🟢 | Sesli not modu | "not al" + ses → transkript otomatik not olarak kaydedilsin (şu an ses → komut olarak yorumlanıyor). |
| 🟢 | Notlar üzerinde soru-cevap (mini RAG) | "X hakkında ne not almıştım?" → ilgili notları bulup Groq'la cevap sentezle. |

## 4. Harcamalar ve Bütçe

| Öncelik | Özellik | Açıklama |
|---|---|---|
| 🟡 | Geçmiş tarihli harcama | System prompt'a `expense_date` ekle — "dün 200 TL harcadım" şu an bugüne yazılıyor (service zaten destekliyor). |
| 🟡 | Budget REST endpoint'leri | Budget modülünün hiç REST route'u yok → web panelden bütçe yönetilemiyor. |
| 🟡 | Gelir takibi | `incomes` tablosu; aylık net durum ("bu ay ne kadar kaldı?"). |
| 🟡 | Tekrarlayan harcamalar / abonelikler | Netflix, kira, fatura → scheduler her ay otomatik işlesin + "abonelik özetim" komutu. |
| 🟢 | Fiş/fatura fotoğrafı OCR | Telegram'a fotoğraf at → Groq vision modeli (llama-4-scout) tutar+kategori çıkarsın. |
| 🟢 | CSV/Excel dışa aktarma | `/api/expenses/export?month=` endpoint'i. |
| 🟢 | Aylık karşılaştırma | "geçen aya göre nasılım?" → iki ayın kategori bazlı farkı. |
| 🟢 | Döviz/altın kurları | Türkiye bağlamında çok kullanışlı: "dolar kaç?" → ücretsiz kur API'si + istenirse günlük özete ekle. |

## 5. Yeni Modüller

| Öncelik | Modül | Açıklama |
|---|---|---|
| 🟡 | Alışkanlık takibi (habits) | "su içtim", "spor yaptım" → günlük seri (streak) takibi, haftalık grafik, sabah özetine entegre. |
| 🟡 | Alışveriş listesi | "listeye süt ekle", "markete gidince listemi göster" — hatırlatıcıdan ayrı hafif bir liste. |
| 🟢 | İlaç takibi | Tekrarlayan hatırlatıcının özelleşmiş hali: doz, stok azalınca uyarı. |
| 🟢 | Önemli günler | Doğum günleri, yıldönümleri → yıllık recurrence + N gün önceden haber. |
| 🟢 | İzleme/okuma listesi | Film, dizi, kitap kaydet; "ne izlesem?" önerisi. |
| 🟢 | Haber/gündem özeti | RSS kaynaklarından başlıkları çekip Groq ile özetleyerek sabah özetine ekle. |
| 🟢 | Pomodoro / odak | "25 dk odaklanacağım" → süre sonunda Telegram bildirimi. |

## 6. AI / NLP İyileştirmeleri

| Öncelik | Özellik | Açıklama |
|---|---|---|
| 🟡 | Çoklu komut desteği | "Yarın 10'da toplantı hatırlat ve 50 TL yemek ekle" → şu an tek JSON dönüyor, ilk komut kayboluyor. Prompt'u `{"commands": [...]}` dizi formatına geçir, dispatch'i döngüye al. |
| 🟡 | Silme onayı | "tüm notları sil" gibi yıkıcı işlemlerde inline "Evet/Vazgeç" butonu. |
| 🟡 | Sohbet modunda gerçek bağlam | Chat modunda geçmişteki JSON'lar yerine kullanıcının verileri (bugünkü görevler vb.) sisteme verilirse "bugün neyim var?" gibi sorulara daha isabetli yanıt verir. |
| 🟢 | Tool use / function calling | Prompt-JSON yerine Groq'un native tool calling API'si — şema doğrulama bedavaya gelir. |
| 🟢 | Model fallback | Groq rate limit yerse `llama-3.1-8b-instant`'a düş. |
| 🟢 | Uzun vadeli hafıza | "kahveyi sade içerim" gibi kalıcı tercihler için `memories` tablosu; system prompt'a enjekte et. |

## 7. Telegram Deneyimi

| Öncelik | Özellik | Açıklama |
|---|---|---|
| 🟡 | Akşam özeti (21:00) | "Bugün 3 görev tamamladın, 2 kaldı, 240 TL harcadın, yarın seni şunlar bekliyor." |
| 🟡 | Haftalık rapor (Pazar) | Haftalık harcama grafiği (metin/emoji bar), tamamlanan görev oranı. |
| 🟢 | Liste mesajlarında inline butonlar | `/liste` çıktısında her öğenin yanında ✅/🗑 butonu — ID ezberlemeye son. |
| 🟢 | Telegram Mini App | Mevcut React panel Telegram WebApp olarak açılabilir (`web_app` butonu) — tek dokunuşla panel. |
| 🟢 | Bot komut menüsü | `setMyCommands` ile / menüsü kayıtlı olsun. |
| 🟢 | Sesli yanıt (TTS) | İstenirse özet yanıtları ses dosyası olarak dön. |

## 8. Web Panel

| Öncelik | Özellik | Açıklama |
|---|---|---|
| 🔴 | Panel girişi (auth) | API key auth ile birlikte basit giriş ekranı. |
| 🟡 | Bütçe sayfası | Budget REST endpoint'leri açılınca limit ayarlama + ilerleme barları. |
| 🟡 | Hatırlatıcı düzenleme + recurrence | Şu an panelden tekrarlayan hatırlatıcı oluşturulamıyor ve düzenleme yok. |
| 🟢 | Aylık trend grafikleri | Recharts zaten var: 6 aylık harcama trendi, kategori dağılım pastası. |
| 🟢 | Sohbet geçmişi görüntüleyici | `conversations` tablosunu okuyan salt-okunur sayfa. |
| 🟢 | PWA | Manifest + service worker → telefona "uygulama" olarak eklenebilir. |
| 🟢 | Not düzenleyici (markdown) | Notlar için markdown önizlemeli düzenleme. |

---

## Önerilen uygulama sırası

1. **Güvenlik paketi** (1. bölümdeki 🔴'lar) — API key, webhook secret, background processing
2. **Tekrarlayan hatırlatıcı tamamlama düzeltmesi** — mevcut bug
3. **Küçük kazanımlar** — geçmiş tarihli harcama, notes.update, budget REST, HTML escape
4. **Akşam özeti + haftalık rapor** — az kod, yüksek günlük değer
5. **Çoklu komut desteği** — AI deneyimini belirgin iyileştirir
6. **Habits modülü** — yeni modül şablonunu takip eden ilk büyük ekleme
