# handlers/panels.py
# One consolidated UI router so buttons edit-in-place (no duplicates).
# Panels covered:
# - Main
# - Menus (reads menus.json written by /createmenu; falls back to ENV text)
# - Contact Admins (Roni, Ruby, Suggestions, Anonymous Message to Owner)
# - Help (Buyer Rules, Buyer Requirements, Game Rules, Exemptions)
# - Find Our Models Elsewhere
#
# Used by dm_foolproof.py via callback_data starting with "panel:" or section-specific prefixes.

import os
import json
from pathlib import Path
from typing import Dict, Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.enums import ChatType

# ---------- Config / ENV ----------
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

RONI_ID   = os.getenv("RONI_ID")
RUBY_ID   = os.getenv("RUBY_ID")
RIN_ID    = os.getenv("RIN_ID")
SAVY_ID   = os.getenv("SAVY_ID")

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME", "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

# "Find Our Models Elsewhere" text
ELSEWHERE_TEXT = os.getenv("FIND_MODELS_TEXT", "All verified off-platform links for our models are collected here. Check pinned messages or official posts for updates.")

# Help section texts
HELP_RULES_TEXT        = os.getenv("RULES_TEXT", "House rules will appear here.")
HELP_BUYER_REQS_TEXT   = os.getenv("BUYER_REQUIREMENTS_TEXT", "Buyer requirements here.")
HELP_GAME_RULES_TEXT   = os.getenv("GAME_RULES_TEXT", "Game rules here.")
HELP_EXEMPTIONS_TEXT   = os.getenv("EXEMPTIONS_TEXT", "Exemptions info here.")

# File where /createmenu writes menus
MENUS_FILE = Path(os.getenv("MENUS_FILE", "menus.json"))

# ---------- Helpers ----------
def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _back_main() -> list:
    return [ [_btn("⬅️ Back to Main", "panel:home")] ]

def _main_kb() -> InlineKeyboardMarkup:
    rows = [
        [_btn("💕 Menu", "panel:menu")],
        [_btn("👑 Contact Admins", "panel:contact")],
        [_btn("🔥 Find Our Models Elsewhere", "panel:elsewhere")],
        [_btn("❓ Help", "panel:help")],
    ]
    return InlineKeyboardMarkup(rows)

def _read_menus() -> Dict[str, str]:
    """
    Returns a dict of menus keyed by model key: roni, ruby, rin, savy.
    Source of truth is menus.json written by /createmenu.
    Falls back to ENV MODEL_MENU text if missing.
    """
    data = {}
    if MENUS_FILE.exists():
        try:
            data = json.loads(MENUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    # Normalize keys and merge with ENV fallbacks
    env_fallbacks = {
        "roni": os.getenv("RONI_MENU", ""),
        "ruby": os.getenv("RUBY_MENU", ""),
        "rin":  os.getenv("RIN_MENU", ""),
        "savy": os.getenv("SAVY_MENU", ""),
    }
    # Support older format where we stored by user ID
    id_map = {
        (RONI_ID or "").strip(): "roni",
        (RUBY_ID or "").strip(): "ruby",
        (RIN_ID or "").strip(): "rin",
        (SAVY_ID or "").strip(): "savy",
    }
    normalized: Dict[str, str] = {}

    for k, v in (data or {}).items():
        key = k.lower().strip()
        if key in ("roni", "ruby", "rin", "savy"):
            normalized[key] = v
        elif k in id_map and id_map[k]:
            normalized[id_map[k]] = v

    # Apply fallbacks if still missing
    for k, v in env_fallbacks.items():
        if k not in normalized and v:
            normalized[k] = v

    return normalized

def _menu_names() -> Dict[str, str]:
    return {
        "roni": RONI_NAME or "Roni",
        "ruby": RUBY_NAME or "Ruby",
        "rin":  RIN_NAME  or "Rin",
        "savy": SAVY_NAME or "Savy",
    }

# ---------- Panel Renderers (always EDIT the same message) ----------
async def render_main(msg: Message):
    text = (
        "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
        "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
        "✨ <i>Use the menu below to navigate!</i>"
    )
    try:
        await msg.edit_text(text, reply_markup=_main_kb(), disable_web_page_preview=True)
    except Exception:
        # If the message is not editable (e.g., very old), send a new one with the same keyboard
        await msg.reply_text(text, reply_markup=_main_kb(), disable_web_page_preview=True)

async def render_elsewhere(msg: Message):
    kb = InlineKeyboardMarkup(_back_main())
    await msg.edit_text(f"✨ <b>Find Our Models Elsewhere</b> ✨\n\n{ELSEWHERE_TEXT}", reply_markup=kb, disable_web_page_preview=True)

async def render_help_home(msg: Message):
    rows = [
        [
            _btn("‼️ Buyer Rules", "help:rules"),
            _btn("✨ Buyer Requirements", "help:reqs")
        ],
        [
            _btn("🎮 Game Rules", "help:games"),
            _btn("🧩 Exemptions", "help:exempt")
        ],
        *_back_main()
    ]
    kb = InlineKeyboardMarkup(rows)
    await msg.edit_text("❓ <b>Help</b>\n\nPick a topic below.", reply_markup=kb)

async def render_help_detail(msg: Message, which: str):
    mapping = {
        "rules": ("‼️ Buyer Rules", HELP_RULES_TEXT),
        "reqs":  ("✨ Buyer Requirements", HELP_BUYER_REQS_TEXT),
        "games": ("🎮 Game Rules", HELP_GAME_RULES_TEXT),
        "exempt":("🧩 Exemptions", HELP_EXEMPTIONS_TEXT),
    }
    title, body = mapping.get(which, ("Help", "…"))
    rows = [[_btn("⬅️ Back to Help", "panel:help")], *_back_main()]
    await msg.edit_text(f"<b>{title}</b>\n\n{body}", reply_markup=InlineKeyboardMarkup(rows))

async def render_contact(msg: Message, me_username: Optional[str]):
    rows = []
    if RONI_ID:
        rows.append([InlineKeyboardButton(f"💌 Contact {RONI_NAME}", url=f"https://t.me/{RONI_NAME.replace(' ','')}")])
    if RUBY_ID:
        rows.append([InlineKeyboardButton(f"💌 Contact {RUBY_NAME}", url=f"https://t.me/{RUBY_NAME.replace(' ','')}")])

    rows.append([_btn("💡 Suggestions (type in chat)", "contact:suggest")])
    rows.append([_btn("🕵️ Anonymous message to Owner", "contact:anon")])
    rows += _back_main()

    kb = InlineKeyboardMarkup(rows)
    await msg.edit_text(
        "👑 <b>Contact Admins</b>\n\n"
        "• Tag an admin in chat\n"
        "• Or send an anonymous message via the bot.\n",
        reply_markup=kb
    )

# In-memory state for anon flow; lightweight and fine for this feature.
_waiting_anon: set[int] = set()

async def render_menu_home(msg: Message):
    names = _menu_names()
    rows = [
        [_btn(f"💞 {names['roni']}", "menu:show:roni"), _btn(f"💞 {names['ruby']}", "menu:show:ruby")],
        [_btn(f"💞 {names['rin']}",  "menu:show:rin"),  _btn(f"💞 {names['savy']}", "menu:show:savy")],
        *_back_main()
    ]
    await msg.edit_text("💕 <b>Menus</b>\nPick a model whose menu is saved.", reply_markup=InlineKeyboardMarkup(rows))

async def render_menu_detail(msg: Message, key: str):
    menus = _read_menus()
    names = _menu_names()
    body = menus.get(key, f"No saved menu for {names.get(key, key.title())} yet.")
    rows = [[_btn("⬅️ Back to Menus", "panel:menu")], *_back_main()]
    await msg.edit_text(f"💕 <b>{names.get(key, key.title())} — Menu</b>\n\n{body}", reply_markup=InlineKeyboardMarkup(rows))

# ---------- Router ----------
def register(app: Client):

    # Handle all callback buttons here (keeps UI logic in one place).
    @app.on_callback_query(filters.regex(r"^(panel:|menu:|help:|contact:)"))
    async def on_panel_cb(_, cq: CallbackQuery):
        if cq.message is None:
            await cq.answer()
            return
        data = cq.data or ""
        msg = cq.message

        if data == "panel:home":
            await cq.answer()
            await render_main(msg)

        elif data == "panel:menu":
            await cq.answer()
            await render_menu_home(msg)

        elif data.startswith("menu:show:"):
            await cq.answer()
            key = data.split(":", 2)[-1]
            await render_menu_detail(msg, key)

        elif data == "panel:elsewhere":
            await cq.answer()
            await render_elsewhere(msg)

        elif data == "panel:help":
            await cq.answer()
            await render_help_home(msg)

        elif data.startswith("help:"):
            await cq.answer()
            which = data.split(":", 1)[-1]
            await render_help_detail(msg, which)

        elif data == "panel:contact":
            me = await app.get_me()
            await cq.answer()
            await render_contact(msg, me.username)

        elif data == "contact:suggest":
            await cq.answer("Type your suggestion in chat and tag an admin. ❤️", show_alert=False)

        elif data == "contact:anon":
            user_id = cq.from_user.id if cq.from_user else None
            if user_id:
                _waiting_anon.add(user_id)
            await cq.answer()
            rows = [[_btn("⬅️ Back to Contact", "panel:contact")], *_back_main()]
            await msg.edit_text(
                "🕵️ <b>Anonymous Message</b>\n\n"
                "Send me the text you want to deliver privately to the owner.\n"
                "<i>(Your Telegram account won’t be shown in the message I forward.)</i>",
                reply_markup=InlineKeyboardMarkup(rows)
            )

    # Collect the next message for anonymous flow (private only).
    @app.on_message(filters.private & ~filters.command(["start"]))
    async def on_private_text(client: Client, m: Message):
        if m.from_user and m.from_user.id in _waiting_anon:
            _waiting_anon.discard(m.from_user.id)
            txt = (m.text or "").strip()
            if not txt:
                await m.reply_text("Please send text for the anonymous message. Try again: Menu → Contact Admins → Anonymous.")
                return
            # Forward as plain text to owner (no forward header).
            safe_name = m.from_user.first_name or "Someone"
            note = f"🕵️ <b>Anonymous message</b>\n\n{txt}"
            try:
                if OWNER_ID:
                    await client.send_message(int(OWNER_ID), note, disable_web_page_preview=True)
                await m.reply_text("✅ Sent anonymously to the owner.", reply_markup=_main_kb())
            except Exception:
                await m.reply_text("⚠️ Couldn't deliver the message to the owner right now.", reply_markup=_main_kb())

    # Convenience: Let /menu (in private) open the Menus panel by EDITING the last bot message, or sending new if none.
    @app.on_message(filters.private & filters.command("menu"))
    async def open_menu_shortcut(_, m: Message):
        # try to reply to last bot message; if none, just send a fresh main and then menus via edit
        try:
            sent = await m.reply_text("Opening menus…")
            await render_menu_home(sent)
        except Exception:
            pass
