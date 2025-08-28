# handlers/menu.py
# Inline menu callbacks only. NO /start handler here.

import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import RPCError

log = logging.getLogger(__name__)

# Labels (fallbacks provided)
BTN_MENUS   = os.getenv("BTN_MENUS", "💕 Menus")
BTN_ADMINS  = os.getenv("BTN_ADMINS", "👑 Contact Admins")
BTN_FIND    = os.getenv("BTN_FIND",  "🔥 Find Our Models Elsewhere")
BTN_HELP    = os.getenv("BTN_HELP",  "❓ Help")
BTN_BACK    = os.getenv("BTN_BACK",  "⬅️ Back to Main")
BTN_CM      = os.getenv("BTN_CM",    "💞 Contact Models")

# Model display names / usernames from env
MODELS = [
    ("roni", os.getenv("RONI_NAME", "Roni"), os.getenv("RONI_USERNAME")),  # username without @
    ("ruby", os.getenv("RUBY_NAME", "Ruby"), os.getenv("RUBY_USERNAME")),
    ("rin",  os.getenv("RIN_NAME",  "Rin"),  os.getenv("RIN_USERNAME")),
    ("savy", os.getenv("SAVY_NAME", "Savy"), os.getenv("SAVY_USERNAME")),
]

FIND_MODELS_TEXT = os.getenv(
    "FIND_MODELS_TEXT",
    "All verified off-platform links for our models are collected here. Check pinned messages or official posts for updates."
)
BUYER_RULES_TEXT = os.getenv("BUYER_REQ_TEXT", "Buyer requirements go here.")
RULES_TEXT       = os.getenv("RULES_TEXT", "House rules go here.")

# ---------- keyboards ----------

def kb_main() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(BTN_MENUS,  callback_data="open_menus")],
        [InlineKeyboardButton(BTN_ADMINS, callback_data="open_admins")],
        [InlineKeyboardButton(BTN_FIND,   callback_data="open_find")],
        [InlineKeyboardButton(BTN_HELP,   callback_data="open_help")],
    ]
    return InlineKeyboardMarkup(rows)

def kb_menus() -> InlineKeyboardMarkup:
    # 2x2 models grid
    grid = [
        [
            InlineKeyboardButton(f"💘 {MODELS[0][1]}", callback_data=f"model:{MODELS[0][0]}"),
            InlineKeyboardButton(f"💘 {MODELS[1][1]}", callback_data=f"model:{MODELS[1][0]}"),
        ],
        [
            InlineKeyboardButton(f"💘 {MODELS[2][1]}", callback_data=f"model:{MODELS[2][0]}"),
            InlineKeyboardButton(f"💘 {MODELS[3][1]}", callback_data=f"model:{MODELS[3][0]}"),
        ],
        [InlineKeyboardButton(BTN_CM, callback_data="open_contact_models")],
        [InlineKeyboardButton(BTN_BACK, callback_data="open_main")],
    ]
    return InlineKeyboardMarkup(grid)

def kb_model(slug: str) -> InlineKeyboardMarkup:
    _, label, username = next((m for m in MODELS if m[0] == slug), (slug, slug.title(), None))
    book_btn = InlineKeyboardButton("📖 Book", url=f"https://t.me/{username}" if username else "https://t.me")
    tip_btn  = InlineKeyboardButton("💸 Tip (Coming soon)", callback_data="noop")
    back_btn = InlineKeyboardButton("⬅️ Back to Menus", callback_data="open_menus")
    return InlineKeyboardMarkup([[book_btn], [tip_btn], [back_btn]])

def kb_contact_models() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"💘 {label} ↗", url=f"https://t.me/{username}" if username else "https://t.me")]
        for _, label, username in MODELS
    ]
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="open_main")])
    return InlineKeyboardMarkup(rows)

def kb_admins() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("👑 Message Roni",  url=f"https://t.me/{os.getenv('RONI_USERNAME','')}")],
        [InlineKeyboardButton("👑 Message Ruby",  url=f"https://t.me/{os.getenv('RUBY_USERNAME','')}")],
        [InlineKeyboardButton("🕵️ Anonymous Message", callback_data="noop")],
        [InlineKeyboardButton("💡 Suggestion Box",     callback_data="noop")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="open_main")],
    ]
    return InlineKeyboardMarkup(rows)

def kb_find_models() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="open_main")]])

def kb_help() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help:buyer")],
        [InlineKeyboardButton("✅ Buyer Requirements", callback_data="help:req")],
        [InlineKeyboardButton("🕹️ Game Rules", callback_data="help:game")],
        [InlineKeyboardButton("⬅️ Back to Main", callback_data="open_main")],
    ]
    return InlineKeyboardMarkup(rows)

# ---------- safe editor ----------

async def _safe_edit(q: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await q.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except RPCError as e:
        # Ignore MESSAGE_NOT_MODIFIED or if message is not editable
        log.debug("edit_text skipped: %s", e)

# ---------- register ----------

def register(app: Client):

    @app.on_callback_query(filters.regex("^open_main$"))
    async def _open_main(_, q: CallbackQuery):
        await _safe_edit(
            q,
            "🔥 <b>Welcome to SuccuBot</b> 🔥\nYour naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n✨ <i>Use the menu below to navigate!</i>",
            kb_main()
        )
        await q.answer()

    @app.on_callback_query(filters.regex("^open_menus$"))
    async def _open_menus(_, q: CallbackQuery):
        await _safe_edit(q, "💕 <b>Menus</b>\nPick a model or contact the team.", kb_menus())
        await q.answer()

    @app.on_callback_query(filters.regex(r"^model:(\w+)$"))
    async def _open_model(_, q: CallbackQuery):
        slug = q.data.split(":", 1)[1]
        _, label, _ = next((m for m in MODELS if m[0] == slug), (slug, slug.title(), None))
        await _safe_edit(q, f"💘 <b>{label}</b>\nSelect an option:", kb_model(slug))
        await q.answer()

    @app.on_callback_query(filters.regex("^open_contact_models$"))
    async def _open_contact_models(_, q: CallbackQuery):
        await _safe_edit(q, "💞 <b>Contact Models</b>", kb_contact_models())
        await q.answer()

    @app.on_callback_query(filters.regex("^open_admins$"))
    async def _open_admins(_, q: CallbackQuery):
        await _safe_edit(q, "👑 <b>Contact Admins</b>\nHow would you like to reach us?", kb_admins())
        await q.answer()

    @app.on_callback_query(filters.regex("^open_find$"))
    async def _open_find(_, q: CallbackQuery):
        await _safe_edit(q, f"✨ <b>Find Our Models Elsewhere</b> ✨\n\n{FIND_MODELS_TEXT}", kb_find_models())
        await q.answer()

    @app.on_callback_query(filters.regex("^open_help$"))
    async def _open_help(_, q: CallbackQuery):
        await _safe_edit(q, "❓ <b>Help</b>\nChoose an option.", kb_help())
        await q.answer()

    @app.on_callback_query(filters.regex("^help:buyer$"))
    async def _help_buyer(_, q: CallbackQuery):
        await _safe_edit(q, f"📜 <b>Buyer Rules</b>\n\n{RULES_TEXT}", kb_help())
        await q.answer()

    @app.on_callback_query(filters.regex("^help:req$"))
    async def _help_req(_, q: CallbackQuery):
        await _safe_edit(q, f"✅ <b>Buyer Requirements</b>\n\n{BUYER_RULES_TEXT}", kb_help())
        await q.answer()

    @app.on_callback_query(filters.regex("^help:game$"))
    async def _help_game(_, q: CallbackQuery):
        await _safe_edit(q, "🕹️ <b>Game Rules</b>\n\nComing soon.", kb_help())
        await q.answer()

    @app.on_callback_query(filters.regex("^noop$"))
    async def _noop(_, q: CallbackQuery):
        await q.answer("Coming soon ✨", show_alert=False)
