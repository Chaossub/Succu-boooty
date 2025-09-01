# handlers/panels.py
import os
from typing import Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified

# ========= Core Admin ENV =========
RONI_ID   = os.getenv("RONI_ID")
RUBY_ID   = os.getenv("RUBY_ID")
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RONI_UN   = os.getenv("RONI_USERNAME")   # e.g. Chaossub283 (no @)
RUBY_UN   = os.getenv("RUBY_USERNAME")

# Fallbacks so Roni NEVER disappears
OWNER_ID        = os.getenv("OWNER_ID")
OWNER_USERNAME  = os.getenv("OWNER_USERNAME")

# ========= TEXT PANELS FROM ENV (no URLs) =========
BUYER_RULES_TEXT         = os.getenv("BUYER_RULES_TEXT", "").strip()
BUYER_REQUIREMENTS_TEXT  = os.getenv("BUYER_REQUIREMENTS_TEXT", "").strip()
GAME_RULES_TEXT          = os.getenv("GAME_RULES_TEXT", "").strip()
EXEMPTIONS_TEXT          = os.getenv("EXEMPTIONS_TEXT", "").strip()
FIND_MODELS_TEXT         = os.getenv("FIND_MODELS_TEXT", "").strip()

# ========= Small helpers =========
def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _back_main() -> List[List[InlineKeyboardButton]]:
    return [[_btn("⬅️ Back to Main", "nav:main")]]

def _user_url(username: Optional[str], numeric_id: Optional[str]) -> Optional[str]:
    if username:
        return f"https://t.me/{username.lstrip('@')}"
    if numeric_id:
        return f"https://t.me/user?id={int(numeric_id)}"
    return None

async def _safe_edit(msg: Message, text: str, **kwargs):
    """
    Edit a message but swallow Telegram's 400 MESSAGE_NOT_MODIFIED if content is identical.
    This happens when users tap the same button repeatedly.
    """
    try:
        await msg.edit_text(text, **kwargs)
    except MessageNotModified:
        # Nothing changed – just ignore.
        return

# ========= Panels =========
async def render_main(msg: Message):
    rows = [
        [_btn("💕 Menu", "nav:menu")],
        [_btn("👑 Contact Admins", "nav:contact")],
        [_btn("🔥 Find Our Models Elsewhere", "nav:links")],
        [_btn("❓ Help", "nav:help")],
    ]
    kb = InlineKeyboardMarkup(rows)
    await _safe_edit(
        msg,
        "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
        "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
        "✨ <i>Use the menu below to navigate!</i>",
        reply_markup=kb,
        disable_web_page_preview=True,
    )

async def render_menu(msg: Message):
    # You can swap to your dynamic menu store if desired
    rows = [
        [_btn("💘 Roni", "menu:roni"), _btn("💘 Ruby", "menu:ruby")],
        [_btn("💘 Rin", "menu:rin"), _btn("💘 Savy", "menu:savy")],
    ] + _back_main()
    await _safe_edit(
        msg,
        "💕 <b>Menus</b>\nPick a model whose menu is saved.",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True,
    )

async def render_contact(msg: Message):
    rows: List[List[InlineKeyboardButton]] = []

    # Roni must always show: use explicit RONI_* or fallback to OWNER_*
    roni_url = _user_url(RONI_UN or OWNER_USERNAME, RONI_ID or OWNER_ID)
    ruby_url = _user_url(RUBY_UN, RUBY_ID)

    if roni_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RONI_NAME}", url=roni_url)])
    if ruby_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RUBY_NAME}", url=ruby_url)])

    rows.append([_btn("🕵️ Anonymous Message", "contact:anon")])
    rows += _back_main()

    await _safe_edit(
        msg,
        "👑 <b>Contact Admins</b>\n\n• Tag an admin in chat\n• Or send an anonymous message via the bot.",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True,
    )

# ----- HELP HUB (text buttons → text panels, not URLs)
async def render_help(msg: Message):
    rows = [
        [_btn("📜 Buyer Rules", "help:rules")],
        [_btn("✅ Buyer Requirements", "help:reqs")],
        [_btn("🎲 Game Rules", "help:games")],
        [_btn("🕊️ Exemptions", "help:exempt")],
    ] + _back_main()
    await _safe_edit(
        msg,
        "❓ <b>Help</b>\nChoose a section:",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True,
    )

async def render_help_rules(msg: Message):
    text = BUYER_RULES_TEXT or "No Buyer Rules configured yet."
    await _safe_edit(
        msg,
        text,
        reply_markup=InlineKeyboardMarkup([[ _btn("⬅️ Back to Help", "nav:help") ]]),
        disable_web_page_preview=False,
    )

async def render_help_requirements(msg: Message):
    text = BUYER_REQUIREMENTS_TEXT or "No Buyer Requirements configured yet."
    await _safe_edit(
        msg,
        text,
        reply_markup=InlineKeyboardMarkup([[ _btn("⬅️ Back to Help", "nav:help") ]]),
        disable_web_page_preview=False,
    )

async def render_help_games(msg: Message):
    text = GAME_RULES_TEXT or "No Game Rules configured yet."
    await _safe_edit(
        msg,
        text,
        reply_markup=InlineKeyboardMarkup([[ _btn("⬅️ Back to Help", "nav:help") ]]),
        disable_web_page_preview=False,
    )

async def render_help_exemptions(msg: Message):
    text = EXEMPTIONS_TEXT or "No Exemptions info configured yet."
    await _safe_edit(
        msg,
        text,
        reply_markup=InlineKeyboardMarkup([[ _btn("⬅️ Back to Help", "nav:help") ]]),
        disable_web_page_preview=False,
    )

# ----- MODELS ELSEWHERE (single text block from env)
async def render_links(msg: Message):
    text = FIND_MODELS_TEXT or "No models directory text configured yet."
    await _safe_edit(
        msg,
        text,
        reply_markup=InlineKeyboardMarkup(_back_main()),
        disable_web_page_preview=False,  # allow previews for any links inside your text
    )

# ========= Wiring =========
def register(app: Client):
    @app.on_callback_query(filters.regex("^nav:main$"))
    async def _go_main(c, cq): await render_main(cq.message)

    @app.on_callback_query(filters.regex("^nav:menu$"))
    async def _go_menu(c, cq): await render_menu(cq.message)

    @app.on_callback_query(filters.regex("^nav:contact$"))
    async def _go_contact(c, cq): await render_contact(cq.message)

    @app.on_callback_query(filters.regex("^nav:help$"))
    async def _go_help(c, cq): await render_help(cq.message)

    @app.on_callback_query(filters.regex("^nav:links$"))
    async def _go_links(c, cq): await render_links(cq.message)

    # Help sub-panels
    @app.on_callback_query(filters.regex("^help:rules$"))
    async def _help_rules(c, cq): await render_help_rules(cq.message)

    @app.on_callback_query(filters.regex("^help:reqs$"))
    async def _help_reqs(c, cq): await render_help_requirements(cq.message)

    @app.on_callback_query(filters.regex("^help:games$"))
    async def _help_games(c, cq): await render_help_games(cq.message)

    @app.on_callback_query(filters.regex("^help:exempt$"))
    async def _help_exempt(c, cq): await render_help_exemptions(cq.message)

    # Optional mirrored commands
    @app.on_message(filters.private & filters.command("menu"))
    async def _cmd_menu(c, m):
        ph = await m.reply_text("…")
        await render_menu(ph)

    @app.on_message(filters.private & filters.command("contact"))
    async def _cmd_contact(c, m):
        ph = await m.reply_text("…")
        await render_contact(ph)

    @app.on_message(filters.private & filters.command("help"))
    async def _cmd_help(c, m):
        ph = await m.reply_text("…")
        await render_help(ph)
