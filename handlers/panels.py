# handlers/panels.py
# Only navigation panels. NO /start handler here (prevents duplicate welcomes).
# All "Back" actions use edit_text so nothing duplicates.

import os
import json
from pathlib import Path
from typing import Dict, List

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

# -----------------------------
# small persistence helpers (for anon suggestions)
# -----------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = DATA_DIR / "contact_state.json"   # { "<uid>": {"awaiting": true} }
SUGG_FILE  = DATA_DIR / "suggestions.json"     # { "<id>": {"user_id": int, "text": str} }
SEQ_FILE   = DATA_DIR / "suggestions_seq.txt"  # monotonic suggestion id

def _read_json(p: Path) -> Dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _write_json(p: Path, d: Dict) -> None:
    try:
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _next_id() -> int:
    n = 0
    if SEQ_FILE.exists():
        try:
            n = int(SEQ_FILE.read_text().strip() or "0")
        except Exception:
            n = 0
    n += 1
    try:
        SEQ_FILE.write_text(str(n))
    except Exception:
        pass
    return n

# -----------------------------
# ENV
# -----------------------------
MENU_LABEL   = os.getenv("MENU_BTN", "💕 Menu")
ADMINS_LABEL = os.getenv("ADMINS_BTN", "👑 Contact Admins")
FIND_LABEL   = os.getenv("FIND_MODELS_BTN", "🔥 Find Our Models Elsewhere")
HELP_LABEL   = os.getenv("HELP_BTN", "❓ Help")

RONI_NAME = (os.getenv("RONI_NAME") or "Roni").strip()
RONI_ID   = int((os.getenv("RONI_ID") or "0") or 0)
RUBY_NAME = (os.getenv("RUBY_NAME") or "Ruby").strip()
RUBY_ID   = int((os.getenv("RUBY_ID") or "0") or 0)

FIND_MODELS_TEXT        = (os.getenv("FIND_MODELS_TEXT") or os.getenv("FIND_MODELS") or "").strip()
HELP_INTRO              = os.getenv("HELP_INTRO", "Here’s what I can help with:").strip()
BUYER_RULES_TEXT        = (os.getenv("BUYER_RULES_TEXT") or "").strip()
BUYER_REQUIREMENTS_TEXT = (os.getenv("BUYER_REQUIREMENTS_TEXT") or "").strip()
GAME_RULES_TEXT         = (os.getenv("GAME_RULES_TEXT") or "").strip()
EXEMPTIONS_TEXT         = (os.getenv("EXEMPTIONS_TEXT") or "").strip()

SUGGESTIONS_CHAT_ID = int((os.getenv("SUGGESTIONS_CHAT_ID") or os.getenv("OWNER_ID") or "0") or 0)

# -----------------------------
# UI helpers
# -----------------------------
def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _url(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, url=url)

def _rows(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows)

def _tg_contact(name: str, tid: int) -> InlineKeyboardButton:
    # deep-link to DM with admin if ID exists; otherwise inert button
    return _url(f"📩 Contact {name}", f"tg://user?id={tid}") if tid else _btn(f"📩 Contact {name}", "noop")

def _main_markup() -> InlineKeyboardMarkup:
    return _rows([
        [_btn(MENU_LABEL, "menu")],               # your menu grid is handled by handlers/menu.py
        [_btn(ADMINS_LABEL, "nav:admins")],
        [_btn(FIND_LABEL, "nav:find")],
        [_btn(HELP_LABEL, "nav:help")],
    ])

# -----------------------------
# Public renderers
# -----------------------------
async def main_menu(message: Message):
    """Reply with the main navigation panel (used by your /start flow elsewhere)."""
    await message.reply_text(
        "✨ <i>Use the menu below to navigate!</i>",
        reply_markup=_main_markup(),
        disable_web_page_preview=True,
    )

async def main_menu_edit(message: Message):
    """Edit to the main navigation panel — prevents duplicates."""
    await message.edit_text(
        "✨ <i>Use the menu below to navigate!</i>",
        reply_markup=_main_markup(),
        disable_web_page_preview=True,
    )

# Back-compat alias if other code imports this name:
render_main = main_menu

# -----------------------------
# Internal renders (all EDIT in place)
# -----------------------------
async def _render_admins(msg: Message):
    kb = _rows([
        [_tg_contact(RONI_NAME, RONI_ID)],
        [_tg_contact(RUBY_NAME, RUBY_ID)],
        [_btn("🕵️ Anonymous Suggestions", "contact:anon")],
        [_btn("⬅️ Back to Main", "nav:main")],
    ])
    await msg.edit_text(
        "<b>Contact Admins</b>\nChoose how you want to reach us:",
        reply_markup=kb,
        disable_web_page_preview=True
    )

async def _render_find(msg: Message):
    text = FIND_MODELS_TEXT or "Ask an admin where to find our models elsewhere."
    await msg.edit_text(
        text,
        reply_markup=_rows([[_btn("⬅️ Back to Main", "nav:main")]]),
        disable_web_page_preview=False
    )

def _help_markup() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    line: List[InlineKeyboardButton] = []

    if BUYER_RULES_TEXT:
        line.append(_btn("📜 Buyer Rules", "help:rules"))
    if BUYER_REQUIREMENTS_TEXT:
        line.append(_btn("🧾 Buyer Requirements", "help:reqs"))
    if line:
        rows.append(line)
        line = []

    if GAME_RULES_TEXT:
        line.append(_btn("🎲 Game Rules", "help:games"))
    if EXEMPTIONS_TEXT:
        line.append(_btn("🛡️ Exemptions", "help:exempt"))
    if line:
        rows.append(line)

    rows.append([_btn("⬅️ Back to Main", "nav:main")])
    return _rows(rows)

async def _render_help(msg: Message):
    await msg.edit_text(
        f"❓ <b>Help</b>\n{HELP_INTRO}",
        reply_markup=_help_markup(),
        disable_web_page_preview=True
    )

async def _render_help_section(msg: Message, title: str, text: str):
    await msg.edit_text(
        f"<b>{title}</b>\n{text}",
        reply_markup=_rows([[_btn("⬅️ Back to Help", "nav:help")]]),
        disable_web_page_preview=False
    )

# -----------------------------
# Anonymous suggestions
# -----------------------------
def _get_state() -> Dict[str, Dict]:
    return _read_json(STATE_FILE)

def _set_state(d: Dict[str, Dict]) -> None:
    _write_json(STATE_FILE, d)

def _get_suggs() -> Dict[str, Dict]:
    return _read_json(SUGG_FILE)

def _set_suggs(d: Dict[str, Dict]) -> None:
    _write_json(SUGG_FILE, d)

async def _start_anon(msg: Message, user_id: int):
    st = _get_state()
    st[str(user_id)] = {"awaiting": True}
    _set_state(st)
    await msg.edit_text(
        "🕵️ <b>Anonymous Suggestions</b>\n"
        "Send your suggestion now (text only). I’ll forward it anonymously to the admins.\n\n"
        "Tap <b>Cancel</b> to abort.",
        reply_markup=_rows([[_btn("❌ Cancel", "contact:anon_cancel")]]),
        disable_web_page_preview=True,
    )

async def _cancel_anon(user_id: int):
    st = _get_state()
    if str(user_id) in st:
        st.pop(str(user_id), None)
        _set_state(st)

# -----------------------------
# Register callbacks — all EDIT (no duplicates)
# -----------------------------
def register(app: Client):

    # Main/back
    @app.on_callback_query(filters.regex(r"^(nav:main|nav:root|back_main)$"))
    async def _go_main(c: Client, cq: CallbackQuery):
        await main_menu_edit(cq.message)     # EDIT in place
        await cq.answer()

    # Contact Admins
    @app.on_callback_query(filters.regex(r"^nav:admins$"))
    async def _admins(c: Client, cq: CallbackQuery):
        await _render_admins(cq.message)
        await cq.answer()

    # Find our models elsewhere
    @app.on_callback_query(filters.regex(r"^nav:find$"))
    async def _find(c: Client, cq: CallbackQuery):
        await _render_find(cq.message)
        await cq.answer()

    # Help hub + sections
    @app.on_callback_query(filters.regex(r"^nav:help$"))
    async def _help(c: Client, cq: CallbackQuery):
        await _render_help(cq.message)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:rules$"))
    async def _help_rules(c: Client, cq: CallbackQuery):
        if not BUYER_RULES_TEXT:
            return await cq.answer("No Buyer Rules configured.", show_alert=True)
        await _render_help_section(cq.message, "📜 Buyer Rules", BUYER_RULES_TEXT)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:reqs$"))
    async def _help_reqs(c: Client, cq: CallbackQuery):
        if not BUYER_REQUIREMENTS_TEXT:
            return await cq.answer("No Buyer Requirements configured.", show_alert=True)
        await _render_help_section(cq.message, "🧾 Buyer Requirements", BUYER_REQUIREMENTS_TEXT)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:games$"))
    async def _help_games(c: Client, cq: CallbackQuery):
        if not GAME_RULES_TEXT:
            return await cq.answer("No Game Rules configured.", show_alert=True)
        await _render_help_section(cq.message, "🎲 Game Rules", GAME_RULES_TEXT)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:exempt$"))
    async def _help_exempt(c: Client, cq: CallbackQuery):
        if not EXEMPTIONS_TEXT:
            return await cq.answer("No Exemptions configured.", show_alert=True)
        await _render_help_section(cq.message, "🛡️ Exemptions", EXEMPTIONS_TEXT)
        await cq.answer()

    # Anonymous suggestions flow
    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def _anon_start(c: Client, cq: CallbackQuery):
        await _start_anon(cq.message, cq.from_user.id)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^contact:anon_cancel$"))
    async def _anon_cancel(c: Client, cq: CallbackQuery):
        await _cancel_anon(cq.from_user.id)
        await main_menu_edit(cq.message)      # back to main (EDIT, not reply)
        await cq.answer()

    # Capture anon text (private; ignore commands)
    @app.on_message(filters.private & ~filters.command(["start", "createmenu", "addmenu", "menudebug"]))
    async def _capture_anon(c: Client, m: Message):
        st = _get_state()
        if not st.get(str(m.from_user.id), {}).get("awaiting"):
            return
        text = (m.text or "").strip()
        if not text:
            return await m.reply_text("Please send your suggestion as text.")
        sid = _next_id()
        suggs = _get_suggs()
        suggs[str(sid)] = {"user_id": m.from_user.id, "text": text}
        _set_suggs(suggs)
        if SUGGESTIONS_CHAT_ID:
            try:
                await c.send_message(
                    SUGGESTIONS_CHAT_ID,
                    f"🕵️ <b>New Anonymous Suggestion</b>\n"
                    f"ID: <code>{sid}</code>\n"
                    f"{text}\n\n"
                    f"Reply with: <code>/sreply {sid} &lt;your reply&gt;</code>"
                )
            except Exception:
                pass
        await _cancel_anon(m.from_user.id)
        await m.reply_text("✅ Sent anonymously to admins. Thanks!")

    # Admin replies back to the anonymous sender
    @app.on_message(filters.command("sreply", prefixes=["/", "!", "."]))
    async def _sreply(c: Client, m: Message):
        if not SUGGESTIONS_CHAT_ID:
            return
        is_owner = str(m.from_user.id) == (os.getenv("OWNER_ID") or "")
        if (m.chat.id != SUGGESTIONS_CHAT_ID) and not is_owner:
            return
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 3:
            return await m.reply_text("Usage: /sreply <id> <reply text>")
        sid, reply_text = parts[1], parts[2]
        entry = _get_suggs().get(sid)
        if not entry:
            return await m.reply_text("Unknown suggestion ID.")
        uid = entry.get("user_id")
        if not uid:
            return await m.reply_text("Missing user for that suggestion.")
        try:
            await c.send_message(uid, f"🛡️ <b>Admin Reply</b>\n{reply_text}")
            await m.reply_text("✅ Reply delivered.")
        except Exception as e:
            await m.reply_text(f"Could not deliver reply: {e}")
