"""REST API kimlik doğrulama — iki yol kabul edilir.

1. `X-API-Key` başlığı — Android uygulaması ve doğrudan API çağrıları için.
2. `prism_session` çerezi — web paneli için. Kullanıcı parolayla giriş yapar,
   sunucu imzalı bir bilet (token) verir. Panelin JS paketinde gizli anahtar
   BULUNMAZ; çerez HttpOnly olduğu için JavaScript de okuyamaz.

Oturum bileti sunucuda saklanmaz — kendi içinde son kullanma tarihini taşır ve
HMAC ile imzalanır. Bu yüzden ayrı bir tablo/temizlik gerekmiyor.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

from fastapi import Cookie, Header, HTTPException

SESSION_COOKIE = "prism_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 gün

# Parola denemesi sınırı (kaba kuvvet denemesine karşı)
_MAX_ATTEMPTS = 8
_LOCKOUT_SECONDS = 15 * 60
_failed_attempts = 0
_locked_until = 0.0


def _signing_key() -> bytes:
    """Oturum imzalama anahtarı API_KEY'den türetilir.

    Ayrı bir env değişkeni istememek için böyle; API_KEY değiştirilirse tüm
    oturumlar geçersiz olur — istenen davranış zaten budur.
    """
    base = os.getenv("API_KEY", "") or os.getenv("PANEL_PASSWORD", "")
    return hmac.new(base.encode(), b"prism-panel-session", hashlib.sha256).digest()


def _sign(payload: str) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")


def create_session_token(ttl: int = SESSION_TTL_SECONDS) -> str:
    """`<son_kullanma>.<imza>` biçiminde bilet üretir."""
    expires = str(int(time.time()) + ttl)
    return f"{expires}.{_sign(expires)}"


def is_valid_session(token: str) -> bool:
    if not token or "." not in token:
        return False
    expires_str, signature = token.rsplit(".", 1)
    if not secrets.compare_digest(signature, _sign(expires_str)):
        return False
    try:
        return int(expires_str) > time.time()
    except ValueError:
        return False


def panel_login_enabled() -> bool:
    """Panel girişi ancak PANEL_PASSWORD tanımlıysa çalışır."""
    return bool(os.getenv("PANEL_PASSWORD", ""))


def check_panel_password(password: str) -> bool:
    """Parolayı doğrular; art arda hatalı denemede geçici olarak kilitler."""
    global _failed_attempts, _locked_until

    expected = os.getenv("PANEL_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Panel girişi sunucuda ayarlanmamış")

    if time.time() < _locked_until:
        remaining = int((_locked_until - time.time()) / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Çok fazla hatalı deneme. {remaining} dakika sonra tekrar dene.",
        )

    if secrets.compare_digest(password, expected):
        _failed_attempts = 0
        return True

    _failed_attempts += 1
    if _failed_attempts >= _MAX_ATTEMPTS:
        _locked_until = time.time() + _LOCKOUT_SECONDS
        _failed_attempts = 0
    return False


async def verify_api_key(
    x_api_key: str = Header(default=""),
    prism_session: Optional[str] = Cookie(default=None),
):
    """API anahtarı VEYA geçerli panel oturumu kabul edilir.

    API_KEY ortam değişkeni boşsa doğrulama devre dışı kalır (lokal geliştirme).
    """
    expected = os.getenv("API_KEY", "")
    if not expected:
        return

    if x_api_key and secrets.compare_digest(x_api_key, expected):
        return
    if prism_session and is_valid_session(prism_session):
        return

    raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı")
