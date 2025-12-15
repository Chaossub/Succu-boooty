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

RONI_OWNER_ID = 6964994611

# Storage keys (MenuStore)
PENDING_KEY_PREFIX = "AGE_REQ:"           # AGE_REQ:<user_id> -> JSON payload
PENDING_INDEX_KEY = "RoniAgePendingIndex" # JSON list[int] pending
AGE_OK_PREFIX = "AGE_OK:"                 # AGE_OK:<user_id> -> "1" or JSON
AGE_INDEX_KEY = "RoniAgeIndex"            # JSON list[int] verified (legacy-compatible)

# DM state
STEP_PREFIX = "_AGE_STEP:"                # _AGE_STEP:<user_id> -> "await_photo"

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
    seen, dedup = set(), []
    for uid in out:
        if uid in seen:
            continue
        seen.add(uid)
        dedup.append(uid)
    return dedup

def _set_pending_index(uids: list[int]) -> None:
    seen, out = set(), []
    for uid in uids:
        try:
            uid = int(uid)
        except Exception:
            continue
        if uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
    _jset(PENDING_INDEX_KEY, out)

def _add_pending(uid: int) -> None:
    idx = _get_pending_index()
    if uid not in idx:
        idx.append(uid)
        _set_pending_index(idx)

def _remove_pending(uid: int) -> None:
    _set_pending_index([x for x in _get_pending_index() if x != uid])

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
    seen, dedup = set(), []
    for uid in out:
        if uid in seen:
            continue
        seen.add(uid)
        dedup.append(uid)
    return dedup

def _set_verified_index(uids: list[int]) -> None:
    seen, out = set(), []
    for uid in uids:
        try:
            uid = int(uid)
        except Exception:
            continue
        if uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
    store.set_menu(AGE_INDEX_KEY, json.dumps(out))

def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    # NOTE: Do NOT auto-treat owner as "verified" here.
    # Owner access is handled elsewhere; verification flags should represent reviewed users only.
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
            [
                InlineKeyboardButton("🧹 Reset this user", callback_data=f"age_admin:reset:{uid}"),
                InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next"),
            ],
        ]
    )

def _admin_next_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")],
            [InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")],
        ]
    )

def _admin_reset_all_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚠️ YES, reset ALL verifications", callback_data="age_admin:reset_all_confirm")],
            [InlineKeyboardButton("⬅ Cancel", callback_data="roni_admin:open")],
        ]
    )

def _admin_reset_user_kb(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚠️ YES, reset this user", callback_data=f"age_admin:reset_confirm:{uid}")],
            [InlineKeyboardButton("⬅ Cancel", callback_data="roni_admin:open")],
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

def _remove_verified(uid: int) -> None:
    # Clear AGE_OK flag
    try:
        store.set_menu(_age_ok_key(uid), "")
    except Exception:
        pass
    # Remove from verified index
    ids = [x for x in _get_verified_index() if x != uid]
    _set_verified_index(ids)

def _clear_pending(uid: int) -> None:
    try:
        store.set_menu(_pending_key(uid), "")
    except Exception:
        pass
    _remove_pending(uid)
    try:
        store.set_menu(_step_key(uid), "")
    except Exception:
        pass

def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal_age (photo + admin review) registered")

    # Entry from Roni assistant menu
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def age_entry(_, cq: CallbackQuery):
        if cq.message and cq.message.chat and cq.message.chat.type != ChatType.PRIVATE:
            await cq.answer("Open this in DM 💕", show_alert=True)
            return

        uid = cq.from_user.id if cq.from_user else None
        if not uid:
            await cq.answer()
            return

        # Owner: show admin-ish info screen (NO auto-verify)
        if uid == RONI_OWNER_ID:
            pending = len(_get_pending_index())
            verified = len(_get_verified_index())
            text = (
                "🧾 <b>Age Verification Admin</b>\n\n"
                f"Pending requests: <b>{pending}</b>\n"
                f"Verified users: <b>{verified}</b>\n\n"
                "Use the Roni Admin panel buttons to review pending requests or view lists."
            )
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🧾 Pending requests", callback_data="roni_admin:age_pending")],
                    [InlineKeyboardButton("✅ Verified list", callback_data="roni_admin:age_list")],
                    [InlineKeyboardButton("🧹 Reset ALL verifications", callback_data="age_admin:reset_all")],
                    [InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")],
                ]
            )
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            await cq.answer()
            return

        # Already verified?
        if is_age_verified(uid):
            await cq.message.edit_text(
                _approved_text(),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔥 Teaser & Promo Channels", callback_data="roni_portal:teaser")],
                        [InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:open")],
                        [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                    ]
                ),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        # Pending?
        if store.get_menu(_pending_key(uid)):
            await cq.message.edit_text(
                _already_pending_text(),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]]),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        await cq.message.edit_text(_pending_user_text(), reply_markup=_user_intro_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_age:begin$"))
    async def age_begin(_, cq: CallbackQuery):
        uid = cq.from_user.id
        if uid == RONI_OWNER_ID:
            await cq.answer("Admin does not submit verification 💜", show_alert=True)
            return
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
        store.set_menu(_step_key(uid), "")
        await cq.message.edit_text(_pending_user_text(), reply_markup=_user_intro_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Receive photo in DM
    @app.on_message(filters.private & filters.photo)
    async def age_photo_receive(_, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id
        if uid == RONI_OWNER_ID:
            return

        step = store.get_menu(_step_key(uid)) or ""
        if step != "await_photo":
            return

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

        _jset(_pending_key(uid), payload)
        _add_pending(uid)
        store.set_menu(_step_key(uid), "")

        await m.reply_text(
            "✅ Submitted! 💜\n\n"
            "Roni will review your verification photo soon.\n"
            "You’ll get a message when you’re approved/denied or if more info is needed.",
            disable_web_page_preview=True,
        )

        await _notify_admin(app, payload)

    # Admin: next pending
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

    # Admin actions approve/deny/moreinfo/reset
    @app.on_callback_query(filters.regex(r"^age_admin:(approve|deny|moreinfo|reset):(\d+)$"))
    async def admin_action(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        parts = (cq.data or "").split(":")
        if len(parts) != 3:
            await cq.answer("Bad callback.", show_alert=True)
            return

        action = parts[1]
        uid = int(parts[2])

        payload = _jget(_pending_key(uid), {})
        # reset can work even if not pending
        if action == "reset":
            await cq.message.reply_text(
                f"Reset age verification for <code>{uid}</code>?\n\nThis will:\n• remove verified status\n• clear pending request (if any)\n• force re-submit photo",
                reply_markup=_admin_reset_user_kb(uid),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        if not payload:
            await cq.answer("Request not found (maybe already handled).", show_alert=True)
            _remove_pending(uid)
            return

        if action == "approve":
            store.set_menu(_age_ok_key(uid), "1")
            ids = _get_verified_index()
            if uid not in ids:
                ids.append(uid)
                _set_verified_index(ids)

            _clear_pending(uid)

            try:
                await app.send_message(uid, _approved_text(), disable_web_page_preview=True)
            except Exception:
                pass

            await cq.answer("Approved ✅", show_alert=True)
            try:
                await cq.message.edit_caption((cq.message.caption or "") + "\n\n✅ <b>APPROVED</b>", reply_markup=_admin_next_kb())
            except Exception:
                pass
            return

        if action == "deny":
            _clear_pending(uid)

            try:
                await app.send_message(uid, _denied_text(), disable_web_page_preview=True)
            except Exception:
                pass

            await cq.answer("Denied ❌", show_alert=True)
            try:
                await cq.message.edit_caption((cq.message.caption or "") + "\n\n❌ <b>DENIED</b>", reply_markup=_admin_next_kb())
            except Exception:
                pass
            return

        if action == "moreinfo":
            payload["status"] = "moreinfo"
            payload["moreinfo_at"] = _now_iso()
            _jset(_pending_key(uid), payload)

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
                await cq.message.edit_caption((cq.message.caption or "") + "\n\n🔁 <b>MORE INFO REQUESTED</b>", reply_markup=_admin_next_kb())
            except Exception:
                pass
            return

    # Confirm reset specific user
    @app.on_callback_query(filters.regex(r"^age_admin:reset_confirm:(\d+)$"))
    async def admin_reset_confirm(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        uid = int((cq.data or "").split(":")[-1])

        _remove_verified(uid)
        _clear_pending(uid)

        try:
            await app.send_message(
                uid,
                "🧹 Your age verification was reset.\n\nPlease tap ✅ Age Verify and submit a new photo (nose + pinky).",
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        await cq.answer("Reset ✅", show_alert=True)
        try:
            await cq.message.edit_text(f"✅ Reset completed for <code>{uid}</code>.", reply_markup=_admin_next_kb(), disable_web_page_preview=True)
        except Exception:
            pass

    # Admin: reset all entry
    @app.on_callback_query(filters.regex(r"^age_admin:reset_all$"))
    async def admin_reset_all(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        await cq.answer()
        await cq.message.edit_text(
            "⚠️ <b>Reset ALL age verifications?</b>\n\n"
            "This will remove verified status for everyone and clear all pending requests.\n"
            "Everyone will have to re-submit a verification photo.\n\n"
            "Are you sure?",
            reply_markup=_admin_reset_all_kb(),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^age_admin:reset_all_confirm$"))
    async def admin_reset_all_confirm(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        # Reset indexes
        verified_ids = _get_verified_index()
        pending_ids = _get_pending_index()

        # Clear AGE_OK flags for verified ids only (best we can do with MenuStore)
        for uid in verified_ids:
            try:
                store.set_menu(_age_ok_key(uid), "")
            except Exception:
                pass

        _set_verified_index([])
        _set_pending_index([])

        # Clear pending payloads
        for uid in pending_ids:
            try:
                store.set_menu(_pending_key(uid), "")
                store.set_menu(_step_key(uid), "")
            except Exception:
                pass

        await cq.answer("Reset ALL ✅", show_alert=True)
        await cq.message.edit_text(
            "✅ <b>All age verifications were reset.</b>\n\n"
            "Everyone will need to re-submit their verification photo.",
            reply_markup=_admin_next_kb(),
            disable_web_page_preview=True,
        )


    # Admin: verified list (paged) + reset buttons
    @app.on_callback_query(filters.regex(r"^roni_admin:age_list(?::(\d+))?$"))
    async def admin_verified_list(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        parts = (cq.data or "").split(":")
        page = 0
        if len(parts) == 3:
            try:
                page = max(0, int(parts[2]))
            except Exception:
                page = 0

        ids = _get_verified_index()
        total = len(ids)
        page_size = 20
        max_page = max(0, (total - 1) // page_size) if total else 0
        if page > max_page:
            page = max_page

        if total == 0:
            text = "✅ <b>Age-Verified Users</b>\n\n• none yet"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]])
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            await cq.answer()
            return

        start = page * page_size
        end = min(total, start + page_size)
        slice_ids = ids[start:end]

        # Resolve names/usernames best-effort
        name_map = {}
        try:
            users = await app.get_users(slice_ids)
            if not isinstance(users, list):
                users = [users]
            for u in users:
                try:
                    uid = int(u.id)
                    uname = (u.username or "")
                    fname = (u.first_name or "User")
                    name_map[uid] = (fname, uname)
                except Exception:
                    pass
        except Exception:
            pass

        lines = [f"✅ <b>Age-Verified Users</b>  (Page {page+1}/{max_page+1})\n"]
        rows = []

        for uid in slice_ids:
            fname, uname = name_map.get(uid, ("User", ""))
            label = f"{fname} " + (f"(@{uname})" if uname else "")
            lines.append(f"• {label} — <code>{uid}</code>")

            btn_label = f"🧹 Reset {fname[:18]} ({uid})"
            rows.append([InlineKeyboardButton(btn_label, callback_data=f"age_admin:reset:{uid}")])

        lines.append(f"\nTotal verified: <b>{total}</b>")

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅ Prev", callback_data=f"roni_admin:age_list:{page-1}"))
        if page < max_page:
            nav_row.append(InlineKeyboardButton("Next ➡", callback_data=f"roni_admin:age_list:{page+1}"))
        if nav_row:
            rows.append(nav_row)

        rows.append([InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")])

        await cq.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), disable_web_page_preview=True)
        await cq.answer()

            return

        start = page * page_size
        end = min(total, start + page_size)
        slice_ids = ids[start:end]

        lines = [f"✅ <b>Age-Verified Users</b>  (Page {page+1}/{max_page+1})\n"]
        for uid in slice_ids:
            lines.append(f"• <code>{uid}</code>")
        lines.append(f"\nTotal verified: <b>{total}</b>")

        rows = []
        for uid in slice_ids:
            rows.append([InlineKeyboardButton(f"🧹 Reset {uid}", callback_data=f"age_admin:reset:{uid}")])

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅ Prev", callback_data=f"roni_admin:age_list:{page-1}"))
        if page < max_page:
            nav_row.append(InlineKeyboardButton("Next ➡", callback_data=f"roni_admin:age_list:{page+1}"))
        if nav_row:
            rows.append(nav_row)

        rows.append([InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")])

        await cq.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), disable_web_page_preview=True)
        await cq.answer()


    # Admin: pending list (paged)
    @app.on_callback_query(filters.regex(r"^roni_admin:age_pending(?::(\d+))?$"))
    async def admin_pending_list(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        parts = (cq.data or "").split(":")
        page = 0
        if len(parts) == 3:
            try:
                page = max(0, int(parts[2]))
            except Exception:
                page = 0

        idx = _get_pending_index()
        total = len(idx)
        page_size = 20
        max_page = max(0, (total - 1) // page_size) if total else 0
        if page > max_page:
            page = max_page

        if total == 0:
            text = "📭 <b>No pending age-verification requests.</b>"
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")],
                    [InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")],
                ]
            )
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            await cq.answer()
            return

        start = page * page_size
        end = min(total, start + page_size)
        slice_ids = idx[start:end]

        lines = [f"🧾 <b>Pending Age-Verification Requests</b>  (Page {page+1}/{max_page+1})\n"]
        rows = [[InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")]]

        for uid in slice_ids:
            p = _jget(_pending_key(uid), {})
            uname = p.get("username") or ""
            name = p.get("name") or "User"
            lines.append(f"• {name} {f'(@{uname})' if uname else ''} — <code>{uid}</code>")
            rows.append([InlineKeyboardButton(f"🧹 Reset {uid}", callback_data=f"age_admin:reset:{uid}")])

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅ Prev", callback_data=f"roni_admin:age_pending:{page-1}"))
        if page < max_page:
            nav_row.append(InlineKeyboardButton("Next ➡", callback_data=f"roni_admin:age_pending:{page+1}"))
        if nav_row:
            rows.append(nav_row)

        rows.append([InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")])

        await cq.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), disable_web_page_preview=True)
        await cq.answer()

    # Admin DM commands    # Admin DM commands
    @app.on_message(filters.private & filters.user(RONI_OWNER_ID) & filters.command(["age_reset", "age_reset_user"]))
    async def cmd_age_reset(_, m: Message):
        parts = (m.text or "").split()
        if len(parts) < 2:
            await m.reply_text("Usage: /age_reset <user_id>")
            return
        try:
            uid = int(parts[1])
        except ValueError:
            await m.reply_text("That doesn't look like a user_id.")
            return
        _remove_verified(uid)
        _clear_pending(uid)
        await m.reply_text(f"✅ Reset completed for <code>{uid}</code>.", disable_web_page_preview=True)

    @app.on_message(filters.private & filters.user(RONI_OWNER_ID) & filters.command(["age_reset_all"]))
    async def cmd_age_reset_all(_, m: Message):
        await m.reply_text(
            "⚠️ This will reset ALL age verifications.\n\n"
            "Tap to confirm:",
            reply_markup=_admin_reset_all_kb(),
            disable_web_page_preview=True,
        )
