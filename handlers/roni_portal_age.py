# handlers/roni_portal_age.py
import json
import logging
import os
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store

log = logging.getLogger(__name__)

RONI_OWNER_ID = 6964994611


def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"


def _av_list_key() -> str:
    return "AGE_OK_LIST"


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


def _legacy_path() -> str:
    return os.getenv("MENU_STORE_PATH", "data/menus.json")


def _load_legacy_json():
    try:
        with open(_legacy_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _normalize_list(lst) -> list[dict]:
    """Supports legacy formats:
    - [123, 456]
    - [{"user_id": 123, "username": "...", "name": "...", "ts": "..."}]
    """
    out: list[dict] = []
    if not isinstance(lst, list):
        return out

    for x in lst:
        if isinstance(x, int):
            out.append({"user_id": x, "username": "", "name": "", "ts": ""})
        elif isinstance(x, dict) and x.get("user_id"):
            out.append(
                {
                    "user_id": int(x.get("user_id")),
                    "username": x.get("username") or "",
                    "name": x.get("name") or "",
                    "ts": x.get("ts") or "",
                }
            )

    seen = set()
    deduped = []
    for e in out:
        uid = e["user_id"]
        if uid in seen:
            continue
        seen.add(uid)
        deduped.append(e)
    return deduped


def _ensure_per_user_flags(entries: list[dict]) -> None:
    """If we recovered users from a list, ensure AGE_OK:{id} exists in current backend
    so the NSFW booking button doesn't disappear on menu rebuild.
    """
    for e in entries:
        uid = e.get("user_id")
        if not uid:
            continue
        try:
            if not store.get_menu(_age_key(uid)):
                store.set_menu(_age_key(uid), "1")
        except Exception:
            continue


def get_age_verified_entries() -> list[dict]:
    # 1) Active backend list
    entries = _normalize_list(_jget(_av_list_key(), []))
    if entries:
        return entries

    # 2) Legacy JSON list (if deploy switched backends)
    legacy = _load_legacy_json()
    legacy_entries = _normalize_list(
        json.loads(legacy.get(_av_list_key(), "[]")) if legacy.get(_av_list_key()) else []
    )
    if legacy_entries:
        log.warning("Recovered legacy AGE_OK_LIST from %s; migrating into active backend", _legacy_path())
        _jset(_av_list_key(), legacy_entries)
        _ensure_per_user_flags(legacy_entries)
        return legacy_entries

    return []


def is_age_verified(user_id: int | None) -> bool:
    if not user_id:
        return False
    if user_id == RONI_OWNER_ID:
        return True

    # Active backend per-user flag
    try:
        if store.get_menu(_age_key(user_id)):
            return True
    except Exception:
        pass

    # Active backend list fallback
    try:
        entries = _normalize_list(_jget(_av_list_key(), []))
        if any(e.get("user_id") == user_id for e in entries):
            return True
    except Exception:
        pass

    # Legacy per-user + list fallback
    legacy = _load_legacy_json()
    try:
        if legacy.get(_age_key(user_id)):
            return True
    except Exception:
        pass
    try:
        legacy_entries = _normalize_list(
            json.loads(legacy.get(_av_list_key(), "[]")) if legacy.get(_av_list_key()) else []
        )
        return any(e.get("user_id") == user_id for e in legacy_entries)
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
            "This assistant is for adults only.\n"
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
        user_id = cq.from_user.id

        # Set per-user flag
        store.set_menu(_age_key(user_id), "1")

        # Update list for admin display
        entries = get_age_verified_entries()
        entries = [e for e in entries if e.get("user_id") != user_id]
        entries.append(
            {
                "user_id": user_id,
                "username": cq.from_user.username or "",
                "name": cq.from_user.first_name or "",
                "ts": datetime.utcnow().isoformat(),
            }
        )
        _jset(_av_list_key(), entries)

        await cq.message.edit_text(
            "✅ <b>Verified</b> 💕\n\n"
            "You’re age-verified. Your booking options and teaser links are now unlocked.\n\n"
            "🚫 <b>NO meetups</b> — online/texting only.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:start")],
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

        entries = get_age_verified_entries()

        if not entries:
            text = "✅ <b>Age-Verified List</b>\n\n• none yet"
        else:
            lines = ["✅ <b>Age-Verified List</b>\n"]
            for e in entries[-80:]:
                uid = e.get("user_id")
                if not uid:
                    continue
                who = (e.get("name") or "User").strip()
                if e.get("username"):
                    who += f" (@{e['username']})"
                lines.append(f"• {who} — <code>{uid}</code>")
            text = "\n".join(lines)

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]])
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()
