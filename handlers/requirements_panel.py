from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from handlers.payments import get_monthly_progress
from req_store import ReqStore  # uses your existing DM-ready / exemption store

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
MANUAL_FILE = DATA_DIR / "manual_requirements.json"

OWNER_ID_ENV = os.getenv("OWNER_ID")
OWNER_ID: Optional[int] = int(OWNER_ID_ENV) if OWNER_ID_ENV else None

# Comma or semicolon separated list of Telegram IDs who should see the model tools
REQ_ADMINS_RAW = os.getenv("REQUIREMENTS_ADMINS", "") or ""

# Requirement thresholds (can be overridden via env)
REQ_MIN_DOLLARS = float(os.getenv("REQ_REQUIRE_DOLLARS", "20"))
REQ_MIN_MODELS = int(os.getenv("REQ_REQUIRE_MODELS", "2"))

_store = ReqStore()

# user_id -> action code (for admin/model flows)
_pending_actions: Dict[int, str] = {}


# ────────────── Manual extra spend storage ──────────────

@dataclass
class ManualEntry:
    extra_dollars: float = 0.0
    note: str = ""


def _ym_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _load_manual() -> Dict[str, Dict[str, Dict[str, object]]]:
    if not MANUAL_FILE.exists():
        return {}
    try:
        with MANUAL_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.exception("Failed to load manual requirements file")
        return {}


def _save_manual(data: Dict[str, Dict[str, Dict[str, object]]]) -> None:
    try:
        with MANUAL_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        log.exception("Failed to save manual requirements file")


def _get_manual_entry(user_id: int, year: int, month: int) -> ManualEntry:
    data = _load_manual()
    mk = _ym_key(year, month)
    u = data.get(mk, {}).get(str(user_id))
    if not u:
        return ManualEntry()
    return ManualEntry(
        extra_dollars=float(u.get("extra_dollars", 0.0) or 0.0),
        note=str(u.get("note") or ""),
    )


def _add_manual_spend(user_id: int, year: int, month: int, amount: float, note: str = "") -> ManualEntry:
    data = _load_manual()
    mk = _ym_key(year, month)
    users = data.setdefault(mk, {})
    rec = users.get(str(user_id)) or {"extra_dollars": 0.0, "note": ""}
    rec["extra_dollars"] = float(rec.get("extra_dollars", 0.0) or 0.0) + amount
    if note:
        if rec.get("note"):
            rec["note"] = f"{rec['note']} | {note}"
        else:
            rec["note"] = note
    users[str(user_id)] = rec
    data[mk] = users
    _save_manual(data)
    return _get_manual_entry(user_id, year, month)


# ────────────── Role helpers ──────────────

def _req_admin_ids() -> set[int]:
    ids: set[int] = set()
    raw = REQ_ADMINS_RAW.replace(";", ",")
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    if OWNER_ID:
        ids.add(OWNER_ID)
    return ids


def _role(user_id: int) -> str:
    if OWNER_ID and user_id == OWNER_ID:
        return "owner"
    if user_id in _req_admin_ids():
        return "model"
    return "member"


# ────────────── Status helpers ──────────────

def _current_year_month() -> Tuple[int, int]:
    now = datetime.utcnow()
    return now.year, now.month


def _status_for_user(user_id: int, year: int, month: int) -> Tuple[str, Dict[str, object]]:
    """
    Returns (description_text, raw_data_dict) for a user for UI use.
    """
    game_dollars, model_count = get_monthly_progress(user_id, year, month)
    manual = _get_manual_entry(user_id, year, month)
    total_dollars = game_dollars + manual.extra_dollars

    # Requirements check
    meets_dollars = total_dollars >= REQ_MIN_DOLLARS
    meets_models = model_count >= REQ_MIN_MODELS
    meets_all = meets_dollars and meets_models

    # exemption (global only, for now)
    try:
        exempt = _store.has_valid_exemption(user_id, chat_id=None)
    except Exception:
        exempt = False

    lines = [
        f"📌 <b>Requirements Status for {year}-{month:02d}</b>",
        f"User ID: <code>{user_id}</code>",
        "",
        f"Stripe game spend this month: <b>${game_dollars:.2f}</b>",
        f"Manual extra credit: <b>${manual.extra_dollars:.2f}</b>",
        f"Total counted spend: <b>${total_dollars:.2f}</b>",
        f"Models spoiled (Stripe only): <b>{model_count}</b>",
        "",
        f"Threshold: at least <b>${REQ_MIN_DOLLARS:.0f}</b> and <b>{REQ_MIN_MODELS}</b> model(s).",
        "",
    ]

    if exempt:
        lines.append("✅ <b>EXEMPT</b> this month by Sanctuary management.")
    elif meets_all:
        lines.append("✅ This user has <b>met</b> this month’s requirements.")
    else:
        lines.append("❌ This user has <b>NOT met</b> this month’s requirements yet.")

        missing_dollars = max(0.0, REQ_MIN_DOLLARS - total_dollars)
        missing_models = max(0, REQ_MIN_MODELS - model_count)
        details: list[str] = []
        if missing_dollars > 0:
            details.append(f"${missing_dollars:.2f} more in games/tips/approved spend")
        if missing_models > 0:
            details.append(f"love for {missing_models} more model(s)")
        if details:
            lines.append("They still need: " + "; ".join(details) + ".")

    if manual.note:
        lines.append("")
        lines.append(f"<b>Manual note:</b> {manual.note}")

    return "\n".join(lines), {
        "game_dollars": game_dollars,
        "manual_extra": manual.extra_dollars,
        "total_dollars": total_dollars,
        "model_count": model_count,
        "exempt": exempt,
        "meets": meets_all,
    }


# ────────────── Keyboards ──────────────

def _member_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:check_self")],
            [InlineKeyboardButton("ℹ️ What Counts as Requirements?", callback_data="reqpanel:info")],
        ]
    )


def _model_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:check_self")],
            [InlineKeyboardButton("👤 Look Up Member", callback_data="reqpanel:lookup_prompt")],
            [InlineKeyboardButton("💸 Add Manual Spend", callback_data="reqpanel:add_spend_prompt")],
            [InlineKeyboardButton("⏸ Exempt / Un-exempt", callback_data="reqpanel:exempt_prompt")],
        ]
    )


def _owner_home_kb() -> InlineKeyboardMarkup:
    # For now owner has the same tools as models; we can add sweeps later.
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:check_self")],
            [InlineKeyboardButton("👤 Look Up Member", callback_data="reqpanel:lookup_prompt")],
            [InlineKeyboardButton("💸 Add Manual Spend", callback_data="reqpanel:add_spend_prompt")],
            [InlineKeyboardButton("⏸ Exempt / Un-exempt", callback_data="reqpanel:exempt_prompt")],
        ]
    )


# ────────────── UI helpers ──────────────

async def _show_home(client: Client, cq: CallbackQuery | Message):
    user = cq.from_user if isinstance(cq, CallbackQuery) else cq.from_user
    if not user:
        if isinstance(cq, CallbackQuery):
            await cq.answer()
        return

    role = _role(user.id)

    if role == "owner":
        text = (
            "📌 <b>Requirements Panel – Owner</b>\n\n"
            "Use these tools to check status, add manual credit for offline games, and mark members exempt.\n\n"
            "All changes here affect this month’s requirement checks and future sweeps/reminders."
        )
        kb = _owner_home_kb()
    elif role == "model":
        text = (
            "📌 <b>Requirements Panel – Model Tools</b>\n\n"
            "You can check your own status, look up a member by ID, add manual spend for approved games, "
            "and mark members exempt when Roni says it’s okay.\n\n"
            "Be careful – changes here affect whether members get to stay in the Sanctuary."
        )
        kb = _model_home_kb()
    else:
        text = (
            "📌 <b>Sanctuary Requirements</b>\n\n"
            "Use the buttons below to check if you’ve met this month’s requirements, "
            "or to see what counts toward them."
        )
        kb = _member_home_kb()

    if isinstance(cq, CallbackQuery):
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()
    else:
        await cq.reply_text(text, reply_markup=kb, disable_web_page_preview=True)


# ────────────── register(app) ──────────────

def register(app: Client) -> None:
    log.info("✅ handlers.requirements_panel registered (OWNER_ID=%s, admins=%s)", OWNER_ID, _req_admin_ids())

    # main entry from menu button
    @app.on_callback_query(filters.regex(r"^reqpanel:home$"))
    async def reqpanel_home_cb(client: Client, cq: CallbackQuery):
        await _show_home(client, cq)

    # optional backup command in PM
    @app.on_message(filters.private & filters.command(["requirements", "reqpanel"]))
    async def reqpanel_cmd(client: Client, m: Message):
        await _show_home(client, m)

    # member: check own status
    @app.on_callback_query(filters.regex(r"^reqpanel:check_self$"))
    async def reqpanel_check_self(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return

        year, month = _current_year_month()
        text, _data = _status_for_user(user.id, year, month)

        try:
            await cq.message.edit_text(
                text,
                reply_markup=_member_home_kb(),
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # info panel
    @app.on_callback_query(filters.regex(r"^reqpanel:info$"))
    async def reqpanel_info(client: Client, cq: CallbackQuery):
        text = (
            "ℹ️ <b>What Counts as Requirements?</b>\n\n"
            f"Right now Sanctuary requirements are usually at least <b>${REQ_MIN_DOLLARS:.0f}</b> in approved games, tips, "
            f"or bundles during the month, and support for at least <b>{REQ_MIN_MODELS}</b> different models.\n\n"
            "Manual credit that a model adds for you (for CashApp, offline games, etc.) also counts here once it’s logged."
        )
        try:
            await cq.message.edit_text(
                text,
                reply_markup=_member_home_kb(),
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # ────────────── Admin/model tools ──────────────

    def _ensure_admin(user_id: int) -> bool:
        return _role(user_id) in ("owner", "model")

    # look up member prompt
    @app.on_callback_query(filters.regex(r"^reqpanel:lookup_prompt$"))
    async def reqpanel_lookup_prompt(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or not _ensure_admin(user.id):
            await cq.answer("Only models / Roni can use that.", show_alert=True)
            return

        _pending_actions[user.id] = "lookup"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]])
        text = (
            "🔍 <b>Look Up Member</b>\n\n"
            "Send me the member’s <b>Telegram numeric ID</b> in one message.\n"
            "I’ll reply with their current monthly requirements status."
        )
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    # add manual spend prompt
    @app.on_callback_query(filters.regex(r"^reqpanel:add_spend_prompt$"))
    async def reqpanel_add_spend_prompt(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or not _ensure_admin(user.id):
            await cq.answer("Only models / Roni can use that.", show_alert=True)
            return

        _pending_actions[user.id] = "add_spend"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]])
        text = (
            "💸 <b>Add Manual Spend</b>\n\n"
            "Send me a message in this format:\n"
            "<code>USER_ID amount [note]</code>\n\n"
            "Example:\n"
            "<code>123456789 15 from CashApp game night</code>\n\n"
            "This adds extra credited dollars on top of Stripe games for <b>this month only</b>."
        )
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    # exempt toggle prompt
    @app.on_callback_query(filters.regex(r"^reqpanel:exempt_prompt$"))
    async def reqpanel_exempt_prompt(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or not _ensure_admin(user.id):
            await cq.answer("Only models / Roni can use that.", show_alert=True)
            return

        _pending_actions[user.id] = "exempt"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]])
        text = (
            "⏸ <b>Exempt / Un-exempt Member</b>\n\n"
            "Send me the member’s <b>Telegram numeric ID</b> in one message.\n\n"
            "If they are currently exempt, I will remove the exemption.\n"
            "If they are not exempt, I will mark them exempt for this month and future checks."
        )
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    # capture admin text actions
    @app.on_message(filters.private & filters.text, group=-3)
    async def reqpanel_capture_private(client: Client, m: Message):
        user = m.from_user
        if not user:
            return
        action = _pending_actions.get(user.id)
        if not action:
            return

        # only models/owner allowed in this flow
        if not _ensure_admin(user.id):
            _pending_actions.pop(user.id, None)
            return

        text = m.text.strip()

        # ----- lookup -----
        if action == "lookup":
            _pending_actions.pop(user.id, None)
            try:
                target_id = int(text.split()[0])
            except Exception:
                await m.reply_text("I need just a numeric Telegram user ID. Try again from the menu. 💜")
                return

            year, month = _current_year_month()
            desc, data = _status_for_user(target_id, year, month)
            await m.reply_text(desc, disable_web_page_preview=True)
            return

        # ----- add manual spend -----
        if action == "add_spend":
            _pending_actions.pop(user.id, None)
            parts = text.split(maxsplit=2)
            if len(parts) < 2:
                await m.reply_text(
                    "Format should be:\n<code>USER_ID amount [note]</code>\n"
                    "Example:\n<code>123456789 15 from CashApp game night</code>",
                    disable_web_page_preview=True,
                )
                return
            try:
                target_id = int(parts[0])
                amount = float(parts[1])
            except Exception:
                await m.reply_text("USER_ID must be a number and amount must be a number. 💜")
                return
            note = parts[2] if len(parts) > 2 else ""

            year, month = _current_year_month()
            entry = _add_manual_spend(target_id, year, month, amount, note)
            desc, data = _status_for_user(target_id, year, month)

            await m.reply_text(
                f"Added <b>${amount:.2f}</b> manual credit for user <code>{target_id}</code>.\n\n{desc}",
                disable_web_page_preview=True,
            )
            return

        # ----- exempt toggle -----
        if action == "exempt":
            _pending_actions.pop(user.id, None)
            try:
                target_id = int(text.split()[0])
            except Exception:
                await m.reply_text("I need a numeric Telegram user ID. Try again from the menu. 💜")
                return

            # toggle exemption (global)
            try:
                currently = _store.has_valid_exemption(target_id, chat_id=None)
            except Exception:
                currently = False

            try:
                if currently:
                    _store.remove_exemption(target_id, chat_id=None)
                    now_exempt = False
                else:
                    _store.add_exemption(target_id, chat_id=None, until_ts=None)
                    now_exempt = True
            except Exception as e:
                log.exception("Failed to toggle exemption: %s", e)
                await m.reply_text("Something went wrong while updating the exemption. 💜")
                return

            year, month = _current_year_month()
            desc, data = _status_for_user(target_id, year, month)

            if now_exempt:
                prefix = f"⏸ Marked user <code>{target_id}</code> as <b>EXEMPT</b>.\n\n"
            else:
                prefix = f"▶ Removed exemption for user <code>{target_id}</code>.\n\n"

            await m.reply_text(prefix + desc, disable_web_page_preview=True)
            return
