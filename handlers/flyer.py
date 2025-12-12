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


def _log_debug(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[FLYER][{ts}] {msg}", flush=True)


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

    return False


# ────────────── Command implementations ──────────────

async def _cmd_addflyer(client: Client, message: Message):
    """
    /addflyer <name> <caption>
    Used either:
      • as caption on a photo
      • or as a text command replying to a photo
    """
    if not await _is_chat_admin(client, message):
        await message.reply_text("Only Sanctuary admins can create or update flyers.")
        return

    # Which photo?
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

    existing = flyers_coll.find_one({"name": norm})
    if existing:
        doc.setdefault("created_at", existing.get("created_at") or _now_utc())
        doc.setdefault("created_by", existing.get("created_by") or message.from_user.id)
    else:
        doc["created_at"] = _now_utc()
        if message.from_user:
            doc["created_by"] = message.from_user.id

    flyers_coll.update_one({"name": norm}, {"$set": doc}, upsert=True)
    _log_debug(f"Saved flyer name={norm} file_id={file_id}")

    await message.reply_text(
        f"✅ Flyer <b>{name}</b> saved.\n"
        "You can send it with <code>/flyer "
        f"{name}</code> or see all flyers with <code>/flyerlist</code>."
    )


async def _cmd_flyer(client: Client, message: Message):
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
    _log_debug(f"/flyer requested name={norm} found={bool(doc)}")

    if not doc:
        await message.reply_text(
            f"❌ I couldn't find a flyer named <b>{name}</b>.\n"
            "Use <code>/flyerlist</code> to see what's saved."
        )
        return

    await message.reply_photo(
        doc["file_id"],
        caption=doc.get("caption") or "",
    )


async def _cmd_flyerlist(client: Client, message: Message):
    """
    /flyerlist → show all saved flyers
    """
    docs: List[dict] = list(flyers_coll.find().sort("name", ASCENDING))
    _log_debug(f"/flyerlist requested, count={len(docs)}")

    if not docs:
        await message.reply_text("No flyers saved yet.")
        return

    lines = ["📌 <b>Saved flyers:</b>"]
    for d in docs:
        name = d["name"]
        caption = (d.get("caption") or "").strip().replace("\n", " ")
        if len(caption) > 60:
            caption = caption[:57] + "…"
        if caption:
            lines.append(f"• <code>{name}</code> — {caption}")
        else:
            lines.append(f"• <code>{name}</code>")

    await message.reply_text("\n".join(lines))


async def _cmd_deleteflyer(client: Client, message: Message):
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


async def _cmd_flyerdebug(client: Client, message: Message):
    """
    /flyerdebug  (OWNER only) → quick sanity check
    """
    if not message.from_user or message.from_user.id != OWNER_ID:
        return

    docs = list(flyers_coll.find().sort("name", ASCENDING))
    count = len(docs)
    preview = ", ".join(d["name"] for d in docs[:10])
    await message.reply_text(
        f"Flyers in DB: <b>{count}</b>\n"
        f"First names: <code>{preview or 'none'}</code>"
    )


# ────────────── Router + register ──────────────

async def flyer_router(client: Client, message: Message):
    """
    Single router for: /addflyer, /flyer, /flyerlist, /deleteflyer, /flyerdebug
    """
    try:
        # message.command exists because we use filters.command in the handler
        cmd = ""
        if getattr(message, "command", None):
            cmd = (message.command[0] or "").lower()

        _log_debug(f"flyer_router got cmd={cmd!r} text={message.text!r}")

        if cmd == "addflyer":
            await _cmd_addflyer(client, message)
        elif cmd == "flyer":
            await _cmd_flyer(client, message)
        elif cmd == "flyerlist":
            await _cmd_flyerlist(client, message)
        elif cmd == "deleteflyer":
            await _cmd_deleteflyer(client, message)
        elif cmd == "flyerdebug":
            await _cmd_flyerdebug(client, message)
        else:
            _log_debug(f"flyer_router: unknown cmd={cmd!r}")
    except Exception as e:
        log.exception("flyer_router crashed: %s", e)
        try:
            await message.reply_text("❌ Flyer command hit an internal error.")
        except Exception:
            pass


def register(app: Client):
    log.info("✅ handlers.flyer registered (router-based flyers)")

    app.add_handler(
        MessageHandler(
            flyer_router,
            filters.command(
                ["addflyer", "flyer", "flyerlist", "deleteflyer", "flyerdebug"],
                prefixes=["/", "!"],
            ),
        ),
        group=0,
    )
