import json
import logging
import os
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Tuple

import pytz
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.menu_store import store

log = logging.getLogger(__name__)

OWNER_ID = int(os.getenv("OWNER_ID", "6964994611"))
LA_TZ = pytz.timezone("America/Los_Angeles")

AVAIL_KEY = "NSFW_TEXTING_AVAIL_V2"
BOOKINGS_KEY = "NSFW_TEXTING_BOOKINGS_V2"
UI_KEY_PREFIX = "NSFW_TEXTING_BOOK_UI:"

DEFAULT_SLOT_MIN = 30


def _now_la() -> datetime:
    return datetime.now(tz=LA_TZ)


def _fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _parse_hhmm(s: str) -> int:
    hh, mm = s.split(":")
    return int(hh) * 60 + int(mm)


def _fmt_hhmm(m: int) -> str:
    hh = (m // 60) % 24
    mm = m % 60
    return f"{hh:02d}:{mm:02d}"


def _merge(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    xs = sorted((a, b) for a, b in intervals if b > a)
    out: List[Tuple[int, int]] = []
    for a, b in xs:
        if not out or a > out[-1][1]:
            out.append((a, b))
        else:
            out[-1] = (out[-1][0], max(out[-1][1], b))
    return out


def _subtract(base: List[Tuple[int, int]], sub: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not base:
        return []
    if not sub:
        return base[:]
    out: List[Tuple[int, int]] = []
    for a, b in base:
        cur = a
        for sa, sb in sub:
            if sb <= cur:
                continue
            if sa >= b:
                break
            if sa > cur:
                out.append((cur, min(sa, b)))
            cur = max(cur, sb)
            if cur >= b:
                break
        if cur < b:
            out.append((cur, b))
    return [(a, b) for a, b in out if b > a]


def _contains(ints: List[Tuple[int, int]], a: int, b: int) -> bool:
    for ia, ib in ints:
        if a >= ia and b <= ib:
            return True
    return False


def _jget(key: str, default: Any) -> Any:
    try:
        raw = store.get_menu(key)
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default


def _jset(key: str, obj: Any) -> None:
    try:
        store.set_menu(key, json.dumps(obj, ensure_ascii=False))
    except Exception as e:
        log.warning("NSFW booking: failed to store %s (%s)", key, e)


def _get_avail() -> Dict[str, Any]:
    return _jget(AVAIL_KEY, {"v": 2, "days": {}})


def _get_bookings() -> List[Dict[str, Any]]:
    return _jget(BOOKINGS_KEY, [])


def _set_bookings(b: List[Dict[str, Any]]) -> None:
    _jset(BOOKINGS_KEY, b)


def _intervals_from_list(lst: List[List[str]]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for item in lst or []:
        try:
            a = _parse_hhmm(item[0])
            b = _parse_hhmm(item[1])
            if b > a:
                out.append((a, b))
        except Exception:
            continue
    return _merge(out)


def _effective_availability(day_cfg: Dict[str, Any]) -> List[Tuple[int, int]]:
    if day_cfg.get("closed"):
        return []
    allowed = _intervals_from_list(day_cfg.get("allowed", []))
    blocked = _intervals_from_list(day_cfg.get("blocked", []))
    return _subtract(allowed, blocked)


def _ui_key(uid: int) -> str:
    return f"{UI_KEY_PREFIX}{uid}"


def _get_ui(uid: int) -> Dict[str, Any]:
    return _jget(_ui_key(uid), {})


def _set_ui(uid: int, ui: Dict[str, Any]) -> None:
    _jset(_ui_key(uid), ui)


async def _safe_edit(cq: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cq.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except MessageNotModified:
        try:
            await cq.answer()
        except Exception:
            pass


def _available_slots_for_day(av: Dict[str, Any], bookings: List[Dict[str, Any]], ds: str, slot_min: int) -> List[int]:
    day_cfg = (av.get("days") or {}).get(ds) or {}
    eff = _effective_availability(day_cfg)
    if not eff:
        return []

    booked_ints: List[Tuple[int, int]] = []
    for b in bookings:
        if b.get("date") == ds and b.get("status") != "cancelled":
            try:
                booked_ints.append((_parse_hhmm(b["start"]), _parse_hhmm(b["end"])))
            except Exception:
                continue
    booked_ints = _merge(booked_ints)

    slots: List[int] = []
    for a, b in eff:
        t = a
        while t + slot_min <= b:
            if not _contains(booked_ints, t, t + slot_min):
                slots.append(t)
            t += slot_min
    return slots


def _can_book(av: Dict[str, Any], bookings: List[Dict[str, Any]], ds: str, start: int, dur_min: int) -> bool:
    day_cfg = (av.get("days") or {}).get(ds) or {}
    eff = _effective_availability(day_cfg)
    if not eff:
        return False
    end = start + dur_min
    if not _contains(eff, start, end):
        return False

    for b in bookings:
        if b.get("date") != ds or b.get("status") == "cancelled":
            continue
        try:
            bs = _parse_hhmm(b["start"])
            be = _parse_hhmm(b["end"])
        except Exception:
            continue
        if not (end <= bs or start >= be):
            return False

    return True


def _week_dates_from_today() -> List[date]:
    today = _now_la().date()
    return [today + timedelta(days=i) for i in range(7)]


def _render_booking_week(av: Dict[str, Any]):
    days = _week_dates_from_today()
    text = "📲 <b>Book a private NSFW texting session (LA time)</b>\n\nPick a day:"
    rows: List[List[InlineKeyboardButton]] = []
    for d in days:
        ds = _fmt_date(d)
        cfg = (av.get("days") or {}).get(ds) or {}
        badge = "✅" if _effective_availability(cfg) else "❌"
        rows.append([InlineKeyboardButton(f"{badge} {d.strftime('%a %b %d')}", callback_data=f"nsfw_book:day:{ds}:0")])
    rows.append([InlineKeyboardButton("⬅️ Back to Assistant", callback_data="roni_portal:home")])
    return text, InlineKeyboardMarkup(rows)


def _render_time_page(ds: str, slots: List[int], page: int):
    page_size = 12
    max_page = max(0, (len(slots) - 1) // page_size) if slots else 0
    page = max(0, min(page, max_page))
    chunk = slots[page * page_size:(page + 1) * page_size]

    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        row = []
        for t in chunk[i:i + 2]:
            hhmm = _fmt_hhmm(t)
            row.append(InlineKeyboardButton(hhmm, callback_data=f"nsfw_book:time:{ds}:{hhmm}"))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"nsfw_book:day:{ds}:{page-1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"nsfw_book:day:{ds}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅️ Back to days", callback_data="nsfw_book:open")])
    rows.append([InlineKeyboardButton("⬅️ Back to Assistant", callback_data="roni_portal:home")])

    text = f"📅 <b>{ds} (LA)</b>\nPick a start time:"
    return text, InlineKeyboardMarkup(rows)


def register(app: Client):
    log.info("✅ nsfw_text_session_booking registered (OWNER_ID=%s)", OWNER_ID)

    @app.on_callback_query(filters.regex(r"^(nsfw_book:open|nsfw_text_session_booking:open|nsfw_booking:open)$"))
    async def book_open(_, cq: CallbackQuery):
        av = _get_avail()
        text, kb = _render_booking_week(av)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_book:day:(\d{4}-\d{2}-\d{2}):(\d+)$"))
    async def book_day(_, cq: CallbackQuery):
        ds = cq.matches[0].group(1)
        page = int(cq.matches[0].group(2))

        av = _get_avail()
        bookings = _get_bookings()

        day_cfg = (av.get("days") or {}).get(ds) or {}
        slot_min = int(day_cfg.get("slot") or DEFAULT_SLOT_MIN)

        slots = _available_slots_for_day(av, bookings, ds, slot_min)
        if not slots:
            rows = [
                [InlineKeyboardButton("⬅️ Back to days", callback_data="nsfw_book:open")],
                [InlineKeyboardButton("⬅️ Back to Assistant", callback_data="roni_portal:home")],
            ]
            await _safe_edit(
                cq,
                f"📅 <b>{ds} (LA)</b>\n\n❌ No available times right now. Try another day.",
                InlineKeyboardMarkup(rows),
            )
            return

        text, kb = _render_time_page(ds, slots, page)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_book:time:(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2})$"))
    async def book_pick_duration(_, cq: CallbackQuery):
        ds = cq.matches[0].group(1)
        hhmm = cq.matches[0].group(2)

        if not cq.from_user:
            return
        _set_ui(cq.from_user.id, {"date": ds, "time": hhmm})

        rows = [
            [InlineKeyboardButton("30 minutes", callback_data="nsfw_book:dur:30"),
             InlineKeyboardButton("1 hour", callback_data="nsfw_book:dur:60")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"nsfw_book:day:{ds}:0")],
            [InlineKeyboardButton("⬅️ Back to Assistant", callback_data="roni_portal:home")],
        ]
        await _safe_edit(
            cq,
            f"⏱️ <b>Confirm duration</b>\nDay: <b>{ds}</b>\nStart: <b>{hhmm}</b>\n\nChoose how long:",
            InlineKeyboardMarkup(rows),
        )

    @app.on_callback_query(filters.regex(r"^nsfw_book:dur:(30|60)$"))
    async def book_confirm(_, cq: CallbackQuery):
        if not cq.from_user:
            return
        dur = int(cq.matches[0].group(1))
        ui = _get_ui(cq.from_user.id)
        ds = ui.get("date")
        hhmm = ui.get("time")
        if not ds or not hhmm:
            await cq.answer("Expired. Start over.", show_alert=True)
            return

        av = _get_avail()
        bookings = _get_bookings()

        start = _parse_hhmm(hhmm)
        if not _can_book(av, bookings, ds, start, dur):
            await cq.answer("That slot was just taken or is no longer available.", show_alert=True)
            return

        end = start + dur
        booking_id = f"B{int(datetime.utcnow().timestamp())}{cq.from_user.id}"

        rec = {
            "id": booking_id,
            "user_id": cq.from_user.id,
            "name": (cq.from_user.first_name or "").strip(),
            "username": (cq.from_user.username or "").strip(),
            "date": ds,
            "start": _fmt_hhmm(start),
            "end": _fmt_hhmm(end),
            "duration_min": dur,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "status": "confirmed",
        }
        bookings.append(rec)
        _set_bookings(bookings)

        # Notify owner (best effort)
        try:
            who = f"{rec['name']} (@{rec['username']})" if rec["username"] else rec["name"]
            await app.send_message(
                OWNER_ID,
                f"📲 <b>New NSFW texting booking</b>\n"
                f"From: <b>{who}</b> (<code>{rec['user_id']}</code>)\n"
                f"When (LA): <b>{ds} {rec['start']}–{rec['end']}</b>\n"
                f"Duration: <b>{dur} min</b>\n"
                f"ID: <code>{booking_id}</code>",
            )
        except Exception:
            pass

        rows = [
            [InlineKeyboardButton("📅 Book another", callback_data="nsfw_book:open")],
            [InlineKeyboardButton("⬅️ Back to Assistant", callback_data="roni_portal:home")],
        ]
        await _safe_edit(
            cq,
            f"✅ <b>Booked!</b>\n\n"
            f"🗓️ <b>{ds}</b>\n"
            f"🕒 <b>{rec['start']}–{rec['end']} (LA)</b>\n\n"
            f"Roni will message you with next steps 💋",
            InlineKeyboardMarkup(rows),
        )
