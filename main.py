stop_evt = asyncio.Event()
loop = asyncio.get_event_loop()
for sig in (signal.SIGINT, signal.SIGTERM):
    loop.add_signal_handler(sig, stop_evt.set)
await stop_evt.wait()
