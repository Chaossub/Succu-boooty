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

# start the scheduler once
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
    # allow both group/supergroup and channels
    CHAT_FILTER = filters.group | filters.channel

    @app.on_message(filters.command("addflyer") & (filters.photo | filters.reply) & CHAT_FILTER)
    async def add_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ You must be an admin to add flyers.")

        # determine photo & raw text
        if message.reply_to_message and message.reply_to_message.photo:
            file_id = message.reply_to_message.photo.file_id
            raw     = message.text or ""
        elif message.photo:
            file_id = message.photo.file_id
            raw     = message.caption or ""
        else:
            return await message.reply_text(
                "Usage:\n"
                "• Reply to an image with /addflyer <name> <ad text>\n"
                "• Or send an image with caption: /addflyer <name> <ad text>"
            )

        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            return await message.reply_text(
                "Please specify both a name and an ad text:\n"
                "/addflyer <name> <ad text>"
            )
        name = parts[1].strip().lower()
        ad   = parts[2].strip()

        all_data  = load_flyers()
        chat_data = all_data.setdefault(str(message.chat.id), {})
        if name in chat_data:
            return await message.reply_text(f"❌ A flyer named “{name}” already exists.")

        chat_data[name] = {"file_id": file_id, "ad": ad}
        save_flyers(all_data)
        await message.reply_text(f"✅ Flyer “{name}” added!")

    @app.on_message(filters.command("changeflyer") & (filters.photo | filters.reply) & CHAT_FILTER)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ You must be an admin to change flyers.")
        if not (message.reply_to_message and message.reply_to_message.photo):
            return await message.reply_text(
                "Usage: reply to an image with /changeflyer <name> [new ad text]"
            )

        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            return await message.reply_text(
                "Please specify the flyer name:\n"
                "/changeflyer <name> [new ad text]"
            )
        name   = parts[1].strip().lower()
        new_ad = parts[2].strip() if len(parts) == 3 else None
        file_id = message.reply_to_message.photo.file_id

        all_data  = load_flyers()
        chat_data = all_data.get(str(message.chat.id), {})
        if name not in chat_data:
            return await message.reply_text(f"❌ No flyer named “{name}” found.")

        chat_data[name]["file_id"] = file_id
        if new_ad:
            chat_data[name]["ad"] = new_ad

        save_flyers(all_data)
        await message.reply_text(f"✅ Flyer “{name}” updated!")

    @app.on_message(filters.command("deleteflyer") & CHAT_FILTER)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply_text("❌ You must be an admin to delete flyers.")
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text("Usage: /deleteflyer <name>")
        name = parts[1].strip().lower()

        all_data  = load_flyers()
        chat_data = all_data.get(str(message.chat.id), {})
        if name not in chat_data:
            return await message.reply_text(f"❌ No flyer named “{name}” found.")
        del chat_data[name]
        save_flyers(all_data)
        await message.reply_text(f"✅ Flyer “{name}” deleted!")

    @app.on_message(filters.command("listflyers") & CHAT_FILTER)
    async def list_flyers(client, message: Message):
        chat_data = load_flyers().get(str(message.chat.id), {})
        if not chat_data:
            return await message.reply_text("❌ No flyers have been added yet.")
        names = "\n".join(f"• {n}" for n in chat_data)
        await message.reply_text(f"<b>Available flyers:</b>\n{names}")

    @app.on_message(filters.command("flyer") & CHAT_FILTER)
    async def get_flyer(client, message: Message):
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text("Usage: /flyer <name>")
        name  = parts[1].strip().lower()
        entry = load_flyers().get(str(message.chat.id), {}).get(name)
        if not entry:
            return await message.reply_text(f"❌ No flyer named “{name}” found.")
        await client.send_photo(
            message.chat.id,
            entry["file_id"],
            caption=entry["ad"]
        )

    @app.on_message(filters.command("scheduleflyer") & CHAT_FILTER)
    async def schedule_flyer(client, message: Message):
        text = message.text.strip()
        parts = text.split(maxsplit=3)
        if len(parts) < 3:
            return await message.reply_text(
                "Usage:\n"
                "• One-off:   /scheduleflyer <name> <YYYY-MM-DD HH:MM>\n"
                "• Weekly:    /scheduleflyer <name> <HH:MM> <Mon,Tue,...|daily>"
            )

        name = parts[1].strip().lower()
        entry = load_flyers().get(str(message.chat.id), {}).get(name)
        if not entry:
            return await message.reply_text(f"❌ No flyer named “{name}” found.")

        # one-off
        if len(parts) == 3:
            try:
                run_date = datetime.strptime(parts[2], "%Y-%m-%d %H:%M")
            except ValueError:
                return await message.reply_text("❌ Invalid format. Use YYYY-MM-DD HH:MM")
            scheduler.add_job(
                client.send_photo,
                trigger=DateTrigger(run_date),
                args=[message.chat.id, entry["file_id"]],
                kwargs={"caption": entry["ad"]}
            )
            return await message.reply_text(
                f"✅ Scheduled one-off flyer “{name}” for {run_date:%Y-%m-%d %H:%M}"
            )

        # recurring
        time_str = parts[2]
        days_str = parts[3]
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

        if days_str.lower() == "daily":
            dow = list(mapping.values())
        else:
            dow = []
            for d in days_str.split(","):
                tok = mapping.get(d.strip().lower())
                if not tok:
                    return await message.reply_text(
                        f"❌ Invalid weekday: {d}\nUse Mon,Tue,... or daily."
                    )
                dow.append(tok)

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
