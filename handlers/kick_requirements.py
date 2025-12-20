# handlers/kick_requirements.py

import logging
from typing import Dict, List, Tuple

from pyrogram import Client
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

log = logging.getLogger(__name__)


def _display_name(first: str | None, last: str | None, username: str | None, user_id: int) -> str:
    name = ((first or "") + (" " + last if last else "")).strip()
    if name:
        return name
    if username:
        return f"@{username}"
    return str(user_id)


async def _get_group_members_map(app: Client, chat_id: int) -> Dict[int, Tuple[str, str, str]]:
    """user_id -> (first, last, username)"""
    out: Dict[int, Tuple[str, str, str]] = {}
    async for m in app.get_chat_members(chat_id):
        u = m.user
        if not u:
            continue
        out[u.id] = (u.first_name or "", u.last_name or "", u.username or "")
    return out


def _compute_behind_for_group(member_map: Dict[int, Tuple[str, str, str]], docs_by_uid: Dict[int, dict], *, rp) -> List[Tuple[int, str]]:
    behind: List[Tuple[int, str]] = []

    for uid, (first, last, username) in member_map.items():
        # Skip bots
        if username and username.lower().endswith("bot"):
            continue
        # Skip owner / super admins / models (don’t auto-kick staff)
        if rp._is_owner(uid) or rp._is_super_admin(uid) or rp._is_model(uid):
            continue

        doc = docs_by_uid.get(uid) or rp._member_doc(uid, username=username, first_name=first, last_name=last)

        if doc.get("is_exempt"):
            continue

        total = int(doc.get("spend_cents", 0)) + int(doc.get("manual_spend_cents", 0))
        if total < int(rp.REQUIRED_MIN_SPEND_CENTS):
            behind.append((uid, _display_name(first, last, username, uid)))

    behind.sort(key=lambda t: t[1].lower())
    return behind


def _menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔍 Preview who would be kicked", callback_data="kickreq:preview")],
            [InlineKeyboardButton("🧹 Kick now (CONFIRM)", callback_data="kickreq:confirm")],
            [InlineKeyboardButton("⬅ Back", callback_data="reqpanel:home")],
        ]
    )


def _after_kick_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅ Back to Requirements", callback_data="reqpanel:home")],
        ]
    )


async def _load_docs_by_uid(rp, user_ids: List[int]) -> Dict[int, dict]:
    # Mongo "in" query
    cur = rp.members_coll.find({"user_id": {"$in": user_ids}}, {"_id": 0})
    out: Dict[int, dict] = {}
    for d in cur:
        out[int(d["user_id"])] = d
    return out


async def _build_preview(app: Client, rp) -> Tuple[str, Dict[int, List[Tuple[int, str]]]]:
    group_ids = list(rp.SANCTUARY_GROUP_IDS)
    if not group_ids:
        return "⚠️ No SANCTUARY_GROUP_IDS configured.", {}

    all_member_maps: Dict[int, Dict[int, Tuple[str, str, str]]] = {}
    all_uids: List[int] = []

    for gid in group_ids:
        try:
            mm = await _get_group_members_map(app, gid)
        except Exception as e:
            log.exception("kickreq: failed fetching members for %s", gid)
            mm = {}
        all_member_maps[gid] = mm
        all_uids.extend(mm.keys())

    docs_by_uid = await _load_docs_by_uid(rp, list(set(all_uids)))

    per_group: Dict[int, List[Tuple[int, str]]] = {}
    total = 0

    for gid, mm in all_member_maps.items():
        behind = _compute_behind_for_group(mm, docs_by_uid, rp=rp)
        per_group[gid] = behind
        total += len(behind)

    lines: List[str] = []
    lines.append("🧹 <b>Manual Kick (Behind Requirements)</b>")
    lines.append(f"Minimum required: <b>${rp.REQUIRED_MIN_SPEND_DOLLARS:.2f}</b>")
    lines.append(f"Groups checked: <b>{len(group_ids)}</b>")
    lines.append(f"Total behind: <b>{total}</b>")
    lines.append("")

    for gid in group_ids:
        behind = per_group.get(gid, [])
        lines.append(f"<b>Group {gid}</b> — behind: <b>{len(behind)}</b>")
        if behind:
            # show first 25
            for uid, name in behind[:25]:
                lines.append(f"• {name} <code>{uid}</code>")
            if len(behind) > 25:
                lines.append(f"…and {len(behind) - 25} more")
        lines.append("")

    return "\n".join(lines).strip(), per_group


async def _do_kick(app: Client, rp, per_group: Dict[int, List[Tuple[int, str]]]) -> str:
    group_ids = list(rp.SANCTUARY_GROUP_IDS)
    kicked_total = 0
    failed_total = 0

    out: List[str] = []
    out.append("🧹 <b>Kicking behind members…</b>")

    for gid in group_ids:
        behind = per_group.get(gid, [])
        if not behind:
            out.append(f"\n<b>Group {gid}</b>: nothing to kick ✅")
            continue

        ok: List[str] = []
        fail: List[str] = []

        for uid, name in behind:
            try:
                await app.ban_chat_member(gid, uid)
                await app.unban_chat_member(gid, uid)
                ok.append(f"• {name} <code>{uid}</code>")
                kicked_total += 1
            except Exception as e:
                fail.append(f"• {name} <code>{uid}</code> — {e}")
                failed_total += 1

        out.append(f"\n<b>Group {gid}</b> — kicked: <b>{len(ok)}</b>, failed: <b>{len(fail)}</b>")
        if ok:
            out.append("<b>Kicked:</b>")
            out.extend(ok[:30])
            if len(ok) > 30:
                out.append(f"…and {len(ok)-30} more")
        if fail:
            out.append("<b>Failed:</b>")
            out.extend(fail[:15])
            if len(fail) > 15:
                out.append(f"…and {len(fail)-15} more")

    out.append("")
    out.append(f"✅ Done. Kicked: <b>{kicked_total}</b> | Failed: <b>{failed_total}</b>")
    return "\n".join(out).strip()


def register(app: Client):
    # Lazy import so this module stays small and always uses the live rp config.
    import handlers.requirements_panel as rp

    @app.on_callback_query(filters.regex(r"^kickreq:menu$"))
    async def kickreq_menu(_, cq: CallbackQuery):
        uid = cq.from_user.id
        if not (rp._is_owner(uid) or rp._is_super_admin(uid)):
            await cq.answer("Admins only.", show_alert=True)
            return

        text = (
            "🧹 <b>Kick Behind (Manual)</b>\n\n"
            "This will remove members who are currently <b>in your Sanctuary group(s)</b> and are <b>behind</b> the minimum spend.\n"
            "It will <b>not</b> kick exempt members, models, the owner, or super admins.\n\n"
            "Tap Preview first to double-check the list, then Confirm to kick."
        )
        await cq.message.edit_text(text, reply_markup=_menu_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^kickreq:preview$"))
    async def kickreq_preview(_, cq: CallbackQuery):
        uid = cq.from_user.id
        if not (rp._is_owner(uid) or rp._is_super_admin(uid)):
            await cq.answer("Admins only.", show_alert=True)
            return

        text, _per = await _build_preview(app, rp)
        # Store preview list in the message so confirm can reuse without re-fetching.
        # (We encode group+uids into callback_data token list is too big; instead re-fetch on confirm.
        # Preview is still useful for the human.)
        await cq.message.edit_text(text, reply_markup=_menu_kb(), disable_web_page_preview=True)
        await cq.answer()

    @app.on_callback_query(filters.regex(r"^kickreq:confirm$"))
    async def kickreq_confirm(_, cq: CallbackQuery):
        uid = cq.from_user.id
        if not (rp._is_owner(uid) or rp._is_super_admin(uid)):
            await cq.answer("Admins only.", show_alert=True)
            return

        await cq.answer("Kicking…", show_alert=False)

        # Rebuild fresh to avoid kicking based on stale preview.
        _text, per_group = await _build_preview(app, rp)
        result = await _do_kick(app, rp, per_group)

        await cq.message.edit_text(result, reply_markup=_after_kick_kb(), disable_web_page_preview=True)

        # Also log to the log group if configured
        try:
            if rp.LOG_CHAT_ID:
                await app.send_message(rp.LOG_CHAT_ID, f"[Requirements] Manual kick run by {uid}: kicked behind members.")
        except Exception:
            log.exception("kickreq: failed logging")
