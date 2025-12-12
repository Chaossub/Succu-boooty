# handlers/flyer.py
import logging
import os
from datetime import datetime
from typing import Optional

from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

log = logging.getLogger(__name__)

# ────────────── ENV / MONGO ──────────────
MONGO_URI = os.getenv("MONGO_DB_URI") or os.getenv("MONGO_URI")
MONGO_DBNAME = os.getenv("MONGO_DBNAME") or "Succubot"

if not MONGO_URI:
    raise RuntimeError("MONGO_DB_URI / MONGO_URI must be set for flyers")

mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
flyers_coll = db["flyers"]

# Unique per chat + name key
flyers_coll.create_index(
    [("chat_id", ASCENDING), ("key", ASCENDING)],
    unique=True,
    name="chat_key_unique",
)

MAX_CAPTION_LENGTH = 1024

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))  # you by default


# ────────────── HELPERS ──────────────
async def is_admin(client: Client, message: Message) -> bool:
    """Owner or chat admin can manage flyers."""
    if message.chat.type == "private":
        return True
    if not message.from_user:
        return False
    if message.from_user.id == OWNER_ID:
        return True

    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
    except Exception:
        return False

    return member.status in ("creator", "administrator")


def parse_addflyer_text(raw: Optional[str]) -> Optional[tuple[str, str]]:
    """
    Expect: /addflyer <name> <caption>
    Return (name, caption) or None if invalid.
    """
    if not raw:
        return None

    parts = raw.split(maxsplit=2)  # /addflyer, name, caption
    if len(parts) < 3:
        return None

    name = parts[1].strip()
    caption = parts[2].strip()
    if not name or not caption:
        return None

    if len(caption) > MAX_CAPTION_LENGTH:
        caption = caption[:MAX_CAPTION_LENGTH]

    return name, caption


# ────────────── COMMAND HANDLERS ──────────────
async def addflyer_cmd(client: Client, message: Message):
    """
    Usage:
      Send a photo with this as the message text OR caption:
        /addflyer <name> <caption>

    Example:
      (photo)
      /addflyer monday Merry & Mischievous Monday 💕
    """
    if not await is_admin(client, message):
        await message.reply_text("Only group admins can add or change flyers.")
        return

    # We want the command and args from either text OR caption
    raw_text = message.text or message.caption
    parsed = parse_addflyer_text(raw_text)
    if not parsed:
        await message.reply_text(
            "Usage:\n"
            "/addflyer <name> <caption>\n\n"
            "Example:\n"
            "/addflyer monday Merry & Mischievous Monday 💕",
            quote=True,
        )
        return

    name, caption = parsed

    if not message.photo:
        await message.reply_text(
            "Please send /addflyer *with a photo attached*.\n\n"
            "Example:\n"
            "(photo)\n"
            "/addflyer monday Merry & Mischievous Monday 💕",
            quote=True,
        )
        return

    # Largest size is last
    file_id = message.photo[-1].file_id

    key = name.lower()

    doc = {
        "chat_id": message.chat.id,
        "name": name,       # pretty display name
        "key": key,         # lowercase key for lookups
        "caption": caption,
        "photo_id": file_id,
        "updated_at": datetime.utcnow(),
    }

    # Upsert by chat_id + key
    flyers_coll.update_one(
        {"chat_id": message.chat.id, "key": key},
        {"$set": doc},
        upsert=True,
    )

    await message.reply_text(
        f"✅ Flyer <b>{name}</b> saved with photo.\n"
        f"Use <code>/flyer {name}</code> to send it.\n"
        f"Use <code>/flyerlist</code> to see all flyers.",
        quote=True,
    )


async def flyer_cmd(client: Client, message: Message):
    """
    /flyer <name> → sends the stored flyer in that chat
    """
    if not message.text:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            "Usage: /flyer <name>\n\nExample: /flyer monday\n"
            "See all flyers with /flyerlist.",
            quote=True,
        )
        return

    name = parts[1].strip()
    if not name:
        await message.reply_text(
            "Usage: /flyer <name>\nExample: /flyer monday",
            quote=True,
        )
        return

    key = name.lower()
    doc = flyers_coll.find_one({"chat_id": message.chat.id, "key": key})

    if not doc:
        await message.reply_text(
            f"I couldn’t find a flyer named <b>{name}</b> in this chat.\n"
            "Use /flyerlist to see what exists.",
            quote=True,
        )
        return

    caption = doc.get("caption") or ""
    photo_id = doc.get("photo_id")

    if photo_id:
        # Reply to user’s command in groups (but not required)
        reply_to = message.id if message.chat.type != "channel" else None
        await client.send_photo(
            chat_id=message.chat.id,
            photo=photo_id,
            caption=caption,
            reply_to_message_id=reply_to,
        )
    else:
        await message.reply_text(
            caption or f"(Flyer <b>{doc.get('name','?')}</b> has no content.)",
            quote=True,
        )


async def flyerlist_cmd(client: Client, message: Message):
    """
    /flyerlist → lists all flyer names in this chat
    """
    cursor = flyers_coll.find({"chat_id": message.chat.id}).sort("name", ASCENDING)
    names = [doc.get("name") for doc in cursor if doc.get("name")]

    if not names:
        await message.reply_text(
            "No flyers saved for this chat yet.\n"
            "Admins can create one with:\n"
            "/addflyer <name> <caption> (with a photo).",
            quote=True,
        )
        return

    text = "📌 <b>Flyers in this chat:</b>\n" + "\n".join(
        f"• <code>{n}</code>" for n in names
    )
    await message.reply_text(text, quote=True)


# ────────────── REGISTRATION ──────────────
def register(app: Client):
    log.info("[FLYER] Registering flyer handlers")

    app.add_handler(
        MessageHandler(addflyer_cmd, filters.command("addflyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(flyer_cmd, filters.command("flyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(
            flyerlist_cmd,
            filters.command(["flyerlist", "listflyers"]),
        ),
        group=0,
    )

    log.info("✅ handlers.flyer registered (flyer commands)")
