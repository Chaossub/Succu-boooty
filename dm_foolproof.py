# DM portal + DM-ready marking + Admin/Models/Links/Help
import os
from typing import Optional, List

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

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

OWNER_ID        = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID  = _to_int(os.getenv("SUPER_ADMIN_ID"))

# models
RONI_ID   = _to_int(os.getenv("RONI_ID")) or OWNER_ID
RUBY_ID   = _to_int(os.getenv("RUBY_ID"))
RIN_ID    = _to_int(os.getenv("RIN_ID"))
SAVY_ID   = _to_int(os.getenv("SAVY_ID"))

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME", "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

def _is_admin(uid: Optional[int]) -> bool:
    return bool(uid and uid in {OWNER_ID, SUPER_ADMIN_ID})

# ---------- copy/text ----------
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
    "Tap a button to begin:"
)

MODELS_LINKS_TEXT = os.getenv("MODELS_LINKS_TEXT", "").strip() or (
    "🔥 <b>Find Our Models Elsewhere</b> 🔥\n\n"
    f"👑 <b>{RONI_NAME}</b>\nhttps://allmylinks.com/chaossub283\n\n"
    f"💎 <b>{RUBY_NAME}</b>\nhttps://allmylinks.com/rubyransoms\n\n"
    f"🍑 <b>{RIN_NAME}</b>\nhttps://allmylinks.com/peachybunsrin\n\n"
    f"⚡ <b>{SAVY_NAME}</b>\nhttps://allmylinks.com/savannahxsavage"
)
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO")

# ---------- keyboards ----------
def _portal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_admins")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
    ])

def _back_portal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_home")]])

def _contact_models_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    if RONI_ID:
        rows.append([InlineKeyboardButton(f"💌 {RONI_NAME}", url=f"tg://user?id={RONI_ID}")])
    if RUBY_ID:
        (rows[-1].append if rows else rows.append)(InlineKeyboardButton(f"💌 {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
    if RIN_ID:
        rows.append([InlineKeyboardButton(f"💌 {RIN_NAME}", url=f"tg://user?id={RIN_ID}")])
    if SAVY_ID:
        (rows[-1].append if rows else rows.append)(InlineKeyboardButton(f"💌 {SAVY_NAME}", url=f"tg://user?id={SAVY_ID}"))
    rows.append([InlineKeyboardButton("⬅️ Back to Menus", callback_data="dmf_open_menu")])
    return InlineKeyboardMarkup(rows)

def _admins_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    if OWNER_ID:
        rows.append([InlineKeyboardButton(f"👑 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}")])
    if SUPER_ADMIN_ID and SUPER_ADMIN_ID != OWNER_ID:
        rows.append([InlineKeyboardButton("💎 Message Admin", url=f"tg://user?id={SUPER_ADMIN_ID}")])
    rows.append([InlineKeyboardButton("🙈 Send Anonymous Message", callback_data="dmf_anon")])
    rows.append([InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_home")])
    return InlineKeyboardMarkup(rows)

# ---------- utils ----------
def _mark_dm_ready_once(uid: int) -> bool:
    if not _store:
        return False
    try:
        if _store.is_dm_ready_global(uid):
            return False
        _store.set_dm_ready_global(uid, True, by_admin=False)
        return True
    except Exception:
        return False

# ---------- registration ----------
def register(app: Client):
    # NOTE: Pyrogram 2.0.106 has no filters.edited, so we keep it simple.
    @app.on_message(filters.command(["start", "portal", "forceportal"]), group=-1000)
    async def start_portal(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0

        first_mark = _mark_dm_ready_once(uid)
        if first_mark and OWNER_ID:
            try:
                if m.from_user and m.from_user.username:
                    mention = f"@{m.from_user.username}"
                else:
                    mention = m.from_user.mention if m.from_user else f"<a href='tg://user?id={uid}'>user</a>"
                await client.send_message(OWNER_ID, f"✅ <b>DM-ready</b> — {mention} just opened the portal.")
            except Exception:
                pass

        await m.reply_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)

    # Back to start
    @app.on_callback_query(filters.regex(r"^dmf_home$"))
    async def back_home(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TEXT, reply_markup=_portal_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Menus (delegates to handlers.menu if present)
    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def open_menu(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.edit_text("💕 Model Menus\nChoose a name:", reply_markup=_contact_models_kb())
        await cq.answer()

    # Contact admins
    @app.on_callback_query(filters.regex(r"^dmf_open_admins$"))
    async def open_admins(client: Client, cq: CallbackQuery):
        kb = _admins_kb()
        try:
            await cq.message.edit_text("How would you like to reach us?", reply_markup=kb)
        except Exception:
            await cq.message.reply_text("How would you like to reach us?", reply_markup=kb)
        await cq.answer()

    # Anonymous message stub
    @app.on_callback_query(filters.regex(r"^dmf_anon$"))
    async def anon_stub(client: Client, cq: CallbackQuery):
        txt = ("You're anonymous. Type the message you want me to forward to the admins.\n"
               "Start with <code>suggestion:</code> or <code>report:</code> if you like.")
        try:
            await cq.message.edit_text(txt, reply_markup=_back_portal_kb())
        except Exception:
            await cq.message.reply_text(txt, reply_markup=_back_portal_kb())
        await cq.answer()

    # Contact models panel (also used by menu module)
    @app.on_callback_query(filters.regex(r"^dmf_contact_models$"))
    async def contact_models(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("Contact a model directly:", reply_markup=_contact_models_kb())
        except Exception:
            await cq.message.reply_text("Contact a model directly:", reply_markup=_contact_models_kb())
        await cq.answer()

    # Links
    @app.on_callback_query(filters.regex(r"^dmf_links$"))
    async def links(client: Client, cq: CallbackQuery):
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(cq.from_user.id, MODELS_LINKS_PHOTO,
                                        caption=MODELS_LINKS_TEXT, reply_markup=_back_portal_kb())
            else:
                await cq.message.edit_text(MODELS_LINKS_TEXT, reply_markup=_back_portal_kb(),
                                           disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=_back_portal_kb(),
                                        disable_web_page_preview=False)
        await cq.answer()

    # Admin: list who is DM-ready
    @app.on_message(filters.private & filters.command("dmready_list"))
    async def dmready_list(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_admin(uid):
            return
        if not _store:
            await m.reply_text("No store available.")
            return
        data = _store.list_dm_ready_global()
        if not data:
            await m.reply_text("No one is marked DM-ready yet.")
            return
        lines = []
        for s_uid in sorted(data.keys(), key=lambda x: int(x)):
            i_uid = int(s_uid)
            try:
                u = await client.get_users(i_uid)
                if u and getattr(u, "username", None):
                    disp = f"@{u.username}"
                else:
                    disp = u.mention if u else f"<a href='tg://user?id={i_uid}'>User {i_uid}</a>"
            except Exception:
                disp = f"<a href='tg://user?id={i_uid}'>User {i_uid}</a>"
            lines.append(f"• {disp}")
        await m.reply_text("✅ <b>DM-ready users</b>\n" + "\n".join(lines))
