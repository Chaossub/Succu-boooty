import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# ---- Logging ----
logger = logging.getLogger(__name__)

# ---- MongoDB ----
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME") or "succubot"
mongo = MongoClient(MONGO_URI)[MONGO_DB]
flyers_col = mongo["flyers"]

# ---- Superuser ----
SUPER_ADMIN_ID = 6964994611

async def is_admin(client: Client, chat_id: int, user_id: int):
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def register(app: Client):
    logger.info("📢 flyer.register() called")

    # Add flyer (photo + caption OR text flyer)
    @app.on_message(filters.command("addflyer") & filters.group)
    async def addflyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply("❌ Admins only!")
            return

        if len(message.command) < 2:
            await message.reply("❌ Usage: /addflyer <name> <caption> (send photo for image flyer)")
            return

        name = message.command[1]
        caption = " ".join(message.command[2:]) if len(message.command) > 2 else ""
        if message.photo:
            # Photo flyer
            file_id = message.photo.file_id
            flyers_col.replace_one(
                {"name": name},
                {"name": name, "type": "photo", "file_id": file_id, "caption": caption},
                upsert=True,
            )
            await message.reply(f"✅ Saved flyer '{name}' (photo).")
        else:
            # Text flyer
            if not caption:
                await message.reply("❌ You must provide text for a text flyer!")
                return
            flyers_col.replace_one(
                {"name": name},
                {"name": name, "type": "text", "text": caption},
                upsert=True,
            )
            await message.reply(f"✅ Saved flyer '{name}' (text).")

    # Retrieve flyer by name
    @app.on_message(filters.command("flyer") & filters.group)
    async def get_flyer(client, message: Message):
        if len(message.command) < 2:
            await message.reply("❌ Usage: /flyer <name>")
            return
        name = message.command[1]
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            await message.reply("❌ Flyer not found!")
            return
        if flyer["type"] == "photo":
            await client.send_photo(message.chat.id, flyer["file_id"], caption=flyer.get("caption", ""))
        else:
            await message.reply(flyer.get("text", flyer.get("caption", "")))

    # List all flyers
    @app.on_message(filters.command("listflyers") & filters.group)
    async def list_flyers(client, message: Message):
        flyers = list(flyers_col.find({}))
        if not flyers:
            await message.reply("No flyers saved.")
            return
        lines = [f"- <b>{f['name']}</b> ({f['type']})" for f in flyers]
        await message.reply("<b>Flyers:</b>\n" + "\n".join(lines))

    # Change flyer (replace image, keep name)
    @app.on_message(filters.command("changeflyer") & filters.group)
    async def change_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply("❌ Admins only!")
            return

        if len(message.command) < 2 or not message.reply_to_message or not message.reply_to_message.photo:
            await message.reply("❌ Usage: Reply with /changeflyer <name> to a new photo")
            return

        name = message.command[1]
        flyer = flyers_col.find_one({"name": name})
        if not flyer:
            await message.reply("❌ Flyer not found!")
            return
        file_id = message.reply_to_message.photo.file_id
        flyers_col.update_one(
            {"name": name},
            {"$set": {"file_id": file_id, "type": "photo"}}
        )
        await message.reply(f"✅ Flyer '{name}' updated (new photo set).")

    # Delete flyer
    @app.on_message(filters.command("deleteflyer") & filters.group)
    async def delete_flyer(client, message: Message):
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply("❌ Admins only!")
            return
        if len(message.command) < 2:
            await message.reply("❌ Usage: /deleteflyer <name>")
            return
        name = message.command[1]
        flyers_col.delete_one({"name": name})
        await message.reply(f"✅ Flyer '{name}' deleted.")
