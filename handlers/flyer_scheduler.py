import logging
import asyncio
import os
from pyrogram import filters
from pyrogram.handlers import MessageHandler
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import sys
from pymongo import MongoClient

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
MAIN_LOOP = None  # Will be set by main.py

# Mongo
mongo_uri = os.getenv("MONGO_URI")
mongo_db = os.getenv("MONGO_DBNAME")
flyer_client = MongoClient(mongo_uri)[mongo_db]
flyer_collection = flyer_client["flyers"]

MAX_CAPTION_LENGTH = 1024

def log_debug(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[SCHEDULER][{ts}] {msg}"
    # Log to file
    try:
        with open("/tmp/scheduler_debug.log", "a") as f:
            f.write(msg +
