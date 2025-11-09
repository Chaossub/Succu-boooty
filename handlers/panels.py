# handlers/panels.py
import os
import time
from typing import Dict, Optional

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified, BadRequest
from pymongo import MongoClient

# ── Mongo (shared with menu storage)
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
DB_NAME   = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"
_mcli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
_db   = _mcli[DB_NAME]
col_model_menus = _db.get_collection("model_menus")
col_anon        = _db.get_collection("anon_sessions")

def _int_or_zero(v: Optional[str]) -> int:
    try:
        return int(v) if v else 0
    except ValueError:
        return 0

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

# ── Small helpers
def _tg_url(username: str) -> str:
    return f"https://t.me/{username}" if username else "https://t.me/"

async def _safe_edit(msg, text: str, **kwargs):
    """
    Edit text safely; if text is unchanged, try updating only the reply_markup.
    Silences 'message not modified' churn.
    """
    try:
        return await msg.edit_text(text, **kwargs)
    except MessageNotModified:
        if "reply_markup" in kwargs:
            try:
                return await msg.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified:
                return
        return
    except BadRequest:
        if "reply_markup" in kwargs:
            try:
                return await msg.edit_reply_markup(kwargs["reply_markup"])
            except Exception:
                pass
        return

# ── Keyboards
def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

def _menus_kb() -> InlineKeyboardMarkup:
    order = ["roni", "ruby", "rin", "savy"]
    btns = [InlineKeyboardButton(MODELS[k]["name"], callback_data=f"menu:{k}") for k in order]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
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
        [InlineKeyboardButton("💬 Contact Roni", url=_tg_url(os.getenv("RONI_USERNAME", "")))],
        [InlineKeyboardButton("💬 Contact Ruby", url=_tg_url(os.getenv("RUBY_USERNAME", "")))],
        [InlineKeyboardButton("🕵️ Send Anonymous Message", callback_data="anon:start")],
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

# ── Welcome copy (shown on /start and when pressing Home)
WELCOME_TEXT = (
    "🔥 **Welcome to SuccuBot** 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "😈 If you ever need to know exactly what I can do, just press the Help button and I’ll spill all my secrets… 💋"
)

def register(app: Client):
    # ── /start should only render the panel here.
    # (dm_ready.py can mark DM-ready silently; it must not reply.)
    @app.on_message(filters.private & filters.command("start"))
    async def _start_panel(_: Client, m):
        await m.reply_text(WELCOME_TEXT, reply_markup=_home_kb(), disable_web_page_preview=True)

    # ── Home / Main (redraw welcome + main buttons)
    @app.on_callback_query(filters.regex(r"^home$"))
    async def _home(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, WELCOME_TEXT, reply_markup=_home_kb(), disable_web_page_preview=True)

    # ── Menus hub
    @app.on_callback_query(filters.regex(r"^menus$"))
    async def _show_menus(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "💕 Choose a model:", reply_markup=_menus_kb())

    # ── A model’s menu
    @app.on_callback_query(filters.regex(r"^menu:(roni|ruby|rin|savy)$"))
    async def _show_model_menu(_: Client, q: CallbackQuery):
        key = q.matches[0].group(1)
        meta = MODELS[key]
        doc = col_model_menus.find_one({"key": key})

        if not doc:
            await _safe_edit(q.message,
                             f"{meta['name']}'s menu has not been set yet.",
                             reply_markup=_menus_kb())
            return

        title = f"**{meta['name']} — Menu**"
        body = (doc.get("text") or "").strip()
        caption = f"{title}\n\n{body}" if body else title
        photo_id = doc.get("photo_id")

        if photo_id:
            try:
                await q.message.delete()
            except Exception:
                pass
            await q.message.reply_photo(
                photo=photo_id,
                caption=caption,
                reply_markup=_model_menu_kb(key, meta["username"]),
            )
        else:
            await _safe_edit(
                q.message,
                caption,
                reply_markup=_model_menu_kb(key, meta["username"]),
                disable_web_page_preview=True,
            )

    # ── Tip placeholder
    @app.on_callback_query(filters.regex(r"^tip:(roni|ruby|rin|savy)$"))
    async def _tip_stub(_: Client, q: CallbackQuery):
        await q.answer("💸 Tips: coming soon!", show_alert=True)

    # ── Admins / anon DM
    @app.on_callback_query(filters.regex(r"^admins$"))
    async def _show_admins(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "👑 Contact Admins", reply_markup=_admins_kb())

    @app.on_callback_query(filters.regex(r"^anon:start$"))
    async def _start_anon(_: Client, q: CallbackQuery):
        # mark user in anon session collection
        col_anon.update_one(
            {"user_id": q.from_user.id},
            {"$set": {"user_id": q.from_user.id, "ts": int(time.time())}},
            upsert=True
        )
        await _safe_edit(
            q.message,
            "🕵️ **Anonymous message mode**\n\n"
            "Send me the message now. I’ll forward it anonymously to the owner.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admins")],
                [InlineKeyboardButton("🏠 Main", callback_data="home")]
            ]),
            disable_web_page_preview=True
        )

    @app.on_message(filters.private & filters.incoming & ~filters.service)
    async def _anon_capture(c: Client, m):
        if not m.from_user:
            return
        if not col_anon.find_one({"user_id": m.from_user.id}):
            return
        owner_id = int(os.getenv("OWNER_ID", "0") or 0)
        try:
            await c.copy_message(owner_id, from_chat_id=m.chat.id, message_id=m.id)
            await m.reply_text("✅ Sent anonymously to the owner.")
        finally:
            col_anon.delete_one({"user_id": m.from_user.id})

    # ── Find our models elsewhere
    @app.on_callback_query(filters.regex(r"^models$"))
    async def _show_elsewhere(_: Client, q: CallbackQuery):
        text = (os.getenv("FIND_MODELS_TEXT") or "Set FIND_MODELS_TEXT in ENV.").strip()
        await _safe_edit(q.message, text, reply_markup=_back_main_kb(), disable_web_page_preview=True)

    # ── Help + subpages
    @app.on_callback_query(filters.regex(r"^help$"))
    async def _show_help(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "❓ Help", reply_markup=_help_kb())

    @app.on_callback_query(filters.regex(r"^help:reqs$"))
    async def _h_reqs(_: Client, q: CallbackQuery):
        text = os.getenv("BUYER_REQUIREMENTS_TEXT") or "Set BUYER_REQUIREMENTS_TEXT in ENV."
        await _safe_edit(q.message, f"🧾 **Buyer Requirements**\n\n{text}",
                         reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:rules$"))
    async def _h_rules(_: Client, q: CallbackQuery):
        text = os.getenv("BUYER_RULES_TEXT") or "Set BUYER_RULES_TEXT in ENV."
        await _safe_edit(q.message, f"📜 **Buyer Rules**\n\n{text}",
                         reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:games$"))
    async def _h_games(_: Client, q: CallbackQuery):
        text = os.getenv("GAME_RULES_TEXT") or "Set GAME_RULES_TEXT in ENV."
        await _safe_edit(q.message, f"🎲 **Game Rules**\n\n{text}",
                         reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:ex$"))
    async def _h_ex(_: Client, q: CallbackQuery):
        text = os.getenv("EXEMPTIONS_TEXT") or "Set EXEMPTIONS_TEXT in ENV."
        await _safe_edit(q.message, f"🕊️ **Exemptions**\n\n{text}",
                         reply_markup=_sub_kb(), disable_web_page_preview=True)
