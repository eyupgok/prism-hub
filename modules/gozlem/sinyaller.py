"""Sinyal üretimi — asistanın "fark ettiği" şeyler.

## Neden burası bu kadar önemli

Kendiliğinden gelen bir mesajda uydurma bilgi, sorulunca gelen bir mesajdaki
uydurmadan çok daha zararlıdır: kullanıcı onu beklemiyordu, bağlamı yok,
doğruluğunu kontrol etmesi için bir sebebi yok. Bir kere "sen bunu uydurdun"
dedirtirse asistanın bütün kendiliğinden konuşma hakkı biter.

Bu yüzden mimarideki en katı kural şu:

    Sinyalleri KOD bulur (SQL + aritmetik, deterministik).
    Model yalnızca "bu söylenmeye değer mi ve nasıl söylenir" sorusunu cevaplar.

Yani model bir cümle kurarken elinde sadece buradan çıkan `kanit` metinleri
olur. Bir sayı uyduramaz, olmayan bir hatırlatıcıdan bahsedemez.

## Sinyalin biçimi

    {
      "anahtar": "butce_hizi:yemek",   # tekrar engelinin kimliği (aşağıya bak)
      "kanit":   "yemek bütçesinin %82'si harcandı, ayın daha %37'si geçti",
      "agirlik": 2,                    # 1 düşük · 2 orta · 3 yüksek
    }

`anahtar` **konu kimliği**: aynı anahtar birkaç gün tekrar seçilemiyor
(`service.KONU_BEKLEME_GUNU`). Bu yüzden anahtar sabit olmalı — sayıya bağlı
bir anahtar ("gecikmis_gorevler:3") sayı değişince yeni konu sanılır ve
asistan aynı şeyi her gün söylemeye başlar. Kategoriye/kayda özel anahtarlar
(`butce_hizi:yemek`, `inatci_gorev:12`) ise bilerek ayrıştırılmış: yemek
bütçesi hakkında konuşmuş olmak, ulaşım bütçesi hakkında susmayı gerektirmez.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz

from logging_setup import get_logger

log = get_logger("prism.gozlem.sinyal")

TZ = pytz.timezone("Europe/Istanbul")

# ── Eşikler ──────────────────────────────────────────────────────────────────
# Hepsi burada toplu duruyor ki asistanın "ne zaman rahatsız olacağı" tek
# yerden ayarlanabilsin. Her biri bir gözlem turunda okunuyor, sabit değil.

# Otomatik harcama yakalama bu kadar gün sustuysa telefondaki dinleyici ölmüş olabilir
SESSIZLIK_GUNU = 3
# ...ama yalnız daha önce gerçekten çalıştıysa. Hiç kurulmamış bir özellik "bozuk" değildir.
SESSIZLIK_ASGARI_GECMIS = 5

# Bütçe: harcama oranı ayın geçen oranını bu kadar puan aşarsa "hızlı gidiyorsunuz"
BUTCE_HIZ_FARKI = 20
BUTCE_HIZ_ASGARI_ORAN = 40      # ayın başında %5 harcamak "hızlı" sayılmasın

# Bir günde bu kadar görev varsa yığılma
YIGILMA_ESIGI = 4

# Vadesi bu kadar gün geçmiş ve hâlâ tamamlanmamış görevler
GECIKME_GUNU = 1
GECIKME_ESIGI = 3

# Haftalık kurma/bitirme dengesizliği
HAFTA_ASGARI_KURULAN = 5

# Tek bir görev: kaç kez ertelenirse "inatçı"
INAT_ERTELEME = 3
INAT_GECIKME_GUNU = 3
# Kaç tanesi bildirilir. Sınır olmasaydı dört unutulmuş görev, listeyi
# birbirinin neredeyse aynısı dört satırla doldurup modelin dikkatini
# gerçekten önemli olan sinyalden kaçırıyordu.
INAT_AZAMI = 2

# Günlük harcama ortalamanın bu katını aşarsa olağandışı
OLAGANDISI_KAT = 2.5
OLAGANDISI_TABAN = 500.0        # küçük tutarlarda kat hesabı anlamsız
OLAGANDISI_PENCERE_GUN = 14

# Hava: bu kodlardan itibaren yağış var (WMO). 51 = çisenti.
YAGIS_KODU = 51
SICAK_ESIK = 35
SOGUK_ESIK = 0


def _para(deger: float) -> str:
    return f"{deger:,.0f}".replace(",", ".")


def _sinyal(anahtar: str, kanit: str, agirlik: int = 2) -> Dict[str, Any]:
    return {"anahtar": anahtar, "kanit": kanit, "agirlik": agirlik}


# ── Harcama tarafı ───────────────────────────────────────────────────────────

def harcama_sessizligi(conn, owner_id: int, now: datetime) -> Optional[Dict]:
    """Banka bildiriminden gelen harcama akışı kesildi mi?

    Bu sinyal aslında bir **arıza teşhisi**: telefondaki dinleyici servisi
    sessizce ölebiliyor (süreç öldürülmesi, MIUI otomatik başlatma kısıtı,
    termal kısıtlama — CLAUDE.md'de uzun uzun yazıyor). Ölünce hiçbir uyarı
    çıkmıyor, sadece harcamalar kaydedilmiyor ve bu haftalarca fark edilmiyor.

    Asistanın bunu fark etmesi, kullanıcının fark etmesinden çok daha olası.
    """
    row = conn.execute(
        "SELECT COUNT(*) c, MAX(COALESCE(source_at, created_at)) son "
        "FROM expenses WHERE owner_id = ? AND source = 'notification'",
        (owner_id,),
    ).fetchone()

    if not row or row["c"] < SESSIZLIK_ASGARI_GECMIS or not row["son"]:
        return None

    try:
        son = datetime.fromisoformat(row["son"])
    except (ValueError, TypeError):
        return None
    if son.tzinfo is None:
        son = TZ.localize(son)

    gun = (now - son).days
    if gun < SESSIZLIK_GUNU:
        return None

    return _sinyal(
        "harcama_sessizligi",
        f"telefondan otomatik gelen son harcama kaydı {gun} gün önce; "
        f"daha önce toplam {row['c']} kayıt bu yoldan gelmişti",
        agirlik=3,
    )


def butce(conn, owner_id: int, now: datetime) -> List[Dict]:
    """Bütçe limiti aşıldı mı, yoksa aşılacak hızda mı gidiyor?

    İkisi ayrı sinyal. "Aşıldı" olan bittiği için artık yapılacak bir şey yok;
    asıl değerli olan "bu hızla gidersen ayın 20'sinde biter" uyarısı — o hâlâ
    önlenebilir bir şey. Mevcut `check_budget_alert` yalnız harcama kaydedilirken
    ve yalnız yüzdeye bakarak çalışıyor; buradaki hesap ayın ne kadarının
    geçtiğini de işin içine katıyor.
    """
    from modules.expenses import service as svc

    ay = now.strftime("%Y-%m")
    # Ayın kaçta kaçı geçti (0..1). Gün başında değil, saat hassasiyetinde.
    ay_basi = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    gelecek_ay = (ay_basi + timedelta(days=32)).replace(day=1)
    ay_orani = (now - ay_basi) / (gelecek_ay - ay_basi)

    bulunan = []
    for b in svc.get_all_budgets(conn, owner_id):
        row = conn.execute(
            "SELECT SUM(amount) t FROM expenses "
            "WHERE owner_id = ? AND expense_date LIKE ? AND category = ?",
            (owner_id, f"{ay}%", b["category"]),
        ).fetchone()
        harcanan = row["t"] or 0
        limit = b["monthly_limit"]
        if harcanan <= 0 or limit <= 0:
            continue

        oran = harcanan / limit * 100

        if oran >= 100:
            bulunan.append(_sinyal(
                f"butce_asildi:{b['category']}",
                f"{b['category']} bütçesi aşıldı: {_para(harcanan)} / {_para(limit)} TL "
                f"(%{oran:.0f}), ayın %{ay_orani * 100:.0f}'i geçti",
                agirlik=3,
            ))
        elif oran >= BUTCE_HIZ_ASGARI_ORAN and oran > ay_orani * 100 + BUTCE_HIZ_FARKI:
            bulunan.append(_sinyal(
                f"butce_hizi:{b['category']}",
                f"{b['category']} bütçesinin %{oran:.0f}'i harcandı "
                f"({_para(harcanan)} / {_para(limit)} TL) ama ayın daha "
                f"%{ay_orani * 100:.0f}'i geçti",
                agirlik=2,
            ))

    return bulunan


def olagandisi_harcama(conn, owner_id: int, now: datetime) -> Optional[Dict]:
    """Bugünkü harcama son iki haftanın günlük ortalamasının çok üstünde mi?

    Bütçeden bağımsız çalışıyor: limit koymamış bir kategoride de olağandışı
    bir gün fark edilebilsin diye.
    """
    bugun = now.strftime("%Y-%m-%d")
    baslangic = (now - timedelta(days=OLAGANDISI_PENCERE_GUN)).strftime("%Y-%m-%d")

    row = conn.execute(
        "SELECT SUM(amount) t FROM expenses WHERE owner_id = ? AND expense_date = ?",
        (owner_id, bugun),
    ).fetchone()
    bugunku = row["t"] or 0
    if bugunku < OLAGANDISI_TABAN:
        return None

    row = conn.execute(
        "SELECT SUM(amount) t FROM expenses "
        "WHERE owner_id = ? AND expense_date >= ? AND expense_date < ?",
        (owner_id, baslangic, bugun),
    ).fetchone()
    onceki = row["t"] or 0
    if onceki <= 0:
        return None

    ortalama = onceki / OLAGANDISI_PENCERE_GUN
    if bugunku < ortalama * OLAGANDISI_KAT:
        return None

    return _sinyal(
        f"olagandisi_harcama:{bugun}",
        f"bugün {_para(bugunku)} TL harcandı; son {OLAGANDISI_PENCERE_GUN} günün "
        f"günlük ortalaması {_para(ortalama)} TL",
        agirlik=2,
    )


# ── Görev tarafı ─────────────────────────────────────────────────────────────

def gorev_yigilmasi(conn, owner_id: int, now: datetime) -> List[Dict]:
    """Önümüzdeki hafta içinde bir güne yığılmış görevler.

    Anahtar tarihe bağlı: 5 Eylül'ün yığılması hakkında konuşmuş olmak,
    12 Eylül'ün yığılması hakkında susmayı gerektirmiyor.
    """
    from modules.reminders import service as rem

    gunler: Dict[str, List[str]] = {}
    sinir = now + timedelta(days=7)

    for r in rem.list_reminders(conn, owner_id, include_completed=False):
        due = rem.parse_dt(r["due_datetime"])
        if now <= due <= sinir:
            gunler.setdefault(due.strftime("%Y-%m-%d"), []).append(r["title"])

    bulunan = []
    for gun, basliklar in sorted(gunler.items()):
        if len(basliklar) < YIGILMA_ESIGI:
            continue
        # Komşu günlerin yükü — "o gün yoğun" demek ancak diğerleri boşsa anlamlı
        tarih = datetime.strptime(gun, "%Y-%m-%d")
        komsu = sum(
            len(gunler.get((tarih + timedelta(days=k)).strftime("%Y-%m-%d"), []))
            for k in (-1, 1)
        )
        bulunan.append(_sinyal(
            f"gorev_yigilmasi:{gun}",
            f"{gun} gününde {len(basliklar)} görev var "
            f"({', '.join(basliklar[:4])}); komşu iki günde toplam {komsu} görev",
            agirlik=2,
        ))
    return bulunan


def gecikmis_gorevler(conn, owner_id: int, now: datetime) -> Optional[Dict]:
    """Vadesi geçmiş ve hâlâ tamamlanmamış görev yığını.

    Anahtar sayıdan bağımsız (`gecikmis_gorevler`) — sayı her gün değişiyor,
    anahtara koysaydık asistan her gün "yeni konu" sanıp aynı şeyi tekrar
    söylerdi.
    """
    from modules.reminders import service as rem

    sinir = now - timedelta(days=GECIKME_GUNU)
    gecikmis = [
        r for r in rem.list_reminders(conn, owner_id, include_completed=False)
        if rem.parse_dt(r["due_datetime"]) < sinir
        and r.get("recurrence", "none") == "none"      # tekrarlayanlar zaten öteleniyor
    ]
    if len(gecikmis) < GECIKME_ESIGI:
        return None

    en_eski = min(rem.parse_dt(r["due_datetime"]) for r in gecikmis)
    return _sinyal(
        "gecikmis_gorevler",
        f"{len(gecikmis)} görevin vadesi geçmiş ve tamamlanmamış; en eskisi "
        f"{(now - en_eski).days} gün önceydi "
        f"({', '.join(r['title'] for r in gecikmis[:3])})",
        agirlik=2,
    )


def inatci_gorev(conn, owner_id: int, now: datetime) -> List[Dict]:
    """Tek tek göze batan görevler: çok ertelenmiş ya da uzun süredir duran.

    Bunlar genelde "aslında yapılmayacak" işler. Asistanın bunu söylemesi
    (silmeyi ya da tarihi düzeltmeyi önermesi) gerçekten faydalı.
    """
    from modules.reminders import service as rem

    bulunan = []
    for r in rem.list_reminders(conn, owner_id, include_completed=False):
        if r.get("recurrence", "none") != "none":
            continue
        due = rem.parse_dt(r["due_datetime"])
        gecikme = (now - due).days
        erteleme = r.get("snooze_count") or 0

        if erteleme >= INAT_ERTELEME:
            bulunan.append((erteleme, gecikme, _sinyal(
                f"inatci_gorev:{r['id']}",
                f"'{r['title']}' görevi {erteleme} kez ertelendi",
                agirlik=2,
            )))
        elif gecikme >= INAT_GECIKME_GUNU:
            bulunan.append((erteleme, gecikme, _sinyal(
                f"inatci_gorev:{r['id']}",
                f"'{r['title']}' görevinin vadesi {gecikme} gün önceydi, "
                f"hâlâ tamamlanmadı",
                agirlik=2,
            )))

    # En göze batanlar önce: çok ertelenen, sonra en uzun süredir duran.
    bulunan.sort(key=lambda x: (-x[0], -x[1]))
    return [s for _, _, s in bulunan[:INAT_AZAMI]]


def tamamlama_orani(conn, owner_id: int, now: datetime) -> Optional[Dict]:
    """Son yedi günde kurulan görevler ile bitirilenlerin dengesi."""
    from modules.reminders import service as rem

    hafta_once = now - timedelta(days=7)

    row = conn.execute(
        "SELECT COUNT(*) c FROM reminders WHERE owner_id = ? AND created_at >= ?",
        (owner_id, hafta_once.isoformat()),
    ).fetchone()
    kurulan = row["c"]
    if kurulan < HAFTA_ASGARI_KURULAN:
        return None

    biten = rem.count_completed_between(conn, owner_id, hafta_once, now)
    if biten > kurulan / 3:
        return None

    return _sinyal(
        "tamamlama_orani",
        f"son 7 günde {kurulan} görev kuruldu, {biten} tanesi tamamlandı",
        agirlik=1,
    )


# ── Dış dünya ────────────────────────────────────────────────────────────────

async def hava_cakismasi(conn, owner_id: int, user: Dict, now: datetime) -> List[Dict]:
    """Önümüzdeki 24 saatteki görevlerden birinin saatinde kötü hava var mı?

    Dışarıya çıkılacak mı bilmiyoruz — hatırlatıcının metninde yazmıyor. Bu
    yüzden kanıt "o saatte yağmur bekleniyor" demekle yetiniyor, "şemsiye alın"
    demiyor; yorumu modele bırakıyoruz, o da görev başlığına bakıp karar veriyor.

    Hava servisi cevap vermezse sessizce boş dönüyor: gözlem turunun tamamı
    dış bir API'ye bağlı kalmamalı.
    """
    from modules.reminders import service as rem
    from modules.weather import service as hava

    yakin = [
        r for r in rem.list_reminders(conn, owner_id, include_completed=False)
        if now <= rem.parse_dt(r["due_datetime"]) <= now + timedelta(hours=24)
    ]
    if not yakin:
        return []

    try:
        tahmin = await hava.saatlik_tahmin(user)
    except Exception as e:
        log.warning("Saatlik tahmin alınamadı (%s) — hava sinyali atlandı", type(e).__name__)
        return []

    bulunan = []
    for r in yakin:
        due = rem.parse_dt(r["due_datetime"])
        saat = tahmin.get(due.strftime("%Y-%m-%dT%H:00"))
        if not saat:
            continue

        kod, sicaklik = saat["kod"], saat["sicaklik"]
        if kod >= YAGIS_KODU:
            durum = hava.WMO_DESCRIPTIONS.get(kod, "kötü hava").lower()
        elif sicaklik >= SICAK_ESIK:
            durum = f"{sicaklik}°C sıcaklık"
        elif sicaklik <= SOGUK_ESIK:
            durum = f"{sicaklik}°C soğuk"
        else:
            continue

        bulunan.append(_sinyal(
            f"hava_cakismasi:{r['id']}",
            f"'{r['title']}' görevi {due.strftime('%d.%m %H:%M')} saatinde ve "
            f"o saatte {durum} bekleniyor",
            agirlik=2,
        ))
    return bulunan


def ev_halki(conn, owner_id: int, now: datetime) -> List[Dict]:
    """Evdeki diğer kişinin yaklaşan önemli görevleri.

    İkiniz zaten birbirinizin verisini görüyorsunuz (bkz. CLAUDE.md "İki
    Kullanıcı"), yani burada yeni bir gizlilik kararı verilmiyor — sadece
    zaten görünen bir şey hatırlatılıyor. Ağırlık en düşük seviyede: bu
    "bilgi", "uyarı" değil.
    """
    from modules.reminders import service as rem

    # Kullanıcı listesi `auth.tum_kullanicilar()` ile değil, elimizdeki
    # bağlantıdan okunuyor: o fonksiyon kendi bağlantısını açıyor ve aynı
    # işlemin içindeki değişiklikleri göremiyor.
    digerleri = conn.execute(
        "SELECT id, ad FROM users WHERE id != ? ORDER BY id", (owner_id,)
    ).fetchall()

    bulunan = []
    for k in digerleri:
        for r in rem.list_reminders(conn, k["id"], include_completed=False):
            due = rem.parse_dt(r["due_datetime"])
            if not (now <= due <= now + timedelta(hours=24)):
                continue
            if r["priority"] > 2:          # yalnız Kritik ve Önemli
                continue
            bulunan.append(_sinyal(
                f"ev_halki:{r['id']}",
                f"{k['ad']} için {due.strftime('%d.%m %H:%M')} saatinde "
                f"'{r['title']}' görevi var ({rem.PRIORITY_NAMES.get(r['priority'])})",
                agirlik=1,
            ))
    return bulunan


# ── Toplayıcı ────────────────────────────────────────────────────────────────

async def topla(conn, owner_id: int, user: Dict, now: datetime = None) -> List[Dict]:
    """Bu kişi için şu anda geçerli bütün sinyaller, ağırlığa göre sıralı.

    Hiçbir yan etkisi yok ve hiçbir şey göndermiyor — `gozlem.py sinyal`
    komutu bunu doğrudan çağırıp ekrana basıyor. Bir sinyalin hesabı çökerse
    tur komple düşmesin diye her üretici ayrı ayrı korunuyor.
    """
    now = now or datetime.now(TZ)
    sinyaller: List[Dict] = []

    tekil = (harcama_sessizligi, olagandisi_harcama, gecikmis_gorevler, tamamlama_orani)
    coklu = (butce, gorev_yigilmasi, inatci_gorev, ev_halki)

    for uretici in tekil:
        try:
            s = uretici(conn, owner_id, now)
            if s:
                sinyaller.append(s)
        except Exception:
            log.exception("Sinyal üretilemedi: %s", uretici.__name__)

    for uretici in coklu:
        try:
            sinyaller.extend(uretici(conn, owner_id, now) or [])
        except Exception:
            log.exception("Sinyal üretilemedi: %s", uretici.__name__)

    try:
        sinyaller.extend(await hava_cakismasi(conn, owner_id, user, now) or [])
    except Exception:
        log.exception("Sinyal üretilemedi: hava_cakismasi")

    return sorted(sinyaller, key=lambda s: -s["agirlik"])
