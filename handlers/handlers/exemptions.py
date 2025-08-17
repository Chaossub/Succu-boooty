# handlers/exemptions.py
# View exemption list: who is exempt from auto-boot, until when, and why.
# Command: /exemptlist   (DM: owner/super-admins only; Groups: chat admins only)

import os, time, json, math
from typing import Any, Dict, Iterable, List, Optional, Set
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Try to use your ReqStore if available
try:
    from req_store import ReqStore
    _store = ReqStore()
except Exception:
    _store = None

def _super_admins() -> Set[int]:
    raw = os.getenv("SUPER_ADMINS", "")
    ids: Set[int] = set()
    for tok in raw.replace(";", ",").split(","):
        tok = tok.strip()
        if tok and tok.lstrip("-").isdigit():
            ids.add(int(tok))
    # legacy single var
    for v in (os.getenv("OWNER_ID"), os.getenv("SUPER_ADMIN_ID")):
        if v and v.isdigit(): ids.add(int(v))
    return ids

async def _is_group_admin(app: Client, chat_id: int, user_id: int) -> bool:
    try:
        m = await app.get_chat_member(chat_id, user_id)
        return (m.privileges is not None) or (m.status in ("administrator", "creator"))
    except Exception:
        return False

def _fmt_dt_remaining(until_ts: Optional[float]) -> str:
    if not until_ts:  # None or 0 → no expiration
        return "no expiration"
    now = time.time()
    delta = max(0, math.floor(until_ts - now))
    if delta <= 0:
        return "expired"
    days, rem = divmod(delta, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if mins or not parts: parts.append(f"{mins}m")
    return "in " + " ".join(parts)

async def _mention_lines(app: Client, items: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for it in items:
        uid = int(it.get("user_id", 0) or it.get("uid", 0) or it.get("id", 0))
        reason = (it.get("reason") or it.get("why") or "").strip()
        until = it.get("until") or it.get("until_ts") or it.get("expires_at")
        # normalize until → float unix ts if given as str
        until_ts: Optional[float] = None
        if isinstance(until, (int, float)):
            until_ts = float(until)
        elif isinstance(until, str):
            try:
                until_ts = float(until)
            except Exception:
                until_ts = None
        try:
            u = await app.get_users(uid)
            who = f"{u.mention} (<code>{uid}</code>)"
        except Exception:
            who = f"<code>{uid}</code>"
        rem = _fmt_dt_remaining(until_ts)
        if reason:
            lines.append(f"• {who}\n   ↪︎ {rem} — {reason}")
        else:
            lines.append(f"• {who}\n   ↪︎ {rem}")
    return lines

def _fallback_from_env() -> List[Dict[str, Any]]:
    """
    EXEMPT_JSON example:
      [{"user_id":123, "until": 1750000000, "reason":"VIP buyer"},
       {"user_id":456, "until": null, "reason":"Team"}]
    """
    raw = os.getenv("EXEMPT_JSON") or ""
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            # keep only dictish rows that contain some id
            out = []
            for it in data:
                if not isinstance(it, dict): continue
                if any(k in it for k in ("user_id","uid","id")):
                    out.append(it)
            return out
    except Exception:
        pass
    # Backwards-compat simple list: EXEMPT_IDS=1,2,3  (no reason/expiry)
    ids_raw = os.getenv("EXEMPT_IDS", "") or ""
    items: List[Dict[str, Any]] = []
    for tok in ids_raw.replace(";", ",").split(","):
        tok = tok.strip()
        if tok and tok.isdigit():
            items.append({"user_id": int(tok), "until": None, "reason": ""})
    return items

def _from_req_store() -> Optional[List[Dict[str, Any]]]:
    if not _store: return None
    # Try common method names
    for name in (
        "get_exempt_records", "list_exempt_records", "list_exemptions_detailed",
        "get_exemptions", "list_exemptions", "list_exempt_users"
    ):
        fn = getattr(_store, name, None)
        if callable(fn):
            try:
                data = fn()
                # Normalize: accept list of dicts OR dict {uid: {"until":..., "reason":...}}
                if isinstance(data, dict):
                    items = []
                    for k, v in data.items():
                        if isinstance(v, dict):
                            v = {**v}  # copy
                            if "user_id" not in v: v["user_id"] = int(k) if str(k).isdigit() else k
                            items.append(v)
                        else:
                            items.append({"user_id": int(k) if str(k).isdigit() else k, "until": None, "reason": str(v)})
                    return items
                if isinstance(data, list):
                    # ensure user_id key exists
                    norm: List[Dict[str, Any]] = []
                    for it in data:
                        if isinstance(it, dict):
                            if not any(k in it for k in ("user_id","uid","id")): continue
                            norm.append(it)
                    return norm
            except Exception:
                pass
    return None

def _back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Start", callback_data="dmf_back_welcome")]])

def register(app: Client):

    @app.on_message(filters.command("exemptlist"))
    async def cmd_exempt_list(client: Client, m: Message):
        # Permissions
        if m.chat and m.chat.type != "private":
            if not await _is_group_admin(client, m.chat.id, m.from_user.id):
                return await m.reply_text("Admins only.", reply_markup=_back_home_kb())
        else:
            if m.from_user.id not in _super_admins():
                return await m.reply_text("Admins only.", reply_markup=_back_home_kb())

        items = _from_req_store()
        if items is None:
            items = _fallback_from_env()

        if not items:
            return await m.reply_text("No active exemptions.", reply_markup=_back_home_kb())

        # Filter out expired if they have a timestamp in the past
        now = time.time()
        live: List[Dict[str, Any]] = []
        for it in items:
            until = it.get("until") or it.get("until_ts") or it.get("expires_at") or None
            ts: Optional[float] = None
            try:
                ts = float(until) if until is not None else None
            except Exception:
                ts = None
            if ts is not None and ts <= now:
                continue
            live.append(it)

        if not live:
            return await m.reply_text("No active exemptions.", reply_markup=_back_home_kb())

        lines = await _mention_lines(client, live)
        await m.reply_text(
            "<b>Exempt from Auto-Boot</b>\n" + "\n".join(lines),
            reply_markup=_back_home_kb(),
            disable_web_page_preview=True
        )
