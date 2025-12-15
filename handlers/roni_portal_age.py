# handlers/roni_portal_age.py
import json
import logging
from datetime import datetime, timezone

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from utils.menu_store import store

log = logging.getLogger(__name__)

# Roni (owner/admin) Telegram user id
RONI_OWNER_ID = 6964994611

# Storage keys (MenuStore)
PENDING_KEY_PREFIX = "AGE_REQ:"          # AGE_REQ:<user_id> -> JSON payload
PENDING_INDEX_KEY = "RoniAgePendingIndex" # JSON list[int] of user_ids pending review
AGE_OK_PREFIX = "AGE_OK:"                # AGE_OK:<user_id> -> "1" or JSON
AGE_INDEX_KEY = "RoniAgeIndex"           # JSON list[int] verified (legacy-compatible)

# Simple convo state for private chat (MenuStore)
STEP_PREFIX = "_AGE_STEP:"               # _AGE_STEP:<user_id> -> "await_photo"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default


def _jget(key: str, default):
    raw = store.get_menu(key)
    if not raw:
        return default
    return _jloads(raw, default)


def _jset(key: str, obj) -> None:
    store.set_menu(key, json.dumps(obj, ensure_ascii=False))


def _step_key(user_id: int) -> str:
    return f"{STEP_PREFIX}{user_id}"


def _pending_key(user_id: int) -> str:
    return f"{PENDING_KEY_PREFIX}{user_id}"


def _age_ok_key(user_id: int) -> str:
    return f"{AGE_OK_PREFIX}{user_id}"


def _get_pending_index() -> list[int]:
    lst = _jget(PENDING_INDEX_KEY, [])
    if not isinstance(lst, list):
        return []
    out = []
    for x in lst:
        try:
            out.append(int(x))
        except Exception:
            pass
    # dedupe preserve order
    seen = set()
    dedup = []
    for uid in out:
        if uid in seen:
            continue
        seen.add(uid)
        dedup.append(uid)
    return dedup


def _set_pending_index(uids: list[int]) -> None:
    # dedupe preserve order
    seen = set()
    out = []
    for uid in uids:
        if uid in seen:
            continue
        seen.add(uid)
        out.append(int(uid))
    _jset(PENDING_INDEX_KEY, out)


def _add_pending(uid: int) -> None:
    idx = _get_pending_index()
    if uid not in idx:
        idx.append(uid)
        _set_pending_index(idx)


def _remove_pending(uid: int) -> None:
    idx = [x for x in _get_pending_index() if x != uid]
    _set_pending_index(idx)


def _get_verified_index() -> list[int]:
    raw = store.get_menu(AGE_INDEX_KEY) or "[]"
    ids = _jloads(raw, [])
    if not isinstance(ids, list):
        return []
    out = []
    for x in ids:
        try:
            out.append(int(x))
        except Exception:
            pass
    # dedupe
    seen = set()
    dedup = []
    for uid in out:
        if uid in seen:
            continue
        seen.add(uid)
        dedup.append(uid)
    return dedup


def _set_verified_index(uids: list[int]) -> None:
    seen = set()
    out = []
    for uid in uids:
        if uid in seen:
            continue
        seen.add(uid)
        out.append(int(uid))
    store.set_menu(AGE_INDEX_KEY, json.dumps(out))


def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True
    try:
        return bool(store.get_menu(_age_ok_key(user_id)))
    except Exception:
        return False


def _user_intro_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📸 Submit verification photo", callback_data="roni_age:begin")],
            [InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")],
        ]
    )


def _await_photo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("❌ Cancel", callback_data="roni_age:cancel")],
            [InlineKeyboardButton("⬅ Back", callback_data="roni_age:back")],
        ]
    )


def _pending_user_text() -> str:
    return (
        "✅ <b>Age Verification</b>\n\n"
        "To unlock NSFW booking + teaser/promo links, please send a clear photo of:\n\n"
        "• <b>Your face</b>\n"
        "• <b>You touching your nose with your pinky</b>\n\n"
        "No text-only confirmations — I need the photo.\n\n"
        "After you send it, Roni will review and approve/deny or ask for more info."
    )


def _already_pending_text() -> str:
    return (
        "⏳ <b>Age Verification Pending</b>\n\n"
        "I already have your verification photo submitted.\n"
        "Please wait for Roni to review it. 💜"
    )


def _approved_text() -> str:
    return (
        "✅ <b>Verified</b> 💕\n\n"
        "You’re approved. Teaser/promo links and NSFW booking are now unlocked.\n\n"
        "🚫 <b>NO meetups</b> — online/texting only."
    )


def _denied_text() -> str:
    return (
        "❌ <b>Verification denied</b>\n\n"
        "Your verification photo didn’t meet the requirements.\n"
        "If you want to try again, tap Age Verify and resubmit with a clearer photo "
        "touching your nose with your pinky."
    )


def _moreinfo_text() -> str:
    return (
        "🔁 <b>More info needed</b>\n\n"
        "Roni needs a clearer verification photo.\n"
        "Please send a new photo with:\n"
        "• Your face clearly visible\n"
        "• You touching your nose with your pinky\n\n"
        "Tap below when you're ready."
    )


def _admin_review_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"age_admin:approve:{uid}"),
                InlineKeyboardButton("❌ Deny", callback_data=f"age_admin:deny:{uid}"),
            ],
            [InlineKeyboardButton("🔁 Ask for more info", callback_data=f"age_admin:moreinfo:{uid}")],
            [InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")],
        ]
    )


def _admin_next_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")],
            [InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")],
        ]
    )


async def _notify_admin(app: Client, payload: dict) -> None:
    uid = int(payload["user_id"])
    username = payload.get("username") or ""
    name = payload.get("name") or ""
    caption = (
        "🧾 <b>Age Verification Request</b>\n\n"
        f"User: {name} {f'(@{username})' if username else ''}\n"
        f"ID: <code>{uid}</code>\n"
        f"Submitted: <code>{payload.get('submitted_at','')}</code>"
    )

    photo_file_id = payload.get("photo_file_id")
    try:
        if photo_file_id:
            await app.send_photo(
                chat_id=RONI_OWNER_ID,
                photo=photo_file_id,
                caption=caption,
                reply_markup=_admin_review_kb(uid),
            )
        else:
            await app.send_message(
                chat_id=RONI_OWNER_ID,
                text=caption + "\n\n⚠️ (No photo_file_id stored)",
                reply_markup=_admin_review_kb(uid),
            )
    except Exception as e:
        log.exception("Failed to notify admin about age request: %s", e)


def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal_age (photo flow) registered")

    # Entry point from Roni assistant main menu
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def age_entry(_, cq: CallbackQuery):
        if cq.message and cq.message.chat and cq.message.chat.type != ChatType.PRIVATE:
            await cq.answer("Open this in DM 💕", show_alert=True)
            return

        uid = cq.from_user.id if cq.from_user else None
        if not uid:
            await cq.answer()
            return

        # If already verified, tell them
        if is_age_verified(uid):
            await cq.message.edit_text(_approved_text(), reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:teaser")],
                    [InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:open")],
                    [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                ]
            ), disable_web_page_preview=True)
            await cq.answer()
            return

        # If pending, tell them
        pending = store.get_menu(_pending_key(uid))
        if pending:
            await cq.message.edit_text(_already_pending_text(),
                                       reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]]),
                                       disable_web_page_preview=True)
            await cq.answer()
            return

        await cq.message.edit_text(_pending_user_text(), reply_markup=_user_intro_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Begin submission: set state to await photo
    @app.on_callback_query(filters.regex(r"^roni_age:begin$"))
    async def age_begin(_, cq: CallbackQuery):
        uid = cq.from_user.id
        store.set_menu(_step_key(uid), "await_photo")
        await cq.message.edit_text(
            "📸 <b>Send your verification photo now</b>\n\n"
            "Please send a clear photo of your face while touching your nose with your pinky.\n\n"
            "Once sent, it will be submitted to Roni for review.",
            reply_markup=_await_photo_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_age:cancel$"))
    async def age_cancel(_, cq: CallbackQuery):
        uid = cq.from_user.id
        store.set_menu(_step_key(uid), "")
        await cq.message.edit_text(
            "Cancelled 💜",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_age:back$"))
    async def age_back(_, cq: CallbackQuery):
        uid = cq.from_user.id
        # back to instructions, keep them able to start again
        store.set_menu(_step_key(uid), "")
        await cq.message.edit_text(_pending_user_text(), reply_markup=_user_intro_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Photo receiver in DM
    @app.on_message(filters.private & filters.photo)
    async def age_photo_receive(_, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id

        step = store.get_menu(_step_key(uid)) or ""
        if step != "await_photo":
            return

        # pick highest resolution photo
        photo = m.photo
        if not photo:
            return
        file_id = photo.file_id

        payload = {
            "user_id": uid,
            "username": m.from_user.username or "",
            "name": m.from_user.first_name or "",
            "photo_file_id": file_id,
            "submitted_at": _now_iso(),
            "status": "pending",
        }

        # store + index
        _jset(_pending_key(uid), payload)
        _add_pending(uid)

        # clear state
        store.set_menu(_step_key(uid), "")

        await m.reply_text(
            "✅ Submitted! 💜\n\n"
            "Roni will review your verification photo soon.\n"
            "You’ll get a message when you’re approved/denied or if more info is needed.",
            disable_web_page_preview=True,
        )

        await _notify_admin(app, payload)

    # Admin: view next pending
    @app.on_callback_query(filters.regex(r"^age_admin:next$"))
    async def admin_next(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        idx = _get_pending_index()
        if not idx:
            await cq.answer("No pending requests.", show_alert=True)
            try:
                await cq.message.edit_text(
                    "📭 <b>No pending age-verification requests.</b>",
                    reply_markup=_admin_next_kb(),
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
            return

        uid = idx[0]
        payload = _jget(_pending_key(uid), {})
        if not payload:
            _remove_pending(uid)
            await cq.answer("That request was missing. Skipping.", show_alert=True)
            return

        await cq.answer("Opening next pending…")
        await _notify_admin(app, payload)

    # Admin: approve/deny/moreinfo
    @app.on_callback_query(filters.regex(r"^age_admin:(approve|deny|moreinfo):(\d+)$"))
    async def admin_action(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        action, uid_s = cq.data.split(":")[1], cq.data.split(":")[2]
        uid = int(uid_s)

        payload = _jget(_pending_key(uid), {})
        if not payload:
            await cq.answer("Request not found (maybe already handled).", show_alert=True)
            _remove_pending(uid)
            return

        if action == "approve":
            # mark verified
            store.set_menu(_age_ok_key(uid), "1")

            # legacy verified index
            verified_ids = _get_verified_index()
            if uid not in verified_ids:
                verified_ids.append(uid)
                _set_verified_index(verified_ids)

            # remove pending
            store.set_menu(_pending_key(uid), "")
            _remove_pending(uid)

            # notify user
            try:
                await app.send_message(uid, _approved_text(), disable_web_page_preview=True)
            except Exception:
                pass

            await cq.answer("Approved ✅", show_alert=True)
            try:
                await cq.message.edit_caption(
                    (cq.message.caption or "") + "\n\n✅ <b>APPROVED</b>",
                    reply_markup=_admin_next_kb(),
                )
            except Exception:
                try:
                    await cq.message.edit_text("✅ Approved.", reply_markup=_admin_next_kb())
                except Exception:
                    pass
            return

        if action == "deny":
            store.set_menu(_pending_key(uid), "")
            _remove_pending(uid)

            try:
                await app.send_message(uid, _denied_text(), disable_web_page_preview=True)
            except Exception:
                pass

            await cq.answer("Denied ❌", show_alert=True)
            try:
                await cq.message.edit_caption(
                    (cq.message.caption or "") + "\n\n❌ <b>DENIED</b>",
                    reply_markup=_admin_next_kb(),
                )
            except Exception:
                try:
                    await cq.message.edit_text("❌ Denied.", reply_markup=_admin_next_kb())
                except Exception:
                    pass
            return

        if action == "moreinfo":
            # keep request pending but reset their step so next photo replaces it
            payload["status"] = "moreinfo"
            payload["moreinfo_at"] = _now_iso()
            _jset(_pending_key(uid), payload)

            # tell user to resend; set state
            store.set_menu(_step_key(uid), "await_photo")
            try:
                await app.send_message(
                    uid,
                    _moreinfo_text(),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("📸 Send new verification photo", callback_data="roni_age:begin")],
                            [InlineKeyboardButton("❌ Cancel", callback_data="roni_age:cancel")],
                        ]
                    ),
                    disable_web_page_preview=True,
                )
            except Exception:
                pass

            await cq.answer("Requested more info 🔁", show_alert=True)
            try:
                await cq.message.edit_caption(
                    (cq.message.caption or "") + "\n\n🔁 <b>MORE INFO REQUESTED</b>",
                    reply_markup=_admin_next_kb(),
                )
            except Exception:
                try:
                    await cq.message.edit_text("🔁 More info requested.", reply_markup=_admin_next_kb())
                except Exception:
                    pass
            return

    # Admin: list verified (legacy)
    @app.on_callback_query(filters.regex(r"^roni_admin:age_list$"))
    async def admin_verified_list(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        ids = _get_verified_index()
        if not ids:
            text = "✅ <b>Age-Verified Users</b>\n\n• none yet"
        else:
            lines = ["✅ <b>Age-Verified Users</b>\n"]
            for uid in ids[-80:]:
                lines.append(f"• <code>{uid}</code>")
            text = "\n".join(lines)

        await cq.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]]),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Admin: list pending
    @app.on_callback_query(filters.regex(r"^roni_admin:age_pending$"))
    async def admin_pending_list(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        idx = _get_pending_index()
        if not idx:
            text = "📭 <b>No pending age-verification requests.</b>"
        else:
            lines = ["🧾 <b>Pending Age-Verification Requests</b>\n"]
            for uid in idx[-80:]:
                p = _jget(_pending_key(uid), {})
                uname = p.get("username") or ""
                name = p.get("name") or "User"
                lines.append(f"• {name} {f'(@{uname})' if uname else ''} — <code>{uid}</code>")
            text = "\n".join(lines)

        await cq.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")],
                    [InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()
