# dm_foolproof.py
# One single /start handler + main panel + lightweight Menus viewer.
# Also marks users DM-ready exactly once (persists to data/dmready.json).

import os, json, time, logging
from typing import Dict, Any, List, Tuple
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

log = logging.getLogger("dm_foolproof")

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")

# Optional Sanctuary groups (comma or space separated)
_SANCT = os.getenv("SANCTUARY_GROUP_IDS", "").replace(",", " ").split()
SANCTUARY_GROUP_IDS = [int(x) for x in _SANCT if x.strip()]

# Buttons (you can tweak labels via env if you like)
BTN_MENUS = os.getenv("BTN_MENU", "💕 Menu")
BTN_CONTACT = os.getenv("BTN_CONTACT", "👑 Contact Admins")
BTN_FIND = os.getenv("BTN_FIND", "🔥 Find Our Models Elsewhere")
BTN_HELP = os.getenv("BTN_HELP", "❓ Help")
BTN_BACK = "⬅️ Back to Main"

DATA_DIR = "data"
DMREADY_PATH = os.path.join(DATA_DIR, "dmready.json")
MENUS_PATH = os.path.join(DATA_DIR, "menus.json")

def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

def _load(path: str, default):
    _ensure_dirs()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save(path: str, obj):
    _ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _dm_store() -> Dict[str, Any]:
    return _load(DMREADY_PATH, {"users": {}})

def _dm_set_ready(user):
    store = _dm_store()
    u = {
        "id": user.id,
        "first_name": user.first_name or "",
        "username": user.username or "",
        "ts": int(time.time()),
    }
    if str(user.id) not in store["users"]:
        store["users"][str(user.id)] = u
        _save(DMREADY_PATH, store)
        return True  # newly added
    return False  # already known

def _dm_is_ready(user_id: int) -> bool:
    return str(user_id) in _dm_store().get("users", {})

def _dm_remove(user_id: int) -> bool:
    store = _dm_store()
    if str(user_id) in store.get("users", {}):
        store["users"].pop(str(user_id), None)
        _save(DMREADY_PATH, store)
        return True
    return False

def _dm_list() -> List[Dict[str, Any]]:
    store = _dm_store()
    out = list(store.get("users", {}).values())
    out.sort(key=lambda x: x.get("ts", 0))
    return out

def _main_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(BTN_MENUS, callback_data="portal:menus")],
        [InlineKeyboardButton(BTN_CONTACT, callback_data="portal:contact")],
        [InlineKeyboardButton(BTN_FIND, callback_data="portal:find")],
        [InlineKeyboardButton(BTN_HELP, callback_data="portal:help")],
    ]
    return InlineKeyboardMarkup(rows)

def _back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="portal:home")]])

WELCOME = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

FIND_ELSEWHERE = os.getenv(
    "FIND_ELSEWHERE_TEXT",
    "✨ <b>Find Our Models Elsewhere</b> ✨\n\n"
    "All verified off-platform links for our models are collected here. "
    "Check pinned messages or official posts for updates."
)

def _menus_caption() -> str:
    return "💕 <b>Menus</b>\nPick a model whose menu is saved."

def _menus_kb() -> InlineKeyboardMarkup:
    data = _load(MENUS_PATH, {})
    names_to_keys: List[Tuple[str, str]] = []
    # discover available menus by key
    for key, blob in data.items():
        label = blob.get("name") or key.title()
        names_to_keys.append((label, key))
    if not names_to_keys:
        # fallback to env names so buttons show up even if empty
        for key in ("roni", "ruby", "rin", "savy"):
            label = os.getenv(f"{key.upper()}_NAME")
            if label:
                names_to_keys.append((label, key))
    rows = []
    # 2-wide
    for i in range(0, len(names_to_keys), 2):
        row = []
        for label, key in names_to_keys[i:i+2]:
            row.append(InlineKeyboardButton(f"💘 {label}", callback_data=f"menus:show:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="portal:home")])
    return InlineKeyboardMarkup(rows)

def _menu_text_for(key: str) -> str:
    data = _load(MENUS_PATH, {})
    m = data.get(key)
    if m and (txt := m.get("text")):
        return txt
    # fallback text
    name = os.getenv(f"{key.upper()}_NAME", key.title())
    return f"No saved menu yet for <b>{name}</b>. Use /createmenu to save one."

async def _announce_dm_ready(client: Client, user):
    if OWNER_ID > 0:
        handle = f"@{user.username}" if user.username else str(user.id)
        msg = f"✅ <b>DM-ready</b> — {user.first_name} {handle}"
        try:
            await client.send_message(OWNER_ID, msg)
        except Exception as e:
            log.warning("Owner notify failed: %s", e)

def register(app: Client):

    # /start (handles deep-link args too)
    @app.on_message(filters.private & filters.command("start"))
    async def start(client: Client, m: Message):
        # Deep-link param (e.g. /start dmnow or /start menu)
        arg = ""
        if m.command and len(m.command) > 1:
            arg = (m.command[1] or "").strip().lower()

        # Mark DM-ready exactly once, and notify owner on first time only
        if not _dm_is_ready(m.from_user.id):
            if _dm_set_ready(m.from_user):
                log.info("DM-ready NEW user %s (%s)", m.from_user.id, m.from_user.first_name)
                await _announce_dm_ready(client, m.from_user)

        # Route deep-link
        if arg == "dmnow":
            # Just show main; the fact they arrived with dmnow is enough.
            pass
        elif arg == "menu":
            await m.reply_text(_menus_caption(), reply_markup=_menus_kb())
            return

        await m.reply_text(WELCOME, reply_markup=_main_kb())

    # Main hub buttons (edit in-place to avoid duplicates)
    @app.on_callback_query(filters.regex(r"^portal:(home|menus|contact|help|find)$"))
    async def portal_nav(client: Client, q: CallbackQuery):
        page = q.data.split(":", 1)[1]
        try:
            if page == "home":
                await q.message.edit_text(WELCOME, reply_markup=_main_kb())
            elif page == "menus":
                await q.message.edit_text(_menus_caption(), reply_markup=_menus_kb())
            elif page == "help":
                # hand off to help handler via callback
                from handlers.help_panel import render_help
                await render_help(client, q.message, edit=True)
            elif page == "contact":
                from handlers.contact_admins import render_contact
                await render_contact(client, q.message, edit=True)
            elif page == "find":
                await q.message.edit_text(FIND_ELSEWHERE, reply_markup=_back_kb(), disable_web_page_preview=True)
        except Exception:
            # If the message is too old to edit, just send a new one
            if page == "home":
                await q.message.reply_text(WELCOME, reply_markup=_main_kb())
            elif page == "menus":
                await q.message.reply_text(_menus_caption(), reply_markup=_menus_kb())
            elif page == "help":
                from handlers.help_panel import render_help
                await render_help(client, q.message, edit=False)
            elif page == "contact":
                from handlers.contact_admins import render_contact
                await render_contact(client, q.message, edit=False)
            elif page == "find":
                await q.message.reply_text(FIND_ELSEWHERE, reply_markup=_back_kb(), disable_web_page_preview=True)
        await q.answer()

    # Menus → model buttons
    @app.on_callback_query(filters.regex(r"^menus:show:([a-z0-9_]+)$"))
    async def show_menu(client: Client, q: CallbackQuery):
        key = q.data.split(":", 2)[2]
        text = _menu_text_for(key)
        try:
            await q.message.edit_text(text, reply_markup=_back_kb(), disable_web_page_preview=True)
        except Exception:
            await q.message.reply_text(text, reply_markup=_back_kb(), disable_web_page_preview=True)
        await q.answer()

    # Utility used by cleanup handler (imported there)
    async def _remove_dm_ready_if_present(user_id: int):
        if _dm_remove(user_id):
            if OWNER_ID > 0:
                try:
                    await app.send_message(OWNER_ID, f"🧹 Removed DM-ready (left/kicked/banned): <code>{user_id}</code>")
                except Exception:
                    pass

    # expose to other modules
    app._succu_dm_store_remove = _remove_dm_ready_if_present  # type: ignore

    log.info("dm_foolproof wired")
