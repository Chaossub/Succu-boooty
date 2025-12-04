# handlers/requirements_panel.py
import logging
import os
import json
import random
from datetime import datetime
from typing import Dict, List, Any, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)

from utils.menu_store import store

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

# Who fully owns this panel
REQ_OWNER_ID = int(os.getenv("REQUIREMENTS_OWNER_ID", "6964994611"))

# Optional: comma-separated user IDs who are "model admins" for this panel
_raw_admins = os.getenv("REQUIREMENTS_MODEL_ADMINS", "").strip()
REQ_MODEL_ADMINS = {
    int(x) for x in _raw_admins.split(",") if x.strip().isdigit()
}

# Minimum spend requirement for the month (can be changed via env)
REQ_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20.0"))

# How many members per selection page
MEMBERS_PER_PAGE = 6


# ────────────── MESSAGE POOLS (RANDOMIZED) ──────────────

REMINDER_MESSAGES = [
    # Soft / medium cute but firm reminders for people who are behind
    "Hey love, SuccuBot here 💋 Just a little reminder that you haven’t met your monthly requirements yet. "
    "There’s still time — go peek at your status and get caught up before the end of the month. I’d hate to see you lose your spot. 💜",

    "Hi babe ✨ My logs say you’re not quite on track for requirements yet. "
    "If you need help or something is missing, message a model early so it can get fixed. "
    "You’ve still got time — don’t stress, just don’t forget. 💕",

    "Sweetheart, you’re a little behind on requirements this month. "
    "Nothing scary, just letting you know so it doesn’t sneak up on you. "
    "Reach out if anything needs adjusting — I’m cheering for you. 💗",

    "Hey cutie 💋 I wanted to nudge you gently — you haven’t met this month’s requirements yet. "
    "There’s still time to make it happen. Don’t wait until the last minute, okay? 💜",

    "⏰ Heads up babe — you’re not meeting Sanctuary requirements yet. "
    "End of the month comes fast, and I don’t want you getting kicked out over a technicality. "
    "If you’ve paid or played games already, tell a model ASAP so it gets logged. 💜",

    "Hi love, quick alert: you’re behind on requirements for this month. "
    "Anyone not caught up before the deadline gets removed and must pay the door fee again to return. "
    "If something’s missing, now’s the time to fix it. 💋",

    "Hey babe 😈 My system says you haven’t hit your requirements yet. "
    "Don’t wait — knock them out before the month ends so you stay safely in the Sanctuary. "
    "Need help? Ask a model early, not last-minute. 💜",

    "Just popping in with a reminder, sweetheart — you’re not on track yet. "
    "If you want to stay in the Sanctuary next month, you’ll need to meet your requirements before the end of the month. "
    "Don’t risk losing your spot. 💗",

    "🚨 Reality check, babe: you haven’t met requirements yet, and time’s moving. "
    "Anyone who doesn’t hit them gets kicked, no exceptions. "
    "If you think something is missing, tell a model NOW. Don’t lose your spot over procrastination. 😘",

    "Hi love, we’re getting closer to the deadline and you’re still behind on requirements. "
    "If you don’t finish them, you’ll be removed and will have to pay the door fee again. "
    "This message *is* your warning — don’t ignore it. 💜",

    "Babe. 😈 You’re slipping behind on requirements and the month is moving. "
    "I’m giving you the sweet version of a threat — catch up now before I have to kick you. You know the rules. 💋",

    "This is your Sanctuary reminder: you’re not meeting requirements yet. "
    "If you want to stay, get everything done ASAP. "
    "If something is missing, speak up immediately — no last-day rescues. 💗",
]

FINAL_WARNING_MESSAGES = [
    # Final-warning pool: firm, pretty, grown-woman “don’t play with me” energy
    "🚨 Final Requirements Warning\n\n"
    "Babe… you’re still behind, and the deadline is almost here. If you don’t finish your requirements before the end of the month, "
    "you’ll be removed from the Sanctuary and will have to pay the door fee again. No excuses. "
    "If something is missing, message a model now. You can still fix this — don’t drag your feet. 💋",

    "🚨 Last Call, love\n\n"
    "You haven’t met your requirements, and time’s nearly up. If you don’t complete them before month-end, you will be kicked "
    "and will need to pay the door fee again to come back. If anything isn’t showing, reach out immediately. "
    "Handle it before it becomes a problem. 💜",

    "🚨 Reality check\n\n"
    "You’re still not on track with requirements. End of the month means automatic removal if you’re not caught up, and re-entry isn’t free. "
    "If we missed something, tell a model right now so it’s fixed before the sweep. Don’t let this sneak up on you, babe. 💋",

    "🚨 Final Notice\n\n"
    "You’re behind on requirements, and we’re out of time for running in circles. If you don’t meet them before the month ends, you’ll be removed — "
    "and yes, the door fee applies to return. If there’s an issue, speak up *now*.",

    "🚨 Deadline Approaching\n\n"
    "Here’s the truth: you haven’t met your requirements, and the month is ending. If you’re not finished by the sweep, you’ll be removed and will need "
    "to pay the door fee again. If something is unlogged, message a model ASAP. Don’t wait until the last minute.",

    "🚨 Important Reminder\n\n"
    "You’re still behind on requirements. If you don’t complete them before the month ends, you’ll be removed and required to pay the door fee to return. "
    "This rule applies to everyone. If we’re missing anything on your log, get that corrected now.",

    "🚨 Time’s Almost Up\n\n"
    "You haven’t hit your requirements, and the sweep is coming. If you want to stay in the Sanctuary, get caught up now. "
    "Anyone not meeting requirements will be removed — no exceptions. If something needs fixing, contact a model immediately.",

    "🚨 Act Now\n\n"
    "You’re not meeting this month’s requirements, and there’s no time left to procrastinate. Get your requirements done or you’ll be removed and charged "
    "the door fee to return. If your log is missing something, message us right away.",

    "🚨 This Is Your Last Reminder\n\n"
    "You’re still behind on requirements and the end of the month is here. If you don’t finish them, you’ll be removed — door fee applies to rejoin. "
    "If something’s missing, you need to speak up *right now*. I’m not repeating myself again. 💋",

    "🚨 Last Warning, babe\n\n"
    "My logs still show you haven’t met your monthly requirements. If you don’t get them done before the sweep, you will be removed. "
    "Fix it now or message a model if something isn’t showing. This is your final alert.",

    "🚨 Handle This Now\n\n"
    "You’re not on track, and time is basically gone. Finish your requirements before the sweep or you’ll be kicked and required to pay the door fee to come back. "
    "If you’ve already done something that isn’t logged, get it fixed *immediately*. 💜",

    "🚨 Don’t Ignore This\n\n"
    "You still haven’t met requirements and the deadline is here. If you don’t catch up before the end of the month, you’ll be removed — "
    "no “I forgot,” no “I didn’t know.” If anything’s missing, tell a model right now so it gets updated.",
]


# ────────────── SMALL HELPERS ──────────────

def _is_owner(user_id: int | None) -> bool:
    return bool(user_id) and user_id == REQ_OWNER_ID


def _is_model_admin(user_id: int | None) -> bool:
    return bool(user_id) and user_id in REQ_MODEL_ADMINS


def _is_any_admin(user_id: int | None) -> bool:
    return _is_owner(user_id) or _is_model_admin(user_id)


def _ym_key() -> str:
    """Current year-month as a simple key, e.g. '2025-12'."""
    return datetime.utcnow().strftime("%Y-%m")


def _members_key(chat_id: int) -> str:
    return f"req:members:{chat_id}"


def _progress_key(chat_id: int, ym: str | None = None) -> str:
    if ym is None:
        ym = _ym_key()
    return f"req:progress:{chat_id}:{ym}"


def _load_json(key: str, default):
    raw = store.get_menu(key) or ""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        log.exception("Failed to load JSON for key=%s", key)
        return default


def _save_json(key: str, value) -> None:
    try:
        store.set_menu(key, json.dumps(value))
    except Exception:
        log.exception("Failed to save JSON for key=%s", key)


def _load_members(chat_id: int) -> List[Dict[str, Any]]:
    return _load_json(_members_key(chat_id), [])


def _save_members(chat_id: int, members: List[Dict[str, Any]]) -> None:
    # De-duplicate by user_id
    seen = set()
    cleaned = []
    for m in members:
        uid = int(m.get("id", 0))
        if uid and uid not in seen:
            seen.add(uid)
            cleaned.append(m)
    _save_json(_members_key(chat_id), cleaned)


def _load_progress(chat_id: int, ym: str | None = None) -> Dict[str, Dict[str, Any]]:
    return _load_json(_progress_key(chat_id, ym), {})


def _save_progress(chat_id: int, progress: Dict[str, Dict[str, Any]], ym: str | None = None) -> None:
    _save_json(_progress_key(chat_id, ym), progress)


def _get_display_name(user) -> str:
    if not user:
        return "Unknown"
    if user.username:
        return f"@{user.username}"
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    if user.first_name:
        return user.first_name
    if user.last_name:
        return user.last_name
    return "Unknown"


def _ensure_progress_record(
    chat_id: int, user_id: int, display_name: str | None = None
) -> Dict[str, Any]:
    ym = _ym_key()
    progress = _load_progress(chat_id, ym)
    key = str(user_id)
    rec = progress.get(key) or {
        "user_id": user_id,
        "display_name": display_name or "",
        "auto_spend": 0.0,
        "manual_spend": 0.0,
        "exempt": False,
        "exempt_reason": "",
        "last_update": datetime.utcnow().isoformat(),
    }
    if display_name:
        rec["display_name"] = display_name
    rec["last_update"] = datetime.utcnow().isoformat()
    progress[key] = rec
    _save_progress(chat_id, progress, ym)
    return rec


def _get_status_for(chat_id: int, user_id: int) -> Tuple[str, bool]:
    """
    Returns (text, is_behind)
    """
    ym = _ym_key()
    progress = _load_progress(chat_id, ym)
    rec = progress.get(str(user_id))
    total = 0.0
    exempt = False

    if rec:
        total = float(rec.get("auto_spend", 0.0)) + float(rec.get("manual_spend", 0.0))
        exempt = bool(rec.get("exempt", False))

    # if no record at all => treat as 0, not exempt
    if exempt:
        status_line = (
            f"Status: <b>Exempt</b> for {ym}\n"
            "You’re marked as exempt this month, so requirements don’t apply. 💜"
        )
        return (status_line, False)

    if total >= REQ_MIN_SPEND:
        status_line = (
            f"Status: <b>On Track / Met</b> for {ym}\n"
            f"Logged spend: <b>${total:.2f}</b> / required <b>${REQ_MIN_SPEND:.2f}</b>."
        )
        return (status_line, False)

    # behind
    status_line = (
        f"Status: <b>Not on track yet</b> for {ym}\n"
        f"Logged spend: <b>${total:.2f}</b> / required <b>${REQ_MIN_SPEND:.2f}</b>.\n\n"
        "You’ll need to finish your requirements before the end of the month to stay in the Sanctuary. 💋"
    )
    return (status_line, True)


# ────────────── INLINE KEYBOARDS ──────────────

def _requirements_home_keyboard(is_admin: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📊 Check My Status", callback_data="reqpanel:my_status")],
    ]
    if is_admin:
        rows.append(
            [InlineKeyboardButton("🛠 Admin Controls", callback_data="reqpanel:admin:home")]
        )
    rows.append(
        [InlineKeyboardButton("⬅ Back to Main Menu", callback_data="portal:home")]
    )
    return InlineKeyboardMarkup(rows)


def _admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("📋 Member Status List", callback_data="reqpanel:admin:member_status"),
            InlineKeyboardButton("➕ Add Manual Spend", callback_data="reqpanel:admin:add_spend"),
        ],
        [
            InlineKeyboardButton("🛡 Exempt / Un-Exempt", callback_data="reqpanel:admin:exempt"),
        ],
    ]
    # Scan group can be owner or model admins
    if _is_any_admin(user_id):
        rows.append(
            [InlineKeyboardButton("📡 Scan Group Members", callback_data="reqpanel:admin:scan")]
        )
    # Reminders & final warnings: OWNER ONLY
    if _is_owner(user_id):
        rows.append(
            [InlineKeyboardButton("📨 Send Reminders (Behind Only)", callback_data="reqpanel:admin:reminders")]
        )
        rows.append(
            [InlineKeyboardButton("🚨 Send Final Warnings", callback_data="reqpanel:admin:final")]
        )
    rows.append(
        [InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")]
    )
    return InlineKeyboardMarkup(rows)


def _members_page_keyboard(
    chat_id: int,
    members: List[Dict[str, Any]],
    action: str,
    page: int,
    per_page: int = MEMBERS_PER_PAGE,
) -> InlineKeyboardMarkup:
    start = page * per_page
    end = start + per_page
    slice_members = members[start:end]

    buttons: List[List[InlineKeyboardButton]] = []

    for m in slice_members:
        uid = int(m.get("id", 0))
        name = m.get("name") or f"ID {uid}"
        label = f"{name} ({uid})"
        cb = f"reqpanel:pick:{action}:{uid}:{page}"
        buttons.append([InlineKeyboardButton(label, callback_data=cb)])

    # Navigation
    nav_row: List[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅ Prev", callback_data=f"reqpanel:page:{action}:{page-1}"))
    if end < len(members):
        nav_row.append(InlineKeyboardButton("Next ➡", callback_data=f"reqpanel:page:{action}:{page+1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [InlineKeyboardButton("⬅ Back to Admin", callback_data="reqpanel:admin:home")]
    )
    return InlineKeyboardMarkup(buttons)


# ────────────── PENDING STATE (IN-MEMORY) ──────────────

# admin_id -> {"chat_id": int, "target_id": int}
_pending_add_spend: Dict[int, Dict[str, int]] = {}


# ────────────── REGISTER HANDLERS ──────────────

def register(app: Client) -> None:
    log.info(
        "✅ handlers.requirements_panel registered (OWNER_ID=%s, admins=%s)",
        REQ_OWNER_ID,
        REQ_MODEL_ADMINS or {REQ_OWNER_ID},
    )

    # ───────── Requirements home ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        is_admin = _is_any_admin(user_id)
        kb = _requirements_home_keyboard(is_admin)

        text = (
            "📌 <b>Sanctuary Requirements Help</b>\n\n"
            "This panel helps you keep track of your monthly requirements so you don’t lose your spot in the Sanctuary.\n\n"
            "Each month you’re expected to:\n"
            "• Be active in chat and games\n"
            "• Hit the minimum spend / game requirement listed in our rules\n\n"
            "Use <b>📊 Check My Status</b> to see whether you’re on track. "
            "If you’re not meeting requirements by the end of the month, you’ll be removed and will need to pay the door fee again to come back.\n\n"
            "If something looks wrong, please reach out to a model or admin <b>early</b> — not on the last day."
        )

        try:
            await cq.message.edit_text(
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # ───────── My Status ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:my_status$"))
    async def reqpanel_my_status_cb(_, cq: CallbackQuery):
        if not cq.from_user or not cq.message:
            await cq.answer()
            return

        chat = cq.message.chat
        if not chat:
            await cq.answer("This only works inside the Sanctuary group.", show_alert=True)
            return

        chat_id = chat.id
        user_id = cq.from_user.id

        # Ensure they’re at least in the progress table if previously touched
        status_text, is_behind = _get_status_for(chat_id, user_id)

        text = (
            "📊 <b>Your Sanctuary Requirements Status</b>\n\n"
            f"{status_text}\n\n"
            "If you believe your spend or games are logged incorrectly, please contact a model so it can be fixed."
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Requirements", callback_data="reqpanel:home")],
            ]
        )
        try:
            await cq.message.edit_text(
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # ───────── Admin home ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:admin:home$"))
    async def reqpanel_admin_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_any_admin(user_id):
            await cq.answer("Only Sanctuary admin/models can use this panel. 💜", show_alert=True)
            return

        kb = _admin_keyboard(user_id)

        text = (
            "🛠 <b>Requirements Panel – Owner / Models</b>\n\n"
            "Use these tools to manage Sanctuary requirements for the month. "
            "Everything you do here updates what SuccuBot uses when checking member status or running sweeps, "
            "so double-check before you confirm changes.\n\n"
            "From here you can:\n"
            "• 📋 View member status\n"
            "• ➕ Add manual spend credits\n"
            "• 🛡 Exempt / un-exempt members for this month\n"
            "• 📡 Scan the group to log members\n"
            "• 📨 Send reminder DMs to members who are behind\n"
            "• 🚨 Send final warnings to those still not caught up\n\n"
            "Only you and approved model admins see this panel. Members just see their own status."
        )

        try:
            await cq.message.edit_text(
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # ───────── Scan group members ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:admin:scan$"))
    async def reqpanel_admin_scan_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_any_admin(user_id):
            await cq.answer("You don’t have permission to run a scan.", show_alert=True)
            return

        if not cq.message or not cq.message.chat:
            await cq.answer()
            return

        chat = cq.message.chat
        chat_id = chat.id

        members = _load_members(chat_id)
        existing_ids = {int(m["id"]) for m in members if "id" in m}
        added = 0

        try:
            async for member in client.get_chat_members(chat_id):
                u = member.user
                if u.is_bot:
                    continue
                uid = u.id
                name = _get_display_name(u)
                if uid not in existing_ids:
                    members.append({"id": uid, "name": name})
                    existing_ids.add(uid)
                    added += 1
        except Exception as e:
            log.exception("Failed to scan members for chat_id=%s", chat_id)
            await cq.answer("Scan failed. Check logs.", show_alert=True)
            return

        _save_members(chat_id, members)

        text = (
            "📡 <b>Scan Complete</b>\n\n"
            f"Chat: <code>{chat.title or chat_id}</code>\n"
            f"New members logged: <b>{added}</b>\n"
            f"Total logged members: <b>{len(members)}</b>\n\n"
            "These members are now available to pick from the list when viewing status or logging manual spend."
        )

        kb = _admin_keyboard(user_id)
        try:
            await cq.message.edit_text(
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer("Scan finished ✅", show_alert=False)

    # ───────── Show member list for actions ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:admin:(member_status|add_spend|exempt)$"))
    async def reqpanel_admin_list_cb(_, cq: CallbackQuery):
        if not cq.from_user or not cq.message or not cq.message.chat:
            await cq.answer()
            return

        user_id = cq.from_user.id
        if not _is_any_admin(user_id):
            await cq.answer("You don’t have permission for that.", show_alert=True)
            return

        chat_id = cq.message.chat.id
        members = _load_members(chat_id)
        if not members:
            await cq.answer("No logged members yet. Run a scan first.", show_alert=True)
            return

        # map actions
        action_map = {
            "reqpanel:admin:member_status": "status",
            "reqpanel:admin:add_spend": "addspend",
            "reqpanel:admin:exempt": "exempt",
        }
        full = cq.data
        action = action_map.get(full, "status")
        page = 0

        kb = _members_page_keyboard(chat_id, members, action, page)

        title = {
            "status": "📋 Choose a member to view their status:",
            "addspend": "➕ Choose a member to add manual spend for:",
            "exempt": "🛡 Choose a member to toggle exempt / non-exempt:",
        }.get(action, "Choose a member:")

        try:
            await cq.message.edit_text(
                title,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # ───────── Page navigation for member picker ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:page:(status|addspend|exempt):(\d+)$"))
    async def reqpanel_page_cb(_, cq: CallbackQuery):
        if not cq.from_user or not cq.message or not cq.message.chat:
            await cq.answer()
            return

        user_id = cq.from_user.id
        if not _is_any_admin(user_id):
            await cq.answer()
            return

        _, _, action, page_str = cq.data.split(":")
        page = int(page_str)
        chat_id = cq.message.chat.id
        members = _load_members(chat_id)
        if not members:
            await cq.answer("No logged members.", show_alert=True)
            return

        kb = _members_page_keyboard(chat_id, members, action, page)

        title = {
            "status": "📋 Choose a member to view their status:",
            "addspend": "➕ Choose a member to add manual spend for:",
            "exempt": "🛡 Choose a member to toggle exempt / non-exempt:",
        }.get(action, "Choose a member:")

        try:
            await cq.message.edit_text(
                title,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # ───────── Member picked for status / spend / exempt ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:pick:(status|addspend|exempt):(\d+):(\d+)$"))
    async def reqpanel_pick_cb(_, cq: CallbackQuery):
        if not cq.from_user or not cq.message or not cq.message.chat:
            await cq.answer()
            return

        user_id = cq.from_user.id
        if not _is_any_admin(user_id):
            await cq.answer("You don’t have permission for that.", show_alert=True)
            return

        _, _, action, uid_str, page_str = cq.data.split(":")
        target_id = int(uid_str)
        chat_id = cq.message.chat.id

        members = _load_members(chat_id)
        name = f"ID {target_id}"
        for m in members:
            if int(m.get("id", 0)) == target_id:
                name = m.get("name") or name
                break

        # STATUS
        if action == "status":
            status_text, is_behind = _get_status_for(chat_id, target_id)
            text = (
                "📋 <b>Member Status</b>\n\n"
                f"Member: {name} (<code>{target_id}</code>)\n\n"
                f"{status_text}"
            )
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back to Admin", callback_data="reqpanel:admin:home")]]
            )
            try:
                await cq.message.edit_text(
                    text,
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
            await cq.answer()
            return

        # ADD SPEND
        if action == "addspend":
            _pending_add_spend[user_id] = {
                "chat_id": chat_id,
                "target_id": target_id,
            }
            text = (
                "➕ <b>Add Manual Spend</b>\n\n"
                f"Member: {name} (<code>{target_id}</code>)\n\n"
                "Send the amount to add in <b>one message</b> (numbers only, e.g. <code>20</code> or <code>20.50</code>). "
                "This will be added as manual credit for the current month."
            )
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancel", callback_data="reqpanel:addspend:cancel")]]
            )
            try:
                await cq.message.edit_text(
                    text,
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
            await cq.answer()
            return

        # EXEMPT TOGGLE
        if action == "exempt":
            ym = _ym_key()
            progress = _load_progress(chat_id, ym)
            rec = progress.get(str(target_id)) or _ensure_progress_record(chat_id, target_id, name)
            currently = bool(rec.get("exempt", False))
            new_val = not currently
            rec["exempt"] = new_val
            if new_val and not rec.get("exempt_reason"):
                rec["exempt_reason"] = "Manually exempted"
            progress[str(target_id)] = rec
            _save_progress(chat_id, progress, ym)

            state = "Exempt ✅" if new_val else "Not Exempt ❌"
            text = (
                "🛡 <b>Exempt Status Updated</b>\n\n"
                f"Member: {name} (<code>{target_id}</code>)\n"
                f"New status: <b>{state}</b>"
            )
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back to Admin", callback_data="reqpanel:admin:home")]]
            )
            try:
                await cq.message.edit_text(
                    text,
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
            await cq.answer("Exempt status updated.", show_alert=False)
            return

        await cq.answer()

    # ───────── Cancel add spend ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:addspend:cancel$"))
    async def reqpanel_addspend_cancel_cb(_, cq: CallbackQuery):
        if not cq.from_user:
            await cq.answer()
            return

        admin_id = cq.from_user.id
        _pending_add_spend.pop(admin_id, None)

        kb = _admin_keyboard(admin_id)
        try:
            await cq.message.edit_text(
                "Cancelled manual spend input. No changes were made. 💜",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # ───────── Capture manual spend amount ─────────
    @app.on_message(filters.text & filters.user(list(REQ_MODEL_ADMINS | {REQ_OWNER_ID})), group=-2)
    async def reqpanel_addspend_capture(_, m: Message):
        if not m.from_user:
            return
        admin_id = m.from_user.id
        pending = _pending_add_spend.get(admin_id)
        if not pending:
            return  # nothing pending, ignore

        # Only handle if text looks like a number
        try:
            amount = float(m.text.replace(",", "").strip())
        except Exception:
            await m.reply_text(
                "Please send only the number amount (for example <code>20</code> or <code>20.50</code>).",
                disable_web_page_preview=True,
            )
            return

        chat_id = pending["chat_id"]
        target_id = pending["target_id"]

        members = _load_members(chat_id)
        name = f"ID {target_id}"
        for member in members:
            if int(member.get("id", 0)) == target_id:
                name = member.get("name") or name
                break

        ym = _ym_key()
        progress = _load_progress(chat_id, ym)
        rec = progress.get(str(target_id)) or _ensure_progress_record(chat_id, target_id, name)
        rec["manual_spend"] = float(rec.get("manual_spend", 0.0)) + amount
        rec["last_update"] = datetime.utcnow().isoformat()
        progress[str(target_id)] = rec
        _save_progress(chat_id, progress, ym)

        _pending_add_spend.pop(admin_id, None)

        total = float(rec.get("manual_spend", 0.0)) + float(rec.get("auto_spend", 0.0))
        await m.reply_text(
            "✅ Manual spend added.\n\n"
            f"Member: {name} (<code>{target_id}</code>)\n"
            f"Added: <b>${amount:.2f}</b>\n"
            f"New total logged (this month): <b>${total:.2f}</b>",
            disable_web_page_preview=True,
        )

    # ───────── Send reminders (behind only) ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:admin:reminders$"))
    async def reqpanel_admin_reminders_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_owner(user_id):
            await cq.answer("Only the Sanctuary owner can send sweeps.", show_alert=True)
            return

        if not cq.message or not cq.message.chat:
            await cq.answer()
            return

        chat_id = cq.message.chat.id
        members = _load_members(chat_id)
        if not members:
            await cq.answer("No logged members to message. Run a scan first.", show_alert=True)
            return

        ym = _ym_key()
        progress = _load_progress(chat_id, ym)

        behind_ids: List[int] = []
        for m in members:
            uid = int(m.get("id", 0))
            if not uid:
                continue
            rec = progress.get(str(uid))
            total = 0.0
            exempt = False
            if rec:
                total = float(rec.get("auto_spend", 0.0)) + float(rec.get("manual_spend", 0.0))
                exempt = bool(rec.get("exempt", False))
            if exempt:
                continue
            if total < REQ_MIN_SPEND:
                behind_ids.append(uid)

        sent = 0
        failed = 0

        for uid in behind_ids:
            msg = random.choice(REMINDER_MESSAGES)
            try:
                await client.send_message(uid, msg, disable_web_page_preview=True)
                sent += 1
            except Exception:
                failed += 1

        text = (
            "📨 <b>Reminder Sweep Complete</b>\n\n"
            f"Month: <code>{ym}</code>\n"
            f"Members behind requirements: <b>{len(behind_ids)}</b>\n"
            f"DMs sent successfully: <b>{sent}</b>\n"
            f"DMs failed (no DM / blocked / never started bot): <b>{failed}</b>"
        )
        kb = _admin_keyboard(user_id)
        try:
            await cq.message.edit_text(
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer("Reminder sweep sent.", show_alert=False)

    # ───────── Send final warnings (behind only) ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:admin:final$"))
    async def reqpanel_admin_final_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not _is_owner(user_id):
            await cq.answer("Only the Sanctuary owner can send final warnings.", show_alert=True)
            return

        if not cq.message or not cq.message.chat:
            await cq.answer()
            return

        chat_id = cq.message.chat.id
        members = _load_members(chat_id)
        if not members:
            await cq.answer("No logged members to message. Run a scan first.", show_alert=True)
            return

        ym = _ym_key()
        progress = _load_progress(chat_id, ym)

        behind_ids: List[int] = []
        for m in members:
            uid = int(m.get("id", 0))
            if not uid:
                continue
            rec = progress.get(str(uid))
            total = 0.0
            exempt = False
            if rec:
                total = float(rec.get("auto_spend", 0.0)) + float(rec.get("manual_spend", 0.0))
                exempt = bool(rec.get("exempt", False))
            if exempt:
                continue
            if total < REQ_MIN_SPEND:
                behind_ids.append(uid)

        sent = 0
        failed = 0

        for uid in behind_ids:
            msg = random.choice(FINAL_WARNING_MESSAGES)
            try:
                await client.send_message(uid, msg, disable_web_page_preview=True)
                sent += 1
            except Exception:
                failed += 1

        text = (
            "🚨 <b>Final Warning Sweep Complete</b>\n\n"
            f"Month: <code>{ym}</code>\n"
            f"Members still behind requirements: <b>{len(behind_ids)}</b>\n"
            f"Final warnings sent: <b>{sent}</b>\n"
            f"DMs failed (no DM / blocked / never started bot): <b>{failed}</b>\n\n"
            "Anyone still not meeting requirements after this can be auto-removed at the end of the month."
        )
        kb = _admin_keyboard(user_id)
        try:
            await cq.message.edit_text(
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer("Final warnings sent.", show_alert=False)
