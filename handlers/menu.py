from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# ── Single source of truth for models (RONI FIRST; she will appear everywhere)
MODELS = [
    {"key": "roni", "display": "Roni", "emoji": "💘", "username": os.getenv("RONI_USERNAME", "")},
    {"key": "ruby", "display": "Ruby", "emoji": "💘", "username": os.getenv("RUBY_USERNAME", "")},
    {"key": "rin",  "display": "Rin",  "emoji": "💘", "username": os.getenv("RIN_USERNAME", "")},
    {"key": "savy", "display": "Savy", "emoji": "💘", "username": os.getenv("SAVY_USERNAME", "")},
]

def _model_menu_text(key: str, display: str) -> str:
    return os.getenv(f"{key.upper()}_MENU_TEXT") or f"💋 **{display}’s Menu**\nPick your poison, lover…"

FIND_ELSEWHERE_TEXT = os.getenv("FIND_MODELS_ELSEWHERE_TEXT") or "Links coming soon."
BUYER_RULES_TEXT = os.getenv("BUYER_RULES_TEXT") or "No buyer rules set."
BUYER_REQS_TEXT = os.getenv("BUYER_REQUIREMENTS_TEXT") or "No buyer requirements set."
GAME_RULES_TEXT = os.getenv("GAME_RULES_TEXT") or "No game rules set."

ADMIN_RONI = os.getenv("ADMIN_RONI_USERNAME", os.getenv("RONI_USERNAME", ""))
ADMIN_RUBY = os.getenv("ADMIN_RUBY_USERNAME", os.getenv("RUBY_USERNAME", ""))

WELCOME_CARD = (
    "🔥 **Welcome to SuccuBot** 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ *Use the menu below to navigate!*"
)

CB_MAIN = "main"
CB_MENUS = "menus"
CB_CONTACT_MODELS = "contact_models"
CB_CONTACT_ADMINS = "contact_admins"
CB_FIND_ELSEWHERE = "find_elsewhere"
CB_HELP = "help"

def cb_model(k: str) -> str: return f"model_{k}"
def cb_tip(k: str) -> str:   return f"tip_{k}"

# ── Keyboards
def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data=CB_MENUS)],
        [InlineKeyboardButton("👑 Contact Admins", callback_data=CB_CONTACT_ADMINS)],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data=CB_FIND_ELSEWHERE)],
        [InlineKeyboardButton("❓ Help", callback_data=CB_HELP)],
    ])

def _kb_menus() -> InlineKeyboardMarkup:
    grid = []
    row = []
    for m in MODELS:
        row.append(InlineKeyboardButton(f"{m['emoji']} {m['display']}", callback_data=cb_model(m["key"])))
        if len(row) == 2:
            grid.append(row); row = []
    if row: grid.append(row)
    grid.append([InlineKeyboardButton("💞 Contact Models", callback_data=CB_CONTACT_MODELS)])
    grid.append([InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)])
    return InlineKeyboardMarkup(grid)

def _kb_contact_models() -> InlineKeyboardMarkup:
    grid = []
    row = []
    for m in MODELS:
        url = f"https://t.me/{m['username'].lstrip('@')}" if m["username"] else "https://t.me/"
        row.append(InlineKeyboardButton(f"{m['emoji']} {m['display']} ↗", url=url))
        if len(row) == 2:
            grid.append(row); row = []
    if row: grid.append(row)
    grid.append([InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)])
    return InlineKeyboardMarkup(grid)

def _kb_model_menu(key: str) -> InlineKeyboardMarkup:
    m = next(x for x in MODELS if x["key"] == key)
    book_url = f"https://t.me/{m['username'].lstrip('@')}" if m["username"] else "https://t.me/"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Book", url=book_url)],
        [InlineKeyboardButton("💸 Tip", callback_data=cb_tip(key))],
        [InlineKeyboardButton("⬅️ Back to Menus", callback_data=CB_MENUS)],
    ])

def _kb_contact_admins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 Message Roni", url=f"https://t.me/{ADMIN_RONI.lstrip('@')}") if ADMIN_RONI else InlineKeyboardButton("👑 Message Roni", url="https://t.me/"),
            InlineKeyboardButton("👑 Message Ruby", url=f"https://t.me/{ADMIN_RUBY.lstrip('@')}") if ADMIN_RUBY else InlineKeyboardButton("👑 Message Ruby", url="https://t.me/"),
        ],
        [InlineKeyboardButton("🕵️ Anonymous Message", callback_data="anon_msg"),
         InlineKeyboardButton("💡 Suggestion Box", callback_data="suggestion")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)],
    ])

def _kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help_rules")],
        [InlineKeyboardButton("✅ Buyer Requirements", callback_data="help_requirements")],
        [InlineKeyboardButton("🕹️ Game Rules", callback_data="help_games")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)],
    ])

# ── Render helpers (edit in place; no extra sends)
async def _show_main(target: Message | CallbackQuery):
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(WELCOME_CARD, reply_markup=_kb_main(), disable_web_page_preview=True)
        except Exception:
            pass
        await target.answer()
    else:
        await target.reply_text(WELCOME_CARD, reply_markup=_kb_main(), disable_web_page_preview=True)

async def _show_menus(q: CallbackQuery):
    await q.message.edit_text("💕 **Menus**", reply_markup=_kb_menus(), disable_web_page_preview=True); await q.answer()

async def _show_contact_models(q: CallbackQuery):
    await q.message.edit_text("Contact a model directly:", reply_markup=_kb_contact_models(), disable_web_page_preview=True); await q.answer()

async def _show_contact_admins(q: CallbackQuery):
    await q.message.edit_text("Contact Admins:", reply_markup=_kb_contact_admins(), disable_web_page_preview=True); await q.answer()

async def _show_find_elsewhere(q: CallbackQuery):
    await q.message.edit_text(FIND_ELSEWHERE_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)]]), disable_web_page_preview=True); await q.answer()

async def _show_help(q: CallbackQuery):
    await q.message.edit_text("❓ Help", reply_markup=_kb_help(), disable_web_page_preview=True); await q.answer()

async def _show_model_menu(q: CallbackQuery, key: str):
    m = next(x for x in MODELS if x["key"] == key)
    await q.message.edit_text(_model_menu_text(key, m["display"]), reply_markup=_kb_model_menu(key), disable_web_page_preview=True); await q.answer()

# ── Register once
def register(app: Client):

    @app.on_message(filters.private & filters.command(["start", "portal"]))
    async def _start(_, m: Message):
        await _show_main(m)

    @app.on_callback_query(filters.regex(f"^{CB_MAIN}$"))
    async def _cb_main(_, q: CallbackQuery): await _show_main(q)

    @app.on_callback_query(filters.regex(f"^{CB_MENUS}$"))
    async def _cb_menus(_, q: CallbackQuery): await _show_menus(q)

    @app.on_callback_query(filters.regex(f"^{CB_CONTACT_MODELS}$"))
    async def _cb_contact_models(_, q: CallbackQuery): await _show_contact_models(q)

    @app.on_callback_query(filters.regex(f"^{CB_CONTACT_ADMINS}$"))
    async def _cb_contact_admins(_, q: CallbackQuery): await _show_contact_admins(q)

    @app.on_callback_query(filters.regex(f"^{CB_FIND_ELSEWHERE}$"))
    async def _cb_elsewhere(_, q: CallbackQuery): await _show_find_elsewhere(q)

    @app.on_callback_query(filters.regex(f"^{CB_HELP}$"))
    async def _cb_help(_, q: CallbackQuery): await _show_help(q)

    @app.on_callback_query(filters.regex(r"^help_rules$"))
    async def _cb_help_rules(_, q: CallbackQuery):
        await q.message.edit_text(BUYER_RULES_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)]]), disable_web_page_preview=True); await q.answer()

    @app.on_callback_query(filters.regex(r"^help_requirements$"))
    async def _cb_help_reqs(_, q: CallbackQuery):
        await q.message.edit_text(BUYER_REQS_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)]]), disable_web_page_preview=True); await q.answer()

    @app.on_callback_query(filters.regex(r"^help_games$"))
    async def _cb_help_games(_, q: CallbackQuery):
        await q.message.edit_text(GAME_RULES_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)]]), disable_web_page_preview=True); await q.answer()

    @app.on_callback_query(filters.regex(r"^model_(roni|ruby|rin|savy)$"))
    async def _cb_model(_, q: CallbackQuery):
        await _show_model_menu(q, q.data.split("_", 1)[1])

    @app.on_callback_query(filters.regex(r"^tip_(roni|ruby|rin|savy)$"))
    async def _cb_tip(_, q: CallbackQuery):
        await q.answer("Coming soon 💸", show_alert=False)

    # Anonymous/suggestions → DM to owner (optional)
    BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0") or "0")

    async def _ask_and_forward(q: CallbackQuery, title: str):
        await q.answer()
        await q.message.edit_text(f"{title}\n\nSend your message now. Type /cancel to stop.",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data=CB_MAIN)]]))
        user_id = q.from_user.id

        @app.on_message(filters.private & ~filters.command(["cancel"]) & filters.user(user_id), group=9999)
        async def _collector(_, m: Message):
            if BOT_OWNER_ID:
                try:
                    await app.send_message(BOT_OWNER_ID, f"📩 From @{m.from_user.username or m.from_user.id}:\n\n{m.text}")
                except Exception:
                    pass
            await _show_main(m)
            app.remove_handler(_collector, group=9999); app.remove_handler(_cancel, group=9998)

        @app.on_message(filters.private & filters.command(["cancel"]) & filters.user(user_id), group=9998)
        async def _cancel(_, m: Message):
            await _show_main(m)
            app.remove_handler(_collector, group=9999); app.remove_handler(_cancel, group=9998)

    @app.on_callback_query(filters.regex(r"^anon_msg$"))
    async def _cb_anon(_, q: CallbackQuery): await _ask_and_forward(q, "🕵️ **Anonymous Message**")

    @app.on_callback_query(filters.regex(r"^suggestion$"))
    async def _cb_suggest(_, q: CallbackQuery): await _ask_and_forward(q, "💡 **Suggestion Box**")
