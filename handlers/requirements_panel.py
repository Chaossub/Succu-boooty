from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Tuple, Optional, Union

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)

from utils.menu_store import store  # Mongo-backed key/value store

log = logging.getLogger(__name__)

# ────────────── SAFE IMPORTS FOR PAYMENTS / REQ STORE ──────────────

# Try to pull real monthly progress from your payments.py
try:
    from payments import get_monthly_progress as _real_get_monthly_progress  # type: ignore

    def get_monthly_progress(user_id: int, year: int, month: int) -> Tuple[float, int]:
        # (game_dollars, model_count)
        return _real_get_monthly_progress(user_id, year, month)

except Exception:
    log.warning("requirements_panel: payments.get_monthly_progress not available, using dummy 0/0")

    def get_monthly_progress(user_id: int, year: int, month: int) -> Tuple[float, int]:
        # Fallback: nothing tracked yet
        return 0.0, 0


# We *try* to use an external ReqStore; if it’s missing, we make a Mongo-backed one
try:
    from req_store import ReqStore as _RealReqStore  # type: ignore

    _store = _RealReqStore()
except Exception:
    log.warning(
        "requirements_panel: req_store.ReqStore not available, using Mongo-backed fallback store via menu_store"
    )

    _EXEMPT_KEY = "ReqExemptV1"  # stored as JSON list of user IDs

    def _load_exempt_ids() -> set[int]:
        raw = store.get_menu(_EXEMPT_KEY) or "[]"
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return {int(x) for x in data}
        except Exception:
            pass
        return set()

    def _save_exempt_ids(ids: set[int]) -> None:
        try:
            store.set_menu(_EXEMPT_KEY, json.dumps(sorted(ids)))
        except Exception:
            log.exception("Failed to persist exemption list")

    class _MongoReqStore:
        def has_valid_exemption(self, user_id: int, chat_id: Optional[int] = None) -> bool:
            ids = _load_exempt_ids()
            return user_id in ids

        def remove_exemption(self, user_id: int, chat_id: Optional[int] = None) -> None:
            ids = _load_exempt_ids()
            if user_id in ids:
                ids.remove(user_id)
                _save_exempt_ids(ids)

        def add_exemption(
            self,
            user_id: int,
            chat_id: Optional[int] = None,
            until_ts: Optional[float] = None,
        ) -> None:
            ids = _load_exempt_ids()
            if user_id not in ids:
                ids.add(user_id)
                _save_exempt_ids(ids)

    _store = _MongoReqStore()


# ────────────── ENV / CONSTANTS ──────────────

OWNER_ID_ENV = os.getenv("OWNER_ID")
OWNER_ID: Optional[int] = int(OWNER_ID_ENV) if OWNER_ID_ENV else None

# Comma or semicolon separated list of Telegram IDs who should see the model tools
REQ_ADMINS_RAW = os.getenv("REQUIREMENTS_ADMINS", "") or ""

# Requirement thresholds (can be overridden via env)
REQ_MIN_DOLLARS = float(os.getenv("REQ_REQUIRE_DOLLARS", "20"))
REQ_MIN_MODELS = int(os.getenv("REQ_REQUIRE_MODELS", "2"))

# Mongo menu_store keys for this panel
MANUAL_KEY = "ReqManualV1"   # per-month extra spend
MEMBERS_KEY = "ReqMembersV1" # logged members from /req_sync

# user_id -> action code (for admin/model flows)
# actions:
#   "add_spend_for:<uid>"
_pending_actions: Dict[int, str] = {}


# ────────────── Manual extra spend storage (Mongo via menu_store) ──────────────

@dataclass
class ManualEntry:
    extra_dollars: float = 0.0
    note: str = ""


def _ym_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _load_manual_raw() -> Dict[str, Dict[str, Dict[str, object]]]:
    """
    Structure:
    {
      "YYYY-MM": {
         "user_id_str": {"extra_dollars": float, "note": "..." }
      }
    }
    """
    raw = store.get_menu(MANUAL_KEY) or "{}"
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        log.exception("Failed to decode manual requirements data")
    return {}


def _save_manual_raw(data: Dict[str, Dict[str, Dict[str, object]]]) -> None:
    try:
        store.set_menu(MANUAL_KEY, json.dumps(data))
    except Exception:
        log.exception("Failed to save manual requirements data")


def _get_manual_entry(user_id: int, year: int, month: int) -> ManualEntry:
    data = _load_manual_raw()
    mk = _ym_key(year, month)
    u = data.get(mk, {}).get(str(user_id))
    if not u:
        return ManualEntry()
    return ManualEntry(
        extra_dollars=float(u.get("extra_dollars", 0.0) or 0.0),
        note=str(u.get("note") or ""),
    )


def _add_manual_spend(user_id: int, year: int, month: int, amount: float, note: str = "") -> ManualEntry:
    data = _load_manual_raw()
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
    _save_manual_raw(data)
    return _get_manual_entry(user_id, year, month)


# ────────────── Tracked members storage (Mongo via menu_store) ──────────────

def _load_members() -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Format:
    {
      "users": {
         "123": {"display": "@name", "first_name": "...", "last_name": "...", "username": "name"},
         ...
      }
    }
    """
    raw = store.get_menu(MEMBERS_KEY) or "{}"
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"users": {}}
        data.setdefault("users", {})
        return data
    except Exception:
        log.exception("Failed to decode req_members data")
        return {"users": {}}


def _save_members(data: Dict[str, Dict[str, Dict[str, str]]]) -> None:
    try:
        store.set_menu(MEMBERS_KEY, json.dumps(data))
    except Exception:
        log.exception("Failed to save req_members data")


async def _sync_group_members(client: Client, chat_id: int) -> Tuple[int, int]:
    """
    Iterate group members, log them into Mongo (via menu_store).
    Returns (seen_count, updated_count).
    """
    data = _load_members()
    users = data.setdefault("users", {})
    seen = 0
    updated = 0

    async for member in client.iter_chat_members(chat_id):
        u = member.user
        if not u or u.is_bot:
            continue
        seen += 1
        key = str(u.id)
        if u.username:
            display = f"@{u.username}"
        else:
            display = (u.first_name or "Unknown").strip()
        rec = users.get(key) or {}
        old_display = rec.get("display")
        if old_display != display:
            users[key] = {
                "display": display,
                "first_name": u.first_name or "",
                "last_name": u.last_name or "",
                "username": u.username or "",
            }
            updated += 1

    data["users"] = users
    _save_members(data)
    return seen, updated


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


def _ensure_admin(user_id: int) -> bool:
    return _role(user_id) in ("owner", "model")


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
            [InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="panels:root")],
        ]
    )


def _model_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:check_self")],
            [InlineKeyboardButton("👤 Look Up Member", callback_data="reqpanel:lookup_prompt")],
            [InlineKeyboardButton("💸 Add Manual Spend", callback_data="reqpanel:add_spend_prompt")],
            [InlineKeyboardButton("⏸ Exempt / Un-exempt", callback_data="reqpanel:exempt_prompt")],
            [InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="panels:root")],
        ]
    )


def _owner_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:check_self")],
            [InlineKeyboardButton("👤 Look Up Member", callback_data="reqpanel:lookup_prompt")],
            [InlineKeyboardButton("💸 Add Manual Spend", callback_data="reqpanel:add_spend_prompt")],
            [InlineKeyboardButton("⏸ Exempt / Un-exempt", callback_data="reqpanel:exempt_prompt")],
            [
                InlineKeyboardButton("🧾 Exempt Members", callback_data="reqpanel:list_exempt"),
                InlineKeyboardButton("📒 Manual Credits", callback_data="reqpanel:list_manual"),
            ],
            [InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="panels:root")],
        ]
    )


# ────────────── UI helpers ──────────────

async def _show_home(client: Client, obj: Union[CallbackQuery, Message]):
    user = obj.from_user
    if not user:
        if isinstance(obj, CallbackQuery):
            await obj.answer()
        return

    role = _role(user.id)

    if role == "owner":
        text = (
            "📌 <b>Requirements Panel – Owner</b>\n\n"
            "Use these tools to check status, add manual credit for offline games, mark members exempt, "
            "and review who is currently exempt or has manual credits logged.\n\n"
            "All changes here affect this month’s requirement checks and future sweeps/reminders."
        )
        kb = _owner_home_kb()
    elif role == "model":
        text = (
            "📌 <b>Requirements Panel – Model Tools</b>\n\n"
            "You can check your own status, look up a member, add manual spend for approved games, "
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

    if isinstance(obj, CallbackQuery):
        try:
            await obj.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await obj.answer()
    else:
        await obj.reply_text(text, reply_markup=kb, disable_web_page_preview=True)


def _build_member_list_kb(action: str, page: int = 0, per_page: int = 8) -> Tuple[str, InlineKeyboardMarkup]:
    """
    action: "lookup", "add", "exempt"
    """
    data = _load_members()
    users = data.get("users", {})
    entries = []
    for uid_str, rec in users.items():
        display = rec.get("display") or uid_str
        entries.append((int(uid_str), display))
    entries.sort(key=lambda x: x[1].lower())

    if not entries:
        text = (
            "👥 <b>No members have been logged yet.</b>\n\n"
            "Ask Roni or a model to run <code>/req_sync</code> in the Sanctuary group to log members "
            "before using this list."
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]]
        )
        return text, kb

    total = len(entries)
    max_page = (total - 1) // per_page if total > 0 else 0
    page = max(0, min(page, max_page))
    start = page * per_page
    end = start + per_page
    slice_entries = entries[start:end]

    if action == "lookup":
        header = "🔍 <b>Pick a member to view their status.</b>"
    elif action == "add":
        header = "💸 <b>Pick a member to add manual spend for.</b>"
    else:
        header = "⏸ <b>Pick a member to exempt / un-exempt.</b>"

    lines = [header, "", f"Page {page + 1} of {max_page + 1}"]

    rows: list[list[InlineKeyboardButton]] = []
    for uid, display in slice_entries:
        label = f"{display} ({uid})"
        rows.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"reqpanel:pick:{action}:{uid}",
                )
            ]
        )

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("◀", callback_data=f"reqpanel:page:{action}:{page - 1}")
        )
    if page < max_page:
        nav_row.append(
            InlineKeyboardButton("▶", callback_data=f"reqpanel:page:{action}:{page + 1}")
        )
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")])

    kb = InlineKeyboardMarkup(rows)
    return "\n".join(lines), kb


# ────────────── register(app) ──────────────

def register(app: Client) -> None:
    log.info(
        "✅ handlers.requirements_panel registered (OWNER_ID=%s, admins=%s)",
        OWNER_ID,
        _req_admin_ids(),
    )

    # ───────── Group sync: /req_sync ─────────
    @app.on_message(filters.group & filters.command(["req_sync", "reqsync"]))
    async def req_sync_cmd(client: Client, m: Message):
        if not m.from_user or not _ensure_admin(m.from_user.id):
            return

        await m.reply_text("👥 Logging members in this chat… this may take a moment.")
        seen, updated = await _sync_group_members(client, m.chat.id)
        await m.reply_text(
            f"✅ Logged <b>{seen}</b> members from this chat.\n"
            f"Updated / added records: <b>{updated}</b>.\n\n"
            "These members will now show up in the Requirements pick-from-list screens.",
            disable_web_page_preview=True,
        )

    # ───────── main entry from menu button ─────────
    @app.on_callback_query(filters.regex(r"^reqpanel:home$"))
    async def reqpanel_home_cb(client: Client, cq: CallbackQuery):
        await _show_home(client, cq)

    # optional backup command in PM
    @app.on_message(filters.private & filters.command(["requirements", "reqpanel"]))
    async def reqpanel_cmd(client: Client, m: Message):
        await _show_home(client, m)

    # ───────── member: check own status ─────────
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

    # ───────── member info panel ─────────
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

    # ───────── Admin/model tools: prompts ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:lookup_prompt$"))
    async def reqpanel_lookup_prompt(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or not _ensure_admin(user.id):
            await cq.answer("Only models / Roni can use that.", show_alert=True)
            return

        text, kb = _build_member_list_kb("lookup", page=0)
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^reqpanel:add_spend_prompt$"))
    async def reqpanel_add_spend_prompt(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or not _ensure_admin(user.id):
            await cq.answer("Only models / Roni can use that.", show_alert=True)
            return

        text, kb = _build_member_list_kb("add", page=0)
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^reqpanel:exempt_prompt$"))
    async def reqpanel_exempt_prompt(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or not _ensure_admin(user.id):
            await cq.answer("Only models / Roni can use that.", show_alert=True)
            return

        text, kb = _build_member_list_kb("exempt", page=0)
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    # ───────── Admin-only: list exemptions & manual credits ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:list_exempt$"))
    async def reqpanel_list_exempt(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or _role(user.id) != "owner":
            await cq.answer()
            return

        if "_EXEMPT_KEY" not in globals():
            text = (
                "🧾 <b>Exempt Members</b>\n\n"
                "Listing exemptions isn’t available because an external requirements store is in use."
            )
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]]
            )
            try:
                await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                pass
            await cq.answer()
            return

        ids = _load_exempt_ids()
        if not ids:
            text = (
                "🧾 <b>Exempt Members</b>\n\n"
                "No one is currently marked exempt for requirements."
            )
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]]
            )
            try:
                await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                pass
            await cq.answer()
            return

        members = _load_members().get("users", {})
        lines = ["🧾 <b>Exempt Members</b>\n"]
        for uid in sorted(ids):
            rec = members.get(str(uid)) or {}
            name = rec.get("display") or f"ID {uid}"
            lines.append(f"• {name} (<code>{uid}</code>)")

        text = "\n".join(lines)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]]
        )
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^reqpanel:list_manual$"))
    async def reqpanel_list_manual(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or _role(user.id) != "owner":
            await cq.answer()
            return

        year, month = _current_year_month()
        mk = _ym_key(year, month)
        data = _load_manual_raw()
        entries = data.get(mk, {})

        if not entries:
            text = (
                f"📒 <b>Manual Credits for {year}-{month:02d}</b>\n\n"
                "No manual credits have been logged yet this month."
            )
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]]
            )
            try:
                await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                pass
            await cq.answer()
            return

        members = _load_members().get("users", {})
        lines = [f"📒 <b>Manual Credits for {year}-{month:02d}</b>\n"]
        for uid_str, rec in entries.items():
            try:
                uid = int(uid_str)
            except ValueError:
                uid = 0
            name_rec = members.get(uid_str) or {}
            name = name_rec.get("display") or f"ID {uid_str}"
            extra = float(rec.get("extra_dollars", 0.0) or 0.0)
            note = str(rec.get("note") or "")
            line = f"• {name} (<code>{uid_str}</code>) — +${extra:.2f}"
            if note:
                line += f"\n  Note: {note}"
            lines.append(line)

        text = "\n".join(lines)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")]]
        )
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    # ───────── Member list pagination ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:page:(lookup|add|exempt):(\d+)$"))
    async def reqpanel_page_cb(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or not _ensure_admin(user.id):
            await cq.answer()
            return

        _, action, page_str = cq.data.split(":")
        page = int(page_str)
        text, kb = _build_member_list_kb(action, page=page)
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    # ───────── Member picked from list ─────────

    @app.on_callback_query(filters.regex(r"^reqpanel:pick:(lookup|add|exempt):(\d+)$"))
    async def reqpanel_pick_cb(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user or not _ensure_admin(user.id):
            await cq.answer()
            return

        _, action, uid_str = cq.data.split(":")
        target_id = int(uid_str)

        year, month = _current_year_month()

        if action == "lookup":
            desc, _data = _status_for_user(target_id, year, month)
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:lookup_prompt")]]
            )
            try:
                await cq.message.edit_text(desc, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                pass
            await cq.answer()
            return

        if action == "add":
            # Next message from this admin will be amount + optional note
            _pending_actions[user.id] = f"add_spend_for:{target_id}"
            text = (
                f"💸 <b>Adding manual spend for user ID {target_id}</b>\n\n"
                "Send me a message in this chat with the format:\n"
                "<code>amount [note]</code>\n\n"
                "Example:\n"
                "<code>15 from CashApp game night</code>\n\n"
                "This adds extra credited dollars on top of Stripe games for <b>this month only</b>."
            )
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:add_spend_prompt")]]
            )
            try:
                await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                pass
            await cq.answer()
            return

        if action == "exempt":
            # toggle exemption immediately
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
                await cq.answer("Something went wrong updating the exemption.", show_alert=True)
                return

            desc, _data = _status_for_user(target_id, year, month)
            if now_exempt:
                prefix = f"⏸ Marked user <code>{target_id}</code> as <b>EXEMPT</b>.\n\n"
            else:
                prefix = f"▶ Removed exemption for user <code>{target_id}</code>.\n\n"

            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="reqpanel:exempt_prompt")]]
            )
            try:
                await cq.message.edit_text(prefix + desc, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                pass
            await cq.answer("Updated exemption.", show_alert=False)
            return

    # ───────── Capture admin text actions (amount + note) ─────────

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

        # add_spend_for:<uid>
        if action.startswith("add_spend_for:"):
            _pending_actions.pop(user.id, None)
            try:
                target_id = int(action.split(":", 1)[1])
            except Exception:
                await m.reply_text("Something went wrong with that member selection. Try again from the menu. 💜")
                return

            parts = text.split(maxsplit=1)
            if not parts:
                await m.reply_text(
                    "Format should be:\n<code>amount [note]</code>\n"
                    "Example:\n<code>15 from CashApp game night</code>",
                    disable_web_page_preview=True,
                )
                return

            try:
                amount = float(parts[0])
            except Exception:
                await m.reply_text("Amount must be a number, like <code>15</code> or <code>20.5</code>. 💜")
                return

            note = parts[1] if len(parts) > 1 else ""

            year, month = _current_year_month()
            _ = _add_manual_spend(target_id, year, month, amount, note)
            desc, _data = _status_for_user(target_id, year, month)

            await m.reply_text(
                f"Added <b>${amount:.2f}</b> manual credit for user <code>{target_id}</code>.\n\n{desc}",
                disable_web_page_preview=True,
            )
            return
