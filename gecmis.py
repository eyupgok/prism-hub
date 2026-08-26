#!/usr/bin/env python3
"""Konuşma geçmişini okuma aracı.

PRISM her mesajı iki satır olarak saklıyor: kullanıcının yazdığı metin ve
Groq'un ondan çıkardığı JSON komut. Bu araç ikisini okunur hâle getirip
zaman sırasına dizer. Sunucuda:

    source venv/bin/activate
    python gecmis.py                          # son 40 satır, herkes
    python gecmis.py --kisi "Zeynep"        # sadece o kişi
    python gecmis.py --son 100 --ara dişçi    # arama
    python gecmis.py --ham                    # JSON'u olduğu gibi göster

⚠️ Veritabanı ortak: kişi süzmezsen ikinizin de yazışmaları listelenir.

⚠️ Kayıtlar **30 günlük**. Her gece 03:00'te eskiler siliniyor
(`scheduler.cleanup_conversations`), yani eski bir şeyin çıkmaması arıza
değil. Telegram'ın kendi sohbeti süresiz duruyor; asıl arşiv orası, burası
yalnızca botun "neyi nasıl anladığı"nın kaydı.

Bir kişinin İKİ kanalı olabiliyor: Telegram sohbeti (chat_id) ve web panelindeki
sohbet sayfası (`panel:<kullanıcı id>`). `--kisi` ikisini birden getirir, yoksa
panelden yazılanlar görünmez ve geçmiş eksikmiş gibi durur.

`--ara` iki noktada şaşırtabilir: (1) satır satır eşleşir, yani bir soru bulunup
cevabı listede çıkmayabilir; (2) büyük/küçük harf ayrımı yalnız İngiliz harflerinde
yok sayılır — "Dişçi" aranırken "dişçi" bulunur ama "İŞ" aranırken "iş" bulunmaz
(SQLite'ın LIKE'ı Türkçe harfleri katlamıyor). Emin olmak için kelimenin ortasından
bir parça ara: `--ara işçi`.
"""

import argparse
import json
import sys
from datetime import datetime

from dotenv import load_dotenv

# Konuşma dökümü Türkçe ve emoji içeriyor; Windows konsolu (cp1254) bunları
# yazamayıp UnicodeEncodeError atıyor. kullanici.py'de de aynısı var.
for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from database import get_db


def _kanallar(conn, ad: str) -> list:
    """Kişinin yazışmalarının geçtiği chat_id'ler: Telegram + panel."""
    row = conn.execute("SELECT id, telegram_chat_id FROM users WHERE ad = ?", (ad,)).fetchone()
    if not row:
        adlar = [r["ad"] for r in conn.execute("SELECT ad FROM users ORDER BY id")]
        sys.exit(f"'{ad}' bulunamadı. Kayıtlı kişiler: {', '.join(adlar) or '(yok)'}")

    kanallar = [f"panel:{row['id']}"]
    if row["telegram_chat_id"]:
        kanallar.append(row["telegram_chat_id"])
    return kanallar


def _komut_ozeti(komut) -> str:
    """Tek bir JSON komutu tek satırlık okunur metne çevirir."""
    if not isinstance(komut, dict):
        return str(komut)

    modul = komut.get("module", "?")
    params = komut.get("params") or {}

    # Sohbet yanıtlarında asıl bilgi metnin kendisi; "chat.respond" yazmak
    # okuyana hiçbir şey söylemiyor.
    if modul == "chat":
        return params.get("message", "") or "chat.respond"

    detay = ", ".join(f"{a}={d}" for a, d in params.items())
    baslik = f"{modul}.{komut.get('action', '?')}"
    return f"{baslik} ({detay})" if detay else baslik


def _okunur(icerik: str) -> str:
    """Asistan satırındaki ham JSON'u özetler; çözülemezse olduğu gibi bırakır."""
    try:
        veri = json.loads(icerik)
    except (json.JSONDecodeError, TypeError):
        return icerik          # düz metin ya da bozuk kayıt — dokunma

    komutlar = veri.get("commands") if isinstance(veri, dict) else None
    if komutlar is None:
        komutlar = [veri]
    return "  +  ".join(_komut_ozeti(k) for k in komutlar)


def _saat(ham: str) -> str:
    try:
        return datetime.fromisoformat(ham).strftime("%d.%m %H:%M")
    except ValueError:
        return ham[:16]


def main():
    ap = argparse.ArgumentParser(description="PRISM konuşma geçmişi")
    ap.add_argument("--kisi", help="sadece bu kişinin yazışmaları (users.ad)")
    ap.add_argument("--son", type=int, default=40, help="kaç satır (varsayılan 40)")
    ap.add_argument("--ara", help="içinde bu kelime geçen satırlar")
    ap.add_argument("--ham", action="store_true", help="JSON'u özetlemeden göster")
    a = ap.parse_args()

    with get_db() as conn:
        kosullar, degerler = [], []

        if a.kisi:
            kanallar = _kanallar(conn, a.kisi)
            kosullar.append(f"c.chat_id IN ({','.join('?' * len(kanallar))})")
            degerler.extend(kanallar)

        if a.ara:
            kosullar.append("c.content LIKE ?")
            degerler.append(f"%{a.ara}%")

        nerede = f"WHERE {' AND '.join(kosullar)}" if kosullar else ""

        # Son N kaydı almak için tersten sıralanıyor, ekrana eskiden yeniye basılıyor —
        # sohbet yukarıdan aşağı okunsun diye.
        satirlar = conn.execute(
            f"""
            SELECT c.created_at, c.role, c.content, c.chat_id,
                   COALESCE(u.ad, c.chat_id) AS kim
            FROM conversations c
            LEFT JOIN users u
              ON u.telegram_chat_id = c.chat_id
              OR 'panel:' || u.id = c.chat_id
            {nerede}
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (*degerler, a.son),
        ).fetchall()

    if not satirlar:
        print("Kayıt bulunamadı. (Geçmiş 30 günlük tutuluyor — eskiler silinmiş olabilir.)")
        return

    for r in reversed(satirlar):
        panelden = " ·panel" if str(r["chat_id"]).startswith("panel:") else ""
        if r["role"] == "user":
            kim, metin = f"{r['kim']}{panelden}", r["content"]
        else:
            kim = "PRISM"
            metin = r["content"] if a.ham else _okunur(r["content"])
        print(f"{_saat(r['created_at'])}  {kim:<16} {metin}")

    print(f"\n{len(satirlar)} satır. Daha fazlası için: --son {a.son * 2}")


if __name__ == "__main__":
    main()
