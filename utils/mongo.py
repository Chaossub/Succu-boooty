from pymongo import MongoClient
import os

MONGO_URI = os.environ["MONGO_URI"]
mongo_client = MongoClient(MONGO_URI)
db_name = os.environ.get("MONGO_DBNAME") or os.environ.get("MONGO_DB_NAME", "SuccuBot")

db = mongo_client[db_name]
flyer_collection = db.flyers
scheduled_jobs = db.scheduled_jobs
