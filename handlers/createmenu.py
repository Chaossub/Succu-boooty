# handlers/createmenu.py
from __future__ import annotations
import os, json
from pathlib import Path
from typing import Dict, Iterable

from pyrogram import Client, filters
from pyrogram.types import Message

# Where menu overrides are stored (persisted as JSON)
DATA_PATH = Path(os.getenv("MODEL_MENU_DATA", "data/model_menus.json"))
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

MODEL_KEYS = {"roni", "ruby", "rin", "savy"}


# -------- Admin detection (accept many env names) -----------------------------
def _parse_ids(raw: str) -> Iterable[int]:
    for token in (raw or "").replace(";", ",").replace(" ", "").split(","):
        if token.isdigit():
            yield int(token)

def _get_admin_ids() -> set[int]:
    admin_vars = [
        "OWNER_IDS", "OWNERS", "OWNER_ID",
        "SUPER_ADMIN_IDS", "SUPER_ADMINS", "ADMINS",
    ]
    ids: set[int] = set()
    for var in admin_vars:
        ids.update(_parse_ids(os.getenv(var, "")))
    return ids

ADMIN_IDS = _get_admin_ids()


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

    # NOTE: allow command in private or groups
    @app.on_message(filters.command(["createmenu"]))
    async def createmenu(client: Client, m: Message):
        # auth
        user_id = m.from_user.id if m.from_user else 0
        if user_id not in ADMIN_IDS:
            return await m.reply_text("You are not authorized to use this command.")

        # Expect: /createmenu roni <menu text>
        # Works with `/createmenu@YourBot`
        raw = (m.text or "").split(None, 2)  # ['/createmenu', 'roni', '<menu text>']
        if len(raw) < 3:
            return await m.reply_text(
                "Usage:\n<code>/createmenu roni &lt;menu text&gt;</code>\n"
                "Models: roni, ruby, rin, savy"
            )

        model = raw[1].split("@", 1)[0].strip().lower()  # handle '/createmenu@bot roni ...' too
        if model not in MODEL_KEYS:
            return await m.reply_text("Unknown model. Use: roni, ruby, rin, savy")

        menu_text = raw[2].strip()
        data = _load()
        data = _ensure_entry(data, model)
        data[model]["menu_text"] = menu_text
        _save(data)

        return await m.reply_text(
            f"✅ Saved menu text for <b>{model.title()}</b>:\n\n<blockquote>{menu_text}</blockquote>\n\n"
            "Open Menus → that model to see it live."
        )
