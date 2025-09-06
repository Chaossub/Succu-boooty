# handlers/panels.py
import os, time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply

# === HARD-CODED CONTACTS ===
RONI_USERNAME = "RoniUserHere"   # <-- put the real @ username (without @)
RUBY_USERNAME = "RubyUserHere"   # <-- put the real @ username (without @)

# admin that receives anonymous messages (we already have this in env)
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# your existing “find models elsewhere” text comes from MODELS_CHAT (per your env)
MODELS_ELSEWHERE_TEXT = os.getenv("MODELS_CHAT", "").strip() or "No links configured yet."

# ephemeral in-memory intake for anon messages (no new DB / handlers)
_PENDING_ANON = {}  # user_id -> expires_at (epoch seconds)

def main_menu_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menu", callback_data="menu")],
            [InlineKeyboardButton("📩 Contact Roni", url=f"https://t.me/{RONI_USERNAME}")],
            [InlineKeyboardButton("📩 Contact Ruby", url=f"https://t.me/{RUBY_USERNAME}")],
            [InlineKeyboardButton("🙈 Send Anonymous Message", callback_data="anon_admin")],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere 🔥", callback_data="models_elsewhere")],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
        ]
    )

# === callbacks ===

@Client.on_callback_query(filters.regex("^models_elsewhere$"))
async def _models_elsewhere(_, cq):
    await cq.message.edit_text(
        f"🔥 **Find Our Models Elsewhere** 🔥\n\n{MODELS_ELSEWHERE_TEXT}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]])
    )

@Client.on_callback_query(filters.regex("^anon_admin$"))
async def _anon_admin(_, cq):
    uid = cq.from_user.id
    # allow 5 minutes to type the anon message
    _PENDING_ANON[uid] = time.time() + 300
    await cq.message.reply_text(
        "✍️ Send me the **anonymous message** now (text only). I’ll deliver it to the admin.\n\n"
        "_You have 5 minutes. Type `/cancel` to abort._",
        reply_markup=ForceReply(selective=True)
    )
    await cq.answer("Waiting for your anonymous message…")

# capture next private text if waiting for anon
@Client.on_message(filters.private & filters.text)
async def _maybe_capture_anon(client, msg):
    uid = msg.from_user.id
    # cancel path
    if msg.text.strip().lower() == "/cancel":
        if uid in _PENDING_ANON:
            _PENDING_ANON.pop(uid, None)
            await msg.reply_text("🚫 Anonymous message canceled.")
        return

    # if user is in pending window, relay anonymously and clear
    exp = _PENDING_ANON.get(uid)
    if exp and exp > time.time():
        # DO NOT forward (that reveals user); send a fresh message
        body = msg.text
        if OWNER_ID > 0:
            await client.send_message(
                OWNER_ID,
                f"📨 **Anonymous message**\n\n{body}"
            )
        await msg.reply_text("✅ Sent anonymously to admin. Thanks!")
        _PENDING_ANON.pop(uid, None)

