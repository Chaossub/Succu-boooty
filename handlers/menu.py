# handlers/menu.py
# Menu tree exactly as requested. Admin intake goes to OWNER_ID DMs.

from os import getenv
from typing import Dict, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, Message, ForceReply
)

# ---------- ENV ----------
FIND_ELSEWHERE_URL      = getenv("FIND_ELSEWHERE_URL", "https://example.com/models")
BUYER_RULES_URL         = getenv("BUYER_RULES_URL", "https://example.com/buyer-rules")
BUYER_REQUIREMENTS_URL  = getenv("BUYER_REQUIREMENTS_URL", "https://example.com/buyer-requirements")
GAME_RULES_TEXT         = getenv("GAME_RULES_TEXT", "• Game rules go here.")
MEMBER_COMMANDS_TEXT    = getenv("MEMBER_COMMANDS_TEXT", "• Members can use: /menu, /help, /portal")

# Models (usernames WITHOUT @)
MODEL_RONI_USER = getenv("MODEL_RONI_USER", "RoniJane")
MODEL_RUBY_USER = getenv("MODEL_RUBY_USER", "Ruby")
MODEL_RIN_USER  = getenv("MODEL_RIN_USER",  "Rin")
MODEL_SAVY_USER = getenv("MODEL_SAVY_USER", "Savy")

# Admins for “Contact Admins”
ADMIN_RONI_USER = getenv("ADMIN_RONI_USER", MODEL_RONI_USER)
ADMIN_RUBY_USER = getenv("ADMIN_RUBY_USER", MODEL_RUBY_USER)

def _to_int(x: Optional[str]) -> Optional[int]:
    try:
        return int(str(x)) if x not in (None, "", "None") else None
    except Exception:
        return None

OWNER_ID = _to_int(getenv("OWNER_ID"))

# ---------- simple state for reply flows ----------
# pending[user_id] = "anon" | "sugg_anon" | "sugg_named"
_pending: Dict[int, str] = {}

# ---------- Keyboards ----------
def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Menus", callback_data="menus")],
        [InlineKeyboardButton("🔎 Find Our Models Elsewhere", url=FIND_ELSEWHERE_URL)],
        [InlineKeyboardButton("🛡️ Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🧵 Help", callback_data="help")],
    ])

def _kb_menus() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💗 Roni", callback_data="menu_roni"),
            InlineKeyboardButton("💗 Ruby", callback_data="menu_ruby"),
        ],
        [
            InlineKeyboardButton("💗 Rin", callback_data="menu_rin"),
            InlineKeyboardButton("💗 Savy", callback_data="menu_savy"),
        ],
        [InlineKeyboardButton("💬 Contact Models", callback_data="contact_models_all")],
        [InlineKeyboardButton("◀️ Back", callback_data="back_main")],
    ])

def _kb_contact_models_all() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("DM Roni", url=f"https://t.me/{MODEL_RONI_USER}")],
        [InlineKeyboardButton("DM Ruby", url=f"https://t.me/{MODEL_RUBY_USER}")],
        [InlineKeyboardButton("DM Rin",  url=f"https://t.me/{MODEL_RIN_USER}")],
        [InlineKeyboardButton("DM Savy", url=f"https://t.me/{MODEL_SAVY_USER}")],
        [InlineKeyboardButton("◀️ Back", callback_data="menus")],
    ])

def _kb_model_single(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💌 Open DMs", url=f"https://t.me/{username}")],
        [InlineKeyboardButton("◀️ Back", callback_data="menus")],
    ])

def _kb_admins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Message Roni", url=f"https://t.me/{ADMIN_RONI_USER}")],
        [InlineKeyboardButton("👑 Message Ruby", url=f"https://t.me/{ADMIN_RUBY_USER}")],
        [InlineKeyboardButton("🙈 Send Anonymous Message", callback_data="anon")],
        [InlineKeyboardButton("💡 Suggestion (Anon)", callback_data="sugg_anon")],
        [InlineKeyboardButton("💡 Suggestion (With Name)", callback_data="sugg_named")],
        [InlineKeyboardButton("◀️ Back", callback_data="back_main")],
    ])

def _kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("‼️ Buyer Rules", url=BUYER_RULES_URL)],
        [InlineKeyboardButton("✨ Buyer Requirements", url=BUYER_REQUIREMENTS_URL)],
        [InlineKeyboardButton("❓ Member Commands", callback_data="help_cmds")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="help_game")],
        [InlineKeyboardButton("◀️ Back", callback_data="back_main")],
    ])

def _kb_help_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="help")]])

# ---------- Public: show Main Menu ----------
async def send_main_menu(app: Client, chat_id: int):
    await app.send_message(chat_id, "Main Menu", reply_markup=_kb_main())

# ---------- Register handlers ----------
def register(app: Client):

    # Nav: Main <-> submenus
    @app.on_callback_query(filters.regex("^back_main$"))
    async def _back_main(_, q: CallbackQuery):
        await q.message.edit_text("Main Menu", reply_markup=_kb_main())
        await q.answer()

    @app.on_callback_query(filters.regex("^menus$"))
    async def _menus(_, q: CallbackQuery):
        await q.message.edit_text("Menus", reply_markup=_kb_menus())
        await q.answer()

    @app.on_callback_query(filters.regex("^admins$"))
    async def _admins(_, q: CallbackQuery):
        await q.message.edit_text("Contact Admins", reply_markup=_kb_admins())
        await q.answer()

    @app.on_callback_query(filters.regex("^help$"))
    async def _help(_, q: CallbackQuery):
        await q.message.edit_text("Help", reply_markup=_kb_help())
        await q.answer()

    # Menus -> each model submenu
    @app.on_callback_query(filters.regex("^menu_roni$"))
    async def _menu_roni(_, q: CallbackQuery):
        await q.message.edit_text("Roni", reply_markup=_kb_model_single(MODEL_RONI_USER))
        await q.answer()

    @app.on_callback_query(filters.regex("^menu_ruby$"))
    async def _menu_ruby(_, q: CallbackQuery):
        await q.message.edit_text("Ruby", reply_markup=_kb_model_single(MODEL_RUBY_USER))
        await q.answer()

    @app.on_callback_query(filters.regex("^menu_rin$"))
    async def _menu_rin(_, q: CallbackQuery):
        await q.message.edit_text("Rin", reply_markup=_kb_model_single(MODEL_RIN_USER))
        await q.answer()

    @app.on_callback_query(filters.regex("^menu_savy$"))
    async def _menu_savy(_, q: CallbackQuery):
        await q.message.edit_text("Savy", reply_markup=_kb_model_single(MODEL_SAVY_USER))
        await q.answer()

    # Menus -> Contact Models (all names → DMs)
    @app.on_callback_query(filters.regex("^contact_models_all$"))
    async def _contact_models_all(_, q: CallbackQuery):
        await q.message.edit_text("Contact Models", reply_markup=_kb_contact_models_all())
        await q.answer()

    # Help leaves
    @app.on_callback_query(filters.regex("^help_cmds$"))
    async def _help_cmds(_, q: CallbackQuery):
        await q.message.edit_text(MEMBER_COMMANDS_TEXT, reply_markup=_kb_help_back(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex("^help_game$"))
    async def _help_game(_, q: CallbackQuery):
        await q.message.edit_text(GAME_RULES_TEXT, reply_markup=_kb_help_back(), disable_web_page_preview=True)
        await q.answer()

    # -------- Anonymous / Suggestions intake --------
    async def _start_intake(q: CallbackQuery, kind: str, prompt: str):
        u = q.from_user
        if not u:
            await q.answer("Cannot start input.", show_alert=True)
            return
        _pending[u.id] = kind
        await q.message.reply_text(prompt, reply_markup=ForceReply(selective=True))
        await q.answer()

    @app.on_callback_query(filters.regex("^anon$"))
    async def _anon(_, q: CallbackQuery):
        await _start_intake(q, "anon", "Send your anonymous message for admins:")

    @app.on_callback_query(filters.regex("^sugg_anon$"))
    async def _sugg_anon(_, q: CallbackQuery):
        await _start_intake(q, "sugg_anon", "Send your suggestion (anonymous):")

    @app.on_callback_query(filters.regex("^sugg_named$"))
    async def _sugg_named(_, q: CallbackQuery):
        await _start_intake(q, "sugg_named", "Send your suggestion (your @ will be included):")

    @app.on_message(filters.private & filters.reply & filters.text)
    async def _capture(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else None
        if not uid or uid not in _pending:
            return
        kind = _pending.pop(uid)

        if not OWNER_ID:
            await m.reply_text("Thanks! (Note: OWNER_ID not set, so I can’t DM the owner.)")
            return

        tag = {"anon": "Anonymous Message", "sugg_anon": "Suggestion (Anon)", "sugg_named": "Suggestion (Named)"}[kind]
        who = "anonymous"
        if kind == "sugg_named" and m.from_user:
            if m.from_user.username:
                who = f"@{m.from_user.username}"
            else:
                who = f"{m.from_user.first_name or 'User'} ({m.from_user.id})"

        text = m.text or ""
        header = f"📩 {tag}\nFrom: {who}\n\n"
        await client.send_message(OWNER_ID, header + text)
        await m.reply_text("Got it! I DM’d the admins. ✅")
