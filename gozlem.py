#!/usr/bin/env python3
"""Gözlem katmanının denetim aracı — asistanın hafızası ve kararları.

Bu katman panelde YOK, bilerek. Asistanın kişi hakkında biriktirdiği bilgiler
ve kendiliğinden konuşma kararları gündelik arayüzde durması gereken şeyler
değil; ama görülmeleri ve düzeltilebilmeleri şart. İkisinin arası burası.

    source venv/bin/activate

    python gozlem.py bilgi                       # PRISM kimin hakkında ne biliyor
    python gozlem.py bilgi --kisi "Eyüp"
    python gozlem.py ekle "Eyüp" "Sabahları erken kalkmaz." --tur alışkanlık
    python gozlem.py unut 12                      # yanlış bir bilgiyi sil
    python gozlem.py cikar "Eyüp"                 # konuşmalardan çıkarımı elle çalıştır

    python gozlem.py takip                        # sonradan soracağı şeyler
    python gozlem.py takip-cikar "Eyüp"           # takip çıkarımını elle çalıştır
    python gozlem.py takip-unut 3                 # gereksiz bir soruyu iptal et

    python gozlem.py sinyal "Eyüp"                # şu an ne fark ediyor (hiçbir şey göndermez)
    python gozlem.py tur "Eyüp"                   # tam tur — ne derdi? (GÖNDERMEZ)
    python gozlem.py tur "Eyüp" --gercek          # gerçekten gönder (onay sorar)
    python gozlem.py gunluk                       # konuştuğu ve SUSTUĞU turlar
    python gozlem.py gunluk --kisi "Eyüp" --son 60

    python gozlem.py seviye "Eyüp" 3              # günde en fazla 3 kendiliğinden mesaj
    python gozlem.py seviye "Zeynep" 0          # kapat

⚠️ **Herkes kapalı başlar** (`gozlem_sinir = 0`). Kendiliğinden mesaj, asistanın
kullanıcının istemediği bir şeyi gönderebildiği tek mekanizma; açılması ayrı bir
komuta bağlı. `tur` komutu `--gercek` olmadan hiçbir şey göndermez, o yüzden
kapalıyken de rahatça denenebilir.

⚠️ `gunluk` çıktısındaki "sustu" satırları asıl değerli olanlar: eşikleri
(`modules/gozlem/service.py` başındaki sabitler) ancak onlara bakarak
ayarlayabilirsin.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime

from dotenv import load_dotenv

# Çıktı Türkçe ve emoji içeriyor; Windows konsolu (cp1254) bunları yazamayıp
# UnicodeEncodeError atıyor. kullanici.py ve gecmis.py'de de aynısı var.
for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")

load_dotenv()

from database import get_db, init_db
from modules.gozlem import hafiza, service, sinyaller, takip


def _kisi(conn, ad: str) -> dict:
    row = conn.execute("SELECT * FROM users WHERE ad = ?", (ad,)).fetchone()
    if not row:
        adlar = [r["ad"] for r in conn.execute("SELECT ad FROM users ORDER BY id")]
        sys.exit(f"'{ad}' bulunamadı. Kayıtlı kişiler: {', '.join(adlar) or '(yok)'}")
    return dict(row)


def _saat(ham: str) -> str:
    try:
        return datetime.fromisoformat(ham).strftime("%d.%m %H:%M")
    except (ValueError, TypeError):
        return str(ham)[:16]


# ── Hafıza ───────────────────────────────────────────────────────────────────

def bilgi_listele(ad: str = None):
    with get_db() as conn:
        if ad:
            kisiler = [_kisi(conn, ad)]
        else:
            kisiler = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id")]

        for k in kisiler:
            bilgiler = hafiza.listele(conn, k["id"])
            print(f"\n=== {k['ad']} — {len(bilgiler)} bilgi ===")
            if not bilgiler:
                print("  (henüz hiçbir şey biriktirmedi)")
                continue
            for b in bilgiler:
                sure = f"  · {b['gecerlilik']}'e kadar" if b["gecerlilik"] else ""
                print(f"  [{b['id']:>3}] {b['icerik']}")
                print(f"        {b['tur']} · {b['kaynak']} · {_saat(b['created_at'])}{sure}")


def bilgi_ekle(ad: str, icerik: str, tur: str, gecerlilik: str):
    with get_db() as conn:
        k = _kisi(conn, ad)
        yeni = hafiza.ekle(conn, k["id"], icerik, tur, kaynak="elle", gecerlilik=gecerlilik)
    if yeni:
        print(f"Eklendi [{yeni['id']}]: {yeni['icerik']}")
    else:
        print("Bu bilgi zaten var (teyit damgası yenilendi).")


def bilgi_unut(hafiza_id: int):
    with get_db() as conn:
        silinen = hafiza.unut(conn, hafiza_id)
    if silinen:
        print(f"Silindi: {silinen['icerik']}")
    else:
        sys.exit(f"[{hafiza_id}] numaralı bilgi bulunamadı.")


def bilgi_cikar(ad: str):
    with get_db() as conn:
        k = _kisi(conn, ad)

    eklenen = asyncio.run(hafiza.cikar(k["id"]))
    if not eklenen:
        print("Yeni bilgi çıkmadı. (İşlenmemiş konuşma yoksa ya da kalıcı bir şey "
              "söylenmediyse olağan.)")
        return
    print(f"{len(eklenen)} yeni bilgi:")
    for i in eklenen:
        print(f"  + {i}")


# ── Takip ────────────────────────────────────────────────────────────────────

def takip_listele(ad: str = None):
    with get_db() as conn:
        if ad:
            kisiler = [_kisi(conn, ad)]
        else:
            kisiler = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id")]

        simdi = datetime.now(service.TZ)
        for k in kisiler:
            acik = takip.acik_takipler(conn, k["id"])
            print(f"\n=== {k['ad']} — {len(acik)} bekleyen takip ===")
            if not acik:
                print("  (sorulacak bir şey yok)")
                continue
            for t in acik:
                vakti = datetime.fromisoformat(t["sorulacak_at"])
                durum = "SORULABİLİR" if vakti <= simdi else f"{_saat(t['sorulacak_at'])}'de"
                print(f"  [{t['id']:>3}] {t['konu']}  ({durum})")
                print(f"        \"{t['soru']}\"")


def takip_cikar(ad: str):
    with get_db() as conn:
        k = _kisi(conn, ad)

    eklenen = asyncio.run(takip.cikar(k["id"]))
    if not eklenen:
        print("Sorulmaya değer yeni bir şey çıkmadı. (Konuşmaların çoğunda olağan.)")
        return
    print(f"{len(eklenen)} takip alındı:")
    for i in eklenen:
        print(f"  + {i}")


def takip_unut(takip_id: int):
    with get_db() as conn:
        silinen = takip.unut(conn, takip_id)
    if silinen:
        print(f"Silindi: {silinen['konu']} — \"{silinen['soru']}\"")
    else:
        sys.exit(f"[{takip_id}] numaralı takip bulunamadı.")


# ── Gözlem ───────────────────────────────────────────────────────────────────

def sinyal_goster(ad: str):
    async def calis():
        with get_db() as conn:
            k = _kisi(conn, ad)
            return k, await sinyaller.topla(conn, k["id"], k)

    k, bulunan = asyncio.run(calis())
    print(f"\n=== {k['ad']} — {len(bulunan)} sinyal ===")
    if not bulunan:
        print("  Şu an dikkat çeken bir şey yok. (Olağan hâl.)")
        return
    for s in bulunan:
        print(f"  [{s['agirlik']}] [{s.get('kategori', 'durum').upper()}] {s['anahtar']}")
        print(f"      {s['kanit']}")


def tur_calistir(ad: str, gercek: bool):
    with get_db() as conn:
        k = _kisi(conn, ad)

    if gercek:
        chat = k["telegram_chat_id"] or "(chat_id yok — Eyüp'ün sohbetine düşer)"
        print(f"⚠️  GERÇEK gönderim: {k['ad']} → Telegram {chat}")
        try:
            if input("Devam edilsin mi? (evet/hayır) ").strip().lower() not in ("evet", "e"):
                print("Vazgeçildi.")
                return
        except EOFError:
            sys.exit("Onay sorulamadı (terminal yok). Hiçbir şey gönderilmedi.")

    sonuc = asyncio.run(service.tur(k["id"], kuru=not gercek))

    print(f"\n=== {k['ad']} — karar: {sonuc['karar'].upper()} ===")
    print(f"  sebep: {sonuc['sebep']}")

    if sonuc.get("sinyaller"):
        print(f"\n  Elindeki sinyaller ({len(sonuc['sinyaller'])}):")
        for s in sonuc["sinyaller"]:
            tur = s.get("kategori", "durum").upper()
            print(f"    [{s['agirlik']}] [{tur}] {s['anahtar']} — {s['kanit']}")

    if sonuc.get("mesaj"):
        print(f"\n  Konu: {sonuc.get('anahtar')}")
        print(f"  Mesaj: {sonuc['mesaj']}")
        if not sonuc.get("gonderildi"):
            print("\n  (KURU ÇALIŞTIRMA — gönderilmedi. Göndermek için: --gercek)")
            if sonuc.get("uyari"):
                print(f"  ⚠️  Gerçek turda susardı: {sonuc['uyari']}")


def gunluk_goster(ad: str, son: int):
    with get_db() as conn:
        kosul, degerler = "", []
        if ad:
            k = _kisi(conn, ad)
            kosul = "WHERE g.owner_id = ?"
            degerler.append(k["id"])

        satirlar = [dict(r) for r in conn.execute(
            f"SELECT g.*, COALESCE(u.ad, '?') kim FROM gozlem_gunlugu g "
            f"LEFT JOIN users u ON u.id = g.owner_id {kosul} "
            f"ORDER BY g.id DESC LIMIT ?",
            (*degerler, son),
        ).fetchall()]

    if not satirlar:
        print("Henüz gözlem turu çalışmamış.")
        return

    for r in reversed(satirlar):
        isaret = "KONUŞTU" if r["karar"] == "konustu" else "sustu  "
        print(f"{_saat(r['created_at'])}  {r['kim']:<12} {isaret}  {r['sebep'] or ''}")
        if r["mesaj"]:
            print(f"{'':>28}  → {r['mesaj']}")
        gorulen = json.loads(r["sinyaller"] or "[]")
        if gorulen and r["karar"] != "konustu":
            print(f"{'':>28}  görülen: {', '.join(gorulen)}")

    konusan = sum(1 for r in satirlar if r["karar"] == "konustu")
    print(f"\n{len(satirlar)} tur · {konusan} mesaj · {len(satirlar) - konusan} sessiz tur")


def seviye_ayarla(ad: str, sinir: int):
    if not 0 <= sinir <= 10:
        sys.exit("Sınır 0 ile 10 arasında olmalı. (0 = kapalı, önerilen 3)")

    with get_db() as conn:
        k = _kisi(conn, ad)
        conn.execute("UPDATE users SET gozlem_sinir = ? WHERE id = ?", (sinir, k["id"]))

    if sinir == 0:
        print(f"'{ad}' için kendiliğinden mesaj KAPATILDI.")
    else:
        print(f"'{ad}' → günde en fazla {sinir} kendiliğinden mesaj.")
        print(f"Aralarında en az {service.ASGARI_ARA_DAKIKA} dakika, "
              f"{service.SESSIZ_BASLANGIC}:00–{service.SESSIZ_BITIS}:00 arası sessiz.")


# ── Giriş ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="PRISM gözlem katmanı — hafıza ve kendiliğinden konuşma",
    )
    alt = ap.add_subparsers(dest="komut", required=True)

    p_bilgi = alt.add_parser("bilgi", help="asistanın bildiklerini listeler")
    p_bilgi.add_argument("--kisi", default=None)

    p_ekle = alt.add_parser("ekle", help="elle bilgi ekler")
    p_ekle.add_argument("kisi")
    p_ekle.add_argument("icerik")
    p_ekle.add_argument("--tur", default="olgu",
                        help="alışkanlık|tercih|durum|ilişki|olgu")
    p_ekle.add_argument("--gecerlilik", default=None,
                        help="YYYY-MM-DD — bu tarihten sonra unutulur")

    p_unut = alt.add_parser("unut", help="bir bilgiyi siler")
    p_unut.add_argument("id", type=int)

    p_cikar = alt.add_parser("cikar", help="konuşmalardan çıkarımı elle çalıştırır")
    p_cikar.add_argument("kisi")

    p_takip = alt.add_parser("takip", help="sonradan sorulacak şeyler")
    p_takip.add_argument("--kisi", default=None)

    p_tcikar = alt.add_parser("takip-cikar", help="konuşmalardan takip çıkarımını elle çalıştırır")
    p_tcikar.add_argument("kisi")

    p_tunut = alt.add_parser("takip-unut", help="bir takibi siler")
    p_tunut.add_argument("id", type=int)

    p_sinyal = alt.add_parser("sinyal", help="şu anki sinyaller (hiçbir şey göndermez)")
    p_sinyal.add_argument("kisi")

    p_tur = alt.add_parser("tur", help="gözlem turu — varsayılan olarak GÖNDERMEZ")
    p_tur.add_argument("kisi")
    p_tur.add_argument("--gercek", action="store_true",
                       help="gerçekten Telegram'a gönder (onay sorar)")

    p_gunluk = alt.add_parser("gunluk", help="karar günlüğü (sustuğu turlar dahil)")
    p_gunluk.add_argument("--kisi", default=None)
    p_gunluk.add_argument("--son", type=int, default=30)

    p_sev = alt.add_parser("seviye", help="günlük kendiliğinden mesaj sınırı")
    p_sev.add_argument("kisi")
    p_sev.add_argument("sinir", type=int)

    a = ap.parse_args()
    init_db()          # tablolar yoksa kurulsun, göç eksikse tamamlansın

    if a.komut == "bilgi":
        bilgi_listele(a.kisi)
    elif a.komut == "ekle":
        bilgi_ekle(a.kisi, a.icerik, a.tur, a.gecerlilik)
    elif a.komut == "unut":
        bilgi_unut(a.id)
    elif a.komut == "cikar":
        bilgi_cikar(a.kisi)
    elif a.komut == "takip":
        takip_listele(a.kisi)
    elif a.komut == "takip-cikar":
        takip_cikar(a.kisi)
    elif a.komut == "takip-unut":
        takip_unut(a.id)
    elif a.komut == "sinyal":
        sinyal_goster(a.kisi)
    elif a.komut == "tur":
        tur_calistir(a.kisi, a.gercek)
    elif a.komut == "gunluk":
        gunluk_goster(a.kisi, a.son)
    elif a.komut == "seviye":
        seviye_ayarla(a.kisi, a.sinir)


if __name__ == "__main__":
    main()
