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
        sections.append("• /cancel — Cancel any pending setup (e.g. federation)\n")

        # Summon
        sections.append("<b>🔔 Summon Commands:</b>")
        sections.append("• /trackall — Track all members (admin only)")
        sections.append("• /summon @username or reply — Summon one")
        sections.append("• /summonall — Summon everyone")
        sections.append("• /flirtysummon @username or reply — Flirty summon one")
        sections.append("• /flirtysummonall — Flirty summon all\n")

        # Fun
        sections.append("<b>🎉 Fun Commands:</b>")
        sections.append("• /bite @username or reply — Playful bite & earn XP")
        sections.append("• /spank @username or reply — Playful spank & earn XP")
        sections.append("• /tease @username or reply — Playful tease & earn XP\n")

        # XP
        sections.append("<b>📈 XP Commands:</b>")
        sections.append("• /naughty — Show your naughty XP & level")
        sections.append("• /leaderboard — Display the XP leaderboard\n")

        # Moderation
        if admin:
            sections.append("<b>⚒ Moderation Commands:</b>")
            sections.append("• /warn @username — Issue a warning")
            sections.append("• /flirtywarn @username — Flirty warning (no mute)")
            sections.append("• /warns @username — Check warnings")
            sections.append("• /resetwarns @username — Reset warnings")
            sections.append("• /mute @username [duration] — Mute a user")
            sections.append("• /unmute @username — Unmute a user")
            sections.append("• /kick @username — Kick a user")
            sections.append("• /ban @username — Ban a user")
            sections.append("• /unban @username — Unban a user")
            sections.append("• /userinfo @username — View user info\n")

        # Federation
        if admin:
            sections.append("<b>🛡 Federation Commands:</b>")
            sections.append("• /createfed <name> — Create a federation")
            sections.append("• /renamefed <fed_id> <new_name> — Rename a federation")
            sections.append("• /purgefed <fed_id> — Delete a federation")
            sections.append("• /addfedadmin <fed_id> @username — Add a fed admin")
            sections.append("• /removefedadmin <fed_id> @username — Remove a fed admin")
            sections.append("• /listfeds — List all federations")
            sections.append("• /fedban <fed_id> @username — Ban in a federation")
            sections.append("• /fedunban <fed_id> @username — Unban in a federation")
            sections.append("• /fedcheck <fed_id> @username — Check ban status")
            sections.append("• /togglefedaction <fed_id> — Toggle enforcement\n")

        # Flyers
        if admin:
            sections.append("<b>📂 Flyer Commands:</b>")
            sections.append("• /flyer <name> — Retrieve a flyer")
            sections.append("• /listflyers — List all flyers")
            sections.append("• /addflyer <name> <ad> — Add a flyer (reply or send image with caption)")
            sections.append("• /changeflyer <name> [new ad] — Update flyer image or ad")
            sections.append("• /deleteflyer <name> — Delete a flyer")
            sections.append("• /scheduleflyer <name> <time or datetime> — Schedule a flyer one-off or recurring\n")

        help_text = "\n".join(sections)
        await message.reply_text(help_text, disable_web_page_preview=True)
