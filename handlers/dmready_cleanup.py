# handlers/dmready_cleanup.py
"""
Legacy cleanup watcher — now a NO-OP shim.

Auto-removal of DM-ready on leave/kick/ban is implemented centrally in
handlers.dm_ready (ChatMemberUpdatedHandler restricted to the Sanctuary group).

Keeping this file as a stub prevents accidental double-handling if it gets wired.
"""

from pyrogram import Client

def register(app: Client):
    # Intentionally register nothing.
    return
