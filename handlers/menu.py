# handlers/menu.py
import os
from pyrogram import filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message
)

# --- ENV content (texts & usernames) -----------------------------

WELCOME_TEXT = (
    "💋 **Welcome to Succubus Sanctuary** 💋\n\n"
    "Tap a button to get started:"
)

# Find Our Models Elsewhere: from ENV (plain text with links)
FIND_ELSEWHERE_TEXT = os.getenv("FIND_MODELS_ELSEWHERE_TEXT", "No links set yet.")

# Help docs from ENV
BUYER_RULES_TEXT = os.getenv("BUYER_RULES_TEXT", "No buyer rules set.")
BUYER_REQUIREMENTS_TEXT = os.getenv("BUYER_REQUIREMENTS_TEXT", "No buyer requirements set.")
GAME_RULES_TEXT = os.getenv("GAME_RULES_TEXT", "No game rules set.")

# Per-model menus from ENV (models can be editable later)
MENU_RONI = os.getenv("MENU_RONI", "Roni’s menu is not set yet.")
MENU_RUBY = os.getenv("MENU_RUBY", "Ruby’s menu is not set yet.")
MENU_SAVY = os.getenv("MENU_SAVY", "Savy’s menu is not set yet.")
MENU_RIN  = os.getenv("MENU_RIN",  "Rin’s menu is not set yet.")

# Model Telegram @usernames for DM links
RONI_USERNAME = os.getenv("RONI_USERNAME", "RoniMissingUser")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "RubyMissingUser")
SAVY_USERNAME = os.getenv("SAVY_USERNAME", "SavyMissingUser")
RIN_USERNAME  = os.getenv("RIN_USERNAME",  "RinMissingUser")

# --- Keyboards ---------------------------------------------------

def kb_main() -> InlineKeyboardMarkup:
    # Main menu: one button per row (vertical), and keep the welcome text visible
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Menus", callback_data="mm:menus")],
        [InlineKeyboardButton("🌐 Find Our Models Elsewhere", callback_data="mm:elsewhere")],
        [InlineKeyboardButton("🛡️ Contact Admins", callback_data="mm:admins")],
        [InlineKeyboardButton("❓ Help", callback_data="mm:help")],
    ])

def kb_menus() -> InlineKeyboardMarkup:
    # 2x2 grid of models + Contact Models row + back rows
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Roni", callback_data="model:roni"),
         InlineKeyboardButton("Ruby", callback_data="model:ruby")],
        [InlineKeyboardButton("Savy", callback_data="model:savy"),
         InlineKeyboardButton("Rin",  callback_data="model:rin")],
        [InlineKeyboardButton("💬 Contact Models", callback_data="menus:contact")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back:main"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
    ])

def kb_contact_models() -> InlineKeyboardMarkup:
    # Contact models: 2x2 grid of URL buttons; ONLY a long “Main Menu” back (as requested)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Message Roni", url=f"https://t.me/{RONI_USERNAME}"),
         InlineKeyboardButton("Message Ruby", url=f"https://t.me/{RUBY_USERNAME}")],
        [InlineKeyboardButton("Message Savy", url=f"https://t.me/{SAVY_USERNAME}"),
         InlineKeyboardButton("Message Rin",  url=f"https://t.me/{RIN_USERNAME}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
    ])

def kb_model(name_key: str) -> InlineKeyboardMarkup:
    # Under each model’s menu: Book + Tip below, plus back to Menus and Main
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📖 Book {name_key.title()}", callback_data=f"book:{name_key}")],
        [InlineKeyboardButton("💸 Tip (coming soon)", callback_data="tip:comingsoon")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back:menus"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
    ])

def kb_elsewhere() -> InlineKeyboardMarkup:
    # Text only screen; simple backs
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="back:main"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
    ])

def kb_admins() -> InlineKeyboardMarkup:
    # 2x2: Message Roni / Ruby, Suggestions & Anonymous Message
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Message Roni", url=f"https://t.me/{RONI_USERNAME}"),
         InlineKeyboardButton("Message Ruby", url=f"https://t.me/{RUBY_USERNAME}")],
        [InlineKeyboardButton("📝 Suggestions", callback_data="admin:suggest"),
         InlineKeyboardButton("🕵️ Anonymous Message", callback_data="admin:anon")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back:main"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
    ])

def kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📕 Buyer Rules", callback_data="help:buyer_rules"),
         InlineKeyboardButton("✅ Buyer Requirements", callback_data="help:buyer_requirements")],
        [InlineKeyboardButton("🎮 Game Rules", callback_data="help:game_rules"),
         InlineKeyboardButton("🆘 Member Commands", callback_data="help:member_cmds")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back:main"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
    ])

def kb_help_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="mm:help"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
    ])

def kb_suggest_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="mm:admins"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
    ])

# --- Utilities ---------------------------------------------------

async def _safe_edit_text(msg: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    try:
        await msg.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    except MessageNotModified:
        # Already showing the same thing – just ignore.
        pass

# --- Screens (renderers) ----------------------------------------

async def show_main(q_or_msg):
    if isinstance(q_or_msg, CallbackQuery):
        await q_or_msg.answer()
        await _safe_edit_text(q_or_msg.message, WELCOME_TEXT, kb_main())
    else:
        await q_or_msg.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

async def show_menus(q: CallbackQuery):
    await q.answer()
    await _safe_edit_text(q.message, "📜 Menus", kb_menus())

async def show_contact_models(q: CallbackQuery):
    await q.answer()
    await _safe_edit_text(q.message, "💬 Contact our models:", kb_contact_models())

async def show_elsewhere(q: CallbackQuery):
    await q.answer()
    await _safe_edit_text(q.message, FIND_ELSEWHERE_TEXT, kb_elsewhere())

async def show_admins(q: CallbackQuery):
    await q.answer()
    await _safe_edit_text(q.message, "🛡️ Contact Admins", kb_admins())

async def show_help(q: CallbackQuery):
    await q.answer()
    await _safe_edit_text(q.message, "❓ Help", kb_help())

async def show_model(q: CallbackQuery, who: str):
    await q.answer()
    text_map = {
        "roni": MENU_RONI,
        "ruby": MENU_RUBY,
        "savy": MENU_SAVY,
        "rin":  MENU_RIN,
    }
    await _safe_edit_text(q.message, text_map.get(who, "No menu yet."), kb_model(who))

# --- Suggestions & Anonymous messages (DM to owner) --------------

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")  # who receives suggestions/anon

_pending_prompts = {}  # {user_id: {"type": "suggest"|"anon"}}

async def start_collecting(q: CallbackQuery, kind: str):
    await q.answer()
    _pending_prompts[q.from_user.id] = {"type": kind}
    prompt = "Send me your suggestion (it can include your name or be anonymous)." if kind == "suggest" \
        else "Send me the anonymous message now. Your username will not be included."
    await _safe_edit_text(q.message, prompt, kb_suggest_back())

# --- Registration ------------------------------------------------

def register(app):
    # /start and /portal -> show main menu with welcome text
    @app.on_message(filters.private & filters.command(["start", "portal"]))
    async def _start(_, m: Message):
        await show_main(m)

    # Callback router
    @app.on_callback_query()
    async def _router(_, q: CallbackQuery):
        data = q.data or ""

        # Main sections
        if data == "mm:menus":
            return await show_menus(q)
        if data == "mm:elsewhere":
            return await show_elsewhere(q)
        if data == "mm:admins":
            return await show_admins(q)
        if data == "mm:help":
            return await show_help(q)

        # Back handling
        if data == "back:main":
            return await show_main(q)
        if data == "back:menus":
            return await show_menus(q)

        # Menus -> Contact Models and model screens
        if data == "menus:contact":
            return await show_contact_models(q)

        if data.startswith("model:"):
            who = data.split(":", 1)[1]
            return await show_model(q, who)

        # Book model (open DM link via an intermediate message)
        if data.startswith("book:"):
            who = data.split(":", 1)[1]
            links = {
                "roni": f"https://t.me/{RONI_USERNAME}",
                "ruby": f"https://t.me/{RUBY_USERNAME}",
                "savy": f"https://t.me/{SAVY_USERNAME}",
                "rin":  f"https://t.me/{RIN_USERNAME}",
            }
            url = links.get(who)
            await q.answer()
            if url:
                # Show a gentle nudge with the URL button
                return await _safe_edit_text(
                    q.message,
                    f"Tap below to message {who.title()}:",
                    InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"Open DM with {who.title()}", url=url)],
                        [InlineKeyboardButton("⬅️ Back", callback_data="back:menus"),
                         InlineKeyboardButton("🏠 Main Menu", callback_data="back:main")],
                    ])
                )
            else:
                return await _safe_edit_text(q.message, "Username not configured.", kb_model(who))

        # Tip (coming soon)
        if data == "tip:comingsoon":
            await q.answer("Coming soon ✨", show_alert=False)
            return

        # Admin suggestion/anon
        if data == "admin:suggest":
            return await start_collecting(q, "suggest")
        if data == "admin:anon":
            return await start_collecting(q, "anon")

        # Help detail pages
        if data == "help:buyer_rules":
            await q.answer()
            return await _safe_edit_text(q.message, BUYER_RULES_TEXT, kb_help_back())
        if data == "help:buyer_requirements":
            await q.answer()
            return await _safe_edit_text(q.message, BUYER_REQUIREMENTS_TEXT, kb_help_back())
        if data == "help:game_rules":
            await q.answer()
            return await _safe_edit_text(q.message, GAME_RULES_TEXT, kb_help_back())
        if data == "help:member_cmds":
            await q.answer()
            member_text = (
                "🆘 **Member Commands**\n"
                "• /menu – open menus\n"
                "• /portal – open main menu\n"
                "• /help – show help\n"
                "(More coming soon)"
            )
            return await _safe_edit_text(q.message, member_text, kb_help_back())

    # Capture text replies for suggestions/anon; deliver to OWNER_ID via DM
    @app.on_message(filters.private & ~filters.command(["start", "portal"]))
    async def _collect(_, m: Message):
        state = _pending_prompts.get(m.from_user.id)
        if not state:
            return  # regular private message; ignore here

        kind = state["type"]
        text = m.text or m.caption or "(no text)"
        try:
            if OWNER_ID:
                tag = "Suggestion" if kind == "suggest" else "Anonymous"
                await app.send_message(
                    OWNER_ID,
                    f"📩 **{tag} received**\nFrom: @{m.from_user.username or m.from_user.id}\n\n{text}"
                    if kind == "suggest"
                    else f"📩 **Anonymous message received**\n\n{text}"
                )
            await m.reply_text("Thanks! Your message was forwarded.", reply_markup=kb_suggest_back())
        finally:
            _pending_prompts.pop(m.from_user.id, None)
