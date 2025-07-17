import os
import logging
from pyrogram import Client, filters, enums
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 6964994611  # Your hardwired Telegram ID

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("main")

# Initialize Pyrogram Client
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML,
)

# -------------- HANDLER IMPORTS --------------
from handlers import (
    welcome,
    help_cmd,
    moderation,
    federation,
    summon,
    xp,
    fun,
    flyer,
    flyer_scheduler,
)
welcome.register(app)
help_cmd.register(app)
moderation.register(app)
federation.register(app)
summon.register(app)
xp.register(app)
fun.register(app)
flyer.register(app)
flyer_scheduler.register(app)
logger.info("Imported all handler modules.")

# --------- ADMIN-ONLY FLYER DEBUGGING ---------
def is_admin_or_owner(user_id):
    return user_id == OWNER_ID

@app.on_message(filters.command("flyertest") & filters.group)
async def flyertest_handler(client, message):
    if not is_admin_or_owner(message.from_user.id):
        return
    try:
        await message.reply("✅ Test message sent to group!")
        await client.send_message(message.chat.id, "TEST: Bot posting directly to this group.")
    except Exception as e:
        logger.error(f"[flyertest] {e}", exc_info=True)
        await message.reply(f"❌ Could not send: <code>{e}</code>")

@app.on_message(filters.command("groupdebug") & filters.group)
async def groupdebug_handler(client, message):
    if not is_admin_or_owner(message.from_user.id):
        return
    try:
        chat = await client.get_chat(message.chat.id)
        status = await client.get_chat_member(message.chat.id, (await client.get_me()).id)
        text = (
            f"Group type: <b>{chat.type}</b>\n"
            f"ID: <code>{chat.id}</code>\n"
            f"Title: {chat.title}\n"
            f"Bot status: <b>{status.status}</b>\n"
            f"Bot can_send_messages: <b>{getattr(status.privileges, 'can_send_messages', 'n/a')}</b>"
        )
        await message.reply(text)
    except Exception as e:
        logger.error(f"[groupdebug] {e}", exc_info=True)
        await message.reply(f"❌ Could not debug: <code>{e}</code>")

if __name__ == "__main__":
    logger.info("MAIN.PY BOOTSTRAP BEGIN")
    app.run()

