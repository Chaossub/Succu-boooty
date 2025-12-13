# handlers/roni_portal.py
import logging
import os

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from utils.menu_store import store  # persistent storage

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

BOT_USERNAME = (os.getenv("BOT_USERNAME") or "YourBotUsernameHere").lstrip("@")
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "chaossub283").lstrip("@")
RONI_OWNER_ID = 6964994611

TIP_RONI_LINK = (os.getenv("TIP_RONI_LINK") or "").strip()

RONI_MENU_KEY = "RoniPersonalMenu"
OPEN_ACCESS_KEY = "RoniOpenAccessText"
TEASER_TEXT_KEY = "RoniTeaserChannelsText"
SANCTUARY_TEXT_KEY = "RoniSanctuaryText"


# Age record key (read-only here; write happens in roni_portal_age)
def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"


# ────────────── SIMPLE AGE HELPERS (READ ONLY) ──────────────

def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        return bool(store.get_menu(_age_key(user_id)))
    except Exception:
        return False


# ────────────── KEYBOARDS & TEXT ──────────────

def _roni_main_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    """
    Build Roni's assistant keyboard (core side).
    Owner: sees teaser + Age Verify (test).
    Normal users: Age Verify before AV, Teaser after AV.
    """
    rows: list[list[InlineKeyboardButton]] = []

    rows.append([InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")])

    rows.append(
        [InlineKeyboardButton("💌 Book Roni", url=f"https://t.me/{RONI_USERNAME}")]
    )

    # ✅ NEW: booking flow (DM-only via Roni assistant menu)
    rows.append(
        [InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:open")]
    )

    if TIP_RONI_LINK:
        rows.append([InlineKeyboardButton("💸 Pay / Tip Roni", url=TIP_RONI_LINK)])
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    "💸 Pay / Tip Roni (coming soon)",
                    callback_data="roni_portal:tip_coming",
                )
            ]
        )

    rows.append([InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:open_access")])

    # NEW: Succubus Sanctuary button
    rows.append(
        [InlineKeyboardButton("😈 Succubus Sanctuary", callback_data="roni_portal:sanctuary")]
    )

    # teaser vs age verify
    if user_id == RONI_OWNER_ID:
        # Owner: show BOTH so you can test
        rows.append(
            [InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:teaser")]
        )
        rows.append(
            [InlineKeyboardButton("✅ Age Verify (test)", callback_data="roni_portal:age")]
        )
    elif user_id and is_age_verified(user_id):
        rows.append(
            [InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:teaser")]
        )
    else:
        rows.append(
            [InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:age")]
        )

    rows.append(
        [InlineKeyboardButton("😈 Models & Creators — Tap Here", url=f"https://t.me/{RONI_USERNAME}")]
    )

    if user_id == RONI_OWNER_ID:
        rows.append([InlineKeyboardButton("⚙️ Roni Admin", callback_data="roni_admin:open")])

    # NOTE: intentionally NO "Back to SuccuBot Menu" here – portal stays self-contained
    return InlineKeyboardMarkup(rows)


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 Edit Roni Menu", callback_data="roni_admin:edit_menu")],
            [InlineKeyboardButton("🌸 Edit Open Access", callback_data="roni_admin:edit_open")],
            [InlineKeyboardButton("🔥 Edit Teaser/Promo Text", callback_data="roni_admin:edit_teaser")],
            [InlineKeyboardButton("😈 Edit Succubus Sanctuary", callback_data="roni_admin:edit_sanctuary")],

            # ✅ NEW: owner-only availability panel (buttons only)
            [InlineKeyboardButton("🗓 NSFW availability (Roni)", callback_data="nsfw_avail:open")],

            [InlineKeyboardButton("✅ Age-Verified List", callback_data="roni_admin:age_list")],
            [InlineKeyboardButton("⬅ Back to Assistant", callback_data="roni_portal:home")],
        ]
    )


def _assistant_welcome_text(user_id: int | None) -> str:
    """Different welcome text depending on age-verified status."""
    is_owner = (user_id == RONI_OWNER_ID)
    av = is_owner or (user_id and is_age_verified(user_id))

    if av:
        # After age verification (or you)
        return (
            "Welcome back to Roni’s personal assistant. 💗\n"
            "You’re age-verified, so you can use the buttons below to see her menu, "
            "booking options, and her teaser & promo channels. ❤️‍🔥"
        )
    else:
        # Before age verification
        return (
            "Welcome to Roni’s personal assistant. 💗\n"
            "Use the buttons below to explore her menu, booking options, and more.\n\n"
            "If you want access to Roni’s free NSFW links and teaser / promo channels, "
            "tap ✅ <b>Age Verify</b> to confirm you’re 18+. ❤️‍🔥"
        )


# ────────────── REGISTER (CORE HANDLERS ONLY) ──────────────

def register(app: Client) -> None:
    log.info(
        "✅ handlers.roni_portal (core) registered (owner=%s, bot=%s, roni=%s, tip_link=%s)",
        RONI_OWNER_ID,
        BOT_USERNAME,
        RONI_USERNAME,
        "set" if TIP_RONI_LINK else "missing",
    )

    # ───────── /roni_portal (welcome channel button) ─────────
    @app.on_message(filters.command("roni_portal"))
    async def roni_portal_command(_, m: Message):
        start_link = f"https://t.me/{BOT_USERNAME}?start=roni_assistant"
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💗 Open Roni’s Assistant", url=start_link)]]
        )
        await m.reply_text(
            "Welcome to Roni’s personal access channel.\n"
            "Click the button below to use my personal assistant SuccuBot for booking, "
            "payments, and more. 💋",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ───────── /start roni_assistant (DM entry) ─────────
    # ✅ FIX: run earlier than other /start handlers so it doesn't get swallowed
    @app.on_message(filters.private & filters.command("start"), group=-10)
    async def roni_assistant_entry(_, m: Message):
        if not m.text:
            return

        parts = m.text.split(maxsplit=1)
        param = parts[1].strip() if len(parts) > 1 else ""

        if not param or not param.lower().startswith("roni_assistant"):
            return

        # ✅ FIX: stop other /start handlers from stealing this
        try:
            m.stop_propagation()
        except Exception:
            pass

        user_id = m.from_user.id if m.from_user else None
        kb = _roni_main_keyboard(user_id)
        text = _assistant_welcome_text(user_id)

        await m.reply_text(
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ───────── Roni menu ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:menu$"))
    async def roni_menu_cb(_, cq: CallbackQuery):
        menu_text = store.get_menu(RONI_MENU_KEY)

        if menu_text:
            text = f"📖 <b>Roni’s Menu</b>\n\n{menu_text}"
        else:
            text = (
                "📖 <b>Roni’s Menu</b>\n\n"
                "Roni hasn’t set up her personal menu yet.\n"
                "She can do it from the ⚙️ Roni Admin button. 💕"
            )

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── Back to assistant ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:home$"))
    async def roni_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        kb = _roni_main_keyboard(user_id)
        text = _assistant_welcome_text(user_id)

        await cq.message.edit_text(
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── Tip coming soon ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:tip_coming$"))
    async def roni_tip_coming_cb(_, cq: CallbackQuery):
        await cq.answer("Roni’s Stripe tip link is coming soon 💕", show_alert=True)

    # ───────── Open Access ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:open_access$"))
    async def roni_open_access_cb(_, cq: CallbackQuery):
        text = store.get_menu(OPEN_ACCESS_KEY) or (
            "🌸 <b>Open Access</b>\n\n"
            "Roni will add some safe-to-view goodies and general info here soon. 💕"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── Succubus Sanctuary (core text) ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:sanctuary$"))
    async def roni_sanctuary_cb(_, cq: CallbackQuery):
        text = store.get_menu(SANCTUARY_TEXT_KEY) or (
            "😈 <b>Succubus Sanctuary</b>\n\n"
            "Roni will add details about her main Sanctuary hub here soon. 💕"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── Teaser & Promo (gated, but logic here) ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:teaser$"))
    async def roni_teaser_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None

        if user_id != RONI_OWNER_ID and not (user_id and is_age_verified(user_id)):
            await cq.answer(
                "You’ll need to complete age verification before seeing Roni’s teaser channels. 💕",
                show_alert=True,
            )
            return

        teaser_text = store.get_menu(TEASER_TEXT_KEY) or (
            os.getenv("RONI_TEASER_CHANNELS_TEXT")
            or "Roni will add her teaser & promo channels here soon. 💕"
        )

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )

        await cq.message.edit_text(teaser_text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── Admin panel (open + text edits) ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:open$"))
    async def roni_admin_open_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        current = store.get_menu(RONI_MENU_KEY) or "No menu set yet."

        await cq.message.edit_text(
            "💜 <b>Roni Admin Panel</b>\n\n"
            "This controls what shows under “📖 Roni’s Menu” in your assistant, "
            "your Open Access text, teaser/promo text, Succubus Sanctuary text, "
            "and lets you review age verification.\n\n"
            f"<b>Current menu preview:</b>\n\n{current}",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_admin:edit_menu$"))
    async def roni_admin_edit_menu_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can edit this 💜", show_alert=True)
            return

        # mark in a tiny in-memory flag via message context – actual capture is below
        from_user_id = cq.from_user.id
        store.set_menu(f"_RONI_PENDING:{from_user_id}", "menu")

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")]])
        await cq.message.edit_text(
            "📖 Send me your new menu text in one message.\n\n"
            "I’ll save it and your assistant will show it under “📖 Roni’s Menu”.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_admin:edit_open$"))
    async def roni_admin_edit_open_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can edit this 💜", show_alert=True)
            return

        from_user_id = cq.from_user.id
        store.set_menu(f"_RONI_PENDING:{from_user_id}", "open_access")

        current = store.get_menu(OPEN_ACCESS_KEY) or "No Open Access text set yet."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")]])
        await cq.message.edit_text(
            "🌸 <b>Edit Open Access</b>\n\n"
            "This is what people see when they tap “🌸 Open Access”.\n\n"
            f"<b>Current text:</b>\n\n{current}\n\n"
            "Send me the new text in one message, and I’ll replace it.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_admin:edit_teaser$"))
    async def roni_admin_edit_teaser_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can edit this 💜", show_alert=True)
            return

        from_user_id = cq.from_user.id
        store.set_menu(f"_RONI_PENDING:{from_user_id}", "teaser")

        current = store.get_menu(TEASER_TEXT_KEY) or (
            os.getenv("RONI_TEASER_CHANNELS_TEXT") or "No teaser/promo text set yet."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")]])
        await cq.message.edit_text(
            "🔥 <b>Edit Teaser & Promo Text</b>\n\n"
            "This is what verified users see when they tap “🔥 Teaser & Promo Channels”.\n\n"
            f"<b>Current text:</b>\n\n{current}\n\n"
            "Send me the new text in one message, and I’ll replace it.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_admin:edit_sanctuary$"))
    async def roni_admin_edit_sanctuary_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can edit this 💜", show_alert=True)
            return

        from_user_id = cq.from_user.id
        store.set_menu(f"_RONI_PENDING:{from_user_id}", "sanctuary")

        current = store.get_menu(SANCTUARY_TEXT_KEY) or "No Succubus Sanctuary text set yet."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")]])
        await cq.message.edit_text(
            "😈 <b>Edit Succubus Sanctuary</b>\n\n"
            "This is what people see when they tap “😈 Succubus Sanctuary”.\n\n"
            f"<b>Current text:</b>\n\n{current}\n\n"
            "Send me the new text in one message, and I’ll replace it.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_admin:cancel$"))
    async def roni_admin_cancel_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return

        store.set_menu(f"_RONI_PENDING:{cq.from_user.id}", "")

        user_id = cq.from_user.id
        kb = _roni_main_keyboard(user_id)

        await cq.message.edit_text(
            "Cancelled. No changes were made. 💜",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── Capture admin text edits (menu/open/teaser/sanctuary) ─────────
    @app.on_message(filters.private & filters.text, group=-2)
    async def roni_admin_capture(_, m: Message):
        if not m.from_user or m.from_user.id != RONI_OWNER_ID:
            return

        pending_key = f"_RONI_PENDING:{m.from_user.id}"
        action = store.get_menu(pending_key) or ""
        if not action:
            return

        # clear the pending flag
        store.set_menu(pending_key, "")

        if action == "menu":
            store.set_menu(RONI_MENU_KEY, m.text)
            current = store.get_menu(RONI_MENU_KEY) or "No menu set yet."
            await m.reply_text(
                "Saved your personal menu. 💕\n\n"
                "You’re back in the Roni Admin panel — here’s your current menu preview:\n\n"
                f"{current}",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return

        if action == "open_access":
            store.set_menu(OPEN_ACCESS_KEY, m.text)
            await m.reply_text(
                "Saved your 🌸 Open Access text. 💕\n\n"
                "Anyone tapping “🌸 Open Access” will now see this updated block.",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return

        if action == "teaser":
            store.set_menu(TEASER_TEXT_KEY, m.text)
            await m.reply_text(
                "Saved your 🔥 Teaser & Promo text. 💕\n\n"
                "Age-verified users tapping “🔥 Teaser & Promo Channels” will now see this updated block.",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return

        if action == "sanctuary":
            store.set_menu(SANCTUARY_TEXT_KEY, m.text)
            await m.reply_text(
                "Saved your 😈 Succubus Sanctuary text. 💕\n\n"
                "Anyone tapping “😈 Succubus Sanctuary” will now see this updated block.",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return
