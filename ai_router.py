import os
import json
from datetime import datetime
from typing import Dict, Any, List
import pytz
from groq import AsyncGroq

TZ = pytz.timezone("Europe/Istanbul")

SYSTEM_PROMPT = """\
Sen PRISM'sin — Eyüp'ün kişisel AI asistanı. Görevin Eyüp'ün günlük hayatını organize etmek: hatırlatıcılar, notlar, harcamalar, bütçe, hava durumu ve günlük özet.

Eyüp Türkçe konuşur. Mesajları analiz et ve SADECE JSON formatında yanıt ver, başka hiçbir şey yazma.

## KİMLİĞİN
- Adın PRISM
- Eyüp'ün kişisel asistanısın
- Samimi ama profesyonelsin
- Türkçe düşün, Türkçe yanıt ver

## MODÜLLER VE AKSIYONLAR

reminders.create → title(str), due_datetime(ISO 8601: {today}T14:30:00), priority(1=Kritik 2=Önemli 3=Normal), recurrence(none|daily|weekly|monthly)
reminders.list → params boş
reminders.update → id(int), title(str opsiyonel), due_datetime(ISO 8601 opsiyonel), priority(int opsiyonel)
reminders.complete → id(int)
reminders.delete → id(int)

notes.create → title(str), content(str), category(iş|kişisel|genel|ders|fikir)
notes.list → category(str opsiyonel)
notes.read → id(int)
notes.search → query(str)
notes.delete → id(int)

expenses.create → amount(float), category(yemek|ulaşım|eğlence|fatura|alışveriş|diğer), description(str opsiyonel)
expenses.list → month(YYYY-MM opsiyonel)
expenses.summary → month(YYYY-MM opsiyonel)
expenses.delete → id(int)

budget.set → category(yemek|ulaşım|eğlence|fatura|alışveriş|diğer), amount(float)
budget.list → params boş
budget.delete → category(str)

weather.get → params boş
summary.get → params boş

## ZAMAN İFADELERİ
Şu an: {now} (Europe/Istanbul)
Bugün: {today}

Türkçe zaman ifadelerini şöyle çevir:
- "yarın" → yarının tarihi
- "bugün" → bugünün tarihi
- "öğlen / öğle" → 12:00
- "sabah" → 09:00
- "akşam" → 18:00
- "gece" → 21:00
- "öğleden sonra 2" → 14:00
- "saat 2" → bağlama göre 14:00 veya 02:00 (gündüz varsay)
- "pazartesi", "salı" vb. → gelecek o günün tarihi
- "hafta sonu" → gelecek cumartesi
- "bu akşam" → bugün 18:00
- "bu gece" → bugün 21:00

Saat yorumlama kuralları:
- Kullanıcı "bugün saat X'e" derse ve o saat geçmişse, otomatik olarak akşam versiyonunu al (örn: saat 9 geçtiyse 21:00 yap)
- "sabah X" → her zaman AM (09:00 gibi)
- "akşam X" veya "gece X" → her zaman PM (21:00 gibi)
- Saat belirtilmeden sadece rakam varsa ve geçmişse → 12 ekle (PM'e çevir)
- Asla geçmiş bir saate hatırlatıcı kurma

## HATIRLATICI YARATMA KURALLARI
Şu ifadeler hatırlatıcı anlamına gelir:
"hatırlatıcı kur/ekle", "unutma", "randevum var", "toplantım var", "sınavım var", "teslim tarihi", "deadline", "başvuru", "ödev", "hatırlat"

Tekrarlama belirleme:
- "her gün", "günlük" → recurrence: daily
- "her hafta", "haftalık", "her pazartesi" vb. → recurrence: weekly
- "her ay", "aylık" → recurrence: monthly
- belirtilmemişse → recurrence: none

Öncelik belirleme:
- "kritik", "çok önemli", "acil", "kesinlikle" → priority: 1
- "önemli", "unutma" → priority: 2
- belirtilmemişse → priority: 2
- "önemsiz", "küçük" → priority: 3

## NOT ALMA KURALLARI
Şu ifadeler not anlamına gelir:
"not al", "yaz", "kaydet", "aklımda kalsın", "unutmayayım"

## HARCAMA KURALLARI
Şu ifadeler harcama anlamına gelir:
"harcadım", "ödedim", "aldım", "TL", "lira", "para"

## SOHBET
Eğer mesaj hiçbir kategoriye girmiyorsa, PRISM olarak samimi ve kısa Türkçe yanıt ver:
{{"module": "chat", "action": "respond", "params": {{"message": "..."}}}}

Selamlaşma, teşekkür, "nasılsın" gibi sorulara da sohbet modunda yanıt ver ama PRISM kimliğini koru.

## ÖNEMLİ
- SADECE JSON döndür, açıklama yazma
- due_datetime her zaman ISO 8601 formatında olsun: YYYY-MM-DDTHH:MM:SS
- Eğer saat belirtilmemişse ve gün varsa 09:00 varsay
- Eğer belirsizlik varsa en mantıklı yorumu yap, kullanıcıya soru sorma
- Konuşma geçmişini kullanarak "onu", "bunu", "onu sil" gibi referansları çöz\
"""

GROQ_MODEL = "llama-3.3-70b-versatile"
HISTORY_LIMIT = 10


def _groq_client() -> AsyncGroq:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY ortam değişkeni ayarlanmamış")
    return AsyncGroq(api_key=key)


async def parse_message(user_message: str, history: List[Dict] = None) -> Dict[str, Any]:
    """Kullanıcı mesajını Groq'a gönderir ve JSON komut olarak döner"""
    now_str = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")
    system = SYSTEM_PROMPT.format(now=now_str, today=today_str)

    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    client = _groq_client()
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=400,
    )

    raw = response.choices[0].message.content.strip()

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

        if module == "budget":
            return await _handle_budget(action, params)

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
            r = svc.create_reminder(
                conn,
                params["title"],
                params["due_datetime"],
                params.get("priority", 2),
                params.get("recurrence", "none"),
            )
            due = svc.parse_dt(r["due_datetime"])
            msg = (
                f"✅ Hatırlatıcı oluşturuldu!\n"
                f"📌 {r['title']}\n"
                f"📅 {svc.format_dt(due)}\n"
                f"🏷 {svc.PRIORITY_NAMES.get(r['priority'], 'Normal')}"
            )
            rec_label = svc.RECURRENCE_LABELS.get(r.get("recurrence", "none"), "")
            if rec_label:
                msg += f"\n🔁 {rec_label}"
            return msg

        if action == "list":
            reminders = svc.list_reminders(conn, False)
            if not reminders:
                return "📋 Aktif hatırlatıcı yok."
            lines = ["📋 <b>Hatırlatıcılarınız:</b>\n"]
            for r in reminders:
                due = svc.parse_dt(r["due_datetime"])
                emoji = svc.PRIORITY_EMOJIS.get(r["priority"], "🟢")
                rec = " 🔁" if r.get("recurrence", "none") != "none" else ""
                lines.append(f"{emoji} [{r['id']}] {r['title']} — {svc.format_dt(due)}{rec}")
            return "\n".join(lines)

        if action == "update":
            r = svc.update_reminder(
                conn,
                params.get("id"),
                params.get("title"),
                params.get("due_datetime"),
                params.get("priority"),
            )
            if not r:
                return "❌ Hatırlatıcı bulunamadı."
            due = svc.parse_dt(r["due_datetime"])
            return (
                f"✏️ Hatırlatıcı güncellendi!\n"
                f"📌 {r['title']}\n"
                f"📅 {svc.format_dt(due)}\n"
                f"🏷 {svc.PRIORITY_NAMES.get(r['priority'], 'Normal')}"
            )

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

        if action == "read":
            n = svc.get_note_by_id(conn, params.get("id"))
            if not n:
                return "❌ Not bulunamadı."
            return f"📝 <b>{n['title']}</b>\n🏷 {n['category']}\n\n{n['content']}"

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
            lines = ["🔍 <b>Arama sonuçları:</b>\n"] + [
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
            msg = (
                f"💰 Harcama kaydedildi!\n"
                f"💵 {e['amount']:.2f} TL — {e['category']}\n"
                f"📝 {e['description'] or '—'}"
            )
            alert = svc.check_budget_alert(conn, e["category"])
            if alert:
                msg += f"\n\n{alert}"
            return msg

        if action == "list":
            expenses = svc.list_expenses(conn, params.get("month"))
            if not expenses:
                return "💰 Harcama bulunamadı."
            total = sum(e["amount"] for e in expenses)
            lines = ["💰 <b>Harcamalar:</b>\n"]
            for e in expenses[:10]:
                lines.append(
                    f"• [{e['id']}] {e['expense_date']} | {e['amount']:.0f} TL | {e['category']} | {e['description'] or '—'}"
                )
            lines.append(f"\n<b>Toplam: {total:.0f} TL</b>")
            return "\n".join(lines)

        if action == "summary":
            s = svc.get_monthly_summary(conn, params.get("month"))
            lines = [f"📊 <b>{s['month']} Harcama Özeti:</b>\n", f"💰 Toplam: {s['total']:.0f} TL\n"]
            for cat, total in sorted(s["by_category"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  • {cat}: {total:.0f} TL")
            return "\n".join(lines)

        if action == "delete":
            ok = svc.delete_expense(conn, params.get("id"))
            return "🗑 Harcama silindi." if ok else "❌ Harcama bulunamadı."

    return f"❓ Bilinmeyen aksiyon: {action}"


async def _handle_budget(action: str, params: Dict) -> str:
    from database import get_db
    from modules.expenses import service as svc

    with get_db() as conn:
        if action == "set":
            b = svc.set_budget(conn, params["category"], float(params["amount"]))
            return f"✅ Bütçe limiti ayarlandı!\n🏷 {b['category']}: {b['monthly_limit']:.0f} TL/ay"

        if action == "list":
            budgets = svc.get_all_budgets(conn)
            if not budgets:
                return "📊 Henüz bütçe limiti ayarlanmamış.\n💡 Örnek: 'Yemek için aylık 3000 TL bütçe koy'"
            lines = ["📊 <b>Aylık Bütçe Limitleri:</b>\n"]
            month = datetime.now(TZ).strftime("%Y-%m")
            for b in budgets:
                alert = svc.check_budget_alert(conn, b["category"], month)
                status = "🚨" if alert and "aşıldı" in alert else ("⚠️" if alert else "✅")
                lines.append(f"{status} {b['category']}: {b['monthly_limit']:.0f} TL/ay")
            return "\n".join(lines)

        if action == "delete":
            ok = svc.delete_budget(conn, params.get("category", ""))
            return "🗑 Bütçe limiti kaldırıldı." if ok else "❌ Kategori bulunamadı."

    return f"❓ Bilinmeyen aksiyon: {action}"


async def route_message(user_message: str, chat_id: str = "") -> str:
    """Ana giriş: mesajı Groq'a gönderir, modüle yönlendirir, cevabı döner"""
    from database import save_message, get_recent_messages

    try:
        history = get_recent_messages(chat_id, HISTORY_LIMIT) if chat_id else []
        parsed = await parse_message(user_message, history)
        response = await dispatch(parsed)

        if chat_id:
            save_message(chat_id, "user", user_message)
            save_message(chat_id, "assistant", json.dumps(parsed, ensure_ascii=False))

        return response
    except json.JSONDecodeError:
        return "⚠️ AI yanıtı işlenemedi. Lütfen mesajınızı farklı şekilde ifade edin."
    except Exception as e:
        return f"⚠️ Hata oluştu: {e}"
