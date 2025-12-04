# handlers/requirements_panel.py
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pymongo import MongoClient, ASCENDING

log = logging.getLogger(__name__)

# ───────────────── ENV / ROLES ─────────────────

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))

# SUPER_ADMINS = "123,456"
_super_raw = os.getenv("SUPER_ADMINS", "").strip()
SUPER_ADMINS = {
    int(x) for x in _super_raw.replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()
}
SUPER_ADMINS.add(OWNER_ID)

# Model IDs from env (RONI_ID, RUBY_ID, RIN_ID, SAVY_ID)
def _env_int(name: str) -> int | None:
    v = os.getenv(name)
    if not v:
        return None
    v = v.strip()
    if not v.lstrip("-").isdigit():
        return None
    return int(v)


MODEL_IDS = {
    v
    for v in [
        _env_int("RONI_ID"),
        _env_int("RUBY_ID"),
        _env_int("RIN_ID"),
        _env_int("SAVY_ID"),
    ]
    if v is not None
}

# Sanctuary groups to scan
def _parse_id_list(raw: str) -> List[int]:
    out: List[int] = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        if p.lstrip("-").isdigit():
            out.append(int(p))
    return out


SANCTUARY_GROUP_IDS: List[int] = _parse_id_list(
    os.getenv("SANCTUARY_GROUP_IDS", "")
)

if not SANCTUARY_GROUP_IDS:
    # Fallback to single main group
    main_gid = _env_int("SUCCUBUS_SANCTUARY")
    if main_gid:
        SANCTUARY_GROUP_IDS = [main_gid]

SANCTU_LOG_GROUP_ID = _env_int("SANCTU_LOG_GROUP_ID") or _env_int(
    "SANCTUARY_LOG_CHANNEL"
)

# ───────────────── MONGO ─────────────────

_MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
if not _MONGO_URI:
    raise RuntimeError("MONGO_URI / MONGODB_URI is required for requirements_panel")

_mclient = MongoClient(_MONGO_URI)
_db = _mclient["Succubot"]

members_coll = _db["requirements_members"]
payments_coll = _db["requirements_payments"]

# Indexes (idempotent)
members_coll.create_index([("user_id", ASCENDING)], unique=True)
payments_coll.create_index([("month_key", ASCENDING), ("user_id", ASCENDING)])


# ───────────────── ROLE HELPERS ─────────────────

def _is_owner(uid: int) -> bool:
    return uid == OWNER_ID


def _is_super(uid: int) -> bool:
    return uid in SUPER_ADMINS


def _is_model(uid: int) -> bool:
    return uid in MODEL_IDS


def _role_for(uid: int) -> str:
    """
    owner/superadmin => "owner"
    model            => "model"
    everyone else    => "user"
    """
    if _is_super(uid):
        return "owner"
    if _is_model(uid):
        return "model"
    return "user"


# ───────────────── TEXT / MESSAGES ─────────────────

REQUIREMENTS_PANEL_TEXT = (
    "📌 <b>Requirements Panel – Owner / Models</b>\n\n"
    "Use these tools to manage Sanctuary requirements for the month.\n"
    "Everything you do here updates what SuccuBot uses when checking "
    "member status or running sweeps, so double-check before you confirm changes.\n\n"
    "From here you can:\n"
    "▫️ View the full member status list\n"
    "▫️ Add manual spend credit for offline payments\n"
    "▫️ Exempt / un-exempt members\n"
    "▫️ Scan groups into the tracker\n"
    "▫️ Send reminder DMs to members who are behind\n"
    "▫️ Send final-warning DMs to those still not meeting minimums\n\n"
    "All changes here affect this month’s requirement checks and future sweeps/reminders.\n\n"
    "<i>Only you and approved model admins see this panel. Members just see their own status.</i>"
)

# Randomized reminder messages – behind, final etc.
# (You can tweak / add more strings any time.)
REMINDER_MESSAGES_BEHIND: List[str] = [
    "👀 Little Sanctuary check-in: you’re a bit behind on this month’s requirements. "
    "If you want to stay in the Sanctuary, make sure you get your spend or games in before the deadline, okay? 💋",

    "✨ Psst… your name popped up on my ‘behind on requirements’ list. "
    "We’d love to keep you in the Sanctuary, so please catch up before the month resets. 💕",

    "📌 Friendly reminder from your SuccuBabes: you haven’t quite met this month’s minimums yet. "
    "Take a peek at the rules and grab a game or a goodie so you don’t lose access. 😈",
]

FINAL_WARNING_MESSAGES: List[str] = [
    "🚨 Final Sanctuary warning: you still haven’t met this month’s requirements. "
    "If nothing changes by the deadline, you’ll be removed from the Sanctuary until you’re ready to meet the minimums.",

    "❗ This is your last reminder about requirements. "
    "You’re still short for this month and will be removed if you don’t catch up before the cutoff.",

    "⚠️ Final notice: your account is still marked as not meeting Sanctuary requirements. "
    "Please fix it ASAP if you want to keep your access.",
]


# ───────────────── SMALL UTILITIES ─────────────────

def _month_key_now() -> str:
    now = datetime.utcnow()
    return f"{now.year:04d}-{now.month:02d}"


def _build_owner_keyboard() -> InlineKeyboardMarkup:
    # Full admin / owner keyboard
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📋 Member Status List", callback_data="reqpanel:list_members"
                ),
                InlineKeyboardButton(
                    "➕ Add Manual Spend", callback_data="reqpanel:add_spend"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛡 Exempt / Un-exempt", callback_data="reqpanel:exempt_menu"
                )
            ],
            [
                InlineKeyboardButton(
                    "📡 Scan Group Members", callback_data="reqpanel:scan"
                )
            ],
            [
                InlineKeyboardButton(
                    "💌 Send Reminders (Behind Only)",
                    callback_data="reqpanel:send_reminders",
                )
            ],
            [
                InlineKeyboardButton(
                    "🚨 Send Final Warnings",
                    callback_data="reqpanel:send_final",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back to Requirements Menu",
                    callback_data="reqpanel:home",
                )
            ],
        ]
    )


def _build_model_keyboard() -> InlineKeyboardMarkup:
    # Limited model keyboard (no scan / no exemptions / no final warnings)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📋 Member Status List", callback_data="reqpanel:list_members"
                ),
                InlineKeyboardButton(
                    "➕ Add Manual Spend", callback_data="reqpanel:add_spend"
                ),
            ],
            [
                InlineKeyboardButton(
                    "💌 Send Reminders (Behind Only)",
                    callback_data="reqpanel:send_reminders",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back to Requirements Menu",
                    callback_data="reqpanel:home",
                )
            ],
        ]
    )


def _build_denied_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅️ Back to Sanctuary Menu", callback_data="portal:home"
                )
            ]
        ]
    )


def _log_to_group(client: Client, text: str):
    if not SANCTU_LOG_GROUP_ID:
        return
    try:
        client.loop.create_task(
            client.send_message(SANCTU_LOG_GROUP_ID, text, disable_web_page_preview=True)
        )
    except Exception as e:
        log.warning("requirements_panel: failed to send log message: %s", e)


# ───────────────── CORE DB HELPERS ─────────────────

def upsert_member_from_tg(user_obj, group_id: int):
    """
    Store / update a member from Telegram user object.
    """
    if user_obj.is_bot:
        return

    members_coll.update_one(
        {"user_id": user_obj.id},
        {
            "$set": {
                "user_id": user_obj.id,
                "first_name": user_obj.first_name or "",
                "last_name": user_obj.last_name or "",
                "username": user_obj.username or "",
                "updated_at": datetime.utcnow(),
            },
            "$addToSet": {"groups": group_id},
        },
        upsert=True,
    )


def add_manual_spend(user_id: int, amount: float, note: str | None = None):
    now = datetime.utcnow()
    month_key = _month_key_now()
    doc = {
        "user_id": user_id,
        "amount": float(amount),
        "note": note or "",
        "created_at": now,
        "month_key": month_key,
    }
    payments_coll.insert_one(doc)


def get_monthly_progress() -> Tuple[int, int]:
    """
    Returns (met, total). For now, this is a very simple calculation:
    - We treat anyone with >= 20 spend this month as 'met'.
    - Everyone else in members_coll is 'total'.
    You can tweak thresholds later.
    """
    month_key = _month_key_now()
    pipeline = [
        {"$match": {"month_key": month_key}},
        {
            "$group": {
                "_id": "$user_id",
                "total": {"$sum": "$amount"},
            }
        },
    ]
    spends: Dict[int, float] = {
        row["_id"]: float(row["total"]) for row in payments_coll.aggregate(pipeline)
    }

    all_members = [m["user_id"] for m in members_coll.find({}, {"user_id": 1})]
    total = len(all_members)
    if not total:
        return 0, 0

    MET_THRESHOLD = float(os.getenv("REQUIREMENTS_SPEND_MIN", "20"))
    met = sum(1 for uid in all_members if spends.get(uid, 0.0) >= MET_THRESHOLD)
    return met, total


# ───────────────── SCAN HELPERS ─────────────────

async def scan_sanctuary_groups(app: Client) -> int:
    """
    Scan all configured SANCTUARY_GROUP_IDS and upsert members into Mongo.

    This DOES NOT care where the command was pressed (DM or group);
    it always uses the env-configured group IDs.
    """
    if not SANCTUARY_GROUP_IDS:
        raise RuntimeError("No SANCTUARY_GROUP_IDS or SUCCUBUS_SANCTUARY configured")

    total = 0
    for gid in SANCTUARY_GROUP_IDS:
        try:
            async for member in app.get_chat_members(gid):
                upsert_member_from_tg(member.user, gid)
                total += 1
        except Exception as e:
            log.warning("requirements_panel: failed scanning group %s: %s", gid, e)
    return total


# ───────────────── REGISTER ─────────────────

def register(app: Client):
    # Just so we don't crash if payments module is missing
    try:
        met, total = get_monthly_progress()
        log.info(
            "requirements_panel: payments.get_monthly_progress -> met=%s total=%s",
            met,
            total,
        )
    except Exception as e:
        log.warning(
            "requirements_panel: payments.get_monthly_progress not available, using dummy 0/0 (%s)",
            e,
        )

    log.info(
        "✅ handlers.requirements_panel registered (OWNER_ID=%s, super_admins=%s, models=%s, groups=%s)",
        OWNER_ID,
        SUPER_ADMINS,
        MODEL_IDS,
        SANCTUARY_GROUP_IDS,
    )

    # ── ENTRY POINT: open the panel (owner/models only) ──
    @app.on_callback_query(filters.regex(r"^reqpanel:open$"))
    async def reqpanel_open_cb(_, cq: CallbackQuery):
        uid = cq.from_user.id
        role = _role_for(uid)

        if role == "user":
            await cq.message.edit_text(
                "You don’t have access to the Requirements Panel.\n"
                "If you think this is a mistake, contact Sanctuary management.",
                reply_markup=_build_denied_keyboard(),
            )
            await cq.answer()
            return

        kb = _build_owner_keyboard() if role == "owner" else _build_model_keyboard()
        await cq.message.edit_text(
            REQUIREMENTS_PANEL_TEXT,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # Simple "home" goes back to same panel
    @app.on_callback_query(filters.regex(r"^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        uid = cq.from_user.id
        role = _role_for(uid)

        if role == "user":
            await cq.message.edit_text(
                "You don’t have access to the Requirements Panel.\n"
                "If you think this is a mistake, contact Sanctuary management.",
                reply_markup=_build_denied_keyboard(),
            )
            await cq.answer()
            return

        kb = _build_owner_keyboard() if role == "owner" else _build_model_keyboard()
        await cq.message.edit_text(
            REQUIREMENTS_PANEL_TEXT,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ── SCAN GROUPS ──
    @app.on_callback_query(filters.regex(r"^reqpanel:scan$"))
    async def reqpanel_scan_cb(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        if not _is_super(uid):
            await cq.answer("Only Roni / super admins can run a scan.", show_alert=True)
            return

        try:
            count = await scan_sanctuary_groups(client)
            msg = f"✅ Scan complete.\nIndexed or updated <b>{count}</b> members from Sanctuary group(s)."
            await cq.message.edit_text(
                msg,
                reply_markup=_build_owner_keyboard(),
                disable_web_page_preview=True,
            )
            await cq.answer("Scan complete.", show_alert=False)
            _log_to_group(
                client,
                f"✅ Requirements scan run by <code>{uid}</code> → indexed {count} members.",
            )
        except Exception as e:
            log.exception("requirements_panel: scan failed: %s", e)
            await cq.answer("Scan failed. Check logs.", show_alert=True)

    # ── MEMBER STATUS LIST (owner + models) ──
    @app.on_callback_query(filters.regex(r"^reqpanel:list_members$"))
    async def reqpanel_list_members_cb(client: Client, cq: CallbackQuery):
        uid = cq.from_user.id
        role = _role_for(uid)
        if role == "user":
            await cq.answer("You don’t have access to member status.", show_alert=True)
            return

        docs = list(
            members_coll.find({}, {"user_id": 1, "first_name": 1, "username": 1}).limit(
                50
            )
        )
        if not docs:
            text = "No tracked members yet. Try running a scan first."
        else:
            lines = []
            for d in docs:
                uname = f"@{d.get('username')}" if d.get("username") else ""
                nm = d.get("first_name") or "Member"
                lines.append(f"• <code>{d['user_id']}</code> {nm} {uname}")
            text = "📋 <b>Tracked members (first 50):</b>\n\n" + "\n".join(lines)

        kb = _build_owner_keyboard() if role == "owner" else _build_model_keyboard()
        await cq.message.edit_text(
            text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
        await cq.answer()

    # ── ADD MANUAL SPEND (owner + models) ──
    @app.on_callback_query(filters.regex(r"^reqpanel:add_spend$"))
    async def reqpanel_add_spend_cb(_, cq: CallbackQuery):
        uid = cq.from_user.id
        role = _role_for(uid)
        if role == "user":
            await cq.answer("You don’t have permission to add manual spend.", show_alert=True)
            return

        text = (
            "➕ <b>Add Manual Spend</b>\n\n"
            "Send me a message in this format:\n"
            "<code>USER_ID  amount  [note]</code>\n\n"
            "Example:\n"
            "<code>123456789  15  from CashApp game night</code>\n\n"
            "This adds extra credited dollars on top of Stripe games for this month only."
        )
        await cq.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Back", callback_data="reqpanel:home"
                        )
                    ]
                ]
            ),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_message(filters.private & filters.reply)
    async def requirements_reply_handler(client: Client, m: Message):
        """
        When Roni / models reply to the 'Add Manual Spend' message in DMs
        with 'USER_ID amount note', parse and store.
        """
        uid = m.from_user.id
        role = _role_for(uid)
        if role == "user":
            return

        if "Add Manual Spend" not in (m.reply_to_message.text or ""):
            return

        parts = (m.text or "").split()
        if len(parts) < 2:
            await m.reply_text(
                "Format is:\n<code>USER_ID  amount  [note]</code>", quote=True
            )
            return

        try:
            target_id = int(parts[0])
            amount = float(parts[1])
        except ValueError:
            await m.reply_text("USER_ID and amount must be numbers.", quote=True)
            return

        note = " ".join(parts[2:]) if len(parts) > 2 else ""

        add_manual_spend(target_id, amount, note)
        await m.reply_text(
            f"✅ Logged <b>${amount:.2f}</b> manual credit for <code>{target_id}</code>.\nNote: {note or '—'}",
            quote=True,
        )
        _log_to_group(
            client,
            f"💰 Manual spend added by <code>{uid}</code> → user <code>{target_id}</code> +${amount:.2f}\nNote: {note}",
        )

    # ── PLACEHOLDERS FOR EXEMPT / REMINDERS / FINAL WARNINGS ──
    # (Buttons already wired; full DM-sending logic can be filled out later.)

    @app.on_callback_query(filters.regex(r"^reqpanel:exempt_menu$"))
    async def reqpanel_exempt_menu_cb(_, cq: CallbackQuery):
        if not _is_super(cq.from_user.id):
            await cq.answer("Only Roni / super admins can change exemptions.", show_alert=True)
            return

        await cq.answer("Exempt menu coming soon 💕", show_alert=True)

    @app.on_callback_query(filters.regex(r"^reqpanel:send_reminders$"))
    async def reqpanel_send_reminders_cb(_, cq: CallbackQuery):
        uid = cq.from_user.id
        role = _role_for(uid)
        if role == "user":
            await cq.answer("You don’t have permission to send reminders.", show_alert=True)
            return

        # Real logic later – for now, just acknowledge.
        await cq.answer("Reminder sending logic will go here 💌", show_alert=True)

    @app.on_callback_query(filters.regex(r"^reqpanel:send_final$"))
    async def reqpanel_send_final_cb(_, cq: CallbackQuery):
        if not _is_super(cq.from_user.id):
            await cq.answer("Only Roni / super admins can send final warnings.", show_alert=True)
            return

        await cq.answer("Final-warning logic will go here ⚠️", show_alert=True)
