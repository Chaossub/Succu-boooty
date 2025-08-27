# handlers/contact_admins.py
from __future__ import annotations
import os
from typing import Optional, List

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

# Panel title (override with CONTACT_ADMINS_TEXT in env)
CONTACT_TEXT = os.getenv("CONTACT_ADMINS_TEXT", "").strip() or "How would you like to reach us?"

# ── Helpers ──────────────────────────────────────────────────────────────────
def _make_link(username_env: str, id_env: str) -> Optional[str]:
    """Return https://t.me/username or tg://user?id=ID from env; None if missing."""
    uname = os.getenv(username_env, "").strip().lstrip("@")
    uid   = os.getenv(id_env, "").strip()
    if uname:
        return f"https://t.me/{uname}"
    if uid.isdigit():
        return f"tg://user?id={uid}"
    return None

def _dm_btn(label: str, link: Optional[str], missing_cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label + (" ↗" if link else ""), url=link) if link \
        else InlineKeyboardButton(label, callback_data=missing_cb)

def _kb_admins() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []

    # Always show Roni & Ruby (even if link missing -> shows toast with env to set)
    roni_link = _make_link("RONI_USERNAME", "RONI_ID")
    ruby_link = _make_link("RUBY_USERNAME", "RUBY_ID")
    rows.append([
        _dm_btn("💌 Message Roni", roni_link, "admins:missing:roni"),
        _dm_btn("💌 Message Ruby", ruby_link, "admins:missing:ruby"),
    ])

    # Optional: add more owners/admins here in pairs if desired
    # savy_link = _make_link("SAVY_USERNAME", "SAVY_ID")
    # rin_link  = _make_link("RIN_USERNAME",  "RIN_ID")
    # rows.append([
    #     _dm_btn("💌 Message Savy", savy_link, "admins:missing:savy"),
    #     _dm_btn("💌 Message Rin",  rin_link,  "admins:missing:rin"),
    # ])

    rows.append([InlineKeyboardButton("🙈 Send anonymous message to admins", callback_data="admins:anon")])
    rows.append([InlineKeyboardButton("💡 Send a suggestion", callback_data="admins:suggest")])
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_home")])
    return InlineKeyboardMarkup(rows)

# ── Register only callback handlers (NO /start here) ─────────────────────────
def register(app: Client):

    # Open Contact Admins (edit in place)
    @app.on_callback_query(filters.regex(r"^dmf_open_admins$"))
    async def open_admins(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(CONTACT_TEXT, reply_markup=_kb_admins(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    # Missing link toast
    @app.on_callback_query(filters.regex(r"^admins:missing:(?P<who>[a-zA-Z0-9_]+)$"))
    async def missing_link(client: Client, cq: CallbackQuery):
        who = cq.matches[0].group("who").upper()
        await cq.answer(
            f"Set contact for {who.title()}:\n"
            f"• {who}_USERNAME (without @)  or\n"
            f"• {who}_ID (numeric Telegram user ID)",
            show_alert=True
        )

    # Placeholder actions
    @app.on_callback_query(filters.regex(r"^admins:anon$"))
    async def anon_msg(client: Client, cq: CallbackQuery):
        await cq.answer("Anon inbox coming soon. An admin will enable this.", show_alert=True)

    @app.on_callback_query(filters.regex(r"^admins:suggest$"))
    async def suggest_msg(client: Client, cq: CallbackQuery):
        await cq.answer("Suggestion box coming soon. Thanks for the idea!", show_alert=True)
