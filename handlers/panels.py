# handlers/panels.py
import logging
import os
from typing import Dict

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from utils.menu_store import store

log = logging.getLogger(__name__)

# ────────────── USERNAMES FROM ENV (NO PLACEHOLDERS) ──────────────
# These mirror contact_admins.py. Env values should NOT contain '@'.
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "chaossub283").lstrip("@")
RUBY_USERNAME = (os.getenv("RUBY_USERNAME") or "RubyRansom").lstrip("@")
RIN_USERNAME  = (os.getenv("RIN_USERNAME")  or "peachyrinn").lstrip("@")
SAVY_USERNAME = (os.getenv("SAVY_USERNAME") or "savage_savy").lstrip("@")

# Static model config: slug -> {name, username}
MODEL_CONFIG: Dict[str, Dict[str, str]] = {
    "roni": {"name": "Roni", "username": RONI_USERNAME},
    "ruby": {"name": "Ruby", "username": RUBY_USERNAME},
    "rin":  {"name": "Rin",  "username": RIN_USERNAME},
    "savy": {"name": "Savy", "username": SAVY_USERNAME},
}

# ────────────── STRIPE TIP LINKS FROM ENV ──────────────
MODEL_TIP_LINKS: Dict[str, str] = {
    "roni": (os.getenv("TIP_RONI_LINK") or "").strip(),
    "ruby": (os.getenv("TIP_RUBY_LINK") or "").strip(),
    "rin":  (os.getenv("TIP_RIN_LINK") or "").strip(),
    "savy": (os.getenv("TIP_SAVY_LINK") or "").strip(),
}


# ────────────── KEYBOARDS ──────────────
def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💞 Menus", callback_data="panels:menus")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("📌 Requirements Help", callback_data="reqpanel:home")],  # NEW
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
        ]
    )


def _models_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("Roni", callback_data="panels:model:roni"),
            InlineKeyboardButton("Ruby", callback_data="panels:model:ruby"),
        ],
        [
            InlineKeyboardButton("Rin", callback_data="panels:model:rin"),
            InlineKeyboardButton("Savy", callback_data="panels:model:savy"),
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="panels:root")],
    ]
    return InlineKeyboardMarkup(rows)


def _model_keyboard(slug: str) -> InlineKeyboardMarkup:
    cfg = MODEL_CONFIG.get(slug, {})
    username = cfg.get("username") or ""
    if username.startswith("@"):
        username = username[1:]

    # Book button
    if username:
        book_button = InlineKeyboardButton("📩 Book", url=f"https://t.me/{username}")
    else:
        book_button = InlineKeyboardButton("📩 Book", callback_data="panels:nodm")

    # Tip button
    tip_link = MODEL_TIP_LINKS.get(slug) or ""
    if tip_link:
        tip_button = InlineKeyboardButton("💸 Tip", url=tip_link)
    else:
        tip_button = InlineKeyboardButton("💸 Tip (coming soon)", callback_data="panels:tip_coming")

    return InlineKeyboardMarkup(
        [
            [book_button],
            [tip_button],
            [
                InlineKeyboardButton("⬅️ Back", callback_data="panels:menus"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="panels:root"),
            ],
        ]
    )


# ────────────── REGISTER HANDLERS ──────────────
def register(app: Client):
    log.info(
        "✅ handlers.panels registered (static 4-model panel, MenuStore=%s, RONI=%s RUBY=%s RIN=%s SAVY=%s)",
        store.uses_mongo(),
        RONI_USERNAME,
        RUBY_USERNAME,
        RIN_USERNAME,
        SAVY_USERNAME,
    )

    # -------- /start --------
    @app.on_message(filters.command("start"))
    async def start_cmd(_, m: Message):
        # ⛔ Skip Sanctuary welcome if launching ANY Roni assistant/portal
        text = (m.text or "").lower()
        if "roni_" in text:
            return

        kb = _main_keyboard()
        await m.reply_text(
            "🔥 Welcome to SuccuBot\n"
            "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # -------- Menus list --------
    @app.on_callback_query(filters.regex(r"^panels:menus$"))
    async def menus_list_cb(_, cq: CallbackQuery):
        kb = _models_keyboard()
        try:
            await cq.message.edit_text(
                "💕 <b>Choose a model:</b>",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Main/root --------
    @app.on_callback_query(filters.regex(r"^panels:root$"))
    async def panels_root_cb(_, cq: CallbackQuery):
        kb = _main_keyboard()
        try:
            await cq.message.edit_text(
                "🔥 Welcome back to SuccuBot\n"
                "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Single model page --------
    @app.on_callback_query(filters.regex(r"^panels:model:(.+)$"))
    async def model_page_cb(_, cq: CallbackQuery):
        slug = cq.data.split(":", 2)[-1]
        cfg = MODEL_CONFIG.get(slug)
        if not cfg:
            await cq.answer("Unknown model.", show_alert=True)
            return

        name = cfg["name"]
        menu_text = store.get_menu(name)

        if menu_text:
            body = f"<b>{name} — Menu</b>\n\n{menu_text}"
        else:
            body = (
                f"<b>{name} — Menu</b>\n\n"
                "No saved menu yet.\n"
                "Ask an admin to run:\n"
                f"<code>/createmenu {name} &lt;text...&gt;</code>"
            )

        kb = _model_keyboard(slug)
        try:
            await cq.message.edit_text(
                body,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # -------- Tip coming soon --------
    @app.on_callback_query(filters.regex(r"^panels:tip_coming$"))
    async def tip_coming_cb(_, cq: CallbackQuery):
        await cq.answer("💸 Tip support coming soon!", show_alert=True)

    # -------- No DM username set --------
    @app.on_callback_query(filters.regex(r"^panels:nodm$"))
    async def nodm_cb(_, cq: CallbackQuery):
        await cq.answer("No DM link set for this model yet. Please contact an admin.", show_alert=True)
