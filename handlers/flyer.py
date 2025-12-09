# handlers/flyer.py
import os
import sys
from pymongo import MongoClient
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

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


def _debug(msg: str) -> None:
    """Tiny debug helper so we can see what the handler is doing."""
    line = f"[FLYER_DEBUG] {msg}"
    try:
        with open("/tmp/flyer_debug.log", "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Failed to write flyer_debug.log: {e}", file=sys.stderr)
    print(line, flush=True)


# ────────────── REGISTER HANDLERS ──────────────
def register(app):
    _debug("register(app) called in handlers.flyer")

    # --- /addflyer ---
    async def addflyer_handler(client, message: Message):
        _debug(f"/addflyer from {message.from_user.id if message.from_user else 'unknown'}: {message.text!r}")
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

        # photo can be on this message or a replied message
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
            _debug(f"/addflyer mongo error: {e}")
            await message.reply(f"❌ Failed to save flyer: {e}")
            return

        await message.reply(
            f"✅ Flyer '<b>{name}</b>' saved{' with photo' if file_id else ''}.",
            disable_web_page_preview=True,
        )

    # --- /flyer <name> ---
    async def flyer_handler(client, message: Message):
        _debug(f"/flyer raw message: {message.text!r}")
        msg_text = message.text or message.caption or ""
        args = msg_text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply("Usage: /flyer <name>")
            return

        name = args[1].strip().lower()
        _debug(f"/flyer requested name={name!r}")

        try:
            flyer = flyer_collection.find_one({"name": name})
        except Exception as e:
            _debug(f"/flyer mongo error: {e}")
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
            await message.reply(flyer.get("caption", "") or f"📢 Flyer: {name}")

    # --- /listflyers ---
    async def listflyers_handler(client, message: Message):
        _debug(f"/listflyers from {message.from_user.id if message.from_user else 'unknown'}")
        # FIRST, prove the handler is being hit:
        await message.reply("🛠 DEBUG: listflyers handler hit, checking DB…")

        try:
            flyers = list(flyer_collection.find({}, {"name": 1}))
        except Exception as e:
            _debug(f"/listflyers mongo error: {e}")
            await message.reply(f"❌ Failed to list flyers: {e}")
            return

        if not flyers:
            await message.reply("No flyers found.")
            return

        msg = "Available flyers:\n" + "\n".join(f"- {f['name']}" for f in flyers)
        await message.reply(msg)

    # --- /deleteflyer <name> ---
    async def deleteflyer_handler(client, message: Message):
        _debug(f"/deleteflyer raw: {message.text!r}")
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
            _debug(f"/deleteflyer mongo error: {e}")
            await message.reply(f"❌ Failed to delete flyer: {e}")
            return

        if result.deleted_count:
            await message.reply(f"🗑️ Flyer '{name}' deleted.")
        else:
            await message.reply(f"No flyer found with name '{name}'.")

    # --- /textflyer <name> ---
    async def textflyer_handler(client, message: Message):
        _debug(f"/textflyer raw: {message.text!r}")
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
            _debug(f"/textflyer mongo lookup error: {e}")
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
            _debug(f"/textflyer mongo update error: {e}")
            await message.reply(f"❌ Failed to update flyer: {e}")
            return

        await message.reply(
            f"✅ Flyer '{name}' is now text-only. Use /flyer {name} to check."
        )

    # ────────────── ACTUAL HANDLER REGISTRATION ──────────────
    # Putting them in group=-1 so they fire early and we’re 100% sure they attach.
    app.add_handler(MessageHandler(addflyer_handler, filters.command("addflyer")), group=-1)
    app.add_handler(MessageHandler(flyer_handler, filters.command("flyer")), group=-1)
    app.add_handler(MessageHandler(listflyers_handler, filters.command("listflyers")), group=-1)
    app.add_handler(MessageHandler(deleteflyer_handler, filters.command("deleteflyer")), group=-1)
    app.add_handler(MessageHandler(textflyer_handler, filters.command("textflyer")), group=-1)

    _debug("handlers.flyer register(app) finished; all commands hooked")
