# handlers/menu.py
# Model Menus with file persistence + DM submenu + contact links.
# Works with text-only menus. No DB required.
#
# Commands:
#   /menu                       → open submenu (also via dmf_open_menu)
#   /addmenu <model> [text]     → save/replace a menu (admin/editor only)
#   /changemenu <model> [text]  → alias of /addmenu
#   /deletemenu <model>         → delete a menu
#   /listmenus                  → list which models have menus saved
#
# Callbacks:
#   menu:open                   → open submenu
#   menu:show:<slug>            → show a model’s menu
#   menu:contact                → contact models screen
#
# ENV:
#   OWNER_ID, SUPER_ADMIN_ID, MENU_EDITORS (comma-separated user_ids)
#   RONI_NAME, RUBY_NAME, RIN_NAME, SAVY_NAME (display names)
#   RUBY_ID, RIN_ID, SAVY_ID (for deep-link contact buttons; integers)
#   MENUS_PATH (optional, default ./data/menus.json)

import os
import json
import asyncio
import logging
from typing import Dict, Optional, Tuple, Set

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

log = logging.getLogger("handlers.menu")

# ---------- Config / IDs ----------
def _to_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(str(s)) if s not in (None, "", "None") else None
    except Exception:
        return None

OWNER_ID       = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))

# Extra editors (comma separated user ids)
_EDITORS: Set[int] = set()
if os.getenv("MENU_EDITORS"):
    for tok in os.getenv("MENU_EDITORS").replace(";", ",").split(","):
        v = _to_int(tok.strip())
        if v:
            _EDITORS.add(v)

ADMIN_OR_EDITORS: Set[int] = set(i for i in (OWNER_ID, SUPER_ADMIN_ID) if i) | _EDITORS

# Names / Contact IDs from env (with sensible fallbacks)
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME",  "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

RUBY_ID = _to_int(os.getenv("RUBY_ID"))
RIN_ID  = _to_int(os.getenv("RIN_ID"))
SAVY_ID = _to_int(os.getenv("SAVY_ID"))
OWNER_DISPLAY = os.getenv("OWNER_DISPLAY", RONI_NAME)  # label for OWNER_ID button

# Model registry (slug → (display, user_id_for_contact or None))
MODELS: Dict[str, Tuple[str, Optional[int]]] = {
    "roni": (RONI_NAME, OWNER_ID),
    "ruby": (RUBY_NAME, RUBY_ID),
    "rin":  (RIN_NAME,  RIN_ID),
    "savy": (SAVY_NAME, SAVY_ID),
}

# ---------- Persistence ----------
MENUS_PATH = os.getenv("MENUS_PATH", "./data/menus.json")
_os_lock = asyncio.Lock()

def _ensure_dir(p: str):
    d = os.path.dirname(os.path.abspath(p)) or "."
    os.makedirs(d, exist_ok=True)

async def _load() -> Dict[str, str]:
    async with _os_lock:
        try:
            if not os.path.exists(MENUS_PATH):
                return {}
            with open(MENUS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            # normalize keys
            return {k.lower(): str(v) for k, v in data.items()}
        except Exception as e:
            log.exception("menus: load failed: %s", e)
            return {}

async def _save(data: Dict[str, str]) -> None:
    async with _os_lock:
        try:
            _ensure_dir(MENUS_PATH)
            tmp = MENUS_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, MENUS_PATH)  # atomic on POSIX
        except Exception as e:
            log.exception("menus: save failed: %s", e)
            raise

def _is_editor(uid: Optional[int]) -> bool:
    return bool(uid and uid in ADMIN_OR_EDITORS)

def _slug(s: str) -> str:
    return s.strip().lower()

def _back_row() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu:open")],
        [InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")],
    ])

def _submenu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(MODELS["roni"][0], callback_data="menu:show:roni"),
         InlineKeyboardButton(MODELS["ruby"][0], callback_data="menu:show:ruby")],
        [InlineKeyboardButton(MODELS["rin"][0],  callback_data="menu:show:rin"),
         InlineKeyboardButton(MODELS["savy"][0], callback_data="menu:show:savy")],
        [InlineKeyboardButton("💌 Contact Models", callback_data="menu:contact")],
        [InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")],
    ]
    return InlineKeyboardMarkup(rows)

def _contact_kb() -> InlineKeyboardMarkup:
    row1 = []
    if OWNER_ID:
        row1.append(InlineKeyboardButton(f"💌 {MODELS['roni'][0]}", url=f"tg://user?id={OWNER_ID}"))
    if RUBY_ID:
        row1.append(InlineKeyboardButton(f"💌 {MODELS['ruby'][0]}", url=f"tg://user?id={RUBY_ID}"))

    row2 = []
    if RIN_ID:
        row2.append(InlineKeyboardButton(f"💌 {MODELS['rin'][0]}", url=f"tg://user?id={RIN_ID}"))
    if SAVY_ID:
        row2.append(InlineKeyboardButton(f"💌 {MODELS['savy'][0]}", url=f"tg://user?id={SAVY_ID}"))

    rows = []
    if row1: rows.append(row1)
    if row2: rows.append(row2)
    rows.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu:open")])
    rows.append([InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")])
    return InlineKeyboardMarkup(rows)

def menu_tabs_text() -> str:
    return "🍽️ <b>Pick a model menu</b>"

def menu_tabs_kb() -> InlineKeyboardMarkup:
    return _submenu_kb()

# ---------- Register ----------
def register(app: Client):

    # /menu entry (and portal calls this callback too)
    @app.on_message(filters.command("menu"))
    async def cmd_menu(client: Client, m: Message):
        try:
            await m.reply_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            pass

    # Portal button compatibility: dmf_open_menu → open submenu
    @app.on_callback_query(filters.regex(r"^dmf_open_menu$"))
    async def cb_portal_open(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(menu_tabs_text(), reply_markup=menu_tabs_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Submenu open
    @app.on_callback_query(filters.regex(r"^menu:open$"))
    async def cb_menu_open(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text(menu_tabs_text(), reply_markup=_submenu_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text(menu_tabs_text(), reply_markup=_submenu_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Contact screen
    @app.on_callback_query(filters.regex(r"^menu:contact$"))
    async def cb_contact(client: Client, cq: CallbackQuery):
        try:
            await cq.message.edit_text("💌 <b>Contact a model directly</b>", reply_markup=_contact_kb(), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("💌 <b>Contact a model directly</b>", reply_markup=_contact_kb(), disable_web_page_preview=True)
        await cq.answer()

    # Show a model’s menu
    @app.on_callback_query(filters.regex(r"^menu:show:(\w+)$"))
    async def cb_show_model(client: Client, cq: CallbackQuery):
        slug = _slug(cq.data.split(":", 2)[2])
        disp, _uid = MODELS.get(slug, (slug.title(), None))
        menus = await _load()
        text = menus.get(slug)
        if not text:
            try:
                await cq.message.edit_text(f"❌ No saved menu for {disp} yet.", reply_markup=_back_row(), disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text(f"❌ No saved menu for {disp} yet.", reply_markup=_back_row(), disable_web_page_preview=True)
            return await cq.answer()

        kb = _back_row()
        # If editor/admin, show a hint
        if _is_editor(cq.from_user.id):
            try:
                await cq.message.edit_text(
                    f"📝 <b>{disp}’s Menu</b>\n\n{text}",
                    reply_markup=kb,
                    disable_web_page_preview=True
                )
            except Exception:
                await cq.message.reply_text(
                    f"📝 <b>{disp}’s Menu</b>\n\n{text}",
                    reply_markup=kb,
                    disable_web_page_preview=True
                )
        else:
            try:
                await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                await cq.message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cq.answer()

    # Add/Change/Delete/List

    @app.on_message(filters.command(["addmenu", "changemenu"]))
    async def cmd_addmenu(client: Client, m: Message):
        if not _is_editor(m.from_user.id if m.from_user else None):
            return await m.reply_text("Admins only.", reply_markup=_back_row())
        if len(m.command) < 2:
            return await m.reply_text("Usage: /addmenu <roni|ruby|rin|savy> [text]\n\nTip: You can also REPLY to a text message.", reply_markup=_back_row())

        model = _slug(m.command[1])
        if model not in MODELS:
            return await m.reply_text("Unknown model. Use one of: roni, ruby, rin, savy.", reply_markup=_back_row())

        # Prefer replied message text; fall back to command remainder
        text: Optional[str] = None
        if m.reply_to_message and (m.reply_to_message.text or m.reply_to_message.caption):
            text = (m.reply_to_message.text or m.reply_to_message.caption).strip()
        else:
            # join everything after the model slug
            if len(m.command) > 2:
                text = " ".join(m.command[2:]).strip()

        if not text:
            return await m.reply_text("No text found. Reply to a text message with /addmenu <model>, or pass the text after the model name.", reply_markup=_back_row())

        data = await _load()
        data[model] = text
        await _save(data)
        await m.reply_text(f"✅ Saved menu for {MODELS[model][0]}.", reply_markup=_back_row())

    @app.on_message(filters.command("deletemenu"))
    async def cmd_deletemenu(client: Client, m: Message):
        if not _is_editor(m.from_user.id if m.from_user else None):
            return await m.reply_text("Admins only.", reply_markup=_back_row())
        if len(m.command) < 2:
            return await m.reply_text("Usage: /deletemenu <roni|ruby|rin|savy>", reply_markup=_back_row())
        model = _slug(m.command[1])
        data = await _load()
        if model in data:
            data.pop(model, None)
            await _save(data)
            return await m.reply_text(f"🗑️ Deleted menu for {MODELS.get(model, (model.title(), None))[0]}.", reply_markup=_back_row())
        else:
            return await m.reply_text("Nothing to delete.", reply_markup=_back_row())

    @app.on_message(filters.command("listmenus"))
    async def cmd_listmenus(client: Client, m: Message):
        data = await _load()
        if not data:
            return await m.reply_text("No menus saved yet.", reply_markup=_back_row())
        lines = []
        for slug, (disp, _uid) in MODELS.items():
            lines.append(f"{'✅' if slug in data else '—'} {disp}")
        await m.reply_text("<b>Menus:</b>\n" + "\n".join(lines), reply_markup=_back_row())
