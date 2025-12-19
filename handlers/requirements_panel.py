import io
from datetime import datetime, timezone

# ...keep your existing imports...


def _label_for_member(d: dict) -> str:
    name = (d.get("first_name") or "Unknown").strip()
    username = (d.get("username") or "").strip()
    uid = d.get("user_id")
    if username:
        return f"{name} (@{username}) — <code>{uid}</code>"
    return f"{name} — <code>{uid}</code>"


async def _try_send_dm(app: Client, chat_id: int, text: str) -> tuple[bool, str]:
    try:
        await app.send_message(chat_id, text)
        return True, ""
    except Exception as e:
        return False, str(e)


def _format_sweep_results(title: str, ok_list: list[str], fail_list: list[str]) -> str:
    # keep message readable + under limits
    MAX_SHOW = 60

    lines = [title, ""]
    lines.append(f"✅ Sent: <b>{len(ok_list)}</b>")
    if ok_list:
        show = ok_list[:MAX_SHOW]
        lines.extend([f"• {x}" for x in show])
        if len(ok_list) > MAX_SHOW:
            lines.append(f"…and <b>{len(ok_list) - MAX_SHOW}</b> more.")

    lines.append("")
    lines.append(f"❌ Failed: <b>{len(fail_list)}</b>")
    if fail_list:
        showf = fail_list[:MAX_SHOW]
        lines.extend([f"• {x}" for x in showf])
        if len(fail_list) > MAX_SHOW:
            lines.append(f"…and <b>{len(fail_list) - MAX_SHOW}</b> more.")

    return "\n".join(lines)


async def _log_sweep_details(
    client: Client,
    title: str,
    ok_list: list[str],
    fail_list: list[str],
):
    """
    Sends detailed results to your log group.
    If the list is too long, sends as a .txt file instead.
    """
    # This assumes you already have LOG_CHAT_ID in your file.
    # If your file uses a different name, replace LOG_CHAT_ID below.
    if not LOG_CHAT_ID:
        return

    text = _format_sweep_results(title, ok_list, fail_list)

    # Telegram message hard limit is ~4096 chars; keep buffer.
    if len(text) <= 3500:
        try:
            await client.send_message(LOG_CHAT_ID, text, disable_web_page_preview=True)
            return
        except Exception:
            pass

    # Too long or failed to send as text -> send as file
    plain = text.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
    buf = io.BytesIO(plain.encode("utf-8"))
    buf.name = "sweep_results.txt"
    await client.send_document(
        LOG_CHAT_ID,
        document=buf,
        caption=title.replace("<b>", "").replace("</b>", ""),
    )


@app.on_callback_query(filters.regex("^reqpanel:reminders$"))
async def reqpanel_reminders_cb(client: Client, cq: CallbackQuery):
    user_id = cq.from_user.id
    if not _is_admin_or_model(user_id):
        await cq.answer("Only Roni and models can send reminders.", show_alert=True)
        return

    docs = list(members_coll.find(
        {
            "is_exempt": {"$ne": True},
            "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
            "reminder_sent": {"$ne": True},
        }
    ))

    sent_to: list[str] = []
    failed: list[str] = []

    for d in docs:
        uid = d["user_id"]
        if uid == OWNER_ID or uid in MODELS:
            continue

        name = d.get("first_name") or "there"
        msg = random.choice(REMINDER_MSGS).format(name=name)

        ok, err = await _try_send_dm(client, uid, msg)
        label = _label_for_member(d)

        if not ok:
            failed.append(f"{label} <i>({err})</i>")
            continue

        members_coll.update_one(
            {"user_id": uid},
            {"$set": {"reminder_sent": True, "last_updated": datetime.now(timezone.utc)}},
        )
        sent_to.append(label)

    # ✅ keep your existing summary log line
    await _log_event(client, f"Reminder sweep sent to {len(sent_to)} members by {user_id}")

    # ✅ NEW: also post the detailed list to the log group
    await _log_sweep_details(
        client,
        "💌 <b>Reminder sweep — detailed results</b>",
        sent_to,
        failed,
    )

    # optional: show quick counts to the admin who clicked
    await cq.answer(f"Sent={len(sent_to)} Failed={len(failed)}", show_alert=True)


@app.on_callback_query(filters.regex("^reqpanel:final_warnings$"))
async def reqpanel_final_warnings_cb(client: Client, cq: CallbackQuery):
    user_id = cq.from_user.id
    if not _is_admin_or_model(user_id):
        await cq.answer("Only Roni and models can send final warnings.", show_alert=True)
        return

    docs = list(members_coll.find(
        {
            "is_exempt": {"$ne": True},
            "manual_spend": {"$lt": REQUIRED_MIN_SPEND},
            "final_warning_sent": {"$ne": True},
        }
    ))

    sent_to: list[str] = []
    failed: list[str] = []

    for d in docs:
        uid = d["user_id"]
        if uid == OWNER_ID or uid in MODELS:
            continue

        name = d.get("first_name") or "there"
        msg = random.choice(FINAL_WARNING_MSGS).format(name=name)

        ok, err = await _try_send_dm(client, uid, msg)
        label = _label_for_member(d)

        if not ok:
            failed.append(f"{label} <i>({err})</i>")
            continue

        members_coll.update_one(
            {"user_id": uid},
            {"$set": {"final_warning_sent": True, "last_updated": datetime.now(timezone.utc)}},
        )
        sent_to.append(label)

    # ✅ keep your existing summary log line
    await _log_event(client, f"Final warning sweep sent to {len(sent_to)} members by {user_id}")

    # ✅ NEW: also post the detailed list to the log group
    await _log_sweep_details(
        client,
        "⚠️ <b>Final warning sweep — detailed results</b>",
        sent_to,
        failed,
    )

    await cq.answer(f"Sent={len(sent_to)} Failed={len(failed)}", show_alert=True)
