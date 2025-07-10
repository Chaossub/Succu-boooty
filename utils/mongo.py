from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME") or "succubot"

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]

flyer_collection = db.flyers
scheduled_jobs = db.scheduled_jobs
