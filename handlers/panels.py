# handlers/panels.py
import os, time, re
from typing import Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
)
from pyrogram.errors import MessageNotModified, BadRequest
from pymongo import MongoClient

# ------------------ Mongo ------------------
MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
DB_NAME   = os.getenv("MONGO_DB") or os.getenv("MONGO_DBNAME") or "succubot"
if not MONGO_URL:
    raise RuntimeError("MONGO_URL / MONGODB_URI / MONGO_URI is required")
_mcli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
_db   = _mcli[DB_NAME]

col_model_menus = _db.get_collection("model_menus")   # stores each model menu (text+photo)
col_anon        = _db.get_collection("anon_sessions") # ephemeral flag for anon message flow

# ---------------- Owner/Admin + Model Auth ----------------
def _parse_ids(env_val: Optional[str]) -> List[int]:
    out: List[int] = []
    if not env_val:
        return out
    for token in env_val.replace(" ", "").split(","):
        if not token:
            continue
        try: out.append(int(token))
        except ValueError: pass
    return out

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
EXTRA_ADMIN_IDS: List[int] = _parse_ids(os.getenv("EXTRA_ADMIN_IDS") or os.getenv("SUPER_ADMINS"))

def _is_owner_or_admin(uid: Optional[int]) -> bool:
    return bool(uid) and (uid == OWNER_ID or uid in EXTRA_ADMIN_IDS)

def _int_or_zero(v: Optional[str]) -> int:
    try: return int(v) if v else 0
    except ValueError: return 0

# Models map for buttons + Book links + self-edit permissions
MODELS: Dict[str, Dict] = {
    "roni": {"name": os.getenv("MODEL_RONI_NAME", os.getenv("RONI_NAME", "Roni")),
             "username": os.getenv("RONI_USERNAME", ""),
             "uid": _int_or_zero(os.getenv("MODEL_RONI_ID") or os.getenv("RONI_ID"))},
    "ruby": {"name": os.getenv("MODEL_RUBY_NAME", os.getenv("RUBY_NAME", "Ruby")),
             "username": os.getenv("RUBY_USERNAME", ""),
             "uid": _int_or_zero(os.getenv("MODEL_RUBY_ID") or os.getenv("RUBY_ID"))},
    "rin":  {"name": os.getenv("MODEL_RIN_NAME",  os.getenv("RIN_NAME",  "Rin")),
             "username": os.getenv("RIN_USERNAME",  ""),
             "uid": _int_or_zero(os.getenv("MODEL_RIN_ID")  or os.getenv("RIN_ID"))},
    "savy": {"name": os.getenv("MODEL_SAVY_NAME", os.getenv("SAVY_NAME", "Savy")),
             "username": os.getenv("SAVY_USERNAME", ""),
             "uid": _int_or_zero(os.getenv("MODEL_SAVY_ID") or os.getenv("SAVY_ID"))},
}

# ---------------- Small helpers ----------------
def _tg_url(username: str) -> str:
    return f"https://t.me/{username}" if username else "https://t.me/"

def _model_key_from_name(name: str) -> Optional[str]:
    k = (name or "").strip().lower()
    if k in MODELS:
        return k
    for key, meta in MODELS.items():
        if meta["name"].lower() == k:
            return key
    return None

def _extract_text_after_command(m: Message) -> str:
    if m.caption and m.caption.strip():
        parts = m.caption.split(maxsplit=2)
        if len(parts) >= 3:
            return parts[2]
        return ""
    if m.text:
        parts = m.text.split(maxsplit=2)
        if len(parts) >= 3:
            return parts[2]
    return ""

async def _safe_edit(msg: Message, text: str, **kwargs):
    try:
        return await msg.edit_text(text, **kwargs)
    except MessageNotModified:
        if "reply_markup" in kwargs and kwargs["reply_markup"] is not None:
            try:
                return await msg.edit_reply_markup(kwargs["reply_markup"])
            except MessageNotModified:
                return
        return
    except BadRequest:
        return await msg.reply_text(text, **kwargs)

# ---------------- Keyboards ----------------
def _menus_kb() -> InlineKeyboardMarkup:
    order = ["roni","ruby","rin","savy"]
    btns = [InlineKeyboardButton(MODELS[k]["name"], callback_data=f"menu:{k}") for k in order]
    rows = [btns[i:i+2] for i in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="home"), InlineKeyboardButton("🏠 Main", callback_data="home")])
    return InlineKeyboardMarkup(rows)

def _model_menu_kb(model_key: str, username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Book", url=_tg_url(username))],
        [InlineKeyboardButton("💸 Tip", callback_data=f"tip:{model_key}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menus")],
    ])

def _admins_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact Roni", url=_tg_url(os.getenv("RONI_USERNAME","")))],
        [InlineKeyboardButton("💬 Contact Ruby", url=_tg_url(os.getenv("RUBY_USERNAME","")))],
        [InlineKeyboardButton("🕵️ Send Anonymous Message", callback_data="anon:start")],
        [InlineKeyboardButton("⬅️ Back", callback_data="home"), InlineKeyboardButton("🏠 Main", callback_data="home")],
    ])

def _help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Buyer Requirements", callback_data="help:reqs")],
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help:rules")],
        [InlineKeyboardButton("🎲 Game Rules", callback_data="help:games")],
        [InlineKeyboardButton("🕊️ Exemptions", callback_data="help:ex")],
        [InlineKeyboardButton("⬅️ Back", callback_data="home"), InlineKeyboardButton("🏠 Main", callback_data="home")],
    ])

def _sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="help")],
        [InlineKeyboardButton("🏠 Main", callback_data="home")],
    ])

URL_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)

def _models_elsewhere_kb() -> InlineKeyboardMarkup:
    """
    Accept either:
      - MODELS_ELSEWHERE: 'Label|URL' per line
      - FIND_MODELS_TEXT: free text (label+url on separate lines, or just URLs)
    """
    raw = (os.getenv("MODELS_ELSEWHERE") or os.getenv("FIND_MODELS_TEXT") or "").strip()
    rows: List[List[InlineKeyboardButton]] = []

    if raw:
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        i = 0
        while i < len(lines):
            ln = lines[i]

            # 1) Label|URL on one line
            if "|" in ln:
                label, url = ln.split("|", 1)
                label, url = label.strip(), url.strip()
                if label and URL_RE.search(url):
                    rows.append([InlineKeyboardButton(label, url=url)])
                    i += 1
                    continue

            # 2) URL alone -> use domain as label
            m = URL_RE.search(ln)
            if m and (ln == m.group(1) or ln.startswith(m.group(1))):
                url = m.group(1)
                label = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
                rows.append([InlineKeyboardButton(label, url=url)])
                i += 1
                continue

            # 3) Label on this line, URL on next line
            if i + 1 < len(lines):
                m2 = URL_RE.search(lines[i + 1])
                if m2:
                    url = m2.group(1)
                    label = ln
                    rows.append([InlineKeyboardButton(label, url=url)])
                    i += 2
                    continue

            # None matched — skip this line
            i += 1

    if not rows:
        rows.append([InlineKeyboardButton("Set MODELS_ELSEWHERE or FIND_MODELS_TEXT", url="https://render.com/")])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="home"),
                 InlineKeyboardButton("🏠 Main", callback_data="home")])
    return InlineKeyboardMarkup(rows)

# ---------------- Panels: callbacks ----------------
def register(app: Client):

    # MENUS list
    @app.on_callback_query(filters.regex(r"^menus$"))
    async def _show_menus(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "💕 Choose a model:", reply_markup=_menus_kb())

    # Model page
    @app.on_callback_query(filters.regex(r"^menu:(roni|ruby|rin|savy)$"))
    async def _show_model_menu(_: Client, q: CallbackQuery):
        key = q.matches[0].group(1)
        meta = MODELS[key]
        doc = col_model_menus.find_one({"key": key})

        if not doc:
            await _safe_edit(q.message, f"{meta['name']}'s menu has not been set yet.", reply_markup=_menus_kb())
            return

        title = f"**{meta['name']} — Menu**"
        body  = (doc.get("text") or "").strip()
        caption = f"{title}\n\n{body}" if body else title
        photo_id = doc.get("photo_id")

        if photo_id:
            try: await q.message.delete()
            except Exception: pass
            await q.message.reply_photo(
                photo=photo_id,
                caption=caption,
                reply_markup=_model_menu_kb(key, meta["username"]),
            )
        else:
            await _safe_edit(
                q.message,
                caption,
                reply_markup=_model_menu_kb(key, meta["username"]),
                disable_web_page_preview=True,
            )

    # Tip stub
    @app.on_callback_query(filters.regex(r"^tip:(roni|ruby|rin|savy)$"))
    async def _tip_stub(_: Client, q: CallbackQuery):
        await q.answer("💸 Tips: coming soon!", show_alert=True)

    # Contact Admins
    @app.on_callback_query(filters.regex(r"^admins$"))
    async def _show_admins(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "👑 Contact Admins", reply_markup=_admins_kb())

    # Anonymous message flow
    @app.on_callback_query(filters.regex(r"^anon:start$"))
    async def _start_anon(_: Client, q: CallbackQuery):
        col_anon.update_one({"user_id": q.from_user.id}, {"$set": {"user_id": q.from_user.id, "ts": int(time.time())}}, upsert=True)
        await _safe_edit(
            q.message,
            "🕵️ *Anonymous message mode*\n\nSend me the message now. I’ll forward it anonymously to the owner.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admins")],
                [InlineKeyboardButton("🏠 Main", callback_data="home")]
            ]),
            disable_web_page_preview=True
        )

    # Capture next private message in anon mode and forward to OWNER_ID
    @app.on_message(filters.private & filters.incoming & ~filters.service)
    async def _anon_capture(c: Client, m: Message):
        if not m.from_user: return
        if not col_anon.find_one({"user_id": m.from_user.id}):
            return
        owner_id = int(os.getenv("OWNER_ID", "0") or 0)
        try:
            await c.copy_message(owner_id, from_chat_id=m.chat.id, message_id=m.id)
            await m.reply_text("✅ Sent anonymously to the owner.")
        finally:
            col_anon.delete_one({"user_id": m.from_user.id})

    # Find Our Models Elsewhere
    @app.on_callback_query(filters.regex(r"^models$"))
    async def _show_elsewhere(_: Client, q: CallbackQuery):
        await _safe_edit(
            q.message,
            "🔥 Find Our Models Elsewhere",
            reply_markup=_models_elsewhere_kb(),
            disable_web_page_preview=True
        )

    # Help panel + subpages (read both *_TEXT and short key variants)
    @app.on_callback_query(filters.regex(r"^help$"))
    async def _show_help(_: Client, q: CallbackQuery):
        await _safe_edit(q.message, "❓ Help", reply_markup=_help_kb())

    @app.on_callback_query(filters.regex(r"^help:reqs$"))
    async def _h_reqs(_: Client, q: CallbackQuery):
        text = os.getenv("BUYER_REQUIREMENTS") or os.getenv("BUYER_REQUIREMENTS_TEXT") or "Set BUYER_REQUIREMENTS(_TEXT) in ENV."
        await _safe_edit(q.message, f"🧾 **Buyer Requirements**\n\n{text}", reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:rules$"))
    async def _h_rules(_: Client, q: CallbackQuery):
        text = os.getenv("BUYER_RULES") or os.getenv("BUYER_RULES_TEXT") or "Set BUYER_RULES(_TEXT) in ENV."
        await _safe_edit(q.message, f"📜 **Buyer Rules**\n\n{text}", reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:games$"))
    async def _h_games(_: Client, q: CallbackQuery):
        text = os.getenv("GAME_RULES") or os.getenv("GAME_RULES_TEXT") or "Set GAME_RULES(_TEXT) in ENV."
        await _safe_edit(q.message, f"🎲 **Game Rules**\n\n{text}", reply_markup=_sub_kb(), disable_web_page_preview=True)

    @app.on_callback_query(filters.regex(r"^help:ex$"))
    async def _h_ex(_: Client, q: CallbackQuery):
        text = os.getenv("EXEMPTIONS") or os.getenv("EXEMPTIONS_TEXT") or "Set EXEMPTIONS(_TEXT) in ENV."
        await _safe_edit(q.message, f"🕊️ **Exemptions**\n\n{text}", reply_markup=_sub_kb(), disable_web_page_preview=True)

    # ---------------- Commands: Menus CRUD ----------------

    # /mymenu <text>  (optionally attach a photo with caption)
    @app.on_message(filters.command("mymenu"))
    async def _my_menu(c: Client, m: Message):
        user = m.from_user
        if not user: return
        # find which model this user controls
        my_key: Optional[str] = None
        for k in MODELS:
            meta = MODELS[k]
            if (meta.get("uid") and user.id == meta["uid"]) or (meta.get("username") and user.username and user.username.lower() == meta["username"].lower()):
                my_key = k; break
        if not my_key:
            await m.reply_text("You are not authorized to edit a model menu with /mymenu.")
            return

        text = _extract_text_after_command(m)
        photo_id = m.photo.file_id if m.photo else None

        if col_model_menus.find_one({"key": my_key}):
            updates = {"updated_at": int(time.time())}
            if text != "": updates["text"] = text
            if m.photo: updates["photo_id"] = photo_id
            col_model_menus.update_one({"key": my_key}, {"$set": updates}, upsert=True)
            await m.reply_text(f"✅ Updated your menu ({MODELS[my_key]['name']}).")
        else:
            col_model_menus.update_one({"key": my_key}, {"$set": {"text": text, "photo_id": photo_id, "updated_at": int(time.time())}}, upsert=True)
            await m.reply_text(f"✅ Created your menu ({MODELS[my_key]['name']}).")

    # /createmenu Roni <text>  (with or without photo)
    @app.on_message(filters.command("createmenu"))
    async def _create_menu_cmd(c: Client, m: Message):
        user = m.from_user
        if not user: return
        if len(m.command) < 2:
            await m.reply_text("Usage:\n`/createmenu Roni <menu text>`\n(You can also attach a photo with caption.)", quote=True)
            return
        def _can_edit_model(key: str) -> bool:
            meta = MODELS[key]
            return _is_owner_or_admin(user.id) or \
                   (meta.get("uid") and user.id == meta["uid"]) or \
                   (meta.get("username") and user.username and user.username.lower() == meta["username"].lower())

        model_key = _model_key_from_name(m.command[1])
        if not model_key:
            await m.reply_text("Invalid model. Choose from: Roni, Ruby, Rin, Savy.", quote=True); return
        if not _can_edit_model(model_key):
            await m.reply_text("You are not allowed to create/overwrite this model’s menu.", quote=True); return

        text = _extract_text_after_command(m)
        photo_id = m.photo.file_id if m.photo else None
        col_model_menus.update_one(
            {"key": model_key},
            {"$set": {"text": text, "photo_id": photo_id, "updated_at": int(time.time())}},
            upsert=True
        )
        await m.reply_text(f"✅ Menu for {MODELS[model_key]['name']} created/overwritten.", quote=True)

    # /editmenu Roni <new text>  (with or without new photo)
    @app.on_message(filters.command("editmenu"))
    async def _edit_menu_cmd(c: Client, m: Message):
        user = m.from_user
        if not user: return
        if len(m.command) < 2:
            await m.reply_text("Usage:\n`/editmenu Roni <new text>`\n(Attach a new photo to replace; omit to keep old.)", quote=True); return

        def _can_edit_model(key: str) -> bool:
            meta = MODELS[key]
            return _is_owner_or_admin(user.id) or \
                   (meta.get("uid") and user.id == meta["uid"]) or \
                   (meta.get("username") and user.username and user.username.lower() == meta["username"].lower())

        model_key = _model_key_from_name(m.command[1])
        if not model_key:
            await m.reply_text("Invalid model. Choose from: Roni, Ruby, Rin, Savy.", quote=True); return
        if not _can_edit_model(model_key):
            await m.reply_text("You are not allowed to edit this model’s menu.", quote=True); return

        text = _extract_text_after_command(m)
        updates = {"updated_at": int(time.time())}
        if text != "": updates["text"] = text
        if m.photo: updates["photo_id"] = m.photo.file_id
        col_model_menus.update_one({"key": model_key}, {"$set": updates}, upsert=True)
        await m.reply_text(f"✅ Menu for {MODELS[model_key]['name']} updated.", quote=True)

    # /deletemenu Roni
    @app.on_message(filters.command("deletemenu"))
    async def _delete_menu_cmd(c: Client, m: Message):
        user = m.from_user
        if not user: return
        if len(m.command) < 2:
            await m.reply_text("Usage: /deletemenu Roni", quote=True); return

        def _can_edit_model(key: str) -> bool:
            meta = MODELS[key]
            return _is_owner_or_admin(user.id) or \
                   (meta.get("uid") and user.id == meta["uid"]) or \
                   (meta.get("username") and user.username and user.username.lower() == meta["username"].lower())

        model_key = _model_key_from_name(m.command[1])
        if not model_key:
            await m.reply_text("Invalid model. Choose from: Roni, Ruby, Rin, Savy.", quote=True); return
        if not _can_edit_model(model_key):
            await m.reply_text("You are not allowed to delete this model’s menu.", quote=True); return

        res = col_model_menus.delete_one({"key": model_key})
        if res.deleted_count:
            await m.reply_text(f"🗑️ Deleted menu for {MODELS[model_key]['name']}.", quote=True)
        else:
            await m.reply_text("There was nothing to delete for that model.", quote=True)

    # /viewmenu Roni
    @app.on_message(filters.command("viewmenu"))
    async def _view_menu_cmd(c: Client, m: Message):
        user = m.from_user
        if not user: return
        if len(m.command) < 2:
            await m.reply_text("Usage: /viewmenu Roni", quote=True); return

        def _can_edit_model(key: str) -> bool:
            meta = MODELS[key]
            return _is_owner_or_admin(user.id) or \
                   (meta.get("uid") and user.id == meta["uid"]) or \
                   (meta.get("username") and user.username and user.username.lower() == meta["username"].lower())

        model_key = _model_key_from_name(m.command[1])
        if not model_key:
            await m.reply_text("Invalid model. Choose from: Roni, Ruby, Rin, Savy.", quote=True); return
        if not _can_edit_model(model_key):
            await m.reply_text("You are not allowed to view this model’s menu via command.", quote=True); return

        doc = col_model_menus.find_one({"key": model_key})
        if not doc:
            await m.reply_text("No menu set.", quote=True); return

        text = (doc.get("text") or "").strip() or f"{MODELS[model_key]['name']}'s menu"
        photo_id = doc.get("photo_id")
        if photo_id:
            await m.reply_photo(photo=photo_id, caption=text)
        else:
            await m.reply_text(text)

    # /listmenus (owner/admin)
    @app.on_message(filters.command("listmenus"))
    async def _list_menus_cmd(c: Client, m: Message):
        user = m.from_user
        if not user: return
        if not _is_owner_or_admin(user.id):
            await m.reply_text("Only owner/admin can use /listmenus."); return

        docs = list(col_model_menus.find({}, {"key": 1, "updated_at": 1, "photo_id": 1}))
        if not docs:
            await m.reply_text("No menus set yet."); return

        lines: List[str] = ["📋 Menus:"]
        for d in docs:
            key = d.get("key")
            nm = MODELS.get(key, {}).get("name", key.title())
            ts = d.get("updated_at")
            when = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts)) if ts else "?"
            has_photo = "📷" if d.get("photo_id") else "—"
            lines.append(f"- {nm} ({key}) — updated {when} UTC {has_photo}")
        await m.reply_text("\n".join(lines))
