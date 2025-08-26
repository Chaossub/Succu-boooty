# dm_foolproof.py — Pyrogram 2.x, wire() pattern

from datetime import datetime
from os import getenv
from typing import Optional
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo.collection import Collection

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

# shared ENV (also read by handlers.menu)
FIND_URL = getenv("FIND_MODELS_ELSEWHERE_URL", "https://t.me/SuccuBot")
BUYER_RULES = getenv("BUYER_RULES_TEXT", "No rules found.")
BUYER_REQS  = getenv("BUYER_REQUIREMENTS_TEXT", "No requirements found.")
GAME_RULES  = getenv("GAME_RULES_TEXT", "No game rules found.")

RONI_USERNAME = getenv("ADMIN_RONI_USERNAME", "RoniJane")
RUBY_USERNAME = getenv("ADMIN_RUBY_USERNAME", "RubySanc")
MODEL_USERNAMES = {
    "Roni": getenv("MODEL_RONI_USERNAME", RONI_USERNAME),
    "Ruby": getenv("MODEL_RUBY_USERNAME", RUBY_USERNAME),
    "Rin":  getenv("MODEL_RIN_USERNAME", "RinSanc"),
    "Savy": getenv("MODEL_SAVY_USERNAME", "SavySanc"),
}

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="admins")],
        [InlineKeyboardButton("💞 Contact Models", callback_data="contact_models")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", url=FIND_URL)],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ])

# ---------- wire() entry ----------
def wire(app, mongo_client, owner_id: Optional[int] = None):
    """Call from main.py AFTER creating `app`."""
    coll: Optional[Collection] = None
    if mongo_client:
        coll = mongo_client["succubot"]["dm_ready"]

    async def mark(uid: int, uname: str | None):
        if coll:
            coll.update_one(
                {"_id": uid},
                {"$setOnInsert": {"username": uname or "", "at": datetime.utcnow()}},
                upsert=True
            )

    async def listed():
        if not coll:
            return []
        rows = coll.find().sort("at", -1).limit(50)
        return [f"- {r.get('username') or r['_id']}" for r in rows]

    # /start, /portal
    @app.on_message(filters.command(["start", "portal"]))
    async def _start(_, m):
        if coll and not coll.find_one({"_id": m.from_user.id}):
            await mark(m.from_user.id, m.from_user.username or m.from_user.first_name)
            await m.reply_text(
                f"✅ <b>{m.from_user.first_name}</b> is now DM-ready!",
                parse_mode=ParseMode.HTML
            )

        await m.reply_text(
            WELCOME_TEXT,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=kb_main()
        )

    # manual mark
    @app.on_message(filters.command(["dmready", "dm_ready"]))
    async def _dmready(_, m):
        await mark(m.from_user.id, m.from_user.username or m.from_user.first_name)
        await m.reply_text(
            f"✅ <b>{m.from_user.first_name}</b> is now DM-ready!",
            parse_mode=ParseMode.HTML
        )

    # list (staff)
    @app.on_message(filters.command(["dmreadylist", "list_dm_ready"]))
    async def _list(_, m):
        rows = await listed()
        txt = "No one is marked DM-ready yet." if not rows else "<b>DM-ready users (latest 50)</b>\n" + "\n".join(rows)
        await m.reply_text(txt, parse_mode=ParseMode.HTML)

    # expose small helpers for other modules if you want
    app._succubot_env = {
        "FIND_URL": FIND_URL,
        "BUYER_RULES": BUYER_RULES,
        "BUYER_REQS": BUYER_REQS,
        "GAME_RULES": GAME_RULES,
        "MODEL_USERNAMES": MODEL_USERNAMES,
        "RONI": RONI_USERNAME,
        "RUBY": RUBY_USERNAME,
        "OWNER_ID": owner_id or int(getenv("OWNER_ID", "0") or "0"),
    }
