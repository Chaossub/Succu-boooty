# handlers/dm_foolproof.py
# DM entry & portal with safe /start and exported builders.

import os, time
from typing import Optional, List
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)

# ---------- UI builders that other modules reuse ----------
def _welcome_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("💌 Contact Admins", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("🔗 Find Our Models Elsewhere", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❔ Help", callback_data="dmf_show_help")],
    ])

def _spicy_intro(name: Optional[str]) -> str:
    who = name or "there"
    return (f"🔥 Welcome to SuccuBot, {who}! 🔥\n"
            "I’m your little helper inside the Sanctuary — keeping things fun, flirty, and flowing.\n\n"
            "Tap a button below to begin 👇")

# ---------- helpers ----------
def _start_payload(m: Message) -> str:
    # /start <payload> (Telegram sends deep-link as the argument)
    txt = (m.text or "") if m.text else (m.caption or "")
    parts = txt.strip().split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""

# Optional: text pulled from env for your models links
MODELS_LINKS_TEXT = os.getenv("MODELS_LINKS_TEXT") or (
    "🔥 Find Our Models Elsewhere 🔥\n\n"
    "👑 Roni Jane (Owner)\nhttps://allmylinks.com/chaossub283\n\n"
    "💎 Ruby Ransom (Co-Owner)\nhttps://allmylinks.com/rubyransoms\n\n"
    "🍑 Peachy Rin\nhttps://allmylinks.com/peachybunsrin\n\n"
    "⚡ Savage Savy\nhttps://allmylinks.com/savannahxsavage\n"
)

def register(app: Client):

    # ---------- /start (works with /start and /start <payload>) ----------
    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        # Read deep-link payload, but don’t crash if weird
        payload = ""
        try:
            payload = _start_payload(m)
        except Exception:
            payload = ""

        # You can branch on payload if you want:
        # if payload == "ready": ...
        name = m.from_user.first_name if m.from_user else None
        await m.reply_text(_spicy_intro(name), reply_markup=_welcome_kb())

    # ---------- Portal buttons ----------
    @app.on_callback_query(filters.regex(r"^dmf_back_welcome$"))
    async def cb_back(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(_spicy_intro(cq.from_user.first_name if cq.from_user else None),
                                       reply_markup=_welcome_kb())
        except Exception:
            await cq.message.reply_text(_spicy_intro(cq.from_user.first_name if cq.from_user else None),
                                        reply_markup=_welcome_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def cb_open_menu(client: Client, cq: CallbackQuery):
        # Reuse handlers.menu, but fail soft
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("💕 <b>Model Menus</b>\n(Temporarily unavailable)", disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_open_direct$"))
    async def cb_contact(client: Client, cq: CallbackQuery):
        rows = []
        if OWNER_ID:
            rows.append([InlineKeyboardButton("💌 Message Roni", url=f"tg://user?id={OWNER_ID}")])
        rows.append([InlineKeyboardButton("🙈 Send anonymous message to the admins", callback_data="dmf_anon_admins")])
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")])
        await cq.message.edit_text("How would you like to reach us?", reply_markup=InlineKeyboardMarkup(rows))
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_models_links$"))
    async def cb_links(client: Client, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")]])
        try:
            await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=kb, disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=kb, disable_web_page_preview=False)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^dmf_show_help$"))
    async def cb_help(client: Client, cq: CallbackQuery):
        # Defer to role-aware help (handlers.help_menu) if present
        try:
            from handlers.help_menu import _help_root_kb  # type: ignore
            uid = cq.from_user.id if cq.from_user else None
            is_admin = False
            try:
                from handlers.help_menu import ADMIN_IDS  # type: ignore
                is_admin = bool(uid and uid in ADMIN_IDS)
            except Exception:
                pass
            await cq.message.edit_text("❓ <b>Help</b>\nPick a topic:",
                                       reply_markup=_help_root_kb(is_admin),
                                       disable_web_page_preview=True)
        except Exception:
            # Fallback minimal help
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")]])
            await cq.message.edit_text("Help is temporarily unavailable. Try again shortly.", reply_markup=kb)
        await cq.answer()
