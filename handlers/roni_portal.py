# handlers/roni_portal.py
import logging
import os
import json

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils.menu_store import store

log = logging.getLogger(__name__)

BOT_USERNAME = (os.getenv("BOT_USERNAME") or "YourBotUsernameHere").lstrip("@")
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "chaossub283").lstrip("@")
RONI_OWNER_ID = 6964994611

TIP_RONI_LINK = (os.getenv("TIP_RONI_LINK") or "").strip()

RONI_MENU_KEY = "RoniPersonalMenu"
OPEN_ACCESS_KEY = "RoniOpenAccessText"
TEASER_TEXT_KEY = "RoniTeaserChannelsText"
SANCTUARY_TEXT_KEY = "RoniSanctuaryText"

AGE_OK_PREFIX = "AGE_OK:"
AGE_INDEX_KEY = "RoniAgeIndex"  # legacy list


def _age_key(user_id: int) -> str:
    return f"{AGE_OK_PREFIX}{user_id}"


def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True  # Owner always has access to teaser/booking; verification is for users only.

    try:
        if store.get_menu(_age_key(user_id)):
            return True
    except Exception:
        pass

    try:
        raw = store.get_menu(AGE_INDEX_KEY) or "[]"
        ids = json.loads(raw)
        if isinstance(ids, list) and user_id in [int(x) for x in ids]:
            return True
    except Exception:
        pass

    return False


def _roni_main_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    rows.append([InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")])
    rows.append([InlineKeyboardButton("💌 Book Roni", url=f"https://t.me/{RONI_USERNAME}")])

    # Booking is age-locked for normal users, always visible to owner
    if user_id and is_age_verified(user_id):
        rows.append([InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:open")])

    if TIP_RONI_LINK:
        rows.append([InlineKeyboardButton("💸 Pay / Tip Roni", url=TIP_RONI_LINK)])
    else:
        rows.append([InlineKeyboardButton("💸 Pay / Tip Roni (coming soon)", callback_data="roni_portal:tip_coming")])

    rows.append([InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:open_access")])
    rows.append([InlineKeyboardButton("😈 Succubus Sanctuary", callback_data="roni_portal:sanctuary")])

    # Teaser is age-locked for users, but always available to owner
    if user_id and is_age_verified(user_id):
        rows.append([InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:teaser")])

    # Age verify (single entry point; no bypass/test)
    rows.append([InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:age")])

    rows.append([InlineKeyboardButton("😈 Models & Creators — Tap Here", url=f"https://t.me/{RONI_USERNAME}")])

    if user_id == RONI_OWNER_ID:
        rows.append([InlineKeyboardButton("⚙️ Roni Admin", callback_data="roni_admin:open")])

    return InlineKeyboardMarkup(rows)


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 Edit Roni Menu", callback_data="roni_admin:edit_menu")],
            [InlineKeyboardButton("🌸 Edit Open Access", callback_data="roni_admin:edit_open")],
            [InlineKeyboardButton("🔥 Edit Teaser/Promo Text", callback_data="roni_admin:edit_teaser")],
            [InlineKeyboardButton("😈 Edit Succubus Sanctuary", callback_data="roni_admin:edit_sanctuary")],
            [InlineKeyboardButton("🗓 NSFW availability (Roni)", callback_data="nsfw_avail:open")],
            [InlineKeyboardButton("🧾 Pending age verifications", callback_data="roni_admin:age_pending")],
            [InlineKeyboardButton("✅ Age-Verified List", callback_data="roni_admin:age_list")],
            [InlineKeyboardButton("⬅ Back to Assistant", callback_data="roni_portal:home")],
        ]
    )


def _assistant_welcome_text(user_id: int | None) -> str:
    av = (user_id == RONI_OWNER_ID) or (user_id and is_age_verified(user_id))
    if av:
        return (
            "Welcome back to Roni’s personal assistant. 💗\n"
            "You can book private texting sessions and view teaser links. ❤️‍🔥\n\n"
            "🚫 <b>NO meetups</b> — online/texting only."
        )
    return (
        "Welcome to Roni’s personal assistant. 💗\n\n"
        "To unlock NSFW booking + teaser links, tap ✅ <b>Age Verify</b> and submit the required photo.\n\n"
        "🚫 <b>NO meetups</b> — online/texting only."
    )


def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal registered")

    @app.on_message(filters.command("roni_portal"))
    async def roni_portal_command(_, m: Message):
        start_link = f"https://t.me/{BOT_USERNAME}?start=roni_assistant"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💗 Open Roni’s Assistant", url=start_link)]])
        await m.reply_text(
            "Welcome to Roni’s personal access channel.\n"
            "Click the button below to use my personal assistant SuccuBot for booking, payments, and more. 💋",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_message(filters.private & filters.command("start"), group=-1)
    async def roni_assistant_entry(_, m: Message):
        if not m.text:
            return
        parts = m.text.split(maxsplit=1)
        param = parts[1].strip() if len(parts) > 1 else ""
        if not param or not param.lower().startswith("roni_assistant"):
            return
        try:
            m.stop_propagation()
        except Exception:
            pass

        user_id = m.from_user.id if m.from_user else None
        await m.reply_text(
            _assistant_welcome_text(user_id),
            reply_markup=_roni_main_keyboard(user_id),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^roni_portal:home$"))
    async def roni_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        await cq.message.edit_text(
            _assistant_welcome_text(user_id),
            reply_markup=_roni_main_keyboard(user_id),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:tip_coming$"))
    async def roni_tip_coming_cb(_, cq: CallbackQuery):
        await cq.answer("Roni’s Stripe tip link is coming soon 💕", show_alert=True)

    @app.on_callback_query(filters.regex(r"^roni_portal:menu"))
    async def roni_menu_cb(_, cq: CallbackQuery):
        menu_text = store.get_menu(RONI_MENU_KEY)
        text = f"📖 <b>Roni’s Menu</b>\n\n{menu_text}" if menu_text else (
            "📖 <b>Roni’s Menu</b>\n\n"
            "Roni hasn’t set up her personal menu yet.\n"
            "She can do it from the ⚙️ Roni Admin button. 💕"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:open_access$"))
    async def roni_open_access_cb(_, cq: CallbackQuery):
        text = store.get_menu(OPEN_ACCESS_KEY) or (
            "🌸 <b>Open Access</b>\n\n"
            "Roni will add some safe-to-view goodies and general info here soon. 💕"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:sanctuary$"))
    async def roni_sanctuary_cb(_, cq: CallbackQuery):
        text = store.get_menu(SANCTUARY_TEXT_KEY) or (
            "😈 <b>Succubus Sanctuary</b>\n\n"
            "Roni will add details about her main Sanctuary hub here soon. 💕"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:teaser$"))
    async def roni_teaser_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if user_id != RONI_OWNER_ID and not (user_id and is_age_verified(user_id)):
            await cq.answer("You’ll need to complete photo age verification first 💕", show_alert=True)
            return
        teaser_text = store.get_menu(TEASER_TEXT_KEY) or (os.getenv("RONI_TEASER_CHANNELS_TEXT") or "Coming soon 💕")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]])
        await cq.message.edit_text(teaser_text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_admin:open$"))
    async def roni_admin_open_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return
        current = store.get_menu(RONI_MENU_KEY) or "No menu set yet."
        await cq.message.edit_text(
            "💜 <b>Roni Admin Panel</b>\n\n"
            "Edit your menu + text blocks and manage NSFW availability.\n\n"
            f"<b>Current menu preview:</b>\n\n{current}",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer()
