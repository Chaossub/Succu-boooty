import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

log = logging.getLogger("health")

def register(app: Client):
    @app.on_message(filters.command("ping"))
    async def ping(client, m):
        await m.reply_text("pong")

    # Safety net: always answer callback queries so buttons don’t hang
    @app.on_callback_query(group=99)
    async def _cb_safety(client: Client, cq: CallbackQuery):
        try:
            await cq.answer(cache_time=0)
        except Exception as e:
            if "QUERY_ID_INVALID" not in str(e):
                log.debug("cb safety: %s", e)
