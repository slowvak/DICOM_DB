import json
import os
import sys
import subprocess
import logging
import tempfile

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PocketBaseSetup")

def setup_pocketbase(config_path):
    """Set up PocketBase schema for DICOM database using PocketBase CLI."""
    try:
        # Load configuration
        with open(config_path, 'r') as f:
            config = json.load(f)

        pb_url = config.get("pocketbase_url", "http://127.0.0.1:8090")
        collection_name = config.get("collection_name", "dicom_files")
        admin_email = config.get("admin_email")
        admin_password = config.get("admin_password")
        pb_executable = config.get("pocketbase_executable", "./pocketbase")  # Path to PocketBase executable

        if not admin_email or not admin_password:
            logger.error("Admin email or password not found in config.json")
            sys.exit(1)

        # Create a temporary directory for our migration files
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Created temporary directory: {temp_dir}")
            
            # Create the collections JSON file
            collections_json = {
                "collections": [
                    {
                        "id": "_pb_users_auth_",
                        "name": "users",
                        "type": "auth",
                        "system": False,
                        "schema": [
                            {
                                "id": "users_name",
                                "name": "name",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "users_avatar",
                                "name": "avatar",
                                "type": "file",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "maxSelect": 1,
                                    "maxSize": 5242880,
                                    "mimeTypes": [
                                        "image/jpeg",
                                        "image/png",
                                        "image/svg+xml",
                                        "image/gif",
                                        "image/webp"
                                    ],
                                    "thumbs": None
                                }
                            }
                        ],
                        "listRule": "id = @request.auth.id",
                        "viewRule": "id = @request.auth.id",
                        "createRule": "",
                        "updateRule": "id = @request.auth.id",
                        "deleteRule": "id = @request.auth.id",
                        "options": {
                            "allowEmailAuth": True,
                            "allowOAuth2Auth": True,
                            "allowUsernameAuth": True,
                            "exceptEmailDomains": None,
                            "manageRule": None,
                            "minPasswordLength": 8,
                            "onlyEmailDomains": None,
                            "requireEmail": False
                        }
                    },
                    {
                        "id": "dicom_files_id",
                        "name": collection_name,
                        "type": "base",
                        "system": False,
                        "schema": [
                            {
                                "id": "file_path_field",
                                "name": "file_path",
                                "type": "text",
                                "system": False,
                                "required": True,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "modality_field",
                                "name": "modality",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "slice_thickness_field",
                                "name": "slice_thickness",
                                "type": "number",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None
                                }
                            },
                            {
                                "id": "study_description_field",
                                "name": "study_description",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "series_description_field",
                                "name": "series_description",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "image_position_field",
                                "name": "image_position",
                                "type": "json",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {}
                            },
                            {
                                "id": "image_orientation_field",
                                "name": "image_orientation",
                                "type": "json",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {}
                            },
                            {
                                "id": "patient_id_field",
                                "name": "patient_id",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "study_instance_uid_field",
                                "name": "study_instance_uid",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "series_instance_uid_field",
                                "name": "series_instance_uid",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "sop_instance_uid_field",
                                "name": "sop_instance_uid",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "kvp_field",
                                "name": "kvp",
                                "type": "number",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None
                                }
                            },
                            {
                                "id": "mas_field",
                                "name": "mas",
                                "type": "number",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None
                                }
                            },
                            {
                                "id": "recon_kernel_field",
                                "name": "recon_kernel",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            },
                            {
                                "id": "tr_field",
                                "name": "tr",
                                "type": "number",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None
                                }
                            },
                            {
                                "id": "te_field",
                                "name": "te",
                                "type": "number",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None
                                }
                            },
                            {
                                "id": "ti_field",
                                "name": "ti",
                                "type": "number",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None
                                }
                            },
                            {
                                "id": "coil_name_field",
                                "name": "coil_name",
                                "type": "text",
                                "system": False,
                                "required": False,
                                "unique": False,
                                "options": {
                                    "min": None,
                                    "max": None,
                                    "pattern": ""
                                }
                            }
                        ],
                        "listRule": "",
                        "viewRule": "",
                        "createRule": "",
                        "updateRule": "",
                        "deleteRule": "",
                        "options": {}
                    }
                ]
            }
            
            # Write the collections JSON to a file
            collections_file = os.path.join(temp_dir, "pb_schema.json")
            with open(collections_file, 'w') as f:
                json.dump(collections_json, f, indent=2)
            
            logger.info(f"Created collections JSON file: {collections_file}")
            
            # Create a script to import the collections
            # This is a workaround since we can't directly use the PocketBase CLI
            # We'll create a shell script that runs the PocketBase migrate command
            
            # First, check if PocketBase is running
            try:
                import requests
                response = requests.get(pb_url)
                if response.status_code == 200:
                    logger.info("PocketBase is running.")
                else:
                    logger.warning(f"PocketBase might not be running. Status code: {response.status_code}")
            except Exception as e:
                logger.warning(f"Could not connect to PocketBase: {e}")
            
            # Create a shell script to run the PocketBase migrate command
            script_content = f"""#!/bin/bash
echo "Stopping any running PocketBase instance..."
pkill -f pocketbase || true
sleep 2

echo "Starting PocketBase with migrations..."
{pb_executable} migrate collections {collections_file}

echo "Migration complete. Starting PocketBase normally..."
{pb_executable} serve &
"""
            
            script_file = os.path.join(temp_dir, "import_schema.sh")
            with open(script_file, 'w') as f:
                f.write(script_content)
            
            # Make the script executable
            os.chmod(script_file, 0o755)
            
            logger.info(f"Created import script: {script_file}")
            
            # Run the script
            logger.info("Running import script...")
            try:
                result = subprocess.run(["bash", script_file], capture_output=True, text=True)
                logger.info(f"Script output: {result.stdout}")
                if result.stderr:
                    logger.warning(f"Script errors: {result.stderr}")
                
                if result.returncode == 0:
                    logger.info("Import script completed successfully.")
                else:
                    logger.error(f"Import script failed with return code {result.returncode}")
            except Exception as e:
                logger.error(f"Failed to run import script: {e}")
                sys.exit(1)
            
            logger.info("PocketBase schema setup complete.")
            
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {config_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {config_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred during setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_pocketbase("./config.json")
