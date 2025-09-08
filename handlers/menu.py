# handlers/admins.py
import os, time
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

MONGO_URL = os.getenv("MONGO_URL"); DB_NAME = os.getenv("MONGO_DB", "succubot")
_mcli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000); _db = _mcli[DB_NAME]
col_anon = _db.get_collection("anon_sessions")

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))
RONI_USERNAME = os.getenv("RONI_USERNAME", "")
RUBY_USERNAME = os.getenv("RUBY_USERNAME", "")

def _tg_url(username: str) -> str:
    return f"https://t.me/{username}" if username else "https://t.me/"

def _admins_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact Roni", url=_tg_url(RONI_USERNAME))],
        [InlineKeyboardButton("💬 Contact Ruby", url=_tg_url(RUBY_USERNAME))],
        [InlineKeyboardButton("🕵️ Send Anonymous Message", callback_data="anon:start")],
        [InlineKeyboardButton("🏠 Main", callback_data="home")],
    ])

def register(app: Client):
    @app.on_callback_query(filters.regex(r"^admins$"))
    async def _show_admins(_, q: CallbackQuery):
        await q.message.edit_text("👑 Contact Admins", reply_markup=_admins_kb())

    @app.on_callback_query(filters.regex(r"^anon:start$"))
    async def _start_anon(_, q: CallbackQuery):
        col_anon.update_one({"user_id": q.from_user.id}, {"$set": {"user_id": q.from_user.id, "ts": int(time.time())}}, upsert=True)
        await q.message.edit_text(
            "🕵️ *Anonymous message mode*\n\n"
            "Send me the message now. I’ll forward it anonymously to the owner.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admins")],
                [InlineKeyboardButton("🏠 Main", callback_data="home")]
            ]),
            disable_web_page_preview=True
        )

    @app.on_message(filters.private & ~filters.service)
    async def _anon_capture(c: Client, m: Message):
        if not m.from_user: return
        if not col_anon.find_one({"user_id": m.from_user.id}):
            return
        try:
            await c.copy_message(OWNER_ID, from_chat_id=m.chat.id, message_id=m.id)
            await m.reply_text("✅ Sent anonymously to the owner.")
        finally:
            col_anon.delete_one({"user_id": m.from_user.id})
