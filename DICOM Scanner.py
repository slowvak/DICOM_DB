import os
import sys
import json
import logging
from pathlib import Path
import pydicom
from pocketbase import PocketBase
from concurrent.futures import ThreadPoolExecutor
from pocketbase.client import FileUpload
from datetime import datetime

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
                        # Check if it looks like a DICOM file based on extension or header later if needed,
                        # but avoid reading the whole file here.
                        # A simple check could be added, e.g., if file.lower().endswith('.dcm'):
                        dicom_files.append(file_path)
            except Exception as e:
                logger.error(f"Error scanning directory {directory}: {e}")
        
        logger.info(f"Found {len(dicom_files)} DICOM files")
        return dicom_files
    

    def _getMajorAxisFromDirCos(self, x, y, z):
        from math import fabs
        axis = ""
        if (x < 0):
            XOrient = "R"
        else:
            XOrient = "L"
        if (y < 0):
            YOrient = "A"
        else:
            YOrient = "P"
        if (z < 0):
            ZOrient = "F"
        else:
            ZOrient = "H"

        absX = fabs(x)
        absY = fabs(y)
        absZ = fabs(z)

        if ((absX > 0.25) and (absX > absY) and (absX > absZ)):
            axis = XOrient
        elif ((absY > 0.25) and (absY > absX) and (absY > absZ)):
            axis = YOrient
        elif ((absZ > 0.25) and (absZ > absX) and (absZ > absY)):
            axis = ZOrient
        return axis

    def _compute_orientation(self, ds):
        label = ""
        rowAxis = self._getMajorAxisFromDirCos(float(ds["ImageOrientationPatient"].value[0]), 
                                               float(ds["ImageOrientationPatient"].value[1]), 
                                               float(ds["ImageOrientationPatient"].value[2]))
        colAxis = self._getMajorAxisFromDirCos(float(ds["ImageOrientationPatient"].value[3]), 
                                               float(ds["ImageOrientationPatient"].value[4]), 
                                               float(ds["ImageOrientationPatient"].value[5]))

        if (rowAxis != "" and colAxis != ""):
            if ((rowAxis == "R" or rowAxis == "L") and (colAxis == "A" or colAxis == "P")):
                label = "AXL"
            if ((rowAxis == "R" or rowAxis == "L") and (colAxis == "A" or colAxis == "P")):
                label = "AXL"

            if ((rowAxis == "R" or rowAxis == "L") and (colAxis == "H" or colAxis == "F")):
                label = "COR"
            if ((rowAxis == "R" or rowAxis == "L") and (colAxis == "H" or colAxis == "F")):
                label = "COR"

            if ((rowAxis == "A" or rowAxis == "P") and (colAxis == "H" or colAxis == "F")):
                label = "SAG"
            if ((rowAxis == "A" or rowAxis == "P") and (colAxis == "H" or colAxis == "F")):
                label = "SAG"
        else:
            label = "OBL"
        return label


    def extract_dicom_tags(self, file_path):
        """Extract the required DICOM tags from the file"""
        try:
            # Check if file exists right before reading, as it might have been deleted since os.walk found it
            if not os.path.exists(file_path):
                logger.warning(f"File not found when trying to extract tags: {file_path}. Skipping.")
                return None
            ds = pydicom.dcmread(file_path)
        except:
            return None
        
        try:
            # Common tags
            SeriesDate = self._get_tag_value(ds, "SeriesDate", "19800101")
            SeriesTime = self._get_tag_value(ds, "SeriesTime", "010101")
            s = SeriesDate + SeriesTime
            ComputedDateTime = datetime.strptime(s, '%Y%m%d%H%M%S')

            if "ImageOrientationPatient" in ds:
                Image_Orientation = self._compute_orientation(ds)
            else:
                Image_Orientation = "Unknown"
            if "DiffusionBValue" in ds:
                IsDiffusion = self._get_tag_value(ds, "DiffusionBValue", False)
            else:
                IsDiffusion = False

            data = {
                "file_path": file_path,
                "Modality": self._get_tag_value(ds, "Modality", "NA"),
                "SliceThickness": self._get_tag_value(ds, "SliceThickness", 0.0),
                "StudyDescription": self._get_tag_value(ds, "StudyDescription", "No Study Description").replace("^", " "),
                "SeriesDescription": self._get_tag_value(ds, "SeriesDescription", "No Series Description").replace("^", " "),
                "ImagePositionPatient": self._get_tag_value(ds, "ImagePositionPatient", 0.0),
                "ImageOrientationPatient": Image_Orientation,
                "PatientID": self._get_tag_value(ds, "PatientID", "NotKnown"),
                "StudyInstanceUID": self._get_tag_value(ds, "StudyInstanceUID", "NotKnown"),
                "SeriesInstanceUID": self._get_tag_value(ds, "SeriesInstanceUID", "NotKnown"),
                "SOPInstanceUID": self._get_tag_value(ds, "SOPInstanceUID", "NotKnown"),
                "PixelSpacing": self._get_tag_value(ds, "PixelSpacing", 0),
                "FieldOfView": self._get_tag_value(ds, "FieldOfView", 0),
                "KVP": self._get_tag_value(ds, "KVP", 0),
                "ExposureInmAs": self._get_tag_value(ds, "ExposureInmAs", 0),
                "ConvolutionKernel": self._get_tag_value(ds, "ConvolutionKernel", "Unknown"),
                "RepetitionTime": self._get_tag_value(ds, "RepetitionTime",0),
                "EchoTime": self._get_tag_value(ds, "EchoTime",0),
                "InversionTime": self._get_tag_value(ds, "InversionTime", 0),
                "ReceiveCoilName": self._get_tag_value(ds, "ReceiveCoilName", "Unknown"),
                "BodyPartExamined": self._get_tag_value(ds, "BodyPartExamined", "Unknown"),
                "SeriesDateTime" : ComputedDateTime,
                "Manufacturer": self._get_tag_value(ds, "Manufacturer", "Unknown"),
                "SoftwareVersion": self._get_tag_value(ds, "SoftwareVersions", "Unknown"),
                "ModelName": self._get_tag_value(ds, "Manufacturer", "Unknown"),
                "AngioFlag": self._get_tag_value(ds, "AngioFlag", False),
                "Diffusion": IsDiffusion
            }
        
        except FileNotFoundError: # Explicitly catch if file disappears between check and read
             logger.warning(f"File not found during tag extraction (FileNotFoundError): {file_path}. Skipping.")
             return None
        except Exception as e:
            # Catch other potential errors during DICOM reading or tag extraction
            logger.error(f"Error extracting tags from {file_path}: {e}")
            return None
        return data

    def _get_tag_value(self, dataset, tag_name, default):
        """Safely get a tag value from a DICOM dataset"""
        # print (f"Tag extract: {tag_name}")
        try:
            if tag_name == 'FieldOfView':  # handle special cases
                if "PixelSpacing" in dataset and "Rows" in dataset:
                    return float(dataset["PixelSpacing"].value[0] * dataset["Rows"].value)
                return 0.0
            if tag_name in dataset:
                if tag_name == 'ImagePositionPatient':  # handle special cases--'default' is actually the orientation of this series
                    if default == 'AXL':
                        return float(dataset[tag_name].value[2])
                    elif default == 'COR':
                        return float (dataset[tag_name].value[1])
                    elif default == 'SAG':
                        return float (dataset[tag_name].value[0])
                    else:
                        return 0.0
                elif tag_name == 'PixelSpacing':    # handle special cases
                    return float(dataset[tag_name].value[0]) # just the X spacing...
                else:
                    value = dataset[tag_name].value
                if isinstance(default, float):
                    return float(value)
                if isinstance(default, int):
                    return float(value)
                if isinstance(default, bool):
                    return bool(value)
                # Convert to string if not already a simple type
                value = str(value).replace('(','').replace(')','').replace(',','')
                return value
            return default
        except Exception:
            print (f"Error: Tag was {tag_name} and value was {value}")
            return default
    
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

            # Convert datetime objects to ISO format strings for JSON serialization
            for key, value in data.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()

            # Check if SOPInstanceUID already exists in database
            try:
                records = self.pb.collection(self.pb_collection).get_list(1, 500).items
                existing_record = next((r for r in records if getattr(r, 'SOPInstanceUID', None) == data.get('SOPInstanceUID')), None)

                if existing_record is not None:
                    # SOPInstanceUID already exists, skip adding
                    return True
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
