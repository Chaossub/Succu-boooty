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


def _load_legacy_menus_age_list():
    """
    If your MenuStore backend changed, old values may still exist in data/menus.json.
    This tries to recover AGE_OK_LIST from there.
    """
    try:
        with open("data/menus.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get(_av_list_key())
        if not raw:
            return []
        legacy = json.loads(raw)

        # legacy could be list[int] or list[dict]
        cleaned = []
        if isinstance(legacy, list):
            for x in legacy:
                if isinstance(x, dict) and x.get("user_id"):
                    cleaned.append(x)
                elif isinstance(x, int):
                    cleaned.append(
                        {"user_id": x, "username": "", "name": "", "ts": ""}
                    )
        return cleaned
    except Exception:
        return []


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

    # fallback: check list (current backend), then legacy
    lst = _jget(_av_list_key(), [])
    if isinstance(lst, list):
        for x in lst:
            if isinstance(x, dict) and x.get("user_id") == user_id:
                return True
            if isinstance(x, int) and x == user_id:
                return True

    legacy = _load_legacy_menus_age_list()
    return any(isinstance(x, dict) and x.get("user_id") == user_id for x in legacy)


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

        # store per-user flag
        store.set_menu(_age_key(user_id), "1")

        # store list entry for admin view
        lst = _jget(_av_list_key(), [])
        if not isinstance(lst, list):
            lst = []

        entry = {
            "user_id": user_id,
            "username": cq.from_user.username or "",
            "name": cq.from_user.first_name or "",
            "ts": datetime.utcnow().isoformat(),
        }

        # dedupe by user_id
        lst = [x for x in lst if not (isinstance(x, dict) and x.get("user_id") == user_id)]
        lst.append(entry)
        _jset(_av_list_key(), lst)

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

        lst = _jget(_av_list_key(), [])
        if not isinstance(lst, list) or not lst:
            # fallback to legacy menus.json
            legacy = _load_legacy_menus_age_list()
            if legacy:
                log.warning("Recovered legacy AGE_OK_LIST from data/menus.json and migrated it into MenuStore")
                _jset(_av_list_key(), legacy)
                lst = legacy

        if not isinstance(lst, list) or not lst:
            txt = "✅ <b>Age-Verified List</b>\n\n• none yet"
        else:
            lines = ["✅ <b>Age-Verified List</b>\n"]
            for x in lst[-50:]:
                if isinstance(x, dict) and x.get("user_id"):
                    who = (x.get("name") or "User")
                    if x.get("username"):
                        who += f" (@{x['username']})"
                    lines.append(f"• {who} — <code>{x.get('user_id')}</code>")
                elif isinstance(x, int):
                    lines.append(f"• <code>{x}</code>")
            txt = "\n".join(lines)

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back", callback_data="roni_admin:open")]])
        await cq.message.edit_text(txt, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()
