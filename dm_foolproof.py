# dm_foolproof.py
# Private DM portal, DM-ready marking, and /start deep-link handling
from __future__ import annotations
import os, time, logging
from typing import Dict, Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType

log = logging.getLogger("dm_foolproof")

OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SANCTUARY_GROUP_IDS = [
    int(x.strip()) for x in (os.getenv("SANCTUARY_GROUP_IDS", "") or "").split(",") if x.strip()
]

# Button labels
BTN_MENUS  = os.getenv("BTN_MENUS", "💕 Menus")
BTN_ADMINS = os.getenv("BTN_CONTACT_ADMINS", "👑 Contact Admins")
BTN_FIND   = os.getenv("BTN_FIND_MODELS", "🔥 Find Our Models Elsewhere")
BTN_HELP   = os.getenv("BTN_HELP", "❓ Help")
BTN_BACK   = os.getenv("BTN_BACK_MAIN", "⬅️ Back to Main")

# Static texts
FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "All verified off-platform links are collected here.")
WELCOME_COPY = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

# ---------- de-dupe state (per-user) ----------
_last_start_ts: Dict[int, float] = {}
_last_portal_msg: Dict[int, int] = {}   # chat_id -> message_id
DEDUP_WINDOW = 2.0  # seconds

def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(BTN_MENUS, callback_data="dmf_main_menus")],
            [InlineKeyboardButton(BTN_ADMINS, callback_data="dmf_contact_admins")],
            [InlineKeyboardButton(BTN_FIND, callback_data="dmf_find_elsewhere")],
            [InlineKeyboardButton(BTN_HELP, callback_data="dmf_help")],
        ]
    )

def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="dmf_back_main")]])

async def _send_or_edit_portal(client: Client, chat_id: int) -> None:
    """Send the single main portal block—or edit the previous one if we have it."""
    text = WELCOME_COPY
    kb = _kb_main()
    msg_id = _last_portal_msg.get(chat_id)
    if msg_id:
        try:
            await client.edit_message_text(chat_id, msg_id, text, reply_markup=kb, disable_web_page_preview=True)
            return
        except Exception:
            # message might be gone or identical; fall through and send fresh
            pass
    m = await client.send_message(chat_id, text, reply_markup=kb, disable_web_page_preview=True)
    _last_portal_msg[chat_id] = m.id

def register(app: Client):

    # ---------- /start handler (private only) ----------
    @app.on_message(filters.private & filters.command("start"))
    async def start_portal(client: Client, m: Message):
        # re-entrancy/dup guard
        if not m.from_user:
            return
        uid = m.from_user.id
        now = time.time()
        if now - _last_start_ts.get(uid, 0.0) < DEDUP_WINDOW:
            return
        _last_start_ts[uid] = now

        # Deep-link payload: /start ready (mark DM-ready)
        payload = ""
        try:
            payload = (m.command[1] if len(m.command) > 1 else "").strip().lower()
        except Exception:
            payload = ""

        if payload == "ready":
            try:
                # mark DM-ready in your ReqStore (if present)
                from utils.req_store import ReqStore  # your existing store
                store = ReqStore()
                if store.set_dm_ready_global(uid, True):
                    # announce once to owner
                    uname = f"@{m.from_user.username}" if m.from_user.username else ""
                    try:
                        await client.send_message(
                            OWNER_ID,
                            f"✅ DM-ready — {m.from_user.first_name} {uname}"
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        # Show portal (single message)
        await _send_or_edit_portal(client, m.chat.id)

    # ---------- Main menu callbacks ----------
    @app.on_callback_query(filters.regex("^dmf_back_main$"))
    async def cb_back_main(client: Client, q):
        await q.answer()
        await _send_or_edit_portal(client, q.message.chat.id)

    @app.on_callback_query(filters.regex("^dmf_main_menus$"))
    async def cb_open_menus(client: Client, q):
        await q.answer()
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💘 Roni", callback_data="dmf_model_roni"),
                 InlineKeyboardButton("💘 Ruby", callback_data="dmf_model_ruby")],
                [InlineKeyboardButton("💘 Rin",  callback_data="dmf_model_rin"),
                 InlineKeyboardButton("💘 Savy", callback_data="dmf_model_savy")],
                [InlineKeyboardButton("💞 Contact Models", callback_data="dmf_contact_models")],
                [InlineKeyboardButton(BTN_BACK, callback_data="dmf_back_main")],
            ]
        )
        await q.message.edit_text("💕 <b>Menus</b>\nPick a model or contact the team.", reply_markup=kb)

    @app.on_callback_query(filters.regex("^dmf_contact_admins$"))
    async def cb_admins(client: Client, q):
        await q.answer()
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("👑 Message Roni", url=f"https://t.me/{os.getenv('RONI_USERNAME','')}")],
                [InlineKeyboardButton("👑 Message Ruby", url=f"https://t.me/{os.getenv('RUBY_USERNAME','')}")],
                [InlineKeyboardButton("🕵️ Anonymous Message", callback_data="dmf_anon")],
                [InlineKeyboardButton("💡 Suggestion Box", callback_data="dmf_suggest")],
                [InlineKeyboardButton(BTN_BACK, callback_data="dmf_back_main")],
            ]
        )
        await q.message.edit_text("How would you like to reach us?", reply_markup=kb)

    @app.on_callback_query(filters.regex("^dmf_find_elsewhere$"))
    async def cb_find_elsewhere(client: Client, q):
        await q.answer()
        await q.message.edit_text(
            f"✨ <b>Find Our Models Elsewhere</b> ✨\n\n{FIND_MODELS_TEXT}",
            reply_markup=_kb_back(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^dmf_help$"))
    async def cb_help(client: Client, q):
        await q.answer()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(BTN_BACK, callback_data="dmf_back_main")]])
        await q.message.edit_text("Help\nChoose an option.", reply_markup=kb)

