import os
from pymongo import MongoClient

mongo_uri = os.environ["MONGO_URI"]
mongo_db = os.environ.get("MONGO_DB_NAME") or os.environ.get("MONGO_DBNAME")

client = MongoClient(mongo_uri)
db = client[mongo_db]

flyer_collection = db["flyers"]
scheduled_jobs = db["scheduled_jobs"]

