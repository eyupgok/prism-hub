"""Tek yerden loglama ayarı.

Neden `print()` yetmiyordu: seviye yok (bilgi mi hata mı belli değil), zaman
damgası yok, hata izi yok. `journalctl -u prism` çıktısında bir sorunu ararken
bunların üçü de gerekiyor.

Çıktı stdout'a gider; systemd onu journald'a yazar. Ayrıca dosyaya yazmıyoruz —
journald zaten döndürüyor (rotate), ikinci bir dosya yönetmeye değmez.
"""

import logging
import os
import sys

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

_FORMAT = "%(asctime)s %(levelname)-7s %(name)-22s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # httpx her istek için INFO satırı basıyor; Telegram'a dakikada birkaç istek
    # gittiği için kayıtları boğuyor. Uyarı ve üstü yeterli.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # APScheduler her iş eklemesini ve çalıştırmasını duyuruyor — 1 dakikalık bir iş
    # olduğu için kayıtlar tamamen bununla doluyor. Kendi açılış satırımız zaten var.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
