# handlers/contact_admins.py
from __future__ import annotations
import os
from typing import Optional, List

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

CONTACT_TEXT = os.getenv("CONTACT_ADMINS_TEXT", "").strip() or "How would you like to reach us?"

def _to_user_link(username_env: str, id_env: str) -> Optional[str]:
    uname = os.getenv(username_env, "").strip().lstrip("@")
    uid   = os.getenv(id_env, "").strip()
    if uname:
        return f"https://t.me/{uname}"
    if uid.isdigit():
        return f"tg://user?id={uid}"
    return None

def _dm_button(label: str, link: Optional[str], missing_cb: str) -> InlineKeyboardButton:
    # Always show the button. If link is present, make it a URL; else a toast callback.
    if link:
        return InlineKeyboardButton(label + " ↗", url=link)
    return InlineKeyboardButton(label, callback_data=missing_cb)

def build_admins_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []

    # Roni & Ruby always visible
    roni = _to_user_link("RONI_USERNAME", "RONI_ID")
    ruby = _to_user_link("RUBY_USERNAME", "RUBY_ID")
    rows.append([
        _dm_button("💌 Message Roni", roni, "admins:missing:roni"),
        _dm_button("💌 Message Ruby", ruby, "admins:missing:ruby"),
    ])

    # You can add more admin contacts in pairs the same way ↑

    rows.append([InlineKeyboardButton("🙈 Send anonymous message to admins", callback_data="admins:anon")])
    rows.append([InlineKeyboardButton("💡 Send a suggestion", callback_data="admins:suggest")])
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_home")])

    return InlineKeyboardMarkup(rows)

def register(app: Client):

    @app.on_callback_query(filters.regex(r"^dmf_open_admins$"))
    async def open_admins(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(CONTACT_TEXT, reply_markup=build_admins_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^admins:missing:(?P<who>roni|ruby)$"))
    async def missing_link(client: Client, cq: CallbackQuery):
        who = cq.matches[0].group("who")
        env_user = "RONI_USERNAME" if who == "roni" else "RUBY_USERNAME"
        env_id   = "RONI_ID"       if who == "roni" else "RUBY_ID"
        await cq.answer(
            f"Set a contact for {who.title()}.\n"
            f"Env options:\n• {env_user} (username w/o @)\n• {env_id} (numeric ID)",
            show_alert=True
        )

    @app.on_callback_query(filters.regex(r"^admins:anon$"))
    async def anon_msg(client: Client, cq: CallbackQuery):
        await cq.answer("Anon inbox coming soon. An admin will enable this.", show_alert=True)

    @app.on_callback_query(filters.regex(r"^admins:suggest$"))
    async def suggest_msg(client: Client, cq: CallbackQuery):
        await cq.answer("Suggestion box coming soon. Thanks for the idea!", show_alert=True)
