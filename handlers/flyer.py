import os
import json
import pytz
import logging
from datetime import datetime
from pyrogram import Client, filters
from apscheduler.schedulers.background import BackgroundScheduler

# ─── Config ─────────────────────────────────────────────────────────────────────
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME")
FLYER_JSON = "flyers.json"
TZ = pytz.timezone("America/Los_Angeles")

# ─── Data ───────────────────────────────────────────────────────────────────────
if not os.path.exists(FLYER_JSON):
    with open(FLYER_JSON, "w") as f:
        json.dump({}, f)

def load_flyers():
    with open(FLYER_JSON, "r") as f:
        return json.load(f)

def save_flyers(data):
    with open(FLYER_JSON, "w") as f:
        json.dump(data, f, indent=2)

# ─── Scheduler ──────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=TZ)
scheduler.start()

def schedule_flyer_posting(app, from_chat_id, target_chat_id, flyer_name, post_time):
    def job():
        flyers = load_flyers()
        group_flyers = flyers.get(str(from_chat_id), {})
        flyer = group_flyers.get(flyer_name)
        if flyer:
            app.send_photo(
                chat_id=target_chat_id,
                photo=flyer["file_id"],
                caption=flyer["caption"]
            )
    scheduler.add_job(job, 'date', run_date=post_time)

# ─── Handlers ───────────────────────────────────────────────────────────────────
def register(app: Client):
    @app.on_message(filters.command("addflyer") & filters.group)
    async def add_flyer(client, message):
        text = message.text or message.caption
        if not text or not message.photo:
            return await message.reply("❌ Usage: Send a photo with the command in the caption.\nFormat: /addflyer <name> <caption>")

        parts = text.split(None, 2)
        if len(parts) < 3:
            return await message.reply("❌ Missing name or caption.\nUsage: /addflyer <name> <caption>")

        _, flyer_name, flyer_caption = parts
        chat_id = str(message.chat.id)
        file_id = message.photo.file_id

        flyers = load_flyers()
        flyers.setdefault(chat_id, {})
        flyers[chat_id][flyer_name] = {"file_id": file_id, "caption": flyer_caption}
        save_flyers(flyers)

        await message.reply(f"✅ Flyer '{flyer_name}' added.")

    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message):
        flyers = load_flyers()
        chat_id = str(message.chat.id)

        if len(message.command) < 2:
            return await message.reply("❌ Usage: /flyer <name>")

        flyer_name = message.command[1]
        flyer = flyers.get(chat_id, {}).get(flyer_name)
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        
        await message.reply_photo(photo=flyer["file_id"], caption=flyer["caption"])

    @app.on_message(filters.command("flyerlist") & filters.group)
    async def list_flyers(client, message):
        flyers = load_flyers()
        chat_id = str(message.chat.id)
        names = flyers.get(chat_id, {}).keys()
        if not names:
            return await message.reply("📭 No flyers found.")
        text = "📌 Flyers:\n" + "\n".join(f"- {name}" for name in names)
        await message.reply(text)

    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message):
        if len(message.command) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")

        flyer_name = message.command[1]
        chat_id = str(message.chat.id)

        flyers = load_flyers()
        if flyer_name in flyers.get(chat_id, {}):
            del flyers[chat_id][flyer_name]
            save_flyers(flyers)
            return await message.reply(f"🗑️ Flyer '{flyer_name}' deleted.")
        await message.reply("❌ Flyer not found.")

    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    async def change_flyer(client, message):
        if not message.reply_to_message.photo:
            return await message.reply("❌ You must reply to a photo.")

        if len(message.command) < 2:
            return await message.reply("❌ Usage: /changeflyer <name>")

        flyer_name = message.command[1]
        chat_id = str(message.chat.id)

        flyers = load_flyers()
        if flyer_name not in flyers.get(chat_id, {}):
            return await message.reply("❌ Flyer not found.")

        flyers[chat_id][flyer_name]["file_id"] = message.reply_to_message.photo.file_id
        save_flyers(flyers)
        await message.reply(f"🔁 Flyer '{flyer_name}' image updated.")

    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def schedule_flyer(client, message):
        args = message.text.split(None, 4)
        if len(args) < 5:
            return await message.reply("❌ Usage: /scheduleflyer <source_group_id> <target_group_id> <flyer_name> <YYYY-MM-DD HH:MM>")

        _, source_id, target_id, flyer_name, time_str = args
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            dt = TZ.localize(dt)
        except ValueError:
            return await message.reply("❌ Invalid date/time format. Use YYYY-MM-DD HH:MM (24hr)")

        schedule_flyer_posting(client, int(source_id), int(target_id), flyer_name, dt)
        await message.reply(f"📅 Flyer '{flyer_name}' from {source_id} will be posted to {target_id} at {dt.strftime('%Y-%m-%d %H:%M %Z')}.")


