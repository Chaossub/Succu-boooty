# handlers/panels.py
# Model picker → show saved menu text + Book/Tip buttons
import os
from typing import List, Optional
from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message,
)
from utils.menu_store import store

# ======= CONFIG =======
_DEFAULT_MODELS = ["Roni", "Ruby", "Rin", "Savy"]
_MODELS_ENV = os.getenv("MODELS", "")
MODELS: List[str] = [x.strip() for x in _MODELS_ENV.split(",") if x.strip()] or _DEFAULT_MODELS

ROOT_CB   = "panels:root"
PICK_CB_P = "panels:pick:"
BOOK_CB_P = "panels:book:"
TIP_CB_P  = "panels:tip:"

def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").upper() if ch.isalnum())

def _clean(name: str) -> str:
    return (name or "").strip().strip("»«‘’“”\"'`").strip()

def _get_url(kind: str, name: str) -> Optional[str]:
    # e.g. RONI_TIP_URL / RONI_BOOK_URL (still supported for TIP);
    # for BOOK we prefer TG handle below.
    key = f"{_norm(name)}_{kind}_URL"
    return os.getenv(key)

def _get_tg_handle(name: str) -> Optional[str]:
    # Support either RONI_TG or RONI_USERNAME for flexibility
    for suffix in ("_TG", "_USERNAME"):
        v = os.getenv(f"{_norm(name)}{suffix}")
        if v:
            v = v.strip()
            if v.startswith("@"):
                v = v[1:]
            return v
    return None

# ───────────────────────────
# Safe edit helper (avoid MESSAGE_NOT_MODIFIED)
# ───────────────────────────
async def safe_edit(msg: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    current = (msg.text or msg.caption or "") or ""
    if current == text:
        # If content is the same, don’t edit — prevents 400 MESSAGE_NOT_MODIFIED.
        return
    try:
        await msg.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e:
        # swallow MESSAGE_NOT_MODIFIED and any minor race
        # you can log e if you like, but staying quiet keeps UX clean
        pass

# ───────────────────────────
# Keyboards
# ───────────────────────────
def _models_keyboard() -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for i, n in enumerate(MODELS, 1):
        row.append(InlineKeyboardButton(n, callback_data=f"{PICK_CB_P}{n}"))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton("⬅ back", callback_data="portal:home"),
        InlineKeyboardButton("🏠 main", callback_data="portal:home"),
    ])
    return InlineKeyboardMarkup(rows)

def _menu_keyboard(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 book", callback_data=f"{BOOK_CB_P}{name}")],
        [InlineKeyboardButton("💸 tip",  callback_data=f"{TIP_CB_P}{name}")],
        [InlineKeyboardButton("⬅ back",  callback_data=ROOT_CB)],
        [InlineKeyboardButton("🏠 main", callback_data="portal:home")],
    ])

def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💞 menus", callback_data=ROOT_CB)],
        [InlineKeyboardButton("🔐 contact admins", callback_data="contact_admins:open")],
        [InlineKeyboardButton("🍑 find our models elsewhere", callback_data="models_elsewhere:open")],
        [InlineKeyboardButton("❓ help", callback_data="help:open")],
    ])

# ───────────────────────────
# Handlers
# ───────────────────────────
def register(app):

    # /start — main entry screen (simple, cute text)
    @app.on_message(filters.command("start"))
    async def start_cmd(_, m: Message):
        await m.reply_text(
            "🔥 welcome to succubot!\n"
            "i’m your flirty little helper — tap a button below ✨",
            reply_markup=_main_keyboard(),
            disable_web_page_preview=True
        )

    # /menu — shortcut to model picker
    @app.on_message(filters.command("menu"))
    async def menu_cmd(_, m: Message):
        await m.reply_text("💕 choose a model:", reply_markup=_models_keyboard())

    # Back to model list (from inside menus)
    @app.on_callback_query(filters.regex(f"^{ROOT_CB}$"))
    async def back_to_models(_, cq: CallbackQuery):
        await safe_edit(cq.message, "💕 choose a model:", _models_keyboard())
        await cq.answer()

    # Pick a specific model → show its saved menu
    @app.on_callback_query(filters.regex(r"^panels:pick:.+"))
    async def pick_cb(_, cq: CallbackQuery):
        raw = cq.data[len(PICK_CB_P):]
        name = _clean(raw)
        text = store.get_menu(name) or "no menu saved yet.\n\nuse /createmenu <Name> <text…> to set one."
        content = f"{name} — menu\n\n{text}"
        await safe_edit(cq.message, content, _menu_keyboard(name))
        await cq.answer()

    # Book button → open model DM via handle from env
    @app.on_callback_query(filters.regex(r"^panels:book:.+"))
    async def book_cb(_, cq: CallbackQuery):
        name = _clean(cq.data[len(BOOK_CB_P):])
        handle = _get_tg_handle(name)
        if handle:
            # send a button that opens DM with the model + keep a back to main
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✉️ message {name}", url=f"https://t.me/{handle}")],
                [InlineKeyboardButton("⬅ back", callback_data="portal:home")]
            ])
            await cq.message.reply_text(f"📖 booking/messages for {name}", reply_markup=kb, disable_web_page_preview=True)
        else:
            # legacy fallback: if someone kept BOOK_URL in env
            url = _get_url("BOOK", name)
            if url:
                await cq.message.reply_text(f"📖 booking for {name}\n{url}")
            else:
                await cq.answer("no tg handle set for this model.", show_alert=True)

    # Tip button → open tip URL from env (stripe to be added later)
    @app.on_callback_query(filters.regex(r"^panels:tip:.+"))
    async def tip_cb(_, cq: CallbackQuery):
        name = _clean(cq.data[len(TIP_CB_P):])
        url = _get_url("TIP", name)
        if url:
            await cq.message.reply_text(f"💸 tip {name}\n{url}")
        else:
            await cq.answer("no tip link set for this model.", show_alert=True)

    # Home button(s) → return to main /start screen (your main.py listens to portal:home too)
    @app.on_callback_query(filters.regex("^portal:home$"))
    async def home_cb(_, cq: CallbackQuery):
        await safe_edit(
            cq.message,
            "🔥 welcome back to succubot!\n"
            "tap a button below ✨",
            _main_keyboard()
        )
        await cq.answer()
