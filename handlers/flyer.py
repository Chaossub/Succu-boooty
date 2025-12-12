# handlers/flyer.py
import logging
import os
from datetime import datetime, timezone

from typing import Optional, List

from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

log = logging.getLogger(__name__)

# ────────────── ENV / DB ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for flyers")

mongo = MongoClient(MONGO_URI)
db = mongo["Succubot"]
flyers_coll = db["flyers"]
flyers_coll.create_index([("name", ASCENDING)], unique=True)

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611"))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_name(name: str) -> str:
    return name.strip().lower()


async def _is_chat_admin(client: Client, message: Message) -> bool:
    """
    Only allow:
      • OWNER_ID anywhere
      • Chat admins / creator in groups & supergroups
      • In DMs, only OWNER_ID is allowed
    """
    if not message.from_user:
        return False

    uid = message.from_user.id
    if uid == OWNER_ID:
        return True

    if message.chat and message.chat.type in ("group", "supergroup"):
        try:
            member = await client.get_chat_member(message.chat.id, uid)
            return member.status in ("creator", "administrator")
        except Exception as e:
            log.warning("flyer: get_chat_member failed: %s", e)
            return False

    # non-group chats → only owner; we already checked that
    return False


# ────────────── Command handlers ──────────────


async def addflyer_cmd(client: Client, message: Message):
    """
    /addflyer <name> <caption>

    Used either:
      • as a *caption* on a photo
      • or as a text command replying to a photo
    """
    if not await _is_chat_admin(client, message):
        await message.reply_text("Only Sanctuary admins can create or update flyers.")
        return

    # Figure out which photo to use
    photo_msg: Optional[Message] = None
    if message.photo:
        photo_msg = message
    elif message.reply_to_message and message.reply_to_message.photo:
        photo_msg = message.reply_to_message

    if not photo_msg or not photo_msg.photo:
        await message.reply_text(
            "Attach a photo with the command, or reply to a photo with:\n"
            "<code>/addflyer &lt;name&gt; &lt;caption&gt;</code>"
        )
        return

    # Parse text (caption or message text)
    raw = (message.text or message.caption or "").strip()
    parts = raw.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text(
            "Usage:\n"
            "<code>/addflyer &lt;name&gt; &lt;caption&gt;</code>\n\n"
            "Example:\n"
            "<code>/addflyer monday Merry &amp; Mischievous Monday 💋</code>"
        )
        return

    _, name, caption = parts
    norm = _normalize_name(name)
    file_id = photo_msg.photo.file_id

    doc = {
        "name": norm,
        "file_id": file_id,
        "caption": caption,
        "updated_at": _now_utc(),
    }

    # Preserve first creator if it exists
    existing = flyers_coll.find_one({"name": norm})
    if existing:
        doc.setdefault("created_at", existing.get("created_at") or _now_utc())
        doc.setdefault("created_by", existing.get("created_by") or message.from_user.id)
    else:
        doc["created_at"] = _now_utc()
        if message.from_user:
            doc["created_by"] = message.from_user.id

    flyers_coll.update_one({"name": norm}, {"$set": doc}, upsert=True)

    await message.reply_text(
        f"✅ Flyer <b>{name}</b> saved.\n"
        "You can send it with <code>/flyer "
        f"{name}</code> or see all flyers with <code>/flyerlist</code>."
    )


async def flyer_cmd(_: Client, message: Message):
    """
    /flyer <name> → send that flyer (anyone can use)
    """
    raw = (message.text or "").strip()
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            "Usage:\n"
            "<code>/flyer &lt;name&gt;</code>\n\n"
            "Use <code>/flyerlist</code> to see available names."
        )
        return

    name = parts[1].strip()
    norm = _normalize_name(name)
    doc = flyers_coll.find_one({"name": norm})
    if not doc:
        await message.reply_text(
            f"❌ I couldn't find a flyer named <b>{name}</b>.\n"
            "Use <code>/flyerlist</code> to see what's saved."
        )
        return

    try:
        await message.reply_photo(
            doc["file_id"],
            caption=doc.get("caption") or "",
        )
    except Exception as e:
        log.warning("flyer: failed to send flyer %s: %s", name, e)
        await message.reply_text("I couldn’t send that flyer (maybe the file_id expired?).")


async def flyerlist_cmd(_: Client, message: Message):
    """
    /flyerlist → show all saved flyers
    """
    docs: List[dict] = list(flyers_coll.find().sort("name", ASCENDING))
    if not docs:
        await message.reply_text("No flyers saved yet.")
        return

    lines = ["📌 <b>Saved flyers:</b>"]
    for d in docs:
        name = d["name"]
        preview = (d.get("caption") or "").strip().replace("\n", " ")
        if len(preview) > 60:
            preview = preview[:57] + "…"
        if preview:
            lines.append(f"• <code>{name}</code> — {preview}")
        else:
            lines.append(f"• <code>{name}</code>")

    await message.reply_text("\n".join(lines))


async def deleteflyer_cmd(client: Client, message: Message):
    """
    /deleteflyer <name>  (admins only)
    """
    if not await _is_chat_admin(client, message):
        await message.reply_text("Only Sanctuary admins can delete flyers.")
        return

    raw = (message.text or "").strip()
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            "Usage:\n"
            "<code>/deleteflyer &lt;name&gt;</code>"
        )
        return

    name = parts[1].strip()
    norm = _normalize_name(name)
    res = flyers_coll.delete_one({"name": norm})
    if res.deleted_count == 0:
        await message.reply_text(f"❌ No flyer named <b>{name}</b> was found.")
    else:
        await message.reply_text(f"🗑 Flyer <b>{name}</b> has been deleted.")


# ────────────── Register ──────────────


def register(app: Client):
    log.info("✅ handlers.flyer registered (Mongo-backed flyers)")

    app.add_handler(MessageHandler(addflyer_cmd, filters.command("addflyer")), group=0)
    app.add_handler(MessageHandler(flyer_cmd, filters.command("flyer")), group=0)
    app.add_handler(MessageHandler(flyerlist_cmd, filters.command("flyerlist")), group=0)
    app.add_handler(MessageHandler(deleteflyer_cmd, filters.command("deleteflyer")), group=0)
