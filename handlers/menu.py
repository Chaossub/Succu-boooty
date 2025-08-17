# handlers/menu.py
# Model menus (Roni, Ruby, Rin, Savy) with Back navigation and clean edit-in-place behavior.
# - /addmenu <Name> <text...>   (DM recommended) — supports text-only OR photo+caption OR reply-to-photo
# - /menu                        — show tabs & open a model's menu
# - /menus                       — list which menus exist
# - /deletemenu <Name>           — delete a menu
#
# Permissions:
#   Admins: SUPER_ADMIN_ID / OWNER_ID / MENU_EDITORS (CSV) → can edit ANY menu
#   Models: RONI_ID/RUBY_ID/RIN_ID/SAVY_ID → can edit ONLY their own menu
#
# Storage: MongoDB (MONGO_URI, MONGO_DBNAME). Collection: "model_menus".

import os
import time
from typing import Optional, Tuple, Dict, Set

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from pymongo import MongoClient

# -------------------- Config --------------------
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DBNAME", "succubus")
COLL = "model_menus"

ALLOWED_MODELS = {"roni": "Roni", "ruby": "Ruby", "rin": "Rin", "savy": "Savy"}

def _to_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(str(s)) if s not in (None, "", "None") else None
    except Exception:
        return None

SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))
OWNER_ID       = _to_int(os.getenv("OWNER_ID"))

RONI_ID = _to_int(os.getenv("RONI_ID"))
RUBY_ID = _to_int(os.getenv("RUBY_ID"))
RIN_ID  = _to_int(os.getenv("RIN_ID"))
SAVY_ID = _to_int(os.getenv("SAVY_ID"))

_EXTRA_EDITORS: Set[int] = set()
if os.getenv("MENU_EDITORS"):
    for tok in os.getenv("MENU_EDITORS").split(","):
        v = _to_int(tok.strip())
        if v:
            _EXTRA_EDITORS.add(v)

ADMIN_IDS: Set[int] = set(i for i in (SUPER_ADMIN_ID, OWNER_ID) if i) | _EXTRA_EDITORS
MODEL_OWNER_ID = {"Roni": RONI_ID, "Ruby": RUBY_ID, "Rin": RIN_ID, "Savy": SAVY_ID}

# ----------------- DB Helpers -------------------
_client: Optional[MongoClient] = None
def _db():
    global _client
    if _client is None:
        if not MONGO_URI:
            raise RuntimeError("MONGO_URI not set")
        _client = MongoClient(MONGO_URI, connect=False)
    return _client[MONGO_DB][COLL]

def set_menu(name: str, text: str, photo_id: Optional[str], by_id: Optional[int]):
    coll = _db()
    coll.update_one(
        {"name": name},
        {"$set": {
            "name": name,
            "text": text,
            "photo_id": photo_id,
            "updated_at": int(time.time()),
            "by": by_id
        }},
        upsert=True
    )

def get_menu(name: str) -> Optional[Dict]:
    return _db().find_one({"name": name})

def list_menus():
    return [x["name"] for x in _db().find({}, {"name": 1}).sort("name", 1)]

def delete_menu(name: str) -> bool:
    res = _db().delete_one({"name": name})
    return res.deleted_count > 0

# ----------------- Permissions ------------------
def _norm_name(raw: str) -> Optional[str]:
    if not raw:
        return None
    return ALLOWED_MODELS.get(raw.strip().lower())

def _is_admin(user_id: Optional[int]) -> bool:
    return bool(user_id and user_id in ADMIN_IDS)

def _is_model_owner(model: str, user_id: Optional[int]) -> bool:
    return bool(user_id and MODEL_OWNER_ID.get(model) and MODEL_OWNER_ID[model] == user_id)

def _can_edit(model: str, user_id: Optional[int]) -> bool:
    # Admins can edit anything; models can edit their own only.
    return _is_admin(user_id) or _is_model_owner(model, user_id)

# ----------------- Parse Helpers ----------------
def _extract_text_and_model(m: Message) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract model name and menu text from message (DM-friendly).
    Accepts:
      - command + name + newline(s) + text...
      - command + name + inline rest
      - command (caption) on a photo
    """
    content = (m.caption or m.text or "").strip()
    if not content:
        return None, None

    parts = content.split(None, 2)  # [/addmenu, Name, rest...]
    if len(parts) < 2:
        return None, None

    model = _norm_name(parts[1])
    if not model:
        return None, None

    if len(parts) >= 3 and parts[2].strip():
        return model, parts[2].strip()

    lines = content.splitlines()
    if len(lines) > 1:
        rest = "\n".join(lines[1:]).strip()
        if rest:
            return model, rest

    return model, None

def _photo_id_from(m: Message) -> Optional[str]:
    if m.photo:
        return m.photo[-1].file_id
    if m.reply_to_message and m.reply_to_message.photo:
        return m.reply_to_message.photo[-1].file_id
    return None

# ----------------- Keyboards --------------------
def _tabs_kb(include_back_to_portal: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("Roni", callback_data="menu_tab:Roni"),
            InlineKeyboardButton("Ruby", callback_data="menu_tab:Ruby"),
        ],
        [
            InlineKeyboardButton("Rin", callback_data="menu_tab:Rin"),
            InlineKeyboardButton("Savy", callback_data="menu_tab:Savy"),
        ],
    ]
    if include_back_to_portal:
        rows.append([InlineKeyboardButton("◀️ Back", callback_data="menu_home")])
    return InlineKeyboardMarkup(rows)

def _back_to_tabs_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Back", callback_data="menu_back_tabs")],
        [InlineKeyboardButton("🏠 Start", callback_data="dmf_back_welcome")],
    ])

def _portal_kb() -> InlineKeyboardMarkup:
    # Match dm_foolproof callbacks
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Menu", callback_data="dmf_open_menu")],
        [InlineKeyboardButton("Contact Admins 👑", callback_data="dmf_open_direct")],
        [InlineKeyboardButton("Find Our Models Elsewhere 🔥", callback_data="dmf_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="dmf_show_help")],
    ])

# ---- Public API expected by dm_foolproof.py ----
def menu_tabs_text() -> str:
    return "💕 <b>Model Menus</b>\nChoose a name:"

def menu_tabs_kb() -> InlineKeyboardMarkup:
    return _tabs_kb(include_back_to_portal=True)

# ----------------- Handlers ---------------------
def register(app: Client):

    @app.on_message(filters.command("addmenu"))
    async def addmenu_handler(client: Client, m: Message):
        # Recommend doing this in DM
        if m.chat.type != ChatType.PRIVATE:
            me = await client.get_me()
            return await m.reply_text(
                "Add menus in DM.\nOpen: https://t.me/{u}".format(u=me.username),
                disable_web_page_preview=True
            )

        model, text = _extract_text_and_model(m)
        photo_id = _photo_id_from(m)
        uid = m.from_user.id if m.from_user else None

        if not model:
            return await m.reply_text(
                "Which model? Use one of: <code>Roni</code>, <code>Ruby</code>, <code>Rin</code>, <code>Savy</code>\n\n"
                "Examples:\n"
                "<code>/addmenu Roni &lt;b&gt;Roni’s Menu&lt;/b&gt; • GFE $XX • Customs $XX</code>\n"
                "or send a photo and put the command + text in the caption.",
                disable_web_page_preview=True
            )

        # Permission check
        if not _can_edit(model, uid):
            return await m.reply_text(
                f"Sorry, you don’t have permission to edit <b>{model}</b>’s menu.\n"
                "If you are that model, ask an admin to set your user ID in the environment (e.g., RONI_ID/RUBY_ID/RIN_ID/SAVY_ID)."
            )

        if not text and not photo_id:
            return await m.reply_text(
                "I need the menu text.\n\n"
                "Send one message like:\n"
                f"<code>/addmenu {model}\n"
                "&lt;b&gt;Title&lt;/b&gt;\\n• line\\n• line</code>\n"
                "Or send a photo and put the command + text in the caption.\n"
                f"You can also reply to a photo with: <code>/addmenu {model} Your text…</code>",
                disable_web_page_preview=True
            )

        set_menu(model, text or "", photo_id, by_id=uid)
        pretty = f"<b>{model}</b> menu saved"
        if photo_id and text:
            pretty += " (photo + text)."
        elif photo_id:
            pretty += " (photo-only)."
        else:
            pretty += " (text-only)."
        return await m.reply_text(f"✅ {pretty}")

    @app.on_message(filters.command("menus"))
    async def menus_handler(client: Client, m: Message):
        names = list_menus()
        if not names:
            return await m.reply_text("No menus saved yet. Use <code>/addmenu Roni ...</code> in DM.")
        await m.reply_text("Available menus:\n• " + "\n• ".join(names))

    @app.on_message(filters.command("deletemenu"))
    async def deletemenu_handler(client: Client, m: Message):
        parts = (m.text or "").split(None, 1)
        if len(parts) < 2:
            return await m.reply_text("Usage: <code>/deletemenu Roni</code>")
        model = _norm_name(parts[1])
        uid = m.from_user.id if m.from_user else None
        if not model:
            return await m.reply_text("Pick one of: Roni, Ruby, Rin, Savy")

        # Permission check
        if not _can_edit(model, uid):
            return await m.reply_text(
                f"Sorry, you don’t have permission to delete <b>{model}</b>’s menu."
            )

        ok = delete_menu(model)
        if ok:
            await m.reply_text(f"🗑 Deleted <b>{model}</b> menu.")
        else:
            await m.reply_text(f"No menu found for <b>{model}</b>.")

    @app.on_message(filters.command("menu"))
    async def open_menu(client: Client, m: Message):
        await m.reply_text(
            menu_tabs_text(),
            reply_markup=menu_tabs_kb(),
            disable_web_page_preview=True
        )

    # ---- Callbacks ----

    @app.on_callback_query(filters.regex(r"^menu_back_tabs$"))
    async def on_back_tabs(client: Client, cq: CallbackQuery):
        # Always EDIT back to tabs (prevents duplicates)
        try:
            await cq.message.edit_text(
                menu_tabs_text(),
                reply_markup=menu_tabs_kb(),
                disable_web_page_preview=True
            )
        except Exception:
            await cq.message.reply_text(
                menu_tabs_text(),
                reply_markup=menu_tabs_kb(),
                disable_web_page_preview=True
            )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu_home$"))
    async def on_menu_home(client: Client, cq: CallbackQuery):
        # Edit back to your portal (dm_foolproof callbacks)
        try:
            await cq.message.edit_text(
                "Welcome to the Sanctuary portal 💋 Choose an option:",
                reply_markup=_portal_kb(),
                disable_web_page_preview=True
            )
        except Exception:
            await cq.message.reply_text(
                "Welcome to the Sanctuary portal 💋 Choose an option:",
                reply_markup=_portal_kb(),
                disable_web_page_preview=True
            )
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu_tab:(Roni|Ruby|Rin|Savy)$"))
    async def on_tab(client: Client, cq: CallbackQuery):
        model = cq.data.split(":", 1)[1]
        doc = get_menu(model)
        if not doc:
            await cq.answer("No menu yet for " + model, show_alert=True)
            return

        text = (doc.get("text") or "").strip()
        photo_id = doc.get("photo_id")

        if photo_id:
            # To avoid duplicate stacks: delete the old message and send the photo once.
            try:
                await cq.message.delete()
            except Exception:
                pass
            try:
                await client.send_photo(
                    cq.from_user.id,
                    photo_id,
                    caption=text or "",
                    reply_markup=_back_to_tabs_kb()
                )
            except Exception:
                # If photo retrieve fails, at least show text
                await client.send_message(
                    cq.from_user.id,
                    text or "(photo unavailable)",
                    reply_markup=_back_to_tabs_kb(),
                    disable_web_page_preview=True
                )
        else:
            # Text-only: edit in place (no new messages)
            try:
                await cq.message.edit_text(
                    text or "(empty)",
                    reply_markup=_back_to_tabs_kb(),
                    disable_web_page_preview=True
                )
            except Exception:
                await cq.message.reply_text(
                    text or "(empty)",
                    reply_markup=_back_to_tabs_kb(),
                    disable_web_page_preview=True
                )
        await cq.answer()
