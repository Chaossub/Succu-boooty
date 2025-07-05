import os
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    print("MONGO_URI environment variable not set")
    exit(1)

try:
    client = MongoClient(MONGO_URI)
    db = client["SuccuBot"]
    collection = db["test_collection"]

    test_doc = {"test_key": "test_value"}

    result = collection.insert_one(test_doc)
    print("Inserted document ID:", result.inserted_id)

    # Clean up: remove the test document
    collection.delete_one({"_id": result.inserted_id})

    print("MongoDB connection and insert test succeeded!")

except Exception as e:
    print("MongoDB test failed:")
    print(e)
