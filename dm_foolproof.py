# Root module: dm_foolproof.py
# - Sends welcome -> "Menu" button on /start
# - Provides Menu -> Contact Models / Contact Admins / Find Elsewhere / Help
# - Marks user DM-ready once (global) and notifies OWNER/SUPER once
# - Shows usernames (not raw IDs) on /dm_ready list
# - No duplicate /start handler side-effects, no html parse mode issues

import os
import time
from contextlib import suppress
from typing import List, Tuple, Optional, Dict

from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

# ---- ReqStore (global DM-ready) ---------------------------------------------
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

def _to_int(x: Optional[str]) -> Optional[int]:
    try:
        return int(str(x)) if x not in (None, "", "None") else None
    except Exception:
        return None

OWNER_ID       = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))

DM_READY_ALERT_CHAT = _to_int(os.getenv("DM_READY_ALERT_CHAT") or str(OWNER_ID or ""))  # where to notify

# ---- Content strings (plain text; no HTML parse mode needed) ----------------
WELCOME_TEXT = (
    "Hey! I’m your SuccuBot assistant.\n"
    "Tap **Menu** to get started. I’ll only mark you DM-ready once."
)

HELP_TEXT = (
    "Help\n"
    "— Commands available to everyone:\n"
    "   • /start – open the menu\n"
    "   • /menu – open the menu\n"
    "   • /dm_ready – see who’s DM-ready (admins only list everyone)\n"
    "\n"
    "Game Rules:\n"
    "• Be kind. No harassment.\n"
    "• Follow host instructions.\n"
    "\n"
    "Buyer Requirements:\n"
    "• Complete verification\n"
    "• Agree to buyer rules\n"
    "\n"
    "Buyer Rules:\n"
    "• No chargebacks\n"
    "• Respect boundaries\n"
)

FIND_ELSEWHERE_TEXT = (
    "Find Our Models Elsewhere\n"
    "Here’s the hub with all off-platform links."
)

CONTACT_MODELS_ELSEWHERE_TEXT = (
    "Contact Our Models Elsewhere\n"
    "Use the directory below to reach models off Telegram."
)

ANON_INSTRUCTIONS = (
    "Anonymous Message\n"
    "Reply here with your message. We’ll forward it without your name."
)

# Optionally override with ENV links
FIND_ELSEWHERE_LINK = os.getenv("FIND_ELSEWHERE_LINK", "")
CONTACT_MODELS_ELSEWHERE_LINK = os.getenv("CONTACT_MODELS_ELSEWHERE_LINK", "")

# ---- Models & Admins --------------------------------------------------------
def _parse_models() -> List[Tuple[str, str]]:
    """
    Build a list of models as (label, username_link).
    Uses MODELS_CSV like:  Label1,@user1|Label2,@user2
    Ensures Roni present if RONI_USERNAME is set.
    """
    items: List[Tuple[str, str]] = []
    raw = os.getenv("MODELS_CSV", "").strip()
    if raw:
        for part in raw.split("|"):
            piece = part.strip()
            if not piece:
                continue
            try:
                label, user = [p.strip() for p in piece.split(",", 1)]
            except ValueError:
                continue
            if not label or not user:
                continue
            if not user.startswith("@"):
                user = "@" + user.lstrip("@")
            items.append((label, user))

    # Ensure Roni appears (as requested) under Contact Models
    roni_user = os.getenv("RONI_USERNAME", "").strip()
    if roni_user:
        if not roni_user.startswith("@"):
            roni_user = "@" + roni_user.lstrip("@")
        # Insert if not already present
        if all(u.lower() != roni_user.lower() for _, u in items):
            items.insert(0, ("Roni", roni_user))

    # Fallback if empty
    if not items:
        items = [("Roni", "@Roni"), ("Ruby", "@Ruby")]
    return items

def _parse_admins() -> List[Tuple[str, str]]:
    """
    Contact Admins menu: ensure both Roni and Ruby are present.
    ADMIN_CSV like:  Roni,@roni|Ruby,@ruby
    """
    items: List[Tuple[str, str]] = []
    raw = os.getenv("ADMIN_CSV", "").strip()
    if raw:
        for part in raw.split("|"):
            piece = part.strip()
            if not piece:
                continue
            try:
                label, user = [p.strip() for p in piece.split(",", 1)]
            except ValueError:
                continue
            if not label or not user:
                continue
            if not user.startswith("@"):
                user = "@" + user.lstrip("@")
            items.append((label, user))

    # Ensure Roni
    roni_user = os.getenv("RONI_USERNAME", "").strip()
    if roni_user:
        if not roni_user.startswith("@"):
            roni_user = "@" + roni_user.lstrip("@")
        if all(lbl.lower() != "roni" for lbl, _ in items):
            items.insert(0, ("Roni", roni_user))
    else:
        if all(lbl.lower() != "roni" for lbl, _ in items):
            items.insert(0, ("Roni", "@Roni"))

    # Ensure Ruby
    ruby_user = os.getenv("RUBY_USERNAME", "").strip()
    if ruby_user:
        if not ruby_user.startswith("@"):
            ruby_user = "@" + ruby_user.lstrip("@")
        if all(lbl.lower() != "ruby" for lbl, _ in items):
            items.append(("Ruby", ruby_user))
    else:
        if all(lbl.lower() != "ruby" for lbl, _ in items):
            items.append(("Ruby", "@Ruby"))

    return items

# ---- Keyboards --------------------------------------------------------------
BTN_MENU                    = "Menu"
BTN_BACK_TO_MENU            = "⬅️ Back"

BTN_CONTACT_MODELS          = "Contact Models"
BTN_CONTACT_ADMINS          = "Contact Admins"
BTN_FIND_ELSEWHERE          = "Find Our Models Elsewhere"
BTN_HELP                    = "Help"

BTN_CONTACT_MODELS_ELSE     = "Contact Our Models Elsewhere"
BTN_ANON_MESSAGE            = "Anonymous Message"

def _kb_start():
    return ReplyKeyboardMarkup([[BTN_MENU]], resize_keyboard=True, one_time_keyboard=False)

def _kb_main():
    return ReplyKeyboardMarkup(
        [
            [BTN_CONTACT_MODELS],
            [BTN_CONTACT_ADMINS],
            [BTN_FIND_ELSEWHERE],
            [BTN_HELP],
        ],
        resize_keyboard=True
    )

def _kb_back():
    return ReplyKeyboardMarkup([[BTN_BACK_TO_MENU]], resize_keyboard=True)

def _kb_models():
    rows = []
    models = _parse_models()
    # 2 per row for compactness
    line = []
    for label, _ in models:
        line.append(label)
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([BTN_CONTACT_MODELS_ELSE])
    rows.append([BTN_BACK_TO_MENU])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def _kb_admins():
    admins = _parse_admins()
    rows = []
    line = []
    for label, _ in admins:
        line.append(label)
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([BTN_ANON_MESSAGE])
    rows.append([BTN_BACK_TO_MENU])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ---- Helpers ----------------------------------------------------------------
def _user_display(u) -> str:
    if hasattr(u, "mention"):
        # mention with markdown
        return f"[{u.first_name or 'User'}](tg://user?id={u.id})"
    if getattr(u, "username", None):
        return f"@{u.username}"
    return f"{u.first_name or 'User'}"

async def _notify_dm_ready_once(client: Client, m: Message):
    """Mark DM-ready globally once; notify OWNER/SUPER only on first time."""
    if not _store:
        return
    uid = m.from_user.id
    if _store.is_dm_ready_global(uid):
        return  # already marked -> do nothing

    _store.set_dm_ready_global(uid, True, by_admin=False)

    name = _user_display(m.from_user)
    text = f"✅ {name} is now DM-ready."
    # Try to send to DM_READY_ALERT_CHAT if set, otherwise skip silently
    if DM_READY_ALERT_CHAT:
        with suppress(Exception):
            await client.send_message(DM_READY_ALERT_CHAT, text, disable_web_page_preview=True)

# ---- Handlers ---------------------------------------------------------------
def register(app: Client):
    # /start and /menu commands (private only)
    @app.on_message(filters.command(["start", "menu"]) & filters.private, group=0)
    async def start_cmd(client: Client, m: Message):
        # Mark DM-ready only once; then show start keyboard with "Menu"
        with suppress(Exception):
            await _notify_dm_ready_once(client, m)

        # Welcome + single "Menu" button
        await m.reply_text(
            WELCOME_TEXT,
            reply_markup=_kb_start(),
            disable_web_page_preview=True
        )

    # Main menu button
    @app.on_message(filters.private & filters.text & filters.regex(f"^{BTN_MENU}$"), group=0)
    async def open_main_menu(client: Client, m: Message):
        await m.reply_text(
            "Main Menu",
            reply_markup=_kb_main(),
            disable_web_page_preview=True
        )

    # Back button
    @app.on_message(filters.private & filters.text & filters.regex(f"^{BTN_BACK_TO_MENU}$"), group=0)
    async def back_to_menu(client: Client, m: Message):
        await m.reply_text("Back to Main Menu", reply_markup=_kb_main(), disable_web_page_preview=True)

    # Contact Models
    @app.on_message(filters.private & filters.text & filters.regex(f"^{BTN_CONTACT_MODELS}$"), group=0)
    async def open_models(client: Client, m: Message):
        await m.reply_text("Contact Models", reply_markup=_kb_models(), disable_web_page_preview=True)

    # Contact Admins
    @app.on_message(filters.private & filters.text & filters.regex(f"^{BTN_CONTACT_ADMINS}$"), group=0)
    async def open_admins(client: Client, m: Message):
        await m.reply_text("Contact Admins", reply_markup=_kb_admins(), disable_web_page_preview=True)

    # Find Our Models Elsewhere
    @app.on_message(filters.private & filters.text & filters.regex(f"^{BTN_FIND_ELSEWHERE}$"), group=0)
    async def find_elsewhere(client: Client, m: Message):
        extra = f"\n\n{FIND_ELSEWHERE_LINK}" if FIND_ELSEWHERE_LINK else ""
        await m.reply_text(FIND_ELSEWHERE_TEXT + extra, reply_markup=_kb_back(), disable_web_page_preview=True)

    # Help
    @app.on_message(filters.private & filters.text & filters.regex(f"^{BTN_HELP}$"), group=0)
    async def help_menu(client: Client, m: Message):
        await m.reply_text(HELP_TEXT, reply_markup=_kb_back(), disable_web_page_preview=True)

    # Contact Our Models Elsewhere (button inside Contact Models)
    @app.on_message(filters.private & filters.text & filters.regex(f"^{BTN_CONTACT_MODELS_ELSE}$"), group=0)
    async def contact_models_elsewhere(client: Client, m: Message):
        extra = f"\n\n{CONTACT_MODELS_ELSEWHERE_LINK}" if CONTACT_MODELS_ELSEWHERE_LINK else ""
        await m.reply_text(CONTACT_MODELS_ELSEWHERE_TEXT + extra, reply_markup=_kb_back(), disable_web_page_preview=True)

    # Anonymous Message (button inside Contact Admins)
    @app.on_message(filters.private & filters.text & filters.regex(f"^{BTN_ANON_MESSAGE}$"), group=0)
    async def anon_msg(client: Client, m: Message):
        await m.reply_text(ANON_INSTRUCTIONS, reply_markup=_kb_back(), disable_web_page_preview=True)

    # Dynamic buttons for each Model/Admin by label (send their @ link)
    @app.on_message(filters.private & filters.text, group=1)
    async def dynamic_buttons(client: Client, m: Message):
        txt = (m.text or "").strip()
        # Models
        for label, user in _parse_models():
            if txt == label:
                await m.reply_text(f"{label}: {user}", reply_markup=_kb_models(), disable_web_page_preview=True)
                return
        # Admins
        for label, user in _parse_admins():
            if txt == label:
                await m.reply_text(f"{label}: {user}", reply_markup=_kb_admins(), disable_web_page_preview=True)
                return

    # /dm_ready command
    @app.on_message(filters.command(["dm_ready", "dmready"]) & filters.private, group=0)
    async def cmd_dm_ready(client: Client, m: Message):
        if not _store:
            await m.reply_text("DM-ready list is unavailable.", reply_markup=_kb_back())
            return

        dm_map: Dict[str, dict] = _store.list_dm_ready_global()  # { "user_id": {...} }
        if not dm_map:
            await m.reply_text("No users are marked DM-ready yet.", reply_markup=_kb_back())
            return

        # Fetch display names
        ids = [int(uid) for uid in dm_map.keys()]
        # Split in chunks to be safe
        chunks = [ids[i:i + 100] for i in range(0, len(ids), 100)]
        pieces: List[str] = []
        for ch in chunks:
            with suppress(Exception):
                users = await client.get_users(ch)
                if not isinstance(users, list):
                    users = [users]
                for u in users:
                    pieces.append(f"• {_user_display(u)}")

        if not pieces:
            # fallback if lookups failed
            pieces = [f"• {uid}" for uid in ids]

        await m.reply_text(
            "DM-Ready Users:\n" + "\n".join(pieces),
            reply_markup=_kb_back(),
            disable_web_page_preview=True
        )
