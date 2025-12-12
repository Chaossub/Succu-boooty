# handlers/flyer.py
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Set

from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.types import Message

log = logging.getLogger(__name__)

# ────────────── MONGO SETUP ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for flyers")

mongo = MongoClient(MONGO_URI)
db_name = os.getenv("MONGO_DBNAME") or "Succubot"
db = mongo[db_name]

flyers_coll = db["flyers"]
flyers_coll.create_index([("name", ASCENDING)], unique=True)

# ────────────── PERMISSIONS ──────────────

OWNER_ID = int(
    os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611")
)

# SUPER_ADMINS env: "123,456,789"
_super_admins_env = os.getenv("SUPER_ADMINS", "")
SUPER_ADMINS: Set[int] = set()
for part in _super_admins_env.split(","):
    part = part.strip()
    if not part:
        continue
    try:
        SUPER_ADMINS.add(int(part))
    except ValueError:
        log.warning("flyer.py: invalid SUPER_ADMINS entry %r", part)

# Always include owner as superadmin-equivalent
SUPER_ADMINS.add(OWNER_ID)

MAX_CAPTION_LENGTH = 1024  # Telegram caption limit


def _normalize_name(name: str) -> str:
    return name.strip().lower()


async def _is_flyer_admin(client: Client, m: Message) -> bool:
    """Owner, global super admins, or chat admins."""
    if not m.from_user:
        return False
    uid = m.from_user.id
    if uid == OWNER_ID or uid in SUPER_ADMINS:
        return True

    # If in a group, also treat Telegram admins as allowed
    try:
        member = await client.get_chat_member(m.chat.id, uid)
        if member.status in ("administrator", "creator"):
            return True
    except Exception:
        pass

    return False


# ────────────── CORE HELPERS ──────────────

def _get_photo_from_message_or_reply(m: Message) -> Optional[str]:
    """Return file_id of photo from this message or replied-to message."""
    if m.photo:
        return m.photo.file_id
    if m.reply_to_message and m.reply_to_message.photo:
        return m.reply_to_message.photo.file_id
    return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ────────────── COMMAND HANDLERS ──────────────

async def addflyer_cmd(client: Client, m: Message):
    if not await _is_flyer_admin(client, m):
        await m.reply_text("You don’t have permission to manage flyers.")
        return

    caption_text = (m.caption or m.text or "").strip()
    if not caption_text.startswith("/addflyer"):
        await m.reply_text(
            "Usage (with photo):\n"
            "<b>Send a photo</b> and set this as the caption:\n"
            "<code>/addflyer &lt;name&gt; &lt;caption&gt;</code>\n\n"
            "Example:\n"
            "<code>/addflyer monday Merry & Mischievous Monday 💋 ...</code>"
        )
        return

    # We expect: /addflyer <name> <caption...>
    parts = caption_text.split(maxsplit=2)
    if len(parts) < 2:
        await m.reply_text(
            "Please provide a name.\n"
            "Example:\n<code>/addflyer monday Merry & Mischievous Monday 💋 ...</code>"
        )
        return

    raw_name = parts[1]
    name = _normalize_name(raw_name)
    flyer_caption = ""
    if len(parts) >= 3:
        flyer_caption = parts[2].strip()

    if len(flyer_caption) > MAX_CAPTION_LENGTH:
        await m.reply_text(
            f"Caption is too long ({len(flyer_caption)} characters). "
            f"Telegram allows up to {MAX_CAPTION_LENGTH}."
        )
        return

    file_id = _get_photo_from_message_or_reply(m)
    if not file_id:
        await m.reply_text(
            "You need to attach a photo, or reply to a photo, when using /addflyer."
        )
        return

    existing = flyers_coll.find_one({"name": name})
    doc = {
        "name": name,
        "file_id": file_id,
        "caption": flyer_caption,
        "home_chat_id": m.chat.id,
        "created_by": m.from_user.id if m.from_user else None,
        "updated_at": _now_utc(),
    }
    if existing:
        # Preserve original created_at if present
        doc["created_at"] = existing.get("created_at", _now_utc())
        flyers_coll.update_one({"name": name}, {"$set": doc}, upsert=True)
        await m.reply_text(f"✅ Flyer <b>{name}</b> updated.")
        log.info("flyer.py: updated flyer %s", name)
    else:
        doc["created_at"] = _now_utc()
        flyers_coll.insert_one(doc)
        await m.reply_text(f"✅ Flyer <b>{name}</b> saved.")
        log.info("flyer.py: created flyer %s", name)


async def flyer_cmd(client: Client, m: Message):
    # Everyone can use this
    text = (m.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await m.reply_text("Usage: <code>/flyer &lt;name&gt;</code>")
        return

    name = _normalize_name(parts[1])
    doc = flyers_coll.find_one({"name": name})
    if not doc:
        await m.reply_text(f"❌ No flyer named <b>{name}</b>.")
        return

    file_id = doc.get("file_id")
    caption = doc.get("caption") or ""
    try:
        await client.send_photo(m.chat.id, file_id, caption=caption)
    except Exception as e:
        log.warning("flyer.py: failed to send flyer %s: %s", name, e)
        await m.reply_text("Failed to send flyer. Maybe the photo is no longer available.")


async def flyerlist_cmd(client: Client, m: Message):
    # Everyone can use this
    docs = list(flyers_coll.find({}, {"name": 1}).sort("name", ASCENDING))
    if not docs:
        await m.reply_text("No flyers have been created yet.")
        return

    lines = ["Available flyers:"]
    for d in docs:
        lines.append(f"• <code>{d['name']}</code>")

    await m.reply_text("\n".join(lines))


async def changeflyer_cmd(client: Client, m: Message):
    if not await _is_flyer_admin(client, m):
        await m.reply_text("You don’t have permission to manage flyers.")
        return

    text = (m.text or "").strip()
    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        await m.reply_text(
            "Usage:\n"
            "Reply to a photo with:\n"
            "<code>/changeflyer &lt;name&gt; [new caption]</code>"
        )
        return

    name = _normalize_name(parts[1])
    new_caption: Optional[str] = None
    if len(parts) >= 3:
        new_caption = parts[2].strip()

    if new_caption and len(new_caption) > MAX_CAPTION_LENGTH:
        await m.reply_text(
            f"Caption is too long ({len(new_caption)} characters). "
            f"Telegram allows up to {MAX_CAPTION_LENGTH}."
        )
        return

    doc = flyers_coll.find_one({"name": name})
    if not doc:
        await m.reply_text(f"❌ No flyer named <b>{name}</b>.")
        return

    file_id = _get_photo_from_message_or_reply(m)
    if not file_id and new_caption is None:
        await m.reply_text(
            "Reply to a photo or provide a new caption (or both) to update this flyer."
        )
        return

    update = {"updated_at": _now_utc()}
    if file_id:
        update["file_id"] = file_id
    if new_caption is not None:
        update["caption"] = new_caption

    flyers_coll.update_one({"name": name}, {"$set": update})
    await m.reply_text(f"✅ Flyer <b>{name}</b> updated.")
    log.info("flyer.py: changeflyer updated %s", name)


async def deleteflyer_cmd(client: Client, m: Message):
    if not await _is_flyer_admin(client, m):
        await m.reply_text("You don’t have permission to manage flyers.")
        return

    text = (m.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await m.reply_text("Usage: <code>/deleteflyer &lt;name&gt;</code>")
        return

    name = _normalize_name(parts[1])
    doc = flyers_coll.find_one({"name": name})
    if not doc:
        await m.reply_text(f"❌ No flyer named <b>{name}</b>.")
        return

    flyers_coll.delete_one({"name": name})
    await m.reply_text(f"✅ Flyer <b>{name}</b> deleted.")
    log.info("flyer.py: deleted flyer %s", name)


# ────────────── REGISTER ──────────────

def register(app: Client):
    log.info("✅ handlers.flyer registered (/addflyer, /flyer, /flyerlist, /changeflyer, /deleteflyer)")

    # Add flyer: must be used with a photo (caption) or replying to one
    app.add_handler(
        # /addflyer in caption OR text
        # filters.photo ensures we catch photo+caption, but we also allow plain text in reply
        # so we don't restrict by photo filter here.
        filters=filters.command("addflyer"),
        handler=addflyer_cmd,
        group=0,
    )

    # In Pyrogram v2, use app.add_handler(MessageHandler(...))
    from pyrogram.handlers import MessageHandler

    app.add_handler(MessageHandler(addflyer_cmd, filters.command("addflyer")), group=0)
    app.add_handler(MessageHandler(flyer_cmd, filters.command("flyer")), group=0)
    app.add_handler(MessageHandler(flyerlist_cmd, filters.command("flyerlist")), group=0)
    app.add_handler(MessageHandler(changeflyer_cmd, filters.command("changeflyer")), group=0)
    app.add_handler(MessageHandler(deleteflyer_cmd, filters.command("deleteflyer")), group=0)
