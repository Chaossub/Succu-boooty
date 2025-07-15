import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.types import Message

logger = logging.getLogger("handlers.flyer_scheduler")

# Mongo
MONGO_URI = os.environ.get("MONGO_URI")
mongo = MongoClient(MONGO_URI)
db = mongo["succubot"]
flyers = db.flyers
scheduled = db.scheduled_flyers

# Hardcoded group aliases and IDs
GROUP_ALIASES = {
    "MODELS_CHAT": -1002884098395,
    "SUCCUBUS_SANCTUARY": -1002823762054,
    "TEST_GROUP": -1002813378700
}

def resolve_group(chat_str):
    """Resolve group alias or chat ID to int."""
    if chat_str.upper() in GROUP_ALIASES:
        return GROUP_ALIASES[chat_str.upper()]
    if chat_str.startswith("-100"):
        return int(chat_str)
    raise ValueError("Unknown group alias or invalid group ID.")

def register(app, scheduler: BackgroundScheduler):

    async def post_flyer(client, group_id, flyer):
        try:
            logger.info(f"Posting flyer '{flyer['name']}' to {group_id} ({type(group_id)})")
            if flyer.get("file_id"):
                await client.send_photo(group_id, flyer["file_id"], caption=flyer.get("caption", ""))
            else:
                await client.send_message(group_id, flyer.get("caption", flyer.get("text", "")))
            logger.info(f"Posted flyer '{flyer['name']}' to {group_id}")
        except Exception as e:
            logger.error(f"Failed scheduled flyer post: {e}")

    # /flyer <name>
    @app.on_message(filters.command("flyer") & (filters.group | filters.private))
    async def flyer_handler(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /flyer <name>")
        name = args[1].strip().lower()
        flyer = flyers.find_one({"name": name})
        if not flyer:
            return await message.reply(f"❌ Flyer '{name}' not found.")
        await post_flyer(client, message.chat.id, flyer)

    # /addflyer <name> <caption> with photo
    @app.on_message(filters.command("addflyer") & filters.group & filters.photo)
    async def addflyer_handler(client, message: Message):
        args = message.caption.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("Usage: /addflyer <name> <caption>")
        _, name, caption = args
        name = name.lower()
        file_id = message.photo.file_id
        flyers.replace_one({"name": name}, {"name": name, "file_id": file_id, "caption": caption}, upsert=True)
        await message.reply(f"✅ Flyer '{name}' added/updated (photo).")

    # /addflyer <name> <text> (text-only flyer)
    @app.on_message(filters.command("addflyer") & (filters.group | filters.private) & ~filters.photo)
    async def addflyer_text_handler(client, message: Message):
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply("Usage: /addflyer <name> <text>")
        _, name, text = args
        name = name.lower()
        flyers.replace_one({"name": name}, {"name": name, "text": text}, upsert=True)
        await message.reply(f"✅ Flyer '{name}' added/updated (text-only).")

    # /changeflyer <name> (reply to photo)
    @app.on_message(filters.command("changeflyer") & filters.reply & filters.group)
    async def changeflyer_handler(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not message.reply_to_message.photo:
            return await message.reply("Reply to a photo: /changeflyer <name>")
        name = args[1].strip().lower()
        file_id = message.reply_to_message.photo.file_id
        flyer = flyers.find_one({"name": name})
        if not flyer:
            return await message.reply(f"Flyer '{name}' not found.")
        flyer["file_id"] = file_id
        flyers.replace_one({"name": name}, flyer, upsert=True)
        await message.reply(f"✅ Flyer '{name}' image updated.")

    # /deleteflyer <name>
    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def deleteflyer_handler(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("Usage: /deleteflyer <name>")
        name = args[1].strip().lower()
        flyers.delete_one({"name": name})
        await message.reply(f"🗑 Flyer '{name}' deleted.")

    # /listflyers
    @app.on_message(filters.command("listflyers") & (filters.group | filters.private))
    async def listflyers_handler(client, message: Message):
        out = []
        for flyer in flyers.find():
            t = "🖼" if flyer.get("file_id") else "📝"
            out.append(f"{t} <b>{flyer['name']}</b>")
        if not out:
            await message.reply("No flyers saved.")
        else:
            await message.reply("\n".join(out))

    # /scheduleflyer <name> <HH:MM> <group> [daily]
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message: Message):
        try:
            args = message.text.split(maxsplit=4)
            if len(args) < 4:
                return await message.reply("Usage: /scheduleflyer <name> <HH:MM> <group> [daily|once]")
            _, name, time_str, group_alias = args[:4]
            freq = args[4].lower() if len(args) > 4 else "once"
            flyer = flyers.find_one({"name": name.lower()})
            if not flyer:
                return await message.reply(f"Flyer '{name}' not found.")
            group_id = resolve_group(group_alias)
            hour, minute = map(int, time_str.split(":"))
            now = datetime.now()
            run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if run_time < now:
                run_time += timedelta(days=1)
            job_id = f"flyer_{name}_{group_id}_{run_time.timestamp()}"
            # Save job info to db
            scheduled.insert_one({
                "job_id": job_id, "name": name, "group": group_id,
                "time": time_str, "freq"_
