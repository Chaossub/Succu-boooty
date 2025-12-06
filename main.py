# main.py 
import os
import logging
from typing import Set, List

from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatType
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

# ────────────── ENV ──────────────
API_ID   = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise ValueError("Missing API_ID / API_HASH / BOT_TOKEN")

FIND_MODELS_TEXT = os.getenv("FIND_MODELS_TEXT", "Nothing here yet 💕")

# Owner / admins / models for summon permissions
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))


def _parse_id_list(val: str | None) -> Set[int]:
    if not val:
        return set()
    out: Set[int] = set()
    for part in val.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            log.warning("main: bad ID in list: %r", part)
    return out


SUPER_ADMINS: Set[int] = _parse_id_list(os.getenv("SUPER_ADMINS"))
MODELS: Set[int] = _parse_id_list(os.getenv("MODELS"))


def _can_use_summon(user_id: int) -> bool:
    """
    Only:
    - OWNER_ID
    - MODELS
    - SUPER_ADMINS
    can use /summonall /summon.
    """
    if user_id == OWNER_ID:
        return True
    if user_id in MODELS:
        return True
    if user_id in SUPER_ADMINS:
        return True
    return False


def _chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
    return [items[i: i + chunk_size] for i in range(0, len(items), chunk_size)]


# ────────────── BOT INIT ──────────────
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)


def _try_register(module_path: str, name: str | None = None):
    mod_name = f"handlers.{module_path}"
    label = name or module_path
    try:
        mod = __import__(mod_name, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info("✅ Registered %s", mod_name)
        else:
            log.warning("%s has no register()", mod_name)
    except Exception as e:
        log.warning("Skipping %s (import/register failed): %s", mod_name, e)


def main():
    log.info("💋 Starting SuccuBot…")
    log.info(
        "Summon permissions: OWNER_ID=%s SUPER_ADMINS=%s MODELS=%s",
        OWNER_ID,
        SUPER_ADMINS,
        MODELS,
    )

    # Warm-up / optional
    _try_register("hi")                      # /hi (warm-up)

    # Core panels & menus (this contains /start; DON'T add another /start here)
    _try_register("panels")                  # Menus picker + home

    # Contact Admins & DM helpers
    _try_register("contact_admins")          # contact_admins:open + anon flow
    _try_register("dm_admin")
    _try_register("dm_ready")
    _try_register("dm_ready_admin")
    _try_register("dm_portal")               # legacy shim (+ optional /dmnow)
    _try_register("portal_cmd")              # /portal → DM button

    # ⭐ Roni personal assistant portal (/roni_portal + /start roni_assistant)
    _try_register("roni_portal")             # core portal UI + text blocks
    _try_register("roni_portal_age")         # age verification + AV admin

    # Help panel (buttons -> env text)
    _try_register("help_panel")              # help:open + pages

    # Menus persistence/creation
    _try_register("menu")                    # (mongo or json)
    _try_register("createmenu")

    # Moderation / warnings
    _try_register("moderation")
    _try_register("warnings")

    # Message scheduler
    _try_register("schedulemsg")

    # Flyers (ad-hoc send + CRUD)
    _try_register("flyer")                   # /addflyer /flyer /listflyers /deleteflyer /textflyer

    # Flyer scheduler (date/time -> post)
    _try_register("flyer_scheduler")

    # ⭐ Requirements panel (Requirements Help UI)
    _try_register("requirements_panel")

    # 🔻 Give both schedulers the running loop so they can post from their threads
    try:
        from handlers import flyer_scheduler as _fs
        _fs.set_main_loop(app.loop)
        log.info("✅ Set main loop for flyer_scheduler")
    except Exception as e:
        log.warning("Could not set main loop for flyer_scheduler: %s", e)

    try:
        from handlers import schedulemsg as _sm
        _sm.set_main_loop(app.loop)
        log.info("✅ Set main loop for schedulemsg")
    except Exception as e:
        log.warning("Could not set main loop for schedulemsg: %s", e)

    # -------- Central “Back to Main” handler (portal:home) --------
    @app.on_callback_query(filters.regex("^portal:home$"))
    async def _portal_home_cb(_, cq: CallbackQuery):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💞 Menus", callback_data="panels:root")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("📌 Requirements Help", callback_data="reqpanel:home")],
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
        ])
        try:
            await cq.message.edit_text(
                "🔥 Welcome back to SuccuBot\n"
                "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        finally:
            await cq.answer()

    # Safety: if panels didn’t provide the “models_elsewhere:open” page, handle it here.
    @app.on_callback_query(filters.regex("^models_elsewhere:open$"))
    async def _models_elsewhere_cb(_, cq: CallbackQuery):
        text = FIND_MODELS_TEXT or "Nothing here yet 💕"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅ Back to Main", callback_data="portal:home")]])
        try:
            await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        finally:
            await cq.answer()

    # -------- /summonall + /summon handler (MentionMembers-style) --------
    @app.on_message(filters.command(["summonall", "summon"], prefixes=["/", "!"]))
    async def summon_cmd(client: Client, msg: Message):
        # Basic sanity
        if not msg.from_user or not msg.chat:
            return

        chat = msg.chat
        user_id = msg.from_user.id
        chat_id = chat.id

        # Only work in groups/supergroups
        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            log.info("summon: ignoring in non-group chat %s type=%s", chat_id, chat.type)
            return

        # Which command? (summonall vs summon)
        cmd_name = ""
        try:
            if getattr(msg, "command", None):
                raw = msg.command[0]  # like 'summonall'
                cmd_name = raw.lstrip("/!").lower()
        except Exception:
            cmd_name = ""

        log.info(
            "summon: command=%s chat=%s from user=%s text=%r",
            cmd_name,
            chat_id,
            user_id,
            msg.text,
        )

        # Only you + models + super_admins
        if not _can_use_summon(user_id):
            await msg.reply_text("Only Roni and approved models can use /summonall here.")
            return

        # Text after the command becomes the message header
        # /summonall Game night is starting! -> "Game night is starting!"
        header_text = ""
        if msg.text:
            parts = msg.text.split(maxsplit=1)
            if len(parts) > 1:
                header_text = parts[1].strip()

        # Collect all human members
        mentions: List[str] = []
        try:
            async for member in client.get_chat_members(chat_id):
                u = member.user
                if not u or u.is_bot:
                    continue
                name = (u.first_name or u.last_name or "Member").strip()
                mentions.append(f'<a href="tg://user?id={u.id}">{name}</a>')
        except Exception as e:
            log.exception("summon: get_chat_members failed: %s", e)
            await msg.reply_text(
                "I couldn’t read the member list. Make sure I can see members."
            )
            return

        if not mentions:
            await msg.reply_text("I don’t see any members to tag (besides bots).")
            return

        total = len(mentions)
        chunks = _chunk_list(mentions, 20)   # 20 mentions per message
        reply_to_id = msg.reply_to_message_id or msg.id

        num_batches = len(chunks)
        batch_num = 1

        for chunk in chunks:
            # Very obvious what happened, like MentionMembers
            header_lines = [f"Summoning {total} member(s) – batch {batch_num}/{num_batches}"]
            if header_text:
                header_lines.append(header_text)

            text = "\n".join(header_lines) + "\n\n" + " ".join(chunk)

            try:
                await client.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=reply_to_id,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                log.warning("summon: failed to send batch %s: %s", batch_num, e)

            batch_num += 1

        # Delete original command for BOTH /summonall and /summon
        try:
            await msg.delete()
        except Exception:
            pass

    # IMPORTANT: no /start fallback here (to avoid duplicates).
    app.run()


if __name__ == "__main__":
    main()
