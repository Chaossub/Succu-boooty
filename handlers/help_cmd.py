# handlers/help.py
from __future__ import annotations
from typing import Dict, List, Literal, Tuple
import os

from pyrogram import Client, filters
from pyrogram.types import Message

# ===== Roles =====
SUPER_ADMIN_ID = 6964994611  # You: see EVERYTHING everywhere
OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID") else None

Audience = Literal["all", "admin", "owner", "superadmin"]

# ===== Cute category emojis =====
CAT_EMOJI = {
    "General": "🛠",
    "DM Ready (Foolproof)": "📩",
    "Requirements": "📋",
    "Exemptions": "🛡",
    "Enforcement": "🚫",
    "Summon": "🔔",
    "Fun & XP": "🎉",
    "Moderation": "⚒",
    "Warnings": "🚨",
    "Federation": "🏛",
    "Flyers": "📂",
    "Scheduling": "⏰",
}

# ===== Dynamic help registry (modules can extend at runtime) =====
HELP_REGISTRY: Dict[str, List[Tuple[str, str, Audience]]] = {}

def register_help_command(category: str, command: str, description: str, audience: Audience = "all") -> None:
    HELP_REGISTRY.setdefault(category, []).append((command, description, audience))


# ===== Built-ins (comprehensive list we know about) =====
def _populate_builtin() -> None:
    if getattr(_populate_builtin, "_done", False):
        return

    # General
    register_help_command("General", "/start", "Start / greet the bot", "all")
    register_help_command("General", "/help", "Show this help menu", "all")
    register_help_command("General", "/hi", "Say hi to test the bot", "all")
    register_help_command("General", "/cancel", "Cancel the current operation", "all")
    register_help_command("General", "/ping", "Quick health check (pong)", "all")
    register_help_command("General", "/id", "Show your ID / chat ID", "all")

    # DM Ready (Foolproof)  (dm_foolproof.py)
    register_help_command("DM Ready (Foolproof)", "/dmsetup", "Drop a button to open DM & auto-opt in", "admin")
    register_help_command("DM Ready (Foolproof)", "/dmready", "Mark yourself DM-ready (admins can reply to set others)", "all")
    register_help_command("DM Ready (Foolproof)", "/dmunready", "Remove DM-ready (admins can reply to set others)", "all")
    register_help_command("DM Ready (Foolproof)", "/dmreadylist", "List DM-ready users (global & permanent)", "admin")
    register_help_command("DM Ready (Foolproof)", "/dmnudge [@user|id]", "Politely DM a user to open DMs (or reply)", "admin")
    # detected extras in your dm_foolproof.py
    register_help_command("DM Ready (Foolproof)", "/dmstatus", "Show your DM-ready status", "all")
    register_help_command("DM Ready (Foolproof)", "/remindnow", "Trigger an immediate reminder/ping (if available)", "admin")

    # Requirements (req_handlers.py)
    register_help_command("Requirements", "/reqhelp", "Show requirement commands", "all")
    register_help_command("Requirements", "/reqstatus [user_id]", "Your status (admins: reply or pass id)", "all")
    # Your tree also had older-style names; keeping the modern ones here:
    register_help_command("Requirements", "/reqadd <amount>", "Add purchase $ to a user (reply or self)", "admin")
    register_help_command("Requirements", "/reqgame", "Add one game to a user (reply or self)", "admin")
    register_help_command("Requirements", "/reqnote <text>", "Set a note for a user (reply or text)", "admin")
    register_help_command("Requirements", "/reqexport", "Export this month’s CSV", "admin")
    register_help_command("Requirements", "/reqadmins [add|remove] (reply or user_id)", "List / manage requirement admins", "admin")

    # Some repos of yours also used admin aliases; we include them so they show in Help if present
    register_help_command("Requirements", "/addreqadmin <user_id>", "Alias: add requirement admin", "admin")
    register_help_command("Requirements", "/reqremove <user_id>", "Alias: remove requirement data/user (if implemented)", "admin")
    register_help_command("Requirements", "/revokepass <user_id>", "Revoke a previously granted pass (if implemented)", "admin")
    register_help_command("Requirements", "/trackonjoin", "Enable auto-tracking on new joins (if present)", "admin")

    # Exemptions
    register_help_command("Exemptions", "/reqexempt list", "Show group + global exemptions", "admin")
    register_help_command("Exemptions", "/reqexempt add [72h|7d] [global] [; note] (reply or user_id)", "Add an exemption", "admin")
    register_help_command("Exemptions", "/reqexempt remove [global] (reply or user_id)", "Remove an exemption", "admin")

    # Enforcement
    register_help_command("Enforcement", "/reqscan", "Show users failing requirements (respects exemptions)", "admin")
    register_help_command("Enforcement", "/reqenforce", "Kick only non-exempt failing users", "admin")

    # Summon (handlers/summon.py)
    register_help_command("Summon", "/trackall", "Track all group members", "admin")
    register_help_command("Summon", "/summon @username", "Summon one user", "all")
    register_help_command("Summon", "/summonall", "Summon all tracked users", "all")
    register_help_command("Summon", "/flirtysummon @username", "Flirty summon one user", "all")
    register_help_command("Summon", "/flirtysummonall", "Flirty summon all users", "all")
    register_help_command("Summon", "/help_summon", "Summon-specific help (if present)", "all")

    # Fun & XP (handlers/fun.py, handlers/xp.py)
    register_help_command("Fun & XP", "/bite @user", "Playful bite & earn XP", "all")
    register_help_command("Fun & XP", "/spank @user", "Playful spank & earn XP", "all")
    register_help_command("Fun & XP", "/tease @user", "Playful tease & earn XP", "all")
    register_help_command("Fun & XP", "/naughtystats", "Show your XP", "all")
    register_help_command("Fun & XP", "/leaderboard", "Show XP leaderboard", "all")
    register_help_command("Fun & XP", "/resetxp <user>", "Admin: reset a user’s XP", "admin")

    # Moderation (handlers/moderation.py)
    register_help_command("Moderation", "/warn <user> [reason]", "Issue a warning", "admin")
    register_help_command("Moderation", "/warns <user>", "Check warnings", "admin")
    register_help_command("Moderation", "/resetwarns <user>", "Reset warns", "admin")
    register_help_command("Moderation", "/flirtywarn <user>", "Flirty warning (no count)", "admin")
    register_help_command("Moderation", "/mute <user> [min]", "Mute a user", "admin")
    register_help_command("Moderation", "/unmute <user>", "Unmute a user", "admin")
    register_help_command("Moderation", "/kick <user>", "Kick a user", "admin")
    register_help_command("Moderation", "/ban <user>", "Ban a user", "admin")
    register_help_command("Moderation", "/unban <user>", "Unban a user", "admin")
    register_help_command("Moderation", "/userinfo <user>", "View user info", "admin")

    # Warnings (handlers/warnings.py) – some builds keep them split
    register_help_command("Warnings", "/warn <user> [reason]", "Issue a warning", "admin")
    register_help_command("Warnings", "/warns <user>", "Check warnings", "admin")
    register_help_command("Warnings", "/resetwarns <user>", "Reset warns", "admin")

    # Federation (handlers/federation.py)
    # Your file is truncated in the ZIP, but these are the standard ones we saw / typically use:
    register_help_command("Federation", "/createfed <name>", "Create a federation", "admin")
    register_help_command("Federation", "/delfed <fed_id>", "Delete federation", "admin")
    register_help_command("Federation", "/fedlist", "List federations", "admin")
    register_help_command("Federation", "/joinfed <fed_id>", "Join a federation (group)", "admin")
    register_help_command("Federation", "/leavefed <fed_id>", "Leave a federation (group)", "admin")
    register_help_command("Federation", "/fedadmins <fed_id>", "List federation admins", "admin")
    register_help_command("Federation", "/addfedadmin <fed_id> <user>", "Add fed admin", "admin")
    register_help_command("Federation", "/removefedadmin <fed_id> <user>", "Remove fed admin", "admin")
    register_help_command("Federation", "/fedban <user>", "Federation ban", "admin")
    register_help_command("Federation", "/fedunban <user>", "Federation unban", "admin")
    register_help_command("Federation", "/fedbans <fed_id>", "List federation bans", "admin")
    register_help_command("Federation", "/fedcheck <user>", "Check federation bans", "admin")
    register_help_command("Federation", "/linkgroup <fed_id>", "Link this group to a federation", "admin")

    # Flyers (handlers/flyer.py)
    register_help_command("Flyers", "/flyer <name>", "Retrieve a flyer", "admin")
    register_help_command("Flyers", "/textflyer <name> <text>", "Create a text-only flyer", "admin")
    register_help_command("Flyers", "/listflyers", "List all flyers", "admin")
    register_help_command("Flyers", "/addflyer <name> <caption>", "Add flyer (photo or text)", "admin")
    register_help_command("Flyers", "/changeflyer <name>", "Update flyer image (reply to new image)", "admin")
    register_help_command("Flyers", "/deleteflyer <name>", "Delete a flyer", "admin")

    # Scheduling (handlers/flyer_scheduler.py, handlers/schedulemsg.py)
    register_help_command("Scheduling", "/scheduleflyer <name> <HH:MM> <group> [daily|once]", "Schedule a flyer", "admin")
    register_help_command("Scheduling", "/listscheduledflyers", "List scheduled flyers", "admin")
    register_help_command("Scheduling", "/cancelflyer <job_id>", "Cancel a scheduled flyer", "admin")

    register_help_command("Scheduling", "/schedulemsg <HH:MM> <group> <text> [daily|once]", "Schedule a text message", "admin")
    register_help_command("Scheduling", "/listmsgs", "List scheduled messages", "admin")
    register_help_command("Scheduling", "/cancelmsg <job_id>", "Cancel a scheduled message", "admin")
    register_help_command("Scheduling", "/cancelallflyers", "Cancel all scheduled flyers (if enabled)", "admin")

    # Warmup (handlers/warmup.py)
    register_help_command("General", "/warmup", "Warm up bot (ready checks, caches, etc.)", "admin")

    _populate_builtin._done = True


# ===== Role helpers =====
async def _is_admin_in_chat(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID or (OWNER_ID and user_id == OWNER_ID):
        return True
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return (m.status in ("administrator", "creator")) or (getattr(m, "privileges", None) is not None)
    except Exception:
        return False

def _audience_allowed(aud: Audience, is_admin: bool, user_id: int, superadmin_view_all: bool) -> bool:
    if superadmin_view_all:
        return True  # SUPER_ADMIN sees everything
    if aud == "all":
        return True
    if aud == "admin":
        return is_admin
    if aud == "owner":
        return (OWNER_ID is not None) and (user_id == OWNER_ID)
    if aud == "superadmin":
        return user_id == SUPER_ADMIN_ID
    return False


# ===== Handler =====
def register(app: Client):
    _populate_builtin()

    @app.on_message(filters.command(["start", "help"]) & ~filters.scheduled)
    async def help_handler(client: Client, message: Message):
        user_id = message.from_user.id if message.from_user else 0
        chat_id = message.chat.id if message.chat else 0

        # SUPER_ADMIN sees EVERYTHING (your ask)
        superadmin_view_all = (user_id == SUPER_ADMIN_ID)

        # Others: check admin in this chat (or owner in PM)
        if chat_id < 0:
            is_admin = await _is_admin_in_chat(client, chat_id, user_id)
        else:
            is_admin = (user_id == SUPER_ADMIN_ID) or (OWNER_ID and user_id == OWNER_ID)

        # Category order; unknown/new categories get appended automatically
        preferred_order = [
            "General",
            "DM Ready (Foolproof)",
            "Requirements",
            "Exemptions",
            "Enforcement",
            "Summon",
            "Fun & XP",
            "Moderation",
            "Warnings",
            "Federation",
            "Flyers",
            "Scheduling",
        ]
        all_cats = preferred_order + [c for c in HELP_REGISTRY.keys() if c not in preferred_order]

        lines: List[str] = []
        lines.append("<b>SuccuBot Commands</b>")

        for cat in all_cats:
            items = HELP_REGISTRY.get(cat, [])
            if not items:
                continue
            visible = [
                (cmd, desc) for (cmd, desc, aud) in items
                if _audience_allowed(aud, is_admin, user_id, superadmin_view_all)
            ]
            if not visible:
                continue
            emoji = CAT_EMOJI.get(cat, "✨")
            lines.append(f"\n{emoji} <b>{cat}</b>")
            for cmd, desc in visible:
                lines.append(f"{cmd} — {desc}")

        if chat_id < 0:
            lines.append("\n<i>Tip: In groups with privacy mode ON, use /command@YourBotUsername for admin actions.</i>")

        await message.reply("\n".join(lines), disable_web_page_preview=True)
