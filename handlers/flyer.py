# handlers/flyer.py
import logging
import os
from datetime import datetime
from typing import List

from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

log = logging.getLogger(__name__)

# ────────────── MONGO ──────────────
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for flyers")

MONGO_DBNAME = os.getenv("MONGO_DBNAME") or "Succubot"

mongo = MongoClient(MONGO_URI)
db = mongo[MONGO_DBNAME]
flyers_coll = db["flyers"]
# one flyer name per chat
flyers_coll.create_index(
    [("chat_id", ASCENDING), ("name", ASCENDING)],
    unique=True,
)

# ────────────── ACCESS CONTROL ──────────────
OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))


def _parse_ids(env_name: str) -> List[int]:
    raw = os.getenv(env_name, "")
    ids: List[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            log.warning("Invalid ID in %s: %r", env_name, part)
    return ids


SUPER_ADMIN_IDS = set(_parse_ids("SUPER_ADMIN_IDS"))
MODEL_IDS = set(_parse_ids("MODEL_IDS"))

CREATOR_IDS = {OWNER_ID} | SUPER_ADMIN_IDS | MODEL_IDS


def is_creator(user_id: int) -> bool:
    # Who can /addflyer
    return user_id in CREATOR_IDS or user_id == OWNER_ID


# ────────────── HELPERS ──────────────

def normalize_name(name: str) -> str:
    return name.strip().lower()


def get_photo_file_id(msg: Message) -> str | None:
    """
    Returns the file_id of the photo attached to this message or its reply.
    Pyrogram v2: message.photo is a Photo object (not a list).
    """
    if msg.photo:
        return msg.photo.file_id

    if msg.reply_to_message and msg.reply_to_message.photo:
        return msg.reply_to_message.photo.file_id

    return None


def get_command_text(message: Message) -> str:
    """
    Return the raw command text for this message.
    For media messages, the command is in caption instead of text.
    """
    return (message.text or message.caption or "").strip()


# ────────────── COMMANDS ──────────────

async def addflyer_cmd(client: Client, message: Message):
    """
    /addflyer <name> <caption...>
    Must be sent with a photo attached OR as a reply to a photo.
    """
    if not is_creator(message.from_user.id):
        return await message.reply_text("Only admins and models can create flyers. 💋")

    raw = get_command_text(message)
    if not raw:
        return await message.reply_text(
            "Usage:\n"
            "<code>/addflyer &lt;name&gt; &lt;caption&gt;</code>\n"
            "• Send it with a photo attached, or reply to a photo.\n"
            "Example:\n"
            "<code>/addflyer monday Warm-up teaser for the boys 💕</code>"
        )

    parts = raw.split(maxsplit=2)
    if len(parts) < 2:
        return await message.reply_text(
            "Usage:\n"
            "<code>/addflyer &lt;name&gt; &lt;caption&gt;</code>\n"
            "• Send it with a photo attached, or reply to a photo."
        )

    # parts[0] is "/addflyer"
    name = normalize_name(parts[1])
    caption = parts[2] if len(parts) >= 3 else ""

    file_id = get_photo_file_id(message)
    if not file_id:
        return await message.reply_text(
            "I need a photo to save as a flyer.\n"
            "Attach a photo or reply to a photo when using /addflyer. 💌"
        )

    doc = {
        "chat_id": message.chat.id,
        "name": name,
        "file_id": file_id,
        "caption": caption,
        "updated_at": datetime.utcnow(),
        "updated_by": message.from_user.id,
    }

    res = flyers_coll.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": doc},
        upsert=True,
    )

    if res.matched_count:
        text = f"✅ Flyer <b>{name}</b> updated."
    else:
        text = f"✅ Flyer <b>{name}</b> saved."

    await message.reply_text(
        text
        + "\nYou can send it with <code>/flyer {}</code> or see all flyers with "
          "<code>/flyerlist</code>.".format(name)
    )


async def flyer_cmd(client: Client, message: Message):
    """
    /flyer <name>
    Anyone can use this to show a saved flyer in the current chat.
    """
    raw = get_command_text(message)
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text(
            "Usage: <code>/flyer &lt;name&gt;</code>\n"
            "Example: <code>/flyer monday</code>"
        )

    name = normalize_name(parts[1])

    doc = flyers_coll.find_one({"chat_id": message.chat.id, "name": name})
    if not doc:
        return await message.reply_text(f"❌ I don't have a flyer named <b>{name}</b> in this chat.")

    await client.send_photo(
        chat_id=message.chat.id,
        photo=doc["file_id"],
        caption=doc.get("caption") or "",
    )


async def flyerlist_cmd(client: Client, message: Message):
    """
    /flyerlist
    Show all flyer names for this chat.
    """
    cursor = flyers_coll.find({"chat_id": message.chat.id}).sort("name", ASCENDING)
    flyers = list(cursor)

    if not flyers:
        return await message.reply_text("No flyers saved for this chat yet. 🥺")

    lines = ["<b>Saved flyers in this chat:</b>"]
    for doc in flyers:
        lines.append(f"• <code>{doc['name']}</code>")

    await message.reply_text("\n".join(lines))


# ────────────── REGISTER ──────────────

def register(app: Client):
    log.info("✅ handlers.flyer registered (simple flyer commands)")
    app.add_handler(MessageHandler(addflyer_cmd, filters.command("addflyer")), group=0)
    app.add_handler(MessageHandler(flyer_cmd, filters.command("flyer")), group=0)
    app.add_handler(MessageHandler(flyerlist_cmd, filters.command("flyerlist")), group=0)
