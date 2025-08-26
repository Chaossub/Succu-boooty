# handlers/menu.py
import os
from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

# ---------- Config / ENV ----------
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # where anon/suggestions are sent

# Public model usernames for DM links
RONI_USERNAME = os.getenv("RONI_USERNAME", "RoniJane")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "RubyExample")
RIN_USERNAME  = os.getenv("RIN_USERNAME",  "RinExample")
SAVY_USERNAME = os.getenv("SAVY_USERNAME", "SavyExample")

# Admin usernames (can be same as model username if applicable)
ADMIN_RONI_USERNAME = os.getenv("ADMIN_RONI_USERNAME", RONI_USERNAME)
ADMIN_RUBY_USERNAME = os.getenv("ADMIN_RUBY_USERNAME", RUBY_USERNAME)

WELCOME_BANNER = (
    "🔥 Welcome to SuccuBot 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

MODELS_ELSEWHERE_TEXT = (os.getenv("MODELS_ELSEWHERE_TEXT") or
                         "No external links have been set yet.").strip()
BUYER_RULES        = (os.getenv("BUYER_RULES") or "No buyer rules configured.").strip()
BUYER_REQUIREMENTS = (os.getenv("BUYER_REQUIREMENTS") or "No buyer requirements configured.").strip()
GAME_RULES         = (os.getenv("GAME_RULES") or "No game rules configured.").strip()

# ---------- Small utility ----------
async def _safe_edit_text(msg: Message, text: str, reply_markup=None):
    """Avoid MESSAGE_NOT_MODIFIED & stop spinner; keep web previews off."""
    current = (msg.text or msg.caption or "")
    if current == text:
        await msg.edit_reply_markup(reply_markup=reply_markup)
    else:
        await msg.edit_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

def _tme(username: str) -> str:
    return f"https://t.me/{username.lstrip('@')}"

# ---------- Keyboards ----------
def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("💞 Contact Models", callback_data="contact_models")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="contact_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="find_elsewhere")],
        [InlineKeyboardButton("❓ Help", callback_data="help_root")],
    ])

def _kb_menus() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💗 Roni", callback_data="menu_roni")],
        [InlineKeyboardButton("💗 Ruby", callback_data="menu_ruby")],
        [InlineKeyboardButton("💗 Rin",  callback_data="menu_rin")],
        [InlineKeyboardButton("💗 Savy", callback_data="menu_savy")],
        [InlineKeyboardButton("💞 Contact Models", callback_data="contact_models")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])

def _kb_contact_models() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💌 Roni ↗", url=_tme(RONI_USERNAME))],
        [InlineKeyboardButton("💌 Ruby ↗", url=_tme(RUBY_USERNAME))],
        [InlineKeyboardButton("💌 Rin  ↗", url=_tme(RIN_USERNAME))],
        [InlineKeyboardButton("💌 Savy ↗", url=_tme(SAVY_USERNAME))],
        [InlineKeyboardButton("⬅️ Back to Menus", callback_data="menus")],
    ])

def _kb_contact_admins() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 DM Roni", url=_tme(ADMIN_RONI_USERNAME))],
        [InlineKeyboardButton("👑 DM Ruby", url=_tme(ADMIN_RUBY_USERNAME))],
        [InlineKeyboardButton("🕵️ Anonymous Message", callback_data="admin_anon")],
        [InlineKeyboardButton("💡 Suggestion Box", callback_data="admin_suggest")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])

def _kb_help_root() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help_rules")],
        [InlineKeyboardButton("✅ Buyer Requirements", callback_data="help_requirements")],
        [InlineKeyboardButton("🤖 Member Commands", callback_data="help_commands")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="help_games")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
    ])

def _kb_back_to_menus() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menus", callback_data="menus")]])

# ---------- Per-model menu text & keyboards (NOT DMs) ----------
def _text_menu_roni() -> str:
    return ("💗 Roni — Menu\n"
            "• Customs • Games • Bundles\n"
            "Tap **Book Roni** to open DMs or go back to Menus.")

def _text_menu_ruby() -> str:
    return ("💗 Ruby — Menu\n"
            "• Sets • PPVs • Girlfriend Exp.\n"
            "Tap **Book Ruby** to open DMs or go back to Menus.")

def _text_menu_rin() -> str:
    return ("💗 Rin — Menu\n"
            "• Tease Packs • Clips • Dice Games\n"
            "Tap **Book Rin** to open DMs or go back to Menus.")

def _text_menu_savy() -> str:
    return ("💗 Savy — Menu\n"
            "• Photos • Videos • Wheel Spins\n"
            "Tap **Book Savy** to open DMs or go back to Menus.")

def _kb_menu_roni() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Book Roni", url=_tme(RONI_USERNAME))],
        [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
    ])

def _kb_menu_ruby() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Book Ruby", url=_tme(RUBY_USERNAME))],
        [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
    ])

def _kb_menu_rin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Book Rin", url=_tme(RIN_USERNAME))],
        [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
    ])

def _kb_menu_savy() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Book Savy", url=_tme(SAVY_USERNAME))],
        [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
    ])

# ---------- Registration ----------
def register(app):
    # /start and /portal show the welcome banner + main menu (keep it pretty)
    @app.on_message(filters.command(["start", "portal"]) & filters.private)
    async def _start(_, m: Message):
        await m.reply_text(WELCOME_BANNER, reply_markup=_kb_main(), disable_web_page_preview=True)

    # ==== Main → submenus ====
    @app.on_callback_query(filters.regex("^menus$"))
    async def _cb_menus(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, "💕 Menus", reply_markup=_kb_menus())

    @app.on_callback_query(filters.regex("^contact_models$"))
    async def _cb_contact_models(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, "Contact a model directly:", reply_markup=_kb_contact_models())

    @app.on_callback_query(filters.regex("^contact_admins$"))
    async def _cb_contact_admins(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, "Contact Admins:", reply_markup=_kb_contact_admins())

    @app.on_callback_query(filters.regex("^find_elsewhere$"))
    async def _cb_find_elsewhere(_, q: CallbackQuery):
        await q.answer()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]])
        await _safe_edit_text(q.message, MODELS_ELSEWHERE_TEXT, reply_markup=kb)

    @app.on_callback_query(filters.regex("^help_root$"))
    async def _cb_help_root(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, "Help", reply_markup=_kb_help_root())

    # ==== Help leaf pages ====
    @app.on_callback_query(filters.regex("^help_rules$"))
    async def _cb_help_rules(_, q: CallbackQuery):
        await q.answer()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="help_root")]])
        await _safe_edit_text(q.message, BUYER_RULES, reply_markup=kb)

    @app.on_callback_query(filters.regex("^help_requirements$"))
    async def _cb_help_requirements(_, q: CallbackQuery):
        await q.answer()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="help_root")]])
        await _safe_edit_text(q.message, BUYER_REQUIREMENTS, reply_markup=kb)

    @app.on_callback_query(filters.regex("^help_games$"))
    async def _cb_help_games(_, q: CallbackQuery):
        await q.answer()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="help_root")]])
        await _safe_edit_text(q.message, GAME_RULES, reply_markup=kb)

    @app.on_callback_query(filters.regex("^help_commands$"))
    async def _cb_help_commands(_, q: CallbackQuery):
        await q.answer()
        text = (
            "Member commands:\n"
            "• /portal — open the main menu\n"
            "• /dmready — mark DM-ready (once)\n"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="help_root")]])
        await _safe_edit_text(q.message, text, reply_markup=kb)

    # ==== Model menus (NOT DMs) ====
    @app.on_callback_query(filters.regex("^menu_roni$"))
    async def _cb_menu_roni(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, _text_menu_roni(), reply_markup=_kb_menu_roni())

    @app.on_callback_query(filters.regex("^menu_ruby$"))
    async def _cb_menu_ruby(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, _text_menu_ruby(), reply_markup=_kb_menu_ruby())

    @app.on_callback_query(filters.regex("^menu_rin$"))
    async def _cb_menu_rin(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, _text_menu_rin(), reply_markup=_kb_menu_rin())

    @app.on_callback_query(filters.regex("^menu_savy$"))
    async def _cb_menu_savy(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, _text_menu_savy(), reply_markup=_kb_menu_savy())

    # ==== Admin inbox (anon/suggest) ====
    @app.on_callback_query(filters.regex("^admin_anon$"))
    async def _cb_admin_anon(_, q: CallbackQuery):
        await q.answer()
        if OWNER_ID:
            sender = f"@{q.from_user.username}" if q.from_user and q.from_user.username else f"id:{q.from_user.id}"
            await _.send_message(
                chat_id=OWNER_ID,
                text=f"🕵️ Anonymous message button tapped by {sender}.\n\n"
                     f"(Reply here to reach out privately.)"
            )
        await q.message.reply_text("🕵️ Drop your anonymous message here. I’ve pinged the admin inbox.")
        # keep current view; no edit

    @app.on_callback_query(filters.regex("^admin_suggest$"))
    async def _cb_admin_suggest(_, q: CallbackQuery):
        await q.answer()
        if OWNER_ID:
            sender = f"@{q.from_user.username}" if q.from_user and q.from_user.username else f"id:{q.from_user.id}"
            await _.send_message(
                chat_id=OWNER_ID,
                text=f"💡 New suggestion ping from {sender}.\n\n"
                     f"(They tapped Suggestion Box in the bot.)"
            )
        await q.message.reply_text("💡 Got a suggestion? Type it here and send. I’ll forward it to the admins.")
        # keep current view; no edit

    # ==== Back → Main (keep the banner) ====
    @app.on_callback_query(filters.regex("^back_main$"))
    async def _cb_back_main(_, q: CallbackQuery):
        await q.answer()
        await _safe_edit_text(q.message, WELCOME_BANNER, reply_markup=_kb_main())

    # optional: noop to satisfy any spare callback_data="noop"
    @app.on_callback_query(filters.regex("^noop$"))
    async def _cb_noop(_, q: CallbackQuery):
        await q.answer()
