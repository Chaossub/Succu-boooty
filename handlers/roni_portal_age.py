# handlers/roni_portal_age.py
import json
import logging
from datetime import datetime, timezone

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611

# --- Storage keys ---
AGE_OK_PREFIX = "AGE_OK:"                # AGE_OK:<user_id> => "1"
AGE_INDEX_KEY = "RoniAgeIndex"           # JSON list of verified user_ids (legacy/compat)
PENDING_PREFIX = "AGE_PENDING:"          # AGE_PENDING:<user_id> => JSON blob
PENDING_INDEX_KEY = "RoniAgePendingIndex"  # JSON list of pending user_ids


def _age_key(user_id: int) -> str:
    return f"{AGE_OK_PREFIX}{user_id}"


def _pending_key(user_id: int) -> str:
    return f"{PENDING_PREFIX}{user_id}"


def _jget(key: str, default):
    try:
        raw = store.get_menu(key)
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default


def _jset(key: str, obj) -> None:
    store.set_menu(key, json.dumps(obj, ensure_ascii=False))


def _get_index(key: str) -> list[int]:
    raw = store.get_menu(key) or "[]"
    try:
        data = json.loads(raw)
    except Exception:
        data = []
    ids: list[int] = []
    if isinstance(data, list):
        for x in data:
            try:
                ids.append(int(x))
            except Exception:
                pass
    # unique + stable
    out = []
    seen = set()
    for uid in ids:
        if uid not in seen:
            seen.add(uid)
            out.append(uid)
    return out


def _set_index(key: str, ids: list[int]) -> None:
    store.set_menu(key, json.dumps([int(x) for x in ids], ensure_ascii=False))


def _get_verified_index() -> list[int]:
    return sorted(_get_index(AGE_INDEX_KEY))


def _set_verified_index(ids: list[int]) -> None:
    _set_index(AGE_INDEX_KEY, sorted(ids))


def _get_pending_index() -> list[int]:
    return sorted(_get_index(PENDING_INDEX_KEY))


def _set_pending_index(ids: list[int]) -> None:
    _set_index(PENDING_INDEX_KEY, sorted(ids))


def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True
    try:
        if store.get_menu(_age_key(user_id)):
            return True
    except Exception:
        pass
    return user_id in _get_verified_index()


def _ensure_verified(user_id: int) -> None:
    store.set_menu(_age_key(user_id), "1")
    ids = _get_verified_index()
    if user_id not in ids:
        ids.append(user_id)
        _set_verified_index(ids)


def _remove_verified(user_id: int) -> None:
    try:
        store.set_menu(_age_key(user_id), "")
    except Exception:
        pass
    ids = [x for x in _get_verified_index() if x != user_id]
    _set_verified_index(ids)


def _remove_pending(user_id: int) -> None:
    try:
        store.set_menu(_pending_key(user_id), "")
    except Exception:
        pass
    ids = [x for x in _get_pending_index() if x != user_id]
    _set_pending_index(ids)


def _back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]])


def _back_to_assistant() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]])


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "unknown time"
    try:
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return "unknown time"


def _pending_controls(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"age_admin:approve:{uid}"),
                InlineKeyboardButton("❌ Deny", callback_data=f"age_admin:deny:{uid}"),
            ],
            [
                InlineKeyboardButton("🔁 Need more info", callback_data=f"age_admin:more:{uid}"),
                InlineKeyboardButton("🧹 Reset user", callback_data=f"age_admin:reset:{uid}"),
            ],
            [InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")],
            [InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")],
        ]
    )


async def _resolve_users(client: Client, ids: list[int]) -> dict[int, tuple[str, str]]:
    """uid -> (first_name, username) best-effort"""
    out: dict[int, tuple[str, str]] = {}
    if not ids:
        return out
    try:
        users = await client.get_users(ids)
        if not isinstance(users, list):
            users = [users]
        for u in users:
            try:
                out[int(u.id)] = (u.first_name or "User", u.username or "")
            except Exception:
                pass
    except Exception:
        pass
    return out


async def _show_no_more_pending(cq: CallbackQuery):
    # This is the UX you asked for: show "no more" and close buttons.
    try:
        await cq.message.edit_text(
            "✅ <b>No more pending age-verification requests.</b>",
            reply_markup=_back_to_admin(),
            disable_web_page_preview=True,
        )
    except Exception:
        pass


def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal_age registered (approve/deny closes, no-more shows)")

    # --- USER: start ---
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def age_start(_, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        if uid and is_age_verified(uid):
            await cq.answer("You’re already verified ✅", show_alert=True)
            try:
                await cq.message.edit_text("✅ You are already age-verified.", reply_markup=_back_to_assistant())
            except Exception:
                pass
            return

        await cq.message.edit_text(
            "✅ <b>Age Verification</b>\n\n"
            "Send ONE photo of you touching your nose with your pinky.\n"
            "After you send it, Roni will approve/deny.\n\n"
            "🚫 No meetups — online/texting only.",
            reply_markup=_back_to_assistant(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # --- USER: photo intake in DM ---
    @app.on_message(filters.private & filters.photo)
    async def photo_in_dm(client: Client, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id
        if uid == RONI_OWNER_ID:
            return
        if is_age_verified(uid):
            return

        pending = {
            "user_id": uid,
            "username": (m.from_user.username or ""),
            "name": (m.from_user.first_name or "User"),
            "ts": int(datetime.now(tz=timezone.utc).timestamp()),
            "message_id": m.id,
        }
        _jset(_pending_key(uid), pending)

        idx = _get_pending_index()
        if uid not in idx:
            idx.append(uid)
            _set_pending_index(idx)

        # forward the photo to Roni
        try:
            await client.forward_messages(RONI_OWNER_ID, m.chat.id, m.id)
        except Exception:
            try:
                await client.send_photo(
                    RONI_OWNER_ID,
                    photo=m.photo.file_id,
                    caption=f"📸 Age verification photo\n\nFrom: {pending['name']} "
                            f"{'(@'+pending['username']+')' if pending['username'] else ''}\n"
                            f"ID: <code>{uid}</code>\nReceived: {_fmt_ts(pending['ts'])}",
                )
            except Exception:
                pass

        # control message for Roni
        try:
            await client.send_message(
                RONI_OWNER_ID,
                f"📸 <b>New age verification request</b>\n\n"
                f"{pending['name']} {'(@'+pending['username']+')' if pending['username'] else ''}\n"
                f"ID: <code>{uid}</code>\n"
                f"Received: <b>{_fmt_ts(pending['ts'])}</b>",
                reply_markup=_pending_controls(uid),
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        await m.reply_text("✅ Photo received! Roni will review it shortly 💕")

    # --- ADMIN: verified list (paged, names) ---
    @app.on_callback_query(filters.regex(r"^roni_admin:age_list(?::(\d+))?$"))
    async def admin_verified_list(client: Client, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        parts = (cq.data or "").split(":")
        page = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else 0

        ids = _get_verified_index()
        total = len(ids)
        if total == 0:
            await cq.message.edit_text("✅ <b>Age-Verified Users</b>\n\n• none yet", reply_markup=_back_to_admin())
            await cq.answer()
            return

        page_size = 20
        max_page = (total - 1) // page_size
        page = max(0, min(page, max_page))

        slice_ids = ids[page * page_size : (page + 1) * page_size]
        name_map = await _resolve_users(client, slice_ids)

        text_lines = [f"✅ <b>Age-Verified Users</b>  (Page {page+1}/{max_page+1})\n"]
        rows = []
        for uid in slice_ids:
            fname, uname = name_map.get(uid, ("User", ""))
            label = f"{fname}" + (f" (@{uname})" if uname else "")
            text_lines.append(f"• {label} — <code>{uid}</code>")
            rows.append([InlineKeyboardButton(f"🧹 Reset {fname[:18]} ({uid})", callback_data=f"age_admin:reset:{uid}")])

        text_lines.append(f"\nTotal verified: <b>{total}</b>")

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"roni_admin:age_list:{page-1}"))
        if page < max_page:
            nav.append(InlineKeyboardButton("Next ➡", callback_data=f"roni_admin:age_list:{page+1}"))
        if nav:
            rows.append(nav)
        rows.append([InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")])

        await cq.message.edit_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(rows))
        await cq.answer()

    # --- ADMIN: pending list (paged, shows received time) ---
    @app.on_callback_query(filters.regex(r"^roni_admin:age_pending(?::(\d+))?$"))
    async def admin_pending_list(client: Client, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        parts = (cq.data or "").split(":")
        page = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else 0

        idx = _get_pending_index()
        total = len(idx)
        if total == 0:
            await cq.message.edit_text(
                "✅ <b>No pending age-verification requests.</b>",
                reply_markup=_back_to_admin(),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        page_size = 20
        max_page = (total - 1) // page_size
        page = max(0, min(page, max_page))

        slice_ids = idx[page * page_size : (page + 1) * page_size]
        name_map = await _resolve_users(client, slice_ids)

        text_lines = [f"🧾 <b>Pending Age-Verification Requests</b>  (Page {page+1}/{max_page+1})\n"]
        rows = []

        for uid in slice_ids:
            pending = _jget(_pending_key(uid), {})
            fname, uname = name_map.get(uid, (pending.get("name") or "User", pending.get("username") or ""))
            recv = _fmt_ts(pending.get("ts"))
            label = f"{fname}" + (f" (@{uname})" if uname else "")
            text_lines.append(f"• {label} — <code>{uid}</code> — <i>{recv}</i>")
            rows.append([InlineKeyboardButton(f"Open {fname[:18]} ({uid})", callback_data=f"age_admin:open:{uid}")])

        text_lines.append(f"\nTotal pending: <b>{total}</b>")

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"roni_admin:age_pending:{page-1}"))
        if page < max_page:
            nav.append(InlineKeyboardButton("Next ➡", callback_data=f"roni_admin:age_pending:{page+1}"))
        if nav:
            rows.append(nav)
        rows.append([InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")])
        rows.append([InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")])

        await cq.message.edit_text("\n".join(text_lines), reply_markup=InlineKeyboardMarkup(rows))
        await cq.answer()

    # --- ADMIN: open/next pending ---
    @app.on_callback_query(filters.regex(r"^age_admin:next$"))
    async def admin_next(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        idx = _get_pending_index()
        if not idx:
            await cq.answer("No pending requests ✅", show_alert=True)
            await _show_no_more_pending(cq)
            return
        uid = idx[0]
        pending = _jget(_pending_key(uid), {})
        name = pending.get("name") or "User"
        uname = pending.get("username") or ""
        recv = _fmt_ts(pending.get("ts"))
        await cq.message.edit_text(
            f"📸 <b>Pending request</b>\n\n"
            f"{name} {'(@'+uname+')' if uname else ''}\n"
            f"ID: <code>{uid}</code>\n"
            f"Received: <b>{recv}</b>",
            reply_markup=_pending_controls(uid),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^age_admin:open:(\d+)$"))
    async def admin_open(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        uid = int((cq.data or "").split(":")[-1])
        pending = _jget(_pending_key(uid), {})
        if not pending:
            await cq.answer("That request no longer exists.", show_alert=True)
            # remove from index just in case
            _remove_pending(uid)
            idx = _get_pending_index()
            if not idx:
                await _show_no_more_pending(cq)
            return
        name = pending.get("name") or "User"
        uname = pending.get("username") or ""
        recv = _fmt_ts(pending.get("ts"))
        await cq.message.edit_text(
            f"📸 <b>Pending request</b>\n\n"
            f"{name} {'(@'+uname+')' if uname else ''}\n"
            f"ID: <code>{uid}</code>\n"
            f"Received: <b>{recv}</b>",
            reply_markup=_pending_controls(uid),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # --- ADMIN: approve/deny/more/reset ---
    @app.on_callback_query(filters.regex(r"^age_admin:approve:(\d+)$"))
    async def admin_approve(client: Client, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        uid = int((cq.data or "").split(":")[-1])
        _ensure_verified(uid)
        _remove_pending(uid)

        # Close the action message (removes buttons) + show status
        try:
            await cq.message.edit_text(
                f"✅ <b>APPROVED</b>\nUser: <code>{uid}</code>\n\nNo meetups — online/texting only.",
                reply_markup=None,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        try:
            await client.send_message(uid, "✅ You’re approved! Teaser/promo links and NSFW booking are now unlocked. 💕")
        except Exception:
            pass

        # If no more pending, show "no more" on next click
        if not _get_pending_index():
            await cq.answer("Approved ✅ (no more pending)", show_alert=True)
        else:
            await cq.answer("Approved ✅", show_alert=True)

    @app.on_callback_query(filters.regex(r"^age_admin:deny:(\d+)$"))
    async def admin_deny(client: Client, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        uid = int((cq.data or "").split(":")[-1])
        _remove_pending(uid)
        _remove_verified(uid)

        try:
            await cq.message.edit_text(
                f"❌ <b>DENIED</b>\nUser: <code>{uid}</code>\n\nThey can re-verify by sending a new photo.",
                reply_markup=None,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        try:
            await client.send_message(uid, "❌ Your verification was denied. Please resend a clear photo (pinky touching nose).")
        except Exception:
            pass

        await cq.answer("Denied ❌", show_alert=True)

    @app.on_callback_query(filters.regex(r"^age_admin:more:(\d+)$"))
    async def admin_more(client: Client, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        uid = int((cq.data or "").split(":")[-1])
        try:
            await client.send_message(uid, "🔁 I need a clearer photo. Please resend with your pinky touching your nose. 💕")
        except Exception:
            pass
        await cq.answer("Asked for more ✅", show_alert=True)

    @app.on_callback_query(filters.regex(r"^age_admin:reset:(\d+)$"))
    async def admin_reset(client: Client, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        uid = int((cq.data or "").split(":")[-1])
        _remove_pending(uid)
        _remove_verified(uid)

        try:
            await cq.message.edit_text(
                f"🧹 <b>RESET</b>\nUser: <code>{uid}</code>\n\nThey must re-verify.",
                reply_markup=None,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        try:
            await client.send_message(uid, "🧹 Your verification was reset. Please re-verify by sending the required photo.")
        except Exception:
            pass
        await cq.answer("Reset ✅", show_alert=True)
