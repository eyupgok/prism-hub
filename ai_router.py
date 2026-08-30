import html
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import pytz

from groq_client import complete_json
from logging_setup import get_logger

log = get_logger("prism.ai")

TZ = pytz.timezone("Europe/Istanbul")


def _esc(value: Any) -> str:
    """Kullanıcı içeriğini Telegram HTML parse_mode için güvenli hale getirir"""
    return html.escape(str(value if value is not None else ""))

SYSTEM_PROMPT = """\
Sen PRISM'sin — {ad} kişisinin kişisel asistanı. Ona "efendim" diye seslenirsin.
Görevin onun günlük hayatını yönetmek: hatırlatıcılar, notlar, harcamalar, bütçe, hava durumu ve günlük özet.

Kullanıcı Türkçe konuşur. Mesajları analiz et ve SADECE JSON formatında yanıt ver, başka hiçbir şey yazma.

## KİMLİĞİN VE ÜSLUBUN
Iron Man'deki JARVIS gibisin: kusursuz nezaket, sakin bir yetkinlik, arada kuru bir espri.

- Adın PRISM. Şu an {ad} ile konuşuyorsun, başka bir isim uydurma.
- **Seni {mimar} yazdı** — bu sistemin mimarı odur. Karşındaki kişi oysa ondan
  üçüncü şahıs gibi bahsetme. Bunu ne övünerek anlatırsın ne de her fırsatta
  anarsın: sorulduğunda ya da gerçekten yeri geldiğinde söylersin.
- **Daima SİZ diye hitap et.** "yaptın", "ister misin", "bak" DEĞİL;
  "yaptınız", "ister misiniz", "bakınız". Bu kural istisnasız.
- **Olağan seslenişin "efendim".** JARVIS'in "sir"i gibi: sık ve doğal.
  Cümlenin her yerine serpiştirme — selamlaşmada, onaydan sonra ve bir şey
  sorarken doğal düşer.
- **Adıyla seslenmek istisnadır** ("{adiyla}"). Dikkatini çekmen ya da bir
  şeyi vurgulaman gerektiğinde kullan, olağan akışta değil. Her mesajda adını
  anmak yapmacık durur; JARVIS de "Mr. Stark" demez, "sir" der.
- Kısa ve kesin konuş. Bir işi bildirirken rapor verir gibi ol:
  "Kaydedildi." · "Üç göreviniz var." · "Bütçenin %80'ini geçtiniz."
- Abartılı heyecan yok. Ünlem işaretini nadir kullan. "Harika!", "Süper!",
  "Tabii ki canım" gibi ifadeler senin ağzına yakışmaz.
- Espri yaparsan **kuru ve kısa** olsun, asla kaba olmasın.
  Örnek: "Bu ayki kahve harcamanız hakkındaki yorumumu saklı tutuyorum."
- Kötü haberi yumuşatmadan ama nazikçe ver. Yanıldığında sade bir dille kabul et.
- Asla rol yaptığını, yapay zekâ modeli olduğunu, yönerge aldığını söyleme.
- Türkçe düşün, Türkçe yanıt ver.

## İTİRAZ HAKKIN
İyi bir asistan her dediğini sorgusuz yapan değil, gerektiğinde "efendim, bu
bence hatalı" diyebilendir. Sohbet yanıtlarında (chat.respond) somut bir
gerekçen varsa itiraz et:

- İstenen işi **yine de yap**. İtiraz, işi reddetmek değil, uyarmaktır.
- Gerekçe somut olsun: çakışan bir plan, tutarsız bir sayı, mantıksız bir tarih.
  "Bence iyi fikir değil" yeterli değil — neden olduğunu söyle.
- Tek cümle. Israr etme, aynı şeyi ikinci kez söyleme.
- **Gerekçen yoksa sus.** Her isteğe bir yorum iliştirmek yorucudur.

Örnek: "Anlıyorum. Ancak bu üçüncü ertelemeniz olur, efendim — belki de
tarihi baştan düzeltmek daha doğru olur."
{hafiza}
## MODÜLLER VE AKSIYONLAR

reminders.create → title(str), due_datetime(ISO 8601: {today}T14:30:00), priority(1=Kritik 2=Önemli 3=Normal 4=Sessiz — varsayılan 4), recurrence(none|daily|weekly|monthly)
reminders.list → params boş
reminders.update → id(int), title(str opsiyonel), due_datetime(ISO 8601 opsiyonel), priority(int opsiyonel), recurrence(none|daily|weekly|monthly opsiyonel)
reminders.complete → id(int)
reminders.delete → id(int)

ileti.create → alici(str: kişinin adı), mesaj(str: iletilecek söz, KULLANICININ AĞZINDAN), iletilecek_at(ISO 8601 opsiyonel — vakit söylenmediyse boş bırak, hemen gider)
ileti.list → params boş (gönderilmeyi bekleyenler)
ileti.delete → id(int)

notes.create → title(str), content(str), category(iş|kişisel|genel|ders|fikir)
notes.list → category(str opsiyonel)
notes.read → id(int)
notes.search → query(str)
notes.update → id(int), title(str opsiyonel), content(str opsiyonel), category(str opsiyonel)
notes.delete → id(int)

expenses.create → amount(float), category(yemek|ulaşım|eğlence|fatura|alışveriş|diğer), description(str opsiyonel), expense_date(YYYY-MM-DD opsiyonel — sadece geçmiş bir günden bahsediliyorsa doldur), expense_time(HH:MM opsiyonel — fiş/faturada saat yazıyorsa), from_receipt(bool opsiyonel — bilgi fiş/fatura görselinden okunduysa true)
expenses.list → month(YYYY-MM opsiyonel)
expenses.summary → month(YYYY-MM opsiyonel)
expenses.delete → id(int)

budget.set → category(yemek|ulaşım|eğlence|fatura|alışveriş|diğer), amount(float)
budget.list → params boş
budget.delete → category(str)

weather.get → params boş
summary.get → params boş

## ZAMAN İFADELERİ
Şu an: {now} (Europe/Istanbul)
Bugün: {today}

Türkçe zaman ifadelerini şöyle çevir:
- "yarın" → yarının tarihi
- "bugün" → bugünün tarihi
- "öğlen / öğle" → 12:00
- "sabah" → 09:00
- "akşam" → 18:00
- "gece" → 21:00
- "öğleden sonra 2" → 14:00
- "saat 2" → bağlama göre 14:00 veya 02:00 (gündüz varsay)
- "pazartesi", "salı" vb. → gelecek o günün tarihi
- "hafta sonu" → gelecek cumartesi
- "bu akşam" → bugün 18:00
- "bu gece" → bugün 21:00

Saat yorumlama kuralları:
- Kullanıcı "bugün saat X'e" derse ve o saat geçmişse, otomatik olarak akşam versiyonunu al (örn: saat 9 geçtiyse 21:00 yap)
- "sabah X" → her zaman AM (09:00 gibi)
- "akşam X" veya "gece X" → her zaman PM (21:00 gibi)
- Saat belirtilmeden sadece rakam varsa ve geçmişse → 12 ekle (PM'e çevir)
- Asla geçmiş bir saate hatırlatıcı kurma

## HATIRLATICI YARATMA KURALLARI
Şu ifadeler hatırlatıcı anlamına gelir:
"hatırlatıcı kur/ekle", "unutma", "randevum var", "toplantım var", "sınavım var", "teslim tarihi", "deadline", "başvuru", "ödev", "hatırlat"

Tekrarlama belirleme:
- "her gün", "günlük" → recurrence: daily
- "her hafta", "haftalık", "her pazartesi" vb. → recurrence: weekly
- "her ay", "aylık" → recurrence: monthly
- belirtilmemişse → recurrence: none

Öncelik belirleme (kaç kere bildirim gideceğini belirler):
- "kritik", "çok önemli", "acil", "kesinlikle" → priority: 1  (7 bildirim)
- "önemli", "unutma", "sakın kaçırmayayım" → priority: 2      (4 bildirim)
- "önceden haber ver", "erkenden hatırlat" → priority: 3      (2 bildirim)
- belirtilmemişse → priority: 4                               (1 bildirim, tam vaktinde)
Kullanıcı ısrar ölçüsünü söylemediyse HER ZAMAN 4 kullan. Öncelik yükseltmek
bildirim sayısını artırır; istenmediği halde yükseltmek rahatsız edicidir.

## NOT ALMA KURALLARI
Şu ifadeler not anlamına gelir:
"not al", "yaz", "kaydet", "aklımda kalsın", "unutmayayım"

## HARCAMA KURALLARI
Şu ifadeler harcama anlamına gelir:
"harcadım", "ödedim", "aldım", "TL", "lira", "para"

İade / iptal / geri ödeme:
- "200 TL iade aldım", "aldığım ayakkabıyı iade ettim, 450 TL geri geldi" → expenses.create
  ama amount NEGATİF olsun (-200, -450). Kategori iadenin ait olduğu alışverişinkidir.
- İade tutarı aylık toplamdan kendiliğinden düşer, ayrıca bir şey yapma.

Geçmiş tarihli harcama:
- "dün 200 TL harcadım" → expense_date: dünün tarihi (YYYY-MM-DD)
- "geçen cuma", "3 gün önce" vb. → ilgili günün tarihi
- Tarihten bahsedilmiyorsa expense_date gönderme (bugün varsayılır)

## GÖRSEL MESAJLAR
Kullanıcı fotoğraf gönderirse mesajda "[Görsel analizi]: ..." bloğu bulunur — bu, gönderilen fotoğrafın içeriğidir.
- Fiş/fatura analiziyse ve kullanıcı kaydetmek istiyorsa (veya sadece fiş gönderip hiçbir şey yazmadıysa) expenses.create kullan: tutar, kategori, işyeri adını description'a, fişteki tarih bugünden farklıysa expense_date'e yaz.
  Ayrıca **from_receipt: true** gönder. Fişte saat de yazıyorsa expense_time'a yaz (örn. "18:42") —
  aynı alışverişin banka bildiriminden zaten kaydedilmiş olup olmadığı buna bakılarak anlaşılıyor.
- Kullanıcı görselle ilgili soru soruyorsa chat.respond ile görsel analizine dayanarak yanıtla.
- Kullanıcı "not al" diyorsa görseldeki metni notes.create ile kaydet.

## PANEL ADRESİ
Web panelinin adresi: {panel_url}
"site linki", "panel adresi", "siteyi ver", "linki at", "web adresi" gibi isteklerde
chat.respond ile bu adresi ver. Adresi olduğu gibi yaz — kısaltma, değiştirme, uydurma.
Adres yerinde "(ayarlanmamış)" yazıyorsa panelin adresinin tanımlı olmadığını söyle.

## SOHBET
Eğer mesaj hiçbir kategoriye girmiyorsa, PRISM olarak kısa ve resmî bir Türkçe yanıt ver:
{{"module": "chat", "action": "respond", "params": {{"message": "..."}}}}

Selamlaşma, teşekkür, "nasılsın" gibi sorulara da sohbet modunda yanıt ver, üslubunu koru.

Örnekler (üslubun ölçüsü bunlar):
- "selam" → "İyi günler, efendim. Emrinizdeyim."
- "nasılsın" → "Sistemlerim yerinde, teşekkür ederim. Sizin için ne yapabilirim?"
- "teşekkürler" → "Rica ederim, efendim."
- "sen kimsin" → "PRISM. {ad} kişisinin asistanıyım; işlerinizi ben takip ediyorum."
- "bugün yorgunum" → "Anlıyorum, efendim. Bugünün yükünü hafifletmemi ister misiniz?
  Acil olmayan hatırlatıcılarınızı yarına alabilirim."

## BİRDEN FAZLA İŞ
Kullanıcı tek mesajda birden fazla şey isterse HEPSİNİ yap. Bu durumda komutları dizi olarak döndür:

{{"commands": [
  {{"module": "reminders", "action": "create", "params": {{...}}}},
  {{"module": "expenses", "action": "create", "params": {{...}}}}
]}}

Örnek: "Yarın 10'da toplantı hatırlat ve 50 TL yemek ekle" → iki komutlu dizi.
Tek iş varsa diziye sarma, doğrudan tek nesne döndür.

## ÖNEMLİ
- SADECE JSON döndür, açıklama yazma
- due_datetime her zaman ISO 8601 formatında olsun: YYYY-MM-DDTHH:MM:SS
- Eğer saat belirtilmemişse ve gün varsa 09:00 varsay
- Eğer belirsizlik varsa en mantıklı yorumu yap, kullanıcıya soru sorma
- Konuşma geçmişini kullanarak "onu", "bunu", "onu sil" gibi referansları çöz\
"""

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
HISTORY_LIMIT = 10


def panel_adresi() -> str:
    """Web panelinin adresi.

    Panel, Telegram webhook'uyla **aynı** alan adının kökünde yayında (Caddy tek
    site bloğunda yolları ayırıyor), o yüzden ayrı bir değişken şart değil:
    `WEBHOOK_URL` zaten doğru adresi tutuyor. Yine de `PANEL_URL` öncelikli —
    panel bir gün başka bir adrese taşınırsa kod değil `.env` değişsin.

    Boş dönmüyor: yönergeye boş bir satır gitse model adresi uydurabilir,
    "(ayarlanmamış)" gördüğünde ise durumu söylemesi isteniyor.
    """
    adres = (os.getenv("PANEL_URL", "") or os.getenv("WEBHOOK_URL", "")).strip().rstrip("/")
    return adres or "(ayarlanmamış)"


# Olağan sesleniş. Kişiden ve cinsiyetten bağımsız, JARVIS'in "sir"inin
# karşılığı. Asistanın ağzından çıkan seslenişlerin neredeyse tamamı bu.
OLAGAN_HITAP = "efendim"

# PRISM'i yazan kişi. **Hafızaya değil kimliğe ait**: hafıza kullanıcı hakkında
# bilgi tutar ve kişiye özeldir, mimar ise kim konuşursa konuşsun aynıdır —
# Zeynep konuşurken de mimar Eyüp Bey'dir.
#
# users tablosundan okunmuyor: her mesaja fazladan bir sorgu eklerdi ve bu
# değişen bir değer değil. Sistemin sahibi değişirse burası da değişir.
MIMAR = "Eyüp Bey"


def adiyla_hitap(ad: str, hitap: Optional[str]) -> str:
    """Adıyla sesleniş: "Eyüp Bey" / "Zeynep Hanım" / hitap yoksa yalnız ad.

    ⚠️ Bu asistanın OLAĞAN seslenişi DEĞİL — o `OLAGAN_HITAP` ("efendim").
    Buradaki biçim vurgu için; yönergelerde "istisnadır" diye işaretli.
    Her mesajda adı anmak yapmacık duruyor, JARVIS de "Mr. Stark" demiyor.

    Addan cinsiyet çıkarılmıyor: yanlış hitap gerçek bir kişiyi rahatsız eder.
    Doldurmak için: kullanici.py hitap "<ad>" "Bey"
    """
    hitap = (hitap or "").strip()
    return f"{ad} {hitap}" if hitap else ad


def yonerge_metni(
    ad: str = "kullanıcı",
    hitap: Optional[str] = None,
    hafiza_metni: str = "",
    now: Optional[datetime] = None,
) -> str:
    """Yönergenin yer tutucularını doldurur.

    Tek yerden kurulmasının sebebi pratik: yönergeye yeni bir alan eklendiğinde
    (hitap, panel adresi, hafıza — üçü de sonradan geldi) `format()` çağıran her
    nokta KeyError ile kırılıyor. Şimdi çağıran tek bir yer var.
    """
    now = now or datetime.now(TZ)
    return SYSTEM_PROMPT.format(
        now=now.strftime("%Y-%m-%d %H:%M"),
        today=now.strftime("%Y-%m-%d"),
        ad=ad,
        adiyla=adiyla_hitap(ad, hitap),
        mimar=MIMAR,
        panel_url=panel_adresi(),
        hafiza=hafiza_metni,
    )


async def parse_message(
    user_message: str,
    history: List[Dict] = None,
    ad: str = "kullanıcı",
    hitap: Optional[str] = None,
    hafiza_metni: str = "",
) -> Dict[str, Any]:
    """Kullanıcı mesajını Groq'a gönderir ve JSON komut olarak döner.

    `ad` ve `hitap` yönergeye gömülür: sistem iki kişilik, asistan karşısındakine
    kendi adıyla ve doğru hitapla seslenmeli. Eskiden yönergede "Eyüp" sabit
    yazılıydı ve bot ikinci kullanıcıya da "Selam Eyüp" diyordu.

    `hafiza_metni` asistanın kişi hakkında biriktirdiği kalıcı bilgiler
    (`modules.gozlem.hafiza.yonergeye`). Boş geçilebilir — hafıza boşken
    yönergeye hiçbir şey eklenmiyor, çünkü "BİLDİKLERİN: (yok)" diye bir
    başlık modele orayı doldurma baskısı yapıyor.

    JSON modu ve model yedeği `groq_client.complete_json()` içinde hallediliyor.
    """
    messages = [{"role": "system", "content": yonerge_metni(ad, hitap, hafiza_metni)}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Akıl yürüten modellerde (gpt-oss) düşünme adımları da bu bütçeden yiyor.
    # Çoklu komut çıktısı zaten uzun; dar bırakmak JSON'u yarıda kesiyor.
    return await complete_json(messages, max_tokens=900)


# Tek mesajda çalıştırılacak azami komut sayısı — modelin uçmuş bir çıktısı
# yüzünden onlarca işlem yapılmasın.
MAX_COMMANDS = 5


async def dispatch(parsed: Dict[str, Any], owner_id: int) -> str:
    """Komut(ları) çalıştırır.

    İki biçim kabul edilir:
    - Tek iş:     {"module": ..., "action": ..., "params": {...}}
    - Çoklu iş:   {"commands": [ {...}, {...} ]}

    Kullanıcı "yarın 10'da toplantı hatırlat ve 50 TL yemek ekle" dediğinde
    eskiden tek JSON dönüyordu ve ikinci iş sessizce kayboluyordu.
    """
    commands = parsed.get("commands")
    if isinstance(commands, list) and commands:
        results = []
        for command in commands[:MAX_COMMANDS]:
            if isinstance(command, dict):
                results.append(await dispatch_one(command, owner_id))
        if len(commands) > MAX_COMMANDS:
            results.append(f"<i>({len(commands) - MAX_COMMANDS} komut atlandı)</i>")
        return "\n\n".join(r for r in results if r)

    return await dispatch_one(parsed, owner_id)


async def dispatch_one(parsed: Dict[str, Any], owner_id: int) -> str:
    """Tek bir komutu ilgili servis fonksiyonuna yönlendirir"""
    module = parsed.get("module")
    action = parsed.get("action")
    params = parsed.get("params", {})

    try:
        if module == "chat":
            return _esc(params.get("message", "Nasıl yardımcı olabilirim?"))

        if module == "reminders":
            return await _handle_reminders(action, params, owner_id)

        if module == "ileti":
            return await _handle_ileti(action, params, owner_id)

        if module == "notes":
            return await _handle_notes(action, params, owner_id)

        if module == "expenses":
            return await _handle_expenses(action, params, owner_id)

        if module == "budget":
            return await _handle_budget(action, params, owner_id)

        if module == "weather":
            from modules.weather import service as weather_svc
            from auth import kullanici_getir

            weather = await weather_svc.get_weather(kullanici_getir(owner_id))
            return weather_svc.format_weather_message(weather)

        if module == "summary":
            from modules.summary import service as summary_svc
            return await summary_svc.get_morning_summary(owner_id)

        return f"❓ Bilinmeyen modül: {module}"

    except KeyError as e:
        # Groq beklenen bir parametreyi göndermemiş — kullanıcıya anlaşılır bir şey söyle
        log.warning("Eksik parametre: modül=%s aksiyon=%s alan=%s", module, action, e)
        return "⚠️ Ne yapmamı istediğinizi çözemedim. Biraz daha açık ifade eder misiniz?"
    except Exception:
        # Hata izi kayıtlara; kullanıcıya iç detay (dosya yolu, SQL, API mesajı) gitmesin
        log.exception("Komut çalıştırılamadı: modül=%s aksiyon=%s", module, action)
        return "⚠️ İşlem sırasında bir aksaklık oldu. Kayda geçirdim."


# İki hatırlatıcının arası bu kadar dakikadan azsa çakışıyor sayılır.
CAKISMA_DAKIKA = 30

# Bir güne bu kadar görev düşerse "hepsi gerçekten bugüne mi ait" diye sorulur.
GUN_YIGILMA_ESIGI = 5


def _itiraz(conn, owner_id: int, yeni: Dict[str, Any]) -> str:
    """Yeni kurulan hatırlatıcı hakkında söylenecek bir itiraz varsa metni.

    Bu itiraz **modelden değil koddan** geliyor, bilerek. Komut yanıtlarını
    `dispatch` kuruyor; modelin oraya yorum iliştirme imkânı yok. Ayrıca
    çakışma tespiti aritmetik bir iş — modele bırakılırsa bazen görür bazen
    görmez, bu da güvenilmez bir uyarı demektir.

    İş her hâlükârda YAPILMIŞ oluyor; bu yalnızca eklenen bir not. İtirazın
    isteği engellememesi kural: kullanıcı ne istediğini biliyor olabilir.
    """
    from modules.reminders import service as svc

    due = svc.parse_dt(yeni["due_datetime"])
    gun = due.strftime("%Y-%m-%d")
    ayni_gun = 0

    for r in svc.list_reminders(conn, owner_id, include_completed=False):
        if r["id"] == yeni["id"]:
            continue
        d = svc.parse_dt(r["due_datetime"])
        if abs((d - due).total_seconds()) <= CAKISMA_DAKIKA * 60:
            return (
                f"\n\n<i>Ancak {d.strftime('%H:%M')} saatinde zaten "
                f"'{_esc(r['title'])}' göreviniz var. Birini kaydırmamı "
                f"ister misiniz?</i>"
            )
        if d.strftime("%Y-%m-%d") == gun:
            ayni_gun += 1

    if ayni_gun + 1 >= GUN_YIGILMA_ESIGI:
        return (
            f"\n\n<i>Bu, {due.strftime('%d.%m')} günü için {ayni_gun + 1}. göreviniz. "
            f"Hepsi gerçekten o güne mi ait?</i>"
        )

    return ""


async def _handle_reminders(action: str, params: Dict, owner_id: int) -> str:
    from database import get_db
    from modules.reminders import service as svc

    with get_db() as conn:
        if action == "create":
            r = svc.create_reminder(
                conn,
                owner_id,
                params["title"],
                params["due_datetime"],
                # Model öncelik yazmadıysa en sessiz seviye. Yönergede de yazıyor
                # ama son söz burada: varsayılanı modelin insafına bırakmıyoruz.
                params.get("priority", svc.DEFAULT_PRIORITY),
                params.get("recurrence", "none"),
            )
            due = svc.parse_dt(r["due_datetime"])
            msg = (
                f"✅ Hatırlatıcı kuruldu.\n"
                f"📌 {_esc(r['title'])}\n"
                f"📅 {svc.format_dt(due)}\n"
                f"🏷 {svc.PRIORITY_NAMES.get(r['priority'], 'Normal')}"
            )
            rec_label = svc.RECURRENCE_LABELS.get(r.get("recurrence", "none"), "")
            if rec_label:
                msg += f"\n🔁 {rec_label}"
            return msg + _itiraz(conn, owner_id, r)

        if action == "list":
            reminders = svc.list_reminders(conn, owner_id, False)
            if not reminders:
                return "📋 Aktif hatırlatıcı yok."
            lines = ["📋 <b>Hatırlatıcılarınız:</b>\n"]
            for r in reminders:
                due = svc.parse_dt(r["due_datetime"])
                emoji = svc.PRIORITY_EMOJIS.get(r["priority"], "🟢")
                rec = " 🔁" if r.get("recurrence", "none") != "none" else ""
                lines.append(f"{emoji} [{r['id']}] {_esc(r['title'])} — {svc.format_dt(due)}{rec}")
            return "\n".join(lines)

        if action == "update":
            r = svc.update_reminder(
                conn,
                owner_id,
                params.get("id"),
                params.get("title"),
                params.get("due_datetime"),
                params.get("priority"),
            )
            if not r:
                return "❌ Böyle bir hatırlatıcı bulamadım."
            due = svc.parse_dt(r["due_datetime"])
            return (
                f"✏️ Hatırlatıcı güncellendi!\n"
                f"📌 {_esc(r['title'])}\n"
                f"📅 {svc.format_dt(due)}\n"
                f"🏷 {svc.PRIORITY_NAMES.get(r['priority'], 'Normal')}"
            )

        if action == "complete":
            r = svc.complete_reminder(conn, owner_id, params.get("id"))
            if not r:
                return "❌ Böyle bir hatırlatıcı bulamadım."
            if r.get("rescheduled"):
                due = svc.parse_dt(r["due_datetime"])
                return f"✅ '{_esc(r['title'])}' tamamlandı!\n🔁 Sonraki tekrar: {svc.format_dt(due)}"
            return f"✅ '{_esc(r['title'])}' tamamlandı."

        if action == "delete":
            r = svc.get_reminder_by_id(conn, params.get("id"))
            if not r:
                return "❌ Böyle bir hatırlatıcı bulamadım."
            due = svc.parse_dt(r["due_datetime"])
            return await _ask_delete_confirmation(
                "reminder", r["id"], f"📌 {_esc(r['title'])} — {svc.format_dt(due)}"
            )

    return f"❓ Bilinmeyen aksiyon: {action}"


async def _handle_ileti(action: str, params: Dict, owner_id: int) -> str:
    """Başka bir kullanıcıya, asistanın ağzından iletilecek söz.

    ⚠️ Onay mesajı iletinin TAM METNİNİ gösteriyor. Sebebi ses: bu komut çoğu
    zaman sesli mesajla veriliyor ve Whisper bir kelimeyi yanlış duyabiliyor.
    Kullanıcı ne gideceğini görmezse yanlış cümle nişanlısına gider ve haberi
    bile olmaz. Zamanlanmışsa hâlâ iptal edebilir; hemen gidende en azından
    hatayı anında görüp düzeltmesini yollar.
    """
    from database import get_db
    from modules.iletiler import service as svc

    with get_db() as conn:
        if action == "create":
            try:
                ileti = svc.olustur(
                    conn,
                    owner_id,
                    params.get("alici", ""),
                    params.get("mesaj", ""),
                    params.get("iletilecek_at"),
                )
            except svc.IletiHatasi as e:
                return _esc(str(e))

            alici_ad = _esc(ileti["alici"]["ad"])
            govde = f"«{_esc(ileti['mesaj'])}»"
            if ileti["hemen"]:
                # Gönderimi dakikalık iş yapıyor; burada "iletilecek" demek
                # doğru, "iletildi" demek yalan olurdu.
                return f"{alici_ad} kişisine birazdan iletiyorum:\n{govde}"
            an = svc.datetime.fromisoformat(ileti["iletilecek_at"])
            return (
                f"{an.strftime('%d.%m %H:%M')} — {alici_ad} kişisine ileteceğim:\n"
                f"{govde}\n\nVazgeçerseniz: «{ileti['id']} numaralı iletiyi iptal et»"
            )

        if action == "list":
            bekleyen = svc.bekleyenler(conn, owner_id)
            if not bekleyen:
                return "Bekleyen iletiniz yok."
            satirlar = ["<b>Bekleyen iletiler:</b>"]
            for i in bekleyen:
                an = svc.datetime.fromisoformat(i["iletilecek_at"])
                satirlar.append(
                    f"[{i['id']}] {an.strftime('%d.%m %H:%M')} → {_esc(i['alici_ad'])}: "
                    f"«{_esc(i['mesaj'])}»"
                )
            return "\n".join(satirlar)

        if action == "delete":
            silinen = svc.iptal(conn, owner_id, int(params["id"]))
            if not silinen:
                return "Öyle bir bekleyen ileti bulamadım."
            return f"İptal edildi: «{_esc(silinen['mesaj'])}»"

    return "Bu iletiyle ne yapmamı istediğinizi anlayamadım."


async def _handle_notes(action: str, params: Dict, owner_id: int) -> str:
    from database import get_db
    from modules.notes import service as svc

    with get_db() as conn:
        if action == "create":
            n = svc.create_note(conn, owner_id, params["title"], params["content"], params.get("category", "genel"))
            return f"📝 Not kaydedildi.\n📌 {_esc(n['title'])}\n🏷 {n['category']}"

        if action == "read":
            n = svc.get_note_by_id(conn, params.get("id"))
            if not n:
                return "❌ Böyle bir not bulamadım."
            return f"📝 <b>{_esc(n['title'])}</b>\n🏷 {n['category']}\n\n{_esc(n['content'])}"

        if action == "list":
            cat = params.get("category")
            notes = svc.list_notes(conn, owner_id, cat)
            if not notes:
                return "📝 Kayıtlı not yok."
            header = f"📝 <b>Notlar{' — ' + _esc(cat) if cat else ''}:</b>\n"
            lines = [header] + [f"• [{n['id']}] {_esc(n['title'])} ({n['category']})" for n in notes[:10]]
            return "\n".join(lines)

        if action == "search":
            notes = svc.search_notes(conn, owner_id, params.get("query", ""))
            if not notes:
                return f"🔍 '{_esc(params.get('query'))}' için bir sonuç bulamadım."
            lines = ["🔍 <b>Arama sonuçları:</b>\n"] + [
                f"• [{n['id']}] {_esc(n['title'])}" for n in notes[:10]
            ]
            return "\n".join(lines)

        if action == "update":
            n = svc.update_note(
                conn,
                owner_id,
                params.get("id"),
                params.get("title"),
                params.get("content"),
                params.get("category"),
            )
            if not n:
                return "❌ Böyle bir not bulamadım."
            return f"✏️ Not güncellendi!\n📌 {_esc(n['title'])}\n🏷 {n['category']}"

        if action == "delete":
            n = svc.get_note_by_id(conn, params.get("id"))
            if not n:
                return "❌ Böyle bir not bulamadım."
            return await _ask_delete_confirmation(
                "note", n["id"], f"📝 {_esc(n['title'])} ({n['category']})"
            )

    return f"❓ Bilinmeyen aksiyon: {action}"


async def _ask_delete_confirmation(kind: str, item_id: int, label: str) -> str:
    """Silmeyi hemen yapmaz; Telegram'a onay butonu gönderir.

    AI mesajı yanlış anlayıp yanlış kaydı silebilir ve silinen geri gelmez.
    Ne silineceğini göstermek, iki dokunuşa değer.
    """
    import confirm
    from telegram_bot import send_message

    token = confirm.remember({"kind": kind, "id": item_id})

    await send_message(
        f"🗑 <b>Silinecek</b>\n{label}\n\n<i>Onaylıyor musunuz?</i>",
        reply_markup={"inline_keyboard": [[
            {"text": "🗑 Evet, sil", "callback_data": f"delok_{token}"},
            {"text": "Vazgeç", "callback_data": f"delno_{token}"},
        ]]},
    )
    return "🗑 Silmeden önce onayınızı bekliyorum."


def _receipt_moment(params: Dict) -> Optional[str]:
    """Fişteki tarih + saatten ISO bir an üretir. Saat okunamadıysa None döner —
    o zaman çift kayıt kontrolü gün seviyesine düşer."""
    time_str = (params.get("expense_time") or "").strip()
    if not time_str:
        return None

    day = params.get("expense_date") or datetime.now(TZ).strftime("%Y-%m-%d")
    try:
        return datetime.strptime(f"{day} {time_str}", "%Y-%m-%d %H:%M").isoformat()
    except ValueError:
        return None


async def _check_receipt_duplicate(conn, params: Dict, owner_id: int) -> Optional[str]:
    """Fişteki alışveriş zaten kayıtlıysa uyarı metni döner, değilse None."""
    from modules.expenses import service as svc
    from modules.expenses.ingest import (
        DUPLICATE_WINDOW_MINUTES,
        format_tl,
        remember_duplicate,
    )
    from telegram_bot import send_message

    expense_date = params.get("expense_date") or datetime.now(TZ).strftime("%Y-%m-%d")
    source_at = _receipt_moment(params)

    twin = svc.find_duplicate(
        conn,
        owner_id,
        params["amount"],
        source_at=source_at,
        window_minutes=DUPLICATE_WINDOW_MINUTES,
        expense_date=expense_date,
        day_level=True,   # fişte saat olmayabilir
    )
    if not twin:
        return None

    candidate = {
        "amount": params["amount"],
        "category": params.get("category", "diğer"),
        "description": params.get("description", "") or "Fiş",
        "expense_date": expense_date,
        "source": "receipt",
        "source_hash": None,
        "source_at": source_at,
    }
    token = remember_duplicate(candidate)

    await send_message(
        "\n".join([
            "🔁 <b>Bu alışveriş zaten kayıtlı görünüyor</b>",
            f"{format_tl(params['amount'])} TL · {_esc(candidate['description'])}",
            f"<i>Mevcut kayıt: #{twin['id']} — {_esc(twin['description'])} ({twin['expense_date']})</i>",
        ]),
        reply_markup={"inline_keyboard": [[
            {"text": "➕ Yine de kaydet", "callback_data": f"dupadd_{token}"},
        ]]},
    )
    return "🔁 Bu alışveriş zaten kayıtlı görünüyor — dilerseniz aşağıdaki mesajdan yine de ekleyebilirsiniz."


async def _handle_expenses(action: str, params: Dict, owner_id: int) -> str:
    from database import get_db
    from modules.expenses import service as svc

    with get_db() as conn:
        if action == "create":
            # Fişten okunan harcama, banka bildiriminden zaten kaydedilmiş olabilir.
            # Elle yazılan harcamalara karışmıyoruz — kullanıcı bilerek girmiştir.
            if params.get("from_receipt"):
                warning = await _check_receipt_duplicate(conn, params, owner_id)
                if warning:
                    return warning

            try:
                e = svc.create_expense(
                    conn,
                    owner_id,
                    params["amount"],
                    params.get("category", "diğer"),
                    params.get("description", ""),
                    params.get("expense_date"),
                    source="receipt" if params.get("from_receipt") else "manual",
                    source_at=_receipt_moment(params) if params.get("from_receipt") else None,
                )
            except svc.InvalidAmount as err:
                return f"⚠️ Tutarı kaydedemedim: {err}"
            refund = e["amount"] < 0
            msg = (
                f"{'↩️ İade kaydedildi.' if refund else '💰 Harcama kaydedildi.'}\n"
                f"💵 {abs(e['amount']):.2f} TL — {e['category']}\n"
                f"📅 {e['expense_date']}\n"
                f"📝 {_esc(e['description']) or '—'}"
            )
            alert = svc.check_budget_alert(conn, owner_id, e["category"])
            if alert:
                msg += f"\n\n{alert}"
            return msg

        if action == "list":
            expenses = svc.list_expenses(conn, owner_id, params.get("month"))
            if not expenses:
                return "💰 Kayıtlı harcama yok."
            total = sum(e["amount"] for e in expenses)
            lines = ["💰 <b>Harcamalar:</b>\n"]
            for e in expenses[:10]:
                lines.append(
                    f"• [{e['id']}] {e['expense_date']} | {e['amount']:.0f} TL | {e['category']} | {_esc(e['description']) or '—'}"
                )
            lines.append(f"\n<b>Toplam: {total:.0f} TL</b>")
            return "\n".join(lines)

        if action == "summary":
            s = svc.get_monthly_summary(conn, owner_id, params.get("month"))
            lines = [f"📊 <b>{s['month']} Harcama Özeti:</b>\n", f"💰 Toplam: {s['total']:.0f} TL\n"]
            for cat, total in sorted(s["by_category"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {cat}: {total:.0f} TL")
            return "\n".join(lines)

        if action == "delete":
            e = svc.get_expense_by_id(conn, params.get("id"))
            if not e:
                return "❌ Böyle bir harcama bulamadım."
            return await _ask_delete_confirmation(
                "expense", e["id"],
                f"💵 {abs(e['amount']):.2f} TL — {e['category']} · {_esc(e['description']) or '—'} ({e['expense_date']})",
            )

    return f"❓ Bilinmeyen aksiyon: {action}"


async def _handle_budget(action: str, params: Dict, owner_id: int) -> str:
    from database import get_db
    from modules.expenses import service as svc

    with get_db() as conn:
        if action == "set":
            b = svc.set_budget(conn, owner_id, params["category"], float(params["amount"]))
            return f"✅ Bütçe limiti ayarlandı.\n🏷 {b['category']}: {b['monthly_limit']:.0f} TL/ay"

        if action == "list":
            budgets = svc.get_all_budgets(conn, owner_id)
            if not budgets:
                return "📊 Henüz bütçe limiti ayarlanmamış.\n💡 Örnek: 'Yemek için aylık 3000 TL bütçe koy'"
            lines = ["📊 <b>Aylık Bütçe Limitleri:</b>\n"]
            month = datetime.now(TZ).strftime("%Y-%m")
            for b in budgets:
                alert = svc.check_budget_alert(conn, owner_id, b["category"], month)
                status = "🚨" if alert and "aşıldı" in alert else ("⚠️" if alert else "✅")
                lines.append(f"{status} {b['category']}: {b['monthly_limit']:.0f} TL/ay")
            return "\n".join(lines)

        if action == "delete":
            ok = svc.delete_budget(conn, owner_id, params.get("category", ""))
            return "🗑 Bütçe limiti kaldırıldı." if ok else "❌ Böyle bir kategori bulamadım."

    return f"❓ Bilinmeyen aksiyon: {action}"


def _hafiza(owner_id: int) -> str:
    """Kişi hakkında biriktirilmiş bilgilerin yönerge metni; hata hâlinde boş.

    Hafıza bir **konfor** katmanı: olmasa da asistan çalışır, sadece kişiyi
    tanımaz. Bu yüzden buradaki her hata yutuluyor — hafıza tablosu okunamadı
    diye kullanıcının mesajının cevapsız kalması kabul edilemez.
    """
    from database import get_db
    from modules.gozlem import hafiza

    try:
        with get_db() as conn:
            return hafiza.yonergeye(conn, owner_id)
    except Exception:
        log.warning("Hafıza okunamadı (owner=%s) — yönergeye eklenmedi", owner_id)
        return ""


async def route_message(
    user_message: str,
    chat_id: str = "",
    owner_id: int = None,
    gorunen: str = None,
) -> str:
    """Ana giriş: mesajı Groq'a gönderir, modüle yönlendirir, cevabı döner.

    `owner_id` verilmezse chat_id'den çözülür — Telegram tarafı zaten kullanıcıyı
    bulup geçiriyor, ama REST/panel yolu chat_id ile geliyor. İkisi de bulunamazsa
    istek reddedilir: sahipsiz bir komutun kimin verisine yazacağı belirsizdir.

    `gorunen`: kullanıcının EKRANDA gördüğü hâli, `user_message`'tan farklıysa.
    Sesli mesajda dökümün önüne 🎤 giriyor, görselde ise `user_message`
    baştan aşağı `[Görsel analizi]: ...` bloğu — o metni sohbet geçmişine
    kullanıcının cümlesi diye basmak yanlış olurdu.
    """
    from auth import kullanici_chat_id_ile, kullanici_getir
    from database import save_message, get_recent_messages

    if owner_id is None:
        k = kullanici_chat_id_ile(chat_id)
        if not k:
            log.warning("Sahibi çözülemeyen mesaj yok sayıldı (chat_id=%s)", chat_id)
            return "⛔ Sizi tanıyamadım."
        owner_id = k["id"]
    else:
        k = kullanici_getir(owner_id)

    # Kayıt silinmiş olabilir; asistan isimsiz konuşsun, çökmesin.
    ad = (k or {}).get("ad") or "kullanıcı"
    hitap = (k or {}).get("hitap")

    try:
        history = get_recent_messages(chat_id, HISTORY_LIMIT) if chat_id else []
        parsed = await parse_message(user_message, history, ad, hitap, _hafiza(owner_id))
        response = await dispatch(parsed, owner_id)

        if chat_id:
            save_message(chat_id, "user", user_message, gorunen)
            # Asistan satırında iki metin birden: modele ham JSON, panele cevabın
            # kendisi. Tek sütun olsaydı biri diğerini bozardı.
            save_message(
                chat_id, "assistant", json.dumps(parsed, ensure_ascii=False), response
            )

        return response
    except json.JSONDecodeError:
        log.warning("Groq geçerli JSON döndürmedi")
        return "⚠️ Yanıtı işleyemedim. Mesajınızı biraz farklı ifade eder misiniz?"
    except Exception:
        log.exception("Mesaj yönlendirilemedi")
        return "⚠️ Bir aksaklık oldu, kayda geçirdim. Tekrar dener misiniz?"
