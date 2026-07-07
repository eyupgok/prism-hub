import os
import secrets

from fastapi import Header, HTTPException


async def verify_api_key(x_api_key: str = Header(default="")):
    """REST API için X-API-Key doğrulaması.

    API_KEY ortam değişkeni boşsa doğrulama devre dışı kalır (lokal geliştirme).
    """
    expected = os.getenv("API_KEY", "")
    if not expected:
        return
    if not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı")
