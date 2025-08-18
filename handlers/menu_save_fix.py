# handlers/menu_save_fix.py
import os, json
from pyrogram import Client, filters
from pyrogram.types import Message

MENUS_PATH = os.getenv("MENUS_PATH", "./data/menus.json")

def _ensure_dir(path: str):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)

def _load_menus():
    try:
        with open(MENUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_menus(data: dict):
    _ensure_dir(MENUS_PATH)
    tmp = MENUS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MENUS_PATH)

SLUGS = {"roni": "Roni", "ruby": "Ruby", "rin": "Rin", "savy": "Savy"}

def _is_editor(uid: int) -> bool:
    def to_int(s):
        try: return int(str(s)) if s not in (None,"","None") else None
        except: return None
    owner = to_int(os.getenv("OWNER_ID"))
    super_admin = to_int(os.getenv("SUPER_ADMIN_ID"))
    extras = set()
    if os.getenv("MENU_EDITORS"):
        for tok in os.getenv("MENU_EDITORS").split(","):
            try:
                v = int(tok.strip())
                extras.add(v)
            except: pass
    return uid in {x for x in (owner, super_admin) if x} | extras

def register(app: Client):
    @app.on_message(filters.command("addmenu"))
    async def addmenu(client: Client, m: Message):
        uid = m.from_user.id if m.from_user else 0
        if not _is_editor(uid):
            return await m.reply_text("Admins only for saving menus.")

        # Parse: /addmenu <slug> [optional text…]
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 2:
            return await m.reply_text("Usage: /addmenu <roni|ruby|rin|savy> (reply with text or put text after the slug).")

        slug = parts[1].strip().lower()
        if slug not in SLUGS:
            return await m.reply_text("Unknown model. Use one of: roni, ruby, rin, savy.")

        # Prefer inline text; else use reply text
        inline_text = parts[2].strip() if len(parts) >= 3 else ""
        if not inline_text and m.reply_to_message:
            inline_text = (m.reply_to_message.text or m.reply_to_message.caption or "").strip()

        if not inline_text:
            return await m.reply_text("No text found. Either put the menu text after the slug or reply to a message that has the text.")

        try:
            data = _load_menus()
            data[slug] = inline_text
            _save_menus(data)
            await m.reply_text(f"✅ Saved menu for {SLUGS[slug]}.")
        except Exception as e:
            await m.reply_text(f"Could not save menu: {e}")

    @app.on_message(filters.command("listmenus"))
    async def listmenus(client: Client, m: Message):
        data = _load_menus()
        if not data:
            return await m.reply_text("No menus saved yet.")
        lines = [f"• {SLUGS.get(k,k)}" for k in data.keys()]
        await m.reply_text("Saved menus:\n" + "\n".join(lines))

    @app.on_message(filters.command("changemenu"))
    async def changemenu(client: Client, m: Message):
        # Same parsing as addmenu; overwrite existing
        parts = (m.text or "").split(maxsplit=2)
        if len(parts) < 2:
            return await m.reply_text("Usage: /changemenu <roni|ruby|rin|savy> (reply with new text or put text after slug).")
        m.text = m.text.replace("/changemenu", "/addmenu", 1)
        await addmenu(client, m)  # reuse logic
