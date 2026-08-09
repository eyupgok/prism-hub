"""Web paneli giriş uçları.

Bu router bilerek `verify_api_key` KORUMASI OLMADAN eklenir — giriş yapabilmek için
zaten giriş yapmış olmak gerekemez. Korunan asıl şey `/api/*` verileri; buraya
gelen tek şey parola denemesi ve o da `check_panel_password()` içinde sayaçla sınırlı.
"""

import os
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

from auth import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    check_panel_password,
    create_session_token,
    is_valid_session,
    panel_login_enabled,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


def _cookie_secure() -> bool:
    """HTTPS'te çerez 'secure' işaretlenir; lokal http geliştirmede işaretlenmez."""
    return os.getenv("WEBHOOK_URL", "").startswith("https://")


@router.get("/me")
def me(prism_session: Optional[str] = Cookie(default=None)):
    """Panelin açılışta sorduğu uç: giriş gerekiyor mu, yapılmış mı?

    `login_required` false ise sunucuda API_KEY yok demektir (lokal geliştirme) —
    panel giriş ekranı göstermeden açılır.
    """
    return {
        "authenticated": bool(prism_session and is_valid_session(prism_session)),
        "login_required": bool(os.getenv("API_KEY", "")),
        "login_enabled": panel_login_enabled(),
    }


@router.post("/login")
def login(data: LoginRequest, response: Response):
    if not panel_login_enabled():
        raise HTTPException(
            status_code=503,
            detail="Panel girişi sunucuda ayarlanmamış (PANEL_PASSWORD eksik)",
        )

    if not check_panel_password(data.password):
        raise HTTPException(status_code=401, detail="Parola hatalı")

    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,      # JavaScript okuyamaz — XSS'te bilet çalınamaz
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return {"authenticated": False}
