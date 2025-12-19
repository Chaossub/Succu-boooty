# handlers/kick_requirements.py

import os
import io
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from pymongo import MongoClient, ASCENDING

log = logging.getLogger(__name__)

# ────────────── ENV / DB ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for kick_requirements")

mongo = MongoClient(MONGO_URI)
db = mongo["Succubot"]
members_coll = db["requirements_members"]
members_coll.create_index([("user_id", ASCENDING)], unique=True)

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

def _parse_id_list(val: Optional[str]) -> Set[int]:
    if not val:
        return set()
    out: Set[int] = set()
    for part in val.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            pass
    return out

SUPER_ADMINS: Set[int] = _parse_id_list(os.getenv("SUPER_ADMINS"))
MODELS: Set[int] = _parse_id_list(os.getenv("MODELS"))

REQUIRED_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20"))

LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL"):
    if os.getenv(key):
        try:
            LOG_GROUP_ID = int(os.getenv(key))
            break
        except ValueError:
            pass


# ────────────── HELPERS ──────────────

def _is_adminish(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in SUPER_ADMINS or user_id in MODELS

async def _log_to_group(client: Client, text: str):
    if not LOG_GROUP_ID:
        return
    try:
        await client.send_message(LOG_GROUP_ID, text, disable_web_page_preview=True)
    except Exception as e:
        log.warning("kick_requirements: failed logging to group: %s", e)

def _label(d: Dict[str, Any]) -> str:
    uid = d.get("user_id")
    name = (d.get("first_name") or "").strip() or "Unknown"
    uname = d.get("username")
    if uname:
        return f"{name} (@{uname}) — <code>{uid}</code>"
    return f"{name} — <code>{uid}</code>"


async def _admin_ids_for_chat(client: Client, chat_id: int) -> Set[int]:
    admin_ids: Set[int] = set()
    try:
        # This is efficient: only returns admins
        async for m in client.get_chat_members(chat_id, filter="administrators"):
            if m.user:
                admin_ids.add(m.user.id)
    except Exception:
        # If Telegram blocks the admin list, we just fall back to try/except on kick
        pass
    return admin_ids


def _candidates_for_kick(chat_id: int) -> List[Dict[str, Any]]:
    """
    Uses scan-tracked membership via `groups: chat_id`.
    If you haven't run Scan Group Members, this will be empty.
    """
    return list(
        members_coll.find(
            {
                "groups": chat_id,
                "is_exempt": {"$ne": True},
                "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
            }
        ).sort("first_name", ASCENDING)
    )


def _too_long(text: str) -> bool:
    return len(text) > 3500


async def _send_long_or_file(client: Client, chat_id: int, title: str, body_html: str):
    """
    Sends as a message if small enough, else as a .txt document.
    """
    if not _too_long(body_html):
        await client.send_message(chat_id, body_html, disable_web_page_preview=True)
        return

    plain = (
        body_html.replace("<b>", "")
        .replace("</b>", "")
        .replace("<code>", "")
        .replace("</code>", "")
        .replace("<i>", "")
        .replace("</i>", "")
    )
    buf = io.BytesIO(plain.encode("utf-8"))
    buf.name = "kick_sweep_results.txt"
    await client.send_document(chat_id, document=buf, caption=title)


# ────────────── STATE ──────────────
# Store pending confirmation per admin clicker
PENDING: Dict[int, Dict[str, Any]] = {}


# ────────────── COMMANDS ──────────────

def register(app: Client):

    @app.on_message(filters.command(["kicksweep", "kickbehind", "kickrequirements"]) & filters.group)
    async def cmd_kicksweep(client: Client, msg: Message):
        user_id = msg.from_user.id if msg.from_user else 0
        if not _is_adminish(user_id):
            await msg.reply_text("Admins/models only 💜")
            return

        chat_id = msg.chat.id
        docs = _candidates_for_kick(chat_id)

        if not docs:
            await msg.reply_text(
                "✅ No kick candidates found.\n\n"
                "If you expected people here, run 📡 <b>Scan Group Members</b> first so the bot knows who's in this group.",
                disable_web_page_preview=True,
            )
            return

        # Store snapshot of the user IDs we intend to kick
        PENDING[user_id] = {
            "chat_id": chat_id,
            "uids": [d.get("user_id") for d in docs if d.get("user_id")],
            "created": datetime.now(timezone.utc),
        }

        preview_lines = [f"🚪 <b>Kick Sweep Preview</b>", f"Group: <code>{chat_id}</code>", ""]
        preview_lines.append(f"⚠️ Candidates (behind & not exempt): <b>{len(docs)}</b>")
        preview_lines.append("")
        preview_lines.extend([f"• {_label(d)}" for d in docs[:30]])
        if len(docs) > 30:
            preview_lines.append(f"\n…plus <b>{len(docs) - 30}</b> more.")

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🧪 Dry Run (show full list)", callback_data="kreq:dry"),
                ],
                [
                    InlineKeyboardButton("❌ Cancel", callback_data="kreq:cancel"),
                    InlineKeyboardButton("🚪 Kick Them", callback_data="kreq:go"),
                ],
            ]
        )

        await msg.reply_text("\n".join(preview_lines), reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^kreq:(dry|cancel|go)$"))
    async def cb_kreq(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else 0
        action = (cq.data or "").split(":")[-1]

        if not _is_adminish(user_id):
            await cq.answer("Admins/models only 💜", show_alert=True)
            return

        pending = PENDING.get(user_id)
        if not pending:
            await cq.answer("Nothing pending. Run /kicksweep again.", show_alert=True)
            return

        chat_id = pending["chat_id"]
        uids: List[int] = [int(x) for x in pending.get("uids", []) if x]

        if action == "cancel":
            PENDING.pop(user_id, None)
            await cq.message.edit_text("❌ Kick sweep canceled.", disable_web_page_preview=True)
            await cq.answer()
            return

        if action == "dry":
            # Full list (DM to admin, plus log group)
            docs = _candidates_for_kick(chat_id)
            title = f"🧪 Dry Run — Kick candidates ({len(docs)})"
            body = "\n".join([f"• {_label(d)}" for d in docs]) or "None."
            html = f"<b>{title}</b>\nGroup: <code>{chat_id}</code>\n\n{body}"
            await _send_long_or_file(client, cq.from_user.id, title, html)
            await cq.answer("Sent you the full list ✅", show_alert=True)
            return

        # action == "go"
        await cq.answer("Running kick sweep…", show_alert=False)

        admin_ids = await _admin_ids_for_chat(client, chat_id)

        kicked: List[str] = []
        failed: List[str] = []
        skipped = 0

        # We re-check live docs so we respect newly updated spend/exempt flags
        docs = _candidates_for_kick(chat_id)
        doc_by_uid = {int(d.get("user_id")): d for d in docs if d.get("user_id")}

        for uid in uids:
            if uid == OWNER_ID or uid in MODELS or uid in SUPER_ADMINS:
                skipped += 1
                continue
            if uid in admin_ids:
                skipped += 1
                continue

            d = doc_by_uid.get(uid, {"user_id": uid, "first_name": "", "username": None})
            label = _label(d)

            try:
                # Kick = ban + unban
                await client.ban_chat_member(chat_id, uid)
                await client.unban_chat_member(chat_id, uid)
                kicked.append(label)
            except Exception as e:
                failed.append(f"{label} <i>({e.__class__.__name__})</i>")

        PENDING.pop(user_id, None)

        # Log results
        summary = (
            f"🚪 <b>Manual Kick Sweep</b>\n"
            f"By: <code>{user_id}</code>\n"
            f"Group: <code>{chat_id}</code>\n\n"
            f"✅ Kicked: <b>{len(kicked)}</b>\n"
            f"❌ Failed: <b>{len(failed)}</b>\n"
            f"⏭ Skipped (owner/models/admins): <b>{skipped}</b>\n"
            f"💵 Requirement minimum: ${REQUIRED_MIN_SPEND:.2f}"
        )
        await _log_to_group(client, summary)

        if kicked:
            await _send_long_or_file(
                client,
                LOG_GROUP_ID or chat_id,
                "✅ Kicked users",
                "<b>✅ Kicked</b>\n\n" + "\n".join([f"• {x}" for x in kicked]),
            )
        if failed:
            await _send_long_or_file(
                client,
                LOG_GROUP_ID or chat_id,
                "❌ Kick failures",
                "<b>❌ Failed</b>\n\n" + "\n".join([f"• {x}" for x in failed]),
            )

        # Update the message where you clicked the button
        await cq.message.edit_text(summary, disable_web_page_preview=True)
