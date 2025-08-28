# dm_foolproof.py
# Single source for /start:
# - Shows main panel (de-duped)
# - Marks DM-ready (persisted via utils.dmready_store)
# - Menus read from utils.menu_store first; fallback to ENV (RONI_MENU, etc.)
# - Handles all panel callbacks here (so buttons always work)

import os, time
from typing import Dict, Tuple, List, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType

from utils.menu_store import MenuStore

# DM-ready persistence
try:
    from utils.dmready_store import DMReadyStore
    _dm = DMReadyStore()
except Exception:
    class _MemDM:
        def __init__(self): self._g=set()
        def set_dm_ready_global(self, uid:int, username=None, first=None): new = uid not in self._g; self._g.add(uid); return new
        def is_dm_ready_global(self, uid:int)->bool: return uid in self._g
    _dm = _MemDM()

OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "All verified links are pinned in the group.")
HELP_TEXT = os.getenv("HELP_TEXT", "Ask questions or tap buttons below.")

WELCOME_TITLE = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)
MENUS_TITLE  = "💕 <b>Menus</b>\nPick a model or contact the team."
ADMINS_TITLE = "👑 <b>Contact Admins</b>"
MODELS_TITLE = "✨ <b>Find Our Models Elsewhere</b> ✨"
HELP_TITLE   = "❓ <b>Help</b>"

# Debounce duplicate /start
_recent: Dict[Tuple[int,int], float] = {}
DEDUP_WINDOW = 10.0
def _soon(chat:int, user:int)->bool:
    now=time.time(); k=(chat,user)
    if now-_recent.get(k,0)<DEDUP_WINDOW: return True
    _recent[k]=now; 
    # prune a bit
    for kk, ts in list(_recent.items()):
        if now-ts>5*DEDUP_WINDOW: _recent.pop(kk, None)
    return False

# Models from ENV
def _collect_models() -> List[dict]:
    models=[]
    for key in ["RONI","RUBY","RIN","SAVY"]:
        name = os.getenv(f"{key}_NAME")
        if not name: continue
        username = os.getenv(f"{key}_USERNAME")
        env_menu = os.getenv(f"{key}_MENU")
        models.append({"key": key.lower(),"name": name,"username": username,"env_menu": env_menu})
    return models

MODELS = _collect_models()
_store = MenuStore()

def _main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="open:menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="open:admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="open:models")],
        [InlineKeyboardButton("❓ Help", callback_data="open:help")]
    ])

def _menus_kb():
    rows=[]; row=[]
    for m in MODELS:
        row.append(InlineKeyboardButton(f"💘 {m['name']}", callback_data=f"menus:{m['key']}"))
        if len(row)==2: rows.append(row); row=[]
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("💞 Contact Models", callback_data="menus:contact")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="open:main")])
    return InlineKeyboardMarkup(rows)

def _contact_models_kb():
    rows=[]
    for m in MODELS:
        if m["username"]:
            rows.append([InlineKeyboardButton(f"💌 Message {m['name']}", url=f"https://t.me/{m['username']}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="open:menus")])
    return InlineKeyboardMarkup(rows)

async def _mark_dm_ready(client:Client, m:Message):
    if m.chat.type!=ChatType.PRIVATE or (m.from_user and m.from_user.is_bot): return
    u=m.from_user
    first=_dm.set_dm_ready_global(u.id, u.username, u.first_name)
    if first and OWNER_ID:
        handle=f"@{u.username}" if u.username else ""
        try:
            await client.send_message(OWNER_ID,f"✅ DM-ready — {u.first_name} {handle}")
        except Exception:
            pass

def _menu_text_for(key:str)->str:
    # Saved store first
    txt = None
    try:
        txt = _store.get_menu(key)
    except Exception:
        txt = None
    if not txt:
        # ENV fallback e.g., RONI_MENU
        txt = os.getenv(f"{key.upper()}_MENU")
    if not txt:
        model_name = next((m["name"] for m in MODELS if m["key"]==key), key.capitalize())
        txt = f"No menu set for <b>{model_name}</b> yet."
    return txt

def register(app:Client):

    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client, m:Message):
        await _mark_dm_ready(client,m)
        if _soon(m.chat.id, m.from_user.id if m.from_user else 0): 
            return
        await m.reply_text(WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex("^open:main$"))
    async def cb_main(client,cq:CallbackQuery):
        try:
            await cq.message.edit_text(WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TITLE, reply_markup=_main_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex("^open:menus$"))
    async def cb_menus(client,cq:CallbackQuery):
        try:
            await cq.message.edit_text(MENUS_TITLE, reply_markup=_menus_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(MENUS_TITLE, reply_markup=_menus_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex("^open:admins$"))
    async def cb_admins(client,cq:CallbackQuery):
        text = f"{ADMINS_TITLE}\n\n• Tag an admin in chat\n• Or send an anonymous message via the bot."
        try:
            await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="open:main")]]), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="open:main")]]), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex("^open:models$"))
    async def cb_models(client,cq:CallbackQuery):
        text = f"{MODELS_TITLE}\n\n{FIND_MODELS_TEXT}"
        try:
            await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="open:main")]]), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="open:main")]]), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex("^open:help$"))
    async def cb_help(client,cq:CallbackQuery):
        text = f"{HELP_TITLE}\n\n{HELP_TEXT}"
        try:
            await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="open:main")]]), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="open:main")]]), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menus:(.+)$"))
    async def cb_model_menu(client,cq:CallbackQuery):
        slot=(cq.data.split(":",1)[1] or "").lower().strip()
        if slot=="contact":
            try:
                await cq.message.edit_text("💞 <b>Contact Models</b>\nPick who you’d like to message.", reply_markup=_contact_models_kb(), disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text("💞 <b>Contact Models</b>\nPick who you’d like to message.", reply_markup=_contact_models_kb(), disable_web_page_preview=True)
            await cq.answer(); return

        m=next((x for x in MODELS if x["key"]==slot),None)
        if not m: 
            await cq.answer("Unknown model."); 
            return
        menu_text = _menu_text_for(slot)
        text=f"💘 <b>{m['name']}</b>\n{menu_text}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menus", callback_data="open:menus")]])
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()
