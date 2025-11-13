# handlers/panels.py
import os
import logging

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)

from utils.menu_store import store

log = logging.getLogger(__name__)

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "Nothing here yet 💕")

# Fixed model list used for the Menus panel
MODELS = [
    {"slug": "roni", "label": "Roni", "env": "RONI_USERNAME"},
    {"slug": "ruby", "label": "Ruby", "env": "RUBY_USERNAME"},
    {"slug": "rin",  "label": "Rin",  "env": "RIN_USERNAME"},
    {"slug": "savy", "label": "Savy", "env": "SAVY_USERNAME"},
]


def _username_for(slug: str) -> str | None:
    """Get @username for a model from env, cleaned."""
    rec = next((m for m in MODELS if m["slug"] == slug), None)
    if not rec:
        return None
    username = (os.getenv(rec["env"], "") or "").strip()
    if username.startswith("@"):
        username = username[1:]
    return username or None


def _main_kb() -> InlineKeyboardMarkup:
    """Main /start keyboard."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menus", callback_data="panels:menus")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
        ]
    )


def _menus_kb() -> InlineKeyboardMarkup:
    """
    2x2 grid of model names:
    [Roni Ruby]
    [Rin  Savy]
    [Back]
    """
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for rec in MODELS:
        row.append(
            InlineKeyboardButton(
                rec["label"], callback_data=f"menus:model:{rec['slug']}"
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="panels:root")])
    return InlineKeyboardMarkup(rows)


def _menu_text(name: str) -> str:
    """
    Get saved menu text from menu_store.
    Falls back to 'no menu saved yet' if nothing is stored.
    """
    txt = store.get_menu(name)
    if txt:
        return txt
    return (
        "no menu saved yet.\n\n"
        f"use /createmenu {name} <text...> to set one."
    )


def register(app: Client):
    log.info("✅ handlers.panels registered (static Menus + Book/Tip)")

    # ───────── /start -> Main panel ─────────
    @app.on_message(filters.command("start") & filters.private)
    async def start_cmd(_, m: Message):
        await m.reply_text(
            "🔥 Welcome to SuccuBot\n"
            "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
            "😈 If you ever need to know exactly what I can do, just press the Help button "
            "and I’ll spill all my secrets… 💋",
            reply_markup=_main_kb(),
            disable_web_page_preview=True,
        )

    # ───────── Back to main (panels:root) ─────────
    @app.on_callback_query(filters.regex(r"^panels:root$"))
    async def root_cb(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "🔥 Welcome back to SuccuBot\n"
                "Use the menu below to navigate!",
                reply_markup=_main_kb(),
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # ───────── Menus button from main ─────────
    @app.on_callback_query(filters.regex(r"^panels:menus$"))
    async def open_menus(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "📖 <b>Menus</b>\nTap a name to view.",
                reply_markup=_menus_kb(),
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # Optional: /menus command (same as tapping Menus button)
    @app.on_message(filters.command("menus") & filters.private)
    async def menus_cmd(_, m: Message):
        await m.reply_text(
            "📖 <b>Menus</b>\nTap a name to view.",
            reply_markup=_menus_kb(),
            disable_web_page_preview=True,
        )

    # ───────── Individual model menus ─────────
    @app.on_callback_query(filters.regex(r"^menus:model:(\w+)$"))
    async def model_menu(_, cq: CallbackQuery):
        slug = cq.data.split(":", 2)[-1]
        rec = next((m for m in MODELS if m["slug"] == slug), None)
        if not rec:
            await cq.answer("Unknown model.", show_alert=True)
            return

        name = rec["label"]
        text = _menu_text(name)
        username = _username_for(slug)

        buttons: list[list[InlineKeyboardButton]] = []

        # 📖 Book – open DM if username is set, otherwise alert
        if username:
            buttons.append(
                [InlineKeyboardButton("📖 Book", url=f"https://t.me/{username}")]
            )
        else:
            buttons.append(
                [InlineKeyboardButton("📖 Book", callback_data="menus:nobook")]
            )

        # 💸 Tip (coming soon)
        buttons.append(
            [InlineKeyboardButton("💸 Tip (coming soon)", callback_data="menus:tip_soon")]
        )

        # Back + Main
        buttons.append(
            [InlineKeyboardButton("⬅️ Back", callback_data="panels:menus")]
        )
        buttons.append(
            [InlineKeyboardButton("🏠 Main Menu", callback_data="panels:root")]
        )

        kb = InlineKeyboardMarkup(buttons)

        try:
            await cq.message.edit_text(
                f"{name} — menu\n\n{text}",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # Small alerts for disabled actions
    @app.on_callback_query(filters.regex(r"^menus:nobook$"))
    async def no_book(_, cq: CallbackQuery):
        await cq.answer("Booking link isn’t set yet for this model. 💕", show_alert=True)

    @app.on_callback_query(filters.regex(r"^menus:tip_soon$"))
    async def tip_soon(_, cq: CallbackQuery):
        await cq.answer("Tips are coming soon. 💋", show_alert=True)
