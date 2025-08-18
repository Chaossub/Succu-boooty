import logging
from contextlib import suppress
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger("dm_foolproof")

# Replace with your real store
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    class _Dummy:
        def is_dm_ready_global(self, uid: int) -> bool: return False
        def set_dm_ready_global(self, uid: int, ready: bool, by_admin=False): pass
    _store = _Dummy()

def _welcome_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Help & Commands", callback_data="help")],
        [InlineKeyboardButton("Portal", callback_data="portal")]
    ])

def _mark_kb_shown(uid: int): pass  # stub, fill in if needed
def _targets_any(): return []       # stub
async def _notify(client, targets, text): pass

DM_READY_NOTIFY_MODE = "first_time"

def register(app: Client):
    @app.on_message(filters.private & filters.command("start"))
    async def dmf_start(client: Client, m: Message):
        try:
            uid = m.from_user.id if m.from_user else 0
            first_time = not _store.is_dm_ready_global(uid)

            if first_time:
                try:
                    _store.set_dm_ready_global(uid, True, by_admin=False)
                except Exception as e:
                    log.exception("set_dm_ready_global failed: %s", e)
                if DM_READY_NOTIFY_MODE in ("always", "first_time") and _targets_any():
                    with suppress(Exception):
                        await _notify(client, _targets_any(),
                                      f"🔔 DM-ready: {m.from_user.mention} (<code>{uid}</code>)")

            await m.reply_text(
                "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
                "I’m your naughty little helper inside the Sanctuary — here to keep things fun, flirty, and flowing.",
                reply_markup=_welcome_kb(),
                disable_web_page_preview=True
            )
            _mark_kb_shown(uid)

        except Exception as e:
            log.exception("/start failed: %s", e)
            try:
                await m.reply_text("I’m awake, but something hiccuped. Tap Menu below 👇", reply_markup=_welcome_kb())
            except Exception:
                pass
