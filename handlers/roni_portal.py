# handlers/roni_portal.py
import logging
import os

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

log = logging.getLogger(__name__)

# Your bot's username (without @) – used for the deep link
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "YourBotUsernameHere").lstrip("@")

# Your personal @username – used for customer + business DMs
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "chaossub283").lstrip("@")


def _roni_main_keyboard() -> InlineKeyboardMarkup:
    rows = [
        # Roni’s Menu (placeholder for now)
        [InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")],

        # 💌 Book Roni → open Roni’s DMs (customer side)
        [
            InlineKeyboardButton(
                "💌 Book Roni",
                url=f"https://t.me/{RONI_USERNAME}",
            )
        ],

        # 💸 Pay / Tip Roni – placeholder for now
        [InlineKeyboardButton("💸 Pay / Tip Roni", callback_data="roni_portal:todo")],

        # 🌸 Open Access – placeholder for now
        [InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:todo")],

        # ✅ Age Verify – placeholder for now
        [InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:todo")],

        # 🔥 Teaser & Promo Channels – placeholder for now
        [InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:todo")],

        # 😈 Models & Creators — DM Roni with /business pre-filled (business quick reply)
        [
            InlineKeyboardButton(
                "😈 Models & Creators — Tap Here",
                url=f"https://t.me/{RONI_USERNAME}?text=/business",
            )
        ],

        # Back to main SuccuBot menu
        [
            InlineKeyboardButton(
                "🏠 Back to SuccuBot Menu",
                callback_data="panels:root",
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal registered")

    # ───────── /roni_portal command (for your welcome channel) ─────────
    @app.on_message(filters.command("roni_portal"))
    async def roni_portal_command(_, m: Message):
        """
        Run this in your welcome channel.
        It replies with a button that opens DM with SuccuBot in assistant mode.
        """
        start_link = f"https://t.me/{BOT_USERNAME}?start=roni_assistant"

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💗 Open Roni’s Assistant", url=start_link)]]
        )

        await m.reply_text(
            "Tap below to open a private chat with SuccuBot in Roni’s assistant mode. 💕",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ───────── /start roni_assistant in DM (assistant mode) ─────────
    # group=-1 makes this run BEFORE your normal /start handler from panels
    @app.on_message(filters.private & filters.command("start"), group=-1)
    async def roni_assistant_entry(_, m: Message):
        if not m.text:
            return

        parts = m.text.split(maxsplit=1)
        param = parts[1].strip() if len(parts) > 1 else ""

        # Only handle /start roni_assistant
        if not param or not param.lower().startswith("roni_assistant"):
            return  # Let the normal /start handler handle everything else

        # This IS our special assistant start – stop other /start handlers
        try:
            m.stop_propagation()
        except Exception:
            pass

        kb = _roni_main_keyboard()
        await m.reply_text(
            "Welcome to Roni’s personal assistant. 💗\n"
            "Use the buttons below to explore her menu, booking options, and more.\n"
            "Some features are still being built, so you might see 'coming soon' for now. 💕",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ───────── Roni’s Menu placeholder ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:menu$"))
    async def roni_menu_cb(_, cq: CallbackQuery):
        text = (
            "📖 <b>Roni’s Menu</b>\n\n"
            "This is a placeholder for Roni’s personal menu.\n"
            "Once everything is tested and stable, this will show her full services, bundles, and options. 💕"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                [InlineKeyboardButton("🏠 Back to SuccuBot Menu", callback_data="panels:root")],
            ]
        )
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── Back to main assistant menu ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:home$"))
    async def roni_home_cb(_, cq: CallbackQuery):
        kb = _roni_main_keyboard()
        await cq.message.edit_text(
            "Welcome to Roni’s personal assistant. 💗\n"
            "Use the buttons below to explore her menu, booking options, and more.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── Placeholder for not-yet-implemented buttons ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:todo$"))
    async def roni_todo_cb(_, cq: CallbackQuery):
        await cq.answer("This feature is coming soon 💕", show_alert=True)
