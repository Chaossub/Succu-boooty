# handlers/createmenu.py
from __future__ import annotations
import os, json
from pathlib import Path
from typing import Dict

from pyrogram import Client, filters
from pyrogram.types import Message

# Where menu overrides are stored (persisted as JSON)
DATA_PATH = Path(os.getenv("MODEL_MENU_DATA", "data/model_menus.json"))
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

# Who can run /createmenu
OWNER_IDS = {int(x) for x in os.getenv("OWNER_IDS", "").replace(" ", "").split(",") if x.isdigit()}
SUPER_ADMIN_IDS = {int(x) for x in os.getenv("SUPER_ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()}
ADMIN_IDS = OWNER_IDS | SUPER_ADMIN_IDS

MODEL_KEYS = {"roni", "ruby", "rin", "savy"}

def _load() -> Dict[str, dict]:
    try:
        if DATA_PATH.is_file():
            return json.loads(DATA_PATH.read_text() or "{}")
    except Exception:
        pass
    return {}

def _save(d: Dict[str, dict]):
    DATA_PATH.write_text(json.dumps(d, indent=2, ensure_ascii=False))

def _ensure_entry(d: Dict[str, dict], model: str) -> Dict[str, dict]:
    if model not in d:
        d[model] = {}
    return d

def register(app: Client):

    @app.on_message(filters.private & filters.command(["createmenu"]))
    async def createmenu(client: Client, m: Message):
        # auth
        if not m.from_user or m.from_user.id not in ADMIN_IDS:
            return await m.reply_text("You are not authorized to use this command.")

        # Expect: /createmenu roni <menu text>
        parts = (m.text or "").split(None, 2)
        if len(parts) < 3:
            return await m.reply_text(
                "Usage:\n<code>/createmenu roni &lt;menu text&gt;</code>\n"
                "Models: roni, ruby, rin, savy"
            )

        model = parts[1].strip().lower()
        if model not in MODEL_KEYS:
            return await m.reply_text("Unknown model. Use: roni, ruby, rin, savy")

        menu_text = parts[2].strip()
        data = _load()
        data = _ensure_entry(data, model)
        data[model]["menu_text"] = menu_text
        _save(data)

        return await m.reply_text(
            f"✅ Saved menu text for <b>{model.title()}</b>:\n\n<blockquote>{menu_text}</blockquote>\n\n"
            "Open Menus → that model to see it live."
        )
