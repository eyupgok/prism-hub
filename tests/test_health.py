"""Sağlık kontrolü — dışarıdaki izleme servisi buna bakarak alarm veriyor.

Önemli olan yeşil hali değil, KIRMIZI hali: bozuk durumda gerçekten 503 dönmezse
izleme sessiz kalır ve arıza fark edilmez.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(db):
    # db fixture'ı geçici veritabanını kurar; /health oradan okuyacak
    import main

    # TestClient'ı `with` olmadan kullanıyoruz: lifespan çalışmasın, yani
    # gerçek zamanlayıcı başlamasın ve Telegram webhook'u kurulmasın.
    return TestClient(main.app)


def _fake_scheduler(monkeypatch, running=True, last_check_age_seconds=0):
    import scheduler as sched

    monkeypatch.setattr(sched, "scheduler", SimpleNamespace(running=running))
    if last_check_age_seconds is None:
        monkeypatch.setattr(sched, "last_reminder_check", None)
    else:
        from datetime import datetime

        monkeypatch.setattr(
            sched,
            "last_reminder_check",
            datetime.now(sched.TZ) - timedelta(seconds=last_check_age_seconds),
        )


def test_saglikli_durumda_200(client, monkeypatch):
    _fake_scheduler(monkeypatch, running=True, last_check_age_seconds=30)

    r = client.get("/health")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_zamanlayici_durduysa_503(client, monkeypatch):
    _fake_scheduler(monkeypatch, running=False, last_check_age_seconds=30)

    r = client.get("/health")

    assert r.status_code == 503
    assert r.json()["checks"]["scheduler"] == "durmuş"


def test_dongu_takildiysa_503(client, monkeypatch):
    """Zamanlayıcı ayakta ama hatırlatıcı işi tur atmıyor — en sinsi arıza."""
    _fake_scheduler(monkeypatch, running=True, last_check_age_seconds=20 * 60)

    r = client.get("/health")

    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert "takılmış" in r.json()["checks"]["reminder_loop"]


def test_dongu_hic_calismadiysa_503(client, monkeypatch):
    _fake_scheduler(monkeypatch, running=True, last_check_age_seconds=None)

    r = client.get("/health")

    assert r.status_code == 503
    assert r.json()["checks"]["reminder_loop"] == "hiç çalışmadı"
