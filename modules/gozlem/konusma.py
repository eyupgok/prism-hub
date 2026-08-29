"""Konuşma dökümü okuma — hafıza ve takip çıkarımlarının ortak zemini.

İkisi de aynı işi yapıyor: bir kişinin yeni konuşma satırlarını bul, modele
verilebilecek düz metne çevir. Ayrı ayrı yazılsalardı iki farklı "asistan
satırı nasıl okunur" kuralı doğardı ve biri değiştiğinde diğeri sessizce
eskirdi.

`conversations` tablosunda `owner_id` yok (bilerek — bkz. `database.py`);
ayrım `chat_id`'de ve bir kişinin İKİ kanalı olabiliyor: Telegram sohbeti ve
web panelindeki sohbet sayfası (`panel:<kullanıcı id>`).
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple


def kanallar(conn, owner_id: int) -> List[str]:
    """Kişinin yazışmalarının geçtiği chat_id'ler: panel + Telegram."""
    row = conn.execute("SELECT telegram_chat_id FROM users WHERE id = ?", (owner_id,)).fetchone()
    liste = [f"panel:{owner_id}"]
    if row and row["telegram_chat_id"]:
        liste.append(str(row["telegram_chat_id"]))
    return liste


def _damga(ham: str) -> str:
    """`created_at` → "[gg.aa ss:dd]". Okunamazsa boş döner, satır yine yazılır."""
    try:
        return datetime.fromisoformat(ham).strftime("[%d.%m %H:%M] ")
    except (ValueError, TypeError):
        return ""


def dokum(satirlar: List[Dict], ad: str) -> str:
    """Konuşma satırlarını modele verilecek düz metne çevirir.

    Asistan satırları ham JSON olarak saklanıyor. Komut JSON'ları atlanıyor —
    içlerinde çıkarılacak bir şey yok, sadece gürültü. Sohbet yanıtları metin
    olarak alınıyor, çünkü soruyu görmeden cevabı anlamak mümkün değil:
    "Nerelisiniz?" olmadan "Elazığ" hiçbir şey ifade etmiyor.

    ⚠️ **Her satırın başında zaman damgası var ve şart.** Damgasız dökümde
    "yarın dişçiye gidiyorum" cümlesinin ne zaman söylendiği belli olmuyor;
    model onu okuduğu ana göre çözüyor ve üç hafta önce olmuş bitmiş bir olay
    için yarına soru kuruyor (gerçekten oldu). Damga olmadan yönergedeki
    "geçmişte kalmış olayları yazma" kuralı da uygulanamaz — model neyin
    geçmişte kaldığını göremez. Bu, katmanın temel kuralının gereği: olguyu
    kod verir, model yalnız ifadeyi kurar.
    """
    cikti = []
    for r in satirlar:
        an = _damga(r.get("created_at"))
        if r["role"] == "user":
            cikti.append(f"{an}{ad}: {r['content']}")
            continue
        try:
            veri = json.loads(r["content"])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(veri, dict) and veri.get("module") == "chat":
            mesaj = (veri.get("params") or {}).get("message", "")
            if mesaj:
                cikti.append(f"{an}PRISM: {mesaj}")
    return "\n".join(cikti)


def yeni_dokum(
    conn, owner_id: int, son_id: int, sinir: int
) -> Tuple[str, Optional[int]]:
    """`son_id`'den sonraki konuşma satırlarının dökümü + son satırın numarası.

    Yeni satır yoksa `("", None)` döner — çağıran taraf o zaman modele hiç
    gitmiyor. Damga (ikinci değer) satırlar VARSA doluyor: döküm boş çıksa
    bile (hepsi komut JSON'uymuş) damga ilerlemeli, yoksa aynı satırlar her
    turda yeniden okunur.
    """
    kanal = kanallar(conn, owner_id)
    satirlar = [dict(r) for r in conn.execute(
        f"SELECT id, role, content, created_at FROM conversations "
        f"WHERE id > ? AND chat_id IN ({','.join('?' * len(kanal))}) "
        f"ORDER BY id ASC LIMIT ?",
        (son_id, *kanal, sinir),
    ).fetchall()]

    if not satirlar:
        return "", None

    ad_row = conn.execute("SELECT ad FROM users WHERE id = ?", (owner_id,)).fetchone()
    ad = ad_row["ad"] if ad_row else "Kullanıcı"
    return dokum(satirlar, ad), satirlar[-1]["id"]


def damga_oku(conn, owner_id: int, sutun: str) -> int:
    row = conn.execute(
        f"SELECT {sutun} FROM gozlem_durum WHERE owner_id = ?", (owner_id,)
    ).fetchone()
    return row[sutun] if row else 0


def damga_yaz(conn, owner_id: int, sutun: str, conv_id: int):
    conn.execute(
        f"INSERT INTO gozlem_durum (owner_id, {sutun}) VALUES (?, ?) "
        f"ON CONFLICT(owner_id) DO UPDATE SET {sutun} = excluded.{sutun}",
        (owner_id, conv_id),
    )
