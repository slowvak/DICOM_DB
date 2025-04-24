from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
# to start mongodb server:  brew services start mongodb-community@8.0
# to stop it: brew services stop mongodb-community@8.0
from pymongo import MongoClient
import os

app = FastAPI()

# Allow CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "dicom_db")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "dicom_files")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
collection = db[MONGO_COLLECTION_NAME]

# Helper to convert MongoDB document to dict with string id
def doc_to_dict(doc):
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc

# Pydantic model for filter query
class FilterQuery(BaseModel):
    filters: Optional[Dict[str, Any]] = None

@app.post("/api/dicom_files/search", response_model=List[Dict[str, Any]])
def search_dicom_files(filter_query: FilterQuery):
    filters = filter_query.filters or {}

    # Build MongoDB query
    mongo_query = {}

    for field, condition in filters.items():
        if isinstance(condition, dict):
            # condition is like {"$gt": value} or {"$lt": value}
            mongo_query[field] = condition
        else:
            # exact match
            mongo_query[field] = condition

    try:
        docs = collection.find(mongo_query).limit(500)
        results = [doc_to_dict(doc) for doc in docs]
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
