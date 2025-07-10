import os
from pymongo import MongoClient

# Get Mongo connection URI and DB name from environment variables
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DBNAME")

if not MONGO_URI or not MONGO_DB:
    raise ValueError("MongoDB URI and DB name must be set in environment variables.")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]

# Collection used for storing flyers
flyer_collection = db["flyers"]
