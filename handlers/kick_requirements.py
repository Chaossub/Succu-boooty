# handlers/kick_requirements.py
import os
import io
import logging
from datetime import datetime, timezone
from typing import Optional, Set, List, Dict, Any

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient, ASCENDING

log = logging.getLogger(__name__)

# ────────────── ENV ──────────────
MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI missing")

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))
REQUIRED_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20"))


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

# Optional: if you want to allow running from DM and picking a group
def _parse_groups(val: Optional[str]) -> List[int]:
    if not val:
        return []
    out: List[int] = []
    for part in val.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out


SANCTUARY_GROUP_IDS: List[int] = _parse_groups(os.getenv("SANCTUARY_GROUP_IDS"))

LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL"):
    if os.getenv(key):
        try:
            LOG_GROUP_ID = int(os.getenv(key))
            break
        except ValueError:
            pass

# ────────────── DB ──────────────
mongo = MongoClient(MONGO_URI)
db = mongo["Succubot"]
members_coll = db["requirements_members"]
members_coll.create_index([("user_id", ASCENDING)], unique=True)

# ────────────── STATE ──────────────
# per clicker: {"gid": int, "at": datetime}
PENDING: Dict[int, Dict[str, Any]] = {}


# ────────────── HELPERS ──────────────
def _is_adminish(uid: int) -> bool:
    return uid == OWNER_ID or uid in SUPER_ADMINS or uid in MODELS


def _label(d: Dict[str, Any]) -> str:
    uid = d.get("user_id")
    name = (d.get("first_name") or "").strip() or "Unknown"
    uname = (d.get("username") or "").strip()
    if uname:
        return f"{name} (@{uname}) — <code>{uid}</code>"
    return f"{name} — <code>{uid}</code>"


async def _log(client: Client, text: str):
    if not LOG_GROUP_ID:
        return
    try:
        await client.send_message(LOG_GROUP_ID, text, disable_web_page_preview=True)
    except Exception as e:
        log.warning("kick_requirements: log failed: %s", e)


async def _send_long_or_file(client: Client, chat_id: int, title: str, body_html: str):
    # Telegram safe limit buffer
    if len(body_html) <= 3500:
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
    buf.name = "kick_sweep_list.txt"
    await client.send_document(chat_id, document=buf, caption=title)


async def _admin_ids_for_chat(client: Client, chat_id: int) -> Set[int]:
    ids: Set[int] = set()
    try:
        async for m in client.get_chat_members(chat_id, filter="administrators"):
            if m.user:
                ids.add(m.user.id)
    except Exception:
        # If blocked, we’ll rely on kick failures
        pass
    return ids


def _kick_candidates(gid: int) -> List[Dict[str, Any]]:
    """
    Uses scan-tracked membership: requirements_members.groups contains gid.
    If you haven't run Scan Group Members, this will be empty.
    """
    return list(
        members_coll.find(
            {
                "groups": gid,
                "is_exempt": {"$ne": True},
                "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
            }
        ).sort("first_name", ASCENDING)
    )


def _actions_kb(gid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧪 Preview Full List", callback_data=f"reqkick:preview:{gid}")],
            [
                InlineKeyboardButton("❌ Cancel", callback_data="reqkick:cancel"),
                InlineKeyboardButton("🚪 Kick Them", callback_data=f"reqkick:confirm:{gid}"),
            ],
            [InlineKeyboardButton("⬅ Back", callback_data="reqpanel:admin")],
        ]
    )


def _confirm_kb(gid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("❌ No, go back", callback_data=f"reqkick:open_gid:{gid}"),
                InlineKeyboardButton("✅ Yes, kick", callback_data=f"reqkick:run:{gid}"),
            ],
            [InlineKeyboardButton("⬅ Back", callback_data="reqpanel:admin")],
        ]
    )


def _group_picker_kb() -> InlineKeyboardMarkup:
    rows = []
    for gid in SANCTUARY_GROUP_IDS[:30]:
        rows.append([InlineKeyboardButton(f"📍 Group {gid}", callback_data=f"reqkick:open_gid:{gid}")])
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="reqpanel:admin")])
    return InlineKeyboardMarkup(rows)


# ────────────── REGISTER ──────────────
def register(app: Client):
    log.info("✅ handlers.kick_requirements registered (button-only)")

    # Entry button from requirements_panel: callback_data="reqkick:open"
    @app.on_callback_query(filters.regex(r"^reqkick:open$"))
    async def reqkick_open(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else 0
        if not _is_adminish(uid):
            await cq.answer("Admins/models only 💜", show_alert=True)
            return

        # If clicked inside a group, use that group
        if cq.message and cq.message.chat and cq.message.chat.id < 0:
            gid = cq.message.chat.id
            await cq.answer()
            await cq.message.edit_text(
                "🚪 <b>Kick Behind Requirements</b>\n\n"
                f"Group: <code>{gid}</code>\n"
                "Choose what you want to do:",
                reply_markup=_actions_kb(gid),
                disable_web_page_preview=True,
            )
            return

        # Otherwise, allow picking a group from DM if SANCTUARY_GROUP_IDS exists
        if not SANCTUARY_GROUP_IDS:
            await cq.answer("Click this inside the group (or set SANCTUARY_GROUP_IDS).", show_alert=True)
            return

        await cq.answer()
        await cq.message.edit_text(
            "🚪 <b>Kick Behind Requirements</b>\n\nPick which group to run the sweep in:",
            reply_markup=_group_picker_kb(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqkick:open_gid:(-?\d+)$"))
    async def reqkick_open_gid(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else 0
        if not _is_adminish(uid):
            await cq.answer("Admins/models only 💜", show_alert=True)
            return

        gid = int((cq.data or "").split(":")[-1])
        await cq.answer()
        await cq.message.edit_text(
            "🚪 <b>Kick Behind Requirements</b>\n\n"
            f"Group: <code>{gid}</code>\n"
            "Choose what you want to do:",
            reply_markup=_actions_kb(gid),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqkick:preview:(-?\d+)$"))
    async def reqkick_preview(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else 0
        if not _is_adminish(uid):
            await cq.answer("Admins/models only 💜", show_alert=True)
            return

        gid = int((cq.data or "").split(":")[-1])
        docs = _kick_candidates(gid)

        if not docs:
            await cq.answer("No candidates. Run Scan Group Members first.", show_alert=True)
            return

        body = (
            "<b>🧪 Kick Sweep Preview</b>\n"
            f"Group: <code>{gid}</code>\n"
            f"Requirement min: <b>${REQUIRED_MIN_SPEND:.2f}</b>\n"
            f"Candidates: <b>{len(docs)}</b>\n\n"
            + "\n".join([f"• {_label(d)}" for d in docs])
        )

        # Send preview to YOUR DM (cleanest). If it fails, fallback to log group
        try:
            await _send_long_or_file(client, uid, f"Kick preview ({len(docs)})", body)
            await cq.answer("Sent preview to your DM ✅", show_alert=True)
        except Exception:
            target = LOG_GROUP_ID or (cq.message.chat.id if cq.message else uid)
            await _send_long_or_file(client, target, f"Kick preview ({len(docs)})", body)
            await cq.answer("Sent preview to log group ✅", show_alert=True)

    @app.on_callback_query(filters.regex(r"^reqkick:confirm:(-?\d+)$"))
    async def reqkick_confirm(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else 0
        if not _is_adminish(uid):
            await cq.answer("Admins/models only 💜", show_alert=True)
            return

        gid = int((cq.data or "").split(":")[-1])
        docs = _kick_candidates(gid)

        if not docs:
            await cq.answer("No candidates. Run Scan Group Members first.", show_alert=True)
            return

        PENDING[uid] = {"gid": gid, "at": datetime.now(timezone.utc)}

        await cq.answer()
        await cq.message.edit_text(
            "⚠️ <b>Confirm Kick Sweep</b>\n\n"
            f"Group: <code>{gid}</code>\n"
            f"Will kick: <b>{len(docs)}</b> members\n\n"
            "This removes them from the group (ban+unban).",
            reply_markup=_confirm_kb(gid),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqkick:cancel$"))
    async def reqkick_cancel(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else 0
        PENDING.pop(uid, None)
        await cq.answer("Canceled.", show_alert=True)

    @app.on_callback_query(filters.regex(r"^reqkick:run:(-?\d+)$"))
    async def reqkick_run(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else 0
        if not _is_adminish(uid):
            await cq.answer("Admins/models only 💜", show_alert=True)
            return

        gid = int((cq.data or "").split(":")[-1])
        pending = PENDING.get(uid)
        if not pending or pending.get("gid") != gid:
            await cq.answer("No confirmed sweep pending. Hit Kick Them again.", show_alert=True)
            return

        await cq.answer("Running kick sweep…", show_alert=False)

        docs = _kick_candidates(gid)
        admin_ids = await _admin_ids_for_chat(client, gid)

        kicked: List[str] = []
        failed: List[str] = []
        skipped = 0

        for d in docs:
            target = int(d.get("user_id"))
            # Hard safety checks
            if target == OWNER_ID or target in MODELS or target in SUPER_ADMINS:
                skipped += 1
                continue
            if target in admin_ids:
                skipped += 1
                continue

            try:
                # Kick = ban then unban
                await client.ban_chat_member(gid, target)
                await client.unban_chat_member(gid, target)
                kicked.append(_label(d))
            except Exception as e:
                failed.append(f"{_label(d)} <i>({e.__class__.__name__})</i>")

        PENDING.pop(uid, None)

        summary = (
            "🚪 <b>Kick Sweep Complete</b>\n\n"
            f"Group: <code>{gid}</code>\n"
            f"✅ Kicked: <b>{len(kicked)}</b>\n"
            f"❌ Failed: <b>{len(failed)}</b>\n"
            f"⏭ Skipped (owner/models/admins): <b>{skipped}</b>\n"
            f"Min spend: <b>${REQUIRED_MIN_SPEND:.2f}</b>\n"
        )

        await _log(client, summary)

        # Send details to log group (or group if no log group)
        target_chat = LOG_GROUP_ID or gid

        if kicked:
            await _send_long_or_file(
                client,
                target_chat,
                f"Kicked ({len(kicked)})",
                "<b>✅ Kicked</b>\n\n" + "\n".join([f"• {x}" for x in kicked]),
            )
        if failed:
            await _send_long_or_file(
                client,
                target_chat,
                f"Kick failed ({len(failed)})",
                "<b>❌ Failed</b>\n\n" + "\n".join([f"• {x}" for x in failed]),
            )

        # Update the panel message so you see completion right away
        await cq.message.edit_text(summary, reply_markup=_actions_kb(gid), disable_web_page_preview=True)
