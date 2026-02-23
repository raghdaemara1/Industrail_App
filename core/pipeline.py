import time
from datetime import datetime
from core.pdf_processor import PDFProcessor
from core.database import DatabaseManager
from core.schemas import ExtractionResult, AlarmRecord, ParameterRecord
from core.file_store import FileStore
from config import EXTRACTION_VERSION
from extractors.local_llm_extractor import LocalLLMExtractor
from extractors.parameter_specs_extractor import ParameterSpecsExtractor
from core.phase_engine import PhaseEngine

class BulkUploadPipeline:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.file_store = FileStore()
        self.alarm_extractor = LocalLLMExtractor()
        self.param_extractor = ParameterSpecsExtractor()

    def process_pdf(self, file_bytes: bytes, filename: str, machine: str, force_reprocess: bool = False, log_callback=None) -> ExtractionResult:
        start_time = time.time()
        
        def log(msg: str):
            if log_callback: log_callback(msg)
            
        log("Step 1: Generated MD5 Fingerprint")
        # Step 1 — FINGERPRINT
        processor = PDFProcessor(file_bytes)
        md5 = processor.md5
        
        cached = self.db.get_processed_file(md5)
        
        if cached and not force_reprocess:
            if cached.get("extraction_version") == EXTRACTION_VERSION:
                log("Cache HIT! Bypassing parsing and returning stored database values.")
                # Cache HIT
                from pydantic import ValidationError
                alarms_db = self.db.get_alarms({"source_md5": md5})
                params_db = self.db.get_parameters({"source_md5": md5})
                return ExtractionResult(
                    success=True,
                    alarms=[AlarmRecord(**a) for a in alarms_db],
                    parameters=[ParameterRecord(**p) for p in params_db],
                    errors=[],
                    warnings=[],
                    debug_steps=["Loaded from cache"],
                    timings={"total": time.time() - start_time},
                    source_filename=filename,
                    source_md5=md5,
                    source_text=""
                )

        # Step 2 — PARSE TEXT
        log("Step 2: Parsing PDF Text & Classifying Tables")
        text = processor.extract_text()
        processor.classify_content()
        log(f"PDF Analysis complete - Alarms Found: {processor.has_alarms}, Parameters Found: {processor.has_parameters}")
        
        alarms_extracted = []
        params_extracted = []
        
        # Step 3A — EXTRACT ALARMS
        if processor.has_alarms:
            log("Step 3A: Pushing Alarm data into LLM Regex Extractor (This can take 30-60 secs).")
            extracted = self.alarm_extractor.extract_alarms(text)
            log(f"Step 3A Complete: Successfully extracted {len(extracted)} Alarm payloads.")
            for item in extracted:
                alarms_extracted.append(AlarmRecord(
                    alarm_id=str(item.get("alarm_id")),
                    description=item.get("description", ""),
                    cause=item.get("cause"),
                    action=item.get("action"),
                    reason_level_1=item.get("reason_level_1"),
                    reason_level_2=item.get("reason_level_2"),
                    reason_level_3=item.get("cause"),
                    reason_level_4=item.get("action"),
                    category_type=item.get("category_type", "Unplanned Downtime"),
                    machine=machine,
                    source_md5=md5,
                    source_file=filename,
                    extracted_at=datetime.now()
                ))

        # Step 3B — EXTRACT PARAMETERS
        if processor.has_parameters:
            log("Step 3B: Pushing Variable data into Regex Parameter Matcher.")
            extracted = self.param_extractor.extract_parameters(text)
            log(f"Step 3B Complete: Picked up {len(extracted)} Variable payloads.")
            for item in extracted:
                params_extracted.append(ParameterRecord(
                    description=item.get("description", ""),
                    target=item.get("target"),
                    unit=item.get("unit"),
                    machine=machine,
                    source_md5=md5,
                    source_file=filename,
                    extracted_at=datetime.now()
                ))

        # Step 4 — STORE IN MONGODB
        log("Step 4A: Pushing models to internal Database storage...")
        self.db.save_alarms(alarms_extracted)
        self.db.save_parameters(params_extracted)
        log("Step 4A Complete: Database commit successful.")
        
        tabs_extracted = []
        if processor.has_alarms: tabs_extracted.append("alarms")
        if processor.has_parameters: tabs_extracted.append("parameters")
        
        self.db.register_processed_file(
            md5=md5,
            filename=filename,
            machine=machine,
            tabs_extracted=tabs_extracted,
            record_counts={"alarms": len(alarms_extracted), "parameters": len(params_extracted)},
            extraction_version=EXTRACTION_VERSION,
            file_bytes=file_bytes
        )
        log("Step 4B: Saving Document Cache to Local HDD.")
        self.file_store.save_file(md5, file_bytes)

        log("Pipeline Completely Resolved.")

        return ExtractionResult(
            success=True,
            alarms=alarms_extracted,
            parameters=params_extracted,
            errors=[],
            warnings=[],
            debug_steps=["Parsed PDF", f"Found Alarms: {processor.has_alarms}", f"Found Params: {processor.has_parameters}"],
            timings={"total": time.time() - start_time},
            source_filename=filename,
            source_md5=md5,
            source_text=text
        )
