# main.py
# main.py
import logging
import os
from pyrogram import Client
from dotenv import load_dotenv

# Load environment
load_dotenv()

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("SuccuBot")

# ---------- Bot credentials ----------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not (API_ID and API_HASH and BOT_TOKEN):
    raise RuntimeError("API_ID, API_HASH, and BOT_TOKEN must be set.")

# ---------- Pyrogram client ----------
app = Client(
    "SuccuBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=None,  # we wire modules manually
)

# ---------- Utility ----------
def wire(import_path: str):
    """Import module and call register(app) if present. Logs on failure, keeps going."""
    try:
        mod = __import__(import_path, fromlist=["register"])
        if hasattr(mod, "register"):
            mod.register(app)
            log.info(f"✅ Wired: {import_path}")
        else:
            log.warning(f"⚠️ No register() in {import_path}")
    except Exception as e:
        log.error(f"❌ Failed to wire {import_path}: {e}", exc_info=True)

# ---------- Handlers ----------
def wire_all_handlers():
    # The ONLY /start portal — keep just this one to prevent duplicates.
    wire("dm_foolproof")

    # Core UI & panels
    wire("handlers.menu")             # Menus UI (💕 Menus, model menus)
    wire("handlers.createmenu")       # /createmenu <model> <text>
    wire("handlers.contact_admins")   # Contact Admins callbacks (no /start inside)
    wire("handlers.help_panel")       # Help buttons/panels

    # Requirements / Ops
    wire("handlers.enforce_requirements")  # /reqstatus, /reqremind, /reqreport, /reqsweep, etc.
    wire("handlers.req_handlers")          # legacy req commands (/reqadd, /reqgame, /reqexport, ...)
    wire("handlers.test_send")             # /test -> DM "test" to DM-ready missing requirements

    # DM tools
    wire("handlers.dmnow")         # /dmnow -> deep link to DM + mark DM-ready
    wire("handlers.dm_admin")      # /dmreadylist, /dmreadyclear

    # Schedulers & Flyers
    wire("handlers.flyer")              # /flyer, /addflyer, /deleteflyer, /flyerhelp, ...
    wire("handlers.flyer_scheduler")    # /scheduleflyer, /listscheduledflyers, /cancelflyer, ...
    wire("handlers.schedulemsg")        # /schedulemsg, /listmsgs, /cancelmsg

    # Moderation & Federation
    wire("handlers.moderation")    # /warn, /warns, /mute, /ban, /kick, /userinfo, ...
    wire("handlers.warnings")      # alternate warnings module (if present)
    wire("handlers.federation")    # /createfed, /fedban, /fedadmins, ...

    # Summons / XP / Fun / Misc
    wire("handlers.summon")        # /summon, /summonall, /trackall
    wire("handlers.xp")            # /naughtystats, /resetxp (and XP-linked fun cmds)
    wire("handlers.fun")           # /bite, /kiss, /spank, /tease (standalone fun)
    wire("handlers.misc")          # /ping, etc.
    wire("handlers.hi")            # /hi
    wire("handlers.warmup")        # /warmup
    wire("handlers.health")        # healthcheck if present
    wire("handlers.welcome")       # welcome extras (should NOT own /start)

    # Admin utilities
    wire("handlers.bloop")         # /bloop -> full command index (admin-only)
    wire("handlers.whoami")        # /whoami -> show caller's Telegram ID

    # ❌ IMPORTANT: Do NOT wire the old portal (it duplicates /start)
    # wire("handlers.dm_portal")

if __name__ == "__main__":
    wire_all_handlers()
    log.info("🚀 SuccuBot starting…")
    app.run()

