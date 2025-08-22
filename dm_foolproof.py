# dm_foolproof.py — /start portal + mark DM-ready once + contact admins + links + help + admin list

import os, time
from typing import Optional, List, Dict
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ReqStore (JSON-based) for DM-ready tracking
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

# --- ENV ---
OWNER_ID: Optional[int] = int(os.getenv("OWNER_ID", "0")) or None
SUPER_ADMIN_ID: Optional[int] = int(os.getenv("SUPER_ADMIN_ID", "0")) or None
ADMIN_IDS: List[int] = [x for x in [OWNER_ID, SUPER_ADMIN_ID] if x]

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")

RONI_ID: Optional[int] = int(os.getenv("RONI_ID", "0")) or None
RUBY_ID: Optional[int] = int(os.getenv("RUBY_ID", "0")) or None

# Texts
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
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO")  # optional file_id

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
    "Tap a button to begin:"
)

# ---------- Keyboards ----------
def _welcome_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ])

def _back_welcome() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="dmf_back_welcome")]])

def _contact_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    # direct DM links to admins (Roni / Ruby)
    row: List[InlineKeyboardButton] = []
    if OWNER_ID:
        row.append(InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID:
        row.append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
    if row:
        rows.append(row)
    # anon relay
    rows.append([InlineKeyboardButton("🙈 Anonymous message to Admins", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

# ---------- Helpers ----------
def _is_admin(uid: Optional[int]) -> bool:
    return bool(uid and uid in ADMIN_IDS)

def _mark_dm_ready_once(uid: int) -> bool:
    """
    Mark DM-ready in the global store. Returns True only the first time it's set.
    """
    if not _store:
        return False
    try:
        if not _store.is_dm_ready_global(uid):
            _store.set_dm_ready_global(uid, True, by_admin=False)
            return True
        return False
    except Exception:
        return False

async def _notify_admin_dmready(client: Client, user: Optional["pyrogram.types.User"]):
    if not user:
        return
    # Notify only OWNER_ID if present; else SUPER_ADMIN_ID
    admin_target = OWNER_ID or SUPER_ADMIN_ID
    if not admin_target:
        return
    try:
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or f"id {user.id}"
        await client.send_message(admin_target, f"🟢 <b>DM Ready</b>: {name} (<code>{user.id}</code>)")
    except Exception:
        pass

# ---------- Public API for other modules (optional) ----------
async def show_help_root(client: Client, msg_or_cqmessage, from_callback: bool = False):
    # Delegate to handlers.help_panel if present, else fallback
    try:
        from handlers.help_panel import register as _  # import check
        # If their help_panel exposes dedicated callbacks, just tell user to press Help
        await client.send_message(
            msg_or_cqmessage.chat.id,
            "❔ Help is open via the <b>Help</b> button below.",
            reply_markup=_welcome_kb()
        )
    except Exception:
        await client.send_message(
            msg_or_cqmessage.chat.id,
            "❔ Help is currently unavailable.",
            reply_markup=_welcome_kb()
        )

# ---------- Handlers ----------
def register(app: Client):

    # /start — mark DM-ready once and show portal
    @app.on_message(filters.private & filters.command("start"))
    async def start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        became_ready = _mark_dm_ready_once(uid)
        if became_ready:
            await _notify_admin_dmready(client, m.from_user)
        await m.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)

    # Back to welcome (no re-notify)
    @app.on_callback_query(filters.regex("^dmf_back_welcome$"))
    async def back_welcome(client: Client, cq: CallbackQuery):
        # Do NOT mark again; only show the portal
        try:
            await cq.message.edit_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Open Menu tabs (delegates to handlers.menu)
    @app.on_callback_query(filters.regex("^dmf_open_menu$"))
    async def open_menu(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            try:
                await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("Menu is unavailable right now.", reply_markup=_back_welcome())
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex("^dmf_open_direct$"))
    async def open_direct(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("How would you like to reach us?", reply_markup=_contact_kb())
        except Exception:
            await cq.message.reply_text("How would you like to reach us?", reply_markup=_contact_kb())
        await cq.answer()

    # Anonymous message entry (placeholder: your anon relay can hook here)
    @app.on_callback_query(filters.regex("^dmf_anon_admins$"))
    async def anon_admins(client: Client, cq: CallbackQuery):
        txt = (
            "🙈 <b>Anonymous Admin Message</b>\n"
            "Reply with the message you want me to send to the admins.\n\n"
            "<i>(Your identity won’t be included in the forwarded note.)</i>"
        )
        try:
            await cq.message.edit_text(txt, reply_markup=_back_welcome(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(txt, reply_markup=_back_welcome(), disable_web_page_preview=True)
        await cq.answer()
        # If you already have an anon flow, set a flag in your storage here.

    # Links panel
    @app.on_callback_query(filters.regex("^dmf_models_links$"))
    async def models_links(client: Client, cq: CallbackQuery):
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(
                    cq.from_user.id,
                    MODELS_LINKS_PHOTO,
                    caption=MODELS_LINKS_TEXT,
                    reply_markup=_back_welcome()
                )
            else:
                await cq.message.edit_text(
                    MODELS_LINKS_TEXT,
                    reply_markup=_back_welcome(),
                    disable_web_page_preview=False
                )
        except Exception:
            await cq.message.reply_text(
                MODELS_LINKS_TEXT,
                reply_markup=_back_welcome(),
                disable_web_page_preview=False
            )
        await cq.answer()

    # ---- Admin: list DM-ready users ----
    @app.on_message(filters.private & filters.command("dmreadylist"))
    async def dmready_list(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_admin(uid):
            return await m.reply_text("This command is for admins only.")
        if not _store:
            return await m.reply_text("Storage unavailable.")
        data: Dict[str, dict] = _store.list_dm_ready_global()
        if not data:
            return await m.reply_text("No one is DM-ready yet.")
        # Build a compact listing
        lines = []
        now = time.time()
        for s_uid, rec in sorted(data.items(), key=lambda kv: int(kv[0])):
            since = rec.get("since")
            ago = int((now - since) // 3600) if since else None
            lines.append(f"• <code>{s_uid}</code>{' — '+str(ago)+'h' if ago is not None else ''}")
        text = "🟢 <b>DM-Ready Users</b>\n" + "\n".join(lines)
        await m.reply_text(text)
