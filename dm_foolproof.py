# DM entry & messaging helper with Back buttons and links panel.
# Welcome (DM /start): [💕 Menu] [💌 Contact] [🔗 Find our models elsewhere] [❔ Help]
# Welcome Contact: direct (Roni/Ruby) + Anonymous to admins + Suggestions + Back
# Menu Contact: direct (Roni/Ruby/Rin/Savy) only + Back
# /message -> Menu Contact (no anon)
# Anonymous reply bridge for OWNER
# Rules / Buyer buttons with Back to Menu/Welcome

import os, time, asyncio, secrets, json
from typing import Optional, List, Dict
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from pyrogram.errors import RPCError, FloodWait, UserIsBlocked, PeerIdInvalid

# Optional req store
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    class _DummyStore:
        def __init__(self): self._dm=set(); self._admins=set()
        def is_dm_ready_global(self, uid:int)->bool: return uid in self._dm
        def set_dm_ready_global(self, uid:int, ready:bool, by_admin:bool=False):
            (self._dm.add(uid) if ready else self._dm.discard(uid))
        def list_dm_ready_global(self): return {str(x): True for x in self._dm}
        def list_admins(self): return list(self._admins)
    _store = _DummyStore()

# ==== ENV ====
OWNER_ID       = int(os.getenv("OWNER_ID", "0"))
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "6964994611"))

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME",  "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

RUBY_ID = int(os.getenv("RUBY_ID", "0"))
RIN_ID  = int(os.getenv("RIN_ID",  "0"))
SAVY_ID = int(os.getenv("SAVY_ID", "0"))

DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_time").lower()  # first_time|always|off
DM_FORWARD_MODE      = os.getenv("DM_FORWARD_MODE", "off").lower()              # off|first|all
SHOW_RELAY_KB        = os.getenv("SHOW_RELAY_KB", "first_time").lower()         # first_time|daily

RULES_TEXT      = os.getenv("RULES_TEXT", "")
BUYER_REQ_TEXT  = os.getenv("BUYER_REQ_TEXT", "")
RULES_PHOTO     = os.getenv("RULES_PHOTO")
BUYER_REQ_PHOTO = os.getenv("BUYER_REQ_PHOTO")

# Links panel (welcome)
MODELS_LINKS_TEXT = os.getenv(
    "MODELS_LINKS_TEXT",
    "Here are our verified links 💖\n\n"
    "• Roni — <a href='https://example.com/roni'>Profile</a>\n"
    "• Ruby — <a href='https://example.com/ruby'>Profile</a>\n"
    "• Rin — <a href='https://example.com/rin'>Profile</a>\n"
    "• Savy — <a href='https://example.com/savy'>Profile</a>\n"
)
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO")
MODELS_LINKS_BUTTONS_JSON = os.getenv("MODELS_LINKS_BUTTONS_JSON")

# ==== STATE ====
_pending: Dict[int, Dict[str, bool]] = {}
_kb_last_shown: Dict[int, float] = {}
_anon_threads: Dict[str, int] = {}         # token -> user_id
_admin_pending_reply: Dict[int, str] = {}  # admin_id -> token

# ==== HELPERS ====
def _targets_owner_only() -> List[int]:
    return [OWNER_ID] if OWNER_ID > 0 else []

def _targets_any() -> List[int]:
    return [OWNER_ID] if OWNER_ID > 0 else getattr(_store, "list_admins", lambda: [])()

async def _is_admin(app: Client, chat_id: int, user_id: int) -> bool:
    if user_id in (OWNER_ID, SUPER_ADMIN_ID) or user_id in getattr(_store, "list_admins", lambda: [])():
        return True
    try:
        m = await app.get_chat_member(chat_id, user_id)
        return (m.privileges is not None) or (m.status in ("administrator", "creator"))
    except Exception:
        return False

def _should_show_kb_daily(uid: int) -> bool:
    last = _kb_last_shown.get(uid, 0)
    return (time.time() - last) >= 24 * 3600

def _mark_kb_shown(uid: int) -> None:
    _kb_last_shown[uid] = time.time()

async def _notify(app: Client, targets: List[int], text: str, reply_markup: InlineKeyboardMarkup | None = None):
    for uid in targets:
        try: await app.send_message(uid, text, reply_markup=reply_markup)
        except Exception: pass

async def _copy_to(app: Client, targets: List[int], src: Message, header: str, reply_markup: InlineKeyboardMarkup | None = None):
    for uid in targets:
        try:
            await app.send_message(uid, header, reply_markup=reply_markup)
            await app.copy_message(chat_id=uid, from_chat_id=src.chat.id, message_id=src.id)
        except FloodWait as e:
            await asyncio.sleep(int(getattr(e, "value", 1)) or 1)
        except RPCError:
            continue

def _append_back(kb: Optional[InlineKeyboardMarkup], back_cb: str = "dmf_back_welcome") -> InlineKeyboardMarkup:
    rows = []
    if isinstance(kb, InlineKeyboardMarkup) and kb.inline_keyboard:
        rows = [list(r) for r in kb.inline_keyboard]
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)

# ==== UI BUILDERS ====
def _welcome_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("💌 Contact", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("🔗 Find our models elsewhere", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❔ Help", callback_data="dmf_show_help")],
    ])

def _contact_welcome_kb() -> InlineKeyboardMarkup:
    rows = []
    row_direct = []
    if OWNER_ID > 0:
        row_direct.append(InlineKeyboardButton(f"💌 Message {RONI_NAME}", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID > 0:
        row_direct.append(InlineKeyboardButton(f"💌 Message {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
    if row_direct: rows.append(row_direct)
    rows.append([InlineKeyboardButton("🙈 Send anonymous message to the admins", callback_data="dmf_anon_admins")])
    rows.append([InlineKeyboardButton("💡 Send a suggestion", callback_data="dmf_open_suggest")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def _contact_menu_kb() -> InlineKeyboardMarkup:
    rows = []
    row1 = []
    if OWNER_ID > 0:
        row1.append(InlineKeyboardButton(f"💌 {RONI_NAME}", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID > 0:
        row1.append(InlineKeyboardButton(f"💌 {RUBY_NAME}", url=f"tg://user?id={RUBY_ID}"))
    if row1: rows.append(row1)
    row2 = []
    if RIN_ID > 0:
        row2.append(InlineKeyboardButton(f"💌 {RIN_NAME}", url=f"tg://user?id={RIN_ID}"))
    if SAVY_ID > 0:
        row2.append(InlineKeyboardButton(f"💌 {SAVY_NAME}", url=f"tg://user?id={SAVY_ID}"))
    if row2: rows.append(row2)
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="dmf_open_menu")])
    return InlineKeyboardMarkup(rows)

def _suggest_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Send suggestion (with your @)", callback_data="dmf_suggest_ident")],
        [InlineKeyboardButton("🙈 Send suggestion anonymously", callback_data="dmf_suggest_anon")],
        [InlineKeyboardButton("✖️ Cancel", callback_data="dmf_cancel")],
    ])

def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel", callback_data="dmf_cancel")]])

def _build_links_kb() -> Optional[InlineKeyboardMarkup]:
    raw = MODELS_LINKS_BUTTONS_JSON
    if not raw:
        return None
    try:
        data = json.loads(raw)
        rows: List[List[InlineKeyboardButton]] = []
        if isinstance(data, list) and data and isinstance(data[0], dict):
            row = []
            for it in data:
                t = str(it.get("text") or "").strip()
                u = str(it.get("url") or "").strip()
                if t and u:
                    row.append(InlineKeyboardButton(t, url=u))
                if len(row) == 2:
                    rows.append(row); row = []
            if row: rows.append(row)
        elif isinstance(data, list) and data and isinstance(data[0], list):
            for r in data:
                row = []
                for it in r:
                    t = str(it.get("text") or "").strip()
                    u = str(it.get("url") or "").strip()
                    if t and u:
                        row.append(InlineKeyboardButton(t, url=u))
                if row: rows.append(row)
        if rows:
            return InlineKeyboardMarkup(rows)
    except Exception:
        pass
    return None

def _spicy_intro(name: Optional[str]) -> str:
    name = name or "there"
    return f"Welcome to the Sanctuary, {name} 😈\nYou’re all set — tap Menu to see your options 👇"

def _fallback_full_help(is_admin: bool) -> str:
    lines = ["<b>SuccuBot Commands</b>",
             "\n🛠 <b>General</b>",
             "/help — show this menu",
             "/menu — open the model menus",
             "/message — contact options (no anon)",
             "/cancel — cancel current action",
             "/ping — bot check",
             "\n💌 <b>DM Ready</b>",
             "/dmready, /dmunready, /dmreadylist, /dmnudge"]
    return "\n".join(lines)

def _build_full_help_text(is_admin: bool) -> str:
    try:
        from handlers.help_cmd import _build_help_text as _central
        return _central(is_admin)
    except Exception:
        return _fallback_full_help(is_admin)

# ==== REGISTER ====
def register(app: Client):

    # --- Force the welcome UI on /start in DM ---
    @app.on_message(filters.private & filters.command("start"))
    async def dmf_start(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        first_time = not _store.is_dm_ready_global(uid)
        if first_time:
            _store.set_dm_ready_global(uid, True, by_admin=False)
            if DM_READY_NOTIFY_MODE in ("always", "first_time") and _targets_any():
                await _notify(client, _targets_any(),
                              f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via /start")
        await m.reply_text(_spicy_intro(m.from_user.first_name if m.from_user else None),
                           reply_markup=_welcome_kb())
        _mark_kb_shown(uid)

    # Group helper to drop a DM button
    @app.on_message(filters.command("dmsetup"))
    async def dmsetup(client: Client, m: Message):
        # allow only admins in groups; in DMs owner/super
        if m.chat and m.chat.type != "private":
            if not await _is_admin(client, m.chat.id, m.from_user.id):
                return await m.reply_text("Admins only.")
        else:
            if m.from_user.id not in (OWNER_ID, SUPER_ADMIN_ID):
                return await m.reply_text("Admins only.")
        me = await client.get_me()
        if not me.username:
            return await m.reply_text("I need a @username to create a DM button.")
        url = f"https://t.me/{me.username}?start=ready"
        btn = os.getenv("DMSETUP_BTN", "💌 DM Now")
        text = os.getenv("DMSETUP_TEXT", "Tap to DM for quick support—Contact menu, Help, and anonymous relay in one click.")
        await m.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(btn, url=url)]]))

    # /message — menu-style contact (no anon)
    @app.on_message(filters.private & filters.command(["message", "contact"]))
    async def dm_message_panel(client: Client, m: Message):
        uid = m.from_user.id
        first_time = not _store.is_dm_ready_global(uid)
        if first_time:
            _store.set_dm_ready_global(uid, True, by_admin=False)
            if DM_READY_NOTIFY_MODE in ("always", "first_time") and _targets_any():
                await _notify(client, _targets_any(), f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via /message")
        await m.reply_text("Contact a model directly:", reply_markup=_contact_menu_kb())
        _mark_kb_shown(uid)

    # Generic DM inbox (welcome/daily, anon/suggest, optional forward)
    @app.on_message(filters.private & ~filters.command(["message", "contact", "start"]))
    async def on_private_message(client: Client, m: Message):
        if not m.from_user: return
        uid = m.from_user.id

        # Owner anonymous reply bridge
        if uid in _admin_pending_reply:
            token = _admin_pending_reply.pop(uid)
            target_uid = _anon_threads.get(token)
            if not target_uid:
                return await m.reply_text("This anonymous thread has expired or was cleared.")
            if uid != OWNER_ID:
                return await m.reply_text("Only the owner can send anonymous replies.")
            try:
                await client.send_message(target_uid, f"📮 Message from {RONI_NAME}:")
                await client.copy_message(chat_id=target_uid, from_chat_id=m.chat.id, message_id=m.id)
                await m.reply_text("Sent anonymously ✅")
            except RPCError:
                await m.reply_text("Could not deliver message.")
            return

        # Pending flows (started from welcome contact)
        if uid in _pending:
            spec = _pending.pop(uid)
            kind = spec.get("kind")
            anon = spec.get("anon", False)
            targets = _targets_owner_only()
            if not targets:
                return await m.reply_text("Owner is not configured. Try later.")

            if kind == "anon":
                token = secrets.token_urlsafe(8)
                _anon_threads[token] = uid
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Reply anonymously", callback_data=f"dmf_anon_reply:{token}")]])
                await _copy_to(client, targets, m, header="📨 Anonymous message", reply_markup=kb)
                return await m.reply_text("Sent anonymously ✅")

            if kind == "suggest":
                if anon:
                    token = secrets.token_urlsafe(8)
                    _anon_threads[token] = uid
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Reply anonymously", callback_data=f"dmf_anon_reply:{token}")]])
                    await _copy_to(client, targets, m, header="💡 Anonymous suggestion", reply_markup=kb)
                    return await m.reply_text("Suggestion sent anonymously ✅")
                else:
                    header = f"💡 Suggestion from {m.from_user.mention} (<code>{uid}</code>)"
                    await _copy_to(client, targets, m, header=header)
                    return await m.reply_text("Thanks! Your suggestion was sent ✅")

        # First DM & notify
        first_time = not _store.is_dm_ready_global(uid)
        if first_time:
            _store.set_dm_ready_global(uid, True, by_admin=False)
            if DM_READY_NOTIFY_MODE in ("always", "first_time") and _targets_any():
                await _notify(client, _targets_any(), f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>) — via private chat")

        # Optional auto-forward (off by default)
        if DM_FORWARD_MODE in ("all", "first") and _targets_any():
            if DM_FORWARD_MODE == "all" or (DM_FORWARD_MODE == "first" and first_time):
                await _copy_to(client, _targets_any(), m, header=f"💌 New DM from {m.from_user.mention} (<code>{uid}</code>):")

        # Welcome on first_time or daily (config)
        show_intro = (first_time and SHOW_RELAY_KB == "first_time") or (SHOW_RELAY_KB == "daily" and _should_show_kb_daily(uid))
        if show_intro:
            await m.reply_text(_spicy_intro(m.from_user.first_name if m.from_user else None), reply_markup=_welcome_kb())
            _mark_kb_shown(uid)

    # Back to Welcome
    @app.on_callback_query(filters.regex("^dmf_back_welcome$"))
    async def cb_back_welcome(client: Client, cq: CallbackQuery):
        await cq.message.reply_text(
            _spicy_intro(cq.from_user.first_name if cq.from_user else None),
            reply_markup=_welcome_kb()
        )
        _mark_kb_shown(cq.from_user.id)
        await cq.answer()

    # Help
    @app.on_callback_query(filters.regex("^dmf_show_help$"))
    async def cb_show_help(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        is_admin = (uid in (OWNER_ID, SUPER_ADMIN_ID)) or (uid in getattr(_store, "list_admins", lambda: [])())
        nav = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")],
        ])
        await cq.message.reply_text(_build_full_help_text(is_admin), reply_markup=nav)
        await cq.answer()

    # Contact (welcome)
    @app.on_callback_query(filters.regex("^dmf_open_direct$"))
    async def cb_open_direct_welcome(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("How would you like to reach us?", reply_markup=_contact_welcome_kb())
        await cq.answer()

    # Contact (menu) — no anon here
    @app.on_callback_query(filters.regex("^dmf_open_direct_menu$"))
    async def cb_open_direct_menu(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("Contact a model directly:", reply_markup=_contact_menu_kb())
        await cq.answer()

    # Open Menu tabs
    @app.on_callback_query(filters.regex("^dmf_open_menu$"))
    async def cb_open_menu(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import _tabs_kb  # reuse the same tabs
            await cq.message.reply_text("Pick a menu:", reply_markup=_tabs_kb())
        except Exception:
            await cq.message.reply_text("Menu is unavailable right now.")
        await cq.answer()

    # Links (welcome)
    @app.on_callback_query(filters.regex("^dmf_models_links$"))
    async def cb_models_links(client: Client, cq: CallbackQuery):
        kb = _append_back(_build_links_kb(), "dmf_back_welcome")
        try:
            if MODELS_LINKS_PHOTO:
                await client.send_photo(cq.from_user.id, MODELS_LINKS_PHOTO, caption=MODELS_LINKS_TEXT, reply_markup=kb)
            else:
                await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=kb, disable_web_page_preview=False)
        except Exception:
            await cq.message.reply_text(MODELS_LINKS_TEXT, reply_markup=kb, disable_web_page_preview=False)
        await cq.answer()

    # Anonymous + Suggestions (welcome only)
    @app.on_callback_query(filters.regex("^dmf_anon_admins$"))
    async def cb_anon_admins(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not _targets_owner_only():
            return await cq.answer("Owner is not configured.", show_alert=True)
        _pending[uid] = {"kind": "anon", "anon": True}
        await cq.message.reply_text("You're anonymous. Type the message you want me to send to the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex("^dmf_open_suggest$"))
    async def cb_open_suggest(client: Client, cq: CallbackQuery):
        await cq.message.reply_text("How would you like to send your suggestion?", reply_markup=_suggest_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex("^dmf_suggest_ident$"))
    async def cb_suggest_ident(client: Client, cq: CallbackQuery):
        _pending[cq.from_user.id] = {"kind": "suggest", "anon": False}
        await cq.message.reply_text("Great! Type your suggestion and I’ll send it to the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex("^dmf_suggest_anon$"))
    async def cb_suggest_anon(client: Client, cq: CallbackQuery):
        _pending[cq.from_user.id] = {"kind": "suggest", "anon": True}
        await cq.message.reply_text("You're anonymous. Type your suggestion for the admins.", reply_markup=_cancel_kb())
        await cq.answer()

    @app.on_callback_query(filters.regex("^dmf_anon_reply:"))
    async def cb_anon_reply(client: Client, cq: CallbackQuery):
        admin_id = cq.from_user.id
        token = cq.data.split(":", 1)[1]
        if admin_id != OWNER_ID:
            return await cq.answer("Only the owner can reply anonymously.", show_alert=True)
        if token not in _anon_threads:
            return await cq.answer("That anonymous thread has expired.", show_alert=True)
        _admin_pending_reply[admin_id] = token
        await cq.message.reply_text("Reply mode enabled. Type your reply now — it will be sent anonymously. Use /cancel to exit.")
        await cq.answer("Reply to this message to send anonymously.")

    @app.on_callback_query(filters.regex("^dmf_cancel$"))
    async def cb_cancel(client: Client, cq: CallbackQuery):
        _pending.pop(cq.from_user.id, None)
        await cq.answer("Canceled.")
        try: await cq.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        try: await client.send_message(cq.from_user.id, "Canceled.", reply_markup=ReplyKeyboardRemove())
        except Exception: pass

    # Rules / Buyer with Back
    @app.on_callback_query(filters.regex("^dmf_rules$"))
    async def cb_rules(client: Client, cq: CallbackQuery):
        nav = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")],
            [InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")],
        ])
        if RULES_PHOTO:
            try: await client.send_photo(cq.from_user.id, RULES_PHOTO, caption=RULES_TEXT or " ", reply_markup=nav)
            except Exception: await cq.message.reply_text(RULES_TEXT or " ", reply_markup=nav, disable_web_page_preview=True)
        else:
            await cq.message.reply_text(RULES_TEXT or " ", reply_markup=nav, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex("^dmf_buyer$"))
    async def cb_buyer(client: Client, cq: CallbackQuery):
        nav = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")],
            [InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")],
        ])
        if BUYER_REQ_PHOTO:
            try: await client.send_photo(cq.from_user.id, BUYER_REQ_PHOTO, caption=BUYER_REQ_TEXT or " ", reply_markup=nav)
            except Exception: await cq.message.reply_text(BUYER_REQ_TEXT or " ", reply_markup=nav, disable_web_page_preview=True)
        else:
            await cq.message.reply_text(BUYER_REQ_TEXT or " ", reply_markup=nav, disable_web_page_preview=True)
        # Optional quick /reqstatus button
        kb = ReplyKeyboardMarkup([["/reqstatus"]], resize_keyboard=True, one_time_keyboard=True, selective=True)
        await client.send_message(cq.from_user.id, "Tap to check your status:", reply_markup=kb)
        await cq.answer()

    # Admin utilities
    @app.on_message(filters.command(["dmready", "dmunready"]))
    async def dm_ready_toggle(client: Client, m: Message):
        ready = m.command[0].lower() == "dmready"
        target_id = m.from_user.id
        if m.reply_to_message and m.reply_to_message.from_user:
            if m.chat and m.chat.type != "private":
                if not await _is_admin(client, m.chat.id, m.from_user.id):
                    return await m.reply_text("Admins only for toggling others.")
            target_id = m.reply_to_message.from_user.id
        try: _store.set_dm_ready_global(target_id, ready, by_admin=(target_id != m.from_user.id))
        except Exception: pass
        status = "✅ DM-ready (global)" if ready else "❌ Not DM-ready"
        who = "you" if target_id == m.from_user.id else f"<code>{target_id}</code>"
        await m.reply_text(f"{status} set for {who}.")
        if ready and _targets_any():
            try:
                u = await client.get_users(target_id)
                await _notify(client, _targets_any(), f"🔔 DM-ready: {u.mention} (<code>{target_id}</code>) — set by admin")
            except Exception:
                await _notify(client, _targets_any(), f"🔔 DM-ready: <code>{target_id}</code> — set by admin")

    @app.on_message(filters.command("dmreadylist"))
    async def dmreadylist(client: Client, m: Message):
        try: dm = _store.list_dm_ready_global()
        except Exception: dm = {}
        if not dm: return await m.reply_text("No one is marked DM-ready (global) yet.")
        lines = []
        for uid_str in list(dm.keys())[:200]:
            uid = int(uid_str)
            try:
                u = await client.get_users(uid)
                lines.append(f"• {u.mention} (<code>{uid}</code>)")
            except Exception:
                lines.append(f"• <code>{uid}</code>")
        await m.reply_text("<b>DM-ready (global):</b>\n" + "\n".join(lines))

    @app.on_message(filters.command("dmnudge"))
    async def dmnudge(client: Client, m: Message):
        if m.chat and m.chat.type != "private":
            if not await _is_admin(client, m.chat.id, m.from_user.id):
                return await m.reply_text("Admins only.")
        else:
            if m.from_user.id not in (OWNER_ID, SUPER_ADMIN_ID):
                return await m.reply_text("Admins only.")
        target: Optional[int] = None
        if m.reply_to_message and m.reply_to_message.from_user:
            target = m.reply_to_message.from_user.id
        elif len(m.command) > 1:
            arg = m.command[1]
            if arg.isdigit(): target = int(arg)
            else:
                try: target = (await client.get_users(arg)).id
                except Exception: pass
        if not target:
            return await m.reply_text("Reply to a user or pass @username/user_id.")
        text = ("Hey! Quick nudge from the Sanctuary 💋\n\n"
                "Please keep your DMs open to receive content you purchase and game rewards. "
                "If you’d rather not, just let us know and we’ll arrange an alternative.\n\n"
                "Thanks for helping things run smoothly! 😇")
        try:
            await client.send_message(target, text); await m.reply_text("Nudge sent ✅")
        except UserIsBlocked: await m.reply_text("User blocked the bot ❌")
        except (PeerIdInvalid, FloodWait, RPCError): await m.reply_text("Could not DM user (privacy/flood).")
