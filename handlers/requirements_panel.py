# handlers/requirements_panel.py
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Tuple

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from handlers.payments import get_monthly_progress, has_met_requirements
from req_store import ReqStore

log = logging.getLogger(__name__)

_store = ReqStore()

OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID") else None

def _req_admin_ids() -> set[int]:
    raw = os.getenv("REQUIREMENTS_ADMINS", "") or ""
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            pass
    if OWNER_ID:
        ids.add(OWNER_ID)
    return ids

def _role(user_id: int) -> str:
    if OWNER_ID and user_id == OWNER_ID:
        return "owner"
    if user_id in _req_admin_ids():
        return "model"
    return "member"

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
            [InlineKeyboardButton("👥 Sync Group Members", callback_data="reqpanel:sync")],
            [InlineKeyboardButton("📋 View Tracked / Unmet", callback_data="reqpanel:list_unmet")],
            [InlineKeyboardButton("👤 Find Member", callback_data="reqpanel:find_prompt")],
        ]
    )

def _owner_home_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("👥 Sync Group Members", callback_data="reqpanel:sync")],
        [InlineKeyboardButton("📋 View Tracked / Unmet", callback_data="reqpanel:list_unmet")],
        [InlineKeyboardButton("👤 Find Member", callback_data="reqpanel:find_prompt")],
        [
            InlineKeyboardButton("🔍 Live Sweep", callback_data="reqpanel:sweep"),
            InlineKeyboardButton("🧹 Run Purge", callback_data="reqpanel:purge_confirm"),
        ],
        [
            InlineKeyboardButton("📅 Mid-Month Reminders", callback_data="reqpanel:remind_mid"),
            InlineKeyboardButton("⏰ 3-Day Reminders", callback_data="reqpanel:remind_3d"),
        ],
    ]
    return InlineKeyboardMarkup(rows)

async def _show_home(client: Client, cq: CallbackQuery):
    user = cq.from_user
    if not user:
        return
    role = _role(user.id)

    if role == "owner":
        text = (
            "📌 <b>Requirements Panel – Owner</b>\n\n"
            "You can sync members, view unmet users, adjust spend/exemptions (coming soon), "
            "and run sweeps / purges.\n\n"
            "_Owner-only tools are at the bottom._"
        )
        kb = _owner_home_kb()
    elif role == "model":
        text = (
            "📌 <b>Requirements Panel – Model Tools</b>\n\n"
            "You can sync members and view which buyers are being tracked for requirements. "
            "Spend tracking + exemptions will live here next.\n\n"
            "_Only Roni can run purges or global sweeps._"
        )
        kb = _model_home_kb()
    else:
        text = (
            "📌 <b>Sanctuary Requirements</b>\n\n"
            "Use the buttons below to check if you’ve met this month’s requirements, "
            "or to see what counts toward them."
        )
        kb = _member_home_kb()

    try:
        await cq.message.edit_text(
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
    except Exception as e:
        log.warning("Failed to show requirements home: %s", e)
    await cq.answer()

def _current_year_month() -> Tuple[int, int]:
    now = datetime.utcnow()
    return now.year, now.month

def register(app: Client) -> None:
    log.info("Registering handlers.requirements_panel")

    # main entry from the DM menu button
    @app.on_callback_query(filters.regex(r"^reqpanel:home$"))
    async def reqpanel_home_cb(client: Client, cq: CallbackQuery):
        await _show_home(client, cq)

    # backup command in DM
    @app.on_message(filters.private & filters.command(["requirements", "reqpanel"]))
    async def reqpanel_cmd(client: Client, m):
        # Fake a CallbackQuery-like entry
        class _Dummy:
            from_user = m.from_user
            message = m
            async def answer(self, *a, **k): ...
        await _show_home(client, _Dummy())

    # member: check self status
    @app.on_callback_query(filters.regex(r"^reqpanel:check_self$"))
    async def reqpanel_check_self(client: Client, cq: CallbackQuery):
        user = cq.from_user
        if not user:
            await cq.answer()
            return

        year, month = _current_year_month()
        spent, models = get_monthly_progress(user.id, year, month)
        met = has_met_requirements(user.id, year, month)
        exempt = _store.has_valid_exemption(user.id, chat_id=None)

        text_lines = [
            f"📌 <b>Requirements Status for {year}-{month:02d}</b>\n",
            f"Total game spend: <b>${spent:.2f}</b>",
            f"Models supported: <b>{models}</b>",
            "",
        ]
        if exempt:
            text_lines.append("✅ You are <b>exempt</b> for this month by Sanctuary management.")
        elif met:
            text_lines.append("✅ You have <b>met</b> this month’s requirements.")
        else:
            text_lines.append("❌ You have <b>not yet met</b> this month’s requirements.")
        text = "\n".join(text_lines)

        try:
            await cq.message.edit_text(
                text,
                reply_markup=_member_home_kb(),
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.warning("Failed to edit status msg: %s", e)
        await cq.answer()

    # member: info text
    @app.on_callback_query(filters.regex(r"^reqpanel:info$"))
    async def reqpanel_info(client: Client, cq: CallbackQuery):
        text = (
            "ℹ️ <b>What Counts as Requirements?</b>\n\n"
            "Right now to stay in the Sanctuary you need to do at least one of:\n"
            "• Spend <b>$20+</b> total in games/menus/tips, and support at least two models\n"
            "• (Or whatever current rules Roni sets in announcements.)\n\n"
            "Ask a model or check the SuccuBot menus if you’re unsure."
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

    # model/owner: sync group members – we’ll plug into your existing DM-ready + store later
    @app.on_callback_query(filters.regex(r"^reqpanel:sync$"))
    async def reqpanel_sync(client: Client, cq: CallbackQuery):
        role = _role(cq.from_user.id if cq.from_user else 0)
        if role not in ("owner", "model"):
            await cq.answer("You don’t have permission for this.", show_alert=True)
            return

        # For now, just a stub message – we’ll wire this to ReqStore + SANCTUARY_CHAT_ID next
        text = (
            "👥 <b>Sync Group Members</b>\n\n"
            "This will scan the Sanctuary group and ensure everyone is tracked "
            "for requirements for the current month.\n\n"
            "_The internal sync logic will be wired into ReqStore/enforce_requirements._"
        )
        kb = _owner_home_kb() if role == "owner" else _model_home_kb()
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            pass
        await cq.answer()

    # Placeholders for model/owner actions we’ll fill in later
    @app.on_callback_query(filters.regex(r"^reqpanel:list_unmet$"))
    async def reqpanel_list_unmet(client: Client, cq: CallbackQuery):
        await cq.answer("Coming soon: unmet list here 💋", show_alert=True)

    @app.on_callback_query(filters.regex(r"^reqpanel:find_prompt$"))
    async def reqpanel_find_prompt(client: Client, cq: CallbackQuery):
        await cq.answer("Coming soon: search & member card UI 💋", show_alert=True)

    # Owner-only dangerous buttons – stubbed for now
    @app.on_callback_query(filters.regex(r"^reqpanel:(sweep|purge_confirm|remind_mid|remind_3d)$"))
    async def reqpanel_owner_only(client: Client, cq: CallbackQuery):
        if _role(cq.from_user.id if cq.from_user else 0) != "owner":
            await cq.answer("Owner only.", show_alert=True)
            return
        await cq.answer("Owner tools will hook into enforce_requirements.py 💋", show_alert=True)
