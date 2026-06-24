import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# .env dosyasını en başta yükle
load_dotenv()

from database import init_db
from scheduler import start_scheduler, stop_scheduler
from telegram_bot import router as telegram_router, set_webhook
from modules.reminders.routes import router as reminders_router
from modules.notes.routes import router as notes_router
from modules.expenses.routes import router as expenses_router
from modules.weather.routes import router as weather_router
from modules.summary.routes import router as summary_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Başlangıç ---
    init_db()
    start_scheduler()

    webhook_url = os.getenv("WEBHOOK_URL", "").rstrip("/")
    if webhook_url:
        await set_webhook(f"{webhook_url}/webhook")
    else:
        print("⚠️  WEBHOOK_URL ayarlanmamış — Telegram webhook kurulmadı")

    yield

    # --- Kapanış ---
    stop_scheduler()


app = FastAPI(
    title="PRISM — Kişisel AI Asistan Hub",
    description="Telegram + Web panel üzerinden yönetilen modüler AI asistan sistemi",
    version="1.0.0",
    lifespan=lifespan,
)

# Geniş CORS — ilerisi için mobil uygulama desteği
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telegram webhook
app.include_router(telegram_router)

# API rotaları
app.include_router(reminders_router)
app.include_router(notes_router)
app.include_router(expenses_router)
app.include_router(weather_router)
app.include_router(summary_router)

# Statik dosyalar
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_panel():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "PRISM"}
