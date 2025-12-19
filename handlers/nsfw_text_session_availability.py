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

# Global keys (stored via MenuStore)
AVAIL_KEY = "NSFW_TEXTING_AVAIL_V2"          # availability + blocks
UI_KEY_PREFIX = "NSFW_TEXTING_AVAIL_UI:"     # per-user UI state

DEFAULT_OPEN = "09:00"
DEFAULT_CLOSE = "22:00"
DEFAULT_SLOT_MIN = 30

# Allow presets (LA time)
PRESETS = {
    "morning": ("09:00", "12:00"),
    "afternoon": ("12:00", "17:00"),
    "evening": ("17:00", "22:00"),
    "full": ("09:00", "22:00"),
}


def _now_la() -> datetime:
    return datetime.now(tz=LA_TZ)


def _fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _parse_hhmm(s: str) -> int:
    hh, mm = s.split(":")
    return int(hh) * 60 + int(mm)


def _fmt_hhmm(m: int) -> str:
    m = max(0, min(23 * 60 + 59, m))
    hh = m // 60
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
        log.warning("NSFW availability: failed to store %s (%s)", key, e)


def _get_avail() -> Dict[str, Any]:
    return _jget(AVAIL_KEY, {"v": 2, "days": {}})


def _set_avail(av: Dict[str, Any]) -> None:
    _jset(AVAIL_KEY, av)


def _day_defaults() -> Dict[str, Any]:
    return {
        "open": DEFAULT_OPEN,
        "close": DEFAULT_CLOSE,
        "slot": DEFAULT_SLOT_MIN,
        "allowed": [["09:00", "22:00"]],
        "blocked": [],
        "closed": False,
    }


def _get_day(av: Dict[str, Any], day: str) -> Dict[str, Any]:
    days = av.setdefault("days", {})
    if day not in days or not isinstance(days[day], dict):
        days[day] = _day_defaults()
    for k, v in _day_defaults().items():
        days[day].setdefault(k, v)
    return days[day]


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


def _list_from_intervals(ints: List[Tuple[int, int]]) -> List[List[str]]:
    return [[_fmt_hhmm(a), _fmt_hhmm(b)] for a, b in _merge(ints)]


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


def _week_days(start: date) -> List[date]:
    return [start + timedelta(days=i) for i in range(7)]


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _render_week(av: Dict[str, Any], week_start: date):
    days = _week_days(week_start)
    header = (
        f"🗓️ <b>NSFW Availability (LA time)</b>\n"
        f"Week of <b>{days[0].strftime('%b %d')}</b> → <b>{days[-1].strftime('%b %d')}</b>\n\n"
        "Tap a day to edit hours, allowed windows, and blocks."
    )
    rows: List[List[InlineKeyboardButton]] = []
    for d in days:
        ds = _fmt_date(d)
        cfg = _get_day(av, ds)
        eff = _effective_availability(cfg)
        badge = "✅" if eff else "❌"
        rows.append([InlineKeyboardButton(f"{badge} {d.strftime('%a %b %d')}", callback_data=f"nsfw_av:day:{ds}")])

    rows.append([
        InlineKeyboardButton("⬅️ Prev week", callback_data=f"nsfw_av:week:{_fmt_date(week_start - timedelta(days=7))}"),
        InlineKeyboardButton("Next week ➡️", callback_data=f"nsfw_av:week:{_fmt_date(week_start + timedelta(days=7))}"),
    ])
    rows.append([InlineKeyboardButton("⬅️ Back to Roni Admin", callback_data="roni_admin:open")])
    return header, InlineKeyboardMarkup(rows)


def _render_day(av: Dict[str, Any], ds: str):
    cfg = _get_day(av, ds)
    open_t = cfg.get("open", DEFAULT_OPEN)
    close_t = cfg.get("close", DEFAULT_CLOSE)
    slot = int(cfg.get("slot", DEFAULT_SLOT_MIN))
    allowed = _intervals_from_list(cfg.get("allowed", []))
    blocked = _intervals_from_list(cfg.get("blocked", []))
    eff = _effective_availability(cfg)

    def fmt_list(ints: List[Tuple[int, int]]) -> str:
        if not ints:
            return "—"
        return "\n".join([f"• {_fmt_hhmm(a)}–{_fmt_hhmm(b)}" for a, b in ints])

    txt = (
        f"📅 <b>{ds} (LA)</b>\n\n"
        f"Business hours: <b>{open_t}–{close_t}</b>  |  Slot: <b>{slot}m</b>\n"
        f"Closed all day: <b>{'Yes' if cfg.get('closed') else 'No'}</b>\n\n"
        f"<b>Allowed windows</b>\n{fmt_list(allowed)}\n\n"
        f"<b>Blocked windows</b>\n{fmt_list(blocked)}\n\n"
        f"<b>Effective availability (Allowed minus Blocked)</b>\n{fmt_list(eff)}"
    )

    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("🌅 Morning", callback_data=f"nsfw_av:allow:{ds}:morning"),
         InlineKeyboardButton("🌤️ Afternoon", callback_data=f"nsfw_av:allow:{ds}:afternoon")],
        [InlineKeyboardButton("🌙 Evening", callback_data=f"nsfw_av:allow:{ds}:evening"),
         InlineKeyboardButton("✅ Full", callback_data=f"nsfw_av:allow:{ds}:full")],
        [InlineKeyboardButton("🧹 Clear allowed", callback_data=f"nsfw_av:allow:{ds}:clear"),
         InlineKeyboardButton("🧼 Clear blocks", callback_data=f"nsfw_av:blocks:{ds}:clear")],
        [InlineKeyboardButton("🚫 Block a window", callback_data=f"nsfw_av:block:{ds}"),
         InlineKeyboardButton("♻️ Unblock a window", callback_data=f"nsfw_av:unblock:{ds}")],
        [InlineKeyboardButton("⛔ Close all day", callback_data=f"nsfw_av:closed:{ds}:1"),
         InlineKeyboardButton("✅ Open all day", callback_data=f"nsfw_av:closed:{ds}:0")],
        [InlineKeyboardButton("⬅️ Back to week", callback_data=f"nsfw_av:week:{ds}")],
        [InlineKeyboardButton("⬅️ Back to Roni Admin", callback_data="roni_admin:open")],
    ]
    return txt, InlineKeyboardMarkup(rows)


def _time_buttons(open_t: str, close_t: str, slot: int, base_cb: str, page: int = 0) -> InlineKeyboardMarkup:
    start = _parse_hhmm(open_t)
    end = _parse_hhmm(close_t)
    times = list(range(start, end, slot))
    page_size = 12
    max_page = max(0, (len(times) - 1) // page_size)
    page = max(0, min(page, max_page))
    chunk = times[page * page_size:(page + 1) * page_size]

    rows: List[List[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        row = []
        for t in chunk[i:i + 2]:
            row.append(InlineKeyboardButton(_fmt_hhmm(t), callback_data=f"{base_cb}:{_fmt_hhmm(t)}"))
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{base_cb}:PAGE:{page-1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"{base_cb}:PAGE:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="nsfw_av:back")])
    return InlineKeyboardMarkup(rows)


def register(app: Client):
    log.info("✅ nsfw_text_session_availability registered (OWNER_ID=%s)", OWNER_ID)

    # OPEN WEEK (includes your admin button alias nsfw_avail:open)
    @app.on_callback_query(filters.regex(r"^(nsfw_avail:open|nsfw_av:open|nsfw_availability:open|nsfw_text_session_availability:open)$"))
    async def av_open(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only.", show_alert=True)
            return
        av = _get_avail()
        ws = _week_start(_now_la().date())
        text, kb = _render_week(av, ws)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_av:week:(\d{4}-\d{2}-\d{2})$"))
    async def av_week(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only.", show_alert=True)
            return
        any_ds = cq.matches[0].group(1)
        d = datetime.strptime(any_ds, "%Y-%m-%d").date()
        ws = _week_start(d)
        av = _get_avail()
        text, kb = _render_week(av, ws)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_av:day:(\d{4}-\d{2}-\d{2})$"))
    async def av_day(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only.", show_alert=True)
            return
        ds = cq.matches[0].group(1)
        av = _get_avail()
        text, kb = _render_day(av, ds)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_av:allow:(\d{4}-\d{2}-\d{2}):(morning|afternoon|evening|full|clear)$"))
    async def av_allow(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only.", show_alert=True)
            return
        ds = cq.matches[0].group(1)
        mode = cq.matches[0].group(2)
        av = _get_avail()
        cfg = _get_day(av, ds)

        if mode == "clear":
            cfg["allowed"] = []
            cfg["closed"] = False
        else:
            cfg["closed"] = False
            cfg["allowed"] = [[PRESETS[mode][0], PRESETS[mode][1]]]

        _set_avail(av)
        text, kb = _render_day(av, ds)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_av:blocks:(\d{4}-\d{2}-\d{2}):clear$"))
    async def av_blocks_clear(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only.", show_alert=True)
            return
        ds = cq.matches[0].group(1)
        av = _get_avail()
        cfg = _get_day(av, ds)
        cfg["blocked"] = []
        _set_avail(av)
        text, kb = _render_day(av, ds)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_av:closed:(\d{4}-\d{2}-\d{2}):(0|1)$"))
    async def av_closed(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only.", show_alert=True)
            return
        ds = cq.matches[0].group(1)
        val = cq.matches[0].group(2) == "1"
        av = _get_avail()
        cfg = _get_day(av, ds)
        cfg["closed"] = val
        if val:
            cfg["allowed"] = []
        _set_avail(av)
        text, kb = _render_day(av, ds)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_av:(block|unblock):(\d{4}-\d{2}-\d{2})$"))
    async def av_block_start(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            await cq.answer("Admin only.", show_alert=True)
            return
        mode = cq.matches[0].group(1)
        ds = cq.matches[0].group(2)

        av = _get_avail()
        cfg = _get_day(av, ds)

        _set_ui(OWNER_ID, {"mode": mode, "day": ds})
        base_cb = f"nsfw_av:pick:{mode}:{ds}"
        kb = _time_buttons(cfg["open"], cfg["close"], int(cfg["slot"]), base_cb, page=0)
        await _safe_edit(
            cq,
            f"🕒 <b>{mode.title()} a window</b>\nPick a start time for <b>{ds}</b> (LA):",
            kb
        )

    @app.on_callback_query(filters.regex(r"^nsfw_av:pick:(block|unblock):(\d{4}-\d{2}-\d{2}):PAGE:(\d+)$"))
    async def av_pick_page(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            return
        mode = cq.matches[0].group(1)
        ds = cq.matches[0].group(2)
        page = int(cq.matches[0].group(3))
        av = _get_avail()
        cfg = _get_day(av, ds)
        base_cb = f"nsfw_av:pick:{mode}:{ds}"
        kb = _time_buttons(cfg["open"], cfg["close"], int(cfg["slot"]), base_cb, page=page)
        await _safe_edit(
            cq,
            f"🕒 <b>{mode.title()} a window</b>\nPick a start time for <b>{ds}</b> (LA):",
            kb
        )

    @app.on_callback_query(filters.regex(r"^nsfw_av:pick:(block|unblock):(\d{4}-\d{2}-\d{2}):(\d{2}:\d{2})$"))
    async def av_pick_time(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            return
        mode = cq.matches[0].group(1)
        ds = cq.matches[0].group(2)
        start_hhmm = cq.matches[0].group(3)

        ui = _get_ui(OWNER_ID)
        ui.update({"mode": mode, "day": ds, "start": start_hhmm})
        _set_ui(OWNER_ID, ui)

        rows = [
            [InlineKeyboardButton("30m", callback_data="nsfw_av:dur:30"),
             InlineKeyboardButton("60m", callback_data="nsfw_av:dur:60"),
             InlineKeyboardButton("90m", callback_data="nsfw_av:dur:90")],
            [InlineKeyboardButton("2h", callback_data="nsfw_av:dur:120"),
             InlineKeyboardButton("3h", callback_data="nsfw_av:dur:180"),
             InlineKeyboardButton("4h", callback_data="nsfw_av:dur:240")],
            [InlineKeyboardButton("All day", callback_data="nsfw_av:dur:ALL")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"nsfw_av:day:{ds}")],
        ]
        await _safe_edit(
            cq,
            f"🧩 <b>{mode.title()} window</b>\nDay: <b>{ds}</b>\nStart: <b>{start_hhmm}</b>\n\nChoose duration:",
            InlineKeyboardMarkup(rows),
        )

    @app.on_callback_query(filters.regex(r"^nsfw_av:dur:(30|60|90|120|180|240|ALL)$"))
    async def av_apply_duration(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            return

        ui = _get_ui(OWNER_ID)
        mode = ui.get("mode")
        ds = ui.get("day")
        start_hhmm = ui.get("start")
        if not (mode and ds and start_hhmm):
            await cq.answer("Expired. Try again.", show_alert=True)
            return

        av = _get_avail()
        cfg = _get_day(av, ds)

        day_open = _parse_hhmm(cfg.get("open", DEFAULT_OPEN))
        day_close = _parse_hhmm(cfg.get("close", DEFAULT_CLOSE))
        start_m = _parse_hhmm(start_hhmm)

        if cq.matches[0].group(1) == "ALL":
            a, b = day_open, day_close
        else:
            dur = int(cq.matches[0].group(1))
            a, b = start_m, start_m + dur

        a = max(day_open, a)
        b = min(day_close, b)
        if b <= a:
            await cq.answer("Invalid window.", show_alert=True)
            return

        blocked = _intervals_from_list(cfg.get("blocked", []))

        if mode == "block":
            blocked = _merge(blocked + [(a, b)])
        else:
            blocked = _subtract(blocked, _merge([(a, b)]))

        cfg["blocked"] = _list_from_intervals(blocked)
        cfg["closed"] = False

        _set_avail(av)
        text, kb = _render_day(av, ds)
        await _safe_edit(cq, text, kb)

    @app.on_callback_query(filters.regex(r"^nsfw_av:back$"))
    async def av_back(_, cq: CallbackQuery):
        if not cq.from_user or cq.from_user.id != OWNER_ID:
            return
        ui = _get_ui(OWNER_ID)
        ds = ui.get("day")
        av = _get_avail()
        if ds:
            text, kb = _render_day(av, ds)
        else:
            ws = _week_start(_now_la().date())
            text, kb = _render_week(av, ws)
        await _safe_edit(cq, text, kb)
