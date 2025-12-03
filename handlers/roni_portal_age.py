# handlers/roni_portal_age.py
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

from utils.menu_store import store

log = logging.getLogger(__name__)

# ────────────── CONSTANTS (MUST MATCH roni_portal.py) ──────────────

BOT_USERNAME = (os.getenv("BOT_USERNAME") or "YourBotUsernameHere").lstrip("@")
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "chaossub283").lstrip("@")
RONI_OWNER_ID = 6964994611

RONI_MENU_KEY = "RoniPersonalMenu"
OPEN_ACCESS_KEY = "RoniOpenAccessText"
TEASER_TEXT_KEY = "RoniTeaserChannelsText"
SANCTUARY_TEXT_KEY = "RoniSanctuaryText"

AGE_INDEX_KEY = "RoniAgeIndex"
AGE_MEDIA_PREFIX = "RoniAgeMedia:"

# in-memory state *only* for age flow
_pending_age: dict[int, bool] = {}


# ────────────── SHARED AGE STORAGE HELPERS ──────────────

def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"


def _media_key(user_id: int) -> str:
    return f"{AGE_MEDIA_PREFIX}{user_id}"


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
        store.set_menu(AGE_INDEX_KEY, json.dumps(list(dict.fromkeys(ids))))
    except Exception:
        log.exception("Failed to save age index")


def _ensure_in_index(user_id: int) -> None:
    ids = _load_age_index()
    if user_id not in ids:
        ids.append(user_id)
        _save_age_index(ids)


def _load_age_media(user_id: int) -> list[dict]:
    raw = store.get_menu(_media_key(user_id)) or "[]"
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_age_media(user_id: int, items: list[dict]) -> None:
    try:
        store.set_menu(_media_key(user_id), json.dumps(items))
    except Exception:
        log.exception("Failed to save age media for %s", user_id)


def _append_age_media(user_id: int, item: dict) -> None:
    items = _load_age_media(user_id)
    items.append(item)
    _save_age_media(user_id, items)


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
        _ensure_in_index(user_id)
    except Exception:
        log.exception("Failed to save age record for %s", user_id)


def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        return bool(store.get_menu(_age_key(user_id)))
    except Exception:
        return False


def set_age_verified(user_id: int, username: str | None = None) -> None:
    try:
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
        _ensure_in_index(user_id)
    except Exception:
        log.exception("Failed to persist age verify state for %s", user_id)


# ────────────── LOCAL KEYBOARDS (MATCH core) ──────────────

def _roni_main_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    rows.append([InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")])
    rows.append([InlineKeyboardButton("💌 Book Roni", url=f"https://t.me/{RONI_USERNAME}")])

    # We don’t handle tip link here; just show neutral button
    rows.append(
        [InlineKeyboardButton("💸 Pay / Tip Roni (coming soon)", callback_data="roni_portal:tip_coming")]
    )

    rows.append([InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:open_access")])
    rows.append([InlineKeyboardButton("😈 Succubus Sanctuary", callback_data="roni_portal:sanctuary")])

    if user_id == RONI_OWNER_ID:
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

    return InlineKeyboardMarkup(rows)


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 Edit Roni Menu", callback_data="roni_admin:edit_menu")],
            [InlineKeyboardButton("🌸 Edit Open Access", callback_data="roni_admin:edit_open")],
            [InlineKeyboardButton("🔥 Edit Teaser/Promo Text", callback_data="roni_admin:edit_teaser")],
            [InlineKeyboardButton("😈 Edit Succubus Sanctuary", callback_data="roni_admin:edit_sanctuary")],
            [InlineKeyboardButton("✅ Age-Verified List", callback_data="roni_admin:age_list")],
            [InlineKeyboardButton("⬅ Back to Assistant", callback_data="roni_portal:home")],
        ]
    )


def _age_verified_status_text(mention: str, uid: int) -> str:
    rec = _load_age_record(uid)
    approved_at = rec.get("verified_at", "unknown time")
    note = rec.get("note")
    base = (
        "✅ <b>Age-Verified User</b>\n\n"
        f"User: {mention}\n"
        f"ID: <code>{uid}</code>\n"
        f"Approved at: {approved_at}"
    )
    if note:
        base += f"\n\n<b>Note:</b>\n{note}"
    return base


def _age_verified_status_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📝 Add / Edit Note", callback_data=f"roni_admin:note:{uid}")],
            [InlineKeyboardButton("♻️ Remove AV Status", callback_data=f"roni_admin:age_remove:{uid}")],
            [InlineKeyboardButton("⬅ Back to Age-Verified List", callback_data="roni_admin:age_list")],
        ]
    )


# ────────────── REGISTER (AGE HANDLERS) ──────────────

def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal_age registered")

    # ───────── Start AV flow from button ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def roni_age_start_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else None
        if not user_id:
            await cq.answer()
            return

        if is_age_verified(user_id):
            await cq.answer("You’re already age verified, naughty one. 💕", show_alert=True)
            return

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

    # ───────── Capture age selfie/video ─────────
    @app.on_message(filters.private & (filters.photo | filters.video), group=-2)
    async def roni_age_capture(_, m: Message):
        if not m.from_user:
            return
        user_id = m.from_user.id

        if not _pending_age.get(user_id):
            return

        try:
            m.stop_propagation()
        except Exception:
            pass

        _pending_age.pop(user_id, None)

        username = m.from_user.username
        mention = f"@{username}" if username else m.from_user.first_name or "Someone"

        media_type = "photo" if m.photo else "video"
        file_id = ""
        if m.photo:
            file_id = m.photo.file_id
        elif m.video:
            file_id = m.video.file_id

        if file_id:
            _append_age_media(
                user_id,
                {
                    "type": media_type,
                    "file_id": file_id,
                    "saved_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                },
            )

        try:
            await m.copy(
                chat_id=RONI_OWNER_ID,
                caption=(
                    "📩 <b>Age Verification Media</b>\n\n"
                    f"From: {mention}\n"
                    f"User ID: <code>{user_id}</code>"
                ),
            )
        except Exception:
            log.exception("Failed to copy age verify media for %s", user_id)

        id_text = (
            "📩 <b>Age Verification Received</b>\n\n"
            f"From: {mention}\n"
            f"User ID: <code>{user_id}</code>\n\n"
            "Their media is above. Review it and choose an action:"
        )

        controls = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Approve", callback_data=f"age:approve:{user_id}")],
                [InlineKeyboardButton("🪪 Need more info", callback_data=f"age:more:{user_id}")],
                [InlineKeyboardButton("⛔ Deny", callback_data=f"age:deny:{user_id}")],
            ]
        )

        await _.send_message(
            RONI_OWNER_ID,
            id_text,
            reply_markup=controls,
            disable_web_page_preview=True,
        )

        await m.reply_text(
            "Thanks! I’ve sent this to Roni for review. 💕\n"
            "You’ll get a message as soon as she approves you or asks for more info.",
            disable_web_page_preview=True,
        )

    # ───────── Age actions (approve / more / deny) ─────────
    @app.on_callback_query(filters.regex(r"^age:(approve|more|deny):(\d+)$"))
    async def roni_age_action_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can do that 💜", show_alert=True)
            return

        action, user_id_str = cq.data.split(":", 2)[1:]
        target_id = int(user_id_str)

        username = ""
        mention = f"ID {target_id}"
        try:
            user = await _.get_users(target_id)
            if user.username:
                username = f"@{user.username}"
            else:
                username = user.first_name or ""
            if username:
                mention = username
        except Exception:
            log.exception("Failed to fetch user for age action")

        # Close the old card
        try:
            await cq.message.delete()
        except Exception:
            try:
                await cq.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        if action == "approve":
            set_age_verified(target_id, username=username)

            kb_user = _roni_main_keyboard(target_id)
            await _.send_message(
                target_id,
                "You’re all set — Roni has verified you as 18+ ✅\n\n"
                "You now have access to her teaser & promo options. 💕",
                reply_markup=kb_user,
                disable_web_page_preview=True,
            )

            status_text = _age_verified_status_text(mention, target_id)
            await _.send_message(
                RONI_OWNER_ID,
                status_text,
                reply_markup=_age_verified_status_keyboard(target_id),
                disable_web_page_preview=True,
            )

            await cq.answer("Marked as age verified ✅", show_alert=True)

        elif action == "more":
            await _.send_message(
                target_id,
                "Hey, Roni just needs a little more info to finish verifying you. 💕\n\n"
                "Please send one more photo in this chat:\n"
                "• Your face + your photo ID visible\n"
                "• Only your face and birth date need to be readable — you can cover other details.\n\n"
                "No minors. If your ID shows under 18, you’ll be removed.",
                disable_web_page_preview=True,
            )

            _pending_age[target_id] = True

            await _.send_message(
                RONI_OWNER_ID,
                "📩 <b>Age Verification Processed</b>\n\n"
                f"Action: 🪪 <b>Requested More Info</b>\n"
                f"User: {mention}\n"
                f"User ID: <code>{target_id}</code>",
                disable_web_page_preview=True,
            )

            await cq.answer("Asked them for more info 🪪", show_alert=True)

        elif action == "deny":
            await _.send_message(
                target_id,
                "Roni wasn’t able to verify you as 18+, so she can’t give access to her explicit content. 💜\n\n"
                "If you believe this is a mistake, you can reach out politely and ask what’s needed to verify.",
                disable_web_page_preview=True,
            )

            await _.send_message(
                RONI_OWNER_ID,
                "📩 <b>Age Verification Processed</b>\n\n"
                f"Action: ⛔ <b>Denied</b>\n"
                f"User: {mention}\n"
                f"User ID: <code>{target_id}</code>",
                disable_web_page_preview=True,
            )

            await cq.answer("Marked as not verified ⛔", show_alert=True)

    # optional close helper
    @app.on_callback_query(filters.regex(r"^age:close$"))
    async def roni_age_close_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni can do that 💜", show_alert=True)
            return
        try:
            await cq.message.delete()
        except Exception:
            try:
                await cq.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
        await cq.answer("Closed ✔")

    # ───────── Admin: Age-verified list & notes ─────────
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

        for uid in ids:
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

        text = "\n".join(lines)
        note_buttons.append(
            [InlineKeyboardButton("⬅ Back to Admin", callback_data="roni_admin:open")]
        )
        kb = InlineKeyboardMarkup(note_buttons)

        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_admin:note:(\d+)$"))
    async def roni_admin_note_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return

        parts = cq.data.split(":")
        target_id = int(parts[-1])

        store.set_menu(f"_RONI_PENDING_NOTE:{cq.from_user.id}", str(target_id))

        rec = _load_age_record(target_id)
        existing_note = rec.get("note", "") or "None set."

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="roni_admin:cancel")]]
        )

        await cq.message.edit_text(
            f"📝 Editing note for user ID <code>{target_id}</code>.\n\n"
            f"Current note:\n{existing_note}\n\n"
            "Send a new note in one message. It will replace the existing note.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_admin:age_remove:(\d+)$"))
    async def roni_admin_age_remove_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return

        parts = cq.data.split(":")
        target_id = int(parts[-1])

        store.set_menu(_age_key(target_id), "")

        ids = _load_age_index()
        ids = [i for i in ids if i != target_id]
        _save_age_index(ids)

        try:
            await _.send_message(
                target_id,
                "Roni has removed your age-verified status, so you no longer have access to her explicit content. 💜\n\n"
                "If you believe this is a mistake, you can reach out politely to ask about re-verifying.",
                disable_web_page_preview=True,
            )
        except Exception:
            log.exception("Failed to notify user about AV removal for %s", target_id)

        try:
            await cq.message.edit_text(
                "❌ <b>Age Verification Status Removed</b>\n\n"
                f"User ID: <code>{target_id}</code>\n\n"
                "They have been removed from the age-verified list.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⬅ Back to Age-Verified List",
                                callback_data="roni_admin:age_list",
                            )
                        ]
                    ]
                ),
                disable_web_page_preview=True,
            )
        except Exception:
            log.exception("Failed to edit message after AV removal for %s", target_id)

        await cq.answer("Removed age-verified status ❌", show_alert=True)

    # ───────── Capture note edits ─────────
    @app.on_message(filters.private & filters.text, group=-2)
    async def roni_note_capture(_, m: Message):
        if not m.from_user or m.from_user.id != RONI_OWNER_ID:
            return

        pending_key = f"_RONI_PENDING_NOTE:{m.from_user.id}"
        target_str = store.get_menu(pending_key) or ""
        if not target_str:
            return

        try:
            target_id = int(target_str)
        except ValueError:
            store.set_menu(pending_key, "")
            await m.reply_text(
                "Something went wrong while editing the note. 💜",
                disable_web_page_preview=True,
            )
            return

        rec = _load_age_record(target_id)
        if not rec:
            rec = {
                "status": "ok",
                "user_id": target_id,
                "username": "",
                "verified_at": "unknown",
                "note": "",
            }

        rec["note"] = m.text
        _save_age_record(target_id, rec)

        store.set_menu(pending_key, "")

        await m.reply_text(
            f"Saved note for user ID {target_id}. 💕",
            reply_markup=_admin_keyboard(),
            disable_web_page_preview=True,
        )

    # ───────── /age_check helper ─────────
    @app.on_message(filters.command("age_check"))
    async def roni_age_check_cmd(_, m: Message):
        if not m.from_user or m.from_user.id != RONI_OWNER_ID:
            return

        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            await m.reply_text(
                "Usage: <code>/age_check &lt;user_id&gt;</code>\n\n"
                "I’ll tell you if they’re age-verified, in the index, and how many verify photos are logged.",
                disable_web_page_preview=True,
            )
            return

        try:
            target_id = int(parts[1])
        except ValueError:
            await m.reply_text("User ID must be a number. 💜", disable_web_page_preview=True)
            return

        rec = _load_age_record(target_id)
        ids = _load_age_index()
        in_index = target_id in ids
        media_list = _load_age_media(target_id)

        if not rec:
            await m.reply_text(
                "No age verification record found for this user.\n\n"
                f"ID: <code>{target_id}</code>\n"
                f"In index: {'✅ yes' if in_index else '❌ no'}\n"
                f"Logged media items: {len(media_list)}",
                disable_web_page_preview=True,
            )
            return

        uname = rec.get("username") or f"ID {target_id}"
        verified_at = rec.get("verified_at", "unknown time")
        note = rec.get("note") or "None"

        text = (
            "🔍 <b>Age Check</b>\n\n"
            f"User: {uname}\n"
            f"ID: <code>{target_id}</code>\n"
            f"Verified at: {verified_at}\n"
            f"In index: {'✅ yes' if in_index else '❌ no'}\n"
            f"Logged media items: {len(media_list)}\n\n"
            f"<b>Note:</b>\n{note}"
        )

        kb = None
        if not in_index:
            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Fix index entry",
                            callback_data=f"roni_admin:fix_index:{target_id}",
                        )
                    ]
                ]
            )

        await m.reply_text(text, reply_markup=kb, disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^roni_admin:fix_index:(\d+)$"))
    async def roni_admin_fix_index_cb(_, cq: CallbackQuery):
        if cq.from_user.id != RONI_OWNER_ID:
            await cq.answer()
            return

        try:
            target_id = int(cq.data.split(":")[-1])
        except Exception:
            await cq.answer("Something went wrong parsing the ID 💜", show_alert=True)
            return

        rec = _load_age_record(target_id)
        if not rec:
            await cq.answer(
                "There’s no age-verify record stored for this user, so I can’t fix the index. 💜",
                show_alert=True,
            )
            return

        _ensure_in_index(target_id)
        await cq.answer("Index fixed for this user ✅", show_alert=True)

    # ───────── /age_media helper ─────────
    @app.on_message(filters.command("age_media"))
    async def roni_age_media_cmd(_, m: Message):
        if not m.from_user or m.from_user.id != RONI_OWNER_ID:
            return

        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            await m.reply_text(
                "Usage: <code>/age_media &lt;user_id&gt;</code>\n\n"
                "I’ll resend any stored age verification media for that user.",
                disable_web_page_preview=True,
            )
            return

        try:
            target_id = int(parts[1])
        except ValueError:
            await m.reply_text("User ID must be a number. 💜", disable_web_page_preview=True)
            return

        media_list = _load_age_media(target_id)
        if not media_list:
            await m.reply_text(
                f"No stored age verification media found for user ID <code>{target_id}</code>.",
                disable_web_page_preview=True,
            )
            return

        rec = _load_age_record(target_id)
        uname = rec.get("username") or f"ID {target_id}"

        for item in media_list:
            file_id = item.get("file_id")
            mtype = item.get("type", "photo")
            saved_at = item.get("saved_at", "unknown time")

            caption = (
                "📂 <b>Logged Age Verification Media</b>\n\n"
                f"User: {uname}\n"
                f"User ID: <code>{target_id}</code>\n"
                f"Logged at: {saved_at}"
            )

            try:
                if mtype == "video":
                    await _.send_video(
                        m.chat.id,
                        file_id,
                        caption=caption,
                        disable_web_page_preview=True,
                    )
                else:
                    await _.send_photo(
                        m.chat.id,
                        file_id,
                        caption=caption,
                        disable_web_page_preview=True,
                    )
            except Exception:
                log.exception("Failed to resend age media for %s", target_id)
