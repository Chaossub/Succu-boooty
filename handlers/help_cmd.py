# handlers/help_cmd.py

import os
from pyrogram import Client, filters
from pyrogram.types import Message

# Super-user override
SUPER_ADMIN_ID = 6964994611

# Import your existing admin checker if you have one,
# otherwise we’ll reimplement it here:
async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except:
        return False

def register(app: Client):
    @app.on_message(filters.command(["start", "help"]) & (filters.group | filters.private))
    async def help_cmd(client: Client, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        admin = await is_admin(client, chat_id, user_id)

        sections = []

        # ── General ─────────────────────
        sections.append("<b>🛠 General Commands</b>")
        sections.append("• /start — Initialize the bot")
        sections.append("• /help — Show this help message")
        sections.append("• /cancel — Cancel current operation\n")

        # ── Summon ──────────────────────
        sections.append("<b>🔔 Summon Commands</b>")
        if admin:
            sections.append("• /trackall — Track all group members (admin only)")
        sections.append("• /summon &lt;@username&gt; — Summon one user")
        sections.append("• /summonall — Summon all tracked users")
        sections.append("• /flirtysummon &lt;@username&gt; — Flirty summon one")
        sections.append("• /flirtysummonall — Flirty summon all\n")

        # ── Fun ─────────────────────────
        sections.append("<b>🎉 Fun Commands</b>")
        sections.append("• /bite &lt;@username&gt; — Playful bite & earn XP")
        sections.append("• /spank &lt;@username&gt; — Playful spank & earn XP")
        sections.append("• /tease &lt;@username&gt; — Playful tease & earn XP\n")

        # ── XP & Leaderboard ────────────
        sections.append("<b>📈 XP Commands</b>")
        sections.append("• /naughty — Show your XP")
        sections.append("• /leaderboard — Show top naughty users\n")

        # ── Moderation ──────────────────
        if admin:
            sections.append("<b>⚒ Moderation Commands</b>")
            sections.append("• /warn &lt;user&gt; [reason] — Issue a warning")
            sections.append("• /warns &lt;user&gt; — Check warnings")
            sections.append("• /resetwarns &lt;user&gt; — Reset warns")
            sections.append("• /flirtywarn &lt;user&gt; — Flirty warning (no count)")
            sections.append("• /mute &lt;user&gt; [min] — Mute a user")
            sections.append("• /unmute &lt;user&gt; — Unmute a user")
            sections.append("• /kick &lt;user&gt; — Kick a user")
            sections.append("• /ban &lt;user&gt; — Ban a user")
            sections.append("• /unban &lt;user&gt; — Unban a user")
            sections.append("• /userinfo &lt;user&gt; — View user info\n")

        # ── Federation ──────────────────
        if admin:
            sections.append("<b>🛡 Federation Commands</b>")
            sections.append("• /createfed &lt;name&gt; — Create federation")
            sections.append("• /deletefed &lt;fed_id&gt; — Delete federation")
            sections.append("• /purgefed &lt;fed_id&gt; — Purge fed ban list")
            sections.append("• /renamefed &lt;fed_id&gt; &lt;new_name&gt; — Rename federation")
            sections.append("• /addfedadmin &lt;fed_id&gt; &lt;user&gt; — Add fed admin")
            sections.append("• /removefedadmin &lt;fed_id&gt; &lt;user&gt; — Remove fed admin")
            sections.append("• /listfeds — List federations")
            sections.append("• /listfedgroups &lt;fed_id&gt; — List groups in a federation")
            sections.append("• /listfedadmins &lt;fed_id&gt; — List fed admins")
            sections.append("• /fedban &lt;fed_id&gt; &lt;user&gt; — Federation ban")
            sections.append("• /fedunban &lt;fed_id&gt; &lt;user&gt; — Federation unban")
            sections.append("• /fedcheck &lt;user&gt; — Check fed bans")
            sections.append("• /togglefedaction &lt;fed_id&gt; &lt;kick|mute|off&gt; — Toggle enforcement\n")

        # ── Flyers ───────────────────────
        if admin:
            sections.append("<b>📂 Flyer Commands</b>")
            sections.append("• /flyer &lt;name&gt; — Retrieve a flyer")
            sections.append("• /listflyers — List all flyers")
            sections.append("• /addflyer &lt;name&gt; — Add a flyer (photo with caption)")
            sections.append("• /changeflyer &lt;name&gt; — Update flyer image")
            sections.append("• /deleteflyer &lt;name&gt; — Delete a flyer")
            sections.append("• /scheduleflyer &lt;name&gt; &lt;HH:MM&gt; &lt;chat&gt; — Schedule flyer")
            sections.append("• /scheduletext &lt;HH:MM&gt; &lt;chat&gt; &lt;text&gt; — Schedule text")
            sections.append("• /listscheduled — View scheduled posts")
            sections.append("• /cancelflyer &lt;index&gt; — Cancel a scheduled post\n")

        # send it all
        await message.reply_text(
            "\n".join(sections),
            disable_web_page_preview=True,
            parse_mode="HTML"
        )
