import json
import re
import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from pyrogram import filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# ─── Paths & Scheduler ─────────────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).resolve().parent.parent
DATA_DIR       = PROJECT_ROOT / "data"
FLYER_PATH     = DATA_DIR / "flyers.json"
SUPER_ADMIN_ID = 6964994611

DATA_DIR.mkdir(parents=True, exist_ok=True)

scheduler = BackgroundScheduler()
scheduler.start()

# ─── Helpers ────────────────────────────────────────────────────────────
async def is_admin(client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
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
    CHAT_FILTER = filters.group | filters.channel

    @app.on_message(filters.command(["addflyer","createflyer"]) & (filters.photo|filters.reply) & CHAT_FILTER)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ You must be an admin to add flyers.")
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
            return await message.reply_text(f"❌ Flyer “{name}” already exists.")
        data[chat][name] = {"file_id": file_id, "ad": ad}
        save_flyers(data)
        await message.reply_text(f"✅ Flyer “{name}” added!")

    @app.on_message(filters.command(["changeflyer","updateflyer"]) & (filters.photo|filters.reply) & CHAT_FILTER)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ You must be an admin to change flyers.")
        if not (message.reply_to_message and message.reply_to_message.photo):
            return await message.reply_text("Usage: reply to image with `/changeflyer <name> [new ad]`")
        parts = message.text.split(maxsplit=2)
        name = parts[1].lower() if len(parts) > 1 else None
        new_ad = parts[2] if len(parts) == 3 else None
        file_id = message.reply_to_message.photo.file_id
        data = load_flyers()
        chat = str(message.chat.id)
        if not name or name not in data.get(chat, {}):
            return await message.reply_text(f"❌ No flyer named “{name}” found.")
        data[chat][name]["file_id"] = file_id
        if new_ad:
            data[chat][name]["ad"] = new_ad
        save_flyers(data)
        await message.reply_text(f"✅ Flyer “{name}” updated!")

    @app.on_message(filters.command(["deleteflyer","removeflyer"]) & CHAT_FILTER)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ You must be an admin to delete flyers.")
        parts = message.text.split(maxsplit=1)
        name = parts[1].lower() if len(parts) > 1 else None
        data = load_flyers()
        chat = str(message.chat.id)
        if not name or name not in data.get(chat, {}):
            return await message.reply_text(f"❌ No flyer named “{name}” found.")
        del data[chat][name]
        save_flyers(data)
        await message.reply_text(f"✅ Flyer “{name}” deleted!")

    @app.on_message(filters.command("listflyers") & CHAT_FILTER)
    async def list_flyers(client, message: Message):
        items = load_flyers().get(str(message.chat.id), {})
        if not items:
            return await message.reply_text("❌ No flyers have been added yet.")
        names = "\n".join(f"• {n}" for n in items)
        await message.reply_text(f"<b>Available flyers:</b>\n{names}")

    @app.on_message(filters.command(["flyer","getflyer"]) & CHAT_FILTER)
    async def get_flyer(client, message: Message):
        parts = message.text.split(maxsplit=1)
        name = parts[1].lower() if len(parts) > 1 else None
        entry = load_flyers().get(str(message.chat.id), {}).get(name)
        if not entry:
            return await message.reply_text(f"❌ No flyer named “{name}” found.")
        await client.send_photo(message.chat.id, entry["file_id"], caption=entry["ad"])

    @app.on_message(filters.command("scheduleflyer") & CHAT_FILTER)
    async def schedule_flyer(client, message: Message):
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            return await message.reply_text(
                "Usage:\n"
                "• One-off:   /scheduleflyer <name> <YYYY-MM-DD HH:MM>\n"
                "• Recurring: /scheduleflyer <name> <HH:MM> <Mon,Tue,...|daily>"
            )
        name, rest = parts[1].lower(), parts[2].strip()
        entry = load_flyers().get(str(message.chat.id), {}).get(name)
        if not entry:
            return await message.reply_text(f"❌ No flyer named “{name}” found.")

        date_part, time_part = (rest.split(" ",1) + [None])[:2]
        if date_part and re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", date_part):
            y,m,d = date_part.split("-")
            dt_str = f"{y}-{m.zfill(2)}-{d.zfill(2)} {time_part}"
            try:
                run_date = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            except:
                return await message.reply_text("❌ Invalid date/time. Use YYYY-MM-DD HH:MM")
            job = scheduler.add_job(
                client.send_photo,
                trigger=DateTrigger(run_date),
                args=[message.chat.id, entry["file_id"]],
                kwargs={"caption": entry["ad"]}
            )
            return await message.reply_text(f"✅ One-off “{name}” scheduled (job id: {job.id}) for {run_date:%Y-%m-%d %H:%M}")

        rec = rest.split(maxsplit=1)
        if len(rec) < 2:
            return await message.reply_text("❌ Recurring: `/scheduleflyer <name> <HH:MM> <Mon,Tue,...|daily>`")
        time_str, days_str = rec
        try:
            hour, minute = map(int, time_str.split(":"))
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
        dow = list(mapping.values()) if days_str.lower()=="daily" else [
            mapping.get(d.strip().lower()) for d in days_str.split(",")
        ]
        if any(d is None for d in dow):
            return await message.reply_text("❌ Invalid weekdays. Use Mon,Tue,... or daily.")
        job = scheduler.add_job(
            client.send_photo,
            trigger=CronTrigger(day_of_week=",".join(dow), hour=hour, minute=minute),
            args=[message.chat.id, entry["file_id"]],
            kwargs={"caption": entry["ad"]}
        )
        return await message.reply_text(f"✅ Recurring “{name}” scheduled (job id: {job.id}) {days_str} at {time_str}")

    @app.on_message(filters.command("listjobs") & CHAT_FILTER)
    async def list_jobs(client, message: Message):
        jobs = scheduler.get_jobs()
        if not jobs:
            return await message.reply_text("🗓 No scheduled jobs.")
        lines = [f"• {j.id} → next at {j.next_run_time}" for j in jobs]
        await message.reply_text("🗓 Scheduled jobs:\n" + "\n".join(lines))

    @app.on_message(filters.command("cancelschedule") & CHAT_FILTER)
    async def cancel_schedule(client, message: Message):
        parts = message.text.split(maxsplit=1)
        job_id = parts[1].strip() if len(parts) > 1 else None
        if not job_id:
            return await message.reply_text("Usage: `/cancelschedule <job_id>`")
        try:
            scheduler.remove_job(job_id)
            await message.reply_text(f"✅ Cancelled job `{job_id}`")
        except:
            await message.reply_text(f"❌ No job found with ID `{job_id}`")
