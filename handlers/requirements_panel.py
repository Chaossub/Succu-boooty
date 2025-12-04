# handlers/requirements_panel.py

import json
import logging
import os
import random
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from utils.menu_store import store

log = logging.getLogger(__name__)

# ────────────── OWNER / ADMINS ──────────────

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))

_ADMIN_IDS: set[int] = {OWNER_ID}
_raw_super = (os.getenv("SUPER_ADMINS") or "").strip()
if _raw_super:
    for part in _raw_super.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            _ADMIN_IDS.add(int(part))
        except ValueError:
            log.warning("requirements_panel: bad SUPER_ADMINS id: %r", part)

def _is_admin(user_id: int | None) -> bool:
    if not user_id:
        return False
    return user_id in _ADMIN_IDS


# ────────────── GROUP IDS (FOR SCAN) ──────────────

_raw_group_ids = (os.getenv("SANCTUARY_GROUP_IDS") or "").strip()
_main_group_id_str = (os.getenv("SUCCUBUS_SANCTUARY") or "").strip()

SANCTUARY_GROUP_IDS: List[int] = []

if _raw_group_ids:
    for part in _raw_group_ids.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            gid = int(part)
            SANCTUARY_GROUP_IDS.append(gid)
        except ValueError:
            log.warning(
                "requirements_panel: bad id in SANCTUARY_GROUP_IDS: %r", part
            )

if _main_group_id_str:
    try:
        mg = int(_main_group_id_str)
        if mg not in SANCTUARY_GROUP_IDS:
            SANCTUARY_GROUP_IDS.insert(0, mg)
    except ValueError:
        log.warning(
            "requirements_panel: bad id in SUCCUBUS_SANCTUARY: %r",
            _main_group_id_str,
        )

PRIMARY_GROUP_ID: Optional[int] = SANCTUARY_GROUP_IDS[0] if SANCTUARY_GROUP_IDS else None


# ────────────── REQUIREMENT RULES ──────────────

REQUIRED_SPENT = float(os.getenv("REQ_MIN_SPENT", "20"))
REQUIRED_GAMES = int(os.getenv("REQ_MIN_GAMES", "4"))

try:
    from handlers import payments  # type: ignore
    if not hasattr(payments, "get_monthly_progress"):
        log.warning(
            "requirements_panel: payments.get_monthly_progress not available, "
            "using dummy 0/0"
        )
        payments = None  # type: ignore
except Exception:
    log.warning(
        "requirements_panel: payments.get_monthly_progress not available, "
        "using dummy 0/0"
    )
    payments = None  # type: ignore


# ────────────── STORAGE ──────────────

_STATE_KEY = "RequirementsPanel:state_v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _default_state() -> Dict:
    return {
        "month_key": datetime.now(timezone.utc).strftime("%Y-%m"),
        "members": {},  # uid(str) -> record
    }


def _load_state() -> Dict:
    raw = store.get_menu(_STATE_KEY) or ""
    if not raw:
        return _default_state()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            if "members" not in data:
                data["members"] = {}
            if "month_key" not in data:
                data["month_key"] = datetime.now(timezone.utc).strftime("%Y-%m")
            return data
    except Exception:
        log.exception("requirements_panel: failed to parse state; resetting")
    return _default_state()


def _save_state(state: Dict) -> None:
    try:
        store.set_menu(_STATE_KEY, json.dumps(state))
    except Exception:
        log.exception("requirements_panel: failed to save state")


def _get_display_name(user) -> str:
    if getattr(user, "username", None):
        return f"@{user.username}"
    if getattr(user, "first_name", None):
        if getattr(user, "last_name", None):
            return f"{user.first_name} {user.last_name}"
        return user.first_name
    return f"ID {user.id}"


def _ensure_member(uid: int, name: str | None = None) -> Dict:
    state = _load_state()
    members = state.setdefault("members", {})
    key = str(uid)
    rec = members.get(key)
    if not rec:
        rec = {
            "id": uid,
            "name": name or f"ID {uid}",
            "manual_credit": 0.0,
            "exempt": False,
            "notes": "",
            "reminders_sent": 0,
            "warnings_sent": 0,
            "last_reminder_at": "",
            "last_warning_at": "",
        }
        members[key] = rec
        _save_state(state)
    else:
        # keep existing but maybe refresh name
        if name and rec.get("name") != name:
            rec["name"] = name
            _save_state(state)
    return rec


def _get_member(uid: int) -> Optional[Dict]:
    state = _load_state()
    members = state.get("members", {})
    return members.get(str(uid))


def _update_member(uid: int, rec: Dict) -> None:
    state = _load_state()
    members = state.setdefault("members", {})
    members[str(uid)] = rec
    _save_state(state)


def _iter_members() -> List[Dict]:
    state = _load_state()
    members = state.get("members", {})
    return list(members.values())


# ────────────── PROGRESS / STATUS ──────────────

def _get_auto_progress(uid: int) -> Tuple[float, int]:
    """Return (spent, games) from payments helper or (0,0)."""
    if payments is None:
        return 0.0, 0
    try:
        result = payments.get_monthly_progress(uid)  # type: ignore
        # Allow either (spent, games) or dict
        if isinstance(result, tuple) and len(result) >= 2:
            return float(result[0]), int(result[1])
        if isinstance(result, dict):
            spent = float(result.get("spent", 0.0))
            games = int(result.get("games", 0))
            return spent, games
    except Exception:
        log.exception("requirements_panel: error in payments.get_monthly_progress")
    return 0.0, 0


def _calculate_status(uid: int) -> Dict:
    rec = _get_member(uid) or {
        "id": uid,
        "name": f"ID {uid}",
        "manual_credit": 0.0,
        "exempt": False,
        "notes": "",
        "reminders_sent": 0,
        "warnings_sent": 0,
        "last_reminder_at": "",
        "last_warning_at": "",
    }
    spent_auto, games = _get_auto_progress(uid)
    manual = float(rec.get("manual_credit", 0.0))
    total_spent = spent_auto + manual
    exempt = bool(rec.get("exempt", False))

    meets_money = total_spent >= REQUIRED_SPENT
    meets_games = games >= REQUIRED_GAMES
    meets = meets_money or meets_games or exempt

    reason = "OK"
    if exempt:
        reason = "Exempt"
    elif meets:
        if meets_money:
            reason = f"Met via ${(total_spent):.2f} spent"
        else:
            reason = f"Met via {games} games"
    else:
        reason = "Behind on requirements"

    return {
        "id": uid,
        "name": rec.get("name", f"ID {uid}"),
        "spent_auto": spent_auto,
        "manual_credit": manual,
        "total_spent": total_spent,
        "games": games,
        "exempt": exempt,
        "meets": meets,
        "reason": reason,
        "reminders_sent": int(rec.get("reminders_sent", 0)),
        "warnings_sent": int(rec.get("warnings_sent", 0)),
    }


def _all_status() -> List[Dict]:
    """Return status for all known members."""
    members = _iter_members()
    return [_calculate_status(m["id"]) for m in members]


# ────────────── REMINDER TEXTS ──────────────

REMINDER_MESSAGES: List[str] = [
    "Hey {name}, little Sanctuary nudge ✨ you’re currently behind on this month’s requirements. If you want to stay in our naughty little corner of the internet, make sure you hit your minimum spend or game count soon 💋",
    "Quick check-in, {name} — SuccuBot shows you’re still short on this month’s requirements. If you plan on staying in the Sanctuary, you’ll want to catch up before sweeps run 🖤",
    "{name}, friendly reminder: you haven’t met this month’s Sanctuary requirements yet. A couple games or a bit of spending will fix that — don’t leave it to the last minute 😈",
    "Hi {name}, you’re showing as **behind** on requirements this month. If you want to keep your spot in the Sanctuary, please make sure you hit your minimum soon 💞",
    "{name}, this is a soft reminder that you’re not up to date on Sanctuary requirements. If something’s going on, you can always reach out — but if nothing changes, your access may be paused at sweeps time.",
    "Sanctuary check-in for {name}: our logs say you’re behind on monthly requirements. If you still want to stay, now’s the time to jump into a game or spoil a model a little 💸",
]

FINAL_WARNING_MESSAGES: List[str] = [
    "{name}, this is your last reminder for this month’s Sanctuary requirements. If they aren’t met by the sweep, you’ll be removed from the Sanctuary until the door fee is paid again.",
    "Final notice, {name}: you’re still behind on Sanctuary requirements. If nothing changes before the sweep, your access will be revoked and you’ll need to re-enter through the door fee.",
    "{name}, you’ve hit the final warning stage. You’re still short on this month’s minimums. If requirements aren’t met by the deadline, SuccuBot will remove you from the Sanctuary.",
    "This is your last call, {name}. Our records still show you as behind on requirements. If that doesn’t change before sweeps, you’ll be removed and will have to pay the door fee to return.",
    "Final Sanctuary warning for {name}: no requirements = no access. If you want to stay, please handle it before the sweep runs.",
]


# ────────────── KEYBOARDS ──────────────

def _requirements_main_keyboard(user_id: int | None) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:self")],
        [InlineKeyboardButton("🔍 Look Up Member", callback_data="reqpanel:lookup")],
        [
            InlineKeyboardButton(
                "⬅ Back to Sanctuary Menu", callback_data="portal:home"
            )
        ],
    ]

    if _is_admin(user_id):
        rows.append(
            [InlineKeyboardButton("🛠 Admin Controls", callback_data="reqpanel:admin")]
        )

    return InlineKeyboardMarkup(rows)


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📋 Member Status List", callback_data="reqpanel:admin:list"
                )
            ],
            [
                InlineKeyboardButton(
                    "➕ Add Manual Spend", callback_data="reqpanel:admin:add_spend"
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ Exempt / Un-exempt",
                    callback_data="reqpanel:admin:exempt_list",
                )
            ],
            [
                InlineKeyboardButton(
                    "📡 Scan Group Members", callback_data="reqpanel:admin:scan"
                )
            ],
            [
                InlineKeyboardButton(
                    "📨 Send Reminders (Behind Only)",
                    callback_data="reqpanel:admin:send_reminders",
                )
            ],
            [
                InlineKeyboardButton(
                    "🚨 Send Final Warnings",
                    callback_data="reqpanel:admin:send_final",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back to Requirements Menu",
                    callback_data="reqpanel:home",
                )
            ],
        ]
    )


def _member_select_keyboard(
    members: List[Dict], action_prefix: str, page: int = 0, page_size: int = 8
) -> InlineKeyboardMarkup:
    start = page * page_size
    end = start + page_size
    chunk = members[start:end]

    rows: List[List[InlineKeyboardButton]] = []
    for m in chunk:
        label = f"{m.get('name','ID')} ({m['id']})"
        if len(label) > 40:
            label = label[:37] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"{action_prefix}:{m['id']}",
                )
            ]
        )

    nav_row: List[InlineKeyboardButton] = []
    if start > 0:
        nav_row.append(
            InlineKeyboardButton(
                "⬅ Prev",
                callback_data=f"{action_prefix}_page:{page-1}",
            )
        )
    if end < len(members):
        nav_row.append(
            InlineKeyboardButton(
                "Next ➡",
                callback_data=f"{action_prefix}_page:{page+1}",
            )
        )
    if nav_row:
        rows.append(nav_row)

    rows.append(
        [
            InlineKeyboardButton(
                "⬅ Back to Admin", callback_data="reqpanel:admin"
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


# ────────────── PENDING ADMIN STATE ──────────────

_pending_admin: Dict[int, str] = {}


# ────────────── REGISTER HANDLERS ──────────────

def register(app: Client) -> None:
    log.info(
        "✅ handlers.requirements_panel registered (OWNER_ID=%s, admins=%s)",
        OWNER_ID,
        _ADMIN_IDS,
    )

    # ───────── MAIN ENTRY ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        kb = _requirements_main_keyboard(uid)
        await cq.message.edit_text(
            "📌 <b>Requirements Panel – Owner / Models</b>\n\n"
            "Use these tools to manage Sanctuary requirements for the month.\n"
            "Everything you do here updates what SuccuBot uses when checking "
            "member status or running sweeps, so double-check before you confirm.\n\n"
            "From here you can:\n"
            "• View your own status\n"
            "• Look up a specific member\n"
            "• (Owner) update credits, exemptions, and send reminders\n\n"
            "Only you and approved model admins see the admin controls. "
            "Members just see their own status.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Button from main menu
    @app.on_callback_query(filters.regex(r"^reqpanel:open$"))
    async def reqpanel_open_cb(_, cq: CallbackQuery):
        await reqpanel_home_cb(_, cq)

    # ───────── SELF STATUS ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:self$"))
    async def reqpanel_self_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user:
            await cq.answer()
            return
        uid = cq.from_user.id
        name = _get_display_name(cq.from_user)
        _ensure_member(uid, name)
        status = _calculate_status(uid)

        text = (
            "📍 <b>Your Sanctuary Status</b>\n\n"
            f"Member: {status['name']}\n"
            f"ID: <code>{status['id']}</code>\n\n"
            f"Auto-tracked spend: ${status['spent_auto']:.2f}\n"
            f"Manual credit: ${status['manual_credit']:.2f}\n"
            f"Total counted: ${status['total_spent']:.2f}\n"
            f"Games played (if tracked): {status['games']}\n"
            f"Exempt: {'✅ yes' if status['exempt'] else '❌ no'}\n\n"
            f"Status: {'✅ <b>Requirements Met</b>' if status['meets'] else '⚠️ <b>Behind on Requirements</b>'}\n"
            f"Reason: {status['reason']}"
        )

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⬅ Back to Requirements Menu",
                        callback_data="reqpanel:home",
                    )
                ]
            ]
        )

        await cq.message.edit_text(
            text, reply_markup=kb, disable_web_page_preview=True
        )
        await cq.answer()

    # ───────── LOOKUP (ADMIN ONLY) ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:lookup$"))
    async def reqpanel_lookup_cb(_, cq: CallbackQuery):
        if not cq.from_user:
            await cq.answer()
            return
        uid = cq.from_user.id
        if not _is_admin(uid):
            # Non-admins can only see themselves
            _pending_admin.pop(uid, None)
            await cq.answer()
            await reqpanel_self_cb(_, cq)
            return

        _pending_admin[uid] = "lookup"
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="reqpanel:admin_cancel"
                    )
                ]
            ]
        )
        await cq.message.edit_text(
            "🔍 <b>Look Up Member</b>\n\n"
            "Send me a message with the member’s <code>user_id</code>.\n"
            "Example:\n"
            "<code>123456789</code>",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── ADMIN PANEL ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer("Only approved model admins can use this 💕", show_alert=True)
            return
        await cq.message.edit_text(
            "💼 <b>Requirements Panel – Owner / Models</b>\n\n"
            "Use these tools to manage Sanctuary requirements for the month.\n"
            "From here you can:\n"
            "• View the full member status list\n"
            "• Add manual spend credit for offline payments\n"
            "• Exempt / un-exempt members\n"
            "• Scan group members into the tracker\n"
            "• Send reminder DMs to members who are behind\n"
            "• Send final-warning DMs to those still not caught up\n\n"
            "All changes here affect how SuccuBot checks requirements and "
            "runs sweeps, so double-check before confirming changes.",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── MEMBER LIST ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:admin:list$"))
    async def reqpanel_admin_list_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer("Only approved model admins can use this 💕", show_alert=True)
            return

        status_list = _all_status()
        if not status_list:
            text = (
                "📋 <b>Member Status List</b>\n\n"
                "No members are logged yet. Run <b>📡 Scan Group Members</b> first."
            )
        else:
            lines = ["📋 <b>Member Status List</b>\n"]
            for s in status_list:
                emoji = "✅" if s["meets"] else "⚠️"
                ex = " (Exempt)" if s["exempt"] else ""
                lines.append(
                    f"{emoji} {s['name']} — ID {s['id']}{ex}\n"
                    f"   Spent: ${s['total_spent']:.2f} (auto ${s['spent_auto']:.2f} + manual ${s['manual_credit']:.2f}), "
                    f"Games: {s['games']}, Reason: {s['reason']}"
                )
            text = "\n".join(lines)

        await cq.message.edit_text(
            text,
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── SCAN GROUP MEMBERS ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:admin:scan$"))
    async def reqpanel_admin_scan_cb(client: Client, cq: CallbackQuery):
        """Scan a Sanctuary group and refresh the logged member list.

        - If used in a group, scans that group.
        - If used in DMs, scans PRIMARY_GROUP_ID from env.
        """
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer("Only approved model admins can use this 💕", show_alert=True)
            return

        origin_chat_id = cq.message.chat.id

        # Group chats have negative IDs
        if origin_chat_id < 0:
            target_chat_id = origin_chat_id
        else:
            if PRIMARY_GROUP_ID is None:
                await cq.answer(
                    "I don’t know which Sanctuary group to scan.\n\n"
                    "Please set SUCCUBUS_SANCTUARY or SANCTUARY_GROUP_IDS in your env first.",
                    show_alert=True,
                )
                return
            target_chat_id = PRIMARY_GROUP_ID

        state = _load_state()
        members = state.get("members", {})
        existing_ids = {int(k) for k in members.keys()}
        added = 0

        try:
            async for member in client.iter_chat_members(target_chat_id):
                u = member.user
                if u.is_bot:
                    continue
                uid = u.id
                name = _get_display_name(u)
                _ensure_member(uid, name)
                if uid not in existing_ids:
                    added += 1
                    existing_ids.add(uid)
        except Exception:
            log.exception(
                "requirements_panel: failed to scan members for chat_id=%s",
                target_chat_id,
            )
            await cq.answer("Scan failed. Check logs.", show_alert=True)
            return

        # re-save state in case _ensure_member wrote any new users
        _save_state(_load_state())

        await cq.message.edit_text(
            "📡 <b>Scan finished</b>\n\n"
            f"Target group ID: <code>{target_chat_id}</code>\n"
            f"New members logged this scan: <b>{added}</b>\n"
            f"Total logged members this month: <b>{len(existing_ids)}</b>",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer("Scan complete ✅")

    # ───────── EXEMPT / UN-EXEMPT LIST ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:admin:exempt_list$"))
    async def reqpanel_admin_exempt_list_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer("Only approved model admins can use this 💕", show_alert=True)
            return

        members = sorted(_iter_members(), key=lambda m: m.get("name", ""))
        if not members:
            await cq.answer("No members logged yet. Scan a group first.", show_alert=True)
            return

        kb = _member_select_keyboard(members, "reqpanel:admin:ex_toggle_page", 0)
        await cq.message.edit_text(
            "✅ <b>Exempt / Un-exempt Members</b>\n\n"
            "Tap a member below to toggle their exemption status.\n"
            "Exempt members are treated as meeting requirements even if they "
            "haven’t spent or played enough.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Page navigation for exempt list
    @app.on_callback_query(filters.regex(r"^reqpanel:admin:ex_toggle_page:(\d+)$"))
    async def reqpanel_admin_ex_page_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer()
            return

        page = int(cq.data.split(":")[-1])
        members = sorted(_iter_members(), key=lambda m: m.get("name", ""))
        kb = _member_select_keyboard(members, "reqpanel:admin:ex_toggle_page", page)
        await cq.message.edit_text(
            "✅ <b>Exempt / Un-exempt Members</b>\n\n"
            "Tap a member below to toggle their exemption status.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Toggle exemption
    @app.on_callback_query(filters.regex(r"^reqpanel:admin:ex_toggle_page:(\d+):(\d+)$"))
    async def reqpanel_admin_ex_toggle_from_page_cb(_, cq: CallbackQuery):
        # Not used; kept for compatibility if Telegram ever sends odd data
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^reqpanel:admin:ex_toggle:(\d+)$"))
    async def reqpanel_admin_ex_toggle_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer()
            return

        uid = int(cq.data.split(":")[-1])
        rec = _get_member(uid) or _ensure_member(uid, f"ID {uid}")
        rec["exempt"] = not bool(rec.get("exempt", False))
        _update_member(uid, rec)

        msg = (
            f"Member <code>{uid}</code> is now "
            f"{'✅ EXEMPT' if rec['exempt'] else '❌ not exempt'}."
        )

        await cq.answer("Toggled exemption ✅", show_alert=False)
        await cq.message.reply_text(msg, disable_web_page_preview=True)

    # ───────── MANUAL SPEND (SELECT + ENTER) ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:admin:add_spend$"))
    async def reqpanel_admin_add_spend_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer("Only approved model admins can use this 💕", show_alert=True)
            return

        uid = cq.from_user.id
        _pending_admin[uid] = "add_spend_instructions"

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🧾 Pick Member from List",
                        callback_data="reqpanel:admin:add_spend_pick",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="reqpanel:admin_cancel"
                    )
                ],
            ]
        )

        await cq.message.edit_text(
            "➕ <b>Add Manual Spend</b>\n\n"
            "Send me a message in this format:\n"
            "<code>USER_ID  amount  [note]</code>\n\n"
            "Example:\n"
            "<code>123456789  15  from CashApp game night</code>\n\n"
            "This adds extra credited dollars on top of Stripe games for this month only.\n\n"
            "If you don’t remember the user_id, tap “🧾 Pick Member from List”.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^reqpanel:admin:add_spend_pick$"))
    async def reqpanel_admin_add_spend_pick_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer()
            return

        members = sorted(_iter_members(), key=lambda m: m.get("name", ""))
        if not members:
            await cq.answer("No members logged yet. Scan a group first.", show_alert=True)
            return

        uid = cq.from_user.id
        _pending_admin[uid] = "add_spend_pick"

        kb = _member_select_keyboard(
            members, "reqpanel:admin:add_spend_member_page", 0
        )
        await cq.message.edit_text(
            "➕ <b>Add Manual Spend</b>\n\n"
            "Pick the member you want to credit. I’ll then ask for the amount.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Page nav for manual-spend pick
    @app.on_callback_query(
        filters.regex(r"^reqpanel:admin:add_spend_member_page:(\d+)$")
    )
    async def reqpanel_admin_add_spend_page_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer()
            return

        page = int(cq.data.split(":")[-1])
        members = sorted(_iter_members(), key=lambda m: m.get("name", ""))
        kb = _member_select_keyboard(
            members, "reqpanel:admin:add_spend_member_page", page
        )
        await cq.message.edit_text(
            "➕ <b>Add Manual Spend</b>\n\n"
            "Pick the member you want to credit. I’ll then ask for the amount.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # When a member is chosen from the list
    @app.on_callback_query(
        filters.regex(r"^reqpanel:admin:add_spend_member:(\d+)$")
    )
    async def reqpanel_admin_add_spend_member_cb(_, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer()
            return

        owner_id = cq.from_user.id
        target_id = int(cq.data.split(":")[-1])
        _pending_admin[owner_id] = f"add_spend_for:{target_id}"

        rec = _get_member(target_id) or _ensure_member(target_id, f"ID {target_id}")
        name = rec.get("name", f"ID {target_id}")

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ Cancel", callback_data="reqpanel:admin_cancel"
                    )
                ]
            ]
        )

        await cq.message.edit_text(
            f"➕ <b>Add Manual Spend</b>\n\n"
            f"Member: {name} (ID {target_id})\n\n"
            "Send the amount and optional note in this format:\n"
            "<code>amount  [note]</code>\n\n"
            "Example:\n"
            "<code>20  from CashApp offline tip</code>",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── SEND REMINDERS / FINAL WARNINGS ─────────

    async def _send_bulk_messages(
        client: Client,
        user_ids: List[int],
        templates: List[str],
        tag: str,
    ) -> int:
        sent = 0
        for uid in user_ids:
            rec = _get_member(uid) or _ensure_member(uid, f"ID {uid}")
            name = rec.get("name", f"ID {uid}")
            text = random.choice(templates).format(name=name)

            try:
                await client.send_message(uid, text)
            except Exception:
                log.exception("requirements_panel: failed to DM user %s", uid)
                continue

            if tag == "reminder":
                rec["reminders_sent"] = int(rec.get("reminders_sent", 0)) + 1
                rec["last_reminder_at"] = _now_iso()
            elif tag == "warning":
                rec["warnings_sent"] = int(rec.get("warnings_sent", 0)) + 1
                rec["last_warning_at"] = _now_iso()
            _update_member(uid, rec)
            sent += 1
        return sent

    @app.on_callback_query(filters.regex(r"^reqpanel:admin:send_reminders$"))
    async def reqpanel_admin_send_reminders_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer("Only approved model admins can use this 💕", show_alert=True)
            return

        status_list = _all_status()
        behind_ids = [
            s["id"]
            for s in status_list
            if not s["meets"] and not s["exempt"]
        ]

        if not behind_ids:
            await cq.answer(
                "Everyone currently logged either meets requirements or is exempt 💕",
                show_alert=True,
            )
            return

        count = await _send_bulk_messages(
            client, behind_ids, REMINDER_MESSAGES, "reminder"
        )

        await cq.message.edit_text(
            "📨 <b>Reminders Sent</b>\n\n"
            f"Members behind on requirements (and not exempt): <b>{len(behind_ids)}</b>\n"
            f"DMs successfully sent: <b>{count}</b>",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer("Reminder DMs sent ✅", show_alert=False)

    @app.on_callback_query(filters.regex(r"^reqpanel:admin:send_final$"))
    async def reqpanel_admin_send_final_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_admin(cq.from_user.id):
            await cq.answer("Only approved model admins can use this 💕", show_alert=True)
            return

        status_list = _all_status()
        behind_ids = [
            s["id"]
            for s in status_list
            if not s["meets"] and not s["exempt"]
        ]

        if not behind_ids:
            await cq.answer(
                "No one is currently behind on requirements — nothing to warn. 💕",
                show_alert=True,
            )
            return

        count = await _send_bulk_messages(
            client, behind_ids, FINAL_WARNING_MESSAGES, "warning"
        )

        await cq.message.edit_text(
            "🚨 <b>Final Warnings Sent</b>\n\n"
            f"Members still behind (and not exempt): <b>{len(behind_ids)}</b>\n"
            f"Final-warning DMs successfully sent: <b>{count}</b>\n\n"
            "Anyone still behind when sweeps run will be removed and will need "
            "to pay the door fee again to return.",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer("Final-warning DMs sent ✅", show_alert=False)

    # ───────── ADMIN CANCEL ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:admin_cancel$"))
    async def reqpanel_admin_cancel_cb(_, cq: CallbackQuery):
        if not cq.from_user:
            await cq.answer()
            return
        _pending_admin.pop(cq.from_user.id, None)
        await reqpanel_admin_cb(_, cq)

    # ───────── ADMIN TEXT CAPTURE (lookup / manual spend) ─────────

    @app.on_message(filters.private & filters.text, group=-2)
    async def reqpanel_admin_text_capture(client: Client, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id
        if not _is_admin(uid):
            return

        action = _pending_admin.get(uid)
        if not action:
            return

        # prevent other handlers from grabbing this
        try:
            m.stop_propagation()
        except Exception:
            pass

        text = m.text.strip()

        # --- lookup ---
        if action == "lookup":
            try:
                target_id = int(text.split()[0])
            except Exception:
                await m.reply_text(
                    "User ID must be a number. Try again or tap ❌ Cancel.",
                    disable_web_page_preview=True,
                )
                return

            rec = _ensure_member(target_id, f"ID {target_id}")
            status = _calculate_status(target_id)
            _pending_admin.pop(uid, None)

            msg = (
                "🔍 <b>Member Lookup</b>\n\n"
                f"Name: {status['name']}\n"
                f"ID: <code>{status['id']}</code>\n\n"
                f"Auto-tracked spend: ${status['spent_auto']:.2f}\n"
                f"Manual credit: ${status['manual_credit']:.2f}\n"
                f"Total counted: ${status['total_spent']:.2f}\n"
                f"Games (if tracked): {status['games']}\n"
                f"Exempt: {'✅ yes' if status['exempt'] else '❌ no'}\n\n"
                f"Status: {'✅ Requirements Met' if status['meets'] else '⚠️ Behind'}\n"
                f"Reason: {status['reason']}\n\n"
                f"Reminders sent: {rec.get('reminders_sent',0)}\n"
                f"Final warnings sent: {rec.get('warnings_sent',0)}"
            )
            await m.reply_text(
                msg,
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return

        # --- add_spend via full line: USER_ID amount [note] ---
        if action == "add_spend_instructions":
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                await m.reply_text(
                    "Format is:\n<code>USER_ID  amount  [note]</code>",
                    disable_web_page_preview=True,
                )
                return
            try:
                target_id = int(parts[0])
                amount = float(parts[1])
            except Exception:
                await m.reply_text(
                    "User ID must be a number and amount must be a valid number.",
                    disable_web_page_preview=True,
                )
                return

            note = parts[2] if len(parts) == 3 else ""
            rec = _ensure_member(target_id, f"ID {target_id}")
            rec["manual_credit"] = float(rec.get("manual_credit", 0.0)) + amount
            if note:
                existing_note = rec.get("notes", "") or ""
                if existing_note:
                    rec["notes"] = existing_note + "\n" + note
                else:
                    rec["notes"] = note
            _update_member(target_id, rec)
            _pending_admin.pop(uid, None)

            await m.reply_text(
                f"Added ${amount:.2f} manual credit for user ID {target_id}.\n"
                f"Total manual credit now: ${rec['manual_credit']:.2f}",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return

        # --- add_spend after picking member: amount [note] ---
        if action.startswith("add_spend_for:"):
            try:
                target_id = int(action.split(":", 1)[1])
            except Exception:
                _pending_admin.pop(uid, None)
                await m.reply_text(
                    "Something went wrong with the selected member. Please try again.",
                    disable_web_page_preview=True,
                )
                return

            parts = text.split(maxsplit=1)
            try:
                amount = float(parts[0])
            except Exception:
                await m.reply_text(
                    "Amount must be a valid number. Example:\n<code>20 from CashApp tip</code>",
                    disable_web_page_preview=True,
                )
                return

            note = parts[1] if len(parts) == 2 else ""
            rec = _ensure_member(target_id, f"ID {target_id}")
            rec["manual_credit"] = float(rec.get("manual_credit", 0.0)) + amount
            if note:
                existing_note = rec.get("notes", "") or ""
                if existing_note:
                    rec["notes"] = existing_note + "\n" + note
                else:
                    rec["notes"] = note
            _update_member(target_id, rec)
            _pending_admin.pop(uid, None)

            await m.reply_text(
                f"Added ${amount:.2f} manual credit for user ID {target_id}.\n"
                f"Total manual credit now: ${rec['manual_credit']:.2f}",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return
