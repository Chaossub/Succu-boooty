import os
from pyrogram import filters
from pyrogram.types import Message

SUPER_ADMIN_ID = 6964994611

async def is_admin(client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def register(app):
    @app.on_message(filters.command("help") & filters.group)
    async def help_cmd(client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        admin = await is_admin(client, chat_id, user_id)

        sections = []

        # General
        sections.append("<b>🛠 General Commands:</b>")
        sections.append("• /help — Show this help message")
        sections.append("• /cancel — Cancel pending setup (e.g. flyer scheduling)\n")

        # Summon
        sections.append("<b>🔔 Summon Commands:</b>")
        if admin:
            sections.append("• /trackall — Track all group members (admin only)")
        sections.append("• /summon @username — Summon one")
        sections.append("• /summonall — Summon all tracked")
        sections.append("• /flirtysummon @username — Flirty summon one")
        sections.append("• /flirtysummonall — Flirty summon all\n")

        # Fun
        sections.append("<b>🎉 Fun Commands:</b>")
        sections.append("• /bite @username — Bite & earn XP")
        sections.append("• /spank @username — Spank & earn XP")
        sections.append("• /tease @username — Tease & earn XP\n")

        # XP
        sections.append("<b>📈 XP Commands:</b>")
        sections.append("• /naughty — Show your XP")
        sections.append("• /leaderboard — Show top naughty users\n")

        # Moderation
        if admin:
            sections.append("<b>⚒ Moderation Commands:</b>")
            sections.append("• /warn, /flirtywarn, /warns, /resetwarns")
            sections.append("• /mute, /unmute, /kick, /ban, /unban")
            sections.append("• /userinfo @user — View user info\n")

        # Federation
        if admin:
            sections.append("<b>🛡 Federation Commands:</b>")
            sections.append("• /createfed, /renamefed, /purgefed")
            sections.append("• /addfedadmin, /removefedadmin")
            sections.append("• /listfeds, /fedban, /fedunban, /fedcheck")
            sections.append("• /togglefedaction\n")

        # Flyers
        if admin:
            sections.append("<b>📂 Flyer Commands:</b>")
            sections.append("• /flyer <name> — Show a flyer")
            sections.append("• /listflyers — List all flyers")
            sections.append("• /addflyer <name> <caption> — Add flyer")
            sections.append("• /changeflyer <name> — Update flyer image")
            sections.append("• /deleteflyer <name> — Delete flyer")
            sections.append("• /scheduleflyer <name> <datetime> <group> — Schedule")
            sections.append("• /listscheduled — View scheduled flyers")
            sections.append("• /cancelflyer <job_id> — Cancel a scheduled flyer\n")

        await message.reply_text("\n".join(sections), disable_web_page_preview=True)
