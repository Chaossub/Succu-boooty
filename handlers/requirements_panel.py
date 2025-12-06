# handlers/requirements_panel.py

import os
import logging
import random
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Optional, Tuple

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)
from pyrogram.errors import MessageNotModified

from pymongo import MongoClient, ASCENDING

log = logging.getLogger(__name__)

# ────────────── ENV & DB ──────────────

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI / MONGO_URI must be set for requirements_panel")

mongo = MongoClient(MONGO_URI)
db = mongo["Succubot"]
members_coll = db["requirements_members"]
members_coll.create_index([("user_id", ASCENDING)], unique=True)

OWNER_ID = int(os.getenv("OWNER_ID", os.getenv("BOT_OWNER_ID", "6964994611")))


def _parse_id_list(val: str | None) -> Set[int]:
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

_group_ids_str = os.getenv("SANCTUARY_GROUP_IDS")
if not _group_ids_str:
    _single = os.getenv("SUCCUBUS_SANCTUARY")
    SANCTUARY_GROUP_IDS: List[int] = [int(_single)] if _single else []
else:
    SANCTUARY_GROUP_IDS = [
        int(x) for x in _group_ids_str.replace(" ", "").split(",") if x
    ]

LOG_GROUP_ID: Optional[int] = None
for key in ("SANCTU_LOG_GROUP_ID", "SANCTUARY_LOG_CHANNEL"):
    if os.getenv(key):
        try:
            LOG_GROUP_ID = int(os.getenv(key))
            break
        except ValueError:
            pass

REQUIRED_MIN_SPEND = float(os.getenv("REQUIREMENTS_MIN_SPEND", "20"))

# simple in-memory state
STATE: Dict[int, Dict[str, Any]] = {}

# ────────────── helper functions ──────────────


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


async def _safe_send(app: Client, chat_id: int, text: str):
    try:
        return await app.send_message(chat_id, text)
    except Exception as e:
        log.warning("requirements_panel: failed to send message to %s: %s", chat_id, e)
        return None


async def _log_event(app: Client, text: str):
    if LOG_GROUP_ID is None:
        return
    await _safe_send(app, LOG_GROUP_ID, f"[Requirements] {text}")


def _member_doc(user_id: int) -> Dict[str, Any]:
    doc = members_coll.find_one({"user_id": user_id}) or {}
    is_owner = user_id == OWNER_ID
    is_model = user_id in MODELS or is_owner
    db_exempt = bool(doc.get("is_exempt", False))
    effective_exempt = db_exempt or is_model

    return {
        "user_id": user_id,
        "first_name": doc.get("first_name", ""),
        "username": doc.get("username"),
        "manual_spend": float(doc.get("manual_spend", 0.0)),
        "is_exempt": effective_exempt,
        "db_exempt": db_exempt,
        "is_model": is_model,
        "is_owner": is_owner,
        "reminder_sent": bool(doc.get("reminder_sent", False)),
        "final_warning_sent": bool(doc.get("final_warning_sent", False)),
        "last_updated": doc.get("last_updated"),
    }


def _display_name(doc: Dict[str, Any]) -> str:
    first_name = doc.get("first_name") or ""
    username = doc.get("username")
    if first_name and username:
        return f"{first_name} (@{username})"
    if first_name:
        return first_name
    if username:
        return f"@{username}"
    return "????"


def _format_member_status(doc: Dict[str, Any]) -> str:
    total = doc["manual_spend"]
    exempt = doc["is_exempt"]
    is_model = doc.get("is_model", False)
    is_owner = doc.get("is_owner", False)

    if is_owner:
        status = (
            "👑 <b>Sanctuary owner</b> – you’re automatically exempt from requirements. "
            "SuccuBot will never mark you behind or kick you for this."
        )
    elif exempt and is_model:
        status = (
            "✅ <b>Model</b> – you’re automatically exempt from requirements. "
            "Even if your spend shows as $0, you won’t be warned or kicked."
        )
    elif exempt:
        status = "✅ Marked exempt from requirements this month."
    elif total >= REQUIRED_MIN_SPEND:
        status = f"✅ Requirements met with ${total:.2f} logged."
    else:
        status = (
            f"⚠️ Currently behind.\n"
            f"Logged so far: ${total:.2f} (minimum ${REQUIRED_MIN_SPEND:.2f})."
        )

    lines = [
        "<b>Requirement Status</b>",
        "",
        f"<b>Member:</b> {_display_name(doc)} (<code>{doc['user_id']}</code>)",
        "",
        status,
    ]
    if doc.get("last_updated"):
        dt = doc["last_updated"].astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        lines.append(f"\nLast updated: <code>{dt}</code>")
    return "\n".join(lines)


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

# ────────────── keyboards ──────────────


def _root_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:self")],
    ]
    if is_admin:
        rows.append(
            [
                InlineKeyboardButton(
                    "🛠 Admin / Model Controls", callback_data="reqpanel:admin"
                )
            ]
        )
    # back to main sanctuary menu (your portal handler)
    rows.append(
        [
            InlineKeyboardButton(
                "⬅ Back to Sanctuary Menu", callback_data="portal:home"
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def _admin_kb(user_is_owner: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "📋 Member Status List", callback_data="reqpanel:list:0"
            ),
            InlineKeyboardButton(
                "➕ Add Manual Spend", callback_data="reqpanel:addmenu:0"
            ),
        ],
        [
            InlineKeyboardButton(
                "✅ Exempt / Un-exempt", callback_data="reqpanel:exemptmenu:0"
            )
        ],
        [
            InlineKeyboardButton(
                "📡 Scan Group Members", callback_data="reqpanel:scan"
            )
        ],
    ]
    # ONLY you can send reminder/final-warning DMs
    if user_is_owner:
        rows.append(
            [
                InlineKeyboardButton(
                    "💌 Send Reminders (pick)",
                    callback_data="reqpanel:remindmenu:0",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    "⚠️ Send Final Warnings (pick)",
                    callback_data="reqpanel:finalmenu:0",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "⬅ Back to Requirements Home", callback_data="reqpanel:home"
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def _pager_buttons(prefix: str, page: int, more: bool) -> List[InlineKeyboardButton]:
    btns: List[InlineKeyboardButton] = []
    if page > 0:
        btns.append(
            InlineKeyboardButton(
                "⬅ Prev", callback_data=f"{prefix}:{page-1}"
            )
        )
    if more:
        btns.append(
            InlineKeyboardButton(
                "Next ➡", callback_data=f"{prefix}:{page+1}"
            )
        )
    return btns


def _member_rows_for_page(
    docs: List[Dict[str, Any]], action_prefix: str, page: int, page_size: int = 8
) -> Tuple[List[List[InlineKeyboardButton]], bool]:
    start = page * page_size
    chunk = docs[start : start + page_size]
    more = len(docs) > start + page_size
    rows: List[List[InlineKeyboardButton]] = []
    for d in chunk:
        name = _display_name(d)
        uid = d["user_id"]
        rows.append(
            [
                InlineKeyboardButton(
                    name, callback_data=f"{action_prefix}:{uid}:{page}"
                )
            ]
        )
    return rows, more


# ────────────── core handlers ──────────────


def register(app: Client):

    log.info(
        "✅ handlers.requirements_panel registered (OWNER_ID=%s, super_admins=%s, models=%s, groups=%s)",
        OWNER_ID,
        SUPER_ADMINS,
        MODELS,
        SANCTUARY_GROUP_IDS,
    )

    # entry from Requirements Help button
    @app.on_callback_query(filters.regex("^reqpanel:home$"))
    async def reqpanel_home_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        is_admin = _is_admin_or_model(user_id)
        text_lines = [
            "<b>Requirements Help</b>",
            "",
            "Use this panel to check how you’re doing on Sanctuary requirements this month.",
            "",
            "• <b>Check My Status</b> – see if you’re met or behind.",
        ]
        if is_admin:
            text_lines.append(
                "• <b>Admin / Model Controls</b> – owner & model tools for requirements "
                "(lists, manual credit, exemptions, reminders)."
            )
        text_lines.append("")
        text_lines.append(
            "Regular members only see their own status. Owner & models get the full tools."
        )

        await _safe_edit_text(
            cq.message,
            text="\n".join(text_lines),
            reply_markup=_root_kb(is_admin),
            disable_web_page_preview=True,
        )
        await cq.answer()

    @app.on_callback_query(filters.regex("^reqpanel:open$"))
    async def reqpanel_open_cb(_, cq: CallbackQuery):
        await reqpanel_home_cb(_, cq)

    # owner / models tools
    @app.on_callback_query(filters.regex("^reqpanel:admin$"))
    async def reqpanel_admin_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and approved models can open this.", show_alert=True
            )
            return

        text = (
            "<b>Admin / Model Controls – Requirements</b>\n\n"
            "These tools manage Sanctuary requirements for the month. "
            "Everything here updates what SuccuBot uses for status checks and sweeps.\n\n"
            "Pick what you want to do using the buttons below – no commands needed. 💕"
        )

        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_admin_kb(_is_owner(user_id)),
            disable_web_page_preview=True,
        )
        await cq.answer()

    # self-status
    @app.on_callback_query(filters.regex("^reqpanel:self$"))
    async def reqpanel_self_cb(_, cq: CallbackQuery):
        user = cq.from_user
        doc = _member_doc(user.id)
        text = _format_member_status(doc)
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=_root_kb(_is_admin_or_model(user.id)),
            disable_web_page_preview=True,
        )

    # ────────────── Member list / view (button-only) ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:list:(\d+)$"))
    async def reqpanel_list_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and models can view the full list.", show_alert=True
            )
            return

        # data = "reqpanel:list:0"
        page = int(cq.data.split(":")[2])
        docs = list(members_coll.find().sort("user_id", ASCENDING))
        if not docs:
            text = (
                "<b>Member Status List</b>\n\n"
                "No tracked members yet. Try running a scan first."
            )
            await cq.answer()
            await _safe_edit_text(
                cq.message,
                text=text,
                reply_markup=_admin_kb(_is_owner(user_id)),
                disable_web_page_preview=True,
            )
            return

        lines = [f"<b>Member Status List</b> – page {page + 1}\n"]
        for d in docs[page * 8 : page * 8 + 8]:
            uid = d["user_id"]
            total = float(d.get("manual_spend", 0.0))
            db_exempt = d.get("is_exempt", False)
            is_owner = uid == OWNER_ID
            is_model = uid in MODELS or is_owner
            effective_exempt = db_exempt or is_model

            if is_owner:
                status = "OWNER (EXEMPT)"
            elif is_model:
                status = "MODEL (EXEMPT)"
            elif effective_exempt:
                status = "EXEMPT"
            elif total >= REQUIRED_MIN_SPEND:
                status = "MET"
            else:
                status = "BEHIND"

            lines.append(
                f"• {_display_name(d)} (<code>{uid}</code>) – {status} (${total:.2f})"
            )

        rows, more = _member_rows_for_page(docs, "reqpanel:view", page)
        pager = _pager_buttons("reqpanel:list", page, more)
        if pager:
            rows.append(pager)
        rows.append(
            [
                InlineKeyboardButton(
                    "⬅ Back to Admin / Model Controls", callback_data="reqpanel:admin"
                )
            ]
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text="\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:view:(-?\d+):(\d+)$"))
    async def reqpanel_view_member_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Not for you, babe 💋", show_alert=True)
            return

        _, _, uid_str, page_str = cq.data.split(":")
        target_id = int(uid_str)
        page = int(page_str)

        doc = _member_doc(target_id)
        text = _format_member_status(doc)

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⬅ Back to Member List", callback_data=f"reqpanel:list:{page}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅ Back to Admin / Model Controls",
                        callback_data="reqpanel:admin",
                    )
                ],
            ]
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ────────────── Add Manual Spend (button flow) ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:addmenu:(\d+)$"))
    async def reqpanel_addmenu_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        page = int(cq.data.split(":")[2])
        docs = list(members_coll.find().sort("user_id", ASCENDING))
        if not docs:
            await cq.answer("No members in the tracker yet.", show_alert=True)
            return

        lines = [
            "<b>Add Manual Spend</b>",
            "",
            "Pick the member you’re crediting. After that I’ll ask for the amount "
            "(buttons + custom) and who it was for (Roni / Ruby / etc).",
            "",
            f"Page {page + 1}",
        ]

        rows, more = _member_rows_for_page(docs, "reqpanel:addpick", page)
        pager = _pager_buttons("reqpanel:addmenu", page, more)
        if pager:
            rows.append(pager)
        rows.append(
            [
                InlineKeyboardButton(
                    "⬅ Back to Admin / Model Controls", callback_data="reqpanel:admin"
                )
            ]
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text="\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:addpick:(-?\d+):(\d+)$"))
    async def reqpanel_addpick_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can add spend.", show_alert=True)
            return

        _, _, uid_str, page_str = cq.data.split(":")
        target_id = int(uid_str)
        page = int(page_str)

        doc = _member_doc(target_id)
        STATE[user_id] = {"mode": "add_amount", "target_id": target_id, "page": page}

        text = (
            "<b>Add Manual Spend</b>\n\n"
            f"Member: {_display_name(doc)} (<code>{target_id}</code>)\n\n"
            "Pick an amount to credit for this month:"
        )

        rows = [
            [
                InlineKeyboardButton("$5", callback_data="reqpanel:addamt:5"),
                InlineKeyboardButton("$10", callback_data="reqpanel:addamt:10"),
                InlineKeyboardButton("$20", callback_data="reqpanel:addamt:20"),
            ],
            [
                InlineKeyboardButton("$25", callback_data="reqpanel:addamt:25"),
                InlineKeyboardButton("$50", callback_data="reqpanel:addamt:50"),
                InlineKeyboardButton(
                    "Custom amount", callback_data="reqpanel:addamt:custom"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅ Back to Member List",
                    callback_data=f"reqpanel:addmenu:{page}",
                )
            ],
        ]

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:addamt:(.+)$"))
    async def reqpanel_addamt_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        state = STATE.get(user_id)
        if not state or state.get("mode") != "add_amount":
            await cq.answer("This flow expired, start again from Add Manual Spend.")
            return

        amt_str = cq.data.split(":")[1]
        target_id = state["target_id"]

        if amt_str == "custom":
            STATE[user_id]["mode"] = "add_amount_custom"
            await cq.answer()
            await _safe_edit_text(
                cq.message,
                text=(
                    "<b>Add Manual Spend – Custom Amount</b>\n\n"
                    "Send me just the number for how many dollars to credit.\n\n"
                    "Example: <code>17.50</code>"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⬅ Cancel", callback_data="reqpanel:admin"
                            )
                        ]
                    ]
                ),
                disable_web_page_preview=True,
            )
            return

        amount = float(amt_str)
        STATE[user_id]["amount"] = amount
        STATE[user_id]["mode"] = "add_who"

        doc = _member_doc(target_id)
        text = (
            "<b>Add Manual Spend</b>\n\n"
            f"Member: {_display_name(doc)} (<code>{target_id}</code>)\n"
            f"Amount: ${amount:.2f}\n\n"
            "Who was this payment for?"
        )

        who_rows = [
            [
                InlineKeyboardButton("Roni", callback_data="reqpanel:addwho:Roni"),
                InlineKeyboardButton("Ruby", callback_data="reqpanel:addwho:Ruby"),
            ],
            [
                InlineKeyboardButton(
                    "Peachy", callback_data="reqpanel:addwho:Peachy"
                ),
                InlineKeyboardButton("Savy", callback_data="reqpanel:addwho:Savy"),
            ],
            [InlineKeyboardButton("Other / mixed", callback_data="reqpanel:addwho:Other")],
            [InlineKeyboardButton("⬅ Cancel", callback_data="reqpanel:admin")],
        ]

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=InlineKeyboardMarkup(who_rows),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:addwho:(.+)$"))
    async def reqpanel_addwho_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        state = STATE.get(user_id)
        if not state or state.get("mode") not in {"add_who"}:
            await cq.answer("This flow expired, start again from Add Manual Spend.")
            return

        who = cq.data.split(":")[1]
        target_id = state["target_id"]
        amount = float(state["amount"])

        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
        new_total = float(doc.get("manual_spend", 0.0)) + amount

        members_coll.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    "manual_spend": new_total,
                    "last_updated": datetime.now(timezone.utc),
                },
                "$setOnInsert": {
                    "first_name": doc.get("first_name", ""),
                },
            },
            upsert=True,
        )

        STATE.pop(user_id, None)

        await cq.answer("Saved.")
        await _safe_edit_text(
            cq.message,
            text=(
                "<b>Manual Spend Added</b>\n\n"
                f"Member: <code>{target_id}</code>\n"
                f"Amount: ${amount:.2f}\n"
                f"For: {who}\n\n"
                f"New manual total for this month: ${new_total:.2f}"
            ),
            reply_markup=_admin_kb(_is_owner(user_id)),
            disable_web_page_preview=True,
        )

        await _log_event(
            client,
            f"Manual spend +${amount:.2f} for {target_id} by {user_id} (for {who})",
        )

    # custom amount text handler (ONLY numbers)
    @app.on_message(filters.private & filters.text)
    async def requirements_state_router(client: Client, msg: Message):
        user_id = msg.from_user.id
        state = STATE.get(user_id)
        if not state:
            return

        if state.get("mode") == "add_amount_custom":
            try:
                amount = float(msg.text.strip())
            except ValueError:
                await msg.reply_text(
                    "That didn’t look like a number. Try again – just the dollars, like <code>15</code> or <code>17.50</code>.",
                )
                return

            STATE[user_id]["amount"] = amount
            STATE[user_id]["mode"] = "add_who"

            target_id = state["target_id"]
            doc = _member_doc(target_id)
            text = (
                "<b>Add Manual Spend</b>\n\n"
                f"Member: {_display_name(doc)} (<code>{target_id}</code>)\n"
                f"Amount: ${amount:.2f}\n\n"
                "Who was this payment for?"
            )
            who_rows = [
                [
                    InlineKeyboardButton(
                        "Roni", callback_data="reqpanel:addwho:Roni"
                    ),
                    InlineKeyboardButton(
                        "Ruby", callback_data="reqpanel:addwho:Ruby"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Peachy", callback_data="reqpanel:addwho:Peachy"
                    ),
                    InlineKeyboardButton(
                        "Savy", callback_data="reqpanel:addwho:Savy"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Other / mixed", callback_data="reqpanel:addwho:Other"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅ Cancel", callback_data="reqpanel:admin"
                    )
                ],
            ]
            await msg.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(who_rows),
                disable_web_page_preview=True,
            )
            return

    # ────────────── Exempt / un-exempt (button-only) ──────────────

    def _render_exempt_page(user_id: int, page: int) -> Tuple[str, InlineKeyboardMarkup]:
        docs = list(members_coll.find().sort("user_id", ASCENDING))
        lines = [
            "<b>Exempt / Un-exempt Member</b>",
            "",
            "Tap a member to flip their exempt flag for this month.",
            "<i>Owner and models are always effectively exempt even if you toggle them.</i>",
            "",
            f"Page {page + 1}",
        ]

        start = page * 8
        chunk = docs[start : start + 8]
        more = len(docs) > start + 8

        rows: List[List[InlineKeyboardButton]] = []
        for d in chunk:
            uid = d["user_id"]
            is_owner = uid == OWNER_ID
            is_model = uid in MODELS or is_owner
            db_exempt = bool(d.get("is_exempt", False))
            effective_exempt = db_exempt or is_model

            if is_owner:
                label = f"👑 {_display_name(d)} (OWNER – always exempt)"
            elif is_model:
                label = f"😈 {_display_name(d)} (MODEL – always exempt)"
            else:
                label = f"{'✅' if effective_exempt else '❌'} {_display_name(d)}"

            rows.append(
                [
                    InlineKeyboardButton(
                        label,
                        callback_data=f"reqpanel:exempttoggle:{uid}:{page}",
                    )
                ]
            )

        pager = _pager_buttons("reqpanel:exemptmenu", page, more)
        if pager:
            rows.append(pager)
        rows.append(
            [
                InlineKeyboardButton(
                    "⬅ Back to Admin / Model Controls",
                    callback_data="reqpanel:admin",
                )
            ]
        )

        return "\n".join(lines), InlineKeyboardMarkup(rows)

    @app.on_callback_query(filters.regex(r"^reqpanel:exemptmenu:(\d+)$"))
    async def reqpanel_exemptmenu_cb(_, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and models can change exemptions.", show_alert=True
            )
            return

        page = int(cq.data.split(":")[2])
        docs_count = members_coll.count_documents({})
        if docs_count == 0:
            await cq.answer("No members in the tracker yet.", show_alert=True)
            return

        text, kb = _render_exempt_page(user_id, page)
        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:exempttoggle:(-?\d+):(\d+)$"))
    async def reqpanel_exempttoggle_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer(
                "Only Roni and models can change exemptions.", show_alert=True
            )
            return

        _, _, uid_str, page_str = cq.data.split(":")
        target_id = int(uid_str)
        page = int(page_str)

        doc = members_coll.find_one({"user_id": target_id}) or {"user_id": target_id}
        new_val = not bool(doc.get("is_exempt", False))
        members_coll.update_one(
            {"user_id": target_id},
            {
                "$set": {
                    "is_exempt": new_val,
                    "last_updated": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

        await _log_event(
            client,
            f"Exempt toggled to {new_val} for {target_id} by {user_id}",
        )

        text, kb = _render_exempt_page(user_id, page)
        await cq.answer("Toggled.")
        await _safe_edit_text(
            cq.message,
            text=text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )

    # ────────────── Scan ──────────────

    @app.on_callback_query(filters.regex(r"^reqpanel:scan$"))
    async def reqpanel_scan_cb(client: Client, cq: CallbackQuery):
        user_id = cq.from_user.id
        if not _is_admin_or_model(user_id):
            await cq.answer("Only Roni and models can run scans.", show_alert=True)
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
                        {
                            "$set": {
                                "first_name": u.first_name or "",
                                "username": username,
                                "last_updated": datetime.now(timezone.utc),
                            },
                        },
                        upsert=True,
                    )
                    total_indexed += 1
            except Exception as e:
                log.warning("requirements_panel: failed scanning group %s: %s", gid, e)

        await _log_event(
            client,
            f"Scan complete by {user_id}: indexed or updated {total_indexed} members.",
        )

        await cq.answer("Scan complete.", show_alert=False)
        await _safe_edit_text(
            cq.message,
            text=(
                f"✅ Scan complete.\n"
                f"Indexed or updated {total_indexed} members from Sanctuary group(s)."
            ),
            reply_markup=_admin_kb(_is_owner(user_id)),
            disable_web_page_preview=True,
        )

    # ────────────── Reminder & final-warning menus (button-only) ──────────────

    def _eligible_reminder_docs(final: bool) -> List[Dict[str, Any]]:
        flag_field = "final_warning_sent" if final else "reminder_sent"
        docs = list(
            members_coll.find(
                {
                    "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
                    flag_field: {"$ne": True},
                }
            )
        )
        docs = [d for d in docs if d["user_id"] != OWNER_ID and d["user_id"] not in MODELS]
        return docs

    async def _show_dm_menu(
        cq: CallbackQuery, final: bool, page: int
    ):
        user_id = cq.from_user.id
        if not _is_owner(user_id):
            await cq.answer("Only Roni can send these DMs.", show_alert=True)
            return

        docs = _eligible_reminder_docs(final)
        kind = "Final Warnings" if final else "Reminders"

        if not docs:
            await cq.answer(f"No members are eligible for {kind.lower()} right now.", show_alert=True)
            await _safe_edit_text(
                cq.message,
                text=f"Nobody is currently behind and eligible for {kind.lower()}.",
                reply_markup=_admin_kb(True),
                disable_web_page_preview=True,
            )
            return

        start = page * 8
        chunk = docs[start : start + 8]
        more = len(docs) > start + 8

        lines = [
            f"<b>Send {kind} – Pick by Button</b>",
            "",
            "Tap a member’s name to send just to them.",
            "If you really want to blast everyone, there’s a button at the bottom. 😈",
            "",
            f"Page {page + 1}",
        ]
        for d in chunk:
            total = float(d.get("manual_spend", 0.0))
            lines.append(
                f"• {_display_name(d)} (<code>{d['user_id']}</code>) – BEHIND (${total:.2f})"
            )

        rows: List[List[InlineKeyboardButton]] = []
        prefix = "reqpanel:finalsendone" if final else "reqpanel:remindsendone"
        for d in chunk:
            rows.append(
                [
                    InlineKeyboardButton(
                        _display_name(d),
                        callback_data=f"{prefix}:{d['user_id']}:{page}",
                    )
                ]
            )

        all_prefix = "reqpanel:finalsendall" if final else "reqpanel:remindsendall"
        rows.append(
            [
                InlineKeyboardButton(
                    f"Send {kind} to EVERYONE on this list",
                    callback_data=all_prefix,
                )
            ]
        )

        pager_prefix = "reqpanel:finalmenu" if final else "reqpanel:remindmenu"
        pager = _pager_buttons(pager_prefix, page, more)
        if pager:
            rows.append(pager)
        rows.append(
            [
                InlineKeyboardButton(
                    "⬅ Back to Admin / Model Controls",
                    callback_data="reqpanel:admin",
                )
            ]
        )

        await cq.answer()
        await _safe_edit_text(
            cq.message,
            text="\n".join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:remindmenu:(\d+)$"))
    async def reqpanel_remindmenu_cb(_, cq: CallbackQuery):
        page = int(cq.data.split(":")[2])
        await _show_dm_menu(cq, final=False, page=page)

    @app.on_callback_query(filters.regex(r"^reqpanel:finalmenu:(\d+)$"))
    async def reqpanel_finalmenu_cb(_, cq: CallbackQuery):
        page = int(cq.data.split(":")[2])
        await _show_dm_menu(cq, final=True, page=page)

    async def _send_one_dm(
        client: Client, cq: CallbackQuery, target_id: int, final: bool, page: int
    ):
        user_id = cq.from_user.id
        if not _is_owner(user_id):
            await cq.answer("Only Roni can send these DMs.", show_alert=True)
            return

        doc = members_coll.find_one({"user_id": target_id})
        if not doc:
            await cq.answer("They’re not in the tracker anymore.", show_alert=True)
            return

        flag_field = "final_warning_sent" if final else "reminder_sent"

        name = doc.get("first_name") or "there"
        if final:
            msg = random.choice(FINAL_WARNING_MSGS).format(name=name)
        else:
            msg = random.choice(REMINDER_MSGS).format(name=name)

        sent = await _safe_send(client, target_id, msg)
        if sent:
            members_coll.update_one(
                {"user_id": target_id},
                {
                    "$set": {
                        flag_field: True,
                        "last_updated": datetime.now(timezone.utc),
                    }
                },
            )
            await _log_event(
                client,
                f"{'Final warning' if final else 'Reminder'} sent to {target_id} by {user_id}",
            )
            await cq.answer("Sent.", show_alert=False)
        else:
            await cq.answer("Couldn’t send DM (maybe they blocked the bot).", show_alert=True)

        await _show_dm_menu(cq, final=final, page=page)

    @app.on_callback_query(filters.regex(r"^reqpanel:remindsendone:(-?\d+):(\d+)$"))
    async def reqpanel_remindsendone_cb(client: Client, cq: CallbackQuery):
        _, _, uid_str, page_str = cq.data.split(":")
        await _send_one_dm(client, cq, int(uid_str), final=False, page=int(page_str))

    @app.on_callback_query(filters.regex(r"^reqpanel:finalsendone:(-?\d+):(\d+)$"))
    async def reqpanel_finalsendone_cb(client: Client, cq: CallbackQuery):
        _, _, uid_str, page_str = cq.data.split(":")
        await _send_one_dm(client, cq, int(uid_str), final=True, page=int(page_str))

    async def _send_all_dm(client: Client, cq: CallbackQuery, final: bool):
        user_id = cq.from_user.id
        if not _is_owner(user_id):
            await cq.answer("Only Roni can send these DMs.", show_alert=True)
            return

        docs = _eligible_reminder_docs(final)
        if not docs:
            await cq.answer("Nobody left on the list.", show_alert=True)
            return

        flag_field = "final_warning_sent" if final else "reminder_sent"
        count = 0
        for d in docs:
            uid = d["user_id"]
            name = d.get("first_name") or "there"
            if final:
                msg = random.choice(FINAL_WARNING_MSGS).format(name=name)
            else:
                msg = random.choice(REMINDER_MSGS).format(name=name)

            sent = await _safe_send(client, uid, msg)
            if not sent:
                continue
            members_coll.update_one(
                {"user_id": uid},
                {
                    "$set": {
                        flag_field: True,
                        "last_updated": datetime.now(timezone.utc),
                    }
                },
            )
            count += 1

        await _log_event(
            client,
            f"{'Final warnings' if final else 'Reminders'} sweep sent to {count} members by {user_id}",
        )
        await cq.answer(f"Sent to {count} member(s).", show_alert=True)
        await _safe_edit_text(
            cq.message,
            text=(
                f"{'⚠️ Final-warning' if final else '💌 Reminder'} sweep complete.\n"
                f"Sent to {count} member(s) currently behind."
            ),
            reply_markup=_admin_kb(True),
            disable_web_page_preview=True,
        )

    @app.on_callback_query(filters.regex(r"^reqpanel:remindsendall$"))
    async def reqpanel_remindsendall_cb(client: Client, cq: CallbackQuery):
        await _send_all_dm(client, cq, final=False)

    @app.on_callback_query(filters.regex(r"^reqpanel:finalsendall$"))
    async def reqpanel_finalsendall_cb(client: Client, cq: CallbackQuery):
        await _send_all_dm(client, cq, final=True)
