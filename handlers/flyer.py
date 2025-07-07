import os
import json
import re
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from pyrogram import filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# ─── Paths & Scheduler ─────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent
DATA_DIR    = ROOT / "data"
FLYER_PATH  = DATA_DIR / "flyers.json"
SUPER_ADMIN = 6964994611

DATA_DIR.mkdir(exist_ok=True)

# read your desired timezone from env (e.g. "America/Los_Angeles")
TZ = os.getenv("SCHEDULER_TZ", "UTC")

# scheduler now runs in that timezone
scheduler = BackgroundScheduler(timezone=TZ)
scheduler.start()

# ─── Helpers ────────────────────────────────────────────────────────────
async def is_admin(client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN:
        return True
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False

def load_flyers():
    if not FLYER_PATH.exists():
        return {}
    return json.loads(FLYER_PATH.read_text())

def save_flyers(data):
    FLYER_PATH.write_text(json.dumps(data))
    logger.debug("Saved flyers.json: %s", data)

# ─── Registration ───────────────────────────────────────────────────────
def register(app):
    CHAT = filters.group | filters.channel

    @app.on_message(filters.command(["addflyer","createflyer"]) & (filters.photo|filters.reply) & CHAT)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ Admins only.")
        if message.reply_to_message and message.reply_to_message.photo:
            file_id = message.reply_to_message.photo.file_id
            raw     = message.text or ""
        elif message.photo:
            file_id = message.photo.file_id
            raw     = message.caption or ""
        else:
            return await message.reply_text("Usage: reply to or send image with `/addflyer <name> <ad>`")
        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            return await message.reply_text("❌ Usage: `/addflyer <name> <ad>`")
        name, ad = parts[1].lower(), parts[2]
        data = load_flyers()
        chat = str(message.chat.id)
        data.setdefault(chat, {})
        if name in data[chat]:
            return await message.reply_text(f"❌ Flyer “{name}” exists.")
        data[chat][name] = {"file_id": file_id, "ad": ad}
        save_flyers(data)
        await message.reply_text(f"✅ Flyer “{name}” added!")

    @app.on_message(filters.command("listflyers") & CHAT)
    async def list_flyers(client, message: Message):
        items = load_flyers().get(str(message.chat.id), {})
        if not items:
            return await message.reply_text("❌ No flyers.")
        out = "\n".join(f"• {n}" for n in items)
        await message.reply_text(f"<b>Flyers:</b>\n{out}")

    @app.on_message(filters.command("flyer") & CHAT)
    async def get_flyer(client, message: Message):
        parts = message.text.split(maxsplit=1)
        if len(parts)<2:
            return await message.reply_text("❌ Usage: `/flyer <name>`")
        name = parts[1].lower()
        entry = load_flyers().get(str(message.chat.id),{}).get(name)
        if not entry:
            return await message.reply_text(f"❌ No flyer “{name}” found.")
        await client.send_photo(message.chat.id, entry["file_id"], caption=entry["ad"])

    @app.on_message(filters.command("scheduleflyer") & CHAT)
    async def schedule_flyer(client, message: Message):
        parts = message.text.split(maxsplit=2)
        if len(parts)<3:
            return await message.reply_text(
                "Usage:\n"
                "`/scheduleflyer <name> YYYY-MM-DD HH:MM`\n"
                "`/scheduleflyer <name> HH:MM Mon,Tue…|daily`"
            )
        name, rest = parts[1].lower(), parts[2].strip()
        entry = load_flyers().get(str(message.chat.id),{}).get(name)
        if not entry:
            return await message.reply_text(f"❌ No flyer “{name}” found.")

        # split into date_part/time_part (one-off) or rec time/days
        date_part, time_part = (rest.split(" ",1)+[None])[:2]
        # — One-off if starts with YYYY-M-D
        if date_part and re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", date_part):
            y,m,d = date_part.split("-")
            dt_str = f"{y}-{m.zfill(2)}-{d.zfill(2)} {time_part}"
            try:
                run_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            except:
                return await message.reply_text("❌ Invalid date/time. Use YYYY-MM-DD HH:MM")
            # tag with your local timezone
            run_date = run_date.replace(tzinfo=ZoneInfo(TZ))
            job = scheduler.add_job(
                client.send_photo,
                trigger=DateTrigger(run_date),
                args=[message.chat.id, entry["file_id"]],
                kwargs={"caption": entry["ad"]}
            )
            return await message.reply_text(
                f"✅ One-off “{name}” scheduled (id {job.id}) for {run_date:%Y-%m-%d %H:%M} {TZ}"
            )

        # — Recurring fallback
        rec = rest.split(maxsplit=1)
        if len(rec)<2:
            return await message.reply_text("❌ Recurring: `/scheduleflyer <name> HH:MM Mon,Tue…|daily`")
        t_str, days_str = rec
        try:
            hour, minute = map(int, t_str.split(":"))
        except:
            return await message.reply_text("❌ Invalid time. Use HH:MM")
        mapping = {
            'mon':'mon','monday':'mon',
            'tue':'tue','tuesday':'tue',
            'wed':'wed','wednesday':'wed',
            'thu':'thu','thursday':'thu',
            'fri':'fri','friday':'fri',
            'sat':'sat','saturday':'sat',
            'sun':'sun','sunday':'sun'
        }
        if days_str.lower()=="daily":
            dow = list(mapping.values())
        else:
            dow = []
            for d in days_str.split(","):
                tok = mapping.get(d.strip().lower())
                if not tok:
                    return await message.reply_text("❌ Bad days – use Mon,Tue… or daily")
                dow.append(tok)
        job = scheduler.add_job(
            client.send_photo,
            trigger=CronTrigger(day_of_week=",".join(dow), hour=hour, minute=minute, timezone=TZ),
            args=[message.chat.id, entry["file_id"]],
            kwargs={"caption": entry["ad"]}
        )
        return await message.reply_text(
            f"✅ Recurring “{name}” scheduled (id {job.id}) {days_str} at {t_str} {TZ}"
        )

    @app.on_message(filters.command("listjobs") & CHAT)
    async def list_jobs(client, message: Message):
        js = scheduler.get_jobs()
        if not js:
            return await message.reply_text("❌ No jobs.")
        out = "\n".join(f"• {j.id} → {j.next_run_time}" for j in js)
        await message.reply_text(f"🗓 Scheduled jobs:\n{out}")

    @app.on_message(filters.command("cancelschedule") & CHAT)
    async def cancel_schedule(client, message: Message):
        parts = message.text.split(maxsplit=1)
        jid = parts[1].strip() if len(parts)>1 else None
        if not jid:
            return await message.reply_text("❌ Usage: `/cancelschedule <job_id>`")
        try:
            scheduler.remove_job(jid)
            await message.reply_text(f"✅ Cancelled job `{jid}`")
        except:
            await message.reply_text(f"❌ No job found with id `{jid}`")
