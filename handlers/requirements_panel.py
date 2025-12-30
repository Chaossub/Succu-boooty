# handlers/requirements_panel.py
import os
import io
import re
import logging
import random
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import MessageNotModified

from pymongo import MongoClient, ASCENDING

log = logging.getLogger(__name__)

# ────────────── ENV & CONSTANTS ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))

def _parse_id_list(val: Optional[str]) -> Set[int]:
    if not val:
        return set()
    out: Set[int] = set()
    for part in val.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            log.warning("requirements_panel: bad ID in list: %r", part)
    return out

SUPER_ADMINS: Set[int] = _parse_id_list(os.getenv("SUPER_ADMINS"))
MODELS: Set[int] = _parse_id_list(os.getenv("MODELS"))

# Sanctuary group IDs to scan
_group_ids_str = os.getenv("SANCTUARY_GROUP_IDS")
if not _group_ids_str:
    _single = os.getenv("SUCCUBUS_SANCTUARY")
    SANCTUARY_GROUP_IDS: List[int] = [int(_single)] if _single else []
else:
    SANCTUARY_GROUP_IDS = [int(x) for x in _group_ids_str.replace(" ", "").split(",") if x]

# Log group
LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL", "LOG_GROUP_ID"):
    if os.getenv(key):
        try:
            LOG_GROUP_ID = int(os.getenv(key))
            break
        except ValueError:
            pass

REQUIRED_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20"))

# Model names for attribution buttons
RONI_NAME = os.getenv("RONI_NAME", "Roni")
RUBY_NAME = os.getenv("RUBY_NAME", "Ruby")
RIN_NAME  = os.getenv("RIN_NAME", "Rin")
SAVY_NAME = os.getenv("SAVY_NAME", "Savy")

MODEL_NAME_MAP: Dict[str, str] = {
    "roni": RONI_NAME,
    "ruby": RUBY_NAME,
    "rin":  RIN_NAME,
    "savy": SAVY_NAME,
}

# ────────────── Mongo (SAFE INIT) ──────────────
# Never crash the whole bot on import; just disable reqpanel if Mongo is down.

mongo: Optional[MongoClient] = None
db = None
members_coll = None
MONGO_OK = False

def _init_mongo() -> bool:
    global mongo, db, members_coll, MONGO_OK
    if MONGO_OK:
        return True
    if not MONGO_URI:
        log.error("requirements_panel: MONGODB_URI/MONGO_URI missing")
        return False
    try:
        mongo = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3500)
        db = mongo["Succubot"]
        members_coll = db["requirements_members"]
        members_coll.create_index([("user_id", ASCENDING)], unique=True)
        MONGO_OK = True
        return True
    except Exception as e:
        log.exception("requirements_panel: Mongo init failed: %s", e)
        return False

# ────────────── Simple state (picker selections) ──────────────
_PICK_STATE: Dict[int, Dict[str, Any]] = {}  # admin_id -> { "reminder": {...}, "final": {...} }

# ────────────── Helpers ──────────────

def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def _is_super_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMINS or _is_owner(user_id)

def _is_model(user_id: int) -> bool:
    return user_id in MODELS or _is_owner(user_id)

def _is_admin_or_model(user_id: int) -> bool:
    return _is_super_admin(user_id) or _is_model(user_id)

async def _safe_edit_text(msg: Message, **kwargs):
    try:
        return await msg.edit_text(**kwargs)
    except MessageNotModified:
        return msg
    except Exception as e:
        log.warning("requirements_panel: edit_text failed: %s", e)
        return msg

async def _safe_send(app: Client, chat_id: int, text: str):
    try:
        return await app.send_message(chat_id, text, disable_web_page_preview=True)
    except Exception as e:
        log.warning("requirements_panel: failed send to %s: %s", chat_id, e)
        return None

async def _log_event(app: Client, text: str):
    if LOG_GROUP_ID is None:
        return
    await _safe_send(app, LOG_GROUP_ID, f"[Requirements] {text}")

def _member_doc(user_id: int) -> Dict[str, Any]:
    """
    Load a member doc and apply derived fields:
    - Owner & models are always effectively exempt
    """
    if not _init_mongo():
        # minimal placeholder
        return {
            "user_id": user_id,
            "first_name": "",
            "username": None,
            "manual_spend": 0.0,
            "is_exempt": _is_model(user_id),
            "db_exempt": False,
            "is_model": _is_model(user_id),
            "is_owner": _is_owner(user_id),
            "reminder_sent": False,
            "final_warning_sent": False,
            "dm_ready": False,
            "last_updated": None,
        }

    doc = members_coll.find_one({"user_id": user_id}) or {}
    is_owner = _is_owner(user_id)
    is_model = _is_model(user_id)
    db_exempt = bool(doc.get("is_exempt", False))
    effective_exempt = db_exempt or is_model

    return {
        "user_id": user_id,
        "first_name": doc.get("first_name", "") or "",
        "username": doc.get("username"),
        "manual_spend": float(doc.get("manual_spend", 0.0)),
        "manual_spend_models": dict(doc.get("manual_spend_models", {})),
        "is_exempt": effective_exempt,
        "db_exempt": db_exempt,
        "is_model": is_model,
        "is_owner": is_owner,
        "reminder_sent": bool(doc.get("reminder_sent", False)),
        "final_warning_sent": bool(doc.get("final_warning_sent", False)),
        "dm_ready": bool(doc.get("dm_ready", False)),
        "last_updated": doc.get("last_updated"),
        "_id": doc.get("_id"),
    }

def _display_name_for_doc(d: Dict[str, Any]) -> str:
    first_name = (d.get("first_name") or "").strip()
    username = d.get("username")
    if username and first_name:
        return f"{first_name} @{username}"
    if first_name:
        return first_name
    if username:
        return f"@{username}"
    return "Unknown"

def _format_member_status(doc: Dict[str, Any]) -> str:
    total = float(doc.get("manual_spend", 0.0))
    exempt = bool(doc.get("is_exempt", False))
    is_model = bool(doc.get("is_model", False))
    is_owner = bool(doc.get("is_owner", False))

    name_parts = []
    if doc.get("first_name"):
        name_parts.append(doc["first_name"])
    if doc.get("username"):
        name_parts.append(f"(@{doc['username']})")
    name = " ".join(name_parts) or "Unknown"

    header = (
        "<b>Requirement Status</b>\n\n"
        f"<b>Member:</b> {name} (<code>{doc['user_id']}</code>)\n\n"
    )

    if is_owner:
        status = "👑 <b>Sanctuary owner</b> – automatically exempt from requirements."
    elif exempt and is_model:
        status = "✅ <b>Model</b> – automatically exempt from requirements."
    elif exempt:
        status = "✅ Marked exempt from requirements this month."
    elif total >= REQUIRED_MIN_SPEND:
        status = f"✅ Requirements met with ${total:.2f} logged."
    else:
        status = (
            f"⚠️ Currently behind.\n"
            f"Logged so far: ${total:.2f} (minimum ${REQUIRED_MIN_SPEND:.2f})."
        )

    lines = [header, status]
    if doc.get("last_updated"):
        try:
            dt = doc["last_updated"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"\nLast updated: <code>{dt}</code>")
        except Exception:
            pass
    return "\n".join(lines)

def _escape(s: str) -> str:
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")

def _fmt_user(d: Dict[str, Any]) -> str:
    name = (d.get("first_name") or "Unknown").strip()
    username = (d.get("username") or "").strip()
    uid = d.get("user_id")
    if username:
        return f"{name} (@{username}) — <code>{uid}</code>"
    return f"{name} — <code>{uid}</code>"

async def _try_send_dm(app: Client, user_id: int, template: str) -> Tuple[bool, str]:
    # template already includes {name}
    try:
        # Try to fetch a name from DB
        md = _member_doc(user_id)
        name = (md.get("first_name") or md.get("username") or "there").strip()
        text = template.format(name=_escape(name))
        await app.send_message(user_id, text, disable_web_page_preview=True)
        return True, "ok"
    except Exception as e:
        return False, str(e)

# ────────────── DM templates ──────────────

REMINDER_MSGS = [
    "Hi {name}! 💋 Just a sweet reminder that Sanctuary requirements are still open this month. "
    "If you’d like to stay in the Sanctuary, make sure you’ve hit your minimum by the deadline. 💞",
    "Hey {name} ✨ You’re showing as <b>behind</b> on Sanctuary requirements right now. "
    "If that’s a mistake or you’ve already played/spent, please let one of the models know so we can update it.",
    "Psst, {name}… 😈 SuccuBot here. I’m showing that you haven’t hit requirements yet for this month. "
    "Please check the menus or DM a model so we can get you caught up ♥",
]

FINAL_WARNING_MSGS = [
    "Hi {name}. This is your <b>final warning</b> for Sanctuary requirements this month. "
    "If your requirements are not met by the deadline, you’ll be removed from the Sanctuary and will "
    "need to pay the door fee again to come back.",
    "{name}, you are still showing as <b>behind</b> on Sanctuary requirements. This is your last notice. "
    "If this isn’t updated in time, you’ll be removed until requirements are met and the door fee is repaid.",
    "Final notice for this month, {name}: Sanctuary requirements are still not met on your account. "
    "If this isn’t fixed before the sweep, you’ll be removed and will need to re-enter through the door fee.",
]

# ────────────── Keyboards ──────────────

def _root_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:self")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🛠 Admin / Model Controls", callback_data="reqpanel:admin")])
    rows.append([InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="panels:root")])
    return InlineKeyboardMarkup(rows)

def _admin_kb_full() -> InlineKeyboardMarkup:
    # This matches your original “big” admin panel layout.
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Member Status List", callback_data="reqpanel:list"),
                InlineKeyboardButton("➕ Add Manual Spend", callback_data="reqpanel:add_spend"),
            ],
            [InlineKeyboardButton("✅ Exempt / Un-exempt", callback_data="reqpanel:toggle_exempt")],
            [
                InlineKeyboardButton("📡 Scan Group Members", callback_data="reqpanel:scan"),
                InlineKeyboardButton("📊 Scan & Log Status", callback_data="reqpanel:scan_log"),
            ],
            [InlineKeyboardButton("💬 DM-Ready (This Group)", callback_data="reqpanel:dm_ready_group")],
            [InlineKeyboardButton("💌 Send Reminders (Behind Only)", callback_data="reqpanel:reminders")],
            [InlineKeyboardButton("⚠️ Send Final Warnings", callback_data="reqpanel:final_warnings")],
            [InlineKeyboardButton("🧹 Kick Behind (Manual)", callback_data="kickreq:menu")],
            [InlineKeyboardButton("⬅ Back to Requirements Menu", callback_data="reqpanel:home")],
        ]
    )

# ────────────── Picker (reminders/final warnings) ──────────────

def _compute_targets() -> List[Dict[str, Any]]:
    # Everyone behind, non-exempt
    if not _init_mongo():
        return []
    docs = list(members_coll.find({}))
    out: List[Dict[str, Any]] = []
    for d in docs:
        md = _member_doc(int(d.get("user_id")))
        if md.get("is_exempt"):
            continue
        if float(md.get("manual_spend", 0.0)) >= REQUIRED_MIN_SPEND:
            continue
        out.append(md)
    out.sort(key=lambda m: (float(m.get("manual_spend", 0.0)), (_display_name_for_doc(m) or "").lower()))
    return out

def _render_picker(admin_id: int, action: str, page: int = 0) -> Tuple[str, InlineKeyboardMarkup]:
    # action in {"reminder","final"}
    st = _PICK_STATE.setdefault(admin_id, {})
    pst = st.setdefault(action, {})
    targets = pst.get("targets")
    if not isinstance(targets, list) or not targets:
        targets = _compute_targets()
        pst["targets"] = targets

    selected = set(pst.get("selected") or [])
    per_page = 10
    max_page = max(0, (len(targets) - 1) // per_page) if targets else 0
    page = max(0, min(page, max_page))
    pst["page"] = page

    title = "💌 Send Reminders (Behind Only)" if action == "reminder" else "⚠️ Send Final Warnings (Not Met)"
    lines = [
        f"<b>{title}</b>",
        f"Minimum required: <b>${REQUIRED_MIN_SPEND:.2f}</b>",
        "",
    ]
    if not targets:
        lines.append("✅ Nobody is behind right now.")
    else:
        lines.append(f"Behind members: <b>{len(targets)}</b>")
        lines.append(f"Selected: <b>{len(selected)}</b>")
        lines.append("")
        lines.append("Tap members to toggle selection. Then choose <b>Send Selected</b> or <b>Send All</b>.")

    kb_rows: List[List[InlineKeyboardButton]] = []
    start = page * per_page
    end = start + per_page

    for md in targets[start:end]:
        uid = int(md["user_id"])
        on = "✅" if uid in selected else "⬜️"
        label = f"{on} {_display_name_for_doc(md)} — ${float(md.get('manual_spend', 0.0)):.2f}"
        kb_rows.append([InlineKeyboardButton(label, callback_data=f"reqpick:{action}:toggle:{uid}")])

    if targets and max_page > 0:
        nav: List[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"reqpick:{action}:page:{page-1}"))
        nav.append(InlineKeyboardButton(f"Page {page+1}/{max_page+1}", callback_data="reqpick:noop"))
        if page < max_page:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"reqpick:{action}:page:{page+1}"))
        kb_rows.append(nav)

    kb_rows.append([
        InlineKeyboardButton("✅ Send Selected", callback_data=f"reqpick:{action}:send_selected"),
        InlineKeyboardButton("📣 Send All", callback_data=f"reqpick:{action}:send_all"),
    ])
    kb_rows.append([InlineKeyboardButton("⬅️ Back to Requirements Menu", callback_data="reqpanel:admin")])

    return "\n".join(lines), InlineKeyboardMarkup(kb_rows)

async def _send_picker(app: Client, cq: CallbackQuery, action: str, only_selected: bool):
    admin_id = cq.from_user.id
    st = _PICK_STATE.get(admin_id, {}).get(action, {}) if _PICK_STATE.get(admin_id) else {}
    targets = st.get("targets") or _compute_targets()
    selected = set(st.get("selected") or [])

    if not targets:
        await cq.answer("Nobody is behind right now.", show_alert=True)
        return

    if only_selected:
        send_list = [m for m in targets if int(m["user_id"]) in selected]
        if not send_list:
            await cq.answer("Select at least one member first.", show_alert=True)
            return
    else:
        send_list = targets

    await cq.answer("Sending…", show_alert=False)

    ok: List[Dict[str, Any]] = []
    fail: List[Tuple[Dict[str, Any], str]] = []

    for md in send_list:
        uid = int(md["user_id"])
        if action == "reminder":
            tmpl = random.choice(REMINDER_MSGS)
            flag_field = "reminder_sent"
        else:
            tmpl = random.choice(FINAL_WARNING_MSGS)
            flag_field = "final_warning_sent"

        sent, reason = await _try_send_dm(app, uid, tmpl)
        if sent:
            ok.append(md)
            # update flag safely
            if _init_mongo():
                members_coll.update_one({"user_id": uid}, {"$set": {flag_field: True}}, upsert=True)
        else:
            fail.append((md, reason))

    title = "Reminders" if action == "reminder" else "Final Warnings"
    summary_lines = [
        f"<b>{title} sent</b>",
        f"✅ Success: <b>{len(ok)}</b>",
        f"❌ Failed: <b>{len(fail)}</b>",
    ]

    if ok:
        summary_lines.append("")
        summary_lines.append("<b>Sent to:</b>")
        summary_lines += [f"• {_fmt_user(m)}" for m in ok[:60]]
        if len(ok) > 60:
            summary_lines.append(f"…and {len(ok)-60} more")

    if fail:
        summary_lines.append("")
        summary_lines.append("<b>Failed:</b>")
        for m, r in fail[:60]:
            summary_lines.append(f"• {_fmt_user(m)} — <code>{_escape(r)[:120]}</code>")
        if len(fail) > 60:
            summary_lines.append(f"…and {len(fail)-60} more")

    # DM result back to you (where you clicked the button)
    try:
        await cq.message.reply_text("\n".join(summary_lines), disable_web_page_preview=True)
    except Exception:
        pass

    # log group summary
    await _log_event(app, f"{title} run by {admin_id}: success={len(ok)} failed={len(fail)}")

    # keep picker open
    page = int(st.get("page") or 0)
    text2, kb2 = _render_picker(admin_id, action, page=page)
    await _safe_edit_text(cq.message, text=text2, reply_markup=kb2, disable_web_page_preview=True)

# ────────────── Register ──────────────

def register(app: Client):
    log.info("✅ handlers.requirements_panel registered (full controls + picker, safe mongo init)")

    # Entry point used by your menu buttons
    @app.on_callback_query(filters.regex("^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        is_admin = _is_admin_or_model(user_id)
        text_lines = [
            "<b>Requirements</b>",
            "",
            "Use this panel to check how you’re doing on Sanctuary requirements this month.",
            "",
            "• <b>Check My Status</b> – see if you’re met or behind.",
        ]
        if is_admin:
            text_lines.append("• <b>Admin / Model Controls</b> – open the tools panel (lists, scans, reminders).")
        text_lines.append("")
        text_lines.append("Owner & models get the full tools.")
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text="\n".join(text_lines),
            reply_markup=_root_kb(is_admin),
            disable_web_page_preview=True,
        )

    # Old compatibility callbacks
    @app.on_callback_query(filters.regex(r"^(requirements:help|requirements_help|requirements:open|requirements:panel)$"))
    async def reqpanel_compat_open_cb(_, cq: CallbackQuery):
        await reqpanel_home_cb(_, cq)

    # Command opener
    @app.on_message(filters.private & filters.command(["requirements", "requirementshelp", "reqhelp", "reqs"]))
    async def reqpanel_command_open(_, m: Message):
        await m.reply_text(
            "<b>Requirements</b>\n\nTap below to open the requirements panel.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 Requirements Panel", callback_data="reqpanel:home")]]),
            disable_web_page_preview=True,
        )

    # Self status
    @app.on_callback_query(filters.regex("^reqpanel:self$"))
    async def reqpanel_self_cb(_, cq: CallbackQuery):
        doc = _member_doc(cq.from_user.id)
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=_format_member_status(doc),
            reply_markup=_root_kb(_is_admin_or_model(cq.from_user.id)),
            disable_web_page_preview=True,
        )

    # Admin panel
    @app.on_callback_query(filters.regex("^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Only Roni and approved models can open this.", show_alert=True)
            return

        # If DB is down, still show the menu, but warn.
        db_note = "" if _init_mongo() else "\n\n⚠️ <b>Database is unavailable right now.</b>\nSome tools won’t work until Mongo is reachable."
        text = (
            "<b>Admin / Model Controls</b>\n\n"
            "Pick an action:" + db_note
        )
        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=_admin_kb_full(), disable_web_page_preview=True)

    # ---- Member Status List ----
    @app.on_callback_query(filters.regex("^reqpanel:list$"))
    async def reqpanel_list_cb(_, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        if not _init_mongo():
            await cq.answer("DB unavailable right now.", show_alert=True)
            return

        docs = list(members_coll.find().sort("user_id", ASCENDING).limit(80))
        if not docs:
            text = "<b>Member Status List</b>\n\nNo tracked members yet. Try running a scan first."
        else:
            lines = ["<b>Member Status List (first 80)</b>\n"]
            for d in docs:
                uid = int(d["user_id"])
                md = _member_doc(uid)
                total = float(md.get("manual_spend", 0.0))
                if md.get("is_owner"):
                    status = "OWNER (EXEMPT)"
                elif md.get("is_model"):
                    status = "MODEL (EXEMPT)"
                elif md.get("db_exempt"):
                    status = "EXEMPT"
                elif total >= REQUIRED_MIN_SPEND:
                    status = "MET"
                else:
                    status = "BEHIND"
                lines.append(f"• {_display_name_for_doc(md)} (<code>{uid}</code>) – {status} (${total:.2f})")
            text = "\n".join(lines)

        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=_admin_kb_full(), disable_web_page_preview=True)

    # ---- Scan ----
    @app.on_callback_query(filters.regex("^reqpanel:scan$"))
    async def reqpanel_scan_cb(client: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        if not _init_mongo():
            await cq.answer("DB unavailable right now.", show_alert=True)
            return
        if not SANCTUARY_GROUP_IDS:
            await cq.answer("No Sanctuary group IDs configured.", show_alert=True)
            return

        total_indexed = 0
        for gid in SANCTUARY_GROUP_IDS:
            try:
                async for member in client.get_chat_members(gid):
                    if member.user.is_bot:
                        continue
                    u = member.user
                    username = (u.username or "").lower() if u.username else None
                    members_coll.update_one(
                        {"user_id": u.id},
                        {"$set": {"first_name": u.first_name or "", "username": username, "last_updated": datetime.now(timezone.utc)},
                         "$addToSet": {"groups": gid}},
                        upsert=True,
                    )
                    total_indexed += 1
            except Exception as e:
                log.warning("requirements_panel: scan failed for %s: %s", gid, e)

        await _log_event(client, f"Scan complete by {cq.from_user.id}: indexed/updated {total_indexed} members.")
        await cq.answer("Scan complete.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=f"✅ Scan complete.\nIndexed or updated {total_indexed} members from Sanctuary group(s).",
            reply_markup=_admin_kb_full(),
            disable_web_page_preview=True,
        )

    # ---- Scan + log ----
    @app.on_callback_query(filters.regex("^reqpanel:scan_log$"))
    async def reqpanel_scan_log_cb(client: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        if not _init_mongo():
            await cq.answer("DB unavailable right now.", show_alert=True)
            return
        if not SANCTUARY_GROUP_IDS:
            await cq.answer("No Sanctuary group IDs configured.", show_alert=True)
            return

        # reuse scan
        total_indexed = 0
        for gid in SANCTUARY_GROUP_IDS:
            try:
                async for member in client.get_chat_members(gid):
                    if member.user.is_bot:
                        continue
                    u = member.user
                    username = (u.username or "").lower() if u.username else None
                    members_coll.update_one(
                        {"user_id": u.id},
                        {"$set": {"first_name": u.first_name or "", "username": username, "last_updated": datetime.now(timezone.utc)},
                         "$addToSet": {"groups": gid}},
                        upsert=True,
                    )
                    total_indexed += 1
            except Exception as e:
                log.warning("requirements_panel: scan_log scan failed for %s: %s", gid, e)

        docs = list(members_coll.find())
        total = len(docs)
        met = behind = exempt = 0
        for d in docs:
            md = _member_doc(int(d.get("user_id", 0)))
            if md.get("is_exempt"):
                exempt += 1
            elif float(md.get("manual_spend", 0.0)) >= REQUIRED_MIN_SPEND:
                met += 1
            else:
                behind += 1

        summary = (
            "📊 <b>Sanctuary Requirements Scan</b>\n\n"
            f"👥 Total members tracked: <b>{total}</b>\n"
            f"✅ Requirements met: <b>{met}</b>\n"
            f"⚠️ Behind: <b>{behind}</b>\n"
            f"🟢 Exempt (models/owner/exempt): <b>{exempt}</b>\n\n"
            f"📡 Indexed/updated this run: <b>{total_indexed}</b>\n"
            f"💵 Minimum required: ${REQUIRED_MIN_SPEND:.2f}"
        )
        await _log_event(client, f"Scan+log by {cq.from_user.id}: indexed {total_indexed} met={met} behind={behind} exempt={exempt}.")
        if LOG_GROUP_ID:
            await _safe_send(client, LOG_GROUP_ID, summary)

        await cq.answer("Scan & log complete ✅", show_alert=True)
        await _safe_edit_text(cq.message, text="✅ Scan & log complete. Summary sent to the log group.", reply_markup=_admin_kb_full())

    # ---- Reminders / Final warnings picker ----
    @app.on_callback_query(filters.regex("^reqpanel:reminders$"))
    async def reqpanel_reminders_cb(app_client: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        if not _init_mongo():
            await cq.answer("DB unavailable right now.", show_alert=True)
            return
        text, kb = _render_picker(cq.from_user.id, "reminder", page=0)
        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=kb)

    @app.on_callback_query(filters.regex("^reqpanel:final_warnings$"))
    async def reqpanel_final_warnings_cb(app_client: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        if not _init_mongo():
            await cq.answer("DB unavailable right now.", show_alert=True)
            return
        text, kb = _render_picker(cq.from_user.id, "final", page=0)
        await cq.answer()
        await _safe_edit_text(cq.message, text=text, reply_markup=kb)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):toggle:(\d+)$"))
    async def reqpick_toggle_cb(app_client: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        action = cq.data.split(":")[1]
        uid = int(cq.data.split(":")[3])
        admin_id = cq.from_user.id
        pst = _PICK_STATE.setdefault(admin_id, {}).setdefault(action, {})
        selected = set(pst.get("selected") or [])
        if uid in selected:
            selected.remove(uid)
        else:
            selected.add(uid)
        pst["selected"] = list(selected)
        page = int(pst.get("page") or 0)
        text2, kb2 = _render_picker(admin_id, action, page=page)
        await cq.answer()
        await _safe_edit_text(cq.message, text=text2, reply_markup=kb2)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):page:(\d+)$"))
    async def reqpick_page_cb(app_client: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        action = cq.data.split(":")[1]
        page = int(cq.data.split(":")[3])
        text2, kb2 = _render_picker(cq.from_user.id, action, page=page)
        await cq.answer()
        await _safe_edit_text(cq.message, text=text2, reply_markup=kb2)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_selected$"))
    async def reqpick_send_selected_cb(app_client: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        action = cq.data.split(":")[1]
        await _send_picker(app_client, cq, action, only_selected=True)

    @app.on_callback_query(filters.regex(r"^reqpick:(reminder|final):send_all$"))
    async def reqpick_send_all_cb(app_client: Client, cq: CallbackQuery):
        if not _is_admin_or_model(cq.from_user.id):
            await cq.answer("Admins only.", show_alert=True)
            return
        action = cq.data.split(":")[1]
        await _send_picker(app_client, cq, action, only_selected=False)

    @app.on_callback_query(filters.regex("^reqpick:noop$"))
    async def reqpick_noop_cb(_, cq: CallbackQuery):
        await cq.answer()
