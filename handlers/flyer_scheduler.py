import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
from pyrogram import Client, filters
from pyrogram.errors import RPCError, PeerIdInvalid
from pymongo import MongoClient

# --- Logging setup ---
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)

# --- ENV ---
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME")
SCHED_TZ = os.environ.get("SCHEDULER_TZ", "America/Los_Angeles")

# Mongo for flyer storage (shared with flyer.py)
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers = mongo.flyers

# Scheduler (single instance)
scheduler = BackgroundScheduler(timezone=SCHED_TZ)
scheduler.start()

# ---- JOB FUNCTION ----
async def post_flyer_job(group_id, flyer_name, request_chat_id):
    logger.info(f"POST FLYER JOB | group_id={group_id} flyer_name={flyer_name} request_chat_id={request_chat_id}")
    try:
        flyer = flyers.find_one({"group_id": group_id, "name": flyer_name})
        if not flyer:
            logger.error(f"Flyer not found: {flyer_name} in {group_id}")
            await Client.get_current().send_message(
                chat_id=request_chat_id,
                text=f"❌ Flyer '{flyer_name}' not found for group <code>{group_id}</code>.",
                parse_mode="HTML"
            )
            return

        photo_id = flyer.get("file_id")
        caption = flyer.get("caption", "")
        logger.info(f"Sending flyer to group {group_id}: {caption} (photo_id={photo_id})")

        await Client.get_current().send_photo(
            chat_id=group_id,
            photo=photo_id,
            caption=caption or "",
            parse_mode="HTML"
        )

        await Client.get_current().send_message(
            chat_id=request_chat_id,
            text=f"✅ Flyer <b>{flyer_name}</b> posted in <code>{group_id}</code>.",
            parse_mode="HTML"
        )
    except PeerIdInvalid:
        logger.error(f"PeerIdInvalid for group: {group_id}")
        await Client.get_current().send_message(
            chat_id=request_chat_id,
            text=f"❌ Flyer schedule failed: Peer id invalid: <code>{group_id}</code>",
            parse_mode="HTML"
        )
    except RPCError as e:
        logger.exception(f"RPCError posting flyer: {e}")
        await Client.get_current().send_message(
            chat_id=request_chat_id,
            text=f"❌ RPCError posting flyer: <code>{str(e)}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.exception(f"Unknown error posting flyer: {e}")
        await Client.get_current().send_message(
            chat_id=request_chat_id,
            text=f"❌ Unknown error posting flyer: <code>{str(e)}</code>",
            parse_mode="HTML"
        )

def get_group_id(alias):
    # Accepts -100xxx, username, or ENV ALIAS
    if alias.startswith("-100"):
        return int(alias)
    # Check for shortcut in ENV (e.g. MODELS_CHAT)
    val = os.environ.get(alias)
    if val and val.startswith("-100"):
        return int(val)
    return None

def register(app: Client):
    @app.on_message(filters.command("scheduleflyer") & filters.group)
    async def scheduleflyer_handler(client, message):
        try:
            args = message.text.split()
            if len(args) < 5:
                await message.reply(
                    "❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD> <HH:MM> <once|daily> <group>",
                    quote=True
                )
                return

            flyer_name = args[1]
            date_str = args[2]
            time_str = args[3]
            repeat = args[4].lower()
            group_str = args[5] if len(args) > 5 else message.chat.id

            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

            group_id = get_group_id(group_str)
            if not group_id:
                await message.reply(f"❌ Invalid group_id or group shortcut: <code>{group_str}</code>", parse_mode="HTML")
                return

            job_id = f"flyer_{flyer_name}_{group_id}_{dt.strftime('%Y%m%d%H%M%S')}"
            logger.info(f"Scheduling flyer: {flyer_name} to {group_id} at {dt} | job_id={job_id}")

            # Remove any duplicate jobs
            try:
                scheduler.remove_job(job_id)
            except JobLookupError:
                pass  # not a problem

            # Schedule
            if repeat == "once":
                scheduler.add_job(
                    post_flyer_job,
                    "date",
                    run_date=dt,
                    args=[group_id, flyer_name, message.chat.id],
                    id=job_id,
                    replace_existing=True
                )
            elif repeat == "daily":
                scheduler.add_job(
                    post_flyer_job,
                    "cron",
                    hour=dt.hour,
                    minute=dt.minute,
                    args=[group_id, flyer_name, message.chat.id],
                    id=job_id,
                    replace_existing=True
                )
            else:
                await message.reply("❌ Repeat type must be 'once' or 'daily'.")
                return

            await message.reply(
                f"✅ Scheduled flyer '<b>{flyer_name}</b>' to post in <code>{group_str}</code> at <b>{dt}</b> ({repeat}).\nJob ID: <code>{job_id}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.exception("Error scheduling flyer:")
            await message.reply(
                f"❌ Error scheduling flyer: <code>{str(e)}</code>",
                parse_mode="HTML"
            )
