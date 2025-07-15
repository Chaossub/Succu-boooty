import asyncio
import logging

def register(app, scheduler):
    # ... other code unchanged ...

    async def flyer_job(group_id, flyer_name):
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            logging.error(f"Flyer '{flyer_name}' not found!")
            return
        try:
            if flyer.get("file_id"):
                await app.send_photo(group_id, flyer["file_id"], caption=flyer.get("caption", ""))
            else:
                await app.send_message(group_id, flyer.get("caption", ""))
        except Exception as e:
            logging.error(f"Failed scheduled flyer post: {e}")

    @app.on_message(filters.command("scheduleflyer") & filters.create(admin_filter))
    async def scheduleflyer_handler(client, message):
        args = message.text.split()
        if len(args) < 4:
            return await message.reply("❌ Usage: /scheduleflyer <flyer_name> <group_alias> <HH:MM> [once|daily|weekly]")
        flyer_name, group_alias, time_str = args[1:4]
        freq = args[4] if len(args) > 4 else "once"
        group_id = ALIASES.get(group_alias)
        if not group_id:
            return await message.reply("❌ Invalid group/alias.")
        flyer = flyers.find_one({"name": flyer_name})
        if not flyer:
            return await message.reply("❌ Flyer not found.")
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now()
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_time < now:
            run_time += timedelta(days=1)
        job_id = f"flyer_{flyer_name}_{group_id}_{int(run_time.timestamp())}"

        loop = asyncio.get_event_loop()
        def run_async_job():
            asyncio.run_coroutine_threadsafe(flyer_job(group_id, flyer_name), loop)

        if freq == "once":
            scheduler.add_job(run_async_job, "date", run_date=run_time, id=job_id)
        elif freq == "daily":
            scheduler.add_job(run_async_job, "cron", hour=hour, minute=minute, id=job_id)
        elif freq == "weekly":
            scheduler.add_job(run_async_job, "cron", day_of_week="mon", hour=hour, minute=minute, id=job_id)
        else:
            return await message.reply("❌ Invalid freq. Use once/daily/weekly")
        scheduled.insert_one({"job_id": job_id, "flyer_name": flyer_name, "group_id": group_id, "time": time_str, "freq": freq})
        await message.reply(f"✅ Scheduled flyer '{flyer_name}' to {group_alias} at {time_str} ({freq}).\nJob ID: <code>{job_id}</code>")
