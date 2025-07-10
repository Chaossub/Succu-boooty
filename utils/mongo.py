# utils/mongo.py

from pymongo import MongoClient
import os

# Get MongoDB connection URI and DB name from environment
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DBNAME")

# Initialize Mongo client and database
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

# Collections
flyer_collection = db["flyers"]
scheduled_jobs = db["scheduled_jobs"]
