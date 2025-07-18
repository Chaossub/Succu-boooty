import os
from pyrogram import Client
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client(
    "SuccuBotTouch",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

async def touch_groups():
    # Scan env vars for possible group IDs/usernames
    group_vars = [k for k in os.environ if k.endswith("_CHAT") or k.endswith("_GROUP")]
    if not group_vars:
        print("No _CHAT or _GROUP variables found in your environment.")
        return

    for var in group_vars:
        value = os.environ[var]
        for group in value.split(","):
            group = group.strip()
            if not group:
                continue
            try:
                await app.send_message(group, "🤖 Bot is now ready to post flyers here! (This message is for setup; you can delete it.)")
                print(f"✅ Touched {group} ({var})")
            except Exception as e:
                print(f"❌ Could not touch {group} ({var}): {e}")

if __name__ == "__main__":
    app.start()
    app.loop.run_until_complete(touch_groups())
    app.stop()
