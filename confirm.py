"""Onay bekleyen yıkıcı işlemler.

AI bir mesajı yanlış anlayıp yanlış kaydı silebilir; silinen hatırlatıcı veya not
geri gelmez. Bu yüzden AI üzerinden gelen silme istekleri doğrudan uygulanmıyor,
Telegram'a "şunu silecektim, onaylıyor musun?" diye butonlu bir mesaj gidiyor.

REST uçları (panel, Android) bu akıştan etkilenmez — orada kullanıcı zaten hangi
satırın çöp kutusuna bastığını görüyor, ikinci bir onay gereksiz sürtünme olurdu.

Bellekte tutuluyor: onay 5 dakika içinde verilmezse düşer. Servis yeniden
başlarsa da düşer — kalıcı saklamaya değmeyecek kadar geçici bir bilgi.
"""

import secrets
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

TTL_SECONDS = 300
MAX_PENDING = 20

_pending: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def _prune():
    cutoff = time.time() - TTL_SECONDS
    for token in [t for t, v in _pending.items() if v["at"] < cutoff]:
        _pending.pop(token, None)
    while len(_pending) > MAX_PENDING:
        _pending.popitem(last=False)


def remember(action: Dict[str, Any]) -> str:
    """Onay bekleyen işlemi saklar, butona konacak kısa anahtarı döner."""
    _prune()
    token = secrets.token_urlsafe(6)
    _pending[token] = {"at": time.time(), "action": action}
    return token


def take(token: str) -> Optional[Dict[str, Any]]:
    """Anahtarı tüketir (tek kullanımlık). Süresi dolmuşsa None."""
    _prune()
    entry = _pending.pop(token, None)
    return entry["action"] if entry else None
