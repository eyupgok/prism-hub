import os
import json
import httpx
from datetime import datetime
from typing import Dict, Any
import pytz

TZ = pytz.timezone("Europe/Istanbul")

SYSTEM_PROMPT = """\
Sen bir kişisel asistan AI'sın. Kullanıcının mesajını analiz et ve \
SADECE aşağıdaki JSON formatında yanıt ver, başka hiçbir şey yazma:

{{"module": "reminders", "action": "create", "params": {{"title": "...", "due_datetime": "ISO_DATETIME", "priority": 1}}}}

Desteklenen modül/aksiyon çiftleri ve parametreler:

reminders.create  → title(str), due_datetime(ISO 8601, ör: {today}T14:30:00), priority(1=Kritik 2=Önemli 3=Normal)
reminders.list    → params boş
reminders.complete → id(int)
reminders.delete   → id(int)

notes.create → title(str), content(str), category(str opsiyonel, ör: iş/kişisel/genel)
notes.list   → category(str opsiyonel)
notes.search → query(str)
notes.delete → id(int)

expenses.create  → amount(float), category(yemek|ulaşım|eğlence|fatura|diğer), description(str opsiyonel)
expenses.list    → month(YYYY-MM opsiyonel)
expenses.summary → month(YYYY-MM opsiyonel)

weather.get → params boş
summary.get → params boş

Eğer mesaj bu kategorilere girmiyorsa doğal dilde cevap ver:
{{"module": "chat", "action": "respond", "params": {{"message": "..."}}}}

Bugünün tarihi ve saati: {now}
Kullanıcının timezone: Europe/Istanbul\
"""


def _build_url() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"


async def parse_message(user_message: str) -> Dict[str, Any]:
    """Kullanıcı mesajını Gemini'ye gönderir ve JSON komut olarak döner"""
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")
    system = SYSTEM_PROMPT.format(now=now_str, today=today_str)

    payload = {
        "system_instruction": {
            "parts": [{"text": system}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": user_message}]}
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 300,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(_build_url(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Markdown code block varsa temizle
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


async def dispatch(parsed: Dict[str, Any]) -> str:
    """Parse edilmiş JSON komutunu ilgili servis fonksiyonuna yönlendirir"""
    module = parsed.get("module")
    action = parsed.get("action")
    params = parsed.get("params", {})

    try:
        if module == "chat":
            return params.get("message", "Nasıl yardımcı olabilirim?")

        if module == "reminders":
            return await _handle_reminders(action, params)

        if module == "notes":
            return await _handle_notes(action, params)

        if module == "expenses":
            return await _handle_expenses(action, params)

        if module == "weather":
            from modules.weather import service as weather_svc
            weather = await weather_svc.get_weather()
            return weather_svc.format_weather_message(weather)

        if module == "summary":
            from modules.summary import service as summary_svc
            return await summary_svc.get_morning_summary()

        return f"❓ Bilinmeyen modül: {module}"

    except Exception as e:
        return f"⚠️ İşlem sırasında hata oluştu: {e}"


async def _handle_reminders(action: str, params: Dict) -> str:
    from database import get_db
    from modules.reminders import service as svc

    with get_db() as conn:
        if action == "create":
            r = svc.create_reminder(conn, params["title"], params["due_datetime"], params.get("priority", 3))
            due = svc.parse_dt(r["due_datetime"])
            return (
                f"✅ Hatırlatıcı oluşturuldu!\n"
                f"📌 {r['title']}\n"
                f"📅 {svc.format_dt(due)}\n"
                f"🏷 {svc.PRIORITY_NAMES.get(r['priority'], 'Normal')}"
            )

        if action == "list":
            reminders = svc.list_reminders(conn, False)
            if not reminders:
                return "📋 Aktif hatırlatıcı yok."
            lines = ["📋 <b>Hatırlatıcılarınız:</b>\n"]
            for r in reminders:
                due = svc.parse_dt(r["due_datetime"])
                emoji = svc.PRIORITY_EMOJIS.get(r["priority"], "🟢")
                lines.append(f"{emoji} [{r['id']}] {r['title']} — {svc.format_dt(due)}")
            return "\n".join(lines)

        if action == "complete":
            r = svc.complete_reminder(conn, params.get("id"))
            return f"✅ '{r['title']}' tamamlandı!" if r else "❌ Hatırlatıcı bulunamadı."

        if action == "delete":
            ok = svc.delete_reminder(conn, params.get("id"))
            return "🗑 Hatırlatıcı silindi." if ok else "❌ Hatırlatıcı bulunamadı."

    return f"❓ Bilinmeyen aksiyon: {action}"


async def _handle_notes(action: str, params: Dict) -> str:
    from database import get_db
    from modules.notes import service as svc

    with get_db() as conn:
        if action == "create":
            n = svc.create_note(conn, params["title"], params["content"], params.get("category", "genel"))
            return f"📝 Not kaydedildi!\n📌 {n['title']}\n🏷 {n['category']}"

        if action == "list":
            cat = params.get("category")
            notes = svc.list_notes(conn, cat)
            if not notes:
                return "📝 Not bulunamadı."
            header = f"📝 <b>Notlar{' — ' + cat if cat else ''}:</b>\n"
            lines = [header] + [f"• [{n['id']}] {n['title']} ({n['category']})" for n in notes[:10]]
            return "\n".join(lines)

        if action == "search":
            notes = svc.search_notes(conn, params.get("query", ""))
            if not notes:
                return f"🔍 '{params.get('query')}' için sonuç bulunamadı."
            lines = [f"🔍 <b>Arama sonuçları:</b>\n"] + [
                f"• [{n['id']}] {n['title']}" for n in notes[:10]
            ]
            return "\n".join(lines)

        if action == "delete":
            ok = svc.delete_note(conn, params.get("id"))
            return "🗑 Not silindi." if ok else "❌ Not bulunamadı."

    return f"❓ Bilinmeyen aksiyon: {action}"


async def _handle_expenses(action: str, params: Dict) -> str:
    from database import get_db
    from modules.expenses import service as svc

    with get_db() as conn:
        if action == "create":
            e = svc.create_expense(
                conn,
                params["amount"],
                params.get("category", "diğer"),
                params.get("description", ""),
            )
            return (
                f"💰 Harcama kaydedildi!\n"
                f"💵 {e['amount']:.2f} TL — {e['category']}\n"
                f"📝 {e['description'] or '—'}"
            )

        if action == "list":
            expenses = svc.list_expenses(conn, params.get("month"))
            if not expenses:
                return "💰 Harcama bulunamadı."
            total = sum(e["amount"] for e in expenses)
            lines = ["💰 <b>Harcamalar:</b>\n"]
            for e in expenses[:10]:
                lines.append(f"• {e['expense_date']} | {e['amount']:.0f} TL | {e['category']} | {e['description'] or '—'}")
            lines.append(f"\n<b>Toplam: {total:.0f} TL</b>")
            return "\n".join(lines)

        if action == "summary":
            s = svc.get_monthly_summary(conn, params.get("month"))
            lines = [f"📊 <b>{s['month']} Harcama Özeti:</b>\n", f"💰 Toplam: {s['total']:.0f} TL\n"]
            for cat, total in sorted(s["by_category"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {cat}: {total:.0f} TL")
            return "\n".join(lines)

    return f"❓ Bilinmeyen aksiyon: {action}"


async def route_message(user_message: str) -> str:
    """Ana giriş: mesajı Gemini'ye gönderir, modüle yönlendirir, cevabı döner"""
    try:
        parsed = await parse_message(user_message)
        return await dispatch(parsed)
    except json.JSONDecodeError:
        return "⚠️ AI yanıtı işlenemedi. Lütfen mesajınızı farklı şekilde ifade edin."
    except Exception as e:
        return f"⚠️ Hata oluştu: {e}"
