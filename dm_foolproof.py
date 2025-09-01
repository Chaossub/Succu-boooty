# dm_foolproof.py
# One-and-only /start handler + self-contained panels:
#   Main → Menus (2x2), Contact Admins, Find Models Elsewhere, Help
# Also marks DM-ready once and pings OWNER_ID. No external panel handlers required.

import os, time, logging
from typing import Dict, Tuple, List, Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType

# Optional menu persistence; falls back to ENV if missing
try:
    from utils.menu_store import MenuStore  # if you have it
    _menu_store = MenuStore()
except Exception:
    _menu_store = None

# DM-ready persistence (JSON store you already have)
from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")

# ── Env ───────────────────────────────────────────────────────────────────────
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "All verified links are pinned in the group.")
HELP_TEXT = os.getenv("HELP_TEXT", "Ask questions or tap buttons below.")

# Button labels
BTN_MENUS = os.getenv("BTN_MENU", "💕 Menus")  # keep "Menus" spelling you asked for
BTN_ADMINS = os.getenv("BTN_ADMINS", "👑 Contact Admins")
BTN_FIND = os.getenv("BTN_FIND", "🔥 Find Our Models Elsewhere")
BTN_HELP = os.getenv("BTN_HELP", "❓ Help")

# Admins panel content (simple placeholder text)
ADMINS_TEXT = os.getenv("ADMINS_TEXT", "• Tag an admin in chat\n• Or send an anonymous message via the bot.")

# Models from ENV (names + @usernames + optional ENV menu text)
# e.g. RONI_NAME, RONI_USERNAME, RONI_MENU etc.
def _collect_models() -> List[dict]:
    keys = ["RONI", "RUBY", "RIN", "SAVY"]
    models = []
    for k in keys:
        name = os.getenv(f"{k}_NAME")
        if not name:
            continue
        username = os.getenv(f"{k}_USERNAME")
        env_menu = os.getenv(f"{k}_MENU")
        models.append({"key": k.lower(), "name": name, "username": username, "env_menu": env_menu})
    return models

MODELS = _collect_models()

# ── DM-ready store ────────────────────────────────────────────────────────────
_ready = DMReadyStore()

# ── Minimal dedupe for rapid taps (per-chat+user) ────────────────────────────
_recent: Dict[Tuple[int, int], float] = {}
DEDUP_WINDOW = 2.5  # seconds

def _soon(chat_id: int, user_id: int) -> bool:
    now = time.time(); key = (chat_id, user_id)
    last = _recent.get(key, 0.0)
    if now - last < DEDUP_WINDOW:
        return True
    _recent[key] = now
    # prune occasionally
    if len(_recent) > 2000:
        stale = [k for k, ts in _recent.items() if now - ts > 5 * DEDUP_WINDOW]
        for k in stale:
            _recent.pop(k, None)
    return False

# ── UI builders ───────────────────────────────────────────────────────────────
WELCOME_TITLE = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

def _main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(BTN_MENUS,  callback_data="open:menus")],
        [InlineKeyboardButton(BTN_ADMINS, callback_data="open:admins")],
        [InlineKeyboardButton(BTN_FIND,   callback_data="open:models")],
        [InlineKeyboardButton(BTN_HELP,   callback_data="open:help")],
    ])

def _menus_kb() -> InlineKeyboardMarkup:
    rows = []
    row: List[InlineKeyboardButton] = []
    for m in MODELS:
        row.append(InlineKeyboardButton(f"💘 {m['name']}", callback_data=f"menus:{m['key']}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("💞 Contact Models", callback_data="menus:contact")])
    rows.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="open:main")])
    return InlineKeyboardMarkup(rows)

def _contact_models_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for m in MODELS:
        if m["username"]:
            rows.append([InlineKeyboardButton(f"💘 {m['name']} ↗", url=f"https://t.me/{m['username']}")])
    rows.append([InlineKeyboardButton("⬅️ Back to Menus", callback_data="open:menus")])
    return InlineKeyboardMarkup(rows)

def _menu_text_for(slot: str) -> str:
    # Priority: saved menu (utils/menu_store) → ENV fallback → placeholder
    if _menu_store:
        try:
            t = _menu_store.get_menu(slot)
            if t:
                return t
        except Exception:
            pass
    env_t = os.getenv(f"{slot.upper()}_MENU")
    if env_t:
        return env_t
    name = next((m["name"] for m in MODELS if m["key"] == slot), slot.capitalize())
    return f"No menu set for <b>{name}</b> yet."

# ── DM-ready marking ──────────────────────────────────────────────────────────
async def _mark_ready_once(client: Client, m: Message):
    if m.chat.type != ChatType.PRIVATE or not m.from_user or m.from_user.is_bot:
        return
    u = m.from_user
    if not _ready.is_ready(u.id):
        _ready.set_ready(u.id, username=u.username, first_name=u.first_name)
        if OWNER_ID:
            try:
                handle = f"@{u.username}" if u.username else ""
                await client.send_message(OWNER_ID, f"✅ DM-ready — {u.first_name or 'User'} {handle}")
            except Exception:
                pass

# ── Register ──────────────────────────────────────────────────────────────────
def register(app: Client):

    # /start (plain or with payload like /start d)
    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        await _mark_ready_once(client, m)
        if _soon(m.chat.id, m.from_user.id if m.from_user else 0):
            return
        await m.reply_text(WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True)

    # Main (back)
    @app.on_callback_query(filters.regex("^open:main$"))
    async def cb_main(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Menus
    @app.on_callback_query(filters.regex("^open:menus$"))
    async def cb_open_menus(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("💕 <b>Menus</b>\nPick a model or contact the team.", reply_markup=_menus_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("💕 <b>Menus</b>\nPick a model or contact the team.", reply_markup=_menus_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Menus → model slot or contact list
    @app.on_callback_query(filters.regex(r"^menus:(.+)$"))
    async def cb_model_or_contact(client: Client, cq: CallbackQuery):
        slot = (cq.data.split(":", 1)[1] or "").lower().strip()
        if slot == "contact":
            try:
                await cq.message.edit_text("💞 <b>Contact Models</b>", reply_markup=_contact_models_kb(), disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text("💞 <b>Contact Models</b>", reply_markup=_contact_models_kb(), disable_web_page_preview=True)
            await cq.answer(); return

        model = next((x for x in MODELS if x["key"] == slot), None)
        if not model:
            await cq.answer("Unknown model")
            return

        text = f"💘 <b>{model['name']}</b>\n{_menu_text_for(slot)}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menus", callback_data="open:menus")]])
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex("^open:admins$"))
    async def cb_admins(client: Client, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="open:main")]])
        try:
            await cq.message.edit_text(f"👑 <b>Contact Admins</b>\n\n{ADMINS_TEXT}", reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(f"👑 <b>Contact Admins</b>\n\n{ADMINS_TEXT}", reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # Find Our Models Elsewhere
    @app.on_callback_query(filters.regex("^open:models$"))
    async def cb_models_elsewhere(client: Client, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="open:main")]])
        try:
            await cq.message.edit_text(f"✨ <b>Find Our Models Elsewhere</b> ✨\n\n{FIND_MODELS_TEXT}", reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(f"✨ <b>Find Our Models Elsewhere</b> ✨\n\n{FIND_MODELS_TEXT}", reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # Help
    @app.on_callback_query(filters.regex("^open:help$"))
    async def cb_help(client: Client, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="open:main")]])
        try:
            await cq.message.edit_text(f"❓ <b>Help</b>\n\n{HELP_TEXT}", reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(f"❓ <b>Help</b>\n\n{HELP_TEXT}", reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()
