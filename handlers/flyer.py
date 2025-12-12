# handlers/flyer.py
import logging
import os
from datetime import datetime

from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

log = logging.getLogger(__name__)

# ────────────── MONGO SETUP ──────────────
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME") or "Succubot"

if not MONGO_URI or not MONGO_DBNAME:
    raise RuntimeError("MONGO_URI / MONGO_DBNAME must be set for flyers")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DBNAME]
flyers_coll = db["flyers"]

# Old code created a unique index just on "name".
# That caused E11000 when you reused a name.
# Drop it if it exists, then create a composite index per chat.
try:
    flyers_coll.drop_index("name_1")
except Exception:
    # Index might not exist yet; ignore.
    pass

flyers_coll.create_index(
    [("chat_id", ASCENDING), ("name", ASCENDING)],
    unique=True,
)

# ────────────── CONFIG ──────────────
OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))


def _normalize_name(raw: str) -> str:
    return raw.strip().lower()


def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def _ensure_admin(message: Message) -> bool:
    """
    Only owner / chat admins can manage flyers.
    Everyone can *use* them.
    """
    if message.from_user is None:
        await message.reply("I can't see who you are.")
        return False

    user_id = message.from_user.id
    if _is_owner(user_id):
        return True

    # Also allow Telegram admins in that chat
    try:
        member = await message.chat.get_member(user_id)
        if member.status in ("administrator", "creator"):
            return True
    except Exception:
        pass

    await message.reply("Only admins can manage flyers.")
    return False


# ────────────── HELPERS ──────────────
def _extract_media(base: Message):
    """
    Return (media_type, file_id) from a message
    that contains a photo / sticker / image document.
    """
    if base.photo:
        # base.photo is a Photo object in Pyrogram 2
        # It already has file_id (largest size).
        return "photo", base.photo.file_id
    if base.sticker:
        return "sticker", base.sticker.file_id
    if base.document and base.document.mime_type:
        if base.document.mime_type.startswith("image/"):
            return "document", base.document.file_id
    return None, None


# ────────────── COMMANDS ──────────────
async def addflyer_cmd(client: Client, message: Message):
    """
    /addflyer <name> <caption>
    (send with a photo OR reply to a photo/sticker/image doc)
    """
    if not await _ensure_admin(message):
        return

    base = message.reply_to_message or message
    media_type, file_id = _extract_media(base)

    if not file_id:
        await message.reply(
            "Reply to a photo/sticker/image (or send one) with:\n"
            "/addflyer <name> <caption>"
        )
        return

    text = message.text or ""
    parts = text.split(maxsplit=2)

    if len(parts) < 2:
        await message.reply(
            "Usage:\n/addflyer <name> <caption>\n"
            "Example: /addflyer monday Merry & Mischievous Monday 💕"
        )
        return

    name = _normalize_name(parts[1])

    # Caption from command text, or fall back to media caption
    if len(parts) >= 3:
        caption = parts[2]
    else:
        caption = base.caption or ""

    doc = {
        "chat_id": message.chat.id,
        "name": name,
        "file_id": file_id,
        "caption": caption or "",
        "type": media_type,
        "updated_at": datetime.utcnow(),
    }

    try:
        flyers_coll.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": doc},
            upsert=True,
        )
    except DuplicateKeyError:
        await message.reply(
            "A flyer with that name already exists in this chat. "
            "Try a different name."
        )
        return

    await message.reply(
        f"✅ Flyer <b>{name}</b> saved with photo.\n"
        f"Use <code>/flyer {name}</code> to send it.",
        quote=True,
    )


async def flyer_cmd(client: Client, message: Message):
    """
    /flyer <name>  → send the saved flyer in this chat
    """
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Usage: /flyer <name>")
        return

    name = _normalize_name(parts[1])

    flyer = flyers_coll.find_one(
        {"chat_id": message.chat.id, "name": name}
    )
    if not flyer:
        await message.reply("I couldn’t find a flyer with that name in this chat.")
        return

    caption = flyer.get("caption") or ""
    file_id = flyer.get("file_id")
    ftype = flyer.get("type") or "photo"

    try:
        if ftype == "photo":
            await client.send_photo(message.chat.id, file_id, caption=caption or None)
        elif ftype == "sticker":
            await client.send_sticker(message.chat.id, file_id)
            if caption:
                await client.send_message(message.chat.id, caption)
        elif ftype == "document":
            await client.send_document(message.chat.id, file_id, caption=caption or None)
        else:
            # Fallback: just text
            if caption:
                await client.send_message(message.chat.id, caption)
            else:
                await client.send_message(message.chat.id, f"[flyer {name}]")
    except Exception as e:
        log.exception("Failed to send flyer %s: %s", name, e)
        await message.reply("I couldn't send that flyer (maybe the file ID expired).")


async def flyerlist_cmd(client: Client, message: Message):
    """
    /flyerlist or /listflyers → list flyer names in this chat
    """
    flyers = list(
        flyers_coll.find({"chat_id": message.chat.id}).sort("name", ASCENDING)
    )
    if not flyers:
        await message.reply("No flyers saved in this chat yet.")
        return

    lines = ["📎 <b>Flyers in this chat:</b>"]
    for f in flyers:
        lines.append(f"• <code>{f['name']}</code>")

    await message.reply("\n".join(lines))


async def deleteflyer_cmd(client: Client, message: Message):
    """
    /deleteflyer <name>  (admin only)
    """
    if not await _ensure_admin(message):
        return

    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Usage: /deleteflyer <name>")
        return

    name = _normalize_name(parts[1])
    res = flyers_coll.delete_one(
        {"chat_id": message.chat.id, "name": name}
    )

    if res.deleted_count:
        await message.reply(f"🗑 Flyer <b>{name}</b> deleted.")
    else:
        await message.reply("I couldn’t find that flyer in this chat.")


async def changeflyer_cmd(client: Client, message: Message):
    """
    /changeflyer <name> (admin only)
    Reply to the new image/sticker to replace the existing flyer media.
    """
    if not await _ensure_admin(message):
        return

    base = message.reply_to_message or message
    media_type, file_id = _extract_media(base)
    if not file_id:
        await message.reply(
            "Reply to the new photo/sticker/image for this flyer.\n"
            "Usage: /changeflyer <name>"
        )
        return

    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Usage: /changeflyer <name>")
        return

    name = _normalize_name(parts[1])

    update = {
        "file_id": file_id,
        "type": media_type,
        "updated_at": datetime.utcnow(),
    }

    flyers_coll.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": update},
        upsert=False,
    )
    await message.reply(f"✅ Flyer <b>{name}</b> updated with new image.")


# ────────────── REGISTER ──────────────
def register(app: Client):
    log.info("✅ handlers.flyer registered (Mongo flyers)")

    app.add_handler(MessageHandler(addflyer_cmd, filters.command("addflyer")))
    app.add_handler(MessageHandler(flyer_cmd, filters.command("flyer")))
    app.add_handler(MessageHandler(flyerlist_cmd, filters.command("flyerlist")))
    app.add_handler(MessageHandler(flyerlist_cmd, filters.command("listflyers")))
    app.add_handler(MessageHandler(deleteflyer_cmd, filters.command("deleteflyer")))
    app.add_handler(MessageHandler(changeflyer_cmd, filters.command("changeflyer")))
