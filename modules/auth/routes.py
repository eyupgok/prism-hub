"""Web paneli giriş uçları.

Bu router bilerek `verify_api_key` KORUMASI OLMADAN eklenir — giriş yapabilmek için
zaten giriş yapmış olmak gerekemez. Korunan asıl şey `/api/*` verileri; buraya
gelen tek şey parola denemesi ve o da `check_panel_password()` içinde sayaçla sınırlı.
"""

import os
from datetime import datetime
from typing import Optional

import pytz
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

from auth import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    verify_api_key,
    check_panel_password,
    create_session_token,
    kullanici_getir,
    panel_login_enabled,
    session_user_id,
    tum_kullanicilar,
)

_TZ = pytz.timezone("Europe/Istanbul")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


def _cookie_secure() -> bool:
    """HTTPS'te çerez 'secure' işaretlenir; lokal http geliştirmede işaretlenmez."""
    return os.getenv("WEBHOOK_URL", "").startswith("https://")


def _acik(k: Optional[dict]) -> Optional[dict]:
    """Kullanıcıdan dışarı verilebilecek alanlar. parola_hash ve chat_id dışarı ÇIKMAZ.

    `sehir` veriliyor çünkü panel "hangi konuma göre hava gösteriyorum"u
    yazabilsin; koordinatlar verilmiyor, ekranda işe yaramıyorlar.
    """
    return {"id": k["id"], "ad": k["ad"], "sehir": k.get("sehir")} if k else None


@router.get("/me")
def me(prism_session: Optional[str] = Cookie(default=None)):
    """Panelin açılışta sorduğu uç: giriş gerekiyor mu, yapılmış mı, kim?

    `login_required` false ise sunucuda API_KEY yok demektir (lokal geliştirme) —
    panel giriş ekranı göstermeden açılır.

    `kullanicilar` üstteki geçiş menüsünü besliyor. Giriş yapılmadan verilmiyor:
    korumasız bir uçtan ev halkının isimlerini saymanın gereği yok.
    """
    uid = session_user_id(prism_session) if prism_session else None
    kullanici = kullanici_getir(uid) if uid is not None else None

    return {
        "authenticated": kullanici is not None,
        "login_required": bool(os.getenv("API_KEY", "")),
        "login_enabled": panel_login_enabled(),
        "kullanici": _acik(kullanici),
        "kullanicilar": [_acik(k) for k in tum_kullanicilar()] if kullanici else [],
    }


@router.post("/login")
def login(data: LoginRequest, response: Response):
    if not panel_login_enabled():
        raise HTTPException(
            status_code=503,
            detail="Panel girişi sunucuda ayarlanmamış (kayıtlı kullanıcı yok)",
        )

    kullanici = check_panel_password(data.password)
    if not kullanici:
        raise HTTPException(status_code=401, detail="Parola hatalı")

    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(kullanici["id"]),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,      # JavaScript okuyamaz — XSS'te bilet çalınamaz
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    return {"authenticated": True, "kullanici": _acik(kullanici)}


class KonumRequest(BaseModel):
    enlem: float
    boylam: float


@router.post("/konum")
async def konum_bildir(data: KonumRequest, user: dict = Depends(verify_api_key)):
    """Panelin girişte tarayıcıdan aldığı konumu kaydeder.

    Bu router `main.py`'de korumasız ekleniyor (giriş uçları için), o yüzden
    koruma burada tek tek: `Depends(verify_api_key)`. Konum kişiye yazılıyor,
    kimin yazdığı kesin olmalı.

    Şehir adı yalnızca kullanıcı gerçekten yer değiştirmişse yeniden çözülüyor;
    çözülemezse eski ad korunuyor — hava durumu koordinatla çalıştığı için ad
    olmasa da bozulmaz.
    """
    from database import get_db
    from modules.weather.service import AYNI_YER_KM, _mesafe_km, sehir_adi

    if not (-90 <= data.enlem <= 90) or not (-180 <= data.boylam <= 180):
        raise HTTPException(status_code=422, detail="Geçersiz koordinat")

    eski_enlem, eski_boylam = user.get("enlem"), user.get("boylam")
    tasindi = (
        eski_enlem is None
        or _mesafe_km(eski_enlem, eski_boylam, data.enlem, data.boylam) > AYNI_YER_KM
    )

    sehir = await sehir_adi(data.enlem, data.boylam) if tasindi else None
    sehir = sehir or user.get("sehir")

    with get_db() as conn:
        conn.execute(
            "UPDATE users SET enlem = ?, boylam = ?, sehir = ?, konum_at = ? WHERE id = ?",
            (data.enlem, data.boylam, sehir,
             datetime.now(_TZ).isoformat(), user["id"]),
        )
    return {"sehir": sehir, "tasindi": tasindi}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return {"authenticated": False}
