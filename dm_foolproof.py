# dm_foolproof.py
# Single /start entry + self-contained panels (no other panel handlers needed).

import os, time, logging
from typing import Dict, Tuple, List, Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType

# Optional menu persistence (safe if missing)
try:
    from utils.menu_store import MenuStore
    _menu_store = MenuStore()
except Exception:
    _menu_store = None

from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

FIND_MODELS_TEXT = os.getenv(
    "FIND_MODELS_TEXT",
    "All verified off-platform links are collected here. Check pins or official posts for updates."
)
HELP_TEXT = os.getenv("HELP_TEXT", "Tap a button above, or ask an admin if you’re stuck.")

BTN_MENUS  = os.getenv("BTN_MENU", "💕 Menus")
BTN_ADMINS = os.getenv("BTN_ADMINS", "👑 Contact Admins")
BTN_FIND   = os.getenv("BTN_FIND", "🔥 Find Our Models Elsewhere")
BTN_HELP   = os.getenv("BTN_HELP", "❓ Help")

ADMINS_TEXT = os.getenv(
    "ADMINS_TEXT",
    "• Tag an admin in chat\n• Or send an anonymous message via the bot."
)

def _collect_models() -> List[dict]:
    keys = ["RONI", "RUBY", "RIN", "SAVY"]
    models = []
    for k in keys:
        name = os.getenv(f"{k}_NAME")
        if not name:
            continue
        username = os.getenv(f"{k}_USERNAME")  # optional @username (no @ needed)
        env_menu = os.getenv(f"{k}_MENU")
        models.append({"key": k.lower(), "name": name, "username": username, "env_menu": env_menu})
    return models

MODELS = _collect_models()

_ready = DMReadyStore()

# ── throttle + single-panel control ───────────────────────────────────────────
_user_last_ts: Dict[int, float] = {}
_user_panel_msg: Dict[int, int] = {}  # user_id -> message_id
DEDUP_WINDOW = 5.0  # seconds

def _throttle(uid: int) -> bool:
    now = time.time()
    last = _user_last_ts.get(uid, 0.0)
    if now - last < DEDUP_WINDOW:
        return True
    _user_last_ts[uid] = now
    return False

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
    rows: List[List[InlineKeyboardButton]] = []
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
    if _menu_store:
        try:
            t = _menu_store.get_menu(slot)
            if t:
                return t
        except Exception as e:
            log.warning("menu_store.get_menu(%s) failed: %s", slot, e)
    env_t = os.getenv(f"{slot.upper()}_MENU")
    if env_t:
        return env_t
    name = next((m["name"] for m in MODELS if m["key"] == slot), slot.capitalize())
    return f"No menu set for <b>{name}</b> yet."

async def _mark_dm_ready_once(client: Client, m: Message):
    if m.chat.type != ChatType.PRIVATE or not m.from_user or m.from_user.is_bot:
        return
    u = m.from_user
    if not _ready.is_ready(u.id):
        _ready.set_ready(u.id, username=u.username, first_name=u.first_name)
        if OWNER_ID:
            try:
                handle = f"@{u.username}" if u.username else ""
                await client.send_message(OWNER_ID, f"✅ DM-ready — {u.first_name or 'User'} {handle}")
            except Exception as e:
                log.warning("owner ping failed: %s", e)

async def _show_or_edit_main(client: Client, uid: int, chat_id: int):
    """Edit an existing panel for this user if possible; otherwise send one."""
    msg_id = _user_panel_msg.get(uid)
    if msg_id:
        try:
            await client.edit_message_text(
                chat_id, msg_id,
                WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True
            )
            return
        except Exception as e:
            # message may be gone; fall through to send a fresh one
            log.debug("edit panel failed for %s: %s", uid, e)
    sent = await client.send_message(
        chat_id, WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True
    )
    _user_panel_msg[uid] = sent.id

# ── register ──────────────────────────────────────────────────────────────────
def register(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        await _mark_dm_ready_once(client, m)
        if _throttle(uid):
            # Even if throttled, ensure we have a single live panel
            try:
                await _show_or_edit_main(client, uid, m.chat.id)
            except Exception:
                pass
            return
        await _show_or_edit_main(client, uid, m.chat.id)

    @app.on_callback_query(filters.regex(r"^open:main$"))
    async def cb_main(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _user_panel_msg[uid] = cq.message.id
        try:
            await cq.message.edit_text(WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True)
        except Exception as e:
            log.debug("edit main failed: %s", e)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^open:menus$"))
    async def cb_open_menus(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _user_panel_msg[uid] = cq.message.id
        try:
            await cq.message.edit_text("💕 <b>Menus</b>\nPick a model or contact the team.",
                                       reply_markup=_menus_kb(), disable_web_page_preview=True)
        except Exception as e:
            log.debug("edit menus failed: %s", e)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menus:(.+)$"))
    async def cb_menus_branch(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _user_panel_msg[uid] = cq.message.id
        slot = (cq.data.split(":", 1)[1] or "").lower().strip()
        if slot == "contact":
            try:
                await cq.message.edit_text("💞 <b>Contact Models</b>",
                                           reply_markup=_contact_models_kb(), disable_web_page_preview=True)
            except Exception as e:
                log.debug("edit contact models failed: %s", e)
            await cq.answer(); return

        model = next((x for x in MODELS if x["key"] == slot), None)
        if not model:
            await cq.answer("Unknown model"); return

        text = f"💘 <b>{model['name']}</b>\n{_menu_text_for(slot)}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menus", callback_data="open:menus")]])
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            log.debug("edit model menu failed: %s", e)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^open:admins$"))
    async def cb_admins(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _user_panel_msg[uid] = cq.message.id
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="open:main")]])
        try:
            await cq.message.edit_text(f"👑 <b>Contact Admins</b>\n\n{ADMINS_TEXT}",
                                       reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            log.debug("edit admins failed: %s", e)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^open:models$"))
    async def cb_models_elsewhere(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _user_panel_msg[uid] = cq.message.id
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="open:main")]])
        try:
            await cq.message.edit_text(f"✨ <b>Find Our Models Elsewhere</b> ✨\n\n{FIND_MODELS_TEXT}",
                                       reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            log.debug("edit models elsewhere failed: %s", e)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^open:help$"))
    async def cb_help(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        _user_panel_msg[uid] = cq.message.id
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="open:main")]])
        try:
            await cq.message.edit_text(f"❓ <b>Help</b>\n\n{HELP_TEXT}",
                                       reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            log.debug("edit help failed: %s", e)
        await cq.answer()
