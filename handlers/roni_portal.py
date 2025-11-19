# handlers/roni_portal.py
import logging
import os
import json
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from utils.menu_store import store  # still used elsewhere; harmless to keep

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

BOT_USERNAME = (os.getenv("BOT_USERNAME") or "succubot_bot").lstrip("@")
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "Chaossub283").lstrip("@")

# Your personal Telegram user ID – only you see admin controls
OWNER_ID = int(os.getenv("RONI_OWNER_ID") or os.getenv("OWNER_ID", "6964994611"))

# Keys for Roni portal text sections
RONI_MENU_KEY   = "menu"
OPEN_ACCESS_KEY = "open_access"
TEASER_KEY      = "teaser"
ANNOUNCE_KEY    = "announce"

# JSON file for fallback text storage
_RONI_TEXT_PATH = os.getenv("RONI_PORTAL_TEXT_PATH", "data/roni_portal_texts.json")

# Shared Mongo config (same envs as age store)
_MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGO_URI")
_MONGO_DB = (
    os.getenv("MONGO_DB")
    or os.getenv("MONGO_DB_NAME")
    or os.getenv("MONGO_DBNAME")
    or "Succubot"
)
_AGE_COLL = os.getenv("MONGO_AGE_COLLECTION") or "roni_age_verifications"
_JSON_PATH = os.getenv("RONI_AGE_STORE_PATH", "data/roni_age_verifications.json")

# ────────────── RoniPortalTextStore (Mongo with JSON fallback) ──────────────

class RoniPortalTextStore:
    """
    Stores Roni portal texts by key: menu, open_access, teaser, announce.

    Mongo doc shape:
      { "_id": key, "text": str, "updated_at": iso str }

    JSON fallback shape:
      { key: text, ... }
    """

    def __init__(self, json_path: str):
        self._lock = threading.RLock()
        self._json_path = json_path
        self._use_mongo = False
        self._cache: Dict[str, str] = {}

        if _MONGO_URL:
            try:
                from pymongo import MongoClient

                self._mc = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=3000)
                self._mc.admin.command("ping")
                self._col = self._mc[_MONGO_DB]["roni_portal_texts"]
                self._use_mongo = True
                log.info(
                    "RoniPortalTextStore: Mongo OK db=%s coll=%s",
                    _MONGO_DB,
                    "roni_portal_texts",
                )
            except Exception as e:
                log.warning(
                    "RoniPortalTextStore: Mongo unavailable, falling back to JSON: %s",
                    e,
                )
                self._use_mongo = False

        if not self._use_mongo:
            self._load_json()

    # ---- JSON helpers ----

    def _load_json(self) -> None:
        try:
            with open(self._json_path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except FileNotFoundError:
            self._cache = {}
        except Exception as e:
            log.warning("RoniPortalTextStore: failed to load JSON: %s", e)
            self._cache = {}

    def _save_json(self) -> None:
        tmp_path = self._json_path + ".tmp"
        os.makedirs(os.path.dirname(self._json_path) or ".", exist_ok=True)
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._json_path)
        except Exception as e:
            log.warning("RoniPortalTextStore: failed to save JSON: %s", e)

    # ---- Public API ----

    def get(self, key: str, fallback: str) -> str:
        with self._lock:
            if self._use_mongo:
                try:
                    doc = self._col.find_one({"_id": key})
                    if doc and isinstance(doc.get("text"), str):
                        return doc["text"]
                except Exception as e:
                    log.warning("RoniPortalTextStore Mongo get failed: %s", e)

            # JSON / fallback
            val = self._cache.get(key)
            return val if isinstance(val, str) and val.strip() else fallback

    def set(self, key: str, text: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._lock:
            if self._use_mongo:
                try:
                    self._col.update_one(
                        {"_id": key},
                        {"$set": {"text": text, "updated_at": now}},
                        upsert=True,
                    )
                    return
                except Exception as e:
                    log.warning("RoniPortalTextStore Mongo set failed: %s", e)
                    # fall through to JSON

            self._cache[key] = text
            self._save_json()


roni_text_store = RoniPortalTextStore(_RONI_TEXT_PATH)

def _get_portal_text(key: str, fallback: str) -> str:
    return roni_text_store.get(key, fallback)

def _set_portal_text(key: str, text: str) -> None:
    roni_text_store.set(key, text)


# ────────────── AgeVerifyStore (Mongo or JSON) ──────────────

class AgeVerifyStore:
    """
    Stores age-verification results per user.

    Record shape (both Mongo + JSON):
    {
        "_id": int user_id,
        "username": str | None,
        "status": "pending" | "approved" | "denied" | "more_info",
        "first_seen": iso str,
        "last_update": iso str,
        "approved_at": iso str | None,
        "note": str | None,
        "media_chat_id": int,
        "media_message_id": int
    }
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._use_mongo = False
        self._cache: Dict[str, Dict[str, Any]] = {}

        if _MONGO_URL:
            try:
                from pymongo import MongoClient

                self._mc = MongoClient(_MONGO_URL, serverSelectionTimeoutMS=3000)
                self._mc.admin.command("ping")
                self._col = self._mc[_MONGO_DB][_AGE_COLL]
                self._col.create_index("status")
                self._use_mongo = True
                log.info(
                    "AgeVerifyStore: Mongo OK db=%s coll=%s", _MONGO_DB, _AGE_COLL
                )
            except Exception as e:
                log.warning(
                    "AgeVerifyStore: Mongo unavailable, falling back to JSON: %s", e
                )
                self._use_mongo = False

        if not self._use_mongo:
            self._load_json()

    # ---- JSON helpers ----

    def _load_json(self) -> None:
        try:
            with open(_JSON_PATH, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except FileNotFoundError:
            self._cache = {}
        except Exception as e:
            log.warning("AgeVerifyStore: failed to load JSON: %s", e)
            self._cache = {}

    def _save_json(self) -> None:
        tmp_path = _JSON_PATH + ".tmp"
        os.makedirs(os.path.dirname(_JSON_PATH) or ".", exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _JSON_PATH)

    # ---- Public API ----

    def upsert(self, user_id: int, **fields: Any) -> None:
        uid = str(user_id)
        now = datetime.utcnow().isoformat(timespec="seconds")

        with self._lock:
            if self._use_mongo:
                from pymongo.errors import PyMongoError
                try:
                    update: Dict[str, Any] = {"$set": {**fields, "last_update": now}}
                    update.setdefault("$setOnInsert", {})["first_seen"] = now
                    self._col.update_one({"_id": user_id}, update, upsert=True)
                    return
                except PyMongoError as e:
                    log.warning("AgeVerifyStore Mongo upsert failed, ignoring: %s", e)
                    # fall back into JSON cache

            rec = self._cache.get(uid, {})
            if "first_seen" not in rec:
                rec["first_seen"] = now
            rec.update(fields)
            rec["last_update"] = now
            self._cache[uid] = rec
            self._save_json()

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        uid = str(user_id)
        with self._lock:
            if self._use_mongo:
                try:
                    return self._col.find_one({"_id": user_id})
                except Exception as e:
                    log.warning("AgeVerifyStore Mongo get failed: %s", e)
            rec = self._cache.get(uid)
            if rec is not None:
                rec = {**rec, "_id": int(uid)}
            return rec

    def list(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            if self._use_mongo:
                try:
                    query: Dict[str, Any] = {}
                    if status:
                        query["status"] = status
                    cur = (
                        self._col.find(query)
                        .sort("last_update", -1)
                        .limit(int(limit))
                    )
                    return list(cur)
                except Exception as e:
                    log.warning("AgeVerifyStore Mongo list failed: %s", e)

            vals = []
            for uid, rec in self._cache.items():
                rec_with_id = {**rec, "_id": int(uid)}
                vals.append(rec_with_id)

            if status:
                vals = [v for v in vals if v.get("status") == status]

            vals.sort(
                key=lambda r: r.get("last_update")
                or r.get("first_seen")
                or "",
                reverse=True,
            )
            return vals[:limit]


age_store = AgeVerifyStore()

# Users who have tapped "Age Verify"
PENDING_AGE_MEDIA: Dict[int, bool] = {}

# Admin edit state
# admin_id -> {"kind": "menu"|"open_access"|"announce"|"teaser"|"note", "user_id"?: int}
ADMIN_EDIT_STATE: Dict[int, Dict[str, Any]] = {}


# ────────────── Helper functions / keyboards ──────────────

def _is_verified(user_id: int) -> bool:
    rec = age_store.get(user_id)
    return bool(rec and rec.get("status") == "approved")


def _roni_main_keyboard(*, is_owner: bool, verified: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")],
        [InlineKeyboardButton("💌 Book Roni", url=f"https://t.me/{RONI_USERNAME}")],
        [InlineKeyboardButton("💸 Pay / Tip Roni", callback_data="roni_portal:todo")],
        [InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:open")],
        [InlineKeyboardButton("📣 Announcements & Promos", callback_data="roni_portal:announce")],
    ]

    if not verified:
        rows.append(
            [InlineKeyboardButton("✅ Age Verify", callback_data="roni_portal:age")]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    "🔥 Teaser & Promo Channels",
                    callback_data="roni_portal:teaser",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "😈 Models & Creators — Tap Here",
                url=f"https://t.me/{RONI_USERNAME}",
            )
        ]
    )

    if is_owner:
        rows.append(
            [InlineKeyboardButton("⚙️ Roni Admin", callback_data="roni_portal:admin")]
        )

    # No "Back to SuccuBot" here – this menu is just for your personal portal
    return InlineKeyboardMarkup(rows)


def _roni_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 Edit Roni Menu", callback_data="roni_portal:admin_edit_menu")],
            [InlineKeyboardButton("🌸 Edit Open Access Text", callback_data="roni_portal:admin_edit_open")],
            [InlineKeyboardButton("📣 Edit Announcements & Promos", callback_data="roni_portal:admin_edit_announce")],
            [InlineKeyboardButton("🔥 Edit Teaser Text", callback_data="roni_portal:admin_edit_teaser")],
            [InlineKeyboardButton("✅ Age-Verified List", callback_data="roni_portal:admin_age_list")],
            [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home_owner")],
        ]
    )


# ────────────── Main register() ──────────────

def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal registered")

    # ───────── /roni_portal in your welcome channel ─────────
    @app.on_message(filters.command("roni_portal"))
    async def roni_portal_command(_, m: Message):
        start_link = f"https://t.me/{BOT_USERNAME}?start=roni_assistant"

        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💗 Open Roni’s Assistant", url=start_link)]]
        )

        await m.reply_text(
            "Welcome to Roni’s personal access channel.\n"
            "Click the button below to use her personal assistant SuccuBot for booking, payments, and more. 💋",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ───────── /start roni_assistant in private chat ─────────
    @app.on_message(filters.private & filters.command("start"), group=-1)
    async def roni_assistant_entry(_, m: Message):
        if not m.text:
            return

        parts = m.text.split(maxsplit=1)
        param = parts[1].strip() if len(parts) > 1 else ""

        if not param or not param.lower().startswith("roni_assistant"):
            return  # let normal /start handler run

        try:
            m.stop_propagation()
        except Exception:
            pass

        u = m.from_user
        user_id = u.id if u else 0
        is_owner = user_id == OWNER_ID
        verified = _is_verified(user_id)

        kb = _roni_main_keyboard(is_owner=is_owner, verified=verified)

        await m.reply_text(
            "Hi cutie, I’m SuccuBot — Roni’s personal assistant. 💗\n"
            "Use the buttons below to explore her menu, booking options, and more.\n"
            "Some features are still being built, so you might see “coming soon” for now. 💕",
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ───────── Navigation: home from callbacks ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:home_owner$"))
    async def roni_home_owner_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else 0
        kb = _roni_main_keyboard(
            is_owner=(user_id == OWNER_ID),
            verified=_is_verified(user_id),
        )
        await cq.message.edit_text(
            "Welcome to Roni’s personal assistant. 💗\n"
            "Use the buttons below to explore her menu, booking options, and more.",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:home$"))
    async def roni_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else 0
        kb = _roni_main_keyboard(
            is_owner=(user_id == OWNER_ID),
            verified=_is_verified(user_id),
        )
        await cq.message.edit_text(
            "Welcome to Roni’s personal assistant. 💗",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── Roni Menu view ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:menu$"))
    async def roni_menu_cb(_, cq: CallbackQuery):
        text = _get_portal_text(
            RONI_MENU_KEY,
            "Roni hasn’t set up her personal menu yet.\n"
            "She can do it from the ⚙ Roni Admin button. 💕",
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")],
            ]
        )
        await cq.message.edit_text(
            f"📖 <b>Roni’s Menu</b>\n\n{text}",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── Open Access / Announcements / Teaser views ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:open$"))
    async def open_access_cb(_, cq: CallbackQuery):
        text = _get_portal_text(
            OPEN_ACCESS_KEY,
            "Roni hasn’t added her open-access info yet. 💕",
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]]
        )
        await cq.message.edit_text(
            f"🌸 <b>Open Access</b>\n\n{text}",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:announce$"))
    async def announce_cb(_, cq: CallbackQuery):
        text = _get_portal_text(
            ANNOUNCE_KEY,
            "Roni hasn’t posted any announcements or promos yet. 💕",
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]]
        )
        await cq.message.edit_text(
            f"📣 <b>Announcements & Promos</b>\n\n{text}",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:teaser$"))
    async def teaser_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else 0
        if not _is_verified(user_id):
            await cq.answer(
                "You’ll unlock the teaser & promo channels after age verification. 💕",
                show_alert=True,
            )
            return

        text = _get_portal_text(
            TEASER_KEY,
            "Roni hasn’t added her teaser / promo channel list yet. 💕",
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]]
        )
        await cq.message.edit_text(
            f"🔥 <b>Teaser & Promo Channels</b>\n\n{text}",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ───────── Admin panel ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:admin$"))
    async def admin_panel_cb(_, cq: CallbackQuery):
        if (cq.from_user is None) or (cq.from_user.id != OWNER_ID):
            await cq.answer("Admin only 💕", show_alert=True)
            return

        await cq.message.edit_text(
            "⚙ <b>Roni Admin Panel</b>\n"
            "Use the buttons below to edit your assistant texts and age-verification info.",
            reply_markup=_roni_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ---- Admin: edit menu / open access / announcements / teaser ----

    async def _start_admin_edit(kind: str, text: str, cq: CallbackQuery):
        ADMIN_EDIT_STATE[OWNER_ID] = {"kind": kind}
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:admin_cancel")]]
        )
        await cq.message.edit_text(
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_edit_menu$"))
    async def admin_edit_menu_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return
        await _start_admin_edit(
            "menu",
            "📖 Send me your new Roni Menu text in one message.\n\n"
            "I’ll save it and your assistant will show it under “📖 Roni’s Menu”.",
            cq,
        )

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_edit_open$"))
    async def admin_edit_open_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return
        await _start_admin_edit(
            "open_access",
            "🌸 Send me the text you want to show for Open Access.\n\n"
            "This is what people see even before they age-verify.",
            cq,
        )

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_edit_announce$"))
    async def admin_edit_announce_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return
        await _start_admin_edit(
            "announce",
            "📣 Send me the text you want to show under Announcements & Promos.\n\n"
            "Use this for important info, current promos, limited-time offers, etc.",
            cq,
        )

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_edit_teaser$"))
    async def admin_edit_teaser_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return
        await _start_admin_edit(
            "teaser",
            "🔥 Send me the text that should show under Teaser & Promo Channels "
            "(for verified users only).",
            cq,
        )

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_cancel$"))
    async def admin_cancel_cb(_, cq: CallbackQuery):
        ADMIN_EDIT_STATE.pop(OWNER_ID, None)
        await cq.answer("Cancelled.", show_alert=False)
        await cq.message.edit_text(
            "⚙ <b>Roni Admin Panel</b>",
            reply_markup=_roni_admin_keyboard(),
            disable_web_page_preview=True,
        )

    # Save admin text edits (menu / open / announcements / teaser / note)
    @app.on_message(filters.private & filters.user(OWNER_ID), group=-1)
    async def admin_text_handler(_, m: Message):
        if not m.text:
            return

        state = ADMIN_EDIT_STATE.pop(OWNER_ID, None)
        if not state:
            # No active edit – ignore, this is just a normal DM from you
            return

        kind = state.get("kind")
        text = m.text.strip()

        if kind == "menu":
            _set_portal_text(RONI_MENU_KEY, text)
            await m.reply_text(
                "📖 Saved your personal menu for Roni’s assistant. 💕",
                reply_markup=_roni_admin_keyboard(),
            )
        elif kind == "open_access":
            _set_portal_text(OPEN_ACCESS_KEY, text)
            await m.reply_text(
                "🌸 Saved your Open Access text. 💕",
                reply_markup=_roni_admin_keyboard(),
            )
        elif kind == "announce":
            _set_portal_text(ANNOUNCE_KEY, text)
            await m.reply_text(
                "📣 Saved your Announcements & Promos text. 💕",
                reply_markup=_roni_admin_keyboard(),
            )
        elif kind == "teaser":
            _set_portal_text(TEASER_KEY, text)
            await m.reply_text(
                "🔥 Saved your Teaser & Promo text. 💕",
                reply_markup=_roni_admin_keyboard(),
            )
        elif kind == "note":
            target_id = state.get("user_id")
            if not target_id:
                await m.reply_text(
                    "Couldn’t find which user this note was for.",
                    reply_markup=_roni_admin_keyboard(),
                )
                return
            age_store.upsert(int(target_id), note=text)
            await m.reply_text(
                f"📝 Saved note for user <code>{target_id}</code>.",
                reply_markup=_roni_admin_keyboard(),
            )

    # ───────── Age Verification: user side ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def age_start_cb(_, cq: CallbackQuery):
        u = cq.from_user
        if not u:
            await cq.answer()
            return

        PENDING_AGE_MEDIA[u.id] = True

        await cq.message.edit_text(
            "💜 Age Check Time 💜\n\n"
            "Please send a clear photo of yourself **right here** doing one of these:\n"
            "• Touching your nose with a fork\n"
            "• Or touching your nose with your pinky\n\n"
            "If you look super fresh-faced, Roni may ask for a selfie with your ID "
            "(only name, birthday, and face visible — nothing else).\n\n"
            "Once you send it, I’ll forward it to Roni for approval. 💕",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Handle media sent after tapping Age Verify OR when status = more_info
    @app.on_message(
        filters.private
        & ~filters.user(OWNER_ID)
        & (filters.photo | filters.video | filters.document | filters.animation | filters.sticker)
    )
    async def handle_age_media(_, m: Message):
        u = m.from_user
        if not u:
            return

        # Was this explicitly started via Age Verify button?
        pending_flag = PENDING_AGE_MEDIA.pop(u.id, False)

        # Or are they in "more_info" state and sending the extra photo?
        rec = age_store.get(u.id)
        more_info = bool(rec and rec.get("status") == "more_info")

        if not pending_flag and not more_info:
            # Not in any age-verify flow; ignore
            return

        # Forward media to Roni
        fwd = await m.forward(OWNER_ID)

        # Store/update record as pending review again
        age_store.upsert(
            u.id,
            username=u.username,
            status="pending",
            media_chat_id=fwd.chat.id,
            media_message_id=fwd.id,
        )

        # Create review card for Roni
        review_text = (
            "✉️ <b>Age Verification Received</b>\n\n"
            f"From: @{u.username or 'no_username'}\n"
            f"User ID: <code>{u.id}</code>\n\n"
            "Their media is forwarded above. Review it and choose an action:"
        )
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Approve", callback_data=f"roni_portal:age_approve:{u.id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🪪 Need more info",
                        callback_data=f"roni_portal:age_moreinfo:{u.id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⛔ Deny", callback_data=f"roni_portal:age_deny:{u.id}"
                    )
                ],
            ]
        )
        await app.send_message(
            OWNER_ID,
            review_text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

        # Let user know it’s pending
        await m.reply_text(
            "💜 Thanks! I’ve sent that to Roni to review.\n"
            "You’ll get a message once you’re approved (or if she needs more info).",
        )

    # ───────── Age Verification: Roni actions ─────────

    async def _close_review_card(cq: CallbackQuery, status_line: str):
        try:
            await cq.message.edit_text(
                cq.message.text + f"\n\n{status_line}",
                reply_markup=None,
                disable_web_page_preview=True,
            )
        except Exception:
            try:
                await cq.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

    async def _send_verified_menu(user_id: int):
        verified_kb = _roni_main_keyboard(
            is_owner=(user_id == OWNER_ID), verified=True
        )
        await app.send_message(
            user_id,
            "✅ You’re age-verified and all set!\n"
            "You now have access to Roni’s teaser & promo goodies. 💕",
            reply_markup=verified_kb,
        )

    @app.on_callback_query(filters.regex(r"^roni_portal:age_approve:(\d+)$"))
    async def age_approve_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return

        target_id = int(cq.data.split(":", 2)[-1])
        now = datetime.utcnow().isoformat(timespec="seconds")
        age_store.upsert(target_id, status="approved", approved_at=now)

        await _close_review_card(cq, f"✅ Approved at {now} (UTC)")
        await cq.answer("Approved ✅", show_alert=False)

        try:
            await _send_verified_menu(target_id)
        except Exception as e:
            log.warning("Failed to notify approved user %s: %s", target_id, e)

    @app.on_callback_query(filters.regex(r"^roni_portal:age_moreinfo:(\d+)$"))
    async def age_moreinfo_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return

        target_id = int(cq.data.split(":", 2)[-1])
        age_store.upsert(target_id, status="more_info")

        await _close_review_card(cq, "🪪 Marked as: needs more info.")
        await cq.answer("Marked as 'need more info'.", show_alert=False)

        try:
            await app.send_message(
                target_id,
                "🪪 Roni needs a little more info to verify you.\n"
                "Please send either:\n"
                "• A clearer nose-touch photo\n"
                "• Or a selfie with your ID (only your name + birthday visible).",
            )
        except Exception as e:
            log.warning("Failed to message user for more info %s: %s", target_id, e)

    @app.on_callback_query(filters.regex(r"^roni_portal:age_deny:(\d+)$"))
    async def age_deny_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return

        target_id = int(cq.data.split(":", 2)[-1])
        age_store.upsert(target_id, status="denied")

        await _close_review_card(cq, "⛔ Marked as denied.")
        await cq.answer("Denied ⛔", show_alert=False)

        try:
            await app.send_message(
                target_id,
                "⛔ Your age verification was not approved.\n"
                "If this is a mistake, you can reach out to Roni with more details.",
            )
        except Exception as e:
            log.warning("Failed to notify denied user %s: %s", target_id, e)

    # ───────── Admin: Age-verified list / media / notes / reset ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:admin_age_list$"))
    async def admin_age_list_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return

        recs = age_store.list(status="approved", limit=50)

        if not recs:
            text = "✅ No approved verifications yet."
            kb_rows: List[List[InlineKeyboardButton]] = [
                [InlineKeyboardButton("⬅ Back", callback_data="roni_portal:admin")]
            ]
        else:
            lines = ["✅ <b>Approved Verifications</b> (most recent first)\n"]
            buttons: List[List[InlineKeyboardButton]] = []

            for idx, rec in enumerate(recs):
                uid = rec.get("_id")
                uname = rec.get("username") or "no_username"
                approved_at = rec.get("approved_at") or rec.get("last_update")
                note_flag = " 📝" if rec.get("note") else ""
                lines.append(
                    f"• @{uname} — <code>{uid}</code> — {approved_at}{note_flag}"
                )

                if idx < 10:  # quick buttons for first few
                    label = f"@{uname}" if uname != "no_username" else str(uid)
                    buttons.append(
                        [
                            InlineKeyboardButton(
                                label,
                                callback_data=f"roni_portal:age_view:{uid}",
                            )
                        ]
                    )

            text = "\n".join(lines)
            buttons.append(
                [InlineKeyboardButton("⬅ Back", callback_data="roni_portal:admin")]
            )
            kb_rows = buttons

        await cq.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(kb_rows),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:age_view:(\d+)$"))
    async def admin_age_view_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return

        target_id = int(cq.data.split(":", 2)[-1])
        rec = age_store.get(target_id)
        if not rec:
            await cq.answer("No record found for that user.", show_alert=True)
            return

        media_chat_id = rec.get("media_chat_id")
        media_message_id = rec.get("media_message_id")
        if media_chat_id and media_message_id:
            try:
                await app.copy_message(
                    chat_id=OWNER_ID,
                    from_chat_id=media_chat_id,
                    message_id=media_message_id,
                )
            except Exception as e:
                log.warning("Failed to copy verification media: %s", e)

        uname = rec.get("username") or "no_username"
        note = rec.get("note") or "— none —"
        approved_at = rec.get("approved_at") or rec.get("last_update")
        first_seen = rec.get("first_seen")

        text = (
            f"🧾 <b>Verification Details</b>\n\n"
            f"User: @{uname}\n"
            f"ID: <code>{target_id}</code>\n"
            f"First seen: {first_seen}\n"
            f"Approved at: {approved_at}\n\n"
            f"Current note:\n<code>{note}</code>"
        )

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📝 Add / Edit Note",
                        callback_data=f"roni_portal:age_note:{target_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Remove Approval",
                        callback_data=f"roni_portal:age_reset:{target_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅ Back to List",
                        callback_data="roni_portal:admin_age_list",
                    )
                ],
            ]
        )
        await cq.message.edit_text(
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:age_note:(\d+)$"))
    async def admin_age_note_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return

        target_id = int(cq.data.split(":", 2)[-1])
        ADMIN_EDIT_STATE[OWNER_ID] = {"kind": "note", "user_id": target_id}

        await cq.message.edit_text(
            f"📝 Send the note you want to store for user <code>{target_id}</code> "
            "(one message).\n\n"
            "I’ll attach it to their verification record.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:admin_cancel")]]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:age_reset:(\d+)$"))
    async def admin_age_reset_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only 💕", show_alert=True)
            return

        target_id = int(cq.data.split(":", 2)[-1])

        age_store.upsert(target_id, status="pending", approved_at=None)

        await cq.answer("Approval removed. User is no longer marked verified.", show_alert=True)

        try:
            await cq.message.edit_text(
                cq.message.text + "\n\n❌ Approval removed. Status reset to pending.",
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        try:
            await app.send_message(
                target_id,
                "🔁 Your age verification status has been reset. "
                "You’ll need to verify again before seeing Roni’s teaser channels.",
            )
        except Exception as e:
            log.warning("Failed to notify reset user %s: %s", target_id, e)

    # ───────── Placeholder for not-yet-wired buttons ─────────
    @app.on_callback_query(filters.regex(r"^roni_portal:todo$"))
    async def roni_todo_cb(_, cq: CallbackQuery):
        await cq.answer("This feature is coming soon 💕", show_alert=True)
