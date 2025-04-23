import requests
import json
import sys
import time

from pocketbase import PocketBase  # Client also works the same
from pocketbase.client import FileUpload



# and much more...
def setup_pocketbase(config_path):
    """Set up PocketBase schema for DICOM database"""
    # Load configuration
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    collection_name = config.get("collection_name", "dicom_files")
    
    # Authenticate as admin
    client = PocketBase('http://127.0.0.1:8090')

    # authenticate as regular user
#    user_data = client.collection("users").auth_with_password(
#        "user@example.com", "0123456789")
    # check if user token is valid
#    user_data.is_valid

    # or as admin
    admin_data = client.admins.auth_with_password(config.get("admin_email"), config.get("admin_password"))

    # check if admin token is valid
    admin_data.is_valid
    

    # Define the collection schema
    result = client.collection(collection_name).create(
    {
        "file_path": "text",
        "modality": "modality",
        "slice_thickness": 0,
        "study_description": "StudyDescription",
        "series_description": "SeriesDescription",
        "image_position": 0.0

            # {
            #     "name": "image_orientation",
            #     "type": "json",
            #     "required": False
            # },
            # {
            #     "name": "patient_id",
            #     "type": "text",
            #     "required": False
            # },
            # {
            #     "name": "study_instance_uid",
            #     "type": "text",
            #     "required": False
            # },
            # {
            #     "name": "series_instance_uid",
            #     "type": "text",
            #     "required": False
            # },
            # {
            #     "name": "sop_instance_uid",
            #     "type": "text",
            #     "required": False
            # },
            # # CT specific fields
            # {
            #     "name": "kvp",
            #     "type": "number",
            #     "required": False
            # },
            # {
            #     "name": "mas",
            #     "type": "number",
            #     "required": False
            # },
            # {
            #     "name": "recon_kernel",
            #     "type": "text",
            #     "required": False
            # },
            # # MRI specific fields
            # {
            #     "name": "tr",
            #     "type": "number",
            #     "required": False
            # },
            # {
            #     "name": "te",
            #     "type": "number",
            #     "required": False
            # },
            # {
            #     "name": "ti",
            #     "type": "number",
            #     "required": False
            # },
            # {
            #     "name": "coil_name",
            #     "type": "text",
            #     "required": False
            # }
    })
    
    result = client.collection(collection_name).get_list(1,20)
#    1, 20, {"filter": 'status = true && created > "2022-08-01 10:00:00"'})

    print(f"Successfully set up '{collection_name}' collection in PocketBase")

if __name__ == "__main__":
        
    setup_pocketbase("./config.json")