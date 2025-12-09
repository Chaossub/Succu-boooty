# handlers/flyer.py
import os
import sys
from pymongo import MongoClient
from pyrogram import filters

# ────────────── MONGO ──────────────
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DBNAME = os.environ.get("MONGO_DBNAME")

mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
flyer_collection = db["flyers"]

# ────────────── OWNER / ADMIN ──────────────
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611"))


def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID


def _dbg(msg: str) -> None:
    """Log to console + a tiny debug file so we can see what's happening."""
    line = f"[FLYER_DEBUG] {msg}"
    try:
        with open("/tmp/flyer_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Failed to write flyer_debug.log: {e}", file=sys.stderr)
    print(line, flush=True)


def register(app):
    _dbg("register(app) called in handlers.flyer")

    # /addflyer <name> <caption> (photo attached OR replying to a photo makes it an image flyer)
    @app.on_message(filters.command("addflyer"))
    async def addflyer_handler(client, message):
        _dbg(f"/addflyer from {getattr(message.from_user, 'id', None)}: {message.text!r}")
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
            _dbg(f"/addflyer mongo error: {e}")
            await message.reply(f"❌ Failed to save flyer: {e}")
            return

        await message.reply(
            f"✅ Flyer '<b>{name}</b>' saved{' with photo' if file_id else ''}.",
            disable_web_page_preview=True,
        )

    # /flyer <name> – send a flyer immediately
    @app.on_message(filters.command("flyer"))
    async def flyer_handler(client, message):
        _dbg(f"/flyer raw: {message.text!r}")
        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /flyer <name>")
            return

        name = args[1].strip().lower()
        _dbg(f"/flyer requested name={name!r}")

        try:
            flyer = flyer_collection.find_one({"name": name})
        except Exception as e:
            _dbg(f"/flyer mongo error: {e}")
            await message.reply(f"❌ Failed to load flyer: {e}")
            return

        if not flyer:
            await message.reply(f"No flyer found with name '{name}'.")
            return

        file_id = flyer.get("file_id")
        caption = flyer.get("caption", "") or f"📢 Flyer: {name}"

        if file_id and flyer.get("type") == "photo":
            await message.reply_photo(file_id, caption=caption)
        else:
            await message.reply(caption)

    # /listflyers – list flyer names
    @app.on_message(filters.command("listflyers"))
    async def listflyers_handler(client, message):
        _dbg(f"/listflyers from {getattr(message.from_user, 'id', None)}")
        # Debug reply so we KNOW the handler fired
        await message.reply("🛠 DEBUG: listflyers handler hit, checking DB…")

        try:
            flyers = list(flyer_collection.find({}, {"name": 1}))
        except Exception as e:
            _dbg(f"/listflyers mongo error: {e}")
            await message.reply(f"❌ Failed to list flyers: {e}")
            return

        if not flyers:
            await message.reply("No flyers found.")
            return

        lines = []
        for f in flyers:
            name = f.get("name") or "(unnamed)"
            lines.append(f"- {name}")

        msg = "Available flyers:\n" + "\n".join(lines)
        await message.reply(msg)

    # /deleteflyer <name>
    @app.on_message(filters.command("deleteflyer"))
    async def deleteflyer_handler(client, message):
        _dbg(f"/deleteflyer raw: {message.text!r}")
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
            _dbg(f"/deleteflyer mongo error: {e}")
            await message.reply(f"❌ Failed to delete flyer: {e}")
            return

        if result.deleted_count:
            await message.reply(f"🗑️ Flyer '{name}' deleted.")
        else:
            await message.reply(f"No flyer found with name '{name}'.")

    # /textflyer <name> – strip image, keep as text
    @app.on_message(filters.command("textflyer"))
    async def textflyer_handler(client, message):
        _dbg(f"/textflyer raw: {message.text!r}")
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
            _dbg(f"/textflyer mongo lookup error: {e}")
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
            _dbg(f"/textflyer mongo update error: {e}")
            await message.reply(f"❌ Failed to update flyer: {e}")
            return

        await message.reply(
            f"✅ Flyer '{name}' is now text-only. Use /flyer {name} to check."
        )

    _dbg("handlers.flyer register(app) finished; all flyer commands hooked")
