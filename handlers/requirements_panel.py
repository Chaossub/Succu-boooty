# handlers/requirements_panel.py
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import builtins

try:
    from pymongo import MongoClient
except Exception:  # pragma: no cover - pymongo always present in prod
    MongoClient = None  # type: ignore

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))

# SUPER_ADMINS (already used elsewhere in your bot)
def _parse_id_list(raw: str) -> List[int]:
    ids: List[int] = []
    if not raw:
        return ids
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            log.warning("requirements_panel: invalid ID %r in env list", part)
    return ids


SUPER_ADMINS: List[int] = _parse_id_list(os.getenv("SUPER_ADMINS", ""))

# NEW: models who should have access to requirements admin tools,
# without being global SUPER_ADMINS.
REQ_MODEL_IDS: List[int] = _parse_id_list(os.getenv("REQUIREMENTS_MODEL_IDS", ""))

REQ_ADMIN_IDS = {OWNER_ID, *SUPER_ADMINS, *REQ_MODEL_IDS}

# group(s) we scan from DMs
SANCTUARY_GROUP_IDS: List[int] = _parse_id_list(os.getenv("SANCTUARY_GROUP_IDS", ""))

# monthly requirement dollars (base; Stripe + manual credits)
MONTHLY_REQUIREMENT = float(os.getenv("REQUIREMENT_DOLLARS", "20.0"))

# MongoDB setup (reuse global client if present)
MONGO_URI = (
    os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URI")
    or os.getenv("DATABASE_URL")
    or ""
)

mongo_client = getattr(builtins, "mongo_client", None)
if mongo_client is None and MongoClient and MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        builtins.mongo_client = mongo_client  # type: ignore[attr-defined]
        log.info("requirements_panel: created local MongoClient")
    except Exception as e:  # pragma: no cover
        log.warning("requirements_panel: failed to init MongoClient: %s", e)
        mongo_client = None

if not mongo_client:
    log.warning("requirements_panel: Mongo not available, requirements won't persist!")

db = mongo_client["Succubot"] if mongo_client else None
coll = db["requirements_members"] if db else None

# Optional Stripe / payments integration (future)
try:
    from handlers import payments  # type: ignore
except Exception:
    payments = None
    log.warning(
        "requirements_panel: payments.get_monthly_progress not available, using dummy 0/0"
    )

# ────────────── HELPER FUNCTIONS ──────────────


def _is_req_admin(user_id: int) -> bool:
    return user_id in REQ_ADMIN_IDS


def _month_key_now() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def _doc_id(month_key: str, user_id: int) -> str:
    return f"{month_key}:{user_id}"


def _ensure_coll():
    if coll is None:
        raise RuntimeError("Mongo collection not available")


def _upsert_member(
    month_key: str, user_id: int, username: str | None, first_name: str | None
) -> Dict[str, Any]:
    """
    Ensure a monthly row exists for this user; return doc.
    """
    _ensure_coll()
    _id = _doc_id(month_key, user_id)

    username_norm = (username or "").lstrip("@")
    first_name = first_name or ""

    doc = coll.find_one({"_id": _id})  # type: ignore[operator]
    if not doc:
        doc = {
            "_id": _id,
            "month": month_key,
            "user_id": user_id,
            "username": username_norm,
            "first_name": first_name,
            "manual_spend": 0.0,  # dollars
            "is_exempt": False,
            "last_updated": datetime.now(timezone.utc),
        }
        coll.insert_one(doc)  # type: ignore[union-attr]
    else:
        # keep existing amounts / exempt flag, update basic info
        updated = False
        if username_norm and doc.get("username") != username_norm:
            doc["username"] = username_norm
            updated = True
        if first_name and doc.get("first_name") != first_name:
            doc["first_name"] = first_name
            updated = True
        if updated:
            doc["last_updated"] = datetime.now(timezone.utc)
            coll.replace_one({"_id": _id}, doc)  # type: ignore[union-attr]
    return doc


def _get_doc(month_key: str, user_id: int) -> Dict[str, Any] | None:
    if coll is None:
        return None
    return coll.find_one({"_id": _doc_id(month_key, user_id)})  # type: ignore[operator]


def _set_manual_spend(month_key: str, user_id: int, amount: float, note: str) -> Dict[str, Any]:
    _ensure_coll()
    _id = _doc_id(month_key, user_id)
    doc = coll.find_one({"_id": _id})  # type: ignore[operator]
    if not doc:
        doc = {
            "_id": _id,
            "month": month_key,
            "user_id": user_id,
            "username": "",
            "first_name": "",
            "manual_spend": 0.0,
            "is_exempt": False,
        }

    doc["manual_spend"] = float(doc.get("manual_spend", 0.0)) + float(amount)
    doc["last_note"] = note
    doc["last_updated"] = datetime.now(timezone.utc)

    coll.replace_one({"_id": _id}, doc, upsert=True)  # type: ignore[union-attr]
    return doc


def _set_exempt(month_key: str, user_id: int, is_exempt: bool) -> Dict[str, Any]:
    _ensure_coll()
    _id = _doc_id(month_key, user_id)
    doc = coll.find_one({"_id": _id})  # type: ignore[operator]
    if not doc:
        doc = {
            "_id": _id,
            "month": month_key,
            "user_id": user_id,
            "username": "",
            "first_name": "",
            "manual_spend": 0.0,
            "is_exempt": is_exempt,
        }
    else:
        doc["is_exempt"] = is_exempt
    doc["last_updated"] = datetime.now(timezone.utc)
    coll.replace_one({"_id": _id}, doc, upsert=True)  # type: ignore[union-attr]
    return doc


def _get_stripe_progress(user_id: int) -> Tuple[float, int]:
    """
    Returns (dollars, games) from Stripe/system, if available.
    """
    if not payments or not hasattr(payments, "get_monthly_progress"):
        return 0.0, 0
    try:
        val = payments.get_monthly_progress(user_id)  # type: ignore[attr-defined]
        if not isinstance(val, dict):
            return 0.0, 0
        dollars = float(val.get("dollars", 0.0))
        games = int(val.get("games", 0))
        return dollars, games
    except Exception:
        log.exception("requirements_panel: error in get_monthly_progress for %s", user_id)
        return 0.0, 0


def _format_status(doc: Dict[str, Any] | None, user_id: int) -> str:
    month_key = _month_key_now()
    stripe_dollars, stripe_games = _get_stripe_progress(user_id)

    manual = 0.0
    is_exempt = False
    if doc:
        manual = float(doc.get("manual_spend", 0.0))
        is_exempt = bool(doc.get("is_exempt", False))

    total = manual + stripe_dollars
    pct = min(100, int((total / MONTHLY_REQUIREMENT) * 100)) if MONTHLY_REQUIREMENT else 0

    lines = [
        f"📅 <b>Requirements Status — {month_key}</b>",
        "",
        f"<b>Total credited this month:</b> ${total:,.2f}",
        f"• Stripe / games: ${stripe_dollars:,.2f} (games: {stripe_games})",
        f"• Manual credits: ${manual:,.2f}",
        f"• Requirement: ${MONTHLY_REQUIREMENT:,.2f} (progress: {pct}%)",
    ]

    if is_exempt:
        lines.append("")
        lines.append("✨ You’re currently <b>EXEMPT</b> from requirements this month.")

    return "\n".join(lines)


# Reminder / warning message pools
REMINDER_LINES = [
    "Hey love, just a quick reminder that you’re a little behind on this month’s Sanctuary requirements. Come play with us so you don’t lose access to all the fun. 💋",
    "Psst… the Sanctuary requirements meter is looking a bit thirsty for you. A game or a little spoil session would make it very happy. 😈",
    "Your spot in the Sanctuary is important to us, but you’re currently short on meeting this month’s requirements. Hop into a game or spoil your favorite succubus so you stay in good standing. 💜",
    "This is your friendly Sanctuary nudge — our logs show you haven’t quite met this month’s requirements yet. There’s still time to jump into a game or spoil the girls and stay cozy with us. 🔥",
]

FINAL_WARN_LINES = [
    "Heads up: you’re still under this month’s Sanctuary requirements. If things don’t update soon you may lose access and have to pay the door fee again to re-enter. If you think this is wrong, please reach out to an admin so we can double-check your logs. 💬",
    "This is a final reminder that our logs show you haven’t met this month’s Sanctuary requirements. Your access may be removed at the start of the month if nothing changes. If you’ve played or tipped and think this is a mistake, message an admin and we’ll review it together. 📋",
    "Our system still has you listed as behind on this month’s Sanctuary requirements. To avoid being removed, please jump into a game or spoil the girls soon. If you believe you already have, contact an admin so we can verify everything. 💜",
]

# ────────────── INLINE KEYBOARDS ──────────────


def _requirements_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []

    rows.append(
        [
            InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:my_status"),
            InlineKeyboardButton("🔍 Look Up Member", callback_data="reqpanel:lookup"),
        ]
    )

    if is_admin:
        rows.append(
            [
                InlineKeyboardButton("➕ Add Manual Spend", callback_data="reqpanel:add_manual"),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton("✅ Exempt / Un-exempt", callback_data="reqpanel:exempt"),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton("📋 Member Status List", callback_data="reqpanel:list"),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    "📡 Scan Group Members", callback_data="reqpanel:scan_group"
                ),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    "📨 Send Reminders (Behind Only)",
                    callback_data="reqpanel:send_reminders",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    "⚠️ Send Final Warnings",
                    callback_data="reqpanel:send_final",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "⬅️ Back to Sanctuary Menu", callback_data="portal:home"
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


# ────────────── REGISTER ──────────────


def register(app: Client) -> None:
    log.info(
        "✅ handlers.requirements_panel registered (OWNER_ID=%s, req_admins=%s, groups=%s)",
        OWNER_ID,
        sorted(REQ_ADMIN_IDS),
        SANCTUARY_GROUP_IDS,
    )

    # -------- Entry from main menu --------
    @app.on_callback_query(filters.regex(r"^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return

        is_admin = _is_req_admin(user.id)

        if is_admin:
            header = "📋 <b>Requirements Panel – Owner / Models</b>\n\n"
            body = (
                "Use these tools to manage Sanctuary requirements for the month.\n"
                "Everything you do here updates what SuccuBot uses when checking member status "
                "or running sweeps, so double-check before you confirm changes.\n\n"
                "From here you can:\n"
                "• View the full member status list\n"
                "• Add manual spend credit for offline payments\n"
                "• Exempt / un-exempt members\n"
                "• Scan group members into the tracker\n"
                "• Send reminder DMs to members who are behind\n"
                "• Send final-warning DMs to those still short at the end of the month\n\n"
                "Only you and approved model admins see this panel. Members just see their own status."
            )
        else:
            header = "📋 <b>Requirements Panel</b>\n\n"
            body = (
                "Here you can check where you stand with this month’s Sanctuary requirements "
                "and see what our system currently has logged for you.\n\n"
                "If you think something looks off, please message an admin so we can review "
                "your games and payments together. 💜"
            )

        kb = _requirements_keyboard(is_admin=is_admin)

        try:
            await cq.message.edit_text(
                header + body,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Check my status --------
    @app.on_callback_query(filters.regex(r"^reqpanel:my_status$"))
    async def reqpanel_my_status_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return

        month_key = _month_key_now()
        doc = _get_doc(month_key, user.id)

        text = _format_status(doc, user.id)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back to Requirements Menu", callback_data="reqpanel:home")]]
        )

        try:
            await cq.message.edit_text(
                text, reply_markup=kb, disable_web_page_preview=True
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Look up member (by ID) --------
    @app.on_callback_query(filters.regex(r"^reqpanel:lookup$"))
    async def reqpanel_lookup_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return

        is_admin = _is_req_admin(user.id)
        if not is_admin:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Back", callback_data="reqpanel:home")]]
            )
            try:
                await cq.message.edit_text(
                    "To protect member privacy, only admins can look up other members’ status.\n\n"
                    "You can still tap <b>Check My Status</b> to see your own logs. 💜",
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
            await cq.answer()
            return

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="reqpanel:home")]]
        )
        try:
            await cq.message.edit_text(
                "🔍 <b>Look Up Member</b>\n\n"
                "Send me a message in this chat in the format:\n"
                "<code>USER_ID</code>\n\n"
                "Example:\n"
                "<code>123456789</code>\n\n"
                "I’ll reply with their current monthly status.",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Add manual spend prompt --------
    @app.on_callback_query(filters.regex(r"^reqpanel:add_manual$"))
    async def reqpanel_add_manual_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return
        if not _is_req_admin(user.id):
            await cq.answer("Only approved admins can do that.", show_alert=True)
            return

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="reqpanel:home")]]
        )
        try:
            await cq.message.edit_text(
                "➕ <b>Add Manual Spend</b>\n\n"
                "Send me a message in this format:\n"
                "<code>USER_ID  amount  [note]</code>\n\n"
                "Example:\n"
                "<code>123456789  15  from CashApp game night</code>\n\n"
                "This adds extra credited dollars on top of anything Stripe logs for this month only.",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Exempt / un-exempt prompt --------
    @app.on_callback_query(filters.regex(r"^reqpanel:exempt$"))
    async def reqpanel_exempt_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return
        if not _is_req_admin(user.id):
            await cq.answer("Only approved admins can do that.", show_alert=True)
            return

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="reqpanel:home")]]
        )
        try:
            await cq.message.edit_text(
                "✅ <b>Exempt / Un-exempt Member</b>\n\n"
                "Send me a message in this format:\n"
                "<code>USER_ID  on/off  [reason]</code>\n\n"
                "Examples:\n"
                "<code>123456789  on  long-term vip</code>\n"
                "<code>123456789  off  back to normal</code>",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Member status list (quick text dump) --------
    @app.on_callback_query(filters.regex(r"^reqpanel:list$"))
    async def reqpanel_list_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return
        if not _is_req_admin(user.id):
            await cq.answer("Only approved admins can do that.", show_alert=True)
            return

        month_key = _month_key_now()
        if coll is None:
            await cq.answer("Storage not available.", show_alert=True)
            return

        docs = list(coll.find({"month": month_key}))  # type: ignore[union-attr]
        if not docs:
            text = "No members have been logged for this month yet."
        else:
            lines = [f"📋 <b>Member Status List — {month_key}</b>\n"]
            for d in docs:
                uid = d.get("user_id")
                uname = d.get("username") or d.get("first_name") or str(uid)
                manual = float(d.get("manual_spend", 0.0))
                is_ex = bool(d.get("is_exempt", False))
                stripe_d, stripe_g = _get_stripe_progress(uid)
                total = manual + stripe_d
                pct = (
                    min(100, int((total / MONTHLY_REQUIREMENT) * 100))
                    if MONTHLY_REQUIREMENT
                    else 0
                )
                flag = " (EXEMPT)" if is_ex else ""
                lines.append(
                    f"• {uname} <code>{uid}</code> — ${total:,.2f} ({pct}%){flag}"
                )
            text = "\n".join(lines)

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="reqpanel:home")]]
        )
        try:
            await cq.message.edit_text(
                text, reply_markup=kb, disable_web_page_preview=True
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Scan group members (from DMs) --------
    @app.on_callback_query(filters.regex(r"^reqpanel:scan_group$"))
    async def reqpanel_scan_group_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return
        if not _is_req_admin(user.id):
            await cq.answer("Only approved admins can do that.", show_alert=True)
            return

        if not SANCTUARY_GROUP_IDS:
            await cq.answer(
                "No SANCTUARY_GROUP_IDS are configured in the bot’s env.",
                show_alert=True,
            )
            return

        month_key = _month_key_now()
        added = 0
        updated = 0
        errors: List[str] = []

        try:
            for gid in SANCTUARY_GROUP_IDS:
                try:
                    async for member in app.iter_chat_members(gid):
                        if member.user.is_bot:
                            continue
                        doc = _upsert_member(
                            month_key,
                            member.user.id,
                            member.user.username,
                            member.user.first_name,
                        )
                        # Rough heuristic: if doc just created, count as added
                        # (no good flag, so we just bump counters loosely)
                        if "last_updated" in doc:
                            updated += 1
                        else:
                            added += 1
                except Exception as e:
                    log.exception(
                        "requirements_panel: error scanning group %s: %s", gid, e
                    )
                    errors.append(str(gid))
        except Exception as e:
            log.exception("requirements_panel: scan failure: %s", e)
            await cq.answer("Scan failed. Check logs.", show_alert=True)
            return

        msg = (
            f"Scan complete for {len(SANCTUARY_GROUP_IDS)} group(s).\n"
            f"Members synced for month {month_key}.\n"
        )
        if coll is None:
            msg += "\n⚠️ Storage not available; results are not persisted."
        if errors:
            msg += (
                "\n\nSome groups could not be scanned:\n"
                + ", ".join(errors)
                + "\nCheck bot logs for details."
            )

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="reqpanel:home")]]
        )
        try:
            await cq.message.edit_text(
                msg, reply_markup=kb, disable_web_page_preview=True
            )
        except Exception:
            pass
        await cq.answer("Scan finished.", show_alert=True)

    # -------- Send reminders (behind only) --------
    @app.on_callback_query(filters.regex(r"^reqpanel:send_reminders$"))
    async def reqpanel_send_reminders_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return
        if not _is_req_admin(user.id):
            await cq.answer("Only approved admins can do that.", show_alert=True)
            return
        if coll is None:
            await cq.answer("Storage not available.", show_alert=True)
            return

        month_key = _month_key_now()
        docs = list(coll.find({"month": month_key}))  # type: ignore[union-attr]

        sent = 0
        for d in docs:
            uid = d.get("user_id")
            if not uid:
                continue
            if bool(d.get("is_exempt", False)):
                continue

            manual = float(d.get("manual_spend", 0.0))
            stripe_d, _ = _get_stripe_progress(uid)
            total = manual + stripe_d
            if total >= MONTHLY_REQUIREMENT:
                continue

            try:
                text = REMINDER_LINES[sent % len(REMINDER_LINES)]
                await _.send_message(uid, text, disable_web_page_preview=True)
                sent += 1
            except Exception as e:
                log.warning("requirements_panel: failed to send reminder to %s: %s", uid, e)

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="reqpanel:home")]]
        )
        msg = f"Sent reminder DMs to {sent} member(s) who are still behind."
        try:
            await cq.message.edit_text(
                msg, reply_markup=kb, disable_web_page_preview=True
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Send final warnings --------
    @app.on_callback_query(filters.regex(r"^reqpanel:send_final$"))
    async def reqpanel_send_final_cb(_, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return
        if not _is_req_admin(user.id):
            await cq.answer("Only approved admins can do that.", show_alert=True)
            return
        if coll is None:
            await cq.answer("Storage not available.", show_alert=True)
            return

        month_key = _month_key_now()
        docs = list(coll.find({"month": month_key}))  # type: ignore[union-attr]

        sent = 0
        for d in docs:
            uid = d.get("user_id")
            if not uid:
                continue
            if bool(d.get("is_exempt", False)):
                continue

            manual = float(d.get("manual_spend", 0.0))
            stripe_d, _ = _get_stripe_progress(uid)
            total = manual + stripe_d
            if total >= MONTHLY_REQUIREMENT:
                continue

            try:
                text = FINAL_WARN_LINES[sent % len(FINAL_WARN_LINES)]
                await _.send_message(uid, text, disable_web_page_preview=True)
                sent += 1
            except Exception as e:
                log.warning("requirements_panel: failed to send final warning to %s: %s", uid, e)

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Back", callback_data="reqpanel:home")]]
        )
        msg = f"Sent final-warning DMs to {sent} member(s) who are still behind."
        try:
            await cq.message.edit_text(
                msg, reply_markup=kb, disable_web_page_preview=True
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Text handlers for owner/admin commands in DM --------
    @app.on_message(filters.private & filters.text, group=-3)
    async def reqpanel_text_handler(_, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id
        if not _is_req_admin(uid):
            return  # ignore normal users for these admin text commands

        text = (m.text or "").strip()
        if not text:
            return

        # Detect which prompt was last shown based on simple prefix in replied-to message
        # This is intentionally lightweight: admins will usually be replying right after
        # tapping the relevant button.
        ctx = (m.reply_to_message.text if m.reply_to_message and m.reply_to_message.text else "").lower()

        month_key = _month_key_now()

        # --- Add manual spend ---
        if "add manual spend" in ctx:
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                await m.reply_text(
                    "Format: <code>USER_ID  amount  [note]</code>",
                    disable_web_page_preview=True,
                )
                return
            try:
                target_id = int(parts[0])
                amount = float(parts[1])
            except ValueError:
                await m.reply_text(
                    "User ID must be a number and amount must be a valid number.",
                    disable_web_page_preview=True,
                )
                return
            note = parts[2] if len(parts) > 2 else ""
            try:
                doc = _set_manual_spend(month_key, target_id, amount, note)
            except Exception as e:
                log.exception("requirements_panel: failed to set manual spend: %s", e)
                await m.reply_text(
                    "Something went wrong saving that credit. Check logs.",
                    disable_web_page_preview=True,
                )
                return

            status = _format_status(doc, target_id)
            await m.reply_text(
                f"Saved manual credit for <code>{target_id}</code> (${amount:,.2f}).\n\n{status}",
                disable_web_page_preview=True,
            )
            return

        # --- Exempt / un-exempt ---
        if "exempt / un-exempt" in ctx or "exempt / un-exempt" in ctx:
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                await m.reply_text(
                    "Format: <code>USER_ID  on/off  [reason]</code>",
                    disable_web_page_preview=True,
                )
                return
            try:
                target_id = int(parts[0])
            except ValueError:
                await m.reply_text(
                    "User ID must be a number.",
                    disable_web_page_preview=True,
                )
                return
            flag_raw = parts[1].lower()
            is_exempt = flag_raw in {"on", "true", "yes", "y", "1"}
            reason = parts[2] if len(parts) > 2 else ""
            try:
                doc = _set_exempt(month_key, target_id, is_exempt)
                if reason:
                    doc["last_note"] = reason
                    _ensure_coll()
                    coll.replace_one({"_id": _doc_id(month_key, target_id)}, doc, upsert=True)  # type: ignore[union-attr]
            except Exception as e:
                log.exception("requirements_panel: failed to set exempt: %s", e)
                await m.reply_text(
                    "Something went wrong updating that member. Check logs.",
                    disable_web_page_preview=True,
                )
                return

            flag_text = "EXEMPT" if is_exempt else "no longer exempt"
            await m.reply_text(
                f"Member <code>{target_id}</code> is now <b>{flag_text}</b> for {month_key}.",
                disable_web_page_preview=True,
            )
            return

        # --- Lookup member (generic text with just an ID) ---
        if "look up member" in ctx:
            try:
                target_id = int(text.split()[0])
            except ValueError:
                await m.reply_text(
                    "Send just the numeric <code>USER_ID</code>.",
                    disable_web_page_preview=True,
                )
                return

            doc = _get_doc(month_key, target_id)
            if not doc:
                await m.reply_text(
                    "No entry found for that user this month.\n"
                    "Try scanning the group or adding manual credit first.",
                    disable_web_page_preview=True,
                )
                return

            status = _format_status(doc, target_id)
            await m.reply_text(status, disable_web_page_preview=True)
            return

