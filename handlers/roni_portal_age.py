# handlers/roni_portal_age.py
import json
import logging
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611

AGE_INDEX_KEY = "RoniAgeIndex"   # ✅ legacy list key from your working build
AGE_OK_LIST = "AGE_OK_LIST"      # optional newer list


def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"


def _jloads(raw: str, default):
    try:
        return json.loads(raw)
    except Exception:
        return default


def _load_index_ids() -> list[int]:
    raw = store.get_menu(AGE_INDEX_KEY) or "[]"
    data = _jloads(raw, [])
    if isinstance(data, list):
        out = []
        for x in data:
            try:
                out.append(int(x))
            except Exception:
                pass
        return out
    return []


def _save_index_ids(ids: list[int]) -> None:
    # dedupe while preserving order
    seen = set()
    dedup = []
    for uid in ids:
        if uid in seen:
            continue
        seen.add(uid)
        dedup.append(uid)
    store.set_menu(AGE_INDEX_KEY, json.dumps(dedup))


def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True
    try:
        return bool(store.get_menu(_age_key(user_id)))
    except Exception:
        return False


def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal_age registered")

    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def age_start(_, cq: CallbackQuery):
        if cq.message and cq.message.chat and cq.message.chat.type != ChatType.PRIVATE:
            await cq.answer("Open this in DM 💕", show_alert=True)
            return

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ I confirm I’m 18+", callback_data="roni_age:confirm")],
                [InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")],
            ]
        )
        await cq.message.edit_text(
            "✅ <b>Age Verification</b>\n\n"
            "Tap below to confirm you’re 18+.\n\n"
            "🚫 <b>NO meetups</b> — online/texting only.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_age:confirm$"))
    async def age_confirm(_, cq: CallbackQuery):
        if not cq.from_user:
            return
        uid = cq.from_user.id

        # per-user record (works with legacy style too)
        record = {
            "status": "ok",
            "user_id": uid,
            "username": cq.from_user.username or "",
            "verified_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "note": "",
        }
        store.set_menu(_age_key(uid), json.dumps(record))

        # ✅ legacy index
        ids = _load_index_ids()
        if uid not in ids:
            ids.append(uid)
            _save_index_ids(ids)

        # optional newer list (won't hurt)
        try:
            raw = store.get_menu(AGE_OK_LIST) or "[]"
            lst = _jloads(raw, [])
            if not isinstance(lst, list):
                lst = []
            lst = [x for x in lst if not (isinstance(x, dict) and x.get("user_id") == uid)]
            lst.append({"user_id": uid, "username": cq.from_user.username or "", "name": cq.from_user.first_name or "", "ts": datetime.utcnow().isoformat()})
            store.set_menu(AGE_OK_LIST, json.dumps(lst))
        except Exception:
            pass

        await cq.message.edit_text(
            "✅ <b>Verified</b> 💕\n\n"
            "You’re age-verified. Your booking options and teaser links are now unlocked.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:open")],
                    [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer("Verified 💕")

    @app.on_callback_query(filters.regex(r"^roni_admin:age_list$"))
    async def admin_age_list(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != RONI_OWNER_ID:
            await cq.answer("Only Roni 💜", show_alert=True)
            return

        ids = _load_index_ids()
        if not ids:
            await cq.message.edit_text("✅ <b>Age-Verified Users</b>\n\n• none yet", reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]]
            ))
            await cq.answer()
            return

        lines = ["✅ <b>Age-Verified Users</b>\n"]
        for uid in ids[-80:]:
            raw = store.get_menu(_age_key(uid)) or ""
            rec = _jloads(raw, {}) if raw else {}
            uname = rec.get("username") or f"ID {uid}"
            verified_at = rec.get("verified_at", "")
            lines.append(f"• {uname} — <code>{uid}</code> {('— ' + verified_at) if verified_at else ''}")

        await cq.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]]),
            disable_web_page_preview=True,
        )
        await cq.answer()
