import logging
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz

# Set up logging
logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

# Example flyer scheduling function
async def scheduleflyer_handler(client, message):
    # Extract flyer name, time, and group from the command
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.reply("❌ Usage: /scheduleflyer <flyer_name> <YYYY-MM-DD HH:MM> <group>")
        return

    flyer_name = args[1]
    time_str = args[2]
    group = args[3]

    try:
        # Assume time in local timezone (e.g., America/Los_Angeles)
        local_tz = pytz.timezone("America/Los_Angeles")
        post_time = local_tz.localize(datetime.strptime(time_str, "%Y-%m-%d %H:%M"))
    except Exception as e:
        await message.reply(f"❌ Invalid time format: {e}")
        return

    # Schedule the flyer post
    scheduler.add_job(
        func=post_flyer,
        trigger='date',
        run_date=post_time,
        args=[client, flyer_name, group]
    )
    await message.reply(f"✅ Scheduled flyer '{flyer_name}' for {time_str} in {group}.")

async def post_flyer(client, flyer_name, group):
    # Replace this with your flyer posting logic
    await client.send_message(group, f"📢 Scheduled Flyer: {flyer_name}")

# Register the handler properly with group=0 (integer)
def register(app):
    app.add_handler(
        MessageHandler(scheduleflyer_handler, filters.command("scheduleflyer")),
        group=0
    )
    # Start the scheduler if not already running
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started in flyer_scheduler.")

# Optional: register immediately if running standalone
if __name__ == "__main__":
    from pyrogram import Client
    import os

    api_id = int(os.environ.get("API_ID", 12345))
    api_hash = os.environ.get("API_HASH", "your_api_hash")
    bot_token = os.environ.get("BOT_TOKEN", "your_bot_token")
    app = Client("flyer_scheduler_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

    register(app)
    print("Bot running with flyer scheduler handler.")
    app.run()
