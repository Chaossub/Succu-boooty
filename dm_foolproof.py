# dm_foolproof.py — /start portal + DM-ready flag + admin contact + links + help + notify
import os, time, logging
from typing import Optional, List, Set
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

log = logging.getLogger("SuccuBot")

# ----- Optional persistent store (if present) -----
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

# ----- ENV -----
OWNER_ID        = int(os.getenv("OWNER_ID", "0")) or None
SUPER_ADMIN_ID  = int(os.getenv("SUPER_ADMIN_ID", "0")) or None

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RUBY_ID   = int(os.getenv("RUBY_ID", "0")) or None

# Notify mode: "off" | "owner" | "chat:<id>" | "both"
DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "owner").strip().lower()

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

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing. 💋\n\n"
    "Tap a button to begin:"
)

# In-memory fallback so we don’t spam notifications if ReqStore isn’t present.
_notified_once: Set[int] = set()

def _welcome_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _contact_kb() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    if OWNER_ID:
        rows.append([InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}")])
    if RUBY_ID:
        if rows:
            rows[-1].append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
        else:
            rows.append([InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}")])
    rows.append([InlineKeyboardButton("🙈 Send Anonymous Message to Admins", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def _back_welcome() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")]])

# ---------- DM-ready helpers ----------
def _already_ready(uid: int) -> bool:
    try:
        if _store:
            return bool(_store.is_dm_ready_global(uid))
    except Exception:
        pass
    return uid in _notified_once  # best-effort fallback

def _set_ready(uid: int):
    try:
        if _store:
            _store.set_dm_ready_global(uid, True, by_admin=False)
    except Exception:
        pass

async def _notify_ready(client: Client, uid: int, first_name: str, username: Optional[str]):
    # Build message
    link = f"<a href='tg://user?id={uid}'>{first_name or 'User'}</a>"
    uname = f"@{username}" if username else ""
    text = f"✅ <b>DM-ready</b>: {link} {uname} (<code>{uid}</code>) just opened a chat with the bot."

    mode = DM_READY_NOTIFY_MODE
    if mode in ("owner", "both"):
        if OWNER_ID:
            with suppress(Exception):
                await client.send_message(OWNER_ID, text, disable_web_page_preview=True)
    if mode.startswith("chat:") or mode == "both":
        chat_id = None
        if mode == "both" and os.getenv("DM_READY_NOTIFY_CHAT"):
            try:
                chat_id = int(os.getenv("DM_READY_NOTIFY_CHAT"))
            except Exception:
                chat_id = None
        elif mode.startswith("chat:"):
            try:
                chat_id = int(mode.split(":", 1)[1])
            except Exception:
                chat_id = None
        if chat_id:
            with suppress(Exception):
                await client.send_message(chat_id, text, disable_web_page_preview=True)

def _remember_notified(uid: int):
    _notified_once.add(uid)

# Mark & maybe notify (idempotent)
async def _mark_dm_ready_and_notify(client: Client, m: Message):
    if not m.from_user:
        return
    uid = m.from_user.id
    if _already_ready(uid):
        return
    _set_ready(uid)
    _remember_notified(uid)
    await _notify_ready(client, uid, m.from_user.first_name, m.from_user.username)

# ---------- Handlers ----------
def register(app: Client):

    # 1) Mark ready on ANY private message (runs before others)
    @app.on_message(filters.private & ~filters.me & ~filters.bot, group=-1001)
    async def on_any_private(client: Client, m: Message):
        try:
            await _mark_dm_ready_and_notify(client, m)
        except Exception:
            log.exception("DM-ready marking failed on private message")

    # 2) /start → welcome + buttons (+ ready mark)
    @app.on_message(filters.private & filters.command("start"))
    async def start(client: Client, m: Message):
        try:
            await _mark_dm_ready_and_notify(client, m)
        except Exception:
            pass
        await m.reply_text(WELCOME_TEXT, reply_markup=_welcome_kb(), disable_web_page_preview=True)

    # Back to welcome
    @app.on_callback_query(filters.regex("^dmf_back_welcome$"))
    async def back_welcome(client: Client, cq: CallbackQuery):
        try:
            # Mark on button usage as well (just in case)
            fake_msg = Message(id=0)  # minimal shim not used; safe-guarding only
        except Exception:
            pass
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
            await cq.message.reply_text("Menu is unavailable right now.")
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex("^dmf_open_direct$"))
    async def open_direct(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("How would you like to reach us?", reply_markup=_contact_kb())
        except Exception:
            await cq.message.reply_text("How would you like to reach us?", reply_markup=_contact_kb())
        await cq.answer()

    # Anonymous message entry (placeholder relay)
    @app.on_callback_query(filters.regex("^dmf_anon_admins$"))
    async def anon_admins(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(
                "You're anonymous. Type the message you want me to send to the admins.",
                reply_markup=_back_welcome()
            )
        except Exception:
            await cq.message.reply_text(
                "You're anonymous. Type the message you want me to send to the admins.",
                reply_markup=_back_welcome()
            )
        await cq.answer()
        # If you have an anon relay flow, hook it here.

    # Links panel
    @app.on_callback_query(filters.regex("^dmf_models_links$"))
    async def models_links(client: Client, cq: CallbackQuery):
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(
                    cq.from_user.id, MODELS_LINKS_PHOTO,
                    caption=MODELS_LINKS_TEXT, reply_markup=_back_welcome()
                )
            else:
                await cq.message.edit_text(
                    MODELS_LINKS_TEXT, reply_markup=_back_welcome(), disable_web_page_preview=False
                )
        except Exception:
            await cq.message.reply_text(
                MODELS_LINKS_TEXT, reply_markup=_back_welcome(), disable_web_page_preview=False
            )
        await cq.answer()

    # Help: delegate to help_panel if available, else hint
    @app.on_callback_query(filters.regex("^dmf_show_help$"))
    async def show_help(client: Client, cq: CallbackQuery):
        try:
            from handlers.help_panel import show_help_root  # optional entrypoint
            await show_help_root(client, cq.message, from_callback=True)  # type: ignore[arg-type]
        except Exception:
            await cq.message.reply_text("Type /help to open the help menu.", reply_markup=_back_welcome())
        await cq.answer()
