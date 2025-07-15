import os
import logging
from datetime import datetime
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from pyrogram import filters
from pyrogram.types import Message

# ───── Mongo Setup ─────
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME")
mongo_client = MongoClient(MONGO_URI)
flyers_col = mongo_client[MONGO_DB]["flyers"]   # Global flyers
sched_col = mongo_client[MONGO_DB]["scheduled"] # Scheduled jobs

# ───── Your Super Admin ─────
SUPER_ADMIN_ID = 6964994611

# ───── Group Aliases ─────
ALIASES = {
    "MODELS_CHAT": int(os.environ.get("MODELS_CHAT", 0)),
    "SUCCUBUS_SANCTUARY": int(os.environ.get("SUCCUBUS_SANCTUARY", 0)),
    "TEST_GROUP": int(os.environ.get("TEST_GROUP", 0)),
}

def resolve_chat_id(alias_or_id):
    if alias_or_id.upper() in ALIASES:
        return ALIASES[alias_or_id.upper()]
    try:
        return int(alias_or_id)
    except:
        return None

async def is_admin(client, chat_id, user_id):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False

# ───── Flyer Sender ─────
async def send_flyer(app, flyer, chat_id):
    if flyer.get("type") == "photo":
        await app.send_photo(chat_id, flyer["file_id"], caption=flyer["caption"])
    else:
        await app.send_message(chat_id, flyer["text"])

# ───── Scheduled Sender ─────
async def scheduled_job(app, flyer_id, chat_id):
    flyer = flyers_col.find_one({"_id": flyer_id})
    if flyer:
        await send_flyer(app, flyer, chat_id)

def register(app, scheduler: BackgroundScheduler):
    logger = logging.getLogger(__name__)
    logger.info("📢 flyer.register() called")

    # Add flyer (text or photo)
    @app.on_message(filters.command("addflyer") & (filters.group | filters.private))
    async def add_flyer(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can add flyers.")

        args = (message.caption if message.photo else message.text).split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage:\n• /addflyer <name> <text>\nOr send a photo with caption.")
        name = args[1].split()[0]
        rest = args[1][len(name):].strip()

        # Check if flyer exists
        if flyers_col.find_one({"name": name}):
            return await message.reply("❌ Flyer already exists.")

        if message.photo:
            flyers_col.insert_one({
                "name": name,
                "type": "photo",
                "file_id": message.photo.file_id,
                "caption": rest,
                "created": datetime.utcnow(),
            })
            return await message.reply(f"✅ Photo flyer '{name}' added.")
        else:
            flyers_col.insert_one({
                "name": name,
                "type": "text",
                "text": rest,
                "created": datetime.utcnow(),
            })
            return await message.reply(f"✅ Text flyer '{name}' added.")

    # Send flyer (by name, anywhere)
    @app.on_message(filters.command("flyer") & (filters.group | filters.private))
    async def get_flyer(client, message: Message):
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        flyer = flyers_col.find_one({"name": args[1].strip()})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        await send_flyer(client, flyer, message.chat.id)

    # List flyers
    @app.on_message(filters.command("listflyers") & (filters.group | filters.private))
    async def list_flyers(client, message: Message):
        flyers = list(flyers_col.find({}))
        if not flyers:
            return await message.reply("ℹ️ No flyers found.")
        txt = "\n".join([f"• <b>{f['name']}</b> ({f['type']})" for f in flyers])
        await message.reply(f"<b>Flyers:</b>\n{txt}")

    # Delete flyer
    @app.on_message(filters.command("deleteflyer") & (filters.group | filters.private))
    async def delete_flyer(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can delete flyers.")
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        name = args[1].strip()
        flyers_col.delete_one({"name": name})
        await message.reply(f"✅ Flyer '{name}' deleted.")

    # Update flyer image/caption
    @app.on_message(filters.command("changeflyer") & filters.photo)
    async def change_flyer(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can change flyers.")
        args = (message.caption or "").split(maxsplit=1)
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> <caption>")
        name = args[1].split()[0]
        rest = args[1][len(name):].strip()
        flyers_col.update_one(
            {"name": name},
            {"$set": {
                "type": "photo",
                "file_id": message.photo.file_id,
                "caption": rest
            }}
        )
        await message.reply(f"✅ Flyer '{name}' updated.")

    # Schedule flyer (to group by alias, one-off or daily)
    @app.on_message(filters.command("scheduleflyer") & (filters.group | filters.private))
    async def schedule_flyer(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can schedule flyers.")
        # /scheduleflyer <flyer> <group> <HH:MM> [once|daily]
        parts = message.text.split()
        if len(parts) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <flyer> <group> <HH:MM> [once|daily]")
        flyer_name, group_alias, timestr = parts[1], parts[2], parts[3]
        mode = parts[4] if len(parts) > 4 else "once"

        flyer = flyers_col.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        tgt_chat = resolve_chat_id(group_alias)
        if not tgt_chat:
            return await message.reply("❌ Invalid group alias.")

        hour, minute = map(int, timestr.split(":"))
        job = {
            "flyer_id": flyer["_id"],
            "chat_id": tgt_chat,
            "hour": hour,
            "minute": minute,
            "mode": mode,
        }
        sched_col.insert_one(job)
        if mode == "daily":
            scheduler.add_job(
                scheduled_job,
                trigger="cron",
                hour=hour,
                minute=minute,
                args=[app, flyer["_id"], tgt_chat],
                id=f"{flyer_name}_{tgt_chat}_daily",
                replace_existing=True,
            )
        else:
            # One-off
            run_date = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            if run_date < datetime.now():
                run_date = run_date.replace(day=run_date.day+1)
            scheduler.add_job(
                scheduled_job,
                trigger="date",
                run_date=run_date,
                args=[app, flyer["_id"], tgt_chat],
                id=f"{flyer_name}_{tgt_chat}_{run_date.timestamp()}",
            )
        await message.reply(f"✅ Scheduled flyer '{flyer_name}' to {group_alias} at {timestr} ({mode}).")

    # List scheduled
    @app.on_message(filters.command("listscheduled") & (filters.group | filters.private))
    async def list_sched(client, message: Message):
        jobs = list(sched_col.find({}))
        if not jobs:
            return await message.reply("ℹ️ No scheduled flyers.")
        out = []
        for j in jobs:
            g = [k for k,v in ALIASES.items() if v==j['chat_id']]
            group = g[0] if g else str(j['chat_id'])
            flyer = flyers_col.find_one({"_id": j["flyer_id"]})
            fname = flyer["name"] if flyer else "❓"
            out.append(f"{fname} → {group} @ {j['hour']:02d}:{j['minute']:02d} ({j['mode']})")
        await message.reply("<b>Scheduled Flyers:</b>\n" + "\n".join(out))

    # Cancel scheduled (by flyer name, all jobs)
    @app.on_message(filters.command("cancelflyer") & (filters.group | filters.private))
    async def cancel_sched(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await is_admin(client, chat_id, user_id):
            return await message.reply("❌ Only admins can cancel scheduled flyers.")
        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("❌ Usage: /cancelflyer <flyer>")
        flyer = flyers_col.find_one({"name": parts[1]})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        sched_col.delete_many({"flyer_id": flyer["_id"]})
        # Also remove jobs from APScheduler
        for job in list(scheduler.get_jobs()):
            if parts[1] in job.id:
                scheduler.remove_job(job.id)
        await message.reply(f"✅ Canceled all scheduled for '{parts[1]}'.")

