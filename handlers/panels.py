# handlers/panels.py
from typing import Optional
import os
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton


# Admin identities from ENV (either usernames or numeric IDs are fine)
RONI_ID    = os.getenv("RONI_ID")
RUBY_ID    = os.getenv("RUBY_ID")
RONI_NAME  = os.getenv("RONI_NAME", "Roni")
RUBY_NAME  = os.getenv("RUBY_NAME", "Ruby")
MODELS_URL = os.getenv("MODELS_LINK") or os.getenv("MODELS_URL")


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def _back_main():
    return [[_btn("⬅️ Back to Main", "panel:main")]]


async def render_main(msg: Message):
    rows = [
        [_btn("💕 Menu", "panel:menu")],
        [_btn("👑 Contact Admins", "panel:contact")],
        [_btn("🔥 Find Our Models Elsewhere", "panel:models")],
        [_btn("❓ Help", "panel:help")],
    ]
    await msg.edit_text(
        "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
        "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
        "✨ <i>Use the menu below to navigate!</i>",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True,
    )


def _profile_url(username_env_key: str, numeric_id: Optional[str]) -> Optional[str]:
    uname = os.getenv(username_env_key)
    if uname:
        return f"https://t.me/{uname.lstrip('@')}"
    if numeric_id:
        try:
            return f"https://t.me/user?id={int(numeric_id)}"
        except Exception:
            return None
    return None


async def render_contact(msg: Message, _me_username: Optional[str] = None):
    rows: list[list[InlineKeyboardButton]] = []

    roni_url = _profile_url("RONI_USERNAME", RONI_ID)
    ruby_url = _profile_url("RUBY_USERNAME", RUBY_ID)

    if roni_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RONI_NAME}", url=roni_url)])
    if ruby_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RUBY_NAME}", url=ruby_url)])

    rows.append([_btn("🕵️ Anonymous Message", "contact:anon")])
    rows += _back_main()

    await msg.edit_text(
        "👑 <b>Contact Admins</b>\n\n"
        "• Tag an admin in chat\n"
        "• Or send an anonymous message via the bot.\n",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True,
    )


async def render_help(msg: Message):
    rows = _back_main()
    await msg.edit_text(
        "❓ <b>Help</b>\n\n"
        "Tap a button above, or ask an admin if you’re stuck.",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def render_models(msg: Message):
    rows = _back_main()
    text = "🧭 <b>Find Our Models Elsewhere</b>\n\n"
    if MODELS_URL:
        text += f"<a href=\"{MODELS_URL}\">Tap here</a> to browse."
    else:
        text += "Ask an admin for the link."
    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(rows), disable_web_page_preview=False)


def register(app):
    from pyrogram import filters
    from pyrogram.types import CallbackQuery

    @app.on_callback_query(filters.regex("^panel:main$"))
    async def _cb_main(_, cq: CallbackQuery):
        await render_main(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex("^panel:contact$"))
    async def _cb_contact(client, cq: CallbackQuery):
        me = await client.get_me()
        await render_contact(cq.message, getattr(me, "username", None))
        await cq.answer()

    @app.on_callback_query(filters.regex("^panel:help$"))
    async def _cb_help(_, cq: CallbackQuery):
        await render_help(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex("^panel:models$"))
    async def _cb_models(_, cq: CallbackQuery):
        await render_models(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex("^panel:menu$"))
    async def _cb_menu(_, cq: CallbackQuery):
        # Your dedicated menus module should be wired separately as handlers.menu.
        # We only acknowledge the tap so it never feels “dead”.
        await cq.answer("Opening menus…")
