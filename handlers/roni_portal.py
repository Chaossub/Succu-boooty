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

from utils.menu_store import store  # for persistent menu storage

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

# Your bot's username (without @) – used for the deep link
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "YourBotUsernameHere").lstrip("@")

# Your personal @username – used for customer + business DMs
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "chaossub283").lstrip("@")

# Your Telegram user ID (owner) – ONLY this ID sees / uses admin
RONI_OWNER_ID = 6964994611

# Stripe tip link for Roni (same env used in panels)
TIP_RONI_LINK = (os.getenv("TIP_RONI_LINK") or "").strip()

# Key used in menu_store for your personal assistant menu
RONI_MENU_KEY = "RoniPersonalMenu"

# Simple in-memory pending state for admin edits
_pending: dict[int, str] = {}


# ────────────── KEYBOARDS ──────────────

def _roni_main_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    """
    Build Roni's assistant keyboard.
    If user_id == RONI_OWNER_ID, show the admin button too.
    """
    rows: list[list[InlineKeyboardButton]] = []

    # Roni’s Menu (backed by Mongo via menu_store)
    rows.append([InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")])

    # 💌 Book Roni → open Roni’s DMs (customer side)
    rows.append(
        [
            InlineKeyboardButton(
                "💌 Book Roni",
                url=f"https://t.me/{RONI_USERNAME}",
            )
        ]
    )

    # 💸 Pay / Tip Roni – use Stripe if set, otherwise “coming soon”
    if TIP_RONI_LINK:
        rows.append(
            [InlineKeyboardButton("💸 Pay / Tip Roni", url=TIP_RONI_LINK)]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    "💸 Pay / Tip Roni (coming soon)",
                    callback_data="roni_portal:tip_coming",
                )
            ]
        )

    # 🌸 Open Access – placeholder for now
    rows.append([InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:todo")])

    # ✅ Age Verify – placeholder for now
    rows.append([InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:todo")])

    # 🔥 Teaser & Promo Channels – placeholder for now
    rows.append([InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:todo")])

    # 😈 Models & Creators — currently just opens your DMs
    rows.append(
        [
            InlineKeyboardButton(
                "😈 Models & Creators — Tap Here",
                url=f"https://t.me/{RONI_USERNAME}",
            )
        ]
    )

    # ⚙️ Roni Admin – only for you
    if user_id == RONI_OWNER_ID:
        rows.append(
            [InlineKeyboardButton("⚙️ Roni Admin", callback_data="roni_admin:open")]
        )

    # Back to main SuccuBot menu (Sanctuary side)
    rows.append(
        [
            InlineKeyboardButton(
                "🏠 Back to SuccuBot Menu",
                callback_data="panels:root",
            )
        ]
    )

    return InlineKeyboardMarkup(rows)


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 Edit Roni Menu", callback_data="roni_admin:edit_menu")],
            [InlineKeyboardButton("⬅ Back to Assistant", callback_data="roni_portal:home")],
        ]
    )


# ────────────── REGISTER ──────────────

def register(app: Client) -> None:
    log.info(
        "✅ handlers.roni_portal registered (owner=%s, bot=%s, roni=%s, tip_link=%s)",
        RONI_OWNER_ID,
        BOT_USERNAME,
        RONI_USERNAME,
        "set" if TIP_RONI_LINK else "missing",
    )

    # ───────── /roni_portal command (for your welcome channel) ─────────
    @app.on_message(filters.command("roni_portal"))
    async def roni_portal_command(_, m: Message):
        """
        Run this in your welcome channel.
        It replies with a button that opens DM with SuccuBot in assistant mode.
        """
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

    # ───────── /start roni_assistant in DM (assistant mode) ─────────
    # group=-1 makes this run BEFORE your normal /start handler from panels
    @app.on_message(filters.private & filters.command("start"), group=-1)
    async def roni_assistant_entry(_, m: Message):
        if not m.text:
            return

        parts = m.text.split(maxsplit=1)
        param = parts[1].strip() if len(parts) > 1 else ""

        # Only handle /start roni_assistant
        if not param or not param.lower().startswith("roni_assistant"):
            return  # Let the normal /start handler handle everything else

        # This IS our special assistant start – stop other /start handlers
        try:
            m.stop_propagation()
        except Exception:
            pass

        user_id = m.from_user.id if m.from_user else None
        kb = _roni_main_keyboard(user_id)

        await m.reply_text(
            "Welcome to Roni’s personal assistant. 💗\n"
            "Use the buttons below to explore her menu, booking options, and more.\n"
            "Some features are still being built, so you might see 'coming soon' for now. 💕",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ───────── Roni’s Menu (reads from Mongo) ─────────
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
                [InlineKeyboardButton("🏠 Back to SuccuBot Menu", callback_data="panels:root")],
            ]
        )
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── Back to main assistant menu ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:home$"))
    async def roni_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        kb = _roni_main_keyboard(user_id)
        await cq.message.edit_text(
            "Welcome to Roni’s personal assistant. 💗\n"
            "Use the buttons below to explore her menu, booking options, and more.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── Tip coming soon alert (if no Stripe link set) ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:tip_coming$"))
    async def roni_tip_coming_cb(_, cq: CallbackQuery):
        await cq.answer("Roni’s Stripe tip link is coming soon 💕", show_alert=True)

    # ───────── Placeholder for not-yet-implemented buttons ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:todo$"))
    async def roni_todo_cb(_, cq: CallbackQuery):
        await cq.answer("This feature is coming soon 💕", show_alert=True)

    # ───────── ADMIN: open admin panel (button-only) ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:open$"))
    async def roni_admin_open_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        current = store.get_menu(RONI_MENU_KEY) or "No menu set yet."

        await cq.message.edit_text(
            "💜 <b>Roni Admin Panel</b>\n\n"
            "This controls what shows under “📖 Roni’s Menu” in your assistant.\n\n"
            f"<b>Current menu preview:</b>\n\n{current}",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── ADMIN: start editing menu ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:edit_menu$"))
    async def roni_admin_edit_menu_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can edit this 💜", show_alert=True)
            return

        _pending[cq.from_user.id] = "menu"

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")],
            ]
        )

        await cq.message.edit_text(
            "📖 Send me your new menu text in one message.\n\n"
            "I’ll save it and your assistant will show it under “📖 Roni’s Menu”.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── ADMIN: cancel editing ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:cancel$"))
    async def roni_admin_cancel_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return

        _pending.pop(cq.from_user.id, None)

        user_id = cq.from_user.id
        kb = _roni_main_keyboard(user_id)

        await cq.message.edit_text(
            "Cancelled. No changes were made. 💜",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── ADMIN: capture new menu text (no slash commands) ─────────
    @app.on_message(filters.private & filters.text)
    async def roni_admin_capture(_, m: Message):
        if not m.from_user or m.from_user.id != RONI_OWNER_ID:
            return

        action = _pending.get(m.from_user.id)
        if not action:
            return

        # We only have one action right now: "menu"
        if action == "menu":
            store.set_menu(RONI_MENU_KEY, m.text)
            _pending.pop(m.from_user.id, None)

            await m.reply_text(
                "Saved your personal menu. 💕\n\n"
                "Your assistant will now show this under “📖 Roni’s Menu”.",
                disable_web_page_preview=True,
            )
