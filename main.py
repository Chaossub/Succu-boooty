import os
import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize the bot client
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)

# Import and register all handler modules
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

# ==============================
#   DEBUG HANDLERS FOR TESTING
# ==============================

@app.on_message(filters.command("flyertest") & filters.group)
async def flyertest_handler(client, message):
    group_id = -1002884098395  # <<---- REPLACE with the group ID you want to test!
    try:
        await client.send_message(group_id, "TEST: Bot posting directly to this group.")
        await message.reply("✅ Test message sent to group!")
    except Exception as e:
        await message.reply(f"❌ Exception: {e}")

@app.on_message(filters.command("groupdebug") & filters.group)
async def groupdebug_handler(client, message):
    chat = await client.get_chat(message.chat.id)
    me = await client.get_me()
    bot_member = await client.get_chat_member(chat.id, me.id)
    can_send = getattr(getattr(bot_member, "privileges", None), "can_send_messages", "n/a")
    await message.reply(
        f"Group type: <code>{chat.type}</code>\n"
        f"ID: <code>{chat.id}</code>\n"
        f"Title: <code>{chat.title}</code>\n"
        f"Bot status: <code>{bot_member.status}</code>\n"
        f"Bot can_send_messages: <code>{can_send}</code>",
        quote=True
    )

# ==============================

print("✅ SuccuBot is running...")
app.run()
