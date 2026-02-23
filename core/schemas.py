from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AlarmRecord(BaseModel):
    # Extracted from PDF
    alarm_id:        str            # "282" or "0282" — always STRING, preserve zeros
    description:     str            # "Drive fault — inverter overtemperature"
    cause:           Optional[str] = None
    action:          Optional[str] = None

    # Filled by ReasonClassifier
    reason_level_1:  Optional[str] = None
    reason_level_2:  Optional[str] = None
    reason_level_3:  Optional[str] = None
    reason_level_4:  Optional[str] = None
    category_type:   str = "Unplanned Downtime"

    # Added by pipeline
    machine:         Optional[str] = None
    source_md5:      Optional[str] = None
    source_file:     Optional[str] = None
    extracted_at:    Optional[datetime] = None
    manually_edited: bool = False

class ParameterRecord(BaseModel):
    parameter_code:  Optional[str] = None
    description:     str             # "Clamping force" — unique key in doc
    section:         Optional[str] = None
    product_desc:    Optional[str] = None

    # Tolerance band — all optional floats
    target:          Optional[float] = None
    unit:            Optional[str] = None
    lrl:             Optional[float] = None
    lsl:             Optional[float] = None
    lwl:             Optional[float] = None
    uwl:             Optional[float] = None
    usl:             Optional[float] = None
    url:             Optional[float] = None

    machine:         Optional[str] = None
    source_md5:      Optional[str] = None
    source_file:     Optional[str] = None
    extracted_at:    Optional[datetime] = None

class ExtractionResult(BaseModel):
    success:         bool
    alarms:          List[AlarmRecord]
    parameters:      List[ParameterRecord]
    errors:          List[str]
    warnings:        List[str]
    debug_steps:     List[str]   # shown in UI "Phase Trace" expander
    timings:         dict        # shown in UI "Tool Timings" expander
    source_filename: Optional[str] = None
    source_md5:      Optional[str] = None
    source_text:     str = ""
