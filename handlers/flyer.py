    @app.on_message(filters.command("scheduleflyer") & CHAT_FILTER)
    async def schedule_flyer(client, message: Message):
        # Split into: ["/scheduleflyer", name, rest_of_text]
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            return await message.reply_text(
                "Usage:\n"
                "• One-off:   /scheduleflyer <name> <YYYY-MM-DD HH:MM>\n"
                "• Recurring: /scheduleflyer <name> <HH:MM> <Mon,Tue,...|daily>"
            )

        name = parts[1].strip().lower()
        rest = parts[2].strip()
        entry = load_flyers().get(str(message.chat.id), {}).get(name)
        if not entry:
            return await message.reply_text(f"❌ No flyer named “{name}” found.")

        # Attempt to parse as one-off (requires a date part)
        date_part, time_part = (rest.split(" ", 1) + [None])[:2]
        if date_part and re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", date_part):
            # normalize date and parse
            y, m, d = date_part.split("-")
            run_str = f"{y}-{m.zfill(2)}-{d.zfill(2)} {time_part}"
            try:
                run_date = datetime.strptime(run_str, "%Y-%m-%d %H:%M")
            except:
                return await message.reply_text("❌ Invalid date/time. Use YYYY-MM-DD HH:MM")

            scheduler.add_job(
                client.send_photo,
                trigger=DateTrigger(run_date),
                args=[message.chat.id, entry["file_id"]],
                kwargs={"caption": entry["ad"]}
            )
            return await message.reply_text(
                f"✅ Scheduled one-off flyer “{name}” for {run_date:%Y-%m-%d %H:%M}"
            )

        # Otherwise treat as recurring: "<HH:MM> <days>"
        rec_parts = rest.split(maxsplit=1)
        if len(rec_parts) < 2:
            return await message.reply_text(
                "❌ For recurring, use:\n"
                "/scheduleflyer <name> <HH:MM> <Mon,Tue,...|daily>"
            )

        time_str, days_str = rec_parts
        try:
            hour, minute = map(int, time_str.split(":"))
        except:
            return await message.reply_text("❌ Invalid time. Use HH:MM")

        mapping = {
            'mon':'mon','monday':'mon',
            'tue':'tue','tuesday':'tue',
            'wed':'wed','wednesday':'wed',
            'thu':'thu','thursday':'thu',
            'fri':'fri','friday':'fri',
            'sat':'sat','saturday':'sat',
            'sun':'sun','sunday':'sun'
        }

        if days_str.lower() == "daily":
            dow = list(mapping.values())
        else:
            dow = []
            for d in days_str.split(","):
                tok = mapping.get(d.strip().lower())
                if not tok:
                    return await message.reply_text(
                        f"❌ Invalid weekday: {d}\nUse Mon,Tue,... or daily."
                    )
                dow.append(tok)

        scheduler.add_job(
            client.send_photo,
            trigger=CronTrigger(day_of_week=",".join(dow), hour=hour, minute=minute),
            args=[message.chat.id, entry["file_id"]],
            kwargs={"caption": entry["ad"]}
        )
        return await message.reply_text(
            f"✅ Scheduled flyer “{name}” every {days_str} at {time_str}"
        )
