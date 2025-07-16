import logging
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# MongoDB connection (global or via import)
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["SuccuBot"]
flyers = db["flyers"]

OWNER_ID = 6964994611  # <-- set to your Telegram ID

def is_admin(client: Client, message: Message):
    """Checks if user is admin or owner."""
    if message.from_user and message.from_user.id == OWNER_ID:
        return True
    try:
        member = client.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def admin_only(func):
    async def wrapper(client, message: Message):
        if not is_admin(client, message):
            await message.reply("❌ Only admins can use this command.")
            return
        await func(client, message)
    return wrapper

# --- Add flyer command ---
@Client.on_message(filters.command("addflyer") & filters.group)
@admin_only
async def addflyer(client, message: Message):
    """Adds a new flyer (photo or text only). Usage: /addflyer <name> <caption> (attach photo or just text)"""
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.reply("❌ Usage: /addflyer <name> <caption> (attach photo or just text)")
        return
    name = args[1].strip().lower()
    caption = args[2].strip() if len(args) > 2 else ""
    photo_id = None

    # Check for attached photo
    if message.photo:
        photo_id = message.photo.file_id

    flyer_doc = {
        "chat_id": message.chat.id,
        "name": name,
        "caption": caption,
        "photo_id": photo_id,
        "added_by": message.from_user.id
    }
    flyers.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": flyer_doc},
        upsert=True
    )
    await message.reply(f"✅ Flyer '{name}' saved{' with photo' if photo_id else ' (text only)'}.")

# --- Change flyer command ---
@Client.on_message(filters.command("changeflyer") & filters.group)
@admin_only
async def changeflyer(client, message: Message):
    """Change flyer photo or caption. Usage: reply to new photo or text with /changeflyer <name>"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Usage: /changeflyer <name> (reply to new photo or text)")
        return
    name = args[1].strip().lower()
    target = flyers.find_one({"chat_id": message.chat.id, "name": name})
    if not target:
        await message.reply(f"❌ Flyer '{name}' does not exist.")
        return

    # If reply to a photo, update the photo
    if message.reply_to_message and message.reply_to_message.photo:
        photo_id = message.reply_to_message.photo.file_id
        flyers.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"photo_id": photo_id}}
        )
        await message.reply(f"✅ Flyer '{name}' photo updated.")
        return

    # If reply to text, update caption
    if message.reply_to_message and message.reply_to_message.text:
        new_caption = message.reply_to_message.text
        flyers.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": {"caption": new_caption}}
        )
        await message.reply(f"✅ Flyer '{name}' caption updated.")
        return

    await message.reply("❌ Please reply to a new photo or text to update.")

# --- Delete flyer command ---
@Client.on_message(filters.command("deleteflyer") & filters.group)
@admin_only
async def deleteflyer(client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Usage: /deleteflyer <name>")
        return
    name = args[1].strip().lower()
    result = flyers.delete_one({"chat_id": message.chat.id, "name": name})
    if result.deleted_count:
        await message.reply(f"🗑️ Flyer '{name}' deleted.")
    else:
        await message.reply(f"❌ Flyer '{name}' not found.")

# --- List flyers command ---
@Client.on_message(filters.command("listflyers") & filters.group)
async def listflyers(client, message: Message):
    results = flyers.find({"chat_id": message.chat.id})
    names = [f"• <b>{f['name']}</b>" for f in results]
    if names:
        await message.reply(f"📋 Flyers in this group:\n" + "\n".join(names))
    else:
        await message.reply("No flyers found in this group.")

# --- Get flyer command ---
@Client.on_message(filters.command("flyer") & filters.group)
async def getflyer(client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❌ Usage: /flyer <name>")
        return
    name = args[1].strip().lower()
    flyer = flyers.find_one({"chat_id": message.chat.id, "name": name})
    if not flyer:
        await message.reply(f"❌ Flyer '{name}' not found.")
        return

    # Send photo + caption, or just text
    if flyer.get("photo_id"):
        await message.reply_photo(flyer["photo_id"], caption=flyer.get("caption", ""))
    else:
        await message.reply(flyer.get("caption", "❌ No content found for this flyer."))

def register(app):
    # All handlers are already registered via decorators above!
    logging.info("flyer.py handlers registered.")

