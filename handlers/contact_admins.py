# handlers/contact_admins.py
from __future__ import annotations
import os
from typing import List, Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

# ---- Helpers to build links from env (username or numeric id) ----------------
def _to_user_link(username_env: str, id_env: str) -> Optional[str]:
    uname = os.getenv(username_env, "").strip().lstrip("@")
    uid   = os.getenv(id_env, "").strip()
    if uname:
        return f"https://t.me/{uname}"
    if uid.isdigit():
        return f"tg://user?id={uid}"
    return None

def _maybe_btn(text: str, username_env: str, id_env: str):
    url = _to_user_link(username_env, id_env)
    if url:
        return InlineKeyboardButton(text, url=url)
    return None

# ---- Panel text (you can override with CONTACT_ADMINS_TEXT in env) -----------
CONTACT_TEXT = os.getenv("CONTACT_ADMINS_TEXT", "").strip() or "How would you like to reach us?"

def build_admins_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []

    # Direct DM buttons (Roni / Ruby). Add more if you want.
    roni_btn = _maybe_btn("💌 Message Roni ↗", "RONI_USERNAME", "RONI_ID")
    ruby_btn = _maybe_btn("💌 Message Ruby ↗", "RUBY_USERNAME", "RUBY_ID")
    if roni_btn or ruby_btn:
        pair = [b for b in (roni_btn, ruby_btn) if b]
        rows.append(pair)

    # Anonymous & suggestion (callbacks you already handle elsewhere or simple notes)
    rows.append([InlineKeyboardButton("🙈 Send anonymous message to admins", callback_data="admins:anon")])
    rows.append([InlineKeyboardButton("💡 Send a suggestion", callback_data="admins:suggest")])

    # Back to Start
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_home")])

    return InlineKeyboardMarkup(rows)

def register(app: Client):

    # Open Contact Admins — EDIT IN PLACE (no reply_text)
    @app.on_callback_query(filters.regex(r"^dmf_open_admins$"))
    async def open_admins(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(CONTACT_TEXT, reply_markup=build_admins_kb(), disable_web_page_preview=True)
        except MessageNotModified:
            pass
        await cq.answer()

    # Optional: simple toasts for anon/suggest until you wire full flows
    @app.on_callback_query(filters.regex(r"^admins:anon$"))
    async def anon_msg(client: Client, cq: CallbackQuery):
        await cq.answer("Anon inbox coming soon. An admin will enable this.", show_alert=True)

    @app.on_callback_query(filters.regex(r"^admins:suggest$"))
    async def suggest_msg(client: Client, cq: CallbackQuery):
        await cq.answer("Suggestion box coming soon. Thanks for the idea!", show_alert=True)
