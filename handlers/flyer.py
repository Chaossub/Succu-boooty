# handlers/flyer.py
import os

from pyrogram import filters
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DBNAME = os.environ.get("MONGO_DBNAME")

mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
flyer_collection = db["flyers"]

# Keep owner logic consistent with main.py
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611"))


def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID


def register(app):
    @app.on_message(filters.command("addflyer"))
    async def addflyer_handler(client, message):
        if not message.from_user or not is_admin(message.from_user.id):
            await message.reply("Only admins can add flyers.")
            return

        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=2)
        if len(args) < 2:
            await message.reply(
                "Usage: /addflyer <name> <caption>\n"
                "Attach or reply to a photo if you want an image flyer."
            )
            return

        name = args[1].strip().lower()
        caption = args[2] if len(args) > 2 else ""
        file_id = None

        if message.photo:
            file_id = message.photo.file_id
        elif message.reply_to_message and message.reply_to_message.photo:
            file_id = message.reply_to_message.photo.file_id

        flyer_type = "photo" if file_id else "text"

        try:
            flyer_collection.update_one(
                {"name": name},
                {
                    "$set": {
                        "name": name,
                        "caption": caption,
                        "file_id": file_id,
                        "type": flyer_type,
                    }
                },
                upsert=True,
            )
        except Exception as e:
            await message.reply(f"❌ Failed to save flyer: {e}")
            return

        await message.reply(
            f"✅ Flyer '<b>{name}</b>' saved{' with photo' if file_id else ''}.",
            disable_web_page_preview=True,
        )

    @app.on_message(filters.command("flyer"))
    async def flyer_handler(client, message):
        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /flyer <name>")
            return

        name = args[1].strip().lower()

        try:
            flyer = flyer_collection.find_one({"name": name})
        except Exception as e:
            await message.reply(f"❌ Failed to load flyer: {e}")
            return

        if not flyer:
            await message.reply(f"No flyer found with name '{name}'.")
            return

        if flyer.get("file_id") and flyer.get("type") == "photo":
            await message.reply_photo(
                flyer["file_id"], caption=flyer.get("caption", "")
            )
        else:
            await message.reply(flyer.get("caption", ""))

    @app.on_message(filters.command("listflyers"))
    async def listflyers_handler(client, message):
        try:
            flyers = list(flyer_collection.find({}, {"name": 1}))
        except Exception as e:
            await message.reply(f"❌ Failed to list flyers: {e}")
            return

        if not flyers:
            await message.reply("No flyers found.")
            return

        msg = "Available flyers:\n" + "\n".join(f"- {f['name']}" for f in flyers)
        await message.reply(msg)

    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer_handler(client, message):
        if not message.from_user or not is_admin(message.from_user.id):
            await message.reply("Only admins can delete flyers.")
            return

        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /deleteflyer <name>")
            return

        name = args[1].strip().lower()

        try:
            result = flyer_collection.delete_one({"name": name})
        except Exception as e:
            await message.reply(f"❌ Failed to delete flyer: {e}")
            return

        if result.deleted_count:
            await message.reply(f"🗑️ Flyer '{name}' deleted.")
        else:
            await message.reply(f"No flyer found with name '{name}'.")

    @app.on_message(filters.command("textflyer"))
    async def textflyer_handler(client, message):
        if not message.from_user or not is_admin(message.from_user.id):
            await message.reply("Only admins can convert flyers to text-only.")
            return

        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /textflyer <name>")
            return

        name = args[1].strip().lower()

        try:
            flyer = flyer_collection.find_one({"name": name})
        except Exception as e:
            await message.reply(f"❌ Failed to load flyer: {e}")
            return

        if not flyer:
            await message.reply(f"No flyer found with name '{name}'.")
            return

        try:
            flyer_collection.update_one(
                {"name": name},
                {"$set": {"file_id": None, "type": "text"}},
            )
        except Exception as e:
            await message.reply(f"❌ Failed to update flyer: {e}")
            return

        await message.reply(
            f"✅ Flyer '{name}' is now text-only. Use /flyer {name} to check."
        )
