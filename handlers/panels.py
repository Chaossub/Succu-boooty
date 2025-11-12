# handlers/panels.py
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.menu_store import store  # only for the Menus picker; safe if Mongo down

log = logging.getLogger("handlers.panels")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b>\n"
    "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.\n\n"
    "✨ Use the menu below to navigate!"
)

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "Nothing here yet 💕")

def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
        [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
        [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
        [InlineKeyboardButton("❓ Help", callback_data="help:open")],
    ])

def _models_kb() -> InlineKeyboardMarkup:
    # Safe even if Mongo is unavailable (store falls back to JSON)
    names = store.list_names()
    rows = []
    if names:
        for n in names:
            rows.append([InlineKeyboardButton(n, callback_data=f"menus:show:{n}")])
    else:
        rows.append([InlineKeyboardButton("➕ Create a menu with /createmenu", callback_data="panels:noop")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="portal:home")])
    return InlineKeyboardMarkup(rows)

def register(app: Client):
    log.info("✅ handlers.panels registered (CI menu lookup)")

    # ---- /start (private) ----
    @app.on_message(filters.private & filters.command("start"))
    async def start_cmd(_, m):
        try:
            log.info("/start from uid=%s", getattr(m.from_user, "id", None))
            await m.reply_text(WELCOME_TEXT, reply_markup=_home_kb(), disable_web_page_preview=True)
        except Exception as e:
            log.exception("start_cmd failed: %s", e)

    # ---- open home from a button (used widely) ----
    @app.on_callback_query(filters.regex("^portal:home$|^panels:root$"))
    async def home_cb(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text(WELCOME_TEXT, reply_markup=_home_kb(), disable_web_page_preview=True)
        except Exception:
            # if message can't be edited (e.g., same text), reply instead
            await cq.message.reply_text(WELCOME_TEXT, reply_markup=_home_kb(), disable_web_page_preview=True)
        finally:
            await cq.answer()

    # ---- models elsewhere (backstop if not provided by help_panel) ----
    @app.on_callback_query(filters.regex("^models_elsewhere:open$"))
    async def models_elsewhere_cb(_, cq: CallbackQuery):
        try:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Main", callback_data="portal:home")]])
            await cq.message.edit_text(FIND_MODELS_TEXT or "Nothing here yet 💕", reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(FIND_MODELS_TEXT or "Nothing here yet 💕",
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Main", callback_data="portal:home")]]),
                                        disable_web_page_preview=True)
        finally:
            await cq.answer()

    # ---- no-op to swallow taps on informational rows ----
    @app.on_callback_query(filters.regex("^panels:noop$"))
    async def noop_cb(_, cq: CallbackQuery):
        await cq.answer("Use /createmenu to add one ✨", show_alert=False)

    # ---- Menus picker page (list) ----
    @app.on_callback_query(filters.regex("^menus:list$|^panels:menus$"))
    async def menus_list_cb(_, cq: CallbackQuery):
        try:
            await cq.message.edit_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=_models_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("📖 <b>Menus</b>\nTap a name to view.", reply_markup=_models_kb(), disable_web_page_preview=True)
        finally:
            await cq.answer()
