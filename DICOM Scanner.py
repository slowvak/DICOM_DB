import os
import sys
import json
import logging
from pathlib import Path
import pydicom
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

FRIENDLY = True

if FRIENDLY:
    from time import sleep

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
        self.mongo_uri = self.config.get("mongo_uri", "mongodb://localhost:27017")
        self.mongo_db_name = self.config.get("mongo_db_name", "dicom_db")
        self.mongo_collection_name = self.config.get("mongo_collection_name", "dicom_files")
        self.scan_directories = self.config.get("scan_directories", [])
        self.max_workers = self.config.get("max_workers", 8)

        # Connect to MongoDB
        try:
            self.mongo_client = MongoClient(self.mongo_uri)
            self.mongo_db = self.mongo_client[self.mongo_db_name]
            self.mongo_collection = self.mongo_db[self.mongo_collection_name]
            logger.info(f"Connected to MongoDB at {self.mongo_uri}, DB: {self.mongo_db_name}, Collection: {self.mongo_collection_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
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
                        dicom_files.append(file_path)
                        if FRIENDLY:
                            sleep(0.1)
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
            if not os.path.exists(file_path):
                logger.warning(f"File not found when trying to extract tags: {file_path}. Skipping.")
                return None
            ds = pydicom.dcmread(file_path)
            if FRIENDLY:
                sleep(0.1)

        except:
            return None
        
        try:
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
                "SeriesDateTime" : ComputedDateTime.isoformat(),
                "Manufacturer": self._get_tag_value(ds, "Manufacturer", "Unknown"),
                "SoftwareVersion": self._get_tag_value(ds, "SoftwareVersions", "Unknown"),
                "ModelName": self._get_tag_value(ds, "Manufacturer", "Unknown"),
                "AngioFlag": self._get_tag_value(ds, "AngioFlag", False),
                "Diffusion": IsDiffusion
            }
        
        except FileNotFoundError:
             logger.warning(f"File not found during tag extraction (FileNotFoundError): {file_path}. Skipping.")
             return None
        except Exception as e:
            logger.error(f"Error extracting tags from {file_path}: {e}")
            return None
        return data

    def _get_tag_value(self, dataset, tag_name, default):
        """Safely get a tag value from a DICOM dataset"""
        try:
            if tag_name == 'FieldOfView':
                if "PixelSpacing" in dataset and "Rows" in dataset:
                    return float(dataset["PixelSpacing"].value[0] * dataset["Rows"].value)
                return 0.0
            if tag_name in dataset:
                if tag_name == 'ImagePositionPatient':
                    if default == 'AXL':
                        return float(dataset[tag_name].value[2])
                    elif default == 'COR':
                        return float(dataset[tag_name].value[1])
                    elif default == 'SAG':
                        return float(dataset[tag_name].value[0])
                    else:
                        return 0.0
                elif tag_name == 'PixelSpacing':
                    return float(dataset[tag_name].value[0])
                else:
                    value = dataset[tag_name].value
                if isinstance(default, float):
                    return float(value)
                if isinstance(default, int):
                    return float(value)
                if isinstance(default, bool):
                    return bool(value)
                value = str(value).replace('(','').replace(')','').replace(',','')
                return value
            return default
        except Exception:
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
        """Process a single DICOM file and store it in MongoDB"""
        try:
            data = self.extract_dicom_tags(file_path)
            if not data:
                return False
            
            # Check if SOPInstanceUID already exists in database
            existing_record = self.mongo_collection.find_one({"SOPInstanceUID": data.get("SOPInstanceUID")})
            if existing_record:
                # Update existing record
                self.mongo_collection.update_one({"_id": existing_record["_id"]}, {"$set": data})
            else:
                # Insert new record
                self.mongo_collection.insert_one(data)
            return True
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return False
    
    def scan_and_store(self):
        """Scan directories for DICOM files and store them in MongoDB"""
        dicom_files = self.find_dicom_files()
        
        success_count = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.process_file, dicom_files))
            success_count = sum(1 for result in results if result)
        
        logger.info(f"Successfully processed {success_count} out of {len(dicom_files)} DICOM files")

if __name__ == "__main__":
    scanner = DicomScanner("./config.json")
    scanner.scan_and_store()
