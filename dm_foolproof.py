# dm_foolproof.py
# (only differences from your current file are marked <<< CHANGED >>>)

import os, time, asyncio, secrets, json
from typing import Optional, List, Dict
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from pyrogram.errors import RPCError, FloodWait, UserIsBlocked, PeerIdInvalid

# Optional req store (unchanged) ...
# [keep your existing req_store/_DummyStore block here]

# ==== ENV ====
OWNER_ID       = int(os.getenv("OWNER_ID", "0"))
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "6964994611"))
SUPER_ADMINS   = {int(x) for x in os.getenv("SUPER_ADMINS", "6964994611,8087941938").replace(";", ",").split(",") if x.strip().isdigit()}
MODEL_IDS      = {int(x) for x in os.getenv("MODEL_IDS", "5650388514,6307783399").replace(";", ",").split(",") if x.strip().isdigit()}

RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME",  "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

RUBY_ID = int(os.getenv("RUBY_ID", "8087941938"))
RIN_ID  = int(os.getenv("RIN_ID",  "0"))
SAVY_ID = int(os.getenv("SAVY_ID", "0"))

DM_READY_NOTIFY_MODE = os.getenv("DM_READY_NOTIFY_MODE", "first_time").lower()
DM_FORWARD_MODE      = os.getenv("DM_FORWARD_MODE", "off").lower()
SHOW_RELAY_KB        = os.getenv("SHOW_RELAY_KB", "first_time").lower()

RULES_TEXT      = os.getenv("RULES_TEXT", "")
BUYER_REQ_TEXT  = os.getenv("BUYER_REQ_TEXT", "")
RULES_PHOTO     = os.getenv("RULES_PHOTO")
BUYER_REQ_PHOTO = os.getenv("BUYER_REQ_PHOTO")

MODELS_LINKS_TEXT = os.getenv(
    "MODELS_LINKS_TEXT",
    "🔥 Find Our Models Elsewhere 🔥\n\n"
    "👑 Roni Jane (Owner)\n"
    "https://allmylinks.com/chaossub283\n\n"
    "💎 Ruby Ransom (Co-Owner)\n"
    "(Link coming soon)\n\n"
    "🍑 Peachy Rin\n"
    "https://allmylinks.com/peachybunsrin\n\n"
    "⚡ Savage Savy\n"
    "https://allmylinks.com/savannahxsavage"
)
MODELS_LINKS_PHOTO = os.getenv("MODELS_LINKS_PHOTO")
MODELS_LINKS_BUTTONS_JSON = os.getenv("MODELS_LINKS_BUTTONS_JSON")

# <<< CHANGED: commands we must NOT intercept in the DM catch-all >>>
MENU_ADMIN_CMDS = ["addmenu", "changemenu", "deletemenu", "listmenus"]

# ==== STATE ==== (unchanged)
_pending: Dict[int, Dict[str, bool]] = {}
_kb_last_shown: Dict[int, float] = {}
_anon_threads: Dict[str, int] = {}
_admin_pending_reply: Dict[int, str] = {}

# ==== ROLE HELPERS / HELPERS / UI BUILDERS ====
# [keep your existing helper + UI functions here unchanged]

# ==== REGISTER ====
def register(app: Client):

    # /start → Welcome UI  (unchanged)
    @app.on_message(filters.private & filters.command("start"))
    async def dmf_start(client: Client, m: Message):
        # [body unchanged]
        ...

    # /dmsetup (unchanged)
    @app.on_message(filters.command("dmsetup"))
    async def dmsetup(client: Client, m: Message):
        # [body unchanged]
        ...

    # /message|/contact (unchanged)
    @app.on_message(filters.private & filters.command(["message", "contact"]))
    async def dm_message_panel(client: Client, m: Message):
        # [body unchanged]
        ...

    # <<< CHANGED: catch-all DM inbox excludes menu admin commands >>>
    @app.on_message(
        filters.private
        & ~filters.command(["message", "contact", "start"] + MENU_ADMIN_CMDS)
    )
    async def on_private_message(client: Client, m: Message):
        # [body unchanged]
        ...

    # All your callback handlers and admin commands below remain unchanged
    # (dmf_back_welcome, dmf_show_help, dmf_* callbacks, dmready/dmunready, dmreadylist, dmnudge, etc.)
    ...
