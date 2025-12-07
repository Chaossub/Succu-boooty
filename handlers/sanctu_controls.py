# handlers/sanctu_controls.py
import logging
import os
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from pymongo import MongoClient, ASCENDING
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    Chat,
    ChatMemberUpdated,
)

log = logging.getLogger(__name__)

# ────────────── ENV / DB ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for sanctu_controls")

mongo = MongoClient(MONGO_URI)
db = mongo["Succubot"]

# blacklisted users
blacklist_coll = db["blacklist_users"]
blacklist_coll.create_index([("user_id", ASCENDING)], unique=True)

# groups the bot has seen (for Safety Sweep)
chats_coll = db["sanctu_known_chats"]
chats_coll.create_index([("chat_id", ASCENDING)], unique=True)

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611") or "6964994611"))

LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL"):
    val = os.getenv(key)
    if val:
        try:
            LOG_GROUP_ID = int(val)
            break
        except ValueError:
            pass

# pending state for multi-step flows
PENDING: Dict[int, Dict[str, Any]] = {}

# ────────────── Leave messages (randomized) ──────────────

LEAVE_MESSAGES: List[str] = [
    "🚪 SuccuBot is leaving this group due to a blacklist restriction.",
    "🚨 A blacklist rule has been triggered. SuccuBot is leaving this chat.",
    "This group contains a user restricted from interacting with SuccuBot. Leaving now.",
    "SuccuBot does not remain in groups that violate its safety settings. Exiting.",
    "A protected rule was triggered. SuccuBot is leaving this conversation.",
    "For safety and system integrity, SuccuBot cannot operate in this group. Leaving now.",
    "SuccuBot only stays in verified spaces. This group did not meet requirements.",
    "SuccuBot is exiting due to restricted member presence.",
    "This environment doesn’t meet SuccuBot’s access rules. Leaving.",
    "A restricted user is present. SuccuBot will now exit.",
    "A restricted presence was detected. SuccuBot does not remain in groups with blacklist violations.",
    "Safety mode activated — this group contains a restricted user. SuccuBot is leaving.",
    "Blacklist rules prevent SuccuBot from staying in this chat. Exiting.",
    "A flagged member was detected. SuccuBot cannot stay in this group.",
    "SuccuBot avoids spaces with restricted users. Leaving now.",
    "To protect Sanctuary systems, SuccuBot cannot remain in groups with restricted users.",
    "Sanctuary safety rules triggered. SuccuBot is exiting the group.",
    "This space doesn’t meet Sanctuary access requirements. SuccuBot is leaving.",
    "Sanctuary protections activated — exiting group.",
    "A restricted member was detected. SuccuBot is withdrawing.",
    "Oops 💋 This group includes someone on the restricted list. SuccuBot is heading out.",
    "SuccuBot only stays where it’s safe and sweet. Something here isn’t. Leaving now 💕",
    "A protected rule was triggered — I’m slipping out of this chat 💋",
    "Blacklist alert 💕 SuccuBot doesn’t stay in groups with restricted users.",
    "Mwah 💋 SuccuBot is leaving — this chat isn’t on the approved list.",
    "A restricted presence was found. SuccuBot does not stay in compromised spaces.",
    "This group contains a user who violates SuccuBot’s access rules. Exiting.",
    "A security rule was broken — SuccuBot is leaving to protect Sanctuary systems.",
    "Restricted user detected. SuccuBot will not remain in this environment.",
    "This chat is not eligible for SuccuBot. Leaving now.",
]

# ────────────── Helpers ──────────────

def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


async def _safe_send(client: Client, chat_id: int, text: str):
    try:
        return await client.send_message(chat_id, text)
    except Exception as e:
        log.warning("sanctu_controls: failed to send to %s: %s", chat_id, e)
        return None


async def _log_event(client: Client, text: str):
    if LOG_GROUP_ID is None:
        return
    await _safe_send(client, LOG_GROUP_ID, f"[Sanctuary] {text}")


def _blacklist_doc(user_id: int) -> Optional[Dict[str, Any]]:
    return blacklist_coll.find_one({"user_id": user_id})


def _is_blacklisted(user_id: int) -> bool:
    return _blacklist_doc(user_id) is not None


def _format_user_line(doc: Dict[str, Any]) -> str:
    uid = doc["user_id"]
    username = doc.get("username")
    reason = doc.get("reason") or "No reason stored"
    ts = doc.get("created_at")
    if ts and isinstance(ts, datetime):
        ts_str = ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    else:
        ts_str = "unknown"
    name_part = f"@{username}" if username else "(no username)"
    return f"- {name_part} (`{uid}`) — {reason} (added {ts_str})"


def _track_chat(chat: Chat):
    """Store chat in Mongo so Safety Sweep knows about it."""
    if chat.type not in ("group", "supergroup"):
        return
    try:
        chats_coll.update_one(
            {"chat_id": chat.id},
            {
                "$set": {
                    "chat_id": chat.id,
                    "title": chat.title or "",
                    "type": chat.type,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    except Exception as e:
        log.warning("sanctu_controls: failed to track chat %s: %s", chat.id, e)


async def _leave_group_for_blacklist(
    client: Client,
    chat: Chat,
    trigger_user_id: Optional[int],
    trigger_reason: str,
):
    msg = random.choice(LEAVE_MESSAGES)
    try:
        await client.send_message(chat.id, msg)
    except Exception as e:
        log.warning("sanctu_controls: failed to announce before leaving %s: %s", chat.id, e)

    try:
        await client.leave_chat(chat.id)
    except Exception as e:
        log.warning("sanctu_controls: failed to leave chat %s: %s", chat.id, e)

    user_info = ""
    if trigger_user_id:
        doc = _blacklist_doc(trigger_user_id)
        uname = doc.get("username") if doc else None
        if uname:
            user_info = f"Blacklisted user: @{uname} (`{trigger_user_id}`)"
        else:
            user_info = f"Blacklisted user ID: `{trigger_user_id}`"

    base = f"Left group: <b>{chat.title or chat.id}</b> (`{chat.id}`)\nReason: {trigger_reason}"
    if user_info:
        base += f"\n{user_info}"

    await _log_event(client, base)

    try:
        await client.send_message(OWNER_ID, f"🚨 {base}")
    except Exception as e:
        log.warning("sanctu_controls: failed to DM owner about leave: %s", e)


async def _scan_chat_for_blacklisted(client: Client, chat: Chat) -> None:
    """Checks whether ANY blacklisted user is present in the given chat."""
    docs = list(blacklist_coll.find({}, {"user_id": 1}))
    if not docs:
        return

    for d in docs:
        uid = d["user_id"]
        try:
            member = await client.get_chat_member(chat.id, uid)
        except Exception:
            continue
        if member and member.status not in ("left", "kicked"):
            await _leave_group_for_blacklist(
                client,
                chat,
                trigger_user_id=uid,
                trigger_reason="Detected blacklisted user in group during scan/add.",
            )
            return


# ────────────── Keyboards ──────────────

def _sanctu_root_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👤 Blacklist Controls", callback_data="sanctu:blacklist")],
            [InlineKeyboardButton("🧭 Safety Sweep (Force Check & Leave)", callback_data="sanctu:force_scan")],
            [InlineKeyboardButton("❌ Close", callback_data="sanctu:close")],
        ]
    )


def _blacklist_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Add User to Blacklist", callback_data="sanctu:blacklist:add")],
            [InlineKeyboardButton("➖ Remove User From Blacklist", callback_data="sanctu:blacklist:remove")],
            [InlineKeyboardButton("📋 View Blacklisted Users", callback_data="sanctu:blacklist:list")],
            [InlineKeyboardButton("⬅ Back", callback_data="sanctu:open")],
        ]
    )


def _main_menu_kb() -> InlineKeyboardMarkup:
    """Clone of your main SuccuBot menu so Close can go back there."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💞 Menus", callback_data="panels:menus")],
            [InlineKeyboardButton("🔐 Contact Admins", callback_data="contact_admins:open")],
            [InlineKeyboardButton("🍑 Find Our Models Elsewhere", callback_data="models_elsewhere:open")],
            [InlineKeyboardButton("📌 Requirements Help", callback_data="reqpanel:home")],
            [InlineKeyboardButton("❓ Help", callback_data="help:open")],
            [InlineKeyboardButton("🛡 Sanctuary Controls", callback_data="sanctu:open")],
        ]
    )


# ────────────── Register ──────────────

def register(app: Client):
    log.info("✅ handlers.sanctu_controls registered (Sanctuary Controls + blacklist + auto-leave)")

    # /sanctu in DM
    @app.on_message(filters.private & filters.command("sanctu"))
    async def sanctu_cmd(client: Client, m: Message):
        if not _is_owner(m.from_user.id):
            await m.reply_text("You don’t have access to Sanctuary Controls.")
            return

        text = (
            "🛡 <b>Sanctuary Controls</b>\n\n"
            "Roni-only control panel for safety + blacklist.\n\n"
            "• Blacklist users so they can’t touch your bot\n"
            "• Auto-leave any group that contains a blacklisted user\n"
            "• Run a Safety Sweep to force check all tracked groups\n"
        )
        await m.reply_text(text, reply_markup=_sanctu_root_kb())

    # open from main-menu button
    @app.on_callback_query(filters.regex(r"^sanctu:open$"))
    async def sanctu_open_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_owner(cq.from_user.id):
            await cq.answer("You don’t have access to this panel.", show_alert=True)
            return
        await cq.message.edit_text(
            "🛡 <b>Sanctuary Controls</b>\n\n"
            "Roni-only control panel.",
            reply_markup=_sanctu_root_kb(),
        )
        await cq.answer()

    # Close → back to normal SuccuBot menu
    @app.on_callback_query(filters.regex(r"^sanctu:close$"))
    async def sanctu_close_cb(client: Client, cq: CallbackQuery):
        kb = _main_menu_kb()
        try:
            await cq.message.edit_text(
                "🔥 Welcome back to SuccuBot\n"
                "I’m your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
                "✨ Use the menu below to navigate!",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        await cq.answer()

    # Blacklist menu
    @app.on_callback_query(filters.regex(r"^sanctu:blacklist$"))
    async def sanctu_blacklist_menu_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_owner(cq.from_user.id):
            await cq.answer("You don’t have access to this panel.", show_alert=True)
            return

        await cq.message.edit_text(
            "👤 <b>Blacklist Controls</b>\n\n"
            "• Add users who should never touch your bot\n"
            "• Remove users if you ever change your mind\n"
            "• View current blacklist",
            reply_markup=_blacklist_menu_kb(),
        )
        await cq.answer()

    # Start add flow
    @app.on_callback_query(filters.regex(r"^sanctu:blacklist:add$"))
    async def sanctu_blacklist_add_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_owner(cq.from_user.id):
            await cq.answer("You don’t have access to this panel.", show_alert=True)
            return

        PENDING[cq.from_user.id] = {"mode": "await_blacklist_target"}
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="sanctu:cancel")]]
        )
        await cq.message.edit_text(
            "➕ <b>Add User to Blacklist</b>\n\n"
            "Forward a message from the user you want to blacklist, or send their @username or numeric ID.\n\n"
            "They will be blocked from using SuccuBot and any group that contains them will be left automatically.\n\n"
            "<i>Note:</i> If Telegram hides their info when you forward, sending their @username or numeric ID works best.",
            reply_markup=kb,
        )
        await cq.answer()

    # Handle the actual forwarded message / id
    @app.on_message(filters.private)
    async def sanctu_private_msg_handler(client: Client, m: Message):
        user_id = m.from_user.id if m.from_user else None
        if user_id is None or not _is_owner(user_id):
            return

        state = PENDING.get(user_id)
        if not state:
            return

        if state.get("mode") == "await_blacklist_target":
            target_id: Optional[int] = None
            target_username: Optional[str] = None

            if m.forward_from:
                # Forward with user info visible
                target_id = m.forward_from.id
                target_username = m.forward_from.username
            else:
                text = (m.text or "").strip()
                if text:
                    if text.startswith("@"):
                        # @username
                        target_username = text[1:]
                        try:
                            user = await client.get_users(text)
                            target_id = user.id
                            if not target_username:
                                target_username = user.username
                        except Exception as e:
                            log.warning("sanctu_controls: failed to resolve username %s: %s", text, e)
                    else:
                        # numeric ID
                        try:
                            target_id = int(text)
                        except ValueError:
                            target_id = None

            if not target_id:
                await m.reply_text(
                    "I couldn’t figure out who you meant.\n"
                    "Please forward a message from them, or send their @username or numeric ID.",
                )
                return

            doc = {
                "user_id": target_id,
                "username": target_username,
                "reason": "Manual blacklist",
                "created_at": datetime.now(timezone.utc),
            }
            blacklist_coll.update_one({"user_id": target_id}, {"$set": doc}, upsert=True)

            PENDING.pop(user_id, None)

            await m.reply_text(
                f"✅ User <code>{target_id}</code> has been added to the blacklist.\n"
                f"They will be blocked from using SuccuBot and any group that contains them will be left automatically."
            )
            await _log_event(
                client,
                f"User `{target_id}` added to blacklist by owner.",
            )

    # Cancel add
    @app.on_callback_query(filters.regex(r"^sanctu:cancel$"))
    async def sanctu_cancel_cb(client: Client, cq: CallbackQuery):
        if cq.from_user:
            PENDING.pop(cq.from_user.id, None)
        await cq.message.edit_text(
            "❌ Action cancelled.\n\nBack to Sanctuary Controls.",
            reply_markup=_sanctu_root_kb(),
        )
        await cq.answer()

    # View blacklist
    @app.on_callback_query(filters.regex(r"^sanctu:blacklist:list$"))
    async def sanctu_blacklist_list_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_owner(cq.from_user.id):
            await cq.answer("You don’t have access to this panel.", show_alert=True)
            return

        docs = list(blacklist_coll.find().sort("created_at", -1))
        if not docs:
            text = "📋 <b>Current blacklist is empty.</b>"
        else:
            lines = ["📋 <b>Current blacklist:</b>", ""]
            lines.extend(_format_user_line(d) for d in docs)
            text = "\n".join(lines)

        await cq.message.edit_text(
            text,
            reply_markup=_blacklist_menu_kb(),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Start remove flow
    @app.on_callback_query(filters.regex(r"^sanctu:blacklist:remove$"))
    async def sanctu_blacklist_remove_start_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_owner(cq.from_user.id):
            await cq.answer("You don’t have access to this panel.", show_alert=True)
            return

        docs = list(blacklist_coll.find().sort("created_at", -1))
        if not docs:
            await cq.message.edit_text(
                "There are no users on the blacklist to remove.",
                reply_markup=_blacklist_menu_kb(),
            )
            await cq.answer()
            return

        buttons = []
        for d in docs:
            uid = d["user_id"]
            uname = d.get("username")
            label = f"@{uname}" if uname else str(uid)
            buttons.append(
                [InlineKeyboardButton(label, callback_data=f"sanctu:blacklist:remove:{uid}")]
            )

        buttons.append([InlineKeyboardButton("⬅ Back", callback_data="sanctu:blacklist")])

        kb = InlineKeyboardMarkup(buttons)
        await cq.message.edit_text(
            "Select a user to remove from the blacklist:",
            reply_markup=kb,
        )
        await cq.answer()

    # Confirm remove
    @app.on_callback_query(filters.regex(r"^sanctu:blacklist:remove:(\d+)$"))
    async def sanctu_blacklist_remove_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_owner(cq.from_user.id):
            await cq.answer("You don’t have access to this panel.", show_alert=True)
            return

        data = cq.data or ""
        try:
            uid = int(data.rsplit(":", 1)[-1])
        except ValueError:
            await cq.answer("Bad user id.", show_alert=True)
            return

        doc = blacklist_coll.find_one({"user_id": uid})
        blacklist_coll.delete_one({"user_id": uid})

        uname = doc.get("username") if doc else None
        label = f"@{uname}" if uname else str(uid)

        await cq.message.edit_text(
            f"✅ Removed <code>{label}</code> from the blacklist.",
            reply_markup=_blacklist_menu_kb(),
        )
        await cq.answer()

        await _log_event(
            client, f"User `{uid}` removed from blacklist by owner."
        )

    # Safety Sweep (no get_dialogs, uses tracked chats)
    @app.on_callback_query(filters.regex(r"^sanctu:force_scan$"))
    async def sanctu_force_scan_cb(client: Client, cq: CallbackQuery):
        if not cq.from_user or not _is_owner(cq.from_user.id):
            await cq.answer("You don’t have access to this panel.", show_alert=True)
            return

        await cq.answer("Starting safety sweep…", show_alert=False)

        docs = list(chats_coll.find({}))
        for d in docs:
            chat_id = d["chat_id"]
            try:
                chat = await client.get_chat(chat_id)
            except Exception as e:
                log.warning("sanctu_controls: failed to get chat %s during sweep: %s", chat_id, e)
                continue
            await _scan_chat_for_blacklisted(client, chat)

        await cq.message.edit_text(
            "🧭 Safety Sweep completed.\n\n"
            "Any tracked groups containing blacklisted users have been left, and you were notified.",
            reply_markup=_sanctu_root_kb(),
        )

    # Track membership changes + auto-leave on blacklisted join
    @app.on_chat_member_updated()
    async def sanctu_chat_member_updated(client: Client, cmu: ChatMemberUpdated):
        chat = cmu.chat
        _track_chat(chat)

        new = cmu.new_chat_member

        # Bot itself added → scan
        if new.user and new.user.is_self:
            if new.status in ("member", "administrator"):
                await _scan_chat_for_blacklisted(client, chat)
            return

        # Other user joined/activated
        user = new.user
        if not user:
            return

        if new.status not in ("member", "restricted"):
            return

        uid = user.id
        if not _is_blacklisted(uid):
            return

        await _leave_group_for_blacklist(
            client,
            chat,
            trigger_user_id=uid,
            trigger_reason="Blacklisted user joined or became active in this group.",
        )

    # Track groups whenever the bot sees group messages (for sweeps)
    @app.on_message(filters.group)
    async def sanctu_track_groups_msg(client: Client, m: Message):
        if m.chat:
            _track_chat(m.chat)
