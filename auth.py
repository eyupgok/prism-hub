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

# ——— Parola karması ———
# Tek kullanıcılıyken parola env'de düz metindi ve `compare_digest` ile karşılaştırılıyordu.
# Artık veritabanında duruyor; veritabanı her gece Telegram'a yedekleniyor, dolayısıyla
# düz metin saklamak olmaz. scrypt seçildi çünkü stdlib'de var (yeni bağımlılık yok) ve
# bellek-zor: GPU ile toplu deneme bcrypt'e göre çok daha pahalı.
_SCRYPT_N = 2 ** 14          # ~16 MB bellek, tek doğrulama ~50 ms
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def _scrypt(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32, maxmem=_SCRYPT_MAXMEM,
    )


def hash_password(password: str) -> str:
    """`scrypt$<tuz>$<karma>` — tuz her parolaya özel, kayıtla birlikte saklanır."""
    salt = secrets.token_bytes(16)
    return f"scrypt${salt.hex()}${_scrypt(password, salt).hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Karmayı doğrular. Biçim bozuksa sessizce False — çökmek yerine reddet."""
    try:
        algo, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        hesaplanan = _scrypt(password, bytes.fromhex(salt_hex)).hex()
    except (ValueError, AttributeError):
        return False
    return secrets.compare_digest(hesaplanan, hash_hex)


def _signing_key() -> bytes:
    """Oturum imzalama anahtarı.

    Eskiden API_KEY'den türetiliyordu. Artık türetilmiyor: parolalar veritabanına
    taşınınca API_KEY tek dayanak olmaktan çıktı, ayrıca kullanıcı başına API
    anahtarına geçilirse imza anahtarının onlara bağlı olmaması gerekir.
    SESSION_SECRET yoksa eski davranışa düşülür — böylece bu sürüm env
    güncellenmeden yayına alınsa bile panel çalışmaya devam eder.
    """
    base = (
        os.getenv("SESSION_SECRET", "")
        or os.getenv("API_KEY", "")
        or os.getenv("PANEL_PASSWORD", "")
    )
    return hmac.new(base.encode(), b"prism-panel-session", hashlib.sha256).digest()


def _sign(payload: str) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(_signing_key(), payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")


def create_session_token(user_id: int, ttl: int = SESSION_TTL_SECONDS) -> str:
    """`<kullanıcı>.<son_kullanma>.<imza>` biçiminde bilet üretir.

    Bilet artık kimlik taşıyor. İmza `kullanıcı.son_kullanma` ikilisinin üstünde:
    kullanıcı numarasını değiştiren biri imzayı da bozmuş olur, yani çerezi
    kurcalayıp başkasının hesabına geçilemez.
    """
    payload = f"{user_id}.{int(time.time()) + ttl}"
    return f"{payload}.{_sign(payload)}"


def session_user_id(token: str) -> Optional[int]:
    """Geçerliyse biletteki kullanıcı numarasını, değilse None döner."""
    if not token or token.count(".") != 2:
        return None
    user_part, expires_str, signature = token.split(".")
    if not secrets.compare_digest(signature, _sign(f"{user_part}.{expires_str}")):
        return None
    try:
        if int(expires_str) <= time.time():
            return None
        return int(user_part)
    except ValueError:
        return None


def is_valid_session(token: str) -> bool:
    return session_user_id(token) is not None


def tum_kullanicilar() -> list:
    """Kayıtlı kullanıcılar (id sırasıyla). Parola karması da gelir — dışarı verme."""
    from database import get_db

    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id").fetchall()]


def kullanici_getir(user_id: int) -> Optional[dict]:
    from database import get_db

    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def kullanici_chat_id_ile(chat_id: str) -> Optional[dict]:
    """Telegram chat_id'sinden kullanıcıyı bulur; tanımadığı chat için None."""
    if not chat_id:
        return None
    from database import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_chat_id = ?", (str(chat_id),)
        ).fetchone()
    return dict(row) if row else None


def panel_login_enabled() -> bool:
    """Panel girişi ancak kayıtlı en az bir kullanıcı varsa çalışır."""
    try:
        return bool(tum_kullanicilar())
    except Exception:          # tablo henüz kurulmamışsa giriş kapalı sayılır
        return False


def check_panel_password(password: str) -> Optional[dict]:
    """Parolayı kayıtlı kullanıcılara karşı dener; eşleşeni döner, yoksa None.

    Kullanıcı adı sorulmuyor: iki kişilik bir sistemde parolanın kendisi kimin
    girdiğini söylüyor, giriş ekranı da olduğu gibi kalıyor.

    ⚠️ Kilitleme sayacı **global**. Parola kime ait olduğu bilinmeden önce
    kilitlemeyi kişiye bağlayamıyoruz (kullanıcı adı yok). Yani biri art arda
    8 kez yanlış girerse diğeri de 15 dakika giremez. İki kişilik bir evde
    kabul edilebilir; üçüncü kişi eklenirse giriş ekranına isim koymak gerekir.
    """
    global _failed_attempts, _locked_until

    kullanicilar = tum_kullanicilar()
    if not kullanicilar:
        raise HTTPException(
            status_code=503,
            detail="Panel girişi sunucuda ayarlanmamış (kayıtlı kullanıcı yok)",
        )

    if time.time() < _locked_until:
        remaining = int((_locked_until - time.time()) / 60) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Çok fazla hatalı deneme. {remaining} dakika sonra tekrar dene.",
        )

    for k in kullanicilar:
        if verify_password(password, k["parola_hash"]):
            _failed_attempts = 0
            return k

    _failed_attempts += 1
    if _failed_attempts >= _MAX_ATTEMPTS:
        _locked_until = time.time() + _LOCKOUT_SECONDS
        _failed_attempts = 0
    return None


async def verify_api_key(
    x_api_key: str = Header(default=""),
    prism_session: Optional[str] = Cookie(default=None),
) -> dict:
    """Doğrular VE giriş yapan kullanıcıyı döner.

    Eskiden yalnızca bir kapıydı (geçer ya da 401). Artık kimliği de o taşıyor:
    rotalar `user: dict = Depends(verify_api_key)` yazarak kimin bağlandığını
    öğreniyor. FastAPI aynı bağımlılığı istek başına bir kez çalıştırdığı için
    `main.py`'deki router seviyesindeki koruma da aynı sonucu paylaşıyor.

    ⚠️ `X-API-Key` başlığı tek bir env değeri ve **1 numaralı kullanıcıya**
    (Eyüp) bağlanıyor — Android uygulamasını yalnız o kullanıyor, Zeynep
    iPhone'da. İkinci bir Android kullanıcısı olursa anahtarların kullanıcı
    başına `users` tablosuna taşınması gerekir; banka bildiriminden gelen
    harcamalar aksi hâlde yanlış kişiye yazılır.
    """
    from modules.auth.models import SAHIP_VARSAYILAN

    expected = os.getenv("API_KEY", "")

    if not expected:                       # lokal geliştirme: doğrulama kapalı
        kullanicilar = tum_kullanicilar()
        if kullanicilar:
            return kullanicilar[0]
        raise HTTPException(status_code=503, detail="Kayıtlı kullanıcı yok")

    if x_api_key and secrets.compare_digest(x_api_key, expected):
        k = kullanici_getir(SAHIP_VARSAYILAN)
        if k:
            return k
        raise HTTPException(status_code=503, detail="API anahtarının sahibi bulunamadı")

    if prism_session:
        uid = session_user_id(prism_session)
        if uid is not None:
            k = kullanici_getir(uid)
            if k:
                return k
            # Bilet geçerli imzalı ama kullanıcı silinmiş — oturumu düşür.
            raise HTTPException(status_code=401, detail="Oturum artık geçerli değil")

    raise HTTPException(status_code=401, detail="Geçersiz veya eksik API anahtarı")
