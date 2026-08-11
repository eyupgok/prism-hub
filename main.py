import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from logging_setup import get_logger, setup_logging

setup_logging()
log = get_logger("prism.main")

from auth import verify_api_key
from database import init_db
from scheduler import start_scheduler, stop_scheduler
from telegram_bot import router as telegram_router, set_webhook
from modules.auth.routes import router as auth_router
from modules.chat.routes import router as chat_router
from modules.reminders.routes import router as reminders_router
from modules.notes.routes import router as notes_router
from modules.expenses.routes import router as expenses_router, budget_router
from modules.weather.routes import router as weather_router
from modules.summary.routes import router as summary_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()

    if not os.getenv("API_KEY", ""):
        log.warning("API_KEY ayarlanmamış — REST API doğrulaması DEVRE DIŞI (sadece lokal geliştirme için uygundur)")
    elif not os.getenv("PANEL_PASSWORD", ""):
        log.warning("PANEL_PASSWORD ayarlanmamış — web paneline giriş yapılamaz (API_KEY ile REST erişimi çalışır)")

    webhook_url = os.getenv("WEBHOOK_URL", "").rstrip("/")
    if webhook_url:
        await set_webhook(f"{webhook_url}/webhook")
    else:
        log.warning("WEBHOOK_URL ayarlanmamış — Telegram webhook kurulmadı")

    yield

    stop_scheduler()


app = FastAPI(
    title="PRISM — Kişisel AI Asistan Hub",
    description="Telegram üzerinden yönetilen modüler AI asistan sistemi",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: CORS_ORIGINS env'i virgülle ayrılmış origin listesi (örn: frontend URL'i).
# Boş bırakılırsa tüm origin'lere izin verilir. Auth cookie değil header tabanlı
# olduğundan allow_credentials kapalı ("*" + credentials geçersiz kombinasyondu).
_cors_origins = [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /webhook API key gerektirmez (Telegram çağırır); tüm /api/* rotaları korunur.
# /api/auth/* de korumasızdır — giriş yapabilmek için giriş yapmış olmak gerekemez.
protected = [Depends(verify_api_key)]

app.include_router(telegram_router)
app.include_router(auth_router)
app.include_router(chat_router, dependencies=protected)
app.include_router(reminders_router, dependencies=protected)
app.include_router(notes_router, dependencies=protected)
app.include_router(expenses_router, dependencies=protected)
app.include_router(budget_router, dependencies=protected)
app.include_router(weather_router, dependencies=protected)
app.include_router(summary_router, dependencies=protected)


@app.get("/health")
async def health(response: Response):
    """Dışarıdan izleme için sağlık kontrolü.

    Sadece "ayaktayım" demek yetmiyor: veritabanı okunamıyorsa, zamanlayıcı
    durmuşsa ya da hatırlatıcı döngüsü takılmışsa servis çalışıyor görünür ama
    işe yaramaz. İzleme servisi bunu fark edebilsin diye üçü de kontrol ediliyor
    ve bozuksa 503 dönüyor.
    """
    checks = {"database": "ok", "scheduler": "ok", "reminder_loop": "ok"}

    try:
        from database import get_db

        with get_db() as conn:
            conn.execute("SELECT 1 FROM reminders LIMIT 1").fetchone()
    except Exception as e:
        checks["database"] = f"hata: {type(e).__name__}"
        log.error("Sağlık kontrolü — veritabanı okunamadı", exc_info=True)

    try:
        import scheduler as sched

        if not sched.scheduler.running:
            checks["scheduler"] = "durmuş"

        age = sched.reminder_loop_age_seconds()
        if age is None:
            checks["reminder_loop"] = "hiç çalışmadı"
        elif age > sched.REMINDER_HEARTBEAT_TIMEOUT_SECONDS:
            checks["reminder_loop"] = f"takılmış (son tur {int(age // 60)} dk önce)"
    except Exception as e:
        checks["scheduler"] = f"hata: {type(e).__name__}"

    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = 503

    return {"status": "ok" if healthy else "degraded", "service": "PRISM", "checks": checks}
