# handlers/roni_portal.py
import logging
import os

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from pymongo import MongoClient

log = logging.getLogger(__name__)

BOT_USERNAME = (os.getenv("BOT_USERNAME") or "").lstrip("@")
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "").lstrip("@")
RONI_OWNER_ID = 6964994611
TIP_RONI_LINK = (os.getenv("TIP_RONI_LINK") or "").strip()

# ─── Mongo ─────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DBNAME", "succubot")

mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]
age_col = db["age_verified_users"]
menu_col = db["roni_menus"]


def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True
    return age_col.find_one({"user_id": user_id}) is not None


def get_menu(key: str) -> str | None:
    doc = menu_col.find_one({"key": key})
    return doc["value"] if doc else None


def _roni_main_keyboard(user_id: int | None) -> InlineKeyboardMarkup:
    rows = []

    rows.append([InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")])
    rows.append([InlineKeyboardButton("💌 Book Roni", url=f"https://t.me/{RONI_USERNAME}")])

    if user_id and is_age_verified(user_id):
        rows.append([InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:start")])

    if TIP_RONI_LINK:
        rows.append([InlineKeyboardButton("💸 Pay / Tip Roni", url=TIP_RONI_LINK)])
    else:
        rows.append([InlineKeyboardButton("💸 Pay / Tip Roni (coming soon)", callback_data="roni_portal:tip_coming")])

    rows.append([InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:open_access")])
    rows.append([InlineKeyboardButton("😈 Succubus Sanctuary", callback_data="roni_portal:sanctuary")])

    if user_id and is_age_verified(user_id):
        rows.append([InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:teaser")])
    else:
        rows.append([InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:age")])

    rows.append([InlineKeyboardButton("😈 Models & Creators — Tap Here", url=f"https://t.me/{RONI_USERNAME}")])

    if user_id == RONI_OWNER_ID:
        rows.append([InlineKeyboardButton("⚙️ Roni Admin", callback_data="roni_admin:open")])

    return InlineKeyboardMarkup(rows)


def _assistant_text(user_id: int | None) -> str:
    if is_age_verified(user_id):
        return (
            "Welcome back to Roni’s personal assistant. 💗\n"
            "You’re age-verified, so NSFW booking and teasers are unlocked.\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
    return (
        "Welcome to Roni’s personal assistant. 💗\n\n"
        "To access NSFW booking and teasers, please complete age verification.\n\n"
        "🚫 <b>NO meetups</b> — online/texting only."
    )


def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal registered")

    @app.on_message(filters.private & filters.command("start"), group=-1)
    async def roni_start(_, m: Message):
        if "roni_assistant" not in (m.text or ""):
            return
        try:
            m.stop_propagation()
        except Exception:
            pass

        uid = m.from_user.id if m.from_user else None
        await m.reply_text(
            _assistant_text(uid),
            reply_markup=_roni_main_keyboard(uid),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex("^roni_portal:home$"))
    async def home(_, cq: CallbackQuery):
        uid = cq.from_user.id
        await cq.message.edit_text(
            _assistant_text(uid),
            reply_markup=_roni_main_keyboard(uid),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^roni_portal:menu$"))
    async def menu(_, cq: CallbackQuery):
        text = get_menu("RoniPersonalMenu") or "Roni hasn’t set her menu yet 💕"
        await cq.message.edit_text(
            f"📖 <b>Roni’s Menu</b>\n\n{text}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^roni_admin:open$"))
    async def admin(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        await cq.message.edit_text(
            "💜 <b>Roni Admin Panel</b>\n\nManage menus, age verification, and bookings.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✅ Age-Verified List", callback_data="roni_admin:age_list")],
                    [InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()
