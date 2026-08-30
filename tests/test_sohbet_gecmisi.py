"""Panelde sohbet geçmişi: ne saklanıyor, ekrana ne çıkıyor.

Bu testlerin ağırlığı **iki metnin karışmaması** üzerinde. `conversations`
tablosunda asistan satırı iki farklı okur kitleye hizmet ediyor:

- `content` → modelin gördüğü ham JSON komut,
- `gorunen` → insanın gördüğü cevap.

İkisi birbirine karışırsa iki ayrı arıza çıkar: ya kullanıcı ekranda
`{"module": "reminders", ...}` görür, ya da model kendi çıktı biçimini
göremeyip komut üretmeyi bırakır.
"""

import json

import pytest

from conftest import SAHIP


@pytest.fixture()
def kova(db):
    """Testler tek bir panel kovası üzerinden ilerliyor."""
    db.commit()          # save_message kendi bağlantısını açıyor
    return f"panel:{SAHIP}"


def _yaz(kova, role, content, gorunen=None):
    from database import save_message
    save_message(kova, role, content, gorunen)


# ── İki metnin ayrılması ─────────────────────────────────────────────────────

def test_modele_ham_json_gider(kova):
    from database import get_recent_messages

    komut = json.dumps({"module": "reminders", "action": "create"}, ensure_ascii=False)
    _yaz(kova, "assistant", komut, "Kaydedildi, efendim.")

    assert get_recent_messages(kova)[-1]["content"] == komut


def test_panele_okunur_metin_gider(kova):
    from database import get_conversation

    _yaz(kova, "user", "yarın 10'da dişçi")
    _yaz(kova, "assistant", '{"module":"reminders"}', "Kaydedildi, efendim.")

    gecmis = get_conversation(kova)
    assert [m["metin"] for m in gecmis] == ["yarın 10'da dişçi", "Kaydedildi, efendim."]


def test_gorunen_yoksa_asistan_satiri_elenir(kova):
    """⚠️ Sütun sonradan eklendi: eski kayıtlarda asistan tarafı ham JSON.
    Kullanıcıya `{"module": ...}` göstermektense hiç göstermemek doğru."""
    from database import get_conversation

    _yaz(kova, "user", "merhaba")
    _yaz(kova, "assistant", '{"module":"chat","action":"respond"}')   # gorunen YOK

    assert [m["metin"] for m in get_conversation(kova)] == ["merhaba"]


def test_kullanici_satiri_gorunen_olmadan_da_cikar(kova):
    """Düz yazılan mesajda iki metin zaten aynı; `gorunen` NULL kalır."""
    from database import get_conversation

    _yaz(kova, "user", "bu ay ne harcamışım")

    assert [m["metin"] for m in get_conversation(kova)] == ["bu ay ne harcamışım"]


# ── Kova ayrımı ──────────────────────────────────────────────────────────────

def test_baska_kovanin_mesaji_gorunmez(kova):
    """Panel ve Telegram ayrı bağlam; birinin geçmişi diğerine sızmamalı."""
    from database import get_conversation

    _yaz(kova, "user", "panelden")
    _yaz("999", "user", "telegramdan")

    assert [m["metin"] for m in get_conversation(kova)] == ["panelden"]


# ── Sıra ve sınır ────────────────────────────────────────────────────────────

def test_kronolojik_sirada_doner(kova):
    from database import get_conversation

    for i in range(5):
        _yaz(kova, "user", f"mesaj {i}")

    assert [m["metin"] for m in get_conversation(kova)] == [f"mesaj {i}" for i in range(5)]


def test_sinir_son_mesajlari_verir(kova):
    """Sınıra takılınca ESKİ değil YENİ olanlar kalmalı."""
    from database import get_conversation

    for i in range(10):
        _yaz(kova, "user", f"mesaj {i}")

    assert [m["metin"] for m in get_conversation(kova, limit=3)] == [
        "mesaj 7", "mesaj 8", "mesaj 9",
    ]


def test_zaman_damgasi_tasiniyor(kova):
    """Panel gün ayracını (Bugün / Dün) buna göre çiziyor."""
    from database import get_conversation

    _yaz(kova, "user", "merhaba")

    assert get_conversation(kova)[0]["created_at"]


# ── Göç ──────────────────────────────────────────────────────────────────────

def test_gorunen_gocu_veri_kaybetmiyor(db):
    """Sütun yokken yazılmış satırlar `init_db()` sonrası duruyor mu."""
    from database import get_conversation, init_db

    db.execute(
        "INSERT INTO conversations (chat_id, role, content, created_at) "
        "VALUES ('panel:1', 'user', 'eski mesaj', '2026-01-01T00:00:00')"
    )
    db.commit()

    init_db()   # idempotent olmalı: ikinci kez çalışması bozmamalı

    assert [m["metin"] for m in get_conversation("panel:1")] == ["eski mesaj"]
