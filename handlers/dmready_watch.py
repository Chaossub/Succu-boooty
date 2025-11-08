# handlers/dmready_watch.py
"""
Legacy DM-ready watcher — now a NO-OP shim.

All DM-ready add/remove logic lives in handlers.dm_ready.
This stub avoids duplicate removals and mixed storage backends.
"""

from pyrogram import Client

def register(app: Client):
    # Intentionally register nothing.
    return
