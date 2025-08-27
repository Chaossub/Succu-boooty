# dm_foolproof.py
# Single /start entrypoint & main portal. Robust DM-ready + no duplicate menus.

from __future__ import annotations
import os
import time
import json
import logging
from typing import Optional, Callable, Iterable, Union
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

DMREADY_NOTIFY_USER = os.getenv("DMREADY_NOTIFY_USER", "1") == "1"

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

# ── DM-ready backend discovery (optional) ────────────────────────────────────
_DM_SET_FN: Optional[Callable[[int], bool]] = None

def _discover_dm_store():
    """Find any available store; otherwise we’ll still announce without persisting."""
    global _DM_SET_FN
    if _DM_SET_FN:
        return
    # req_store.ReqStore
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
    # requirements_store
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
    # Fallback: none
    log.info("DM-ready backend: none (announce-only)")

_discover_dm_store()

# ── Local dedupe/barebones cache (so we don’t spam announces) ────────────────
_last_broadcast_ts = {}  # uid -> ts
BROADCAST_WINDOW = 60.0  # seconds

def _parse_group_ids(env_value: str) -> Iterable[Union[int, str]]:
    """
    Accepts: "-100123,-100456,@mygroup" (ints or @usernames).
    Returns iterator of cleaned ids/usernames.
    """
    for raw in env_value.split(","):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("@"):
            yield s  # username
            continue
        # try int
        try:
            yield int(s)
        except ValueError:
            # accept bare username without @ as well
            yield ("@" + s) if s and not s.startswith("@") else s

async def _announce_ready(client: Client, m: Message):
    uid = m.from_user.id if m.from_user else 0
    now = time.time()
    if uid in _last_broadcast_ts and now - _last_broadcast_ts[uid] < BROADCAST_WINDOW:
        return
    _last_broadcast_ts[uid] = now

    name = (m.from_user.first_name if m.from_user else "Someone")
    text = f"✅ DM-ready — {name} just opened the portal."

    env = os.getenv("SANCTUARY_GROUP_IDS", "")
    if not env:
        return
    for gid in _parse_group_ids(env):
        try:
            await client.send_message(gid, text)  # works for int id or @username
        except Exception as e:
            log.warning(f"DM-ready announce failed for {gid}: {e}")

def _set_dm_ready(uid: int) -> bool:
    """
    Returns True if changed to ready (or unknown but we still want to announce).
    """
    if _DM_SET_FN:
        try:
            return bool(_DM_SET_FN(uid))
        except Exception as e:
            log.warning(f"DM-ready backend failed for {uid}: {e}")
    # No backend means we still announce once.
    return True

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
            if DMREADY_NOTIFY_USER:
                try:
                    await m.reply_text("✅ You’re DM-ready! I can message you privately now.", quote=True)
                except Exception:
                    pass
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
