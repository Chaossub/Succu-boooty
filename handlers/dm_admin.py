# handlers/dm_admin.py
"""
Legacy admin module — converted to a NO-OP to avoid duplicate /dmreadylist
handlers conflicting with the unified implementation in handlers/dm_ready.py.

If this file is wired accidentally, it will not register any commands.
"""

from pyrogram import Client

def register(app: Client):
    # Intentionally register nothing.
    # The canonical /dmreadylist lives in handlers/dm_ready.py
    return
