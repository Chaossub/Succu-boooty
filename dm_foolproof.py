# dm_foolproof.py  (Pyrogram 2.0.x)
from os import getenv
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo.collection import Collection

# --- wiring (imported by main.py) ---
app: Client  # main.py sets this
mongo = None  # main.py sets this (pymongo.MongoClient)
DMREADY_COLL: Collection = None

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

# ENV fallbacks (used by handlers/menu.py too)
ENV_FIND_ELSEWHERE = getenv("FIND_MODELS_ELSEWHERE_URL", "https://t.me/SuccuBot")
ENV_BUYER_RULES = getenv("BUYER_RULES_TEXT", "No rules found.")
ENV_BUYER_REQS = getenv("BUYER_REQUIREMENTS_TEXT", "No requirements found.")
ENV_GAME_RULES  = getenv("GAME_RULES_TEXT", "No game rules found.")

# Admin & models usernames (for deep-link buttons)
RONI_USERNAME = getenv("ADMIN_RONI_USERNAME", "RoniJane")
RUBY_USERNAME = getenv("ADMIN_RUBY_USERNAME", "RubySanc")
MODEL_USERNAMES = {
    "Roni": getenv("MODEL_RONI_USERNAME", RONI_USERNAME),
    "Ruby": getenv("MODEL_RUBY_USERNAME", RUBY_USERNAME),
    "Rin":  getenv("MODEL_RIN_USERNAME", "RinSanc"),
    "Savy": getenv("MODEL_SAVY_USERNAME", "SavySanc"),
}

def _kb_main() -> InlineKeyboardMarkup:
    from handlers.menu import kb_main  # reuse one source of truth
    return kb_main()

async def _ensure_collections():
    global DMREADY_COLL
    if mongo and not DMREADY_COLL:
        DMREADY_COLL = mongo["succubot"]["dm_ready"]

async def mark_dm_ready(uid: int, uname: str | None):
    await _ensure_collections()
    if DMREADY_COLL:
        DMREADY_COLL.update_one(
            {"_id": uid},
            {"$setOnInsert": {
                "username": uname or "",
                "at": datetime.utcnow()
            }},
            upsert=True
        )

async def is_dm_ready(uid: int) -> bool:
    await _ensure_collections()
    if DMREADY_COLL:
        return DMREADY_COLL.find_one({"_id": uid}) is not None
    return False  # if no DB, we’ll just not duplicate notice

async def list_dm_ready() -> list[str]:
    await _ensure_collections()
    if DMREADY_COLL:
        rows = DMREADY_COLL.find().sort("at", -1).limit(50)
        return [f"- {r.get('username') or r['_id']}" for r in rows]
    return []

def _dm_ready_notice(name: str) -> str:
    return f"✅ <b>{name}</b> is now DM-ready!"

# --- Commands ---

@app.on_message(filters.command(["start", "portal"]))
async def start_cmd(_, m):
    await _ensure_collections()

    # Mark DM-ready once
    already = await is_dm_ready(m.from_user.id)
    if not already:
        await mark_dm_ready(m.from_user.id, m.from_user.username or m.from_user.first_name)
        try:
            await m.reply_text(_dm_ready_notice(m.from_user.first_name), parse_mode=ParseMode.HTML)
        except Exception:
            pass

    # Send the welcome card with main menu underneath
    await m.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=_kb_main(),
        disable_web_page_preview=True
    )

# manual opt-in
@app.on_message(filters.command(["dmready", "dm_ready"]))
async def dmready_cmd(_, m):
    await mark_dm_ready(m.from_user.id, m.from_user.username or m.from_user.first_name)
    await m.reply_text(_dm_ready_notice(m.from_user.first_name), parse_mode=ParseMode.HTML)

# list (for staff)
@app.on_message(filters.command(["dmreadylist", "list_dm_ready"]))
async def dmready_list_cmd(_, m):
    rows = await list_dm_ready()
    if not rows:
        txt = "No one is marked DM-ready yet."
    else:
        txt = "<b>DM-ready users (latest 50)</b>\n" + "\n".join(rows)
    await m.reply_text(txt, parse_mode=ParseMode.HTML)

