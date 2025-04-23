import os
import sys
import json
import logging
from pathlib import Path
import pydicom
from pocketbase import PocketBase
from concurrent.futures import ThreadPoolExecutor
from pocketbase.client import FileUpload

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("dicom_scanner.log")]
)
logger = logging.getLogger("DicomScanner")

class DicomScanner:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config()
        self.pb_url = self.config.get("pocketbase_url", "http://localhost:8090")
        self.pb_collection = self.config.get("collection_name", "dicom_files")
        self.pb_admin_email = self.config.get("admin_email")
        self.pb_admin_password = self.config.get("admin_password")
        self.pb = PocketBase(self.pb_url)
        self.scan_directories = self.config.get("scan_directories", [])
        self.max_workers = self.config.get("max_workers", 8)
        # Authenticate as admin
        self.client = PocketBase('http://127.0.0.1:8090')

        # Authenticate as admin
        try:
            self.pb.admins.auth_with_password(self.pb_admin_email, self.pb_admin_password)
            logger.info("Successfully authenticated as admin")
        except Exception as e:
            logger.error(f"Failed to authenticate as admin: {e}")
            sys.exit(1)
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            sys.exit(1)

    
    def find_dicom_files(self):
        """Find all DICOM files in the configured directories"""
        dicom_files = []
        for directory in self.scan_directories:
            logger.info(f"Scanning directory: {directory}")
            try:
                for root, _, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)
                        ds = pydicom.dcmread(file_path)
                        dicom_files.append(file_path)
            except Exception as e:
                logger.error(f"Error scanning directory {directory}: {e}")
        
        logger.info(f"Found {len(dicom_files)} DICOM files")
        return dicom_files
    
    def extract_dicom_tags(self, file_path):
        """Extract the required DICOM tags from the file"""
        try:
            ds = pydicom.dcmread(file_path)
            
            # Common tags
            data = {
                "file_path": file_path,
                "modality": getattr(ds, "Modality", None),
                "slice_thickness": self._get_tag_value(ds, "SliceThickness"),
                "study_description": self._get_tag_value(ds, "StudyDescription"),
                "series_description": self._get_tag_value(ds, "SeriesDescription"),
                "image_position": self._get_sequence_values(ds, "ImagePositionPatient"),
                "image_orientation": self._get_sequence_values(ds, "ImageOrientationPatient"),
                "patient_id": self._get_tag_value(ds, "PatientID"),
                "study_instance_uid": self._get_tag_value(ds, "StudyInstanceUID"),
                "series_instance_uid": self._get_tag_value(ds, "SeriesInstanceUID"),
                "sop_instance_uid": self._get_tag_value(ds, "SOPInstanceUID")
            }
            
            # Modality-specific tags
            if getattr(ds, "Modality", "") == "CT":
                data.update({
                    "kvp": self._get_tag_value(ds, "KVP"),
                    "mas": self._get_tag_value(ds, "ExposureInmAs"),
                    "recon_kernel": self._get_tag_value(ds, "ConvolutionKernel")
                })
            elif getattr(ds, "Modality", "") == "MR":
                data.update({
                    "tr": self._get_tag_value(ds, "RepetitionTime"),
                    "te": self._get_tag_value(ds, "EchoTime"),
                    "ti": self._get_tag_value(ds, "InversionTime"),
                    "coil_name": self._get_tag_value(ds, "ReceiveCoilName")
                })
                
            return data
        except Exception as e:
            logger.error(f"Error extracting tags from {file_path}: {e}")
            return None
    
    def _get_tag_value(self, dataset, tag_name):
        """Safely get a tag value from a DICOM dataset"""
        try:
            if tag_name in dataset:
                value = dataset[tag_name].value
                # Convert to string if not already a simple type
                if not isinstance(value, (str, int, float, bool, type(None))):
                    value = str(value)
                return value
            return None
        except Exception:
            return None
    
    def _get_sequence_values(self, dataset, tag_name):
        """Get sequence values from a DICOM dataset"""
        try:
            if tag_name in dataset:
                value = dataset[tag_name].value
                if hasattr(value, "__iter__") and not isinstance(value, str):
                    return [float(x) for x in value]
                return [float(value)]
            return None
        except Exception:
            return None
    
    def process_file(self, file_path):
        """Process a single DICOM file and store it in PocketBase"""
        try:
            data = self.extract_dicom_tags(file_path)
            if not data:
                return False
            
            # Check if file already exists in database
            try:
                records = self.pb.collection(self.pb_collection).get_list(1, 500).items
                existing_record = next((r for r in records if r["file_path"] == file_path), None)
                
                if existing_record is not None:
                    # Update existing record
                    record_id = existing_record.id
                    self.pb.collection(self.pb_collection).update(record_id, data)
                else:
                    # Create new record
                    self.pb.collection(self.pb_collection).create(data)
                return True
            except Exception as e:
                logger.error(f"Error interacting with PocketBase: {e}")
                return False
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return False
    
    def scan_and_store(self):
        """Scan directories for DICOM files and store them in PocketBase"""
        dicom_files = self.find_dicom_files()
        
        success_count = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.process_file, dicom_files))
            success_count = sum(1 for result in results if result)
        
        logger.info(f"Successfully processed {success_count} out of {len(dicom_files)} DICOM files")

if __name__ == "__main__":
        
    scanner = DicomScanner("./config.json")
    scanner.scan_and_store()
