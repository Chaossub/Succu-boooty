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

# Your Telegram @username (without @)
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "chaossub283").lstrip("@")


def _roni_main_keyboard() -> InlineKeyboardMarkup:
    """
    Full Roni portal layout with all buttons visible.
    Only Menu, DM, and Back function right now.
    """
    rows = [
        [InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")],
        [InlineKeyboardButton("💌 Book Roni", callback_data="roni_portal:todo")],
        [InlineKeyboardButton("💸 Pay / Tip Roni", callback_data="roni_portal:todo")],
        [InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:todo")],
        [InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:todo")],
        [InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:todo")],
        [
            InlineKeyboardButton(
                "😈 Models & Creators — Tap Here",
                url=f"https://t.me/{RONI_USERNAME}"
            )
        ],
        [
            InlineKeyboardButton(
                "🏠 Back to SuccuBot Menu",
                callback_data="panels:root"
            )
        ]
    ]
    return InlineKeyboardMarkup(rows)


def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal registered")

    # ───────────── /start roni_portal entry ─────────────
    @app.on_message(filters.private & filters.command("start"))
    async def roni_start_entry(_, m: Message):
        """
        Trigger only on /start roni_portal
        without interfering with your main /start.
        """
        if not m.text:
            return

        parts = m.text.split(maxsplit=1)
        param = parts[1].strip() if len(parts) > 1 else ""

        if not param or not param.lower().startswith("roni_portal"):
            return  # Not our command

        try:
            m.stop_propagation()
        except Exception:
            pass

        kb = _roni_main_keyboard()
        await m.reply_text(
            "Hi there, I’m SuccuBot — Roni’s virtual assistant.\n"
            "This is your direct portal to Roni’s personal menu.\n\n"
            "Right now you’re seeing the basic layout while she builds out her features.\n"
            "You can DM her or go back to the main SuccuBot menu. 💕",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ───────────── Placeholder Menu Page ─────────────
    @app.on_callback_query(filters.regex(r"^roni_portal:menu$"))
    async def roni_menu_cb(_, cq: CallbackQuery):
        text = (
            "📖 <b>Roni’s Menu</b>\n\n"
            "This is a placeholder for Roni’s personal menu.\n"
            "Once confirmed working, we’ll replace this with her real menu. 💕"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Roni Portal", callback_data="roni_portal:home")],
                [InlineKeyboardButton("🏠 Back to SuccuBot Menu", callback_data="panels:root")],
            ]
        )
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        finally:
            await cq.answer()

    # ───────────── Back to Portal ─────────────
    @app.on_callback_query(filters.regex(r"^roni_portal:home$"))
    async def roni_home_cb(_, cq: CallbackQuery):
        kb = _roni_main_keyboard()
        try:
            await cq.message.edit_text(
                "Hi there, I’m SuccuBot — Roni’s virtual assistant.\n"
                "This is your direct portal to Roni’s personal menu.\n\n"
                "Use the buttons below to explore, DM her, or go back to the main SuccuBot menu. 💕",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # ───────────── Placeholder for inactive buttons ─────────────
    @app.on_callback_query(filters.regex(r"^roni_portal:todo$"))
    async def roni_todo_cb(_, cq: CallbackQuery):
        await cq.answer("This feature is coming soon 💕", show_alert=True)
