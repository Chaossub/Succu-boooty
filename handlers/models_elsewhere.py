# handlers/models_elsewhere.py
import os
import logging

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import MessageNotModified

log = logging.getLogger(__name__)

# ✅ You already use FIND_MODELS_TEXT on Render.
# We also accept aliases so you can rename later without breaking the button.
_ENV_KEYS = [
    "FIND_MODELS_TEXT",          # your current env key
    "FIND_MODELS_ELSEWHERE_TEXT",
    "MODELS_ELSEWHERE_TEXT",
    "FIND_OUR_MODELS_ELSEWHERE_TEXT",
    "MODELS_ELSEWHERE",
]

_DEFAULT_TEXT = (
    "<b>🍑 Find Our Models Elsewhere</b>\n\n"
    "Links aren’t set yet.\n\n"
    "Admin note: set <code>FIND_MODELS_TEXT</code> in your Render env to override this whole message."
)


def _get_text() -> str:
    for k in _ENV_KEYS:
        v = os.getenv(k)
        if v and str(v).strip():
            return str(v).strip()
    return _DEFAULT_TEXT


async def _safe_edit(msg: Message, text: str, kb: InlineKeyboardMarkup):
    try:
        return await msg.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except MessageNotModified:
        return msg


def register(app: Client):
    log.info("✅ handlers.models_elsewhere registered (callback models_elsewhere:open)")

    @app.on_callback_query(filters.regex(r"^models_elsewhere:open$"))
    async def open_cb(_, cq: CallbackQuery):
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="panels:root")]]
        )
        await cq.answer()
        await _safe_edit(cq.message, _get_text(), kb)

    # Optional DM command for quick testing
    @app.on_message(filters.private & filters.command(["models", "elsewhere", "modelselsewhere"]))
    async def cmd(_, m: Message):
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="panels:root")]]
        )
        await m.reply_text(_get_text(), reply_markup=kb, disable_web_page_preview=True)
