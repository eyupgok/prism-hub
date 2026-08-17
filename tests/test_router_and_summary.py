"""Çoklu komut yönlendirme ve akşam/haftalık özetler."""

from datetime import timedelta

import pytest

import ai_router
from modules.expenses import service as exp_svc
from modules.reminders import service as rem_svc
from modules.summary import service as summary_svc
from conftest import SAHIP, OTEKI


async def _dispatch(parsed):
    """dispatch artık sahip istiyor; testler hep aynı sahibi kullanıyor."""
    return await ai_router.dispatch(parsed, SAHIP)


def _chat(message):
    return {"module": "chat", "action": "respond", "params": {"message": message}}


# ── Çoklu komut ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tek_komut_calisir():
    assert await _dispatch(_chat("Tek")) == "Tek"


@pytest.mark.asyncio
async def test_coklu_komut_hepsi_calisir():
    """Eskiden 'X hatırlat ve Y ekle' dendiğinde ikinci iş sessizce kayboluyordu."""
    out = await _dispatch({"commands": [_chat("Birinci"), _chat("İkinci")]})
    assert out == "Birinci\n\nİkinci"


@pytest.mark.asyncio
async def test_coklu_komut_sayisi_sinirli():
    out = await _dispatch({"commands": [_chat(str(i)) for i in range(8)]})
    assert "atlandı" in out


@pytest.mark.asyncio
async def test_bozuk_komut_diger_komutlari_bozmaz():
    out = await _dispatch({"commands": [_chat("İyi"), {"module": "yok"}]})
    assert "İyi" in out


# ── completed_at ve sayımlar ─────────────────────────────────────────────────

def test_tamamlama_ani_kaydedilir(db):
    r = rem_svc.create_reminder(db, SAHIP, "İş", rem_svc.now_local().isoformat(), 2, "none")
    rem_svc.complete_reminder(db, SAHIP, r["id"])

    assert rem_svc.get_reminder_by_id(db, r["id"])["completed_at"] is not None

    start = rem_svc.now_local().replace(hour=0, minute=0, second=0, microsecond=0)
    assert rem_svc.count_completed_between(db, SAHIP, start, start + timedelta(days=1)) == 1
    assert rem_svc.count_completed_between(db, SAHIP, start - timedelta(days=1), start) == 0


# ── Özetler ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_aksam_ozeti_iadeyi_ayirt_eder(db):
    today = rem_svc.now_local().strftime("%Y-%m-%d")
    exp_svc.create_expense(db, SAHIP, 250.0, "yemek", "Öğle", today)
    exp_svc.create_expense(db, SAHIP, -50.0, "yemek", "İade", today)
    db.commit()

    text = await summary_svc.get_evening_summary(SAHIP)

    assert "200 TL harcadın" in text   # 250 - 50
    assert "iade dahil" in text


@pytest.mark.asyncio
async def test_aksam_ozeti_yarini_gosterir(db):
    yarin = (rem_svc.now_local() + timedelta(days=1)).isoformat()
    rem_svc.create_reminder(db, SAHIP, "Yarınki iş", yarin, 1, "none")
    db.commit()

    assert "Yarın 1 görev" in await summary_svc.get_evening_summary(SAHIP)


@pytest.mark.asyncio
async def test_haftalik_rapor_cubuk_ve_kategori(db):
    today = rem_svc.now_local().strftime("%Y-%m-%d")
    exp_svc.create_expense(db, SAHIP, 300.0, "alışveriş", "Market", today)
    db.commit()

    text = await summary_svc.get_weekly_report(SAHIP)

    assert "Haftalık rapor" in text
    assert "▓" in text            # günlük dağılım çubuğu
    assert "alışveriş" in text
