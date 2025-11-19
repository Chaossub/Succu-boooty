# handlers/roni_portal.py
import logging
import os
import json
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from utils.menu_store import store  # for persistent storage

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

# Your bot's username (without @) – used for the deep link
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "YourBotUsernameHere").lstrip("@")

# Your personal @username – used for customer + business DMs
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "chaossub283").lstrip("@")

# Your Telegram user ID (owner) – ONLY this ID sees / uses admin + approvals
RONI_OWNER_ID = 6964994611

# Stripe tip link for Roni (same env used in panels)
TIP_RONI_LINK = (os.getenv("TIP_RONI_LINK") or "").strip()

# Key used in menu_store for your *personal assistant* menu
# (separate from the Sanctuary model menus)
RONI_MENU_KEY = "RoniPersonalMenu"

# Index key for age-verified users (JSON list of IDs)
AGE_INDEX_KEY = "RoniAgeIndex"

# Keys for editable text blocks
OPEN_ACCESS_KEY = "RoniOpenAccessText"
TEASER_TEXT_KEY = "RoniTeaserChannelsText"


# Helpers for age index
def _load_age_index() -> list[int]:
    raw = store.get_menu(AGE_INDEX_KEY) or "[]"
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [int(x) for x in data]
    except Exception:
        pass
    return []


def _save_age_index(ids: list[int]) -> None:
    try:
        # dict.fromkeys to de-duplicate while preserving order
        store.set_menu(AGE_INDEX_KEY, json.dumps(list(dict.fromkeys(ids))))
    except Exception:
        log.exception("Failed to save age index")


# Base key for age verification flags (per-user)
def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"


# Simple in-memory pending state for admin edits + age verify
_pending_admin: dict[int, str] = {}
_pending_age: dict[int, bool] = {}  # user_id -> waiting_for_media


# ────────────── AGE VERIFY HELPERS ──────────────

def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        return bool(store.get_menu(_age_key(user_id)))
    except Exception:
        return False


def set_age_verified(user_id: int, username: str | None = None) -> None:
    """
    Store a JSON record for this user:
    {
      "status": "ok",
      "user_id": 123,
      "username": "@name" or "Name",
      "verified_at": "YYYY-MM-DD HH:MM UTC",
      "note": "optional note"
    }
    Also keeps an index of all verified IDs in AGE_INDEX_KEY.
    """
    try:
        # Preserve existing note if present
        existing_raw = store.get_menu(_age_key(user_id)) or ""
        note = ""
        if existing_raw:
            try:
                existing = json.loads(existing_raw)
                if isinstance(existing, dict):
                    note = existing.get("note", "") or ""
            except Exception:
                pass

        verified_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        record = {
            "status": "ok",
            "user_id": user_id,
            "username": username or "",
            "verified_at": verified_at,
            "note": note,
        }
        store.set_menu(_age_key(user_id), json.dumps(record))

        # Update index
        ids = _load_age_index()
        if user_id not in ids:
            ids.append(user_id)
            _save_age_index(ids)

    except Exception:
        log.exception("Failed to persist age verify state for %s", user_id)


def _load_age_record(user_id: int) -> dict:
    raw = store.get_menu(_age_key(user_id)) or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_age_record(user_id: int, record: dict) -> None:
    try:
        store.set_menu(_age_key(user_id), json.dumps(record))
    except Exception:
        log.exception("Failed to save age record for %s", user_id)


# ────────────── KEYBOARDS ──────────────

def _roni_main_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    """
    Build Roni's assistant keyboard.
    If user_id == RONI_OWNER_ID, show the admin button too.
    If user is age-verified, show Teaser button instead of Age Verify.
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

    # 🌸 Open Access – SFW/preview stuff, editable via admin
    rows.append([InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:open_access")])

    # Age gate vs teaser:
    if user_id and is_age_verified(user_id):
        # Already verified – show teaser/promo access
        rows.append(
            [InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:teaser")]
        )
    else:
        # Not verified yet – show Age Verify
        rows.append(
            [InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:age")]
        )

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
            [InlineKeyboardButton("🌸 Edit Open Access", callback_data="roni_admin:edit_open")],
            [InlineKeyboardButton("🔥 Edit Teaser/Promo Text", callback_data="roni_admin:edit_teaser")],
            [InlineKeyboardButton("✅ Age-Verified List", callback_data="roni_admin:age_list")],
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

    # ───────── Roni’s Menu (reads from *RoniPersonalMenu* key) ─────────
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

    # ───────── OPEN ACCESS: show SFW/preview text ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:open_access$"))
    async def roni_open_access_cb(_, cq: CallbackQuery):
        text = store.get_menu(OPEN_ACCESS_KEY) or (
            "🌸 <b>Open Access</b>\n\n"
            "Roni will add some safe-to-view goodies and general info here soon. 💕"
        )

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                [InlineKeyboardButton("🏠 Back to SuccuBot Menu", callback_data="panels:root")],
            ]
        )

        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── TEASER & PROMO CHANNELS (gated) ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:teaser$"))
    async def roni_teaser_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not user_id or not is_age_verified(user_id):
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
                [InlineKeyboardButton("🏠 Back to SuccuBot Menu", callback_data="panels:root")],
            ]
        )

        await cq.message.edit_text(teaser_text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── AGE VERIFY: start flow ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def roni_age_start_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not user_id:
            await cq.answer()
            return

        if is_age_verified(user_id):
            await cq.answer("You’re already age verified, naughty one. 💕", show_alert=True)
            return

        # Mark that we’re waiting for a selfie from this user
        _pending_age[user_id] = True

        text = (
            "Hi cutie, I just need to confirm you’re 18+ so Roni can keep things safe and adults-only. 💕\n\n"
            "Please send one clear photo or short video in this chat:\n"
            "• Touching your nose with a fork, or\n"
            "• Touching your nose with your pinky finger\n\n"
            "If you look extra fresh-faced, Roni might ask for a second photo with your ID "
            "showing your face and birth date.\n\n"
            "No minors. Sending underage content will get you blocked and removed. 💜"
        )

        await cq.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── AGE VERIFY: capture selfie (photo/video) ─────────
    # group=-2 so it runs early but after admin text-capture is checked
    @app.on_message(filters.private & (filters.photo | filters.video), group=-2)
    async def roni_age_capture(_, m: Message):
        if not m.from_user:
            return
        user_id = m.from_user.id

        if not _pending_age.get(user_id):
            return  # not in age-verify mode

        # Stop other handlers from touching this media
        try:
            m.stop_propagation()
        except Exception:
            pass

        _pending_age.pop(user_id, None)

        username = m.from_user.username
        mention = f"@{username}" if username else m.from_user.first_name or "Someone"

        # 1️⃣ Forward media to Roni
        try:
            await m.forward(RONI_OWNER_ID)
        except Exception:
            log.exception("Failed to forward age verify media for %s", user_id)

        # 2️⃣ Send identification message + buttons to Roni
        id_text = (
            "📩 <b>Age Verification Received</b>\n\n"
            f"From: {mention}\n"
            f"User ID: <code>{user_id}</code>\n\n"
            "Their media is forwarded above. Review it and choose an action:"
        )

        controls = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"age:approve:{user_id}"),
                ],
                [
                    InlineKeyboardButton("🪪 Need more info", callback_data=f"age:more:{user_id}"),
                ],
                [
                    InlineKeyboardButton("⛔ Deny", callback_data=f"age:deny:{user_id}"),
                ],
            ]
        )

        await _.send_message(
            RONI_OWNER_ID,
            id_text,
            reply_markup=controls,
            disable_web_page_preview=True,
        )

        # 3️⃣ Confirm to the user
        await m.reply_text(
            "Thanks! I’ve sent this to Roni for review. 💕\n"
            "You’ll get a message as soon as she approves you or asks for more info.",
            disable_web_page_preview=True,
        )

    # ───────── AGE VERIFY: owner actions (approve / more info / deny) ─────────
    @app.on_callback_query(filters.regex(r"^age:(approve|more|deny):(\d+)$"))
    async def roni_age_action_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can do that 💜", show_alert=True)
            return

        action, user_id_str = cq.data.split(":", 2)[1:]
        target_id = int(user_id_str)

        if action == "approve":
            # Fetch username snapshot for record
            username = ""
            try:
                user = await _.get_users(target_id)
                if user.username:
                    username = f"@{user.username}"
                else:
                    username = user.first_name or ""
            except Exception:
                log.exception("Failed to fetch user for age approve")
            set_age_verified(target_id, username=username)

            # Tell the user + refresh their assistant keyboard
            kb_user = _roni_main_keyboard(target_id)
            await _.send_message(
                target_id,
                "You’re all set — Roni has verified you as 18+ ✅\n\n"
                "You now have access to her teaser & promo options. 💕",
                reply_markup=kb_user,
                disable_web_page_preview=True,
            )

            await cq.answer("Marked as age verified ✅", show_alert=True)

        elif action == "more":
            # Ask user for ID / extra info
            await _.send_message(
                target_id,
                "Hey, Roni just needs a little more info to finish verifying you. 💕\n\n"
                "Please send one more photo in this chat:\n"
                "• Your face + your photo ID visible\n"
                "• Only your face and birth date need to be readable — you can cover other details.\n\n"
                "No minors. If your ID shows under 18, you’ll be removed.",
                disable_web_page_preview=True,
            )

            _pending_age[target_id] = True  # wait for another media message
            await cq.answer("Asked them for more info 🪪", show_alert=True)

        elif action == "deny":
            # Not verified – let user know
            await _.send_message(
                target_id,
                "Roni wasn’t able to verify you as 18+, so she can’t give access to her explicit content. 💜\n\n"
                "If you believe this is a mistake, you can reach out politely and ask what’s needed to verify.",
                disable_web_page_preview=True,
            )

            await cq.answer("Marked as not verified ⛔", show_alert=True)

    # ───────── ADMIN: open admin panel (button-only) ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:open$"))
    async def roni_admin_open_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can use this 💜", show_alert=True)
            return

        current = store.get_menu(RONI_MENU_KEY) or "No menu set yet."

        await cq.message.edit_text(
            "💜 <b>Roni Admin Panel</b>\n\n"
            "This controls what shows under “📖 Roni’s Menu” in your assistant, "
            "your Open Access text, teaser/promo text, and lets you review age verification.\n\n"
            f"<b>Current menu preview:</b>\n\n{current}",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── ADMIN: view age-verified list ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:age_list$"))
    async def roni_admin_age_list_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return

        ids = _load_age_index()
        if not ids:
            text = (
                "💜 <b>Age-Verified Users</b>\n\n"
                "No one has been marked as age verified yet."
            )
            kb = _admin_keyboard()
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            await cq.answer()
            return

        lines = ["💜 <b>Age-Verified Users</b>\n"]
        note_buttons: list[list[InlineKeyboardButton]] = []

        # Limit how many we list in one message to avoid flooding
        max_list = 25
        for i, uid in enumerate(ids[:max_list]):
            rec = _load_age_record(uid)
            uname = rec.get("username") or f"ID {uid}"
            verified_at = rec.get("verified_at", "unknown time")
            note = rec.get("note", "")
            line = f"• {uname} (ID: <code>{uid}</code>) — verified {verified_at}"
            if note:
                line += f"\n  Note: {note}"
            lines.append(line)
            note_buttons.append(
                [InlineKeyboardButton(f"📝 Note for {uid}", callback_data=f"roni_admin:note:{uid}")]
            )

        if len(ids) > max_list:
            lines.append(f"\n…and {len(ids) - max_list} more.")

        text = "\n".join(lines)

        # Add back button row at the bottom
        note_buttons.append(
            [InlineKeyboardButton("⬅ Back to Admin", callback_data="roni_admin:open")]
        )

        kb = InlineKeyboardMarkup(note_buttons)

        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # ───────── ADMIN: start note edit for specific user ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:note:(\d+)$"))
    async def roni_admin_note_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return

        parts = cq.data.split(":")
        target_id = int(parts[-1])

        _pending_admin[cq.from_user.id] = f"note:{target_id}"

        rec = _load_age_record(target_id)
        existing_note = rec.get("note", "") or "None set."

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")],
            ]
        )

        await cq.message.edit_text(
            f"📝 Editing note for user ID <code>{target_id}</code>.\n\n"
            f"Current note:\n{existing_note}\n\n"
            "Send a new note in one message. It will replace the existing note.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── ADMIN: start editing menu ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:edit_menu$"))
    async def roni_admin_edit_menu_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can edit this 💜", show_alert=True)
            return

        _pending_admin[cq.from_user.id] = "menu"

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

    # ───────── ADMIN: start editing Open Access ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:edit_open$"))
    async def roni_admin_edit_open_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can edit this 💜", show_alert=True)
            return

        _pending_admin[cq.from_user.id] = "open_access"

        current = store.get_menu(OPEN_ACCESS_KEY) or "No Open Access text set yet."

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")],
            ]
        )

        await cq.message.edit_text(
            "🌸 <b>Edit Open Access</b>\n\n"
            "This is what people see when they tap “🌸 Open Access”.\n\n"
            f"<b>Current text:</b>\n\n{current}\n\n"
            "Send me the new text in one message, and I’ll replace it.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── ADMIN: start editing Teaser/Promo text ─────────
    @app.on_callback_query(filters.regex(r"^roni_admin:edit_teaser$"))
    async def roni_admin_edit_teaser_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can edit this 💜", show_alert=True)
            return

        _pending_admin[cq.from_user.id] = "teaser"

        current = store.get_menu(TEASER_TEXT_KEY) or (
            os.getenv("RONI_TEASER_CHANNELS_TEXT") or "No teaser/promo text set yet."
        )

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")],
            ]
        )

        await cq.message.edit_text(
            "🔥 <b>Edit Teaser & Promo Text</b>\n\n"
            "This is what verified users see when they tap “🔥 Teaser & Promo Channels”.\n\n"
            f"<b>Current text:</b>\n\n{current}\n\n"
            "Send me the new text in one message, and I’ll replace it.",
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

        _pending_admin.pop(cq.from_user.id, None)

        user_id = cq.from_user.id
        kb = _roni_main_keyboard(user_id)

        await cq.message.edit_text(
            "Cancelled. No changes were made. 💜",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── ADMIN: capture new menu text / open access / teaser / age note ─────────
    # group=-2 so it runs BEFORE other private text handlers that might stop_propagation
    @app.on_message(filters.private & filters.text, group=-2)
    async def roni_admin_capture(_, m: Message):
        if not m.from_user or m.from_user.id != RONI_OWNER_ID:
            return

        action = _pending_admin.get(m.from_user.id)
        if not action:
            return

        # Stop other handlers from touching this message
        try:
            m.stop_propagation()
        except Exception:
            pass

        # Menu edit
        if action == "menu":
            store.set_menu(RONI_MENU_KEY, m.text)
            _pending_admin.pop(m.from_user.id, None)

            current = store.get_menu(RONI_MENU_KEY) or "No menu set yet."

            await m.reply_text(
                "Saved your personal menu. 💕\n\n"
                "You’re back in the Roni Admin panel — here’s your current menu preview:\n\n"
                f"{current}",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return

        # Open Access edit
        if action == "open_access":
            store.set_menu(OPEN_ACCESS_KEY, m.text)
            _pending_admin.pop(m.from_user.id, None)

            await m.reply_text(
                "Saved your 🌸 Open Access text. 💕\n\n"
                "Anyone tapping “🌸 Open Access” will now see this updated block.",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return

        # Teaser/Promo edit
        if action == "teaser":
            store.set_menu(TEASER_TEXT_KEY, m.text)
            _pending_admin.pop(m.from_user.id, None)

            await m.reply_text(
                "Saved your 🔥 Teaser & Promo text. 💕\n\n"
                "Age-verified users tapping “🔥 Teaser & Promo Channels” will now see this updated block.",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return

        # Note edit: action format "note:<user_id>"
        if action.startswith("note:"):
            try:
                _, user_id_str = action.split(":", 1)
                target_id = int(user_id_str)
            except Exception:
                _pending_admin.pop(m.from_user.id, None)
                await m.reply_text(
                    "Something went wrong while editing the note. 💜",
                    disable_web_page_preview=True,
                )
                return

            rec = _load_age_record(target_id)
            if not rec:
                # Make a basic record if it didn't exist
                rec = {
                    "status": "ok",
                    "user_id": target_id,
                    "username": "",
                    "verified_at": "unknown",
                    "note": "",
                }

            rec["note"] = m.text
            _save_age_record(target_id, rec)

            # Ensure ID is in index
            ids = _load_age_index()
            if target_id not in ids:
                ids.append(target_id)
                _save_age_index(ids)

            _pending_admin.pop(m.from_user.id, None)

            await m.reply_text(
                f"Saved note for user ID {target_id}. 💕",
                reply_markup=_admin_keyboard(),
                disable_web_page_preview=True,
            )
            return
