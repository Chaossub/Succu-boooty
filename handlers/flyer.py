# handlers/flyer_scheduler.py

import logging
from pyrogram.errors import PeerIdInvalid, ChatAdminRequired, FloodWait, RPCError

logger = logging.getLogger("handlers.flyer_scheduler")

async def ensure_group_touch(app, group_id):
    """Ensure the bot is 'seen' in the group chat for photo/file_id posting (required for new group schedules)."""
    try:
        m = await app.send_message(group_id, "⏳ [Scheduling check, please ignore]")
        await m.delete()
        logger.info(f"Group {group_id} touch succeeded")
        return True
    except PeerIdInvalid:
        logger.error(f"Peer id invalid for group {group_id} (bot probably not added as admin or never sent message)")
        return False
    except ChatAdminRequired:
        logger.error(f"Bot is not admin in group {group_id}")
        return False
    except Exception as e:
        logger.error(f"Unknown error in group touch: {e}")
        return False

async def flyer_job(app, flyer: dict, group_id):
    """
    Robust scheduled flyer post. Supports text and photo flyers.
    :param app: Pyrogram Client
    :param flyer: Flyer dict with possible keys: name, caption, text, file_id
    :param group_id: Target group ID (int or str alias)
    """
    logger.info(f"Scheduled flyer post to {group_id}: {flyer}")

    # Ensure group session is valid
    ok = await ensure_group_touch(app, group_id)
    if not ok:
        logger.error(f"Could not 'touch' group {group_id}. Aborting flyer post.")
        return

    try:
        if flyer.get("file_id"):
            logger.info(f"Posting PHOTO flyer '{flyer.get('name')}' to {group_id}")
            await app.send_photo(
                group_id,
                flyer["file_id"],
                caption=flyer.get("caption", flyer.get("text", ""))[:1024]  # Telegram limit
            )
        elif flyer.get("text"):
            logger.info(f"Posting TEXT flyer '{flyer.get('name')}' to {group_id}")
            await app.send_message(group_id, flyer["text"])
        elif flyer.get("caption"):
            logger.info(f"Posting CAPTION flyer '{flyer.get('name')}' to {group_id}")
            await app.send_message(group_id, flyer["caption"])
        else:
            logger.warning(f"Flyer '{flyer.get('name')}' has no content!")
            return
        logger.info(f"Flyer '{flyer.get('name')}' posted successfully.")
    except FloodWait as e:
        logger.error(f"FloodWait: Must wait {e.value} seconds for flyer to {group_id}")
    except PeerIdInvalid:
        logger.error(f"Peer id invalid posting flyer to {group_id}")
    except ChatAdminRequired:
        logger.error(f"Bot is not admin in group {group_id}")
    except RPCError as e:
        logger.error(f"Telegram RPCError: {e}")
    except Exception as e:
        logger.exception(f"Failed scheduled flyer post: {e}")
