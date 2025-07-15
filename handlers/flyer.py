import os
from pyrogram import filters
from pyrogram.types import Message
from pymongo import MongoClient

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME", "succubot")
mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DB]
flyers = db.flyers

ADMIN_IDS = [6964994611]  # Update with your admin user IDs

def admin_filter(_, __, m: Message):
    return m.from_user and m.from_user.id in ADMIN_IDS

def register(app):
    # Add a flyer
    @app.on_message(filters.command("addflyer") & filters.create(admin_filter))
    async def addflyer(client, message):
        msg_text = message.text or message.caption
        if not msg_text:
            return await message.reply(
                "❌ Usage: `/addflyer <name> <caption>` (as text, caption, or with a replied photo/doc)",
                quote=True,
            )
        args = msg_text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply(
                "❌ Usage: `/addflyer <name> <caption>` (as text, caption, or with a replied photo/doc)",
                quote=True,
            )
        flyer_name = args[1]
        caption = args[2]
        file_id = None
        # Prefer replied-to media if present
        if message.reply_to_message:
            if message.reply_to_message.photo:
                file_id = message.reply_to_message.photo.file_id
            elif message.reply_to_message.document:
                file_id = message.reply_to_message.document.file_id
            elif message.reply_to_message.text:
                caption = message.reply_to_message.text
        # Otherwise, check this message for media
        elif message.photo:
            file_id = message.photo.file_id
        elif message.document:
            file_id = message.document.file_id

        flyers.update_one(
            {"name": flyer_name},
            {"$set": {"name": flyer_name, "file_id": file_id, "caption": caption}},
            upsert=True
        )
        await message.reply(f"✅ Flyer '{flyer_name}' added.")

    # Get a flyer by name
    @app.on_message(filters.command("flyer"))
    async def getflyer(client, message):
        msg_text = message.text or message.caption
        args = msg_text.split(maxsplit=1) if msg_text else []
        if len(args) < 2:
            return await message.reply("❌ Usage: /flyer <name>")
        flyer = flyers.find_one({"name": args[1].strip()})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        if flyer.get("file_id"):
            await message.reply_photo(flyer["file_id"], caption=flyer.get("caption", ""))
        else:
            await message.reply(flyer.get("caption", ""))

    # List all flyers
    @app.on_message(filters.command("listflyers"))
    async def listflyers(client, message):
        flyer_list = [f"• <b>{f['name']}</b>" for f in flyers.find({})]
        if flyer_list:
            await message.reply("📋 <b>Flyers:</b>\n" + "\n".join(flyer_list))
        else:
            await message.reply("No flyers added yet.")

    # Change/update flyer by name
    @app.on_message(filters.command("changeflyer") & filters.create(admin_filter))
    async def changeflyer(client, message):
        msg_text = message.text or message.caption
        args = msg_text.split(maxsplit=1) if msg_text else []
        if len(args) < 2:
            return await message.reply("❌ Usage: /changeflyer <name> (reply to new photo/doc/text)")
        flyer_name = args[1].strip()
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        file_id = flyer.get("file_id")
        caption = flyer.get("caption", "")
        if message.reply_to_message:
            if message.reply_to_message.photo:
                file_id = message.reply_to_message.photo.file_id
            elif message.reply_to_message.document:
                file_id = message.reply_to_message.document.file_id
            elif message.reply_to_message.text:
                caption = message.reply_to_message.text
        elif message.photo:
            file_id = message.photo.file_id
        elif message.document:
            file_id = message.document.file_id
        flyers.update_one({"name": flyer_name}, {"$set": {"file_id": file_id, "caption": caption}})
        await message.reply(f"✅ Flyer '{flyer_name}' updated.")

    # Delete flyer by name
    @app.on_message(filters.command("deleteflyer") & filters.create(admin_filter))
    async def deleteflyer(client, message):
        msg_text = message.text or message.caption
        args = msg_text.split(maxsplit=1) if msg_text else []
        if len(args) < 2:
            return await message.reply("❌ Usage: /deleteflyer <name>")
        result = flyers.delete_one({"name": args[1].strip()})
        if result.deleted_count:
            await message.reply("✅ Flyer deleted.")
        else:
            await message.reply("❌ Flyer not found.")
