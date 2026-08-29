"""Gözlem turu: fark et, sus, gerekiyorsa konuş.

## İşin özeti

Zamanlayıcı birkaç saatte bir bu turu çalıştırıyor. Tur şunu yapıyor:

    1. Kapalı mı?              → çık
    2. Sessiz saatte mi?       → sus
    3. Günlük sınır doldu mu?  → sus
    4. Son mesajdan bu yana yeterince zaman geçti mi? → geçmediyse sus
    5. Sinyal var mı?          → yoksa sus
    6. Bu konular yakında konuşuldu mu? → konuşulduysa sus
    7. Modele sor: değer mi?   → değmezse sus
    8. Konuş.

Model çağrısı **en sonda**. Turların çoğu Groq'a hiç uğramadan bitiyor;
maliyet de gecikme de bu yüzden önemsiz.

## Neden bu kadar çok engel var

Tek gerçek tasarım riski gürültü. Çok konuşan asistan susturulur, susturulan
asistan ölür. Bir kullanıcı bir kez "bu bot çok konuşuyor" dediğinde geri
dönüşü yok — bildirimleri kapatır ve faydalı olanı da görmez.

Bu yüzden **susmak varsayılan**, konuşmak istisna. Ve sustuğu her tur da
günlüğe yazılıyor: "şu sinyalleri gördüm, şu sebeple sustum". Bu satırlar
olmadan eşikleri ayarlamanın hiçbir yolu olmazdı.
"""

import html
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz

from logging_setup import get_logger
from modules.gozlem import hafiza, sinyaller as sinyal_modulu

log = get_logger("prism.gozlem")

TZ = pytz.timezone("Europe/Istanbul")

# ── Susma bütçesi ────────────────────────────────────────────────────────────

# `gozlem.py seviye` komutunun önerdiği değer. Asıl sınır kişi başına
# `users.gozlem_sinir` sütununda; burası yalnız makul bir başlangıç.
ONERILEN_SINIR = 3

# İki kendiliğinden mesaj arasında en az bu kadar dakika olmalı. Günlük sınır
# tek başına yetmiyor: üç mesajın üçü de öğlen arka arkaya gelirse sınır
# tutulmuş olur ama kullanıcı yine bombardımana uğrar.
ASGARI_ARA_DAKIKA = 180

# Bu saatler arasında hiçbir koşulda konuşulmaz (23:00'ten 08:00'e).
SESSIZ_BASLANGIC = 23
SESSIZ_BITIS = 8

# Aynı konu (sinyal anahtarı) bu kadar gün tekrar açılmaz.
KONU_BEKLEME_GUNU = 3

# Modelin ürettiği mesajın azami uzunluğu. Kendiliğinden gelen mesaj kısa
# olmalı; uzun olursa rapor gibi durur ve okunmaz.
AZAMI_MESAJ = 400


YONERGE = """\
Sen PRISM'sin — {ad} kişisinin kişisel asistanı. Ona "{hitap}" diye hitap edersin.
Üslubun Iron Man'deki JARVIS gibi: kusursuz nezaket, sakin yetkinlik, arada
kuru bir espri. **Daima SİZ** diye hitap edersin, istisnasız.

Şu an: {now}
{hafiza}
## DURUM
Bu bir sohbet değil. Kullanıcı sana bir şey sormadı, senin mesajını beklemiyor.
Sen kendi başına verilere baktın ve aşağıdakileri fark ettin. Vereceğin tek
karar şu: **bunlardan biri, kullanıcının telefonunu titretmeye değer mi?**

## FARK ETTİKLERİN
{sinyaller}

## SİNYAL TÜRLERİ
Her sinyalin başında türü yazıyor:

- **[DURUM]** — kullanıcının taraf olduğu bir hâl (bütçesi, görevleri, hava).
  Burada varsayılan **susmaktır**: bunları kendisi de görebilir.
- **[ARIZA]** — bozulmuş ve düzeltilebilir bir şey. Burada varsayılan
  **söylemektir**. Arızanın tanımı gereği kullanıcının haberi yoktur; haberi
  olsaydı çoktan düzeltmişti. Bunu ondan önce fark etmek senin işin.

## KURALLAR
1. **Susmak, DURUM sinyallerinde varsayılan cevaptır** — ama gerekçesiz değil.
   "Kullanıcı zaten biliyor **olabilir**" susmak için yeterli DEĞİL; bildiğini
   düşünmek için somut bir sebep olmalı. Söylemek için: bilmediği bir şey,
   kaçırmak üzere olduğu bir fırsat, ya da düzeltebileceği bir aksaklık.
2. En fazla **BİR** tanesini seç. Liste yapma, birkaçını birleştirme.
   Elinde hem ARIZA hem DURUM varsa ARIZA'yı seç.
3. **Yalnız yukarıdaki kanıtlarda yazan bilgiyi kullan.** Sayı, tarih, isim,
   tutar UYDURMA. Orada yazmayan hiçbir şeyi söyleme.
4. Kısa yaz: en fazla üç cümle. Bu bir hatırlatma, rapor değil.
5. Düz metin yaz. HTML etiketi, markdown, emoji kullanma.
6. Mümkünse bir şey öner — sadece durumu bildirmek yarım iştir.
7. Sitem etme, azarlama, telaşlandırma. Kötü haberi sakin ver.

## ÇIKTI (sadece JSON)
Söylenecekse:
{{"soyle": true, "anahtar": "<yukarıdaki anahtarlardan biri>", "mesaj": "...", "sebep": "kısa gerekçe"}}

Söylenmeyecekse:
{{"soyle": false, "sebep": "neden değmediği"}}
"""


# ── Günlük ───────────────────────────────────────────────────────────────────

def _gunluge_yaz(
    conn,
    owner_id: int,
    karar: str,
    sebep: str,
    anahtar: str = None,
    mesaj: str = None,
    gorulen: List[str] = None,
):
    conn.execute(
        "INSERT INTO gozlem_gunlugu (owner_id, karar, anahtar, mesaj, sebep, sinyaller, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (owner_id, karar, anahtar, mesaj, sebep,
         json.dumps(gorulen or [], ensure_ascii=False), datetime.now(TZ).isoformat()),
    )


def bugunku_mesaj_sayisi(conn, owner_id: int, now: datetime) -> int:
    gun_basi = now.replace(hour=0, minute=0, second=0, microsecond=0)
    row = conn.execute(
        "SELECT COUNT(*) c FROM gozlem_gunlugu "
        "WHERE owner_id = ? AND karar = 'konustu' AND created_at >= ?",
        (owner_id, gun_basi.isoformat()),
    ).fetchone()
    return row["c"]


def son_mesaj_zamani(conn, owner_id: int) -> Optional[datetime]:
    row = conn.execute(
        "SELECT created_at FROM gozlem_gunlugu "
        "WHERE owner_id = ? AND karar = 'konustu' ORDER BY id DESC LIMIT 1",
        (owner_id,),
    ).fetchone()
    if not row:
        return None
    try:
        return datetime.fromisoformat(row["created_at"])
    except (ValueError, TypeError):
        return None


def yakinda_konusulan(conn, owner_id: int, now: datetime) -> set:
    """Son `KONU_BEKLEME_GUNU` gün içinde konuşulmuş sinyal anahtarları."""
    sinir = (now - timedelta(days=KONU_BEKLEME_GUNU)).isoformat()
    return {
        r["anahtar"] for r in conn.execute(
            "SELECT DISTINCT anahtar FROM gozlem_gunlugu "
            "WHERE owner_id = ? AND karar = 'konustu' AND anahtar IS NOT NULL "
            "AND created_at >= ?",
            (owner_id, sinir),
        )
    }


def sessiz_saat(now: datetime) -> bool:
    return now.hour >= SESSIZ_BASLANGIC or now.hour < SESSIZ_BITIS


# ── Tur ──────────────────────────────────────────────────────────────────────

def _sonuc(karar: str, sebep: str, **ek) -> Dict[str, Any]:
    return {"karar": karar, "sebep": sebep, **ek}


async def tur(owner_id: int, kuru: bool = False, now: datetime = None) -> Dict[str, Any]:
    """Bir gözlem turu çalıştırır.

    `kuru=True` iken hiçbir şey gönderilmez ve günlüğe yazılmaz — model yine de
    çağrılır, yani "ne derdi" görülebilir. `gozlem.py tur` bunu kullanıyor;
    kuru turun bütçeyi harcaması ya da konu bekleme sayacını başlatması
    denemeyi anlamsız kılardı.

    Dönen sözlük CLI tarafından ekrana basılıyor, zamanlayıcı ise yok sayıyor.
    """
    from auth import kullanici_getir
    from database import get_db
    from groq_client import complete_json

    now = now or datetime.now(TZ)

    kullanici = kullanici_getir(owner_id)
    if not kullanici:
        return _sonuc("sustu", "kullanıcı bulunamadı")

    sinir = kullanici.get("gozlem_sinir") or 0
    if sinir <= 0 and not kuru:
        # Günlüğe yazılmıyor: kapalı bir kullanıcı için her tur satır açmak
        # günlüğü okunmaz hâle getirir. Kuru çalıştırmada devam ediliyor ki
        # açmadan önce ne olacağı denenebilsin.
        return _sonuc("sustu", "kapalı (gozlem_sinir = 0)")

    # Bağlantı `topla()` içindeki hava durumu çağrısı boyunca (birkaç saniye)
    # açık kalıyor. Sorun değil: bu noktaya kadar hiçbir yazma yok ve WAL
    # modunda okuyucu, yazıcıyı bloke etmiyor.
    with get_db() as conn:
        # Bütçe engelleri önce toplanıp sonra uygulanıyor. Kuru çalıştırma
        # hiçbirine takılmıyor — gece yarısı ya da sınır dolmuşken de "ne
        # derdi" görülebilmeli — ama engeller `uyari` olarak raporlanıyor,
        # yani denemenin gerçekte gönderileceği anlamına gelmediği görünüyor.
        engeller: List[str] = []

        if sessiz_saat(now):
            engeller.append("sessiz saat")

        adet = bugunku_mesaj_sayisi(conn, owner_id, now)
        if sinir and adet >= sinir:
            engeller.append(f"günlük sınır dolu ({adet}/{sinir})")

        son = son_mesaj_zamani(conn, owner_id)
        if son:
            gecen = (now - son).total_seconds() / 60
            if gecen < ASGARI_ARA_DAKIKA:
                engeller.append(
                    f"son mesajın üstünden {int(gecen)} dk geçti (asgari {ASGARI_ARA_DAKIKA})"
                )

        if engeller and not kuru:
            _gunluge_yaz(conn, owner_id, "sustu", engeller[0])
            return _sonuc("sustu", engeller[0])

        bulunan = await sinyal_modulu.topla(conn, owner_id, kullanici, now)
        gorulen = [s["anahtar"] for s in bulunan]

        if not bulunan:
            if not kuru:
                _gunluge_yaz(conn, owner_id, "sustu", "sinyal yok")
            return _sonuc("sustu", "sinyal yok", sinyaller=[])

        beklemede = yakinda_konusulan(conn, owner_id, now)
        aday = [s for s in bulunan if s["anahtar"] not in beklemede]

        if not aday:
            sebep = f"görülen {len(bulunan)} sinyalin hepsi son {KONU_BEKLEME_GUNU} günde konuşuldu"
            if not kuru:
                _gunluge_yaz(conn, owner_id, "sustu", sebep, gorulen=gorulen)
            return _sonuc("sustu", sebep, sinyaller=bulunan)

        hafiza_metni = hafiza.yonergeye(conn, owner_id)

    from ai_router import hitap_ifadesi

    # Gün adı Türkçe yazılıyor: `strftime("%A")` sunucunun yerel ayarına göre
    # "Saturday" üretiyordu ve baştan sona Türkçe bir yönergenin ortasında
    # duran İngilizce kelime, modelin dil tutarlılığını bozan gereksiz bir
    # sinyal.
    from modules.summary.service import TURKISH_DAYS

    yonerge = YONERGE.format(
        ad=kullanici["ad"],
        hitap=hitap_ifadesi(kullanici["ad"], kullanici.get("hitap")),
        now=f"{now.strftime('%d.%m.%Y %H:%M')} ({TURKISH_DAYS[now.weekday()]})",
        hafiza=hafiza_metni,
        sinyaller="\n".join(
            f"- [{s.get('kategori', sinyal_modulu.DURUM).upper()}] "
            f"[{s['anahtar']}] {s['kanit']}"
            for s in aday
        ),
    )

    try:
        karar = await complete_json(
            [{"role": "system", "content": yonerge},
             {"role": "user", "content": "Söylenmeye değer bir şey var mı?"}],
            max_tokens=300,
            temperature=0.4,        # sabit onay metinlerinden daha serbest, sohbetten daha ölçülü
        )
    except Exception:
        log.exception("Gözlem kararı alınamadı (owner=%s)", owner_id)
        with get_db() as conn:
            if not kuru:
                _gunluge_yaz(conn, owner_id, "sustu", "model yanıt vermedi", gorulen=gorulen)
        return _sonuc("sustu", "model yanıt vermedi", sinyaller=aday)

    if not karar.get("soyle"):
        sebep = str(karar.get("sebep") or "değmez")[:200]
        with get_db() as conn:
            if not kuru:
                _gunluge_yaz(conn, owner_id, "sustu", f"model: {sebep}", gorulen=gorulen)
        return _sonuc("sustu", f"model: {sebep}", sinyaller=aday)

    mesaj = (karar.get("mesaj") or "").strip()[:AZAMI_MESAJ]
    anahtar = karar.get("anahtar")

    # Model seçtiği anahtarı uydurmuş olabilir. Anahtar tanınmazsa konu bekleme
    # sayacı yanlış yere işler ve aynı şey ertesi gün tekrar söylenir.
    gecerli = {s["anahtar"] for s in aday}
    if anahtar not in gecerli:
        anahtar = aday[0]["anahtar"]

    if not mesaj:
        with get_db() as conn:
            if not kuru:
                _gunluge_yaz(conn, owner_id, "sustu", "model boş mesaj döndü", gorulen=gorulen)
        return _sonuc("sustu", "model boş mesaj döndü", sinyaller=aday)

    if kuru:
        return _sonuc("konustu", str(karar.get("sebep") or ""),
                      anahtar=anahtar, mesaj=mesaj, sinyaller=aday,
                      gonderildi=False, uyari=" · ".join(engeller))

    from telegram_bot import sahibin_chati, send_message

    # Modelden düz metin isteniyor ama garanti değil: kaçırılmış bir "<" Telegram'da
    # 400 döndürüp mesajı komple yutar. Kaçış, bu sessiz kaybı imkânsız kılıyor.
    await send_message(f"🔹 {html.escape(mesaj)}", chat_id=sahibin_chati(owner_id))

    with get_db() as conn:
        _gunluge_yaz(conn, owner_id, "konustu", str(karar.get("sebep") or ""),
                     anahtar=anahtar, mesaj=mesaj, gorulen=gorulen)

    log.info("Gözlem mesajı gönderildi (owner=%s, konu=%s)", owner_id, anahtar)
    return _sonuc("konustu", str(karar.get("sebep") or ""),
                  anahtar=anahtar, mesaj=mesaj, sinyaller=aday, gonderildi=True)


async def herkes_icin_tur():
    """Zamanlayıcının çağırdığı iş — her kullanıcı için ayrı tur.

    Hata tek kişiyle sınırlı: birinin verisi tura takılırsa diğerininki yine
    döner (sabah özetindeki `_herkese_ozet` ile aynı gerekçe).
    """
    from auth import tum_kullanicilar

    for k in tum_kullanicilar():
        if (k.get("gozlem_sinir") or 0) <= 0:
            continue
        try:
            await tur(k["id"])
        except Exception:
            log.exception("Gözlem turu çöktü (%s)", k["ad"])


async def herkes_icin_hafiza():
    """Zamanlayıcının çağırdığı iş — konuşmalardan bilgi çıkarımı.

    Gözlem sınırından bağımsız: hafıza kendiliğinden mesaj göndermiyor, sadece
    asistanın verdiği cevapları kişiselleştiriyor. Kapalı kullanıcı için de
    birikmesi doğru.
    """
    from auth import tum_kullanicilar

    for k in tum_kullanicilar():
        try:
            await hafiza.cikar(k["id"])
        except Exception:
            log.exception("Hafıza çıkarımı çöktü (%s)", k["ad"])
