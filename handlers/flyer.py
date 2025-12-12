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

OWNER_ID = int(
    os.getenv("OWNER_ID")
    or os.getenv("BOT_OWNER_ID")
    or "6964994611"
)

# ────────────── Helpers ──────────────


async def _is_admin_or_owner(client: Client, m: Message) -> bool:
    """Only owner or chat admins can create flyers."""
    if not m.from_user:
        return False

    if m.from_user.id == OWNER_ID:
        return True

    if m.chat and m.chat.type in ("group", "supergroup"):
        try:
            member = await client.get_chat_member(m.chat.id, m.from_user.id)
            # Pyrogram uses "owner" in v2, but "creator" also appears sometimes.
            if member.status in ("owner", "creator", "administrator"):
                return True
        except Exception as e:
            log.warning("flyer: get_chat_member failed: %s", e)

    return False


def _get_command_args(m: Message) -> List[str]:
    """Return words of either text or caption (for commands on photos)."""
    raw = (m.text or m.caption or "").strip()
    if not raw:
        return []
    return raw.split()


def _normalize_name(name: str) -> str:
    return name.strip().lower()


# ────────────── Commands ──────────────


async def addflyer_cmd(client: Client, m: Message):
    """
    /addflyer <name> <caption>
    - Must be sent with a photo OR as a reply to a photo.
    - Only owner / admins can create.
    """
    if not await _is_admin_or_owner(client, m):
        await m.reply_text("Only group admins (or Roni 💋) can create flyers.")
        return

    args = _get_command_args(m)
    if len(args) < 2:
        await m.reply_text(
            "Usage:\n"
            "<code>/addflyer &lt;name&gt; &lt;caption&gt;</code>\n\n"
            "➡️ Reply to a photo with this command, or send the command as the photo caption."
        )
        return

    # args[0] = /addflyer, args[1] = name, rest = caption
    name = _normalize_name(args[1])
    caption = ""
    if len(args) >= 3:
        caption = " ".join(args[2:]).strip()

    # Find the photo: either on this message, or the replied-to one
    src_msg: Optional[Message] = None
    if m.photo:
        src_msg = m
    elif m.reply_to_message and m.reply_to_message.photo:
        src_msg = m.reply_to_message

    if not src_msg or not src_msg.photo:
        await m.reply_text(
            "I couldn't find a photo.\n\n"
            "Reply to a photo with:\n"
            "<code>/addflyer &lt;name&gt; &lt;caption&gt;</code>\n"
            "or send the command as the photo caption."
        )
        return

    # If you didn't pass a caption, default to the photo's caption
    if not caption and (src_msg.caption or "").strip():
        caption = (src_msg.caption or "").strip()

    photo_sizes = src_msg.photo
    file_id = photo_sizes[-1].file_id  # largest size

    doc = {
        "name": name,
        "file_id": file_id,
        "caption": caption,
        "chat_id": m.chat.id if m.chat else None,
        "created_by": m.from_user.id if m.from_user else None,
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = flyers_coll.update_one(
            {"name": name},
            {"$set": doc},
            upsert=True,
        )
    except Exception as e:
        log.error("flyer: failed to upsert flyer %s: %s", name, e)
        await m.reply_text("❌ I couldn't save that flyer due to a database error.")
        return

    if result.matched_count:
        msg = f"✅ Flyer <code>{name}</code> updated.\n"
    else:
        msg = f"✅ Flyer <code>{name}</code> saved.\n"

    msg += "You can send it with <code>/flyer {}</code> or see all flyers with <code>/flyerlist</code>.".format(
        name
    )
    await m.reply_text(msg)


async def flyer_cmd(client: Client, m: Message):
    """
    /flyer <name> → send a saved flyer in the current chat.
    Everyone can use this.
    """
    args = _get_command_args(m)
    if len(args) < 2:
        await m.reply_text(
            "Usage: <code>/flyer &lt;name&gt;</code>\n"
            "See all flyers with <code>/flyerlist</code>."
        )
        return

    name = _normalize_name(args[1])
    doc = flyers_coll.find_one({"name": name})

    if not doc:
        await m.reply_text(
            f"❌ I couldn't find a flyer named <code>{name}</code>.\n"
            "Use <code>/flyerlist</code> to see all saved flyers."
        )
        return

    file_id = doc.get("file_id")
    caption = doc.get("caption") or ""

    if not file_id:
        await m.reply_text("That flyer is missing its image. You may need to recreate it.")
        return

    try:
        await client.send_photo(
            chat_id=m.chat.id,
            photo=file_id,
            caption=caption,
        )
    except Exception as e:
        log.error("flyer: failed to send flyer %s: %s", name, e)
        await m.reply_text("❌ I couldn't send that flyer here.")


async def flyerlist_cmd(client: Client, m: Message):
    """
    /flyerlist or /listflyers → list all flyer names.
    Everyone can use this.
    """
    docs = list(flyers_coll.find().sort("name", ASCENDING))

    if not docs:
        await m.reply_text("There are no saved flyers yet.\nCreate one with <code>/addflyer</code>.")
        return

    lines = ["📋 <b>Saved flyers:</b>"]
    for d in docs:
        name = d.get("name") or "unnamed"
        creator_id = d.get("created_by")
        if creator_id:
            lines.append(f"• <code>{name}</code> (by <code>{creator_id}</code>)")
        else:
            lines.append(f"• <code>{name}</code>")

    await m.reply_text("\n".join(lines))


# ────────────── Register ──────────────


def register(app: Client):
    log.info("✅ handlers.flyer registered (router-based flyers)")

    # /addflyer – admin/owner only
    app.add_handler(
        MessageHandler(
            addflyer_cmd,
            filters.command("addflyer", prefixes=["/", "!"]),
        ),
        group=0,
    )

    # /flyer <name> – everyone
    app.add_handler(
        MessageHandler(
            flyer_cmd,
            filters.command("flyer", prefixes=["/", "!"]),
        ),
        group=0,
    )

    # /flyerlist + /listflyers – everyone
    app.add_handler(
        MessageHandler(
            flyerlist_cmd,
            filters.command(["flyerlist", "listflyers"], prefixes=["/", "!"]),
        ),
        group=0,
    )
