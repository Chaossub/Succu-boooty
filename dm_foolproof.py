"""
Start-portal + Contact Admins/Models + one-time DM-ready flag & admin alert.

- Shows the portal on /start with buttons:
  [💕 Menu] [Contact Admins 👑] [💕 Contact Models] [Find Our Models Elsewhere 🔥] [❓ Help]
- Marks the user DM-ready the FIRST time they open the portal (one-time alert to admins).
- /dmready_list  -> lists all global DM-ready users (owner/super-admin only)
- /envcheck      -> quick debug of resolved env (owner only)
"""

import os
import time
from typing import Optional, List

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# --------------------------- optional store ---------------------------
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

# --------------------------- env helpers ---------------------------
def _to_int(x):
    try:
        x = (x or "").strip()
        if not x or x.lower() == "none" or x == "0":
            return None
        return int(x)
    except Exception:
        return None

def _clean_username(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = u.strip()
    return u[1:] if u.startswith("@") else (u or None)

# Accept both OWNER_* and RONI_* for the owner slot
OWNER_ID        = _to_int(os.getenv("OWNER_ID") or os.getenv("RONI_ID"))
OWNER_USERNAME  = _clean_username(os.getenv("OWNER_USERNAME") or os.getenv("RONI_USERNAME"))
RONI_NAME       = os.getenv("RONI_NAME", "Roni")

SUPER_ADMIN_ID  = _to_int(os.getenv("SUPER_ADMIN_ID"))
SUPER_ADMIN_USERNAME = _clean_username(os.getenv("SUPER_ADMIN_USERNAME"))

RUBY_ID        = _to_int(os.getenv("RUBY_ID"))
RUBY_USERNAME  = _clean_username(os.getenv("RUBY_USERNAME"))
RUBY_NAME      = os.getenv("RUBY_NAME", "Ruby")

RIN_ID        = _to_int(os.getenv("RIN_ID"))
RIN_USERNAME  = _clean_username(os.getenv("RIN_USERNAME"))
RIN_NAME      = os.getenv("RIN_NAME", "Rin")

SAVY_ID        = _to_int(os.getenv("SAVY_ID") or os.getenv("SAVVY_ID"))
SAVY_USERNAME  = _clean_username(os.getenv("SAVY_USERNAME") or os.getenv("SAVVY_USERNAME"))
SAVY_NAME      = os.getenv("SAVY_NAME", os.getenv("SAVVY_NAME", "Savy"))

# Links panel content
MODELS_LINKS_TEXT = os.getenv(
    "MODELS_LINKS_TEXT",
    "🔥 <b>Find Our Models Elsewhere</b> 🔥\n\n"
    "👑 <b>Roni Jane (Owner)</b>\n"
    "<a href='https://t.me/{}'>@{}</a>\n\n".format(OWNER_USERNAME or "username", OWNER_USERNAME or "username")
)
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO")  # optional URL/file id

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "Tap a button to begin:"
)

# --------------------------- small utils ---------------------------
def _contact_url(user_id: Optional[int], username: Optional[str]) -> Optional[str]:
    if username:
        return f"https://t.me/{username}"
    if user_id:
        return f"tg://user?id={user_id}"
    return None

def _admins_to_notify() -> List[int]:
    ids = []
    if OWNER_ID:
        ids.append(OWNER_ID)
    if SUPER_ADMIN_ID and SUPER_ADMIN_ID != OWNER_ID:
        ids.append(SUPER_ADMIN_ID)
    # include any custom admins saved in store
    if _store:
        for a in _store.list_admins():
            if a not in ids:
                ids.append(a)
    return ids

def _user_display(u) -> str:
    # prefer @username, fall back to first name or id
    if getattr(u, "username", None):
        return f"@{u.username}"
    if getattr(u, "first_name", None):
        return u.first_name
    return f"User {u.id}"

def _mark_dm_ready_once(uid: int) -> bool:
    """Returns True if it changed from not-ready -> ready."""
    if not _store:
        return False
    try:
        if _store.is_dm_ready_global(uid):
            return False
        _store.set_dm_ready_global(uid, True, by_admin=False)
        return True
    except Exception:
        return False

# --------------------------- keyboards ---------------------------
def _welcome_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_admins")],
        [InlineKeyboardButton("💕 Contact Models", callback_data="dmf_open_models")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _contact_admins_kb() -> InlineKeyboardMarkup:
    rows = []
    url = _contact_url(OWNER_ID, OWNER_USERNAME)
    if url:
        rows.append([InlineKeyboardButton("👑 Message Roni", url=url)])
    url = _contact_url(RUBY_ID, RUBY_USERNAME)
    if url:
        rows.append([InlineKeyboardButton("💎 Message Ruby", url=url)])
    rows.append([InlineKeyboardButton("🙈 Send Anonymous Message", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("◀️ Back to Start", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def _models_panel_kb() -> InlineKeyboardMarkup:
    rows = []
    # Row 1: Roni + Ruby
    row1 = []
    url = _contact_url(OWNER_ID, OWNER_USERNAME)
    if url:
        row1.append(InlineKeyboardButton(f"💌 {RONI_NAME}", url=url))
    url = _contact_url(RUBY_ID, RUBY_USERNAME)
    if url:
        row1.append(InlineKeyboardButton(f"💌 {RUBY_NAME}", url=url))
    if row1:
        rows.append(row1)
    # Row 2: Rin + Savy
    row2 = []
    url = _contact_url(RIN_ID, RIN_USERNAME)
    if url:
        row2.append(InlineKeyboardButton(f"💌 {RIN_NAME}", url=url))
    url = _contact_url(SAVY_ID, SAVY_USERNAME)
    if url:
        row2.append(InlineKeyboardButton(f"💌 {SAVY_NAME}", url=url))
    if row2:
        rows.append(row2)
    rows.append([InlineKeyboardButton("◀️ Back to Menus", callback_data="dmf_open_menu")])
    return InlineKeyboardMarkup(rows)

# --------------------------- register ---------------------------
def register(app: Client):

    # /start: show portal + one-time dm-ready + one-time admin alert
    @app.on_message(filters.private & filters.command("start"))
    async def start_cmd(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0

        changed = _mark_dm_ready_once(uid)
        if changed:
            # alert admins ONCE
            mention = _user_display(m.from_user)
            text = f"✅ <b>DM-ready</b> — {mention} just opened the portal."
            for aid in _admins_to_notify():
                if aid and aid != uid:
                    try:
                        await client.send_message(aid, text)
                    except Exception:
                        pass

        # welcome panel
        await m.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)

    # Back to welcome
    @app.on_callback_query(filters.regex("^dmf_back_welcome$"))
    async def back_welcome(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Open "menu" (delegates to handlers.menu if present)
    @app.on_callback_query(filters.regex("^dmf_open_menu$"))
    async def open_menu(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            try:
                await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("Menu is unavailable right now.")
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex("^dmf_open_admins$"))
    async def open_admins(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("How would you like to reach us?", reply_markup=_contact_admins_kb())
        except Exception:
            await cq.message.reply_text("How would you like to reach us?", reply_markup=_contact_admins_kb())
        await cq.answer()

    # Contact Models
    @app.on_callback_query(filters.regex("^dmf_open_models$"))
    async def open_models(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("Contact a model directly:", reply_markup=_models_panel_kb())
        except Exception:
            await cq.message.reply_text("Contact a model directly:", reply_markup=_models_panel_kb())
        await cq.answer()

    # Anonymous message entry (you can hook this to your existing anon relay)
    @app.on_callback_query(filters.regex("^dmf_anon_admins$"))
    async def anon_admins(client: Client, cq: CallbackQuery):
        txt = (
            "You're anonymous. Type the message you want me to forward to the admins.\n\n"
            "Use /cancel to stop."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to Start", callback_data="dmf_back_welcome")]])
        try:
            await cq.message.edit_text(txt, reply_markup=kb)
        except Exception:
            await cq.message.reply_text(txt, reply_markup=kb)
        await cq.answer()
        # If you already have an anon flow/state machine, set the flag here.

    # Links panel
    @app.on_callback_query(filters.regex("^dmf_models_links$"))
    async def models_links(client: Client, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to Start", callback_data="dmf_back_welcome")]])
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(cq.from_user.id, MODELS_LINKS_PHOTO, caption=MODELS_LINKS_TEXT, reply_markup=kb)
            else:
                await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=kb, disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=kb, disable_web_page_preview=False)
        await cq.answer()

    # Help (delegates to handlers.help_panel if present)
    @app.on_callback_query(filters.regex("^dmf_show_help$"))
    async def show_help(client: Client, cq: CallbackQuery):
        try:
            from handlers.help_panel import show_help_root
            await show_help_root(client, cq.message, from_callback=True)
        except Exception:
            await cq.message.reply_text("Type /help to open the help menu.", reply_markup=_welcome_kb())
        await cq.answer()

    # ------------------- admin utilities -------------------
    def _is_owner(uid: Optional[int]) -> bool:
        return bool(uid and OWNER_ID and uid == OWNER_ID)

    def _is_super(uid: Optional[int]) -> bool:
        return bool(uid and SUPER_ADMIN_ID and uid == SUPER_ADMIN_ID)

    def _is_admin(uid: Optional[int]) -> bool:
        if _is_owner(uid) or _is_super(uid):
            return True
        if _store:
            try:
                return uid in _store.list_admins()
            except Exception:
                return False
        return False

    @app.on_message(filters.private & filters.command("envcheck"))
    async def envcheck(client: Client, m: Message):
        if not _is_owner(m.from_user.id):
            return
        lines = [
            "<b>Resolved contact env:</b>",
            f"RONI: id={OWNER_ID} user={OWNER_USERNAME} name={RONI_NAME}",
            f"RUBY: id={RUBY_ID} user={RUBY_USERNAME} name={RUBY_NAME}",
            f"RIN:  id={RIN_ID} user={RIN_USERNAME} name={RIN_NAME}",
            f"SAVY: id={SAVY_ID} user={SAVY_USERNAME} name={SAVY_NAME}",
        ]
        await m.reply_text("\n".join(lines), disable_web_page_preview=True)

    @app.on_message(filters.private & filters.command(["dmready_list", "dmready"]))
    async def dmready_list(client: Client, m: Message):
        if not _is_admin(m.from_user.id):
            return
        if not _store:
            await m.reply_text("No store is configured.")
            return
        data = _store.list_dm_ready_global() or {}
        if not data:
            await m.reply_text("Nobody is marked DM-ready yet.")
            return
        # try to show nice usernames
        out = ["<b>DM-ready users:</b>"]
        for s_uid, meta in sorted(data.items(), key=lambda kv: int(kv[0])):
            uid = int(s_uid)
            username = None
            try:
                u = await client.get_users(uid)
                username = f"@{u.username}" if u and u.username else None
            except Exception:
                username = None
            ts = meta.get("since")
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "—"
            line = f"• {username or ('<code>'+s_uid+'</code>')} — since {when}"
            out.append(line)
        await m.reply_text("\n".join(out), disable_web_page_preview=True)

