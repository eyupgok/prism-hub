import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from auth import verify_api_key
from database import init_db
from scheduler import start_scheduler, stop_scheduler
from telegram_bot import router as telegram_router, set_webhook
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
        print("⚠️  API_KEY ayarlanmamış — REST API doğrulaması DEVRE DIŞI (sadece lokal geliştirme için uygundur)")

    webhook_url = os.getenv("WEBHOOK_URL", "").rstrip("/")
    if webhook_url:
        await set_webhook(f"{webhook_url}/webhook")
    else:
        print("⚠️  WEBHOOK_URL ayarlanmamış — Telegram webhook kurulmadı")

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

# /webhook API key gerektirmez (Telegram çağırır); tüm /api/* rotaları korunur
protected = [Depends(verify_api_key)]

app.include_router(telegram_router)
app.include_router(chat_router, dependencies=protected)
app.include_router(reminders_router, dependencies=protected)
app.include_router(notes_router, dependencies=protected)
app.include_router(expenses_router, dependencies=protected)
app.include_router(budget_router, dependencies=protected)
app.include_router(weather_router, dependencies=protected)
app.include_router(summary_router, dependencies=protected)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "PRISM"}
