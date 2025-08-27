# dm_foolproof.py
# Single /start entrypoint & main portal.
# Marks users DM-ready (persisted), notifies OWNER_ID & any in DMREADY_NOTIFY_TO,
# and edits menus in-place (no duplicates).

from __future__ import annotations
import os, time, logging
from typing import Union
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import MessageNotModified
from utils.dmready_store import DMReadyStore

log = logging.getLogger("dm_foolproof")
store = DMReadyStore()

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

# ── Notification targets ─────────────────────────────────────────────────────
def _parse_targets(env_value: str) -> list[Union[int, str]]:
    out = []
    for raw in env_value.split(","):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("@"):
            out.append(s)
        else:
            try:
                out.append(int(s))
            except ValueError:
                out.append("@" + s)
    return out

_notify_targets = _parse_targets(
    os.getenv("DMREADY_NOTIFY_TO", str(os.getenv("OWNER_ID") or "").strip())
)
_group_targets = _parse_targets(os.getenv("SANCTUARY_GROUP_IDS", ""))

_last_announce: dict[int, float] = {}
ANNOUNCE_WINDOW = 60.0  # seconds

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

# ── Helpers ──────────────────────────────────────────────────────────────────
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

async def _notify_all(client: Client, text: str):
    for tgt in _notify_targets:
        try:
            await client.send_message(tgt, text)
        except Exception as e:
            log.warning(f"DM-ready notify failed for {tgt}: {e}")

async def _announce_groups(client: Client, text: str):
    for tgt in _group_targets:
        try:
            await client.send_message(tgt, text)
        except Exception as e:
            log.warning(f"Group announce failed for {tgt}: {e}")

# ── Register ─────────────────────────────────────────────────────────────────
def register(app: Client):

    # /start in PRIVATE → mark & notify if NEW
    @app.on_message(filters.private & filters.command("start"))
    async def start_private(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        name = (m.from_user.first_name if m.from_user else "Someone")
        uname = ("@" + m.from_user.username) if (m.from_user and m.from_user.username) else ""

        is_new = store.add(uid, first_name=name, username=(m.from_user.username if m.from_user else None))
        if is_new:
            log.info(f"DM-ready NEW user {uid} ({name})")
            now = time.time()
            if uid not in _last_announce or now - _last_announce[uid] > ANNOUNCE_WINDOW:
                _last_announce[uid] = now
                msg = f"✅ DM-ready — {name} {uname}".strip()
                await _notify_all(client, msg)
                if _group_targets:
                    await _announce_groups(client, msg)

        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # /start in groups → just show portal
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
