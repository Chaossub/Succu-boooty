import os
from datetime import datetime
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import filters, Client
from pyrogram.types import Message

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME") or os.getenv("MONGO_DB_NAME")

if not MONGO_URI or not MONGO_DBNAME:
    raise RuntimeError("MONGO_URI and MONGO_DBNAME must both be set")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DBNAME]
flyers_col = db["flyers"]

scheduler = AsyncIOScheduler()

def register(app: Client):
    CHAT_FILTER = filters.group | filters.channel

    @app.on_message(filters.command("createflyer") & CHAT_FILTER)
    async def create_flyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not message.photo:
            return await message.reply_text("Usage: /createflyer <name> (attach image)")
        name = args[1].strip()
        file_id = message.photo.file_id

        flyers_col.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {
                "chat_id": message.chat.id,
                "name": name,
                "file_id": file_id,
                "created_by": message.from_user.id,
                "created_at": message.date
            }},
            upsert=True
        )
        await message.reply_text(f"✅ Flyer '{name}' created!")

    @app.on_message(filters.command("scheduleflyer") & CHAT_FILTER)
    async def schedule_flyer(client, message: Message):
        parts = message.text.split()
        if len(parts) != 4:
            return await message.reply_text("Usage: /scheduleflyer <name> YYYY-MM-DD HH:MM")
        _, name, date_str, time_str = parts

        doc = flyers_col.find_one({"chat_id": message.chat.id, "name": name})
        if not doc:
            return await message.reply_text(f"❌ No flyer named '{name}'. Use /createflyer first.")

        try:
            run_dt = datetime.fromisoformat(f"{date_str} {time_str}")
        except ValueError:
            return await message.reply_text("❌ Invalid date/time format. Use YYYY-MM-DD HH:MM")

        job_id = f"flyer_{message.chat.id}_{name}_{int(run_dt.timestamp())}"

        scheduler.add_job(
            func=lambda chat_id, file_id: asyncio.create_task(client.send_photo(chat_id, file_id)),
            trigger="date",
            run_date=run_dt,
            args=[message.chat.id, doc["file_id"]],
            id=job_id,
            replace_existing=True
        )
        await message.reply_text(f"✅ Scheduled flyer '{name}' for {run_dt.isoformat(sep=' ')} UTC")

    @app.on_message(filters.command("cancelflyer") & CHAT_FILTER)
    async def cancel_flyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply_text("Usage: /cancelflyer <name>")
        name = args[1].strip()

        jobs = [job for job in scheduler.get_jobs() if f"{message.chat.id}_{name}_" in job.id]
        if not jobs:
            return await message.reply_text(f"❌ No scheduled flyer '{name}' found.")
        for job in jobs:
            scheduler.remove_job(job.id)
        await message.reply_text(f"✅ Canceled {len(jobs)} job(s) for '{name}'.")

    @app.on_message(filters.command("listflyers") & CHAT_FILTER)
    async def list_flyers(client, message: Message):
        docs = flyers_col.find({"chat_id": message.chat.id})
        names = [doc["name"] for doc in docs]
        if not names:
            return await message.reply_text("No flyers created yet. Use /createflyer.")
        text = "📋 Created flyers:\n" + "\n".join(f"- {n}" for n in names)
        await message.reply_text(text)

    @app.on_message(filters.command("helpflyer") & CHAT_FILTER)
    async def help_flyer(client, message: Message):
        help_text = (
            "📋 **Flyer Commands**\n\n"
            "`/createflyer <name>` — Create or update a flyer (attach image)\n"
            "`/scheduleflyer <name> YYYY-MM-DD HH:MM` — Schedule it to post\n"
            "`/cancelflyer <name>` — Cancel scheduled run(s)\n"
            "`/listflyers` — List all created flyers\n"
        )
        await message.reply_text(help_text, parse_mode="markdown")
