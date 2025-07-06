import os
import json

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

from pyrogram import filters
from pyrogram.types import Message

# ─── Config ────────────────────────────────────────────────────────────
FLYER_PATH     = "data/flyers.json"
SUPER_ADMIN_ID = 6964994611
# ────────────────────────────────────────────────────────────────────────

# start scheduler once
scheduler = AsyncIOScheduler()
scheduler.start()

async def is_admin(client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False

def load_flyers():
    if not os.path.exists(FLYER_PATH):
        return {}
    with open(FLYER_PATH, "r") as f:
        return json.load(f)

def save_flyers(data):
    os.makedirs(os.path.dirname(FLYER_PATH), exist_ok=True)
    with open(FLYER_PATH, "w") as f:
        json.dump(data, f)

def register(app):

    # … your add/change/delete/list/flyer handlers stay the same …

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message: Message):
        text = message.text.strip()
        parts = text.split(maxsplit=3)
        if len(parts) < 3:
            return await message.reply_text(
                "Usage:\n"
                "• One-off: /scheduleflyer <name> <YYYY-MM-DD HH:MM>\n"
                "• Weekly: /scheduleflyer <name> <HH:MM> <Mon,Tue,...|daily>"
            )

        name = parts[1].lower()
        # load the flyer entry
        entry = load_flyers().get(str(message.chat.id), {}).get(name)
        if not entry:
            return await message.reply_text(f"❌ No flyer named “{name}” found.")

        # ——— One-off scheduling ———
        # when only 3 parts: parts[2] contains full "YYYY-MM-DD HH:MM"
        if len(parts) == 3:
            dt_txt = parts[2]
            try:
                run_date = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M")
            except ValueError:
                return await message.reply_text(
                    "❌ Invalid date/time format. Use YYYY-MM-DD HH:MM"
                )

            scheduler.add_job(
                client.send_photo,
                trigger=DateTrigger(run_date),
                args=[message.chat.id, entry["file_id"]],
                kwargs={"caption": entry["ad"]}
            )
            return await message.reply_text(
                f"✅ Scheduled one-off flyer “{name}” for {run_date:%Y-%m-%d %H:%M}"
            )

        # ——— Recurring weekly/daily ———
        # parts[2] is time, parts[3] is days spec
        time_str = parts[2]
        days_str = parts[3]
        try:
            hour, minute = map(int, time_str.split(":"))
        except:
            return await message.reply_text(
                "❌ Invalid time. Use HH:MM (24-hour)."
            )

        # map user input days to cron day_of_week tokens
        mapping = {
            'mon':'mon','monday':'mon',
            'tue':'tue','tuesday':'tue',
            'wed':'wed','wednesday':'wed',
            'thu':'thu','thursday':'thu',
            'fri':'fri','friday':'fri',
            'sat':'sat','saturday':'sat',
            'sun':'sun','sunday':'sun'
        }

        dow = []
        if days_str.lower() == "daily":
            dow = list(mapping.values())
        else:
            for d in days_str.split(","):
                token = mapping.get(d.strip().lower())
                if not token:
                    return await message.reply_text(
                        f"❌ Invalid weekday: {d}\nUse Mon,Tue,... or daily."
                    )
                dow.append(token)

        trigger = CronTrigger(day_of_week=",".join(dow), hour=hour, minute=minute)
        scheduler.add_job(
            client.send_photo,
            trigger=trigger,
            args=[message.chat.id, entry["file_id"]],
            kwargs={"caption": entry["ad"]}
        )
        return await message.reply_text(
            f"✅ Scheduled flyer “{name}” every {days_str} at {time_str}"
        )
