"""Takip — kullanıcının ağzından çıkanı sonradan sormak.

## Neden ayrı bir şey

"Yarın dişçiye gidiyorum" cümlesi hiçbir tabloya girmiyor:

- **Hatırlatıcı değil** — kullanıcı kurmadı, kurmak da istemedi.
- **Not değil** — bir şey kaydetmek istemiyor.
- **Hafıza değil** — kalıcı bir özellik değil, tek seferlik bir olay;
  hafızaya yazılsa bir hafta sonra orada yalan olarak dururdu.

Ama bir uşağı asistandan ayıran şey tam da ertesi akşam "dişçi nasıl geçti?"
diye sorabilmesi. Kaydedilecek bir veri yok; sorulacak bir soru var.

## Nasıl çalışıyor

1. Hafıza çıkarımıyla aynı turda konuşmalar taranıyor (ayrı model çağrısı,
   ayrı damga) ve sorulmaya değer olaylar `takipler` tablosuna yazılıyor.
2. Vakti gelince `sinyaller.bekleyen_takip()` bunu bir sinyal olarak
   üretiyor — yani soru da **aynı susma bütçesinden** geçiyor. Ayrı bir
   kanal açılsaydı günde 3 mesaj sınırı delinmiş olurdu.
3. Sorulduğunda işaretleniyor, bir daha sorulmuyor.

⚠️ Bayatlayan takip düşürülüyor (`TAKIP_BAYATLAMA_GUNU`). Geç kalmış soru
sorulmamış sorudan kötü: "geçen hafta dişçi nasıl geçti?" ilgi değil
dalgınlık gösterir.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz

from logging_setup import get_logger
from modules.gozlem.models import AZAMI_ACIK_TAKIP, TAKIP_BAYATLAMA_GUNU

log = get_logger("prism.gozlem.takip")

TZ = pytz.timezone("Europe/Istanbul")

DAMGA = "son_takip_conv_id"

# Çıkarım turunda modele verilecek azami konuşma satırı ve alınacak azami takip
CIKARIM_SATIR_SINIRI = 60
TUR_BASINA_AZAMI = 3


CIKARIM_YONERGESI = """\
Bir kişisel asistanın "sonradan sor" defterisin. Aşağıdaki konuşma dökümünde
{ad} kişisinin ağzından çıkan, **sonradan sorulmaya değer** olayları bul.

Şu an: {now}

## SATIRLARIN ZAMANI — ÖNCE BUNU OKU
Dökümdeki her satır `[gg.aa ss:dd]` ile başlıyor: o cümlenin SÖYLENDİĞİ an.
"yarın", "cuma", "bu hafta sonu" gibi sözler **şu ana göre değil, o satırın
kendi damgasına göre** çözülür.

    [08.08 21:47] {ad}: Yarın saat 4 randevum var
    → olay 09.08'de. Şu an {now} olduğuna göre çoktan geçmiş, ATLA.

Hesapladığın olay zamanı şu andan ÖNCEYSE o olayı yazma; sorulacak vakti
geçmiştir ve geç kalmış soru sorulmamış sorudan kötüdür.

## ZATEN BEKLEYENLER
{mevcut}

## NEYİ YAZARSIN
Kullanıcının bahsettiği, yaşanıp bitecek ve **sonucu merak edilir** olaylar:
- "Yarın dişçiye gidiyorum"      → sorulur: nasıl geçti
- "Cuma sunum yapacağım"         → sorulur: nasıl geçti
- "Bu hafta sonu taşınıyoruz"    → sorulur: hallolabildi mi
- "Annem hastanede"              → sorulur: durumu nasıl

## NEYİ ASLA YAZMAZSIN
- **Adı konmamış olaylar.** Kullanıcı neyin ne olduğunu söylemediyse takip
  ALMA. "Yarın randevum var" → hangi randevu belli değil, ATLA.
  "Yarın dişçi randevum var" → alınır. Eksiği kendin tamamlama; elinde
  olmayanı uydurmaktansa hiç sormamak doğrudur.
- Sonucu olmayan sıradan işler: "markete gideceğim", "duş alacağım".
- Kullanıcının kendisinin sormadığı, senin merak ettiğin şeyler.
- Zaten bekleyenler listesindekiler ya da onların başka kelimelerle yazılmışı.
- Geçmişte kalmış, çoktan olmuş bitmiş olaylar.
- Asistanın kendi cümlelerinden çıkarılan şeyler. Yalnız kullanıcının
  söyledikleri sayılır.

## SORULACAK ZAMAN
`sorulacak_at` olay BİTTİKTEN sonraki ilk uygun an olmalı — genelde aynı
günün akşamı (19:00) ya da ertesi sabah. Olayın saati belirsizse o günün
19:00'unu al. Biçim: "YYYY-MM-DDTHH:MM"

## KONU VE SORU
`konu` iki üç kelimelik bir etiket ve olayı TEK BAŞINA tanıtmalı — aylar
sonra o satırı okuyan biri neyin sorulduğunu anlamalı. `soru` da konuyu
adıyla anmalı, yoksa kullanıcı hangi olaydan bahsedildiğini bilemez.

Kötü:  konu: "randevu"          soru: "Randevu nasıl geçti?"
Kötü:  konu: "toplantı"         soru: "Toplantı nasıldı?"
İyi:   konu: "dişçi randevusu"  soru: "Dişçi nasıl geçti?"
İyi:   konu: "bitirme sunumu"   soru: "Sunumunuz nasıl geçti?"

Etiketi kullanıcının kendi kelimeleriyle kur. Yeterince belirgin bir etiket
kuramıyorsan o olayı hiç yazma.

## ÇIKTI
Sadece JSON:
{{"takipler": [{{"konu": "...", "soru": "...", "sorulacak_at": "YYYY-MM-DDTHH:MM"}}]}}

Sorulmaya değer bir şey yoksa: {{"takipler": []}}
**Boş dönmek olağan ve doğru cevaptır.** Konuşmaların çoğunda böyle bir olay
geçmez. Bir şey bulmak için zorlama — gereksiz soru soran asistan yorucudur.
"""


# ── Okuma / yazma ────────────────────────────────────────────────────────────

def acik_takipler(
    conn, owner_id: int, now: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Henüz sorulmamış, henüz bayatlamamış takipler.

    ⚠️ `now` enjekte edilebilir olmak ZORUNDA: bayatlama eşiği buradan
    hesaplanıyor ve `vakti_gelenler()` kendi `now`'ıyla süzüyor. İkisi ayrı
    saat kullanırsa fonksiyon yalnız gerçek saat testin varsaydığı ana
    yakınken doğru cevap verir — yani test takvime bağlı hâle gelir.
    """
    now = now or datetime.now(TZ)
    esik = (now - timedelta(days=TAKIP_BAYATLAMA_GUNU)).isoformat()
    return [dict(r) for r in conn.execute(
        "SELECT * FROM takipler WHERE owner_id = ? AND soruldu_at IS NULL "
        "AND sorulacak_at >= ? ORDER BY sorulacak_at ASC",
        (owner_id, esik),
    ).fetchall()]


def vakti_gelenler(conn, owner_id: int, now: datetime) -> List[Dict[str, Any]]:
    """Sorulma vakti gelmiş ama henüz bayatlamamış takipler."""
    return [
        t for t in acik_takipler(conn, owner_id, now)
        if datetime.fromisoformat(t["sorulacak_at"]) <= now
    ]


def ekle(
    conn,
    owner_id: int,
    konu: str,
    soru: str,
    sorulacak_at: str,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Takip ekler. Aynı konu zaten varsa ya da sınır dolduysa None döner."""
    konu, soru = (konu or "").strip(), (soru or "").strip()
    if not konu or not soru:
        return None

    try:
        an = datetime.fromisoformat(sorulacak_at)
    except (ValueError, TypeError):
        return None
    if an.tzinfo is None:
        an = TZ.localize(an)

    # Sorulmuş takipler de sayılıyor, sadece açık olanlar değil: aynı soruyu
    # iki gün arayla ikinci kez sormak dalgınlık göstergesi. Bedeli, bir
    # etiketin `temizle()` onu düşürene kadar (30 gün) kilitli kalması —
    # yani düzenli tekrar eden bir olay ("aylık kontrol") ikinci kez
    # alınamaz. Yanlış bir etiket bu yüzden `takip-unut` ile silinmeli.
    if conn.execute(
        "SELECT 1 FROM takipler WHERE owner_id = ? AND konu = ?", (owner_id, konu)
    ).fetchone():
        return None

    if len(acik_takipler(conn, owner_id, now)) >= AZAMI_ACIK_TAKIP:
        log.info("Takip sınırı dolu (owner=%s), '%s' alınmadı", owner_id, konu)
        return None

    cursor = conn.execute(
        "INSERT INTO takipler (owner_id, konu, soru, sorulacak_at, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (owner_id, konu, soru, an.isoformat(), datetime.now(TZ).isoformat()),
    )
    return dict(conn.execute("SELECT * FROM takipler WHERE id = ?", (cursor.lastrowid,)).fetchone())


def soruldu(conn, takip_id: int):
    conn.execute(
        "UPDATE takipler SET soruldu_at = ? WHERE id = ?",
        (datetime.now(TZ).isoformat(), takip_id),
    )


def unut(conn, takip_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM takipler WHERE id = ?", (takip_id,)).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM takipler WHERE id = ?", (takip_id,))
    return dict(row)


def temizle(conn, now: Optional[datetime] = None) -> int:
    """Bayatlamış (vakti geçmiş ama sorulmamış) ve sorulmuş eski takipleri siler."""
    now = now or datetime.now(TZ)
    bayat = (now - timedelta(days=TAKIP_BAYATLAMA_GUNU)).isoformat()
    eski_soru = (now - timedelta(days=30)).isoformat()
    silinen = conn.execute(
        "DELETE FROM takipler WHERE (soruldu_at IS NULL AND sorulacak_at < ?) "
        "OR (soruldu_at IS NOT NULL AND soruldu_at < ?)",
        (bayat, eski_soru),
    ).rowcount
    return silinen


# ── Çıkarım ──────────────────────────────────────────────────────────────────

async def cikar(owner_id: int) -> List[str]:
    """Yeni konuşmalardan takip çıkarır; eklenen konuları döner.

    Hafıza çıkarımıyla aynı zamanlayıcı işinden çağrılıyor ama ayrı bir model
    çağrısı ve ayrı bir damga kullanıyor. Tek bir yönergeye sıkıştırılabilirdi;
    ayrı tutulmasının sebebi kuralların gerçekten farklı olması — biri kalıcı
    özellik arıyor, diğeri bitecek bir olay. Aynı yönergede ikisi de zayıflıyor.
    """
    from database import get_db
    from groq_client import complete_json
    from modules.gozlem import konusma

    now = datetime.now(TZ)

    with get_db() as conn:
        kullanici = conn.execute("SELECT ad FROM users WHERE id = ?", (owner_id,)).fetchone()
        if not kullanici:
            return []
        ad = kullanici["ad"]

        son_id = konusma.damga_oku(conn, owner_id, DAMGA)
        dokum, en_son = konusma.yeni_dokum(conn, owner_id, son_id, CIKARIM_SATIR_SINIRI)
        if en_son is None:
            return []
        mevcut = acik_takipler(conn, owner_id)

    if not dokum.strip():
        with get_db() as conn:
            konusma.damga_yaz(conn, owner_id, DAMGA, en_son)
        return []

    yonerge = CIKARIM_YONERGESI.format(
        ad=ad,
        now=now.strftime("%Y-%m-%d %H:%M"),
        mevcut="\n".join(f"- {t['konu']}" for t in mevcut) or "(hiçbiri)",
    )

    eklenen: List[str] = []
    try:
        sonuc = await complete_json(
            [{"role": "system", "content": yonerge},
             {"role": "user", "content": dokum}],
            max_tokens=900,          # akıl yürütme payı (bkz. groq_client)
            temperature=0.2,
        )
        adaylar = sonuc.get("takipler") or []
    except Exception:
        log.exception("Takip çıkarımı başarısız (owner=%s)", owner_id)
        adaylar = []

    with get_db() as conn:
        for aday in adaylar[:TUR_BASINA_AZAMI]:
            if not isinstance(aday, dict):
                continue
            yeni = ekle(
                conn, owner_id,
                aday.get("konu", ""),
                aday.get("soru", ""),
                aday.get("sorulacak_at", ""),
            )
            if yeni:
                eklenen.append(yeni["konu"])
        konusma.damga_yaz(conn, owner_id, DAMGA, en_son)
        temizle(conn)

    if eklenen:
        log.info("%d takip alındı (owner=%s)", len(eklenen), owner_id)
    return eklenen
