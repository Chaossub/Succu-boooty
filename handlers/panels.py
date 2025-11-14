# handlers/panels.py
import logging
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

# Static model config: slug -> {name, username}
MODEL_CONFIG: Dict[str, Dict[str, str]] = {
    "roni": {"name": "Roni", "username": "your_roni_username_here"},
    "ruby": {"name": "Ruby", "username": "your_ruby_username_here"},
    "rin":  {"name": "Rin",  "username": "your_rin_username_here"},
    "savy": {"name": "Savy", "username": "your_savy_username_here"},
}


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💞 Menus", callback_data="panels:menus")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
        ]
    )


def _models_keyboard() -> InlineKeyboardMarkup:
    # 2x2 grid of names
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

    # If we have a username, book = URL button; otherwise callback that just alerts.
    if username:
        book_button = InlineKeyboardButton(
            "📩 Book", url=f"https://t.me/{username}"
        )
    else:
        book_button = InlineKeyboardButton(
            "📩 Book", callback_data="panels:nodm"
        )

    rows = [
        [book_button],
        # 🔥 Tip button now routes to stripe_tips handler
        [InlineKeyboardButton("💸 Tip", callback_data=f"panels:tip:{slug}")],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="panels:menus"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="panels:root"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def register(app: Client):
    log.info("✅ handlers.panels registered (static 4-model panel, MenuStore=%s)", store.uses_mongo())

    # -------- /start --------
    @app.on_message(filters.command("start"))
    async def start_cmd(_, m: Message):
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
            # If Telegram complains "MESSAGE_NOT_MODIFIED", just ignore.
            pass
        await cq.answer()

    # -------- Main/root from callbacks --------
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

    # -------- Model page --------
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
                f"No saved menu yet.\n"
                f"Ask an admin to run:\n"
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

    # -------- No DM username set --------
    @app.on_callback_query(filters.regex(r"^panels:nodm$"))
    async def nodm_cb(_, cq: CallbackQuery):
        await cq.answer("No DM link set for this model yet. Please contact an admin.", show_alert=True)
