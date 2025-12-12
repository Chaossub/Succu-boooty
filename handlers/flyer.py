# handlers/flyer.py

import os
from pyrogram import filters
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# ────────────── MONGO ──────────────
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DBNAME = os.environ.get("MONGO_DBNAME")

if not MONGO_URI or not MONGO_DBNAME:
    raise RuntimeError("MONGO_URI and MONGO_DBNAME must be set for flyers")

mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
flyer_collection = db["flyers"]

# ────────────── PERMS ──────────────
OWNER_ID = 6964994611
SUPER_ADMINS = {6964994611, 8087941938}  # you can edit this set

def is_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS

# ────────────── REGISTER ──────────────
def register(app):
    """
    Register flyer commands on the given Pyrogram app:
    - /addflyer <name> <caption>   (attach or reply to photo for image flyer)
    - /flyer <name>
    - /flyerlist  (alias: /listflyers)
    - /deleteflyer <name>
    - /textflyer <name>  (convert to text-only)
    """

    # ========= /addflyer =========
    @app.on_message(filters.command("addflyer"))
    async def addflyer_handler(client, message):
        # only admins / superadmins can create / edit flyers
        if not is_admin(message.from_user.id):
            await message.reply("Only admins can add or edit flyers.")
            return

        msg_text = (message.text or message.caption or "").strip()
        parts = msg_text.split(maxsplit=2)  # /addflyer name caption...

        if len(parts) < 2:
            await message.reply(
                "Usage: /addflyer <name> <caption>\n\n"
                "Attach a photo *or* reply to a photo with this command "
                "to make a photo flyer."
            )
            return

        name = parts[1].strip().lower()
        caption = parts[2] if len(parts) > 2 else ""

        # detect photo: either on this message or the replied-to message
        file_id = None
        if message.photo:
            file_id = message.photo.file_id
        elif message.reply_to_message and message.reply_to_message.photo:
            file_id = message.reply_to_message.photo.file_id

        flyer_type = "photo" if file_id else "text"

        doc = {
            "name": name,
            "caption": caption,
            "file_id": file_id,
            "type": flyer_type,
        }

        try:
            # upsert by name only (matches your unique index on "name")
            flyer_collection.update_one(
                {"name": name},
                {"$set": doc},
                upsert=True,
            )
        except DuplicateKeyError:
            # extremely unlikely with this filter, but just in case:
            flyer_collection.update_one({"name": name}, {"$set": doc}, upsert=False)

        await message.reply(
            f"✅ Flyer <b>{name}</b> saved"
            f"{' with photo' if file_id else ''}.\n"
            f"Use <code>/flyer {name}</code> to send it."
        )

    # ========= /flyer =========
    @app.on_message(filters.command("flyer"))
    async def flyer_handler(client, message):
        msg_text = (message.text or message.caption or "").strip()
        parts = msg_text.split(maxsplit=1)

        if len(parts) < 2:
            await message.reply("Usage: /flyer <name>")
            return

        name = parts[1].strip().lower()
        flyer = flyer_collection.find_one({"name": name})

        if not flyer:
            await message.reply(f"❌ No flyer found with name <b>{name}</b>.")
            return

        caption = flyer.get("caption", "")
        file_id = flyer.get("file_id")

        if file_id and flyer.get("type") == "photo":
            await message.reply_photo(file_id, caption=caption or None)
        else:
            await message.reply(caption or f"📢 Flyer: {name}")

    # ========= /flyerlist & /listflyers =========
    @app.on_message(filters.command(["flyerlist", "listflyers"]))
    async def flyerlist_handler(client, message):
        flyers = list(flyer_collection.find({}, {"_id": 0, "name": 1}).sort("name", 1))

        if not flyers:
            await message.reply("No flyers saved yet.")
            return

        lines = ["📂 <b>Available flyers:</b>"]
        for f in flyers:
            lines.append(f"• <code>{f['name']}</code>")

        await message.reply("\n".join(lines))

    # ========= /deleteflyer =========
    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            await message.reply("Only admins can delete flyers.")
            return

        msg_text = (message.text or message.caption or "").strip()
        parts = msg_text.split(maxsplit=1)

        if len(parts) < 2:
            await message.reply("Usage: /deleteflyer <name>")
            return

        name = parts[1].strip().lower()
        res = flyer_collection.delete_one({"name": name})

        if res.deleted_count:
            await message.reply(f"🗑️ Flyer <b>{name}</b> deleted.")
        else:
            await message.reply(f"❌ No flyer found with name <b>{name}</b>.")

    # ========= /textflyer =========
    @app.on_message(filters.command("textflyer"))
    async def textflyer_handler(client, message):
        if not is_admin(message.from_user.id):
            await message.reply("Only admins can convert flyers.")
            return

        msg_text = (message.text or message.caption or "").strip()
        parts = msg_text.split(maxsplit=1)

        if len(parts) < 2:
            await message.reply("Usage: /textflyer <name>")
            return

        name = parts[1].strip().lower()
        flyer = flyer_collection.find_one({"name": name})

        if not flyer:
            await message.reply(f"❌ No flyer found with name <b>{name}</b>.")
            return

        flyer_collection.update_one(
            {"name": name},
            {"$set": {"file_id": None, "type": "text"}},
        )
        await message.reply(
            f"✅ Flyer <b>{name}</b> is now text-only.\n"
            f"Use <code>/flyer {name}</code> to view it."
        )
