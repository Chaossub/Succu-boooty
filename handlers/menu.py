# handlers/menu.py
import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.client import Client

# =========================
# ENV EXPECTATIONS
# =========================
# Usernames (without @) for DM links
#   RONI_USERNAME, RUBY_USERNAME, RIN_USERNAME, SAVY_USERNAME
#
# Per-model menu texts
#   MENU_RONI, MENU_RUBY, MENU_RIN, MENU_SAVY
#
# Misc content
#   WELCOME_TEXT
#   MODELS_ELSEWHERE_TEXT
#   BUYER_RULES_TEXT
#   BUYER_REQUIREMENTS_TEXT
#   GAME_RULES_TEXT
#   COMMANDS_HELP_TEXT
#
# Everything is optional; sensible defaults are provided if missing.

_WIRED = False  # idempotent guard so we don't register twice


# ---------- helpers ----------

def _t(name: str, default: str = "") -> str:
    val = os.environ.get(name)
    if val is None or str(val).strip() == "":
        return default
    return val

def _dm_url(username_var: str) -> str | None:
    u = os.environ.get(username_var)
    if not u:
        return None
    u = u.lstrip("@")
    return f"https://t.me/{u}"

async def _safe_edit(msg: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None):
    try:
        await msg.edit_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception as e:
        # Ignore MESSAGE_NOT_MODIFIED or similar benign errors
        if "MESSAGE_NOT_MODIFIED" not in str(e):
            raise

def _is_pm(q: CallbackQuery) -> bool:
    # Inlined convenience if you ever want to branch later
    return q.message and q.message.chat and q.message.chat.type in ("private",)

# ---------- text blocks ----------

WELCOME = _t(
    "WELCOME_TEXT",
    "👑 Welcome to **Succubus Sanctuary** 👑\n\n"
    "Tap a button below to browse menus, contact admins, or get help."
)

# Per-model menu text defaults
MENU_TEXT = {
    "roni": _t("MENU_RONI", "🍓 **Roni's Menu**\n(Your custom menu text goes here.)"),
    "ruby": _t("MENU_RUBY", "💎 **Ruby's Menu**\n(Your custom menu text goes here.)"),
    "rin":  _t("MENU_RIN",  "🌙 **Rin's Menu**\n(Your custom menu text goes here.)"),
    "savy": _t("MENU_SAVY", "🔥 **Savy's Menu**\n(Your custom menu text goes here.)"),
}

MODELS_ELSEWHERE_TEXT = _t(
    "MODELS_ELSEWHERE_TEXT",
    "🌐 **Find Our Models Elsewhere**\n(Links/content from ENV will appear here.)"
)

BUYER_RULES_TEXT = _t(
    "BUYER_RULES_TEXT",
    "📜 **Buyer Rules**\n(Your rules text from ENV will appear here.)"
)

BUYER_REQUIREMENTS_TEXT = _t(
    "BUYER_REQUIREMENTS_TEXT",
    "🧾 **Buyer Requirements**\n(Your requirements text from ENV will appear here.)"
)

GAME_RULES_TEXT = _t(
    "GAME_RULES_TEXT",
    "🎲 **Game Rules & Extras**\n(Your games text from ENV will appear here.)"
)

COMMANDS_HELP_TEXT = _t(
    "COMMANDS_HELP_TEXT",
    "❓ **Member Commands**\n(Only the commands members can use.)"
)

# ---------- keyboards ----------

def kb_main() -> InlineKeyboardMarkup:
    # Single-column main menu (exactly as requested)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗂️ Menus", callback_data="menus")],
            [InlineKeyboardButton("🔎 Find our models elsewhere", callback_data="elsewhere")],
            [InlineKeyboardButton("🛎️ Contact Admins", callback_data="admins")],
            [InlineKeyboardButton("🆘 Help", callback_data="help")],
        ]
    )

def kb_menus() -> InlineKeyboardMarkup:
    # 2x2 for model names, then Contact Models (full), then Back to Main (full)
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Roni", callback_data="model:roni"),
             InlineKeyboardButton("Ruby", callback_data="model:ruby")],
            [InlineKeyboardButton("Rin", callback_data="model:rin"),
             InlineKeyboardButton("Savy", callback_data="model:savy")],
            [InlineKeyboardButton("✉️ Contact Models", callback_data="contact_models")],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main")],
        ]
    )

def kb_model(name_key: str) -> InlineKeyboardMarkup:
    # Two buttons beneath the menu: Book (DM link) + Tip (coming soon)
    dm_map = {
        "roni": "RONI_USERNAME",
        "ruby": "RUBY_USERNAME",
        "rin":  "RIN_USERNAME",
        "savy": "SAVY_USERNAME",
    }
    dm = _dm_url(dm_map[name_key])
    book_btn = InlineKeyboardButton(f"📩 Book {name_key.capitalize()}", url=dm) if dm else InlineKeyboardButton(
        f"📩 Book {name_key.capitalize()} (setup needed)", callback_data="noop")
    tip_btn = InlineKeyboardButton(f"💖 Tip {name_key.capitalize()} (coming soon)", callback_data=f"tip:{name_key}")

    return InlineKeyboardMarkup(
        [
            [book_btn, tip_btn],
            [InlineKeyboardButton("⬅️ Back to Menus", callback_data="menus")],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main")],
        ]
    )

def kb_contact_models() -> InlineKeyboardMarkup:
    # 2x2 DM links; only Back to Main at bottom (as requested)
    pairs = []
    row = []
    for key, envvar in [("Roni", "RONI_USERNAME"),
                        ("Ruby", "RUBY_USERNAME"),
                        ("Rin",  "RIN_USERNAME"),
                        ("Savy", "SAVY_USERNAME")]:
        url = _dm_url(envvar)
        btn = InlineKeyboardButton(key, url=url) if url else InlineKeyboardButton(f"{key} (setup needed)", callback_data="noop")
        row.append(btn)
        if len(row) == 2:
            pairs.append(row)
            row = []
    if row:
        pairs.append(row)

    pairs.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main")])
    return InlineKeyboardMarkup(pairs)

def kb_admins() -> InlineKeyboardMarkup:
    # 2x2 grid: Message Roni, Message Ruby, Suggestions, Anonymous
    roni = _dm_url("RONI_USERNAME")
    ruby = _dm_url("RUBY_USERNAME")

    roni_btn = InlineKeyboardButton("💬 Message Roni", url=roni) if roni else InlineKeyboardButton("💬 Message Roni (setup)", callback_data="noop")
    ruby_btn = InlineKeyboardButton("💬 Message Ruby", url=ruby) if ruby else InlineKeyboardButton("💬 Message Ruby (setup)", callback_data="noop")

    grid = [
        [roni_btn, ruby_btn],
        [InlineKeyboardButton("💡 Suggestions", callback_data="suggestions"),
         InlineKeyboardButton("🕵️ Anonymous Message", callback_data="anon")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main")],
    ]
    return InlineKeyboardMarkup(grid)

def kb_help() -> InlineKeyboardMarkup:
    # 2x2 for four items, then Back to Main
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 Buyer Rules", callback_data="help:rules"),
             InlineKeyboardButton("🧾 Requirements", callback_data="help:reqs")],
            [InlineKeyboardButton("🎲 Game Rules", callback_data="help:games"),
             InlineKeyboardButton("❓ Commands Help", callback_data="help:cmds")],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main")],
        ]
    )

def kb_back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main")]])


# ---------- callbacks ----------

async def _show_main(msg: Message):
    await _safe_edit(msg, WELCOME, kb_main())

async def _on_start(client: Client, message: Message):
    # /start and /portal should show the Main Menu + Welcome text
    await message.reply_text(WELCOME, reply_markup=kb_main(), disable_web_page_preview=True)

async def _cb_main(client: Client, q: CallbackQuery):
    await q.answer()
    await _show_main(q.message)

async def _cb_menus(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "🗂️ Menus", kb_menus())

async def _cb_model(client: Client, q: CallbackQuery):
    await q.answer()
    key = q.data.split(":", 1)[1]
    text = MENU_TEXT.get(key, f"**{key.capitalize()}'s Menu**")
    await _safe_edit(q.message, text, kb_model(key))

async def _cb_contact_models(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "✉️ Contact Models", kb_contact_models())

async def _cb_elsewhere(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, MODELS_ELSEWHERE_TEXT, kb_back_to_main())

async def _cb_admins(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "🛎️ Contact Admins", kb_admins())

async def _cb_help_home(client: Client, q: CallbackQuery):
    await q.answer()
    await _safe_edit(q.message, "🆘 Help", kb_help())

async def _cb_help_leaf(client: Client, q: CallbackQuery):
    await q.answer()
    leaf = q.data.split(":", 1)[1]
    if leaf == "rules":
        await _safe_edit(q.message, BUYER_RULES_TEXT, kb_back_to_main())
    elif leaf == "reqs":
        await _safe_edit(q.message, BUYER_REQUIREMENTS_TEXT, kb_back_to_main())
    elif leaf == "games":
        await _safe_edit(q.message, GAME_RULES_TEXT, kb_back_to_main())
    elif leaf == "cmds":
        await _safe_edit(q.message, COMMANDS_HELP_TEXT, kb_back_to_main())
    else:
        await _safe_edit(q.message, "Coming soon.", kb_back_to_main())

async def _cb_tip(client: Client, q: CallbackQuery):
    await q.answer("Coming soon 💖", show_alert=False)

async def _cb_noop(client: Client, q: CallbackQuery):
    await q.answer("Not configured yet.", show_alert=False)


# ---------- public register ----------

def register(app: Client):
    global _WIRED
    if _WIRED:
        return
    _WIRED = True

    # Commands to open the portal
    app.add_handler(
        handler=app.on_message(filters.command(["start", "portal"]))(  # no filters.edited here
            _on_start
        ).handler
    )

    # Callback routes
    app.add_handler(app.on_callback_query(filters.regex(r"^main$"))(_cb_main).handler)
    app.add_handler(app.on_callback_query(filters.regex(r"^menus$"))(_cb_menus).handler)
    app.add_handler(app.on_callback_query(filters.regex(r"^model:(roni|ruby|rin|savy)$"))(_cb_model).handler)
    app.add_handler(app.on_callback_query(filters.regex(r"^contact_models$"))(_cb_contact_models).handler)

    app.add_handler(app.on_callback_query(filters.regex(r"^elsewhere$"))(_cb_elsewhere).handler)

    app.add_handler(app.on_callback_query(filters.regex(r"^admins$"))(_cb_admins).handler)
    app.add_handler(app.on_callback_query(filters.regex(r"^help$"))(_cb_help_home).handler)
    app.add_handler(app.on_callback_query(filters.regex(r"^help:(rules|reqs|games|cmds)$"))(_cb_help_leaf).handler)

    app.add_handler(app.on_callback_query(filters.regex(r"^tip:(roni|ruby|rin|savy)$"))(_cb_tip).handler)
    app.add_handler(app.on_callback_query(filters.regex(r"^noop$"))(_cb_noop).handler)
