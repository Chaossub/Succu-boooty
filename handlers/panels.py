# handlers/panels.py
# Navigation panels — NO /start here (prevents duplicate welcomes).
# Contact Admins: Contact Roni, Contact Ruby, Anonymous Suggestions (admin can reply via bot).
# Help content is read entirely from ENV.

import os
import json
from typing import List, Tuple, Dict
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# -------------------------
# Storage for anonymous suggestions
# -------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = DATA_DIR / "contact_state.json"   # { "<user_id>": {"awaiting": true, "from_chat": <chat_id>} }
SUGG_FILE  = DATA_DIR / "suggestions.json"     # { "<sugg_id>": {"user_id": <int>, "text": "<..>"} }
ID_SEQ_FILE= DATA_DIR / "suggestions_seq.txt"  # monotonic id

def _read_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _write_json(path: Path, data: Dict):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _next_sugg_id() -> int:
    n = 0
    if ID_SEQ_FILE.exists():
        try:
            n = int(ID_SEQ_FILE.read_text().strip() or "0")
        except Exception:
            n = 0
    n += 1
    try:
        ID_SEQ_FILE.write_text(str(n))
    except Exception:
        pass
    return n

# -------------------------
# ENV labels/content
# -------------------------
MENU_LABEL   = os.getenv("MENU_BTN", "💕 Menu")
ADMINS_LABEL = os.getenv("ADMINS_BTN", "👑 Contact Admins")
FIND_LABEL   = os.getenv("FIND_MODELS_BTN", "🔥 Find Our Models Elsewhere")
HELP_LABEL   = os.getenv("HELP_BTN", "❓ Help")

RONI_NAME = (os.getenv("RONI_NAME") or "Roni").strip()
RONI_ID   = int((os.getenv("RONI_ID") or "0") or 0)
RUBY_NAME = (os.getenv("RUBY_NAME") or "Ruby").strip()
RUBY_ID   = int((os.getenv("RUBY_ID") or "0") or 0)

SUGGESTIONS_CHAT_ID = int((os.getenv("SUGGESTIONS_CHAT_ID") or os.getenv("OWNER_ID") or "0") or 0)

FIND_MODELS_TEXT        = (os.getenv("FIND_MODELS_TEXT") or os.getenv("FIND_MODELS") or "").strip()
HELP_INTRO              = os.getenv("HELP_INTRO", "Here’s what I can help with:").strip()
BUYER_RULES_TEXT        = (os.getenv("BUYER_RULES_TEXT") or "").strip()
BUYER_REQUIREMENTS_TEXT = (os.getenv("BUYER_REQUIREMENTS_TEXT") or "").strip()
GAME_RULES_TEXT         = (os.getenv("GAME_RULES_TEXT") or "").strip()
EXEMPTIONS_TEXT         = (os.getenv("EXEMPTIONS_TEXT") or "").strip()

# -------------------------
# UI helpers
# -------------------------
def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _url(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, url=url)

def _kb(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows)

def _tg_link(name: str, tid: int) -> InlineKeyboardButton:
    if tid:
        return _url(f"📩 Contact {name}", f"tg://user?id={tid}")
    return _btn(f"📩 Contact {name}", "noop")  # visible but inert if no ID

# -------------------------
# Public renderer (called by /start module or other callbacks)
# -------------------------
async def main_menu(msg: Message):
    """Render the 4-button main panel under the welcome. No duplication here."""
    rows = [
        [ _btn(MENU_LABEL, "menu") ],             # handled ONLY by handlers/menu.py
        [ _btn(ADMINS_LABEL, "nav:admins") ],
        [ _btn(FIND_LABEL, "nav:find") ],
        [ _btn(HELP_LABEL, "nav:help") ],
    ]
    await msg.reply_text(
        "✨ <i>Use the menu below to navigate!</i>",
        reply_markup=_kb(rows),
        disable_web_page_preview=True
    )

# -------------------------
# Internal renderers
# -------------------------
async def _render_admins(msg: Message):
    rows: List[List[InlineKeyboardButton]] = [
        [ _tg_link(RONI_NAME, RONI_ID) ],
        [ _tg_link(RUBY_NAME, RUBY_ID) ],
        [ _btn("🕵️ Anonymous Suggestions", "contact:anon") ],
        [ _btn("⬅️ Back to Main", "nav:main") ],
    ]
    await msg.edit_text("<b>Contact Admins</b>\nChoose how you want to reach us:",
                        reply_markup=_kb(rows), disable_web_page_preview=True)

async def _render_find(msg: Message):
    text = FIND_MODELS_TEXT or "Ask an admin where to find our models elsewhere."
    rows = [[ _btn("⬅️ Back to Main", "nav:main") ]]
    await msg.edit_text(text, reply_markup=_kb(rows), disable_web_page_preview=False)

def _help_rows() -> List[List[InlineKeyboardButton]]:
    rows: List[List[InlineKeyboardButton]] = []
    sub: List[InlineKeyboardButton] = []
    if BUYER_RULES_TEXT:        sub.append(_btn("📜 Buyer Rules", "help:rules"))
    if BUYER_REQUIREMENTS_TEXT: sub.append(_btn("🧾 Buyer Requirements", "help:reqs"))
    if sub: rows.append(sub); sub = []
    if GAME_RULES_TEXT:         sub.append(_btn("🎲 Game Rules", "help:games"))
    if EXEMPTIONS_TEXT:         sub.append(_btn("🛡️ Exemptions", "help:exempt"))
    if sub: rows.append(sub)
    rows.append([ _btn("⬅️ Back to Main", "nav:main") ])
    return rows

async def _render_help(msg: Message):
    await msg.edit_text(f"❓ <b>Help</b>\n{HELP_INTRO}",
                        reply_markup=_kb(_help_rows()),
                        disable_web_page_preview=True)

async def _render_help_section(msg: Message, text: str, title: str):
    rows = [[ _btn("⬅️ Back to Help", "nav:help") ]]
    await msg.edit_text(f"<b>{title}</b>\n{text}", reply_markup=_kb(rows),
                        disable_web_page_preview=False)

# -------------------------
# Anonymous suggestions flow
# -------------------------
def _get_state() -> Dict[str, Dict]:
    return _read_json(STATE_FILE)

def _set_state(d: Dict[str, Dict]):
    _write_json(STATE_FILE, d)

def _get_suggs() -> Dict[str, Dict]:
    return _read_json(SUGG_FILE)

def _set_suggs(d: Dict[str, Dict]):
    _write_json(SUGG_FILE, d)

async def _start_anon_prompt(msg: Message, user_id: int):
    st = _get_state(); st[str(user_id)] = {"awaiting": True, "from_chat": msg.chat.id}
    _set_state(st)
    rows = [[ _btn("❌ Cancel", "contact:anon_cancel") ]]
    await msg.edit_text(
        "🕵️ <b>Anonymous Suggestions</b>\n"
        "Send your suggestion now (text only). I’ll forward it anonymously to the admins.\n\n"
        "Tap <b>Cancel</b> to abort.",
        reply_markup=_kb(rows), disable_web_page_preview=True
    )

async def _cancel_anon(user_id: int):
    st = _get_state()
    if str(user_id) in st:
        st.pop(str(user_id), None)
        _set_state(st)

# -------------------------
# Registration — NO `/start` here
# -------------------------
def register(app: Client):

    @app.on_callback_query(filters.regex(r"^(nav:main|nav:root|back_main)$"))
    async def _go_main(c: Client, cq: CallbackQuery):
        await main_menu(cq.message); await cq.answer()

    @app.on_callback_query(filters.regex(r"^nav:admins$"))
    async def _admins(c: Client, cq: CallbackQuery):
        await _render_admins(cq.message); await cq.answer()

    @app.on_callback_query(filters.regex(r"^contact:anon$"))
    async def _anon_start(c: Client, cq: CallbackQuery):
        await _start_anon_prompt(cq.message, cq.from_user.id); await cq.answer()

    @app.on_callback_query(filters.regex(r"^contact:anon_cancel$"))
    async def _anon_cancel(c: Client, cq: CallbackQuery):
        await _cancel_anon(cq.from_user.id)
        await cq.message.edit_text("Canceled. 👌", reply_markup=_kb([[ _btn("⬅️ Back to Main", "nav:main") ]]))
        await cq.answer()

    @app.on_message(filters.private & ~filters.command(["start", "createmenu", "addmenu", "menudebug"]))
    async def _capture_anon(c: Client, m: Message):
        st = _get_state()
        entry = st.get(str(m.from_user.id))
        if not entry or not entry.get("awaiting"):
            return
        text = (m.text or "").strip()
        if not text:
            return await m.reply_text("Please send your suggestion as text.")
        sid = _next_sugg_id()
        suggs = _get_suggs(); suggs[str(sid)] = {"user_id": m.from_user.id, "text": text}
        _set_suggs(suggs)
        if SUGGESTIONS_CHAT_ID:
            try:
                await c.send_message(
                    SUGGESTIONS_CHAT_ID,
                    f"🕵️ <b>New Anonymous Suggestion</b>\n"
                    f"ID: <code>{sid}</code>\n"
                    f"Message:\n{text}\n\n"
                    f"Reply with: <code>/sreply {sid} &lt;your reply&gt;</code>"
                )
            except Exception:
                pass
        await _cancel_anon(m.from_user.id)
        await m.reply_text("✅ Sent anonymously to admins. Thanks!")

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
        user_id = entry.get("user_id")
        if not user_id:
            return await m.reply_text("Missing user for that suggestion.")
        try:
            await c.send_message(user_id, f"🛡️ <b>Admin Reply</b>\n{reply_text}")
            await m.reply_text("✅ Reply delivered.")
        except Exception as e:
            await m.reply_text(f"Could not deliver reply: {e}")

    @app.on_callback_query(filters.regex(r"^nav:find$"))
    async def _find(c: Client, cq: CallbackQuery):
        await _render_find(cq.message); await cq.answer()

    @app.on_callback_query(filters.regex(r"^nav:help$"))
    async def _help(c: Client, cq: CallbackQuery):
        await _render_help(cq.message); await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:rules$"))
    async def _help_rules(c: Client, cq: CallbackQuery):
        if not BUYER_RULES_TEXT:
            return await cq.answer("No Buyer Rules configured.", show_alert=True)
        await _render_help_section(cq.message, BUYER_RULES_TEXT, "📜 Buyer Rules"); await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:reqs$"))
    async def _help_reqs(c: Client, cq: CallbackQuery):
        if not BUYER_REQUIREMENTS_TEXT:
            return await cq.answer("No Buyer Requirements configured.", show_alert=True)
        await _render_help_section(cq.message, BUYER_REQUIREMENTS_TEXT, "🧾 Buyer Requirements"); await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:games$"))
    async def _help_games(c: Client, cq: CallbackQuery):
        if not GAME_RULES_TEXT:
            return await cq.answer("No Game Rules configured.", show_alert=True)
        await _render_help_section(cq.message, GAME_RULES_TEXT, "🎲 Game Rules"); await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:exempt$"))
    async def _help_exempt(c: Client, cq: CallbackQuery):
        if not EXEMPTIONS_TEXT:
            return await cq.answer("No Exemptions configured.", show_alert=True)
        await _render_help_section(cq.message, EXEMPTIONS_TEXT, "🛡️ Exemptions"); await cq.answer()
