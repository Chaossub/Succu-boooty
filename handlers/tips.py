# handlers/tips.py
#
# Handles "💸 Tip" button clicks from panels.py.
# It looks up a Stripe (or any) payment link from env vars and
# shows a small panel with a Pay Tip button.

import os
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger(__name__)

# Env:
#   TIP_URL_RONI, TIP_URL_RUBY, TIP_URL_RIN, TIP_URL_SAVY
#   DEFAULT_TIP_URL (optional fallback)


def _tip_url_for(slug: str) -> str | None:
    """
    Resolve the tip URL for a model based on its slug.
    Slugs: roni, ruby, rin, savy
    """
    if not slug:
        return None

    key = slug.upper()  # "roni" -> "RONI"
    per_model = os.getenv(f"TIP_URL_{key}")
    if per_model and per_model.strip():
        return per_model.strip()

    default = os.getenv("DEFAULT_TIP_URL")
    if default and default.strip():
        return default.strip()

    return None


def _tip_keyboard(slug: str, url: str) -> InlineKeyboardMarkup:
    """
    Keyboard for the tip panel: one Pay Tip button + a Back button to the model panel.
    """
    rows = [
        [InlineKeyboardButton("💸 Pay Tip", url=url)],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="panels:menus"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="panels:root"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def register(app: Client):
    log.info("✅ handlers.tips registered")

    # tip:<slug>   e.g. tip:roni, tip:ruby, tip:rin, tip:savy
    @app.on_callback_query(filters.regex(r"^tip:(.+)$"))
    async def open_tip_panel(_, cq: CallbackQuery):
        slug = cq.data.split(":", 1)[1]  # after "tip:"
        url = _tip_url_for(slug)

        if not url:
            # No URL configured for this model (and no default)
            await cq.answer(
                "No tip link is set up for this model yet. Please contact an admin.",
                show_alert=True,
            )
            return

        # Nice little text above the button
        text = (
            "💸 <b>Tip Jar</b>\n\n"
            "Tap the button below to open a secure payment page.\n"
            "Thank you for spoiling us 😘"
        )

        kb = _tip_keyboard(slug, url)

        try:
            await cq.message.edit_text(
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception as e:
            # Fallback if edit fails (e.g. MESSAGE_NOT_MODIFIED)
            log.warning("Failed to edit tip panel message: %s", e)
            await cq.message.reply_text(
                text,
                reply_markup=kb,
                disable_web_page_preview=True,
            )

        await cq.answer()
