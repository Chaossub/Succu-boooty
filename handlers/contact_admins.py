# Contact Admins panel: Roni / Ruby links + Suggestion + Anonymous
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# ENV — names/usernames/ids (fallbacks are safe)
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RONI_USERNAME = os.getenv("RONI_USERNAME", "").lstrip("@")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "").lstrip("@")
RONI_ID = int(os.getenv("RONI_ID", "0") or "0")
RUBY_ID = int(os.getenv("RUBY_ID", "0") or "0")

BTN_BACK = os.getenv("BTN_BACK", "⬅️ Back to Main")

def _user_link(username: str, uid: int) -> str:
    if username:
        return f"https://t.me/{username}"
    if uid:
        return f"tg://user?id={uid}"
    return "https://t.me"

def _main_kb() -> InlineKeyboardMarkup:
    # Mirror the hub buttons so Back works even if other modules change later
    rows = [
        [InlineKeyboardButton("💕 Menus", callback_data="open_menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="open_contact_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="open_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="open_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _kb_contact_admins() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(f"💬 Contact {RONI_NAME}", url=_user_link(RONI_USERNAME, RONI_ID)),
            InlineKeyboardButton(f"💬 Contact {RUBY_NAME}", url=_user_link(RUBY_USERNAME, RUBY_ID)),
        ],
        [
            InlineKeyboardButton("💡 Send Suggestion", callback_data="contact_suggest"),
            InlineKeyboardButton("🙈 Anonymous Message", callback_data="contact_anon"),
        ],
        [InlineKeyboardButton(BTN_BACK, callback_data="panel_back_main")],
    ]
    return InlineKeyboardMarkup(rows)

CONTACT_TEXT = (
    "<b>👑 Contact Admins</b>\n"
    "• Tap to message an admin directly.\n"
    "• Or send a suggestion / anonymous message via the bot."
)

SUGGEST_PROMPT = (
    "💡 <b>Suggestions</b>\n"
    "Reply in <b>this chat</b> with your suggestion. I’ll forward it to the admins."
)

ANON_PROMPT = (
    "🙈 <b>Anonymous Message</b>\n"
    "Reply in <b>this chat</b> with the message. I’ll forward it anonymously to the owner."
)

def register(app: Client):
    # Open panel (support multiple IDs seen in older menus)
    @app.on_callback_query(filters.regex(r"^(open_contact_admins|contact_admins)$"))
    async def open_panel(_, cq: CallbackQuery):
        await cq.message.edit_text(CONTACT_TEXT, reply_markup=_kb_contact_admins(), disable_web_page_preview=True)
        await cq.answer()

    # Back to hub
    @app.on_callback_query(filters.regex(r"^panel_back_main$"))
    async def back_main(_, cq: CallbackQuery):
        await cq.message.edit_text(
            "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
            "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
            "✨ <i>Use the menu below to navigate!</i>",
            reply_markup=_main_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Suggestion flow (user will reply; dm_foolproof/owner-forwarder can pick replies if you wish;
    # for now we just show instructions)
    @app.on_callback_query(filters.regex(r"^contact_suggest$"))
    async def suggest(_, cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(SUGGEST_PROMPT, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(BTN_BACK, callback_data="open_contact_admins")]]
        ))

    # Anonymous flow prompt
    @app.on_callback_query(filters.regex(r"^contact_anon$"))
    async def anon(_, cq: CallbackQuery):
        await cq.answer()
        await cq.message.edit_text(ANON_PROMPT, reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(BTN_BACK, callback_data="open_contact_admins")]]
        ))

    # Slash command shortcut (optional)
    @app.on_message(filters.command(["contactadmins", "contact", "admins"]) & ~filters.edited)
    async def cmd_contact(_, m: Message):
        await m.reply_text(CONTACT_TEXT, reply_markup=_kb_contact_admins(), disable_web_page_preview=True)
