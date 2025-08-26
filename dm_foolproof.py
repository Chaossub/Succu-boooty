# dm_foolproof.py
import os
import logging
from typing import Optional, Set

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType

log = logging.getLogger("SuccuBot")

# ──────────────────────────────────────────────────────────────────────────────
# Env content for links / texts
# ──────────────────────────────────────────────────────────────────────────────
FIND_MODELS_ELSEWHERE = os.getenv("FIND_MODELS_ELSEWHERE", "https://example.com")
BUYER_RULES_TEXT = os.getenv("BUYER_RULES_TEXT", "Buyer rules are not configured.")
BUYER_REQUIREMENTS_TEXT = os.getenv("BUYER_REQUIREMENTS_TEXT", "Buyer requirements are not configured.")
GAME_RULES_TEXT = os.getenv("GAME_RULES_TEXT", "Game rules are not configured.")

# Admin usernames for DM routing (e.g., @RoniJane, @Ruby)
ADMIN_RONI = os.getenv("ADMIN_RONI_USERNAME", "")
ADMIN_RUBY = os.getenv("ADMIN_RUBY_USERNAME", "")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

# For when Mongo isn't available
_memory_dmready: Set[int] = set()

# ──────────────────────────────────────────────────────────────────────────────
# Keyboards
# ──────────────────────────────────────────────────────────────────────────────
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💕 Menu", callback_data="m:menus")],
            [InlineKeyboardButton("👑 Contact Admins", callback_data="m:admins")],
            [InlineKeyboardButton("💞 Contact Models", callback_data="m:contact_models")],
            [InlineKeyboardButton("🔥 Find Our Models Elsewhere", url=FIND_MODELS_ELSEWHERE)],
            [InlineKeyboardButton("❓ Help", callback_data="m:help")],
        ]
    )

def kb_menus() -> InlineKeyboardMarkup:
    # Top row is the “contact a model directly” expanded list (your core four)
    rows = [
        [InlineKeyboardButton("💌 Ruby ↗", url=f"https://t.me/{os.getenv('MODEL_RUBY_USERNAME','')}")],
        [
            InlineKeyboardButton("💌 Rin ↗", url=f"https://t.me/{os.getenv('MODEL_RIN_USERNAME','')}"),
            InlineKeyboardButton("💌 Savy ↗", url=f"https://t.me/{os.getenv('MODEL_SAVY_USERNAME','')}"),
        ],
        [InlineKeyboardButton("⬅️ Back to Menus", callback_data="m:main")],
    ]
    # Optional: Roni (some deployments asked to ensure Roni appears)
    roni = os.getenv("MODEL_RONI_USERNAME")
    if roni:
        rows.insert(0, [InlineKeyboardButton("💌 Roni ↗", url=f"https://t.me/{roni}")])
    return InlineKeyboardMarkup(rows)

def kb_admins() -> InlineKeyboardMarkup:
    rows = []
    if ADMIN_RONI:
        rows.append([InlineKeyboardButton("👑 DM Roni", url=f"https://t.me/{ADMIN_RONI}")])
    if ADMIN_RUBY:
        rows.append([InlineKeyboardButton("👑 DM Ruby", url=f"https://t.me/{ADMIN_RUBY}")])
    rows += [
        [InlineKeyboardButton("🕵️ Anonymous Message", callback_data="m:anon")],
        [InlineKeyboardButton("💡 Suggestion Box", callback_data="m:suggest")],
        [InlineKeyboardButton("⬅️ Back", callback_data="m:main")],
    ]
    return InlineKeyboardMarkup(rows)

def kb_help() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📜 Buyer Rules", callback_data="h:rules")],
            [InlineKeyboardButton("✅ Buyer Requirements", callback_data="h:reqs")],
            [InlineKeyboardButton("🆘 Member Commands", callback_data="h:cmds")],
            [InlineKeyboardButton("🎮 Game Rules", callback_data="h:games")],
            [InlineKeyboardButton("⬅️ Back", callback_data="m:main")],
        ]
    )

# ──────────────────────────────────────────────────────────────────────────────
# DM-ready helpers
# ──────────────────────────────────────────────────────────────────────────────
def _already_dm_ready(mongo, user_id: int) -> bool:
    if mongo:
        col = mongo["succubot"]["dm_ready"]
        doc = col.find_one({"_id": user_id})
        return bool(doc)
    return user_id in _memory_dmready

def _mark_dm_ready_once(mongo, user_id: int, mention_html: str) -> Optional[str]:
    """
    Returns a status string to post (or None if already marked).
    """
    if _already_dm_ready(mongo, user_id):
        return None
    if mongo:
        col = mongo["succubot"]["dm_ready"]
        col.update_one({"_id": user_id}, {"$set": {"ready": True}}, upsert=True)
    else:
        _memory_dmready.add(user_id)
    return f"✅ DM-ready — {mention_html} just opened the portal."

# ──────────────────────────────────────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────────────────────────────────────
def wire(app, mongo_client=None, owner_id: int = 0):
    log.info("wired: dm_foolproof")

    @app.on_message(filters.private & filters.command(["start", "portal"]))
    async def start_cmd(_, m: Message):
        # Only private chats should get the menu
        if m.chat.type != ChatType.PRIVATE:
            return

        # Mark DM-ready exactly once
        try:
            status = _mark_dm_ready_once(
                mongo_client,
                m.from_user.id,
                m.from_user.mention(style="html"),
            )
            if status:
                await m.reply_text(status)
        except Exception as e:
            log.error("dm-ready mark failed: %s", e)

        # Send the welcome card with inline buttons
        await m.reply_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)

    # ── Callback navigation ───────────────────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^m:main$"))
    async def _back_main(_, q):
        await q.message.edit_text(WELCOME_TEXT, reply_markup=kb_main(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^m:menus$"))
    async def _menus(_, q):
        await q.message.edit_text("Contact a model directly:", reply_markup=kb_menus(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^m:admins$"))
    async def _admins(_, q):
        await q.message.edit_text("Contact Admins:", reply_markup=kb_admins(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^m:contact_models$"))
    async def _contact_models(_, q):
        # This opens the big directory list (all names) via another module if you have it.
        # For now, just bounce to Menus where core names live.
        await q.message.edit_text("Contact a model directly:", reply_markup=kb_menus(), disable_web_page_preview=True)
        await q.answer()

    # ── Help section ─────────────────────────────────────────────────────────
    @app.on_callback_query(filters.regex(r"^m:help$"))
    async def _help(_, q):
        await q.message.edit_text("Help", reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer()

    @app.on_callback_query(filters.regex(r"^h:rules$"))
    async def _h_rules(_, q):
        await q.message.edit_text(BUYER_RULES_TEXT, reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer("Buyer rules")

    @app.on_callback_query(filters.regex(r"^h:reqs$"))
    async def _h_reqs(_, q):
        await q.message.edit_text(BUYER_REQUIREMENTS_TEXT, reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer("Buyer requirements")

    @app.on_callback_query(filters.regex(r"^h:cmds$"))
    async def _h_cmds(_, q):
        cmds = (
            "🆘 <b>Member Commands</b>\n"
            "• /menu — open the main menu\n"
            "• /portal — same as /start\n"
            "• /help — open help panel\n"
        )
        await q.message.edit_text(cmds, reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer("Member commands")

    @app.on_callback_query(filters.regex(r"^h:games$"))
    async def _h_games(_, q):
        await q.message.edit_text(os.getenv("GAME_RULES_TEXT", GAME_RULES_TEXT), reply_markup=kb_help(), disable_web_page_preview=True)
        await q.answer("Game rules")

    # ── Anonymous / Suggestions (send to owner/admin DM) ─────────────────────
    async def _forward_to_owner(text: str, user):
        target = owner_id or (int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID") else 0)
        if not target:
            log.warning("No OWNER_ID set; dropping anon/suggestion.")
            return
        prefix = f"From @{user.username}" if user and user.username else "From an anonymous user"
        try:
            await app.send_message(target, f"📩 <b>Inbox</b>\n{prefix}:\n\n{text}")
        except Exception as e:
            log.error("Failed to forward to owner: %s", e)

    @app.on_callback_query(filters.regex(r"^m:anon$"))
    async def _anon_prompt(_, q):
        await q.answer()
        await q.message.edit_text(
            "🕵️ <b>Anonymous Message</b>\nSend me the message you want to forward to the admins. "
            "I won’t include your username.",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Cancel", callback_data="m:admins")]]),
        )
        app.set_parse_mode  # no-op keeping linter calm

        # next text only from this user counts
        @app.on_message(filters.private & filters.user(q.from_user.id))
        async def _catch_anon(__, m: Message):
            if m.text:
                await _forward_to_owner(m.text, user=None)
                await m.reply_text("✅ Sent anonymously to the admins.", reply_markup=kb_main())
            __.remove_handler(_catch_anon)  # remove this one-off handler

    @app.on_callback_query(filters.regex(r"^m:suggest$"))
    async def _suggest_prompt(_, q):
        await q.answer()
        await q.message.edit_text(
            "💡 <b>Suggestion Box</b>\nSend your suggestion. I’ll include your @username unless you start the message with the word <code>anonymous</code>.",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Cancel", callback_data="m:admins")]]),
        )

        @app.on_message(filters.private & filters.user(q.from_user.id))
        async def _catch_suggest(__, m: Message):
            if m.text:
                is_anon = m.text.strip().lower().startswith("anonymous")
                await _forward_to_owner(m.text if not is_anon else m.text[len("anonymous"):].strip(), None if is_anon else m.from_user)
                await m.reply_text("✅ Suggestion delivered.", reply_markup=kb_main())
            __.remove_handler(_catch_suggest)
