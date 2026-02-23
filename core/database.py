import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure
from config import MONGODB_URI, MONGODB_DATABASE

class DatabaseManager:
    """Manages MongoDB connections, schema, and queries."""
    def __init__(self):
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            self.db = self.client[MONGODB_DATABASE]
            self.alarms = self.db['alarms']
            self.parameters = self.db['parameters']
            self.processed_files = self.db['processed_files']
            self.export_history = self.db['export_history']
            self._setup_indexes()
        except ConnectionFailure:
            self.client = None
            print(f"Warning: Could not connect to MongoDB at {MONGODB_URI}")

    def _setup_indexes(self):
        if not self.client: return
        self.processed_files.create_index("md5", unique=True)
        self.processed_files.create_index("machine")
        self.processed_files.create_index([("machine", 1), ("processed_at", -1)])

        self.alarms.create_index("source_md5")
        self.alarms.create_index([("machine", 1), ("alarm_id", 1)])
        self.alarms.create_index([("source_md5", 1), ("alarm_id", 1)], unique=True)

        self.parameters.create_index("source_md5")
        self.parameters.create_index([("machine", 1), ("description", 1)])
        self.parameters.create_index([("source_md5", 1), ("description", 1)], unique=True)

    def get_processed_file(self, md5: str) -> dict:
        if not self.client: return None
        return self.processed_files.find_one({"md5": md5})

    def get_all_processed_files(self) -> list:
        if not self.client: return []
        return list(self.processed_files.find({}, {"file_content": 0}).sort("processed_at", DESCENDING))

    def delete_processed_file(self, md5: str) -> bool:
        if not self.client: return False
        try:
            self.processed_files.delete_one({"md5": md5})
            self.alarms.delete_many({"source_md5": md5})
            self.parameters.delete_many({"source_md5": md5})
            return True
        except Exception as e:
            print(f"Error deleting file record: {e}")
            return False

    def register_processed_file(self, md5: str, filename: str, machine: str,
                                tabs_extracted: list, record_counts: dict,
                                extraction_version: str, file_bytes: bytes = None):
        if not self.client: return
        import datetime
        doc = {
            "md5": md5,
            "filename": filename,
            "machine": machine,
            "processed_at": datetime.datetime.now(),
            "tabs_extracted": tabs_extracted,
            "record_counts": record_counts,
            "extraction_version": extraction_version,
            "file_content": file_bytes
        }
        self.processed_files.update_one({"md5": md5}, {"$set": doc}, upsert=True)

    def save_alarms(self, alarms_list: list):
        if not self.client or not alarms_list: return
        from pymongo import UpdateOne
        requests = []
        for r in alarms_list:
            doc = r.model_dump()
            requests.append(UpdateOne(
                {"source_md5": doc.get("source_md5"), "alarm_id": doc.get("alarm_id")},
                {"$set": doc},
                upsert=True
            ))
        if requests:
            self.alarms.bulk_write(requests)

    def save_parameters(self, params_list: list):
        if not self.client or not params_list: return
        from pymongo import UpdateOne
        requests = []
        for r in params_list:
            doc = r.model_dump()
            requests.append(UpdateOne(
                {"source_md5": doc.get("source_md5"), "description": doc.get("description")},
                {"$set": doc},
                upsert=True
            ))
        if requests:
            self.parameters.bulk_write(requests)

    def get_alarms(self, filters: dict) -> list:
        if not self.client: return []
        return list(self.alarms.find(filters))

    def get_parameters(self, filters: dict) -> list:
        if not self.client: return []
        return list(self.parameters.find(filters))

    def log_export(self, machine: str, filename: str, tabs_exported: list, record_counts: dict):
        if not self.client: return
        import datetime
        self.export_history.insert_one({
            "machine": machine,
            "filename": filename,
            "tabs_exported": tabs_exported,
            "record_counts": record_counts,
            "exported_at": datetime.datetime.now()
        })
