# dm_foolproof.py
# Single /start entrypoint & main portal. Robust DM-ready marking + no duplicate menus.

from __future__ import annotations
import os
import time
import logging
from typing import Optional, Callable
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified

log = logging.getLogger("dm_foolproof")

# ── Texts ────────────────────────────────────────────────────────────────────
WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

MODELS_LINKS_TEXT = os.getenv("FIND_MODELS_TEXT") or (
    "✨ <b>Find Our Models Elsewhere</b> ✨\n\n"
    "All verified off-platform links for our models are collected here. "
    "Check pinned messages or official posts for updates."
)

# ── Keyboards ────────────────────────────────────────────────────────────────
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menus", callback_data="dmf_open_menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="dmf_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="dmf_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_help")],
    ])

def _back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main", callback_data="dmf_home")]])

# ── Safe edit helper ────────────────────────────────────────────────────────
async def _safe_edit(message, text, **kwargs):
    try:
        return await message.edit_text(text, **kwargs)
    except MessageNotModified:
        if kwargs.get("reply_markup") is not None:
            try:
                return await message.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified:
                pass
    return None

# ── DM-ready backend discovery ──────────────────────────────────────────────
# We try various stores & method names so this works across your different versions.
_DM_SET_FN: Optional[Callable[[int], bool]] = None

def _discover_dm_store():
    global _DM_SET_FN
    if _DM_SET_FN:
        return

    # Try req_store.ReqStore
    try:
        from req_store import ReqStore  # type: ignore
        store = ReqStore()
        if hasattr(store, "set_dm_ready_global") and hasattr(store, "is_dm_ready_global"):
            def _fn(uid: int) -> bool:
                if not store.is_dm_ready_global(uid):
                    store.set_dm_ready_global(uid, True, by_admin=False)
                    return True
                return False
            _DM_SET_FN = _fn
            log.info("DM-ready backend: req_store.ReqStore (global)")
            return
        if hasattr(store, "set_dm_ready") and hasattr(store, "is_dm_ready"):
            def _fn(uid: int) -> bool:
                if not store.is_dm_ready(uid):
                    store.set_dm_ready(uid, True)
                    return True
                return False
            _DM_SET_FN = _fn
            log.info("DM-ready backend: req_store.ReqStore (legacy)")
            return
    except Exception:
        pass

    # Try requirements_store (alt name)
    try:
        import requirements_store as rqs  # type: ignore
        if hasattr(rqs, "set_dm_ready") and hasattr(rqs, "is_dm_ready"):
            def _fn(uid: int) -> bool:
                if not rqs.is_dm_ready(uid):
                    rqs.set_dm_ready(uid, True)
                    return True
                return False
            _DM_SET_FN = _fn
            log.info("DM-ready backend: requirements_store")
            return
    except Exception:
        pass

    # Try common free functions lying around
    for mod_name in ("dm_ready", "utils.dm_ready", "utils.req_helpers"):
        try:
            mod = __import__(mod_name, fromlist=["*"])
            cand_names = ("mark_dm_ready", "set_dm_ready", "add_dm_ready")
            for n in cand_names:
                fn = getattr(mod, n, None)
                if callable(fn):
                    def _fn(uid: int, _fn=fn) -> bool:  # type: ignore
                        try:
                            return bool(_fn(uid))
                        except TypeError:
                            _fn(uid)  # maybe returns None
                            return True
                    _DM_SET_FN = _fn
                    log.info(f"DM-ready backend: {mod_name}.{n}")
                    return
        except Exception:
            pass

    # Nothing found — we’ll still broadcast but can’t persist
    log.info("DM-ready backend: none (broadcast-only)")

_discover_dm_store()

def _set_dm_ready(uid: int) -> bool:
    """Returns True if we *changed* state to ready; False if already ready or no backend."""
    if _DM_SET_FN:
        try:
            return bool(_DM_SET_FN(uid))
        except Exception as e:
            log.warning(f"DM-ready backend failed for {uid}: {e}")
    # No backend — consider it 'changed' so we still announce once
    return True

# ── Broadcast (dedup per user so it won’t spam) ─────────────────────────────
_last_broadcast_ts = {}  # uid -> ts
BROADCAST_WINDOW = 60.0  # seconds

async def _announce_ready(client: Client, m: Message):
    uid = m.from_user.id if m.from_user else 0
    now = time.time()
    if uid in _last_broadcast_ts and now - _last_broadcast_ts[uid] < BROADCAST_WINDOW:
        return
    _last_broadcast_ts[uid] = now

    groups = [g.strip() for g in os.getenv("SANCTUARY_GROUP_IDS", "").split(",") if g.strip()]
    if not groups:
        return
    name = (m.from_user.first_name if m.from_user else "Someone")
    text = f"✅ DM-ready — {name} just opened the portal."
    for g in groups:
        try:
            await client.send_message(int(g), text)
        except Exception:
            pass

# ── Register ─────────────────────────────────────────────────────────────────
def register(app: Client):

    # /start in PRIVATE → mark DM-ready + portal
    @app.on_message(filters.private & filters.command("start"))
    async def start_private(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        changed = _set_dm_ready(uid)
        if changed:
            log.info(f"DM-ready set for user {uid}")
            await _announce_ready(client, m)
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # /start in groups → just show portal once
    @app.on_message(~filters.private & filters.command("start"))
    async def start_group(client: Client, m: Message):
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # Back/home
    @app.on_callback_query(filters.regex(r"^(dmf_home|portal:home|back_home)$"))
    async def cb_home(client: Client, cq: CallbackQuery):
        await _safe_edit(cq.message, WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)
        await cq.answer()

    # Links
    @app.on_callback_query(filters.regex(r"^(dmf_links|open_links|portal:links)$"))
    async def cb_links(client: Client, cq: CallbackQuery):
        await _safe_edit(cq.message, MODELS_LINKS_TEXT, reply_markup=_back_home_kb(), disable_web_page_preview=False)
        await cq.answer()

    # Menus
    @app.on_callback_query(filters.regex(r"^(dmf_open_menus|dmf_open_menu|open_menu|portal:menus|menus)$"))
    async def cb_menus(client: Client, cq: CallbackQuery):
        try:
            from handlers.menu import menu_tabs_text, menu_tabs_kb
            await _safe_edit(cq.message, menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception as e:
            log.warning(f"menus fallback used: {e}")
            await _safe_edit(
                cq.message,
                "💕 <b>Menus</b>\nPick a model or contact the team.",
                reply_markup=_back_home_kb(),
                disable_web_page_preview=True,
            )
        await cq.answer()

    # Admins
    @app.on_callback_query(filters.regex(r"^(dmf_admins|open_admins|portal:admins)$"))
    async def cb_admins(client: Client, cq: CallbackQuery):
        try:
            from handlers.contact_admins import CONTACT_TEXT, _kb_admins
            await _safe_edit(cq.message, CONTACT_TEXT, reply_markup=_kb_admins(), disable_web_page_preview=True)
        except Exception as e:
            log.warning(f"admins fallback used: {e}")
            await _safe_edit(
                cq.message,
                "👑 <b>Contact Admins</b>\nAdmin panel isn’t configured yet.",
                reply_markup=_back_home_kb(),
                disable_web_page_preview=True,
            )
        await cq.answer()

    # Help
    @app.on_callback_query(filters.regex(r"^(dmf_help|open_help|portal:help)$"))
    async def cb_help(client: Client, cq: CallbackQuery):
        try:
            from handlers.help_panel import HELP_MENU_TEXT, _help_menu_kb
            await _safe_edit(cq.message, HELP_MENU_TEXT, reply_markup=_help_menu_kb(), disable_web_page_preview=True)
        except Exception as e:
            log.warning(f"help fallback used: {e}")
            await _safe_edit(
                cq.message,
                "❓ <b>Help</b>\nChoose an option.",
                reply_markup=_back_home_kb(),
                disable_web_page_preview=True,
            )
        await cq.answer()
