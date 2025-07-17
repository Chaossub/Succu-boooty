import logging
import os
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pymongo import MongoClient
from datetime import datetime

# --- CONFIG ---
OWNER_ID = 6964994611  # Your Telegram user ID (hardwired admin)
try:
    mongo_client = __import__("builtins").mongo_client
except Exception:
    mongo_client = MongoClient(os.environ["MONGO_URI"])
db = mongo_client[os.environ.get("MONGO_DBNAME", "succubot")]
flyers_col = db["flyers"]

logger = logging.getLogger(__name__)

# --- ADMIN CHECK ---
def is_admin(user_id):
    return user_id == OWNER_ID

# --- HANDLERS ---

async def addflyer_handler(client, message):
    try:
        if not is_admin(message.from_user.id):
            await message.reply("❌ Only the group owner can add flyers.")
            return
        if not (message.reply_to_message and message.reply_to_message.photo):
            await message.reply("❌ Please reply to a photo with /addflyer <name> <caption>")
            return
        args = (message.text or "").split(maxsplit=2)
        if len(args) < 3:
            await message.reply("❌ Usage: /addflyer <name> <caption>")
            return
        flyer_name = args[1].strip().lower()
        caption = args[2].strip()
        file_id = message.reply_to_message.photo.file_id
        flyers_col.update_one(
            {"chat_id": message.chat.id, "name": flyer_name},
            {"$set": {
                "chat_id": message.chat.id,
                "name": flyer_name,
                "file_id": file_id,
                "caption": caption,
                "created_by": message.from_user.id,
                "created_at": datetime.utcnow(),
            }},
            upsert=True
        )
        logger.info(f"Flyer '{flyer_name}' added/updated by {message.from_user.id} in {message.chat.id}")
        await message.reply(f"✅ Flyer '{flyer_name}' saved. (with photo)")
    except Exception as e:
        logger.exception("Error in addflyer_handler")
        await message.reply("❌ Error adding flyer.")

async def changeflyer_handler(client, message):
    try:
        if not is_admin(message.from_user.id):
            await message.reply("❌ Only the group owner can change flyers.")
            return
        if not (message.reply_to_message and message.reply_to_message.photo):
            await message.reply("❌ Reply to the new photo with /changeflyer <name> <caption>")
            return
        args = (message.text or "").split(maxsplit=2)
        if len(args) < 3:
            await message.reply("❌ Usage: /changeflyer <name> <caption>")
            return
        flyer_name = args[1].strip().lower()
        caption = args[2].strip()
        file_id = message.reply_to_message.photo.file_id
        result = flyers_col.update_one(
            {"chat_id": message.chat.id, "name": flyer_name},
            {"$set": {"file_id": file_id, "caption": caption, "updated_at": datetime.utcnow()}}
        )
        if result.matched_count:
            logger.info(f"Flyer '{flyer_name}' changed by {message.from_user.id} in {message.chat.id}")
            await message.reply(f"✅ Flyer '{flyer_name}' updated with new photo.")
        else:
            await message.reply("❌ Flyer not found to update.")
    except Exception as e:
        logger.exception("Error in changeflyer_handler")
        await message.reply("❌ Error changing flyer.")

async def flyer_handler(client, message):
    try:
        args = (message.text or "").split(maxsplit=1)
        if len(args) < 2:
            await message.reply("❌ Usage: /flyer <name>")
            return
        flyer_name = args[1].strip().lower()
        flyer = flyers_col.find_one({"chat_id": message.chat.id, "name": flyer_name})
        if not flyer:
            await message.reply(f"❌ Flyer '{flyer_name}' not found.")
            return
        await message.reply_photo(
            flyer["file_id"],
            caption=flyer.get("caption", None) or ""
        )
    except Exception as e:
        logger.exception("Error in flyer_handler")
        await message.reply("❌ Error showing flyer.")

async def listflyers_handler(client, message):
    try:
        flyers = list(flyers_col.find({"chat_id": message.chat.id}))
        if not flyers:
            await message.reply("No flyers set for this group.")
            return
        flyer_list = "\n".join([f"- <b>{f['name']}</b>" for f in flyers])
        await message.reply(
            f"📋 <b>Flyers for this group:</b>\n{flyer_list}",
            parse_mode="html"
        )
    except Exception as e:
        logger.exception("Error in listflyers_handler")
        await message.reply("❌ Error listing flyers.")

async def deleteflyer_handler(client, message):
    try:
        if not is_admin(message.from_user.id):
            await message.reply("❌ Only the group owner can delete flyers.")
            return
        args = (message.text or "").split(maxsplit=1)
        if len(args) < 2:
            await message.reply("❌ Usage: /deleteflyer <name>")
            return
        flyer_name = args[1].strip().lower()
        res = flyers_col.delete_one({"chat_id": message.chat.id, "name": flyer_name})
        if res.deleted_count:
            logger.info(f"Flyer '{flyer_name}' deleted by {message.from_user.id} in {message.chat.id}")
            await message.reply(f"✅ Flyer '{flyer_name}' deleted.")
        else:
            await message.reply(f"❌ Flyer '{flyer_name}' not found.")
    except Exception as e:
        logger.exception("Error in deleteflyer_handler")
        await message.reply("❌ Error deleting flyer.")

# --- REGISTRATION FUNCTION ---

def register(app):
    app.add_handler(MessageHandler(addflyer_handler, filters.command("addflyer") & filters.group))
    app.add_handler(MessageHandler(changeflyer_handler, filters.command("changeflyer") & filters.group))
    app.add_handler(MessageHandler(flyer_handler, filters.command("flyer") & filters.group))
    app.add_handler(MessageHandler(listflyers_handler, filters.command("listflyers") & filters.group))
    app.add_handler(MessageHandler(deleteflyer_handler, filters.command("deleteflyer") & filters.group))

# --- HELPER FOR SCHEDULER MODULE ---
def get_flyer_by_name(chat_id, name):
    flyer = flyers_col.find_one({"chat_id": chat_id, "name": name.lower()})
    if flyer:
        return flyer["file_id"], flyer.get("caption", "")
    return None, None

