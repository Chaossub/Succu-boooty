# handlers/help.py
from __future__ import annotations
import os
from pyrogram import Client, filters
from pyrogram.types import Message

# --- YOU: see everything everywhere ---
SUPER_ADMIN_ID = 6964994611
OWNER_ID = int(os.getenv("OWNER_ID", "0")) if os.getenv("OWNER_ID") else None

async def _is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID or (OWNER_ID and user_id == OWNER_ID):
        return True
    try:
        cm = await client.get_chat_member(chat_id, user_id)
        # v2 has privileges; v1 uses status
        return (getattr(cm, "privileges", None) is not None) or (cm.status in ("administrator", "creator"))
    except Exception:
        return False

def _lines_for(user_is_superadmin: bool, user_is_admin: bool) -> list[str]:
    lines: list[str] = []
    lines.append("<b>SuccuBot Commands</b>")

    # ===== General =====
    lines += [
        "\n🛠 <b>General</b>",
        "/start — greet the bot",
        "/help — show this menu",
        "/hi — say hi",
        "/ping — quick health check",
        "/cancel — cancel current action",
    ]

    # ===== DM Ready =====
    if user_is_admin or user_is_superadmin:
        lines.append("\n📩 <b>DM Ready (Foolproof)</b>")
        lines.append("/dmsetup — post button to open DM & auto-opt in")
        lines.append("/dmready — mark yourself ready (reply to set others)")
        lines.append("/dmunready — remove ready (reply to set others)")
        lines.append("/dmreadylist — list DM-ready users (global)")
        lines.append("/dmnudge [@user|id] — DM a nudge (or reply)")
    else:
        lines += [
            "\n📩 <b>DM Ready</b>",
            "/dmready — mark yourself ready",
            "/dmunready — remove ready",
        ]

    # ===== Requirements =====
    lines += [
        "\n📋 <b>Requirements</b>",
        "/reqhelp — show requirement commands",
        "/reqstatus — your status (admins can /reqstatus <id> or reply)",
    ]
    if user_is_admin or user_is_superadmin:
        lines += [
            "/reqadd <amount> — add purchase (reply or self)",
            "/reqgame — add one game (reply or self)",
            "/reqnote <text> — set note (reply or text)",
            "/reqexport — export this month CSV",
            "/reqadmins — list/add/remove req admins",
        ]

    # ===== Exemptions =====
    if user_is_admin or user_is_superadmin:
        lines += [
            "\n🛡 <b>Exemptions</b>",
            "/reqexempt list — show group + global exemptions",
            "/reqexempt add [72h|7d] [global] [; note] — add exemption (reply or id)",
            "/reqexempt remove [global] — remove exemption (reply or id)",
        ]

    # ===== Enforcement =====
    if user_is_admin or user_is_superadmin:
        lines += [
            "\n🚫 <b>Enforcement</b>",
            "/reqscan — list failing users (respects exemptions)",
            "/reqenforce — kick only non-exempt failing users",
        ]

    # ===== Summon =====
    lines += [
        "\n🔔 <b>Summon</b>",
        "/summon @user — summon one",
        "/summonall — summon all tracked",
        "/flirtysummon @user — flirty summon",
        "/flirtysummonall — flirty summon all",
    ]
    if user_is_admin or user_is_superadmin:
        lines.append("/trackall — track all group members (admin)")

    # ===== Fun & XP =====
    lines += [
        "\n🎉 <b>Fun & XP</b>",
        "/bite @user — playful bite & XP",
        "/spank @user — playful spank & XP",
        "/tease @user — playful tease & XP",
        "/naughtystats — your XP",
        "/leaderboard — XP leaderboard",
    ]

    # ===== Moderation =====
    if user_is_admin or user_is_superadmin:
        lines += [
            "\n⚒ <b>Moderation</b>",
            "/warn <user> [reason] — warn",
            "/warns <user> — show warns",
            "/resetwarns <user> — reset warns",
            "/flirtywarn <user> — flirty warn (no count)",
            "/mute <user> [min] — mute",
            "/unmute <user> — unmute",
            "/kick <user> — kick",
            "/ban <user> — ban",
            "/unban <user> — unban",
            "/userinfo <user> — user info",
        ]

    # ===== Federation =====
    if user_is_admin or user_is_superadmin:
        lines += [
            "\n🏛 <b>Federation</b>",
            "/createfed <name> — create federation",
            "/deletefed <fed_id> — delete federation",
            "/purgefed <fed_id> — purge fed bans",
            "/renamefed <fed_id> <new_name> — rename federation",
            "/addfedadmin <fed_id> <user> — add fed admin",
            "/removefedadmin <fed_id> <user> — remove fed admin",
            "/fedlist — list federations",
            "/listfedgroups <fed_id> — list groups in federation",
            "/fedadmins <fed_id> — list federation admins",
            "/fedban <user> — federation ban",
            "/fedunban <user> — federation unban",
            "/fedcheck <user> — check federation bans",
            "/togglefedaction <kick|mute|off> — toggle enforcement",
        ]

    # ===== Flyers + Scheduling =====
    if user_is_admin or user_is_superadmin:
        lines += [
            "\n📂 <b>Flyers</b>",
            "/flyer <name> — get flyer",
            "/listflyers — list flyers",
            "/addflyer <name> <caption> — add flyer (photo/text)",
            "/changeflyer <name> — update flyer image (reply to photo)",
            "/deleteflyer <name> — delete flyer",
            "\n⏰ <b>Scheduling</b>",
            "/scheduleflyer <name> <HH:MM> <group> [daily|once] — schedule flyer",
            "/scheduletext <HH:MM> <group> <text> [daily|once] — schedule text",
            "/listscheduled — view scheduled flyers",
            "/cancelflyer <job_id> — cancel scheduled flyer",
        ]

    return lines

def register(app: Client):
    @app.on_message(filters.command(["start", "help"]) & ~filters.scheduled)
    async def show_help(client: Client, m: Message):
        user_id = m.from_user.id if m.from_user else 0
        chat_id = m.chat.id if m.chat else 0

        superadmin = (user_id == SUPER_ADMIN_ID)
        if chat_id < 0:  # group/supergroup
            admin = await _is_admin(client, chat_id, user_id)
        else:           # private chat: treat OWNER as admin
            admin = superadmin or (OWNER_ID and user_id == OWNER_ID)

        lines = _lines_for(superadmin, admin)

        if chat_id < 0:
            lines.append("\n<i>Tip: in groups with privacy mode ON, use /command@YourBotUsername.</i>")

        await m.reply("\n".join(lines), disable_web_page_preview=True)
