# handlers/help_menu.py
# Role-aware Help with submenus and clean Back navigation.
# - Callback entry: dmf_show_help   (from your portal)
# - Submenus: buyer requirements/rules/games, commands
# - Members see only member commands
# - Admins see member + admin commands
#
# Depends on env:
#   OWNER_ID, SUPER_ADMIN_ID (ints)
# Optional: RULES_TEXT, BUYER_REQ_TEXT (HTML)

import os
from typing import Optional, Set

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# --------- Config / IDs ----------
def _to_int(s: Optional[str]) -> Optional[int]:
    try:
        return int(str(s)) if s not in (None, "", "None") else None
    except Exception:
        return None

OWNER_ID       = _to_int(os.getenv("OWNER_ID"))
SUPER_ADMIN_ID = _to_int(os.getenv("SUPER_ADMIN_ID"))

# If you’ve got extra admins in your req_store you can merge them in at runtime too
_EXTRA_ADMINS: Set[int] = set()
if os.getenv("MENU_EDITORS"):
    for tok in os.getenv("MENU_EDITORS").split(","):
        v = _to_int(tok.strip())
        if v:
            _EXTRA_ADMINS.add(v)

ADMIN_IDS: Set[int] = set(i for i in (OWNER_ID, SUPER_ADMIN_ID) if i) | _EXTRA_ADMINS

# --------- Text (env overrides ok) ----------
RULES_TEXT = os.getenv("RULES_TEXT") or (
    "📜 <b>Buyer Rules</b>\n\n"
    "1) Respect the models — no harassment or guilt-tripping.\n"
    "2) No freeloading / begging for free content.\n"
    "3) Follow payment & delivery instructions posted by the team.\n"
)

BUYER_REQ_TEXT = os.getenv("BUYER_REQ_TEXT") or (
    "💸 <b>Buyer Requirements</b>\n\n"
    "To stay in the group each month, complete at least ONE:\n"
    "• Spend $20+ (tips/games/content), or\n"
    "• Join 4+ games.\n"
)

GAME_RULES_TEXT = (
    "🎲 <b>Succubus Sanctuary Game Rules</b>\n\n"
    "🕯️ <b>Candle Temptation Game</b>\n"
    "• $5 lights a random candle. 3 candles for a model = her spicy surprise.\n"
    "• All 12 candles by end = special group reward.\n\n"
    "🍑 <b>Pick a Peach</b>\n"
    "• Pick 1–12 and tip $5. Each number hides a model’s surprise.\n"
    "• No repeats per model; spread the love.\n\n"
    "💃 <b>Flash Frenzy</b>\n"
    "• $5 triggers a flash by the chosen girl. Stacks for back-to-back flashes.\n\n"
    "🎰 <b>Dirty Wheel Spins</b>\n"
    "• $10 per spin. Whatever it lands on is the prize. Add jackpots like “double prize”.\n\n"
    "🎲 <b>Dice Roll Game</b>\n"
    "• $5 per roll (1–6). Number = prize. Two dice variant for bigger pools.\n\n"
    "🔥 <b>Forbidden Folder Friday</b>\n"
    "• $80 premium folder (photos + clips), limited-time each Friday.\n"
    "• Pay Ruby; Roni delivers the Dropbox link. Closes at midnight.\n"
)

# --------- Command catalogs (display only) ----------
# What regular members are allowed to SEE (safe/fun/self-service)
MEMBER_COMMANDS = [
    "/help — open this help",
    "/menu — open model menus",
    "/rules — show buyer rules",
    # add your fun/summon/etc here if you want them listed:
    # "/summon @user — tag someone",
    # "/flirtysummon @user — flirty tag",
]

# Admin-only commands (will be shown ONLY to admins)
ADMIN_ONLY_COMMANDS = [
    # requirements (no self-service for members)
    "/reqadd — add purchase amount for a user",
    "/reqgame — add a game for a user",
    # moderation / ops (examples, match your actual handlers)
    "/warn, /resetwarns, /mute, /unmute, /ban, /kick",
    "/fedban, /fedunban, /fedcheck, /togglefedaction",
    "/addflyer, /changeflyer, /deleteflyer, /listflyers, /flyer",
    "/dmready, /dmunready, /dmreadylist, /dmnudge",
]

# --------- UI builders ----------
def _help_root_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💸 Buyer Requirements", callback_data="help:reqs")],
        [InlineKeyboardButton("📜 Buyer Rules", callback_data="help:rules")],
        [InlineKeyboardButton("🎮 Game Rules", callback_data="help:games")],
        [InlineKeyboardButton("🧰 Commands", callback_data="help:cmds_member")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🛡 Admin Commands", callback_data="help:cmds_admin")])
    # Back row (to your portal + menu)
    rows.append([InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")])
    rows.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")])
    return InlineKeyboardMarkup(rows)

def _back_to_help_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("⬅️ Back to Help", callback_data="dmf_show_help")]]
    rows.append([InlineKeyboardButton("⬅️ Back to Welcome", callback_data="dmf_back_welcome")])
    rows.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="dmf_open_menu")])
    return InlineKeyboardMarkup(rows)

# --------- helpers ----------
def _is_admin(uid: Optional[int]) -> bool:
    return bool(uid and uid in ADMIN_IDS)

# --------- register ----------
def register(app: Client):

    # Entry point from your portal Help button
    @app.on_callback_query(filters.regex(r"^dmf_show_help$"))
    async def cb_help_root(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        is_admin = _is_admin(uid)
        try:
            await cq.message.edit_text("❓ <b>Help</b>\nPick a topic:", reply_markup=_help_root_kb(is_admin), disable_web_page_preview=True)
        except Exception:
            await cq.message.reply_text("❓ <b>Help</b>\nPick a topic:", reply_markup=_help_root_kb(is_admin), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^help:reqs$"))
    async def cb_help_reqs(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        is_admin = _is_admin(uid)
        await _edit_or_reply(cq, BUYER_REQ_TEXT, _back_to_help_kb(is_admin))

    @app.on_callback_query(filters.regex(r"^help:rules$"))
    async def cb_help_rules(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        is_admin = _is_admin(uid)
        await _edit_or_reply(cq, RULES_TEXT, _back_to_help_kb(is_admin))

    @app.on_callback_query(filters.regex(r"^help:games$"))
    async def cb_help_games(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        is_admin = _is_admin(uid)
        await _edit_or_reply(cq, GAME_RULES_TEXT, _back_to_help_kb(is_admin))

    # Member-visible commands (filtered)
    @app.on_callback_query(filters.regex(r"^help:cmds_member$"))
    async def cb_help_cmds_member(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        is_admin = _is_admin(uid)
        text = "📌 <b>Available Commands</b>\n\n" + "\n".join(MEMBER_COMMANDS)
        await _edit_or_reply(cq, text, _back_to_help_kb(is_admin))

    # Admin-only commands list (only reachable if admin)
    @app.on_callback_query(filters.regex(r"^help:cmds_admin$"))
    async def cb_help_cmds_admin(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id if cq.from_user else None
        if not _is_admin(uid):
            # Silent ignore or send a gentle notice
            try:
                await cq.answer("Admins only.", show_alert=True)
            except Exception:
                pass
            return
        text = "🛡 <b>Admin Commands</b>\n\n" + "\n".join(ADMIN_ONLY_COMMANDS)
        await _edit_or_reply(cq, text, _back_to_help_kb(True))

# --------- local util ----------
async def _edit_or_reply(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await cq.message.reply_text(text, reply_markup=kb, disable_web_page_preview=True)
    await cq.answer()
