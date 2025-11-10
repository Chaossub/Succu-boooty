# reset_check.py
# Minimal health-check runner for SuccuBot
import os
import asyncio
from pyrogram import Client, filters, idle

OWNER_ID = 6964994611  # Roni

def get_token() -> str:
    token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing BOT_TOKEN (or TELEGRAM_BOT_TOKEN) in environment.")
    return token

BOT_TOKEN = get_token()

# Use a clean session name so this doesn't clash with your main session file
app = Client(name="succubot_reset_check", bot_token=BOT_TOKEN)

@app.on_message(filters.command("start") & filters.private)
async def _start_min(_, m):
    await m.reply_text(
        "Hi! I'm alive. (Minimal /start)\n\n"
        "If your regular /start doesn't answer, your usual handler is being blocked by a filter."
    )

@app.on_message(filters.command("health") & (filters.private | filters.group))
async def _health(_, m):
    await m.reply_text("✅ Health OK")

# Catch-all logger for private messages (helps verify delivery)
@app.on_message(filters.private)
async def _debug_echo(_, m):
    print(f"[ECHO] chat_id={m.chat.id} from={getattr(m.from_user,'id',None)} text={m.text!r}")

async def main():
    await app.start()
    print("✅ reset_check.py booted")

    # Try to DM the owner so we know outbound works
    try:
        await app.send_message(OWNER_ID, "✅ SuccuBot booted and can send messages. (reset_check.py)")
    except Exception as e:
        print(f"⚠️ Could not DM owner: {e}")

    # Stay alive until stopped
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
