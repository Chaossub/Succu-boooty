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

AGE_LIST_KEY = "AGE_OK_LIST"

def _age_key(user_id: int) -> str:
    return f"AGE_OK:{user_id}"

def _jget(key: str, default):
    try:
        raw = store.get_menu(key)
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default

def _jset(key: str, obj):
    store.set_menu(key, json.dumps(obj))

def _load_legacy_list():
    """
    Fallback for old JSON-only storage (menus.json)
    """
    try:
        with open("data/menus.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get(AGE_LIST_KEY)
        if not raw:
            return []
        return json.loads(raw)
    except Exception:
        return []

def get_all_age_verified_ids() -> list[int]:
    # 1️⃣ Try current backend
    ids = _jget(AGE_LIST_KEY, [])

    # 2️⃣ Fallback to legacy JSON if empty
    if not ids:
        legacy = _load_legacy_list()
        if legacy:
            log.warning("Migrating legacy AGE_OK_LIST into active backend")
            _jset(AGE_LIST_KEY, legacy)
            ids = legacy

    return ids

def is_age_verified(user_id: int) -> bool:
    if user_id == RONI_OWNER_ID:
        return True

    if store.get_menu(_age_key(user_id)):
        return True

    # Legacy fallback
    return user_id in get_all_age_verified_ids()

@Client.on_message(filters.command("ageverify") & filters.private)
async def age_verify_cmd(client: Client, message):
    uid = message.from_user.id

    if is_age_verified(uid):
        await message.reply_text("✅ You are already age verified.")
        return

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("I am 18+ and consent", callback_data="age_ok")]]
    )

    await message.reply_text(
        "🔞 Age Verification Required\n\n"
        "By continuing, you confirm you are **18 years or older**.",
        reply_markup=kb,
    )

@Client.on_callback_query(filters.regex("^age_ok$"))
async def age_verify_cb(client: Client, cq: CallbackQuery):
    uid = cq.from_user.id

    store.set_menu(_age_key(uid), "true")

    ids = set(get_all_age_verified_ids())
    ids.add(uid)
    _jset(AGE_LIST_KEY, list(ids))

    await cq.message.edit_text("✅ You are now age verified.")
    await cq.answer()

@Client.on_message(filters.command("ageverified") & filters.user(RONI_OWNER_ID))
async def list_age_verified(client: Client, message):
    ids = get_all_age_verified_ids()

    if not ids:
        await message.reply_text("⚠️ No age-verified users found.")
        return

    lines = [f"• `{uid}`" for uid in ids]
    await message.reply_text(
        "🔐 **Age-Verified Users**\n\n" + "\n".join(lines)
    )
