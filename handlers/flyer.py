import logging
import os
from typing import Optional

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from pymongo import MongoClient, errors

log = logging.getLogger(__name__)

# ────────────── MONGO SETUP ──────────────
mongo_uri = os.getenv("MONGO_URI")
mongo_db = os.getenv("MONGO_DBNAME") or "Succubot"

_mongo_client = MongoClient(mongo_uri)[mongo_db]
flyers_coll = _mongo_client["flyers"]

# Ensure we have a sane unique index (chat_id + name)
try:
    flyers_coll.create_index(
        [("chat_id", 1), ("name", 1)],
        unique=True,
        name="chat_name_unique",
    )
except errors.PyMongoError as e:
    # Don't crash the whole bot if index creation fails for some reason
    log.warning("flyers_coll.create_index failed: %s", e)


OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))


# ────────────── HELPERS ──────────────
async def _is_admin(app: Client, message: Message) -> bool:
    """Only allow the owner or chat admins to manage flyers."""
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return False

    if user_id == OWNER_ID:
        return True

    try:
        member = await app.get_chat_member(message.chat.id, user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        log.warning("Failed to check admin status: %s", e)
        return False


def _get_command_text(message: Message) -> str:
    """Return the raw text of the command, whether it's in text or caption."""
    return (message.text or message.caption or "").strip()


def _normalize_name(name: str) -> str:
    return name.strip().lower()


# ────────────── COMMAND HANDLERS ──────────────
async def addflyer_cmd(app: Client, message: Message):
    if not await _is_admin(app, message):
        await message.reply_text("Only admins can add flyers.")
        return

    raw = _get_command_text(message)
    parts = raw.split(maxsplit=2)  # /addflyer <name> <caption>

    if len(parts) < 3:
        await message.reply_text(
            "Usage: /addflyer <name> <caption> (send as the caption of a photo or reply to a photo)."
        )
        return

    name = _normalize_name(parts[1])
    caption = parts[2].strip()

    # Accept either: command as caption to a photo OR reply to a photo
    photo_msg: Optional[Message] = None
    if message.photo:
        photo_msg = message
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_msg = message.reply_to_message

    if not photo_msg or not photo_msg.photo:
        await message.reply_text(
            "Please send the command as the caption of a photo, or reply to a photo with the command."
        )
        return

    # In Pyrogram v2, message.photo is a Photo object (not a list)
    try:
        file_id = photo_msg.photo.file_id
    except AttributeError:
        # Very old style, just in case
        try:
            file_id = photo_msg.photo.sizes[-1].file_id
        except Exception:
            await message.reply_text("Sorry, I couldn't read that photo. Try sending a normal image.")
            return

    doc = {
        "chat_id": message.chat.id,
        "name": name,
        "title": parts[1].strip(),
        "caption": caption,
        "file_id": file_id,
        "type": "photo",
    }

    try:
        flyers_coll.update_one(
            {"chat_id": message.chat.id, "name": name},
            {"$set": doc},
            upsert=True,
        )
    except errors.PyMongoError as e:
        log.exception("Failed to save flyer: %s", e)
        await message.reply_text("Failed to save flyer in the database.")
        return

    await message.reply_text(
        f"✅ Flyer <b>{doc['title']}</b> saved with photo.\n"
        f"Use <code>/flyer {doc['title']}</code> to send it.",
        quote=True,
    )


async def flyerlist_cmd(app: Client, message: Message):
    cursor = flyers_coll.find({"chat_id": message.chat.id}).sort("name", 1)
    names = [doc.get("title") or doc["name"] for doc in cursor]

    if not names:
        await message.reply_text("No flyers saved in this chat yet.")
        return

    text_lines = ["Saved flyers:"] + [f"• <code>{n}</code>" for n in names]
    await message.reply_text("\n".join(text_lines))


async def flyer_cmd(app: Client, message: Message):
    raw = _get_command_text(message)
    parts = raw.split(maxsplit=1)  # /flyer <name>

    if len(parts) < 2:
        await message.reply_text("Usage: /flyer <name>")
        return

    name = _normalize_name(parts[1])
    doc = flyers_coll.find_one({"chat_id": message.chat.id, "name": name})

    if not doc:
        await message.reply_text(f"I couldn't find a flyer called <code>{parts[1]}</code>.")
        return

    caption = doc.get("caption") or doc.get("title") or name

    if doc.get("file_id"):
        await app.send_photo(
            chat_id=message.chat.id,
            photo=doc["file_id"],
            caption=caption,
        )
    else:
        await message.reply_text(caption)


async def deleteflyer_cmd(app: Client, message: Message):
    if not await _is_admin(app, message):
        await message.reply_text("Only admins can delete flyers.")
        return

    raw = _get_command_text(message)
    parts = raw.split(maxsplit=1)  # /deleteflyer <name>

    if len(parts) < 2:
        await message.reply_text("Usage: /deleteflyer <name>")
        return

    name = _normalize_name(parts[1])

    res = flyers_coll.delete_one({"chat_id": message.chat.id, "name": name})
    if res.deleted_count:
        await message.reply_text(f"🗑 Flyer <code>{parts[1]}</code> deleted.")
    else:
        await message.reply_text(f"I couldn't find a flyer called <code>{parts[1]}</code>.")


async def changeflyer_cmd(app: Client, message: Message):
    """Replace the image (and optionally caption) for an existing flyer."""
    if not await _is_admin(app, message):
        await message.reply_text("Only admins can change flyers.")
        return

    raw = _get_command_text(message)
    parts = raw.split(maxsplit=2)  # /changeflyer <name> [new caption]

    if len(parts) < 2:
        await message.reply_text(
            "Usage: /changeflyer <name> [new caption]\n"
            "Send this as the caption of the new photo, or reply to the new photo."
        )
        return

    name = _normalize_name(parts[1])
    new_caption = parts[2].strip() if len(parts) >= 3 else None

    photo_msg: Optional[Message] = None
    if message.photo:
        photo_msg = message
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_msg = message.reply_to_message

    if not photo_msg or not photo_msg.photo:
        await message.reply_text(
            "Please send the command as the caption of the NEW photo, or reply to the NEW photo."
        )
        return

    try:
        file_id = photo_msg.photo.file_id
    except AttributeError:
        try:
            file_id = photo_msg.photo.sizes[-1].file_id
        except Exception:
            await message.reply_text("Sorry, I couldn't read that photo. Try sending a normal image.")
            return

    update = {"file_id": file_id, "type": "photo"}
    if new_caption is not None:
        update["caption"] = new_caption

    res = flyers_coll.update_one(
        {"chat_id": message.chat.id, "name": name},
        {"$set": update},
    )

    if res.matched_count == 0:
        await message.reply_text(f"I couldn't find a flyer called <code>{parts[1]}</code>.")
    else:
        await message.reply_text(f"✅ Flyer <code>{parts[1]}</code> updated.")


# ────────────── REGISTRATION ──────────────
def register(app: Client):
    log.info("✅ handlers.flyer registered (flyer commands)")

    app.add_handler(
        MessageHandler(addflyer_cmd, filters.command("addflyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(flyerlist_cmd, filters.command(["flyerlist", "listflyers"])),
        group=0,
    )
    app.add_handler(
        MessageHandler(flyer_cmd, filters.command("flyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(deleteflyer_cmd, filters.command("deleteflyer")),
        group=0,
    )
    app.add_handler(
        MessageHandler(changeflyer_cmd, filters.command("changeflyer")),
        group=0,
    )
