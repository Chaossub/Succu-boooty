# handlers/health.py
import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

log = logging.getLogger("health")

def register(app: Client):
    # Simple ping to verify bot liveness
    @app.on_message(filters.command("ping"))
    async def ping(client, m):
        await m.reply_text("pong")

    # Catch-all *last* callback safety net: always answer to clear spinner
    @app.on_callback_query(group=99)  # run after your regular handlers
    async def _cb_safety(client: Client, cq: CallbackQuery):
        # If another handler already answered, this is a no-op.
        try:
            await cq.answer(cache_time=0)
        except Exception as e:
            # Ignore "query is too old"/already answered; log others.
            if "QUERY_ID_INVALID" not in str(e):
                log.debug("cb safety answer: %s", e)
