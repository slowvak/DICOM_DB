from pymongo import MongoClient, ASCENDING
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "dicom_db")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "dicom_files")

def initialize_mongo():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    collection = db[MONGO_COLLECTION_NAME]

    # Create indexes for commonly queried fields
    indexes = [
        ("SOPInstanceUID", ASCENDING),
        ("PatientID", ASCENDING),
        ("StudyInstanceUID", ASCENDING),
        ("SeriesInstanceUID", ASCENDING),
        ("Modality", ASCENDING),
        ("SeriesDateTime", ASCENDING),
    ]

    for field, order in indexes:
        collection.create_index([(field, order)], unique=False)
        print(f"Created index on {field}")

    print("MongoDB initialization complete.")

if __name__ == "__main__":
    initialize_mongo()
