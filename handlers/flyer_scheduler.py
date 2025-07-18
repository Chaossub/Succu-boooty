import logging
import asyncio
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
MAIN_LOOP = None  # Will be set at runtime

async def scheduleflyer_handler(client, message):
    args = message.text.split(maxsplit=4)
    if len(args) < 5:
        await message.reply(
            "❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD HH:MM> <group>\n\n"
            "Example:\n/scheduleflyer tipping 2025-07-17 19:54 MODELS_CHAT"
        )
        return

    flyer_name = args[1]
    date_part = args[2]
    time_part = args[3]
    group = args[4]
    time_str = f"{date_part} {time_part}"

    try:
        local_tz = pytz.timezone("America/Los_Angeles")
        post_time = local_tz.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M"))
    except Exception as e:
        await message.reply(f"❌ Invalid time format: {e}")
        return

    scheduler.add_job(
        func=run_post_flyer,
        trigger='date',
        run_date=post_time,
        args=[client, flyer_name, group]
    )
    await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {time_str} in {group}.")

async def post_flyer(client, flyer_name, group):
    await client.send_message(group, f"📢 Scheduled Flyer: {flyer_name}")

def run_post_flyer(client, flyer_name, group):
    # Use the globally-set MAIN_LOOP to submit the coroutine to the main thread
    global MAIN_LOOP
    if MAIN_LOOP is None:
        MAIN_LOOP = asyncio.get_event_loop()
    asyncio.run_coroutine_threadsafe(post_flyer(client, flyer_name, group), MAIN_LOOP)

def register(app):
    app.add_handler(
        MessageHandler(scheduleflyer_handler, filters.command("scheduleflyer")),
        group=0
    )
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started in flyer_scheduler.")

# Set the event loop when the bot starts
def set_main_loop(loop):
    global MAIN_LOOP
    MAIN_LOOP = loop
