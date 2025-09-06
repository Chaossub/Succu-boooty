# dm_foolproof.py
import json, os, time
from pyrogram import filters
from pyrogram.types import Message

# pull the texts/keyboards from panels so /start can show the normal UI
from handlers.panels import (
    info_card_text,
    main_welcome_text,
    get_main_panel,
)

DATA_FILE = "dm_ready.json"


def _load_dmready() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_dmready(d: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=2)


def _ago(ts: float) -> str:
    delta = max(0, int(time.time() - ts))
    d, r = divmod(delta, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    if d:
        return f"{d}d {h}h ago"
    if h:
        return f"{h}h {m}m ago"
    return f"{m}m ago"


def register(app):
    # SINGLE /start entrypoint — sends:
    #   1) “What can this bot do?” info card
    #   2) Main welcome with buttons
    # Also marks DM-ready ONCE per user (persists across restarts).
    @app.on_message(filters.command("start"))
    async def _start(client, msg: Message):
        user = msg.from_user
        uid = str(user.id)
        data = _load_dmready()

        # Mark DM-ready only if not already set (survives restarts via dm_ready.json)
        if uid not in data:
            data[uid] = {
                "id": user.id,
                "name": user.first_name or "Someone",
                "username": f"@{user.username}" if user.username else "(no username)",
                "since": time.time(),
            }
            _save_dmready(data)
            await msg.reply_text(f"✅ DM-ready — {data[uid]['name']} {data[uid]['username']}")

        # 1) Info card (separate message, like your original flow)
        await msg.reply_text(info_card_text())

        # 2) Main welcome + buttons
        await msg.reply_text(
            main_welcome_text(),
            reply_markup=get_main_panel(),
            disable_web_page_preview=True,
        )

    # /dmreadylist — show all marked, with “since … ago”
    @app.on_message(filters.command("dmreadylist"))
    async def _dmreadylist(client, msg: Message):
        data = _load_dmready()
        if not data:
            await msg.reply_text("📭 Nobody is DM-ready yet.")
            return

        # Stable ordering: newest first
        rows = sorted(data.values(), key=lambda x: x.get("since", 0), reverse=True)
        lines = ["📋 **DM-ready (all)**"]
        for r in rows:
            since = r.get("since")
            since_s = _ago(since) if isinstance(since, (int, float)) else "unknown"
            lines.append(f"• {r['name']} {r['username']} — `{r['id']}` — since {since_s}")

        await msg.reply_text("\n".join(lines))

