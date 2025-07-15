import logging
import asyncio

from pyrogram.errors import PeerIdInvalid, ChatAdminRequired, FloodWait
from datetime import datetime

logger = logging.getLogger("handlers.flyer_scheduler")

# Ensure the bot has an open session with the target group (prevents PeerIdInvalid)
async def ensure_group_touch(app, group_id):
    try:
        # Try a get_chat (doesn't send messages, but touches the peer)
        await app.get_chat(group_id)
        logger.info(f"Touched group {group_id}")
    except PeerIdInvalid:
        logger.warning(f"PeerIdInvalid for group {group_id} on touch.")
        # Try sending a "touch" message and deleting it (if you have admin)
        try:
            msg = await app.send_message(group_id, ".")
            await msg.delete()
            logger.info(f"Touched group {group_id} by message.")
        except Exception as e:
            logger.error(f"Failed group touch for {group_id}: {e}")

# Schedules a flyer post
def schedule_flyer_post(scheduler, app, flyer, when: datetime, job_id=None):
    # Wrap the flyer posting in an async runner
    async def flyer_job():
        group_id = flyer.get("group_id")
        logger.info(f"Scheduled flyer job starting: {flyer}")
        await ensure_group_touch(app, group_id)
        try:
            if flyer.get("file_id"):
                await app.send_photo(
                    group_id,
                    flyer["file_id"],
                    caption=flyer.get("caption", ""),
                )
                logger.info(f"Posted photo flyer {flyer.get('name')} to {group_id}")
            else:
                await app.send_message(
                    group_id,
                    flyer.get("text") or flyer.get("caption", "")
                )
                logger.info(f"Posted text flyer {flyer.get('name')} to {group_id}")
        except FloodWait as fw:
            logger.error(f"FloodWait posting flyer: sleeping {fw.value}s")
            await asyncio.sleep(fw.value)
        except PeerIdInvalid as e:
            logger.error(f"PeerIdInvalid posting flyer: {e}")
        except ChatAdminRequired as e:
            logger.error(f"Missing admin in {group_id}: {e}")
        except Exception as e:
            logger.error(f"Unhandled posting flyer: {e}")

    # Schedule the flyer job with the scheduler
    def run_async_job():
        asyncio.run(flyer_job())
    scheduler.add_job(run_async_job, "date", run_date=when, id=job_id or f"flyer_{flyer.get('name', 'noname')}_{group_id}_{int(when.timestamp())}")

# Example usage in your flyer.py or main:
# schedule_flyer_post(scheduler, app, flyer_data, when=datetime_obj)

