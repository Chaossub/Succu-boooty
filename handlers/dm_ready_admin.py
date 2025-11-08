# handlers/dm_ready_admin.py
"""
Legacy DM-ready admin tools — now a NO-OP shim.
All DM-ready listing/removal/cleanup is handled centrally in handlers/dm_ready.py.
This prevents duplicate command registrations if this module is wired by mistake.
"""

from pyrogram import Client

def register(app: Client):
    # Intentionally do not register any handlers.
    return
