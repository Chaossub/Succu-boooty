# handlers/roni_portal_age.py
import logging
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient
import os

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611

# ─── Mongo ─────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DBNAME", "succubot")

mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]
age_col = db["age_verified_users"]


def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True
    return age_col.find_one({"user_id": user_id}) is not None


def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal_age registered")

    # ── User opens age verification ────────────────────
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def age_start(_, cq: CallbackQuery):
        if cq.message.chat.type != ChatType.PRIVATE:
            await cq.answer("Open this in DM 💕", show_alert=True)
            return

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ I confirm I’m 18+", callback_data="roni_age:confirm")],
                [InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")],
            ]
        )

        await cq.message.edit_text(
            "✅ <b>Age Verification</b>\n\n"
            "This assistant is for adults only.\n"
            "Tap below to confirm you’re 18+.\n\n"
            "🚫 <b>NO meetups</b> — online/texting only.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ── User confirms age ──────────────────────────────
    @app.on_callback_query(filters.regex(r"^roni_age:confirm$"))
    async def age_confirm(_, cq: CallbackQuery):
        u = cq.from_user
        if not u:
            return

        age_col.update_one(
            {"user_id": u.id},
            {
                "$set": {
                    "user_id": u.id,
                    "username": u.username or "",
                    "name": u.first_name or "",
                    "verified_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

        await cq.message.edit_text(
            "✅ <b>Verified</b> 💕\n\n"
            "You’re age-verified. NSFW booking and teaser links are now unlocked.\n\n"
            "🚫 <b>NO meetups</b> — online/texting only.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:start")],
                    [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer("Verified 💕")

    # ── Admin: view age-verified list ──────────────────
    @app.on_callback_query(filters.regex(r"^roni_admin:age_list$"))
    async def admin_age_list(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        users = list(age_col.find().sort("verified_at", -1).limit(50))

        if not users:
            text = "✅ <b>Age-Verified List</b>\n\n• none yet"
        else:
            lines = ["✅ <b>Age-Verified List</b>\n"]
            for u in users:
                name = u.get("name") or "User"
                if u.get("username"):
                    name += f" (@{u['username']})"
                lines.append(f"• {name} — <code>{u['user_id']}</code>")
            text = "\n".join(lines)

        await cq.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()
