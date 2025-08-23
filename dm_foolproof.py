# dm_foolproof.py
# DM portal (root): /start portal + DM-ready flag + Contact Admins + Contact Models + Links + Help
# - Marks users DM-ready once and notifies admins once.
# - Buttons for both admins (Roni & Ruby) and for contacting models directly.
# - /dmreadylist shows all DM-ready users (owner/super-admin only).

import os
from typing import List, Optional
from contextlib import suppress

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

# ---------- store ----------
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

# ---------- env helpers ----------
def _to_int(x: Optional[str]) -> Optional[int]:
    try:
        return int(str(x)) if x not in (None, "", "None") else None
    except Exception:
        return None

def _t_me(username: Optional[str]) -> Optional[str]:
    u = (username or "").lstrip("@").strip()
    return f"https://t.me/{u}" if u else None

def _tg_id_url(uid: Optional[int]) -> Optional[str]:
    return f"tg://user?id={uid}" if uid else None

# ---------- Admins / models ----------
OWNER_ID        = _to_int(os.getenv("OWNER_ID"))
OWNER_USERNAME  = os.getenv("OWNER_USERNAME")   # optional, for link fallback
RONI_NAME       = os.getenv("RONI_NAME", "Roni")

RUBY_ID         = _to_int(os.getenv("RUBY_ID"))
RUBY_USERNAME   = os.getenv("RUBY_USERNAME")
RUBY_NAME       = os.getenv("RUBY_NAME", "Ruby")

RIN_ID          = _to_int(os.getenv("RIN_ID"))
RIN_USERNAME    = os.getenv("RIN_USERNAME")
RIN_NAME        = os.getenv("RIN_NAME", "Rin")

SAVY_ID         = _to_int(os.getenv("SAVY_ID"))
SAVY_USERNAME   = os.getenv("SAVY_USERNAME")
SAVY_NAME       = os.getenv("SAVY_NAME", "Savy")

SUPER_ADMIN_ID  = _to_int(os.getenv("SUPER_ADMIN_ID"))

# ---------- texts ----------
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "Tap a button to begin:"
)

MODELS_LINKS_TEXT = os.getenv(
    "MODELS_LINKS_TEXT",
    "🔥 <b>Find Our Models Elsewhere</b> 🔥\n\n"
    "👑 <b>Roni Jane (Owner)</b>\n"
    "<a href='https://allmylinks.com/chaossub283'>https://allmylinks.com/chaossub283</a>\n\n"
    "💎 <b>Ruby Ransom (Co-Owner)</b>\n"
    "<a href='https://allmylinks.com/rubyransoms'>https://allmylinks.com/rubyransoms</a>\n\n"
    "🍑 <b>Peachy Rin</b>\n"
    "<a href='https://allmylinks.com/peachybunsrin'>https://allmylinks.com/peachybunsrin</a>\n\n"
    "⚡ <b>Savage Savy</b>\n"
    "<a href='https://allmylinks.com/savannahxsavage'>https://allmylinks.com/savannahxsavage</a>"
)
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO")

# ---------- utils ----------
def _is_admin(uid: Optional[int]) -> bool:
    return bool(uid and uid in {OWNER_ID, SUPER_ADMIN_ID, RUBY_ID})

def _edit_or_reply(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup, preview: bool = False):
    async def _do():
        with suppress(Exception):
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=not preview)
            return True
        with suppress(Exception):
            await cq.message.reply_text(text, reply_markup=kb, disable_web_page_preview=not preview)
            return True
        return False
    return _do()

def _open_url_button(label: str, uid: Optional[int], username: Optional[str]) -> Optional[InlineKeyboardButton]:
    # Prefer tg://user?id=..., otherwise https://t.me/username
    url = _tg_id_url(uid) or _t_me(username)
    return InlineKeyboardButton(label, url=url) if url else None

def _welcome_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_admins")],
        [InlineKeyboardButton("💞 Contact Models", callback_data="dmf_contact_models")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _back_to_start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")]])

def _admins_kb() -> InlineKeyboardMarkup:
    row1: List[InlineKeyboardButton] = []
    btn = _open_url_button(f"👑 Message {RONI_NAME}", OWNER_ID, OWNER_USERNAME)
    if btn: row1.append(btn)
    btn = _open_url_button(f"💎 Message {RUBY_NAME}", RUBY_ID, RUBY_USERNAME)
    if btn: row1.append(btn)

    rows = []
    if row1:
        rows.append(row1)
    rows.append([InlineKeyboardButton("🙈 Send Anonymous Message", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def _contact_models_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    # Roni (owner) — ensure she appears here as requested
    btns_row = []
    b = _open_url_button(f"💗 {RONI_NAME}", OWNER_ID, OWNER_USERNAME)
    if b: btns_row.append(b)
    b = _open_url_button(f"💗 {RUBY_NAME}", RUBY_ID, RUBY_USERNAME)
    if b:
        if btns_row: rows.append(btns_row); btns_row = []
        btns_row.append(b)
    if btns_row:
        rows.append(btns_row); btns_row = []

    row = []
    b = _open_url_button(f"💗 {RIN_NAME}", RIN_ID, RIN_USERNAME)
    if b: row.append(b)
    b = _open_url_button(f"💗 {SAVY_NAME}", SAVY_ID, SAVY_USERNAME)
    if b: row.append(b)
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Back to Menus", callback_data="dmf_open_menu")])
    return InlineKeyboardMarkup(rows)

# ---------- DM-ready ----------
async def _mark_dm_ready_once(client: Client, m: Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    if not _store:
        return
    # Only mark & alert once per user
    if _store.is_dm_ready_global(uid):
        return
    with suppress(Exception):
        _store.set_dm_ready_global(uid, True, by_admin=False)

    # Notify admins once with clickable username (when available)
    uname = f"@{m.from_user.username}" if m.from_user.username else f"{m.from_user.first_name}"
    txt = f"✅ <b>DM-ready</b> — {uname} just opened the portal."
    for aid in filter(None, {OWNER_ID, RUBY_ID, SUPER_ADMIN_ID}):
        with suppress(Exception):
            await client.send_message(aid, txt)

# ---------- Handlers ----------
def register(app: Client):

    # /start — shows welcome + marks DM-ready (once)
    @app.on_message(filters.private & filters.command("start"))
    async def on_start(client: Client, m: Message):
        await _mark_dm_ready_once(client, m)
        await m.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)

    # Back to welcome
    @app.on_callback_query(filters.regex("^dmf_back_welcome$"))
    async def back_welcome(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, WELCOME_TEXT, _welcome_kb())
        await cq.answer()

    # Menu (delegates to your handlers.menu if present)
    @app.on_callback_query(filters.regex("^dmf_open_menu$"))
    async def open_menu(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            with suppress(Exception):
                await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
            await cq.answer()
            return
        except Exception:
            pass
        # Fallback basic menu
        await _edit_or_reply(cq, "💞 <b>Model Menus</b>\nChoose a name:", _contact_models_kb())
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex("^dmf_open_admins$"))
    async def open_admins(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, "How would you like to reach us?", _admins_kb())
        await cq.answer()

    # Contact Models (explicit)
    @app.on_callback_query(filters.regex("^dmf_contact_models$"))
    async def contact_models(client: Client, cq: CallbackQuery):
        await _edit_or_reply(cq, "Contact a model directly:", _contact_models_kb())
        await cq.answer()

    # Anonymous message entry (placeholder: your anon relay can hook here)
    @app.on_callback_query(filters.regex("^dmf_anon_admins$"))
    async def anon_admins(client: Client, cq: CallbackQuery):
        await _edit_or_reply(
            cq,
            "You're anonymous. Type the message you want me to forward to the admins.",
            _back_to_start_kb()
        )
        await cq.answer()

    # Links panel
    @app.on_callback_query(filters.regex("^dmf_models_links$"))
    async def models_links(client: Client, cq: CallbackQuery):
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(cq.from_user.id, MODELS_LINKS_PHOTO, caption=MODELS_LINKS_TEXT, reply_markup=_back_to_start_kb())
            else:
                await _edit_or_reply(cq, MODELS_LINKS_TEXT, _back_to_start_kb(), preview=True)
        except Exception:
            with suppress(Exception):
                await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=_back_to_start_kb(), disable_web_page_preview=False)
        await cq.answer()

    # /dmreadylist — admin only
    @app.on_message(filters.private & filters.command(["dmreadylist", "dmrlist", "dmr"]))
    async def dmready_list(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_admin(uid):
            return
        if not _store:
            await m.reply_text("Store unavailable.")
            return
        data = _store.list_dm_ready_global()
        if not data:
            await m.reply_text("No one is marked DM-ready yet.")
            return
        # Build a neat list with @username when available
        lines = ["<b>DM-ready users</b>:"]
        for s_uid in sorted(data.keys(), key=lambda x: int(x)):
            user_id = int(s_uid)
            try:
                u = await client.get_users(user_id)
                handle = f"@{u.username}" if getattr(u, 'username', None) else u.first_name
            except Exception:
                handle = s_uid
            lines.append(f"• {handle} (<code>{user_id}</code>)")
        await m.reply_text("\n".join(lines))
