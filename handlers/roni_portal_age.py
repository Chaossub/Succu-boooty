# handlers/roni_portal_age.py

import json
import logging
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.menu_store import store

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611

# Storage keys
AGE_OK_PREFIX = "AGE_OK:"               # per-user flag: AGE_OK:<user_id> => "1"
AGE_INDEX_KEY = "RoniAgeIndex"          # list of verified ids (legacy/compat)
PENDING_PREFIX = "AGE_PENDING:"         # per-user pending blob
PENDING_INDEX_KEY = "RoniAgePendingIndex"  # list of pending ids

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

def _get_verified_index() -> list[int]:
    raw = store.get_menu(AGE_INDEX_KEY) or "[]"
    try:
        data = json.loads(raw)
    except Exception:
        data = []
    ids = []
    if isinstance(data, list):
        for x in data:
            try:
                ids.append(int(x))
            except Exception:
                pass
    # also merge in any AGE_OK flags we already have in index (keeps stable)
    return sorted(list(dict.fromkeys(ids)))

def _set_verified_index(ids: list[int]) -> None:
    store.set_menu(AGE_INDEX_KEY, json.dumps([int(x) for x in ids], ensure_ascii=False))

def _get_pending_index() -> list[int]:
    raw = store.get_menu(PENDING_INDEX_KEY) or "[]"
    try:
        data = json.loads(raw)
    except Exception:
        data = []
    ids = []
    if isinstance(data, list):
        for x in data:
            try:
                ids.append(int(x))
            except Exception:
                pass
    return sorted(list(dict.fromkeys(ids)))

def _set_pending_index(ids: list[int]) -> None:
    store.set_menu(PENDING_INDEX_KEY, json.dumps([int(x) for x in ids], ensure_ascii=False))

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
    # legacy list fallback
    try:
        return user_id in _get_verified_index()
    except Exception:
        return False

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

def _admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]])

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

def _verify_entry_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
        ]
    )

def _verified_list_text(page: int, max_page: int, total: int, rows: list[str]) -> str:
    head = f"✅ <b>Age-Verified Users</b>  (Page {page+1}/{max_page+1})\n"
    body = "\n".join(rows) if rows else "• none yet"
    return f"{head}\n{body}\n\nTotal verified: <b>{total}</b>"

def _pending_list_text(page: int, max_page: int, total: int, rows: list[str]) -> str:
    head = f"🧾 <b>Pending Age-Verification Requests</b>  (Page {page+1}/{max_page+1})\n"
    body = "\n".join(rows) if rows else "• none"
    return f"{head}\n{body}\n\nTotal pending: <b>{total}</b>"

def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal_age registered (verified/pending lists fire + show none)")

    # --- User entry point (photo required) ---
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def age_start(_, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        if uid and is_age_verified(uid):
            await cq.answer("You’re already verified ✅", show_alert=True)
            # send them back to main
            try:
                await cq.message.edit_text("✅ You are already age-verified.", reply_markup=_verify_entry_kb())
            except Exception:
                pass
            return

        await cq.message.edit_text(
            "✅ <b>Age Verification</b>\n\n"
            "Please send ONE photo of you touching your nose with your pinky.\n"
            "After you send it, Roni will review and approve/deny.\n\n"
            "🚫 No meetups — online/texting only.",
            reply_markup=_verify_entry_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Capture photo in DM to bot while in age verify flow:
    @app.on_message(filters.private & filters.photo)
    async def photo_in_dm(client: Client, m: Message):
        if not m.from_user:
            return
        uid = m.from_user.id
        if uid == RONI_OWNER_ID:
            return

        # If already verified, ignore
        if is_age_verified(uid):
            return

        # Save pending meta
        pending = {
            "user_id": uid,
            "username": (m.from_user.username or ""),
            "name": (m.from_user.first_name or "User"),
            "ts": int(datetime.utcnow().timestamp()),
            "message_id": m.id,
        }
        _jset(_pending_key(uid), pending)
        idx = _get_pending_index()
        if uid not in idx:
            idx.append(uid)
            _set_pending_index(idx)

        # forward/send to Roni for review
        try:
            await client.forward_messages(RONI_OWNER_ID, m.chat.id, m.id)
        except Exception:
            try:
                await client.send_photo(
                    RONI_OWNER_ID,
                    photo=m.photo.file_id,
                    caption=f"📸 Age verification photo\n\nFrom: {pending['name']} "
                            f"{'(@'+pending['username']+')' if pending['username'] else ''}\n"
                            f"ID: <code>{uid}</code>",
                )
            except Exception:
                pass

        # send control message to Roni
        try:
            await client.send_message(
                RONI_OWNER_ID,
                f"📸 <b>New age verification request</b>\n\n"
                f"{pending['name']} {'(@'+pending['username']+')' if pending['username'] else ''}\n"
                f"ID: <code>{uid}</code>",
                reply_markup=_pending_controls(uid),
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        await m.reply_text("✅ Photo received! Roni will review it shortly 💕")

    # --- Admin: verified list (paged) + names ---
    @app.on_callback_query(filters.regex(r"^roni_admin:age_list(?::(\d+))?$"))
    async def admin_verified_list(client: Client, cq: CallbackQuery):
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
            await cq.message.edit_text(
                "✅ <b>Age-Verified Users</b>\n\n• none yet",
                reply_markup=_admin_back(),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        start = page * page_size
        end = min(total, start + page_size)
        slice_ids = ids[start:end]

        # best-effort resolve names
        name_map: dict[int, tuple[str,str]] = {}
        try:
            users = await client.get_users(slice_ids)
            if not isinstance(users, list):
                users = [users]
            for u in users:
                try:
                    name_map[int(u.id)] = (u.first_name or "User", u.username or "")
                except Exception:
                    pass
        except Exception:
            pass

        rows_txt = []
        rows_btn = []
        for uid in slice_ids:
            fname, uname = name_map.get(uid, ("User", ""))
            label = f"{fname}" + (f" (@{uname})" if uname else "")
            rows_txt.append(f"• {label} — <code>{uid}</code>")
            btn_label = f"🧹 Reset {fname[:18]} ({uid})"
            rows_btn.append([InlineKeyboardButton(btn_label, callback_data=f"age_admin:reset:{uid}")])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"roni_admin:age_list:{page-1}"))
        if page < max_page:
            nav.append(InlineKeyboardButton("Next ➡", callback_data=f"roni_admin:age_list:{page+1}"))
        if nav:
            rows_btn.append(nav)

        rows_btn.append([InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")])

        await cq.message.edit_text(
            _verified_list_text(page, max_page, total, rows_txt),
            reply_markup=InlineKeyboardMarkup(rows_btn),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # --- Admin: pending list (paged) ---
    @app.on_callback_query(filters.regex(r"^roni_admin:age_pending(?::(\d+))?$"))
    async def admin_pending_list(client: Client, cq: CallbackQuery):
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
            await cq.message.edit_text(
                "📭 <b>No pending age-verification requests.</b>",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")],
                        [InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")],
                    ]
                ),
                disable_web_page_preview=True,
            )
            await cq.answer()
            return

        start = page * page_size
        end = min(total, start + page_size)
        slice_ids = idx[start:end]

        rows_txt = []
        rows_btn = [[InlineKeyboardButton("📥 Next pending", callback_data="age_admin:next")]]

        # Best-effort resolve names (but also use stored pending meta)
        name_map: dict[int, tuple[str,str]] = {}
        try:
            users = await client.get_users(slice_ids)
            if not isinstance(users, list):
                users = [users]
            for u in users:
                try:
                    name_map[int(u.id)] = (u.first_name or "User", u.username or "")
                except Exception:
                    pass
        except Exception:
            pass

        for uid in slice_ids:
            pending = _jget(_pending_key(uid), {})
            fname, uname = name_map.get(uid, (pending.get("name") or "User", pending.get("username") or ""))
            label = f"{fname}" + (f" (@{uname})" if uname else "")
            rows_txt.append(f"• {label} — <code>{uid}</code>")
            rows_btn.append([InlineKeyboardButton(f"Open {fname[:18]} ({uid})", callback_data=f"age_admin:open:{uid}")])
            rows_btn.append([InlineKeyboardButton(f"🧹 Reset {fname[:18]} ({uid})", callback_data=f"age_admin:reset:{uid}")])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"roni_admin:age_pending:{page-1}"))
        if page < max_page:
            nav.append(InlineKeyboardButton("Next ➡", callback_data=f"roni_admin:age_pending:{page+1}"))
        if nav:
            rows_btn.append(nav)

        rows_btn.append([InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")])

        await cq.message.edit_text(
            _pending_list_text(page, max_page, total, rows_txt),
            reply_markup=InlineKeyboardMarkup(rows_btn),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # --- Admin actions ---
    @app.on_callback_query(filters.regex(r"^age_admin:next$"))
    async def admin_next(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        idx = _get_pending_index()
        if not idx:
            await cq.answer("No pending requests ✅", show_alert=True)
            return
        uid = idx[0]
        pending = _jget(_pending_key(uid), {})
        name = pending.get("name") or "User"
        uname = pending.get("username") or ""
        await cq.message.edit_text(
            f"📸 <b>Pending request</b>\n\n{name} {'(@'+uname+')' if uname else ''}\nID: <code>{uid}</code>",
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
        name = pending.get("name") or "User"
        uname = pending.get("username") or ""
        await cq.message.edit_text(
            f"📸 <b>Pending request</b>\n\n{name} {'(@'+uname+')' if uname else ''}\nID: <code>{uid}</code>",
            reply_markup=_pending_controls(uid),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^age_admin:approve:(\d+)$"))
    async def admin_approve(client: Client, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return
        uid = int((cq.data or "").split(":")[-1])
        _ensure_verified(uid)
        _remove_pending(uid)
        try:
            await client.send_message(uid, "✅ You’re approved! Teaser/promo links and NSFW booking are now unlocked. 💕")
        except Exception:
            pass
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
            await client.send_message(uid, "❌ Your verification was denied. Please try again with a clear photo (pinky touching nose).")
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
            await client.send_message(uid, "🧹 Your verification was reset. Please re-verify by sending the required photo.")
        except Exception:
            pass
        await cq.answer("Reset ✅", show_alert=True)

    # Commands
    @app.on_message(filters.private & filters.user(RONI_OWNER_ID) & filters.command(["age_reset"]))
    async def cmd_reset(_, m: Message):
        parts = (m.text or "").split()
        if len(parts) < 2:
            await m.reply_text("Usage: /age_reset <user_id>")
            return
        try:
            uid = int(parts[1])
        except Exception:
            await m.reply_text("Bad user_id.")
            return
        _remove_pending(uid)
        _remove_verified(uid)
        await m.reply_text(f"✅ Reset {uid}")

    @app.on_message(filters.private & filters.user(RONI_OWNER_ID) & filters.command(["age_reset_all"]))
    async def cmd_reset_all(_, m: Message):
        ids = _get_verified_index()
        for uid in ids:
            _remove_verified(uid)
        store.set_menu(AGE_INDEX_KEY, "[]")
        # also clear pending index
        p = _get_pending_index()
        for uid in p:
            _remove_pending(uid)
        store.set_menu(PENDING_INDEX_KEY, "[]")
        await m.reply_text("✅ Cleared all verified + pending entries.")
