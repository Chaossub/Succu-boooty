# handlers/flyer.py
import logging
import os
from datetime import datetime
from typing import Optional, List

from pymongo import MongoClient, ASCENDING, errors as mongo_errors
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

log = logging.getLogger(__name__)

# ────────────── ENV / DB ──────────────

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME", "Succubot")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI / MONGODB_URI must be set for flyers")

mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
flyers_coll = db["flyers"]

# old index on "name" alone caused duplicate key issues; try to drop it quietly
try:
    flyers_coll.drop_index("name_1")
except Exception:
    pass

# unique per chat + name
flyers_coll.create_index(
    [("chat_id", ASCENDING), ("name", ASCENDING)],
    unique=True,
)

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))
MAX_CAPTION_LENGTH = 1024


# ────────────── HELPERS ──────────────


async def is_admin(client: Client, message: Message) -> bool:
    """Only allow owner or chat admins to create/update flyers."""
    if not message.from_user:
        return False

    user_id = message.from_user.id
    if user_id == OWNER_ID:
        return True

    try:
        member = await client.get_chat_member(message.chat.id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        log.warning("is_admin failed: %s", e)
        return False


def _get_command_text(message: Message) -> Optional[str]:
    """
    For messages with a photo and caption:
      - message.text is None
      - message.caption contains '/addflyer ...'
    For normal text commands:
      - message.text contains '/addflyer ...'
    """
    return message.text or message.caption


def _parse_addflyer_args(raw: str) -> Optional[tuple]:
    """
    Parse '/addflyer <name> <caption>' from raw text/caption.
    Returns (name, caption) or None if invalid.
    """
    parts = raw.split(maxsplit=2)
    if len(parts) < 3:
        return None

    _, name, caption = parts
    name = name.strip()
    caption = caption.strip()

    if not name or not caption:
        return None

    if len(caption) > MAX_CAPTION_LENGTH:
        caption = caption[:MAX_CAPTION_LENGTH]

    return name, caption


def _get_photo_file_id(message: Message) -> Optional[str]:
    """
    Get file_id from:
      - photo attached to the same message
      - OR a replied-to photo
    """
    if message.photo:
        # Pyrogram 2: message.photo is a Photo object
        return message.photo.file_id

    if message.reply_to_message and message.reply_to_message.photo:
        return message.reply_to_message.photo.file_id

    return None


# ────────────── COMMANDS ──────────────


async def addflyer_cmd(client: Client, message: Message):
    """
    /addflyer <name> <caption>
    - Must be sent with a photo attached in the same message
      OR as a reply to a photo.
    - Only admins / owner can use this.
    """
    if not await is_admin(client, message):
        return await message.reply("Only chat admins can add or update flyers.")

    raw = _get_command_text(message)
    parsed = _parse_addflyer_args(raw) if raw else None
    if not parsed:
        return await message.reply(
            "Usage:\n"
            "/addflyer <name> <caption>\n\n"
            "Example:\n"
            "/addflyer monday Merry & Mischievous Monday 💕"
        )

    name, caption = parsed
    name_key = name.lower()

    file_id = _get_photo_file_id(message)
    if not file_id:
        return await message.reply(
            "Please attach a photo to the same message (or reply to a photo) "
            "when using /addflyer."
        )

    doc = {
        "chat_id": message.chat.id,
        "name": name_key,
        "display_name": name,  # keep the original casing
        "caption": caption,
        "file_id": file_id,
        "type": "photo",
        "updated_at": datetime.utcnow(),
        "updated_by": message.from_user.id if message.from_user else None,
    }

    try:
        res = flyers_coll.update_one(
            {"chat_id": message.chat.id, "name": name_key},
            {"$set": doc},
            upsert=True,
        )
    except mongo_errors.DuplicateKeyError as e:
        log.error("DuplicateKeyError in addflyer_cmd: %s", e)
        return await message.reply(
            "I couldn't save that flyer because another flyer with the same "
            "name already exists and conflicts with an old index.\n\n"
            "Try a different name (like 'monday2') and I'll remember that one."
        )

    if res.matched_count:
        msg = f"✅ Flyer <b>{name}</b> updated with photo.\nUse <code>/flyer {name}</code> to send it."
    else:
        msg = f"✅ Flyer <b>{name}</b> saved with photo.\nUse <code>/flyer {name}</code> to send it."

    await message.reply(msg)


async def flyer_cmd(client: Client, message: Message):
    """
    /flyer <name>
    Everyone can use this.
    """
    raw = message.text
    if not raw:
        return

    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Usage: /flyer <name>")

    name = parts[1].strip().lower()
    if not name:
        return await message.reply("Usage: /flyer <name>")

    doc = flyers_coll.find_one(
        {"chat_id": message.chat.id, "name": name}
    ) or flyers_coll.find_one({"name": name})

    if not doc:
        return await message.reply(f"I couldn't find a flyer named <b>{name}</b> here.")

    caption = doc.get("caption") or ""
    file_id = doc.get("file_id")
    ftype = doc.get("type", "photo")

    try:
        if ftype == "photo" and file_id:
            await client.send_photo(
                message.chat.id,
                file_id,
                caption=caption or None,
            )
        else:
            await client.send_message(
                message.chat.id,
                caption or f"<b>{doc.get('display_name', name)}</b>",
            )
    except Exception as e:
        log.error("Failed to send flyer %s: %s", name, e)
        await message.reply("Something went wrong sending that flyer.")


async def flyerlist_cmd(client: Client, message: Message):
    """
    /flyerlist
    Everyone can use this.
    """
    cursor = flyers_coll.find({"chat_id": message.chat.id}).sort("name", ASCENDING)
    flyers: List[dict] = list(cursor)

    if not flyers:
        return await message.reply("No flyers saved in this chat yet.")

    lines = ["<b>Saved flyers in this chat:</b>"]
    for doc in flyers:
        display_name = doc.get("display_name", doc.get("name", ""))
        lines.append(f"• <code>{display_name}</code>")

    await message.reply("\n".join(lines))


# ────────────── REGISTER ──────────────


def register(app: Client):
    log.info("✅ handlers.flyer registered (flyer commands)")

    app.add_handler(
        MessageHandler(addflyer_cmd, filters.command("addflyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(flyer_cmd, filters.command("flyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(flyerlist_cmd, filters.command("flyerlist")),
        group=0,
    )
