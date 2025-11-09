# handlers/panels.py
import os, time
from typing import Dict, Optional
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import MessageNotModified, BadRequest

# bring in the DM-ready helper (DO NOT register /start here)
from handlers.dm_ready import mark_dm_ready_from_message

def _int_or_zero(v: Optional[str]) -> int:
    try: return int(v) if v else 0
    except ValueError: return 0

# ------- Models (for Menus page) -------
MODELS: Dict[str, Dict] = {
    "roni": {"name": os.getenv("RONI_NAME", "Roni"),
             "username": os.getenv("RONI_USERNAME", ""),
             "uid": _int_or_zero(os.getenv("RONI_ID"))},
    "ruby": {"name": os.getenv("RUBY_NAME", "Ruby"),
             "username": os.getenv("RUBY_USERNAME", ""),
             "uid": _int_or_zero(os.getenv("RUBY_ID"))},
    "rin":  {"name": os.getenv("RIN_NAME", "Rin"),
             "username": os.getenv("RIN_USERNAME", ""),
             "uid": _int_or_zero(os.getenv("RIN_ID"))},
    "savy": {"name": os.getenv("SAVY_NAME", "Savy"),
             "username": os.getenv("SAVY_USERNAME", ""),
             "uid": _int_or_zero(os.getenv("SAVY_ID"))},
}

def _tg_url(username: str) -> str:
    return f"https://t.me/{username}" if username else "https://t.me/"

async def _safe_edit(msg, text: str, **kwargs):
    try:
        return await msg.edit_text(text, **kwargs)
    except MessageNotModified:
        if "reply_markup" in kwargs:
            try: return await msg.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified: return
        return
    except BadRequest:
        if "reply_markup" in kwargs:
            try: return await msg.edit_reply_markup(kwargs["reply_markup"])
            except Exception: pass
        return

# -------- Keyboards --------
def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("🫶 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

def _menus_kb() -> InlineKeyboardMarkup:
    order = ["roni","ruby","rin","savy"]
    btns = [InlineKeyboardButton(MODELS[k]["name"], callback_data=f"menu:{k}") for k in order]
    rows = [btns[i:i+2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="home"),
                 InlineKeyboardButton("🏠 Main", callback_data="home")])
    return InlineKeyboardMarkup(rows)

def _model_menu_kb(model_key: str, username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Book", url=_tg_url(username))],
        [InlineKeyboardButton("💸 Tip", callback_data=f"tip:{model_key}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
    ])

def _admins_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact Roni", url=_tg_url(os.getenv("RONI_USERNAME","")))],
        [InlineKeyboardButton("💬 Contact Ruby", url=_tg_url(os.getenv("RUBY_USERNAME","")))],
        [InlineKeyboardButton("⬅️ Back", callback_data="home"),
         InlineKeyboardButton("🏠 Main", callback_data="home")],
    ])

def _help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Buyer Requirements", callback_data="help:reqs")],
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help:rules")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="help:games")],
        [InlineKeyboardButton("🕊️ Exemptions", callback_data="help:ex")],
        [InlineKeyboardButton("⬅️ Back", callback_data="home"),
         InlineKeyboardButton("🏠 Main", callback_data="home")],
    ])

def _sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="help")],
        [InlineKeyboardButton("🏠 Main", callback_data="home")],
    ])

def _back_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="home"),
         InlineKeyboardButton("🏠 Main", callback_data="home")]
    ])

# -------- Handlers --------
def register(app: Client):

    # The ONLY /start handler: shows the welcome + buttons,
    # and also records DM-ready first-seen (idempotent)
    @app.on_message(filters.private & filters.command("start"))
    async def _start_panel(c: Client, m: Message):
        # mark DM-ready once (persists; works with Mongo or JSON)
        await mark_dm_ready_from_message(m)

        text = (
            "🔥 **Welcome to SuccuBot** 🔥\n"
            "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
            "✨ Use the menu below to navigate!"
        )
        await m.reply_text(
            text,
            reply_markup=_home_kb(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^home$"))
    async def _home(_: Client, q: CallbackQuery):
        await _safe_edit(q.message,
                         "💕 **Main Menu**\nChoose an option:",
                         reply_markup=_home_kb(),
                         disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^menus$"))
    async def _show_menus(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "💕 Choose a model:", reply_markup=_menus_kb())

    @app.on_callback_query(filters.regex(r"^menu:(roni|ruby|rin|savy)$"))
    async def _show_model_menu(_: Client, q: CallbackQuery):
        key = q.matches[0].group(1)
        meta = MODELS[key]
        title = f"**{meta['name']} — Menu**"
        body  = (os.getenv(f"{key.upper()}_MENU_TEXT") or "").strip()
        caption = f"{title}\n\n{body}" if body else title

        await _safe_edit(
            q.message,
            caption,
            reply_markup=_model_menu_kb(key, meta["username"]),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^tip:(roni|ruby|rin|savy)$"))
    async def _tip_stub(_: Client, q: CallbackQuery):
        await q.answer("💸 Tips: coming soon!", show_alert=True)

    @app.on_callback_query(filters.regex(r"^admins$"))
    async def _show_admins(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "👑 Contact Admins", reply_markup=_admins_kb())

    @app.on_callback_query(filters.regex(r"^models$"))
    async def _show_elsewhere(_: Client, q: CallbackQuery):
        text = (os.getenv("FIND_MODELS_TEXT") or "Set FIND_MODELS_TEXT in ENV.").strip()
        await _safe_edit(q.message, text, reply_markup=_back_main_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help$"))
    async def _show_help(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "❓ Help", reply_markup=_help_kb())

    @app.on_callback_query(filters.regex(r"^help:reqs$"))
    async def _h_reqs(_: Client, q: CallbackQuery):
        text = os.getenv("BUYER_REQUIREMENTS_TEXT") or "Set BUYER_REQUIREMENTS_TEXT in ENV."
        await _safe_edit(q.message, f"🧾 **Buyer Requirements**\n\n{text}", reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:rules$"))
    async def _h_rules(_: Client, q: CallbackQuery):
        text = os.getenv("BUYER_RULES_TEXT") or "Set BUYER_RULES_TEXT in ENV."
        await _safe_edit(q.message, f"📜 **Buyer Rules**\n\n{text}", reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:games$"))
    async def _h_games(_: Client, q: CallbackQuery):
        text = os.getenv("GAME_RULES_TEXT") or "Set GAME_RULES_TEXT in ENV."
        await _safe_edit(q.message, f"🎲 **Game Rules**\n\n{text}", reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:ex$"))
    async def _h_ex(_: Client, q: CallbackQuery):
        text = os.getenv("EXEMPTIONS_TEXT") or "Set EXEMPTIONS_TEXT in ENV."
        await _safe_edit(q.message, f"🕊️ **Exemptions**\n\n{text}", reply_markup=_sub_kb(), disable_web_page_preview=True)

