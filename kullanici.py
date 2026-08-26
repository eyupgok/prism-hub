#!/usr/bin/env python3
"""Kullanıcı ekleme/düzenleme aracı.

Parola ve chat_id koda ya da .env'e yazılmasın diye ayrı bir komut. Sunucuda:

    source venv/bin/activate
    python kullanici.py listele
    python kullanici.py ekle "Zeynep" --chat-id 123456789
    python kullanici.py parola "Zeynep"
    python kullanici.py chat-id "Zeynep" 123456789
    python kullanici.py ad "Zeynep" "Zeynep"

Parola sorulurken ekrana yazılmaz (getpass). Karma olarak saklanır, geri okunamaz —
unutulursa `parola` komutuyla yenisi konur.

Telegram chat_id'yi öğrenmek için: kişi bota /start yazar, sunucu logunda
"yetkisiz chat" satırı chat_id ile birlikte görünür (telegram_bot.py).
"""

import argparse
import getpass
import sys
from datetime import datetime

import pytz
from dotenv import load_dotenv

# Sunucu UTF-8 ama Windows konsolu cp1254: çıktıdaki "→" ve Türkçe karakterler
# UnicodeEncodeError ile çöküyordu. İş bitmiş, yalnız haber verirken patlıyordu.
for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from auth import hash_password
from database import get_db, init_db

_TZ = pytz.timezone("Europe/Istanbul")


def _kullanici_bul(conn, ad: str):
    return conn.execute("SELECT * FROM users WHERE ad = ?", (ad,)).fetchone()


def _parola_sor(ad: str) -> str:
    p1 = getpass.getpass(f"{ad} için parola: ")
    if len(p1) < 8:
        sys.exit("Parola en az 8 karakter olmalı.")
    if p1 != getpass.getpass("Tekrar: "):
        sys.exit("Parolalar uyuşmadı.")
    return p1


def listele():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, ad, hitap, telegram_chat_id FROM users ORDER BY id"
        ).fetchall()
    if not rows:
        print("Kayıtlı kullanıcı yok.")
        return
    print(f"{'id':<4} {'ad':<20} {'hitap':<8} telegram_chat_id")
    for r in rows:
        print(f"{r['id']:<4} {r['ad']:<20} {(r['hitap'] or '—'):<8} {r['telegram_chat_id'] or '—'}")


def ekle(ad: str, chat_id: str | None):
    with get_db() as conn:
        if _kullanici_bul(conn, ad):
            sys.exit(f"'{ad}' zaten var. Parolasını değiştirmek için: kullanici.py parola \"{ad}\"")
        parola = _parola_sor(ad)
        conn.execute(
            "INSERT INTO users (ad, telegram_chat_id, parola_hash, created_at) VALUES (?, ?, ?, ?)",
            (ad, chat_id or None, hash_password(parola), datetime.now(_TZ).isoformat()),
        )
        yeni = _kullanici_bul(conn, ad)
    print(f"'{ad}' eklendi (id={yeni['id']}).")
    if not chat_id:
        print("Telegram chat_id verilmedi — sonra: kullanici.py chat-id \"%s\" <id>" % ad)


def parola_degistir(ad: str):
    with get_db() as conn:
        if not _kullanici_bul(conn, ad):
            sys.exit(f"'{ad}' bulunamadı.")
        yeni = _parola_sor(ad)
        conn.execute("UPDATE users SET parola_hash = ? WHERE ad = ?", (hash_password(yeni), ad))
    print(f"'{ad}' parolası değiştirildi. Açık oturumları etkilemez.")


def ad_degistir(eski: str, yeni: str):
    """Kullanıcının görünen adını değiştirir.

    Zararsız bir işlem: kayıtların sahipliği numaraya (`owner_id`) bağlı, oturum
    bileti de numara taşıyor. Yani ad değişince ne veriler kayboluyor ne de
    kimse dışarı atılıyor.

    Tek kural benzersizlik: `ad` sütununda UNIQUE yok ama bu araç ve `gecmis.py`
    kişiyi adıyla buluyor. Aynı ad iki kez olursa "hangisi?" sorusu cevapsız
    kalır — o yüzden burada engelleniyor.
    """
    yeni = yeni.strip()
    if not yeni:
        sys.exit("Yeni ad boş olamaz.")

    with get_db() as conn:
        if not _kullanici_bul(conn, eski):
            sys.exit(f"'{eski}' bulunamadı.")
        if eski != yeni and _kullanici_bul(conn, yeni):
            sys.exit(f"'{yeni}' zaten kullanılıyor, başka bir ad seç.")
        conn.execute("UPDATE users SET ad = ? WHERE ad = ?", (yeni, eski))

    print(f"'{eski}' → '{yeni}'")
    print("Panelde sayfayı yenileyince, Telegram'da bir sonraki mesajda görünür.")


def hitap_ata(ad: str, hitap: str):
    """Asistanın kişiye nasıl hitap edeceğini ayarlar ("Bey", "Hanım").

    Addan çıkarılmıyor — isme bakıp cinsiyet tahmin etmek yanlış sonuç verebilir.
    Boş bırakılırsa asistan cinsiyetten bağımsız "efendim" ile idare eder.
    """
    hitap = hitap.strip()
    with get_db() as conn:
        if not _kullanici_bul(conn, ad):
            sys.exit(f"'{ad}' bulunamadı.")
        conn.execute("UPDATE users SET hitap = ? WHERE ad = ?", (hitap or None, ad))

    if hitap:
        print(f"'{ad}' → asistan artık \"{ad} {hitap}\" diye hitap edecek.")
    else:
        print(f"'{ad}' → hitap temizlendi, asistan \"efendim\" diyecek.")


def chat_id_ata(ad: str, chat_id: str):
    with get_db() as conn:
        if not _kullanici_bul(conn, ad):
            sys.exit(f"'{ad}' bulunamadı.")
        sahip = conn.execute(
            "SELECT ad FROM users WHERE telegram_chat_id = ? AND ad != ?", (chat_id, ad)
        ).fetchone()
        if sahip:
            sys.exit(f"Bu chat_id zaten '{sahip['ad']}' üzerinde.")
        conn.execute("UPDATE users SET telegram_chat_id = ? WHERE ad = ?", (chat_id, ad))
    print(f"'{ad}' → telegram_chat_id {chat_id}")


def main():
    ap = argparse.ArgumentParser(description="PRISM kullanıcı yönetimi")
    alt = ap.add_subparsers(dest="komut", required=True)

    alt.add_parser("listele", help="kullanıcıları listeler")

    p_ekle = alt.add_parser("ekle", help="yeni kullanıcı ekler")
    p_ekle.add_argument("ad")
    p_ekle.add_argument("--chat-id", default=None)

    p_par = alt.add_parser("parola", help="parola değiştirir")
    p_par.add_argument("ad")

    p_chat = alt.add_parser("chat-id", help="Telegram chat_id atar")
    p_chat.add_argument("ad")
    p_chat.add_argument("chat_id")

    p_ad = alt.add_parser("ad", help="görünen adı değiştirir")
    p_ad.add_argument("eski")
    p_ad.add_argument("yeni")

    p_hitap = alt.add_parser("hitap", help='asistanın hitabı: "Bey" / "Hanım"')
    p_hitap.add_argument("ad")
    p_hitap.add_argument("hitap", nargs="?", default="",
                         help="boş bırakılırsa temizlenir (asistan 'efendim' der)")

    a = ap.parse_args()
    init_db()   # tablolar yoksa kurulsun, göç eksikse tamamlansın

    if a.komut == "listele":
        listele()
    elif a.komut == "ekle":
        ekle(a.ad, a.chat_id)
    elif a.komut == "parola":
        parola_degistir(a.ad)
    elif a.komut == "chat-id":
        chat_id_ata(a.ad, a.chat_id)
    elif a.komut == "ad":
        ad_degistir(a.eski, a.yeni)
    elif a.komut == "hitap":
        hitap_ata(a.ad, a.hitap)


if __name__ == "__main__":
    main()
