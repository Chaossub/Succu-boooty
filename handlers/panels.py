# handlers/panels.py
import os
from typing import Optional, List
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ========= Core Admin ENV =========
RONI_ID   = os.getenv("RONI_ID")
RUBY_ID   = os.getenv("RUBY_ID")
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RONI_UN   = os.getenv("RONI_USERNAME")   # e.g. Chaossub283  (no @)
RUBY_UN   = os.getenv("RUBY_USERNAME")

# Fallbacks so Roni NEVER disappears
OWNER_ID        = os.getenv("OWNER_ID")
OWNER_USERNAME  = os.getenv("OWNER_USERNAME")

# ========= Links / Help ENV =========
# Preferred: comma-separated "Label|URL" pairs
MODELS_LINKS = os.getenv("MODELS_LINKS", "").strip()
HELP_LINKS   = os.getenv("HELP_LINKS", "").strip()

# Per-site fallbacks for Models Elsewhere (used when MODELS_LINKS is empty)
ALLMYLINKS_URL = os.getenv("ALLMYLINKS_URL", "").strip()
FANSLY_URL     = os.getenv("FANSLY_URL", "").strip()
ONLYFANS_URL   = os.getenv("ONLYFANS_URL", "").strip()
BLUESKY_URL    = os.getenv("BLUESKY_URL", "").strip()
LINKTREE_URL   = os.getenv("LINKTREE_URL", "").strip()
INSTAGRAM_URL  = os.getenv("INSTAGRAM_URL", "").strip()
TWITTER_URL    = os.getenv("TWITTER_URL", "").strip()
TIKTOK_URL     = os.getenv("TIKTOK_URL", "").strip()

# Per-item Help links (used when HELP_LINKS is empty)
HELP_BUYER_RULES_URL        = os.getenv("HELP_BUYER_RULES_URL", "").strip()
HELP_BUYER_REQUIREMENTS_URL = os.getenv("HELP_BUYER_REQUIREMENTS_URL", "").strip()
HELP_GAME_RULES_URL         = os.getenv("HELP_GAME_RULES_URL", "").strip()
HELP_EXEMPTIONS_URL         = os.getenv("HELP_EXEMPTIONS_URL", "").strip()

# ========= Small helpers =========
def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _back_main() -> List[List[InlineKeyboardButton]]:
    return [[_btn("⬅️ Back to Main", "nav:main")]]

def _user_url(username: Optional[str], numeric_id: Optional[str]) -> Optional[str]:
    if username:
        return f"https://t.me/{username.lstrip('@')}"
    if numeric_id:
        return f"https://t.me/user?id={int(numeric_id)}"
    return None

def _pairs_to_buttons(csv: str) -> List[List[InlineKeyboardButton]]:
    rows: List[List[InlineKeyboardButton]] = []
    if not csv:
        return rows
    for raw in csv.split(","):
        item = raw.strip()
        if not item:
            continue
        if "|" in item:
            label, url = [p.strip() for p in item.split("|", 1)]
            if label and url:
                rows.append([InlineKeyboardButton(label, url=url)])
    return rows

def _links_from_env() -> List[List[InlineKeyboardButton]]:
    """
    Build 'Find Our Models Elsewhere' buttons.
    Priority:
      1) MODELS_LINKS bulk string (Label|URL,Label|URL,...)
      2) Individual *_URL env fallbacks
    """
    rows = _pairs_to_buttons(MODELS_LINKS)
    if rows:
        return rows
    # Fallbacks:
    pairs = [
        ("AllMyLinks", ALLMYLINKS_URL),
        ("Fansly", FANSLY_URL),
        ("OnlyFans", ONLYFANS_URL),
        ("Bluesky", BLUESKY_URL),
        ("Linktree", LINKTREE_URL),
        ("Instagram", INSTAGRAM_URL),
        ("Twitter/X", TWITTER_URL),
        ("TikTok", TIKTOK_URL),
    ]
    rows = [[InlineKeyboardButton(lbl, url=url)] for (lbl, url) in pairs if url]
    return rows

def _help_buttons_from_env() -> List[List[InlineKeyboardButton]]:
    """
    Build Help panel.
    Priority:
      1) HELP_LINKS bulk string (Label|URL...)
      2) Explicit four buttons if URLs provided
    """
    rows = _pairs_to_buttons(HELP_LINKS)
    if rows:
        return rows

    specific = []
    if HELP_BUYER_RULES_URL:
        specific.append([InlineKeyboardButton("📜 Buyer Rules", url=HELP_BUYER_RULES_URL)])
    if HELP_BUYER_REQUIREMENTS_URL:
        specific.append([InlineKeyboardButton("✅ Buyer Requirements", url=HELP_BUYER_REQUIREMENTS_URL)])
    if HELP_GAME_RULES_URL:
        specific.append([InlineKeyboardButton("🎲 Game Rules", url=HELP_GAME_RULES_URL)])
    if HELP_EXEMPTIONS_URL:
        specific.append([InlineKeyboardButton("🕊️ Exemptions", url=HELP_EXEMPTIONS_URL)])

    return specific

# ========= Panels =========
async def render_main(msg: Message):
    rows = [
        [_btn("💕 Menu", "nav:menu")],
        [_btn("👑 Contact Admins", "nav:contact")],
        [_btn("🔥 Find Our Models Elsewhere", "nav:links")],
        [_btn("❓ Help", "nav:help")],
    ]
    kb = InlineKeyboardMarkup(rows)
    await msg.edit_text(
        "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
        "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
        "✨ <i>Use the menu below to navigate!</i>",
        reply_markup=kb,
        disable_web_page_preview=True
    )

async def render_menu(msg: Message):
    # You can swap to your dynamic menu store if desired
    rows = [
        [_btn("💘 Roni", "menu:roni"), _btn("💘 Ruby", "menu:ruby")],
        [_btn("💘 Rin", "menu:rin"), _btn("💘 Savy", "menu:savy")],
    ] + _back_main()
    await msg.edit_text(
        "💕 <b>Menus</b>\nPick a model whose menu is saved.",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True
    )

async def render_contact(msg: Message):
    rows: List[List[InlineKeyboardButton]] = []

    # Roni must always show: use explicit RONI_* or fallback to OWNER_*
    roni_url = _user_url(RONI_UN or OWNER_USERNAME, RONI_ID or OWNER_ID)
    ruby_url = _user_url(RUBY_UN, RUBY_ID)

    if roni_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RONI_NAME}", url=roni_url)])
    if ruby_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RUBY_NAME}", url=ruby_url)])

    rows.append([_btn("🕵️ Anonymous Message", "contact:anon")])
    rows += _back_main()

    await msg.edit_text(
        "👑 <b>Contact Admins</b>\n\n• Tag an admin in chat\n• Or send an anonymous message via the bot.",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True
    )

async def render_help(msg: Message):
    rows = _help_buttons_from_env() + _back_main()
    await msg.edit_text(
        "❓ <b>Help</b>\nTap a button below, or ping an admin if you’re stuck.",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True
    )

async def render_links(msg: Message):
    rows = _links_from_env() + _back_main()
    await msg.edit_text(
        "🔥 <b>Find Our Models Elsewhere</b>",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True
    )

# ========= Wiring =========
def register(app: Client):
    @app.on_callback_query(filters.regex("^nav:main$"))
    async def _go_main(c, cq): await render_main(cq.message)

    @app.on_callback_query(filters.regex("^nav:menu$"))
    async def _go_menu(c, cq): await render_menu(cq.message)

    @app.on_callback_query(filters.regex("^nav:contact$"))
    async def _go_contact(c, cq): await render_contact(cq.message)

    @app.on_callback_query(filters.regex("^nav:help$"))
    async def _go_help(c, cq): await render_help(cq.message)

    @app.on_callback_query(filters.regex("^nav:links$"))
    async def _go_links(c, cq): await render_links(cq.message)

    # Optional mirrored commands
    @app.on_message(filters.private & filters.command("menu"))
    async def _cmd_menu(c, m):
        ph = await m.reply_text("…")
        await render_menu(ph)

    @app.on_message(filters.private & filters.command("contact"))
    async def _cmd_contact(c, m):
        ph = await m.reply_text("…")
        await render_contact(ph)

    @app.on_message(filters.private & filters.command("help"))
    async def _cmd_help(c, m):
        ph = await m.reply_text("…")
        await render_help(ph)
