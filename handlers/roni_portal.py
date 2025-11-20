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

from utils.menu_store import store  # harmless even if not used much

log = logging.getLogger(__name__)

# ────────────── ENV / CONSTANTS ──────────────

BOT_USERNAME = (os.getenv("BOT_USERNAME") or "succubot_bot").lstrip("@")
RONI_USERNAME = (os.getenv("RONI_USERNAME") or "Chaossub283").lstrip("@")

# Same tip link env as panels.py
RONI_TIP_LINK = (os.getenv("TIP_RONI_LINK") or "").strip()

# Your personal Telegram user ID – only you see admin controls
OWNER_ID = int(os.getenv("RONI_OWNER_ID") or os.getenv("OWNER_ID", "6964994611"))

# Keys for Roni portal text sections
RONI_MENU_KEY   = "menu"
OPEN_ACCESS_KEY = "open_access"
TEASER_KEY      = "teaser"
ANNOUNCE_KEY    = "announce"

# JSON file for editable text fallback
_RONI_TEXT_PATH = os.getenv("RONI_PORTAL_TEXT_PATH", "data/roni_portal_texts.json")

# Mongo / JSON for age verify
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
    Stores Roni portal texts by key:
      menu, open_access, teaser, announce
    Mongo doc: { "_id": key, "text": str, "updated_at": iso }
    JSON fallback: { key: text }
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
    Stores age-verification per user.

    record:
    {
        "_id": user_id,
        "username": str|None,
        "status": "pending"|"approved"|"denied"|"more_info",
        "first_seen": iso,
        "last_update": iso,
        "approved_at": iso|None,
        "note": str|None,
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
                try:
                    update: Dict[str, Any] = {"$set": {**fields, "last_update": now}}
                    update.setdefault("$setOnInsert", {})["first_seen"] = now
                    self._col.update_one({"_id": user_id}, update, upsert=True)
                    return
                except Exception as e:
                    log.warning("AgeVerifyStore Mongo upsert failed: %s", e)

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

# track who is currently sending age media
PENDING_AGE_MEDIA: Dict[int, bool] = {}

# admin edit state:
#   admin_id -> {"kind": one of menu/open/announce/teaser}
ADMIN_EDIT_STATE: Dict[int, Dict[str, Any]] = {}

# age verification note state:
#   admin_id -> target_user_id
AGE_NOTE_STATE: Dict[int, int] = {}


# ────────────── Helpers / keyboards ──────────────

def _is_verified(user_id: int) -> bool:
    rec = age_store.get(user_id)
    return bool(rec and rec.get("status") == "approved")


def _roni_main_keyboard(*, is_owner: bool, verified: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")],
        [InlineKeyboardButton("💌 Book Roni", url=f"https://t.me/{RONI_USERNAME}")],
    ]

    # Tip button logic – mirror panels.py behavior
    if RONI_TIP_LINK:
        rows.append(
            [InlineKeyboardButton("💸 Pay / Tip Roni", url=RONI_TIP_LINK)]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    "💸 Pay / Tip Roni (coming soon)",
                    callback_data="roni_portal:tip_coming",
                )
            ]
        )

    rows.append([InlineKeyboardButton("🌸 Open Access", callback_data="roni_portal:open")])
    rows.append([InlineKeyboardButton("📣 Announcements & Promos", callback_data="roni_portal:announce")])

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

    # no “Back to SuccuBot Menu” here – this portal is just for Roni
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


def _welcome_text(verified: bool) -> str:
    """
    NEW copy for the assistant welcome, with different text depending
    on whether the user is age-verified already.
    """
    if verified:
        # already age verified
        return (
            "Hi cutie, I’m SuccuBot — Roni’s personal assistant. 💗\n"
            "You’re already age verified, so feel free to dive in and enjoy everything Roni offers.\n"
            "Use the buttons below to explore her menu, previews, and promos — and you can DM her directly any time with “💌 Book Roni”. 😈💌"
        )
    else:
        # not yet verified
        return (
            "Hi cutie, I’m SuccuBot — Roni’s personal assistant. 💗\n"
            "Use the buttons below to explore her menu, booking options, and more.\n"
            "You can also DM Roni directly any time by tapping “💌 Book Roni”.\n\n"
            "Before we go too far, you’ll need to Age Verify so Roni can keep her space 18+ only.\n"
            "Once you’re verified, you’ll unlock her teaser & promo channels. 💕"
        )


# ────────────── register(app) ──────────────

def register(app: Client) -> None:
    log.info("✅ handlers.roni_portal registered")

    # ── /roni_portal in your welcome channel (creates deep-link to assistant mode)
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

    # ── /start roni_assistant in private chat (assistant mode)
    @app.on_message(filters.private & filters.command("start"), group=-1)
    async def roni_assistant_entry(_, m: Message):
        if not m.text:
            return
        parts = m.text.split(maxsplit=1)
        param = parts[1].strip() if len(parts) > 1 else ""
        if not param or not param.lower().startswith("roni_assistant"):
            return

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
            _welcome_text(verified),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ── navigation back to home
    @app.on_callback_query(filters.regex(r"^roni_portal:home_owner$"))
    async def roni_home_owner_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else 0
        verified = _is_verified(user_id)
        kb = _roni_main_keyboard(is_owner=(user_id == OWNER_ID), verified=verified)
        await cq.message.edit_text(
            _welcome_text(verified),
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:home$"))
    async def roni_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id if cq.from_user else 0
        verified = _is_verified(user_id)
        kb = _roni_main_keyboard(is_owner=(user_id == OWNER_ID), verified=verified)
        await cq.message.edit_text(
            _welcome_text(verified),
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ── Roni menu / open access / announcements / teaser views
    @app.on_callback_query(filters.regex(r"^roni_portal:menu$"))
    async def roni_menu_cb(_, cq: CallbackQuery):
        text = _get_portal_text(
            RONI_MENU_KEY,
            "Roni hasn’t set up her personal menu yet.\n"
            "She can do it from the ⚙ Roni Admin button. 💕",
        )
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅ Back to Roni Assistant", callback_data="roni_portal:home")]]
        )
        await cq.message.edit_text(
            f"📖 <b>Roni’s Menu</b>\n\n{text}",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

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

    # ── Tip coming soon fallback (only used if no TIP_RONI_LINK is set)
    @app.on_callback_query(filters.regex(r"^roni_portal:tip_coming$"))
    async def roni_tip_coming_cb(_, cq: CallbackQuery):
        await cq.answer("💸 Tip support is coming soon!", show_alert=True)

    # ── Roni Admin entry
    @app.on_callback_query(filters.regex(r"^roni_portal:admin$"))
    async def roni_admin_cb(_, cq: CallbackQuery):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin-only. 💕", show_alert=True)
            return
        ADMIN_EDIT_STATE.pop(OWNER_ID, None)
        await cq.message.edit_text(
            "⚙️ <b>Roni Admin Panel</b>\nChoose what you want to edit or review.",
            reply_markup=_roni_admin_keyboard(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ── Admin edit flows (menu / open / announce / teaser)
    async def _start_admin_edit(cq: CallbackQuery, kind: str, label: str):
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin-only. 💕", show_alert=True)
            return
        ADMIN_EDIT_STATE[OWNER_ID] = {"kind": kind}
        await cq.message.edit_text(
            f"✏️ Send the new text for <b>{label}</b> in one message.\n\n"
            "When you’re done, I’ll save it and update the button.",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancel", callback_data="roni_portal:admin_cancel")]]
            ),
        )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_edit_menu$"))
    async def admin_edit_menu_cb(_, cq: CallbackQuery):
        await _start_admin_edit(cq, "menu", "Roni’s Menu")

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_edit_open$"))
    async def admin_edit_open_cb(_, cq: CallbackQuery):
        await _start_admin_edit(cq, "open_access", "Open Access")

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_edit_announce$"))
    async def admin_edit_announce_cb(_, cq: CallbackQuery):
        await _start_admin_edit(cq, "announce", "Announcements & Promos")

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_edit_teaser$"))
    async def admin_edit_teaser_cb(_, cq: CallbackQuery):
        await _start_admin_edit(cq, "teaser", "Teaser & Promo Channels")

    @app.on_callback_query(filters.regex(r"^roni_portal:admin_cancel$"))
    async def admin_cancel_cb(_, cq: CallbackQuery):
        if cq.from_user.id == OWNER_ID:
            ADMIN_EDIT_STATE.pop(OWNER_ID, None)
        await cq.answer("Canceled.", show_alert=False)
        await roni_home_owner_cb(_, cq)

    # receive text from you while in admin edit mode OR note mode
    @app.on_message(filters.private & filters.text)
    async def admin_text_router(_, m: Message):
        if m.from_user.id != OWNER_ID:
            return

        # Note flow first
        target_user_id = AGE_NOTE_STATE.get(m.from_user.id)
        if target_user_id:
            note_text = m.text.strip()
            if not note_text:
                await m.reply_text("That message was empty, send your note again. 💕")
                return

            age_store.upsert(int(target_user_id), note=note_text)
            AGE_NOTE_STATE.pop(m.from_user.id, None)

            await m.reply_text(
                f"✅ Saved note for user <code>{target_user_id}</code>.\n"
                "This will be stored with their age verification record.",
                disable_web_page_preview=True,
                parse_mode="html",
            )
            return

        # Admin edit text flow
        state = ADMIN_EDIT_STATE.get(OWNER_ID)
        if not state:
            return

        kind = state.get("kind")
        txt = m.text.strip()
        if not txt:
            await m.reply_text("That message was empty, send your new text again. 💕")
            return

        if kind == "menu":
            _set_portal_text(RONI_MENU_KEY, txt)
            label = "Roni’s Menu"
        elif kind == "open_access":
            _set_portal_text(OPEN_ACCESS_KEY, txt)
            label = "Open Access"
        elif kind == "announce":
            _set_portal_text(ANNOUNCE_KEY, txt)
            label = "Announcements & Promos"
        elif kind == "teaser":
            _set_portal_text(TEASER_KEY, txt)
            label = "Teaser & Promo Channels"
        else:
            return

        ADMIN_EDIT_STATE.pop(OWNER_ID, None)
        await m.reply_text(
            f"✅ Saved your new text for <b>{label}</b> and updated the button.\n"
            "This will survive restarts. 💕",
            disable_web_page_preview=True,
        )

    # ── Age Verify: user taps button
    @app.on_callback_query(filters.regex(r"^roni_portal:age$"))
    async def age_verify_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        PENDING_AGE_MEDIA[user_id] = True

        txt = (
            "🧾 <b>Age Verification</b>\n\n"
            "Please send a clear photo of you touching your nose with a fork, "
            "or with your pinky or thumb.\n\n"
            "If you look extra fresh-faced, Roni may ask for a second picture "
            "showing your face next to your ID (only your name and birthday need to be visible).\n\n"
            "No minors. No exceptions. 💅"
        )
        await cq.message.edit_text(
            txt,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅ Back", callback_data="roni_portal:home")]]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer("Send your verification photo here. 💕")

    # ── Age Verify: user sends media while pending
    @app.on_message(filters.private & (filters.photo | filters.video | filters.animation))
    async def handle_age_media(_, m: Message):
        user = m.from_user
        if not user:
            return
        user_id = user.id
        if not PENDING_AGE_MEDIA.get(user_id):
            return

        PENDING_AGE_MEDIA.pop(user_id, None)

        # forward to you
        fwd = await m.forward(OWNER_ID)
        username = f"@{user.username}" if user.username else "(no @username)"

        age_store.upsert(
            user_id,
            username=user.username,
            status="pending",
            media_chat_id=fwd.chat.id,
            media_message_id=fwd.id,
            approved_at=None,
        )

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Approve", callback_data=f"roni_portal:age_approve:{user_id}")],
                [InlineKeyboardButton("🪪 Need more info", callback_data=f"roni_portal:age_more:{user_id}")],
                [InlineKeyboardButton("⛔ Deny", callback_data=f"roni_portal:age_deny:{user_id}")],
                [InlineKeyboardButton("📝 Add / Edit Note", callback_data=f"roni_portal:age_note:{user_id}")],
                [InlineKeyboardButton("🔄 Remove AV Status", callback_data=f"roni_portal:age_remove:{user_id}")],
            ]
        )

        await app.send_message(
            OWNER_ID,
            (
                "📩 <b>Age Verification Received</b>\n\n"
                f"From: {username}\n"
                f"User ID: <code>{user_id}</code>\n\n"
                "Their media is forwarded above. Review it and choose an action:"
            ),
            reply_markup=kb,
            disable_web_page_preview=True,
        )

        await m.reply_text(
            "💕 Thanks! Roni will review your verification and get back to you soon.",
            disable_web_page_preview=True,
        )

    # helpers for admin decisions
    async def _ensure_owner(cq: CallbackQuery) -> bool:
        if cq.from_user.id != OWNER_ID:
            await cq.answer("Admin-only. 💕", show_alert=True)
            return False
        return True

    async def _age_decision_header(user_id: int, decision: str) -> str:
        rec = age_store.get(user_id)
        uname = rec.get("username") if rec else None
        uname = f"@{uname}" if uname else "(no @username)"
        return f"{decision} for {uname} (ID: <code>{user_id}</code>)."

    @app.on_callback_query(filters.regex(r"^roni_portal:age_approve:(\d+)$"))
    async def age_approve_cb(_, cq: CallbackQuery):
        if not await _ensure_owner(cq):
            return
        user_id = int(cq.data.split(":")[-1])
        age_store.upsert(
            user_id,
            status="approved",
            approved_at=datetime.utcnow().isoformat(timespec="seconds"),
        )

        # notify user
        try:
            await app.send_message(
                user_id,
                "✅ You’re age-verified for Roni’s assistant.\n"
                "You now have access to her teaser & promo channels whenever she shares them. 💕",
            )
        except Exception:
            pass

        # update admin message & close buttons
        try:
            await cq.message.edit_text(
                "✅ Age verification approved.\n"
                f"{await _age_decision_header(user_id, 'Approved')}",
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer("Approved. 💕")

    @app.on_callback_query(filters.regex(r"^roni_portal:age_deny:(\d+)$"))
    async def age_deny_cb(_, cq: CallbackQuery):
        if not await _ensure_owner(cq):
            return
        user_id = int(cq.data.split(":")[-1])
        age_store.upsert(user_id, status="denied", approved_at=None)

        try:
            await app.send_message(
                user_id,
                "⛔ Your age verification was not approved.\n"
                "If this is a mistake, you can contact Roni and ask if she’s open to reviewing again.",
            )
        except Exception:
            pass

        try:
            await cq.message.edit_text(
                "⛔ Age verification denied.\n"
                f"{await _age_decision_header(user_id, 'Denied')}",
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer("Denied.", show_alert=False)

    @app.on_callback_query(filters.regex(r"^roni_portal:age_more:(\d+)$"))
    async def age_more_info_cb(_, cq: CallbackQuery):
        if not await _ensure_owner(cq):
            return
        user_id = int(cq.data.split(":")[-1])
        age_store.upsert(user_id, status="more_info")

        # message user asking for more info
        try:
            await app.send_message(
                user_id,
                "🪪 Roni needs a little more info to verify you.\n\n"
                "Please send a selfie holding your ID next to your face.\n"
                "Only your <b>name</b> and <b>birthday</b> need to be visible.\n\n"
                "You can send it here, and I’ll forward it to her.",
            )
        except Exception:
            pass

        try:
            await cq.message.edit_text(
                "🪪 Marked as 'Need more info'.\n"
                f"{await _age_decision_header(user_id, 'More info requested')}",
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer("Asked them for more info. 💕")

    # ── Admin: Remove age-verified status explicitly
    @app.on_callback_query(filters.regex(r"^roni_portal:age_remove:(\d+)$"))
    async def age_remove_cb(_, cq: CallbackQuery):
        if not await _ensure_owner(cq):
            return
        user_id = int(cq.data.split(":")[-1])

        # Set them to denied and clear approved_at
        age_store.upsert(user_id, status="denied", approved_at=None)

        # Optionally notify user their access has been revoked
        try:
            await app.send_message(
                user_id,
                "⚠️ Your age-verified access to Roni’s assistant has been removed.\n"
                "If you think this is a mistake, you can message Roni directly.",
            )
        except Exception:
            pass

        try:
            await cq.message.edit_text(
                "🔄 Age-verified status removed for this user.\n"
                f"{await _age_decision_header(user_id, 'Access removed')}",
                disable_web_page_preview=True,
            )
        except Exception:
            pass

        await cq.answer("Age-verified status removed.", show_alert=False)

    # ── Admin: Add / Edit note for an age verification record
    @app.on_callback_query(filters.regex(r"^roni_portal:age_note:(\d+)$"))
    async def age_note_cb(_, cq: CallbackQuery):
        if not await _ensure_owner(cq):
            return
        user_id = int(cq.data.split(":")[-1])

        AGE_NOTE_STATE[cq.from_user.id] = user_id

        await cq.answer()
        await cq.message.reply_text(
            f"📝 Send the note you want to attach to this user.\n\n"
            f"Target ID: <code>{user_id}</code>\n\n"
            "Whatever you send next (in this chat) will be saved as their note.",
            disable_web_page_preview=True,
            parse_mode="html",
        )

    # ── Admin age-verified list
    @app.on_callback_query(filters.regex(r"^roni_portal:admin_age_list$"))
    async def admin_age_list_cb(_, cq: CallbackQuery):
        if not await _ensure_owner(cq):
            return

        recs = age_store.list(status="approved", limit=30)

        if not recs:
            txt = "No one is age-verified yet. 💕"
            kb = _roni_admin_keyboard()
        else:
            lines = ["✅ <b>Age-Verified Users</b> (latest 30)\n"]
            buttons: List[List[InlineKeyboardButton]] = []

            for r in recs:
                uid = r.get("_id")
                uname = r.get("username")
                uname_disp = f"@{uname}" if uname else "(no @username)"
                approved_at = r.get("approved_at") or r.get("last_update")
                note = r.get("note")

                if note:
                    short_note = note
                    if len(short_note) > 60:
                        short_note = short_note[:57] + "..."
                    lines.append(
                        f"• {uname_disp} — <code>{uid}</code> — {approved_at}\n"
                        f"  📝 {short_note}"
                    )
                else:
                    lines.append(
                        f"• {uname_disp} — <code>{uid}</code> — {approved_at}"
                    )

                # Up to 10 quick-select buttons for managing specific users
                if len(buttons) < 10 and uid is not None:
                    label = uname_disp if len(uname_disp) <= 25 else f"ID {uid}"
                    buttons.append(
                        [
                            InlineKeyboardButton(
                                label,
                                callback_data=f"roni_portal:age_manage:{uid}",
                            )
                        ]
                    )

            # Add back button at bottom
            buttons.append(
                [InlineKeyboardButton("⬅ Back to Admin", callback_data="roni_portal:admin")]
            )

            txt = "\n".join(lines)
            kb = InlineKeyboardMarkup(buttons)

        await cq.message.edit_text(
            txt,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ── Admin: manage a specific age-verified user from the list
    @app.on_callback_query(filters.regex(r"^roni_portal:age_manage:(\d+)$"))
    async def admin_age_manage_cb(_, cq: CallbackQuery):
        if not await _ensure_owner(cq):
            return
        user_id = int(cq.data.split(":")[-1])

        rec = age_store.get(user_id)
        if not rec:
            await cq.answer("No age-verification record found for this user.", show_alert=True)
            return

        uname = rec.get("username")
        uname_disp = f"@{uname}" if uname else "(no @username)"
        approved_at = rec.get("approved_at") or rec.get("last_update")
        note = rec.get("note")

        lines = [
            "✅ <b>Age-Verified User</b>",
            f"User: {uname_disp}",
            f"ID: <code>{user_id}</code>",
        ]
        if approved_at:
            lines.append(f"Approved at: {approved_at}")
        if note:
            if len(note) > 500:
                short_note = note[:500] + "…"
            else:
                short_note = note
            lines.append("\n📝 <b>Current note:</b>\n" + short_note)

        txt = "\n".join(lines)

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📝 Add / Edit Note", callback_data=f"roni_portal:age_note:{user_id}")],
                [InlineKeyboardButton("🔄 Remove AV Status", callback_data=f"roni_portal:age_remove:{user_id}")],
                [InlineKeyboardButton("⬅ Back to Age-Verified List", callback_data="roni_portal:admin_age_list")],
            ]
        )

        await cq.message.edit_text(
            txt,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()
