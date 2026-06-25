import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

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
    init_db()
    start_scheduler()

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telegram_router)
app.include_router(reminders_router)
app.include_router(notes_router)
app.include_router(expenses_router)
app.include_router(weather_router)
app.include_router(summary_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "PRISM"}
