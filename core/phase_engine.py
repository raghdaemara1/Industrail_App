from core.schemas import AlarmRecord, ParameterRecord
from typing import List, Dict

class PhaseEngine:
    def __init__(self, machine: str, text: str, alarms: List[AlarmRecord], parameters: List[ParameterRecord]):
        self.machine = machine
        self.text = text
        self.alarms = alarms
        self.parameters = parameters

    def build(self, phases: List[int]) -> Dict[str, list]:
        tabs = {}
        if 1 in phases:
            self._build_phase1(tabs)
        if 2 in phases:
            self._build_phase2(tabs)
        if 3 in phases:
            self._build_phase3(tabs)
        return tabs

    def _build_phase1(self, tabs: dict) -> None:
        tabs["Machine Details"] = [{"Machine *": self.machine, "Description": "Main unit"}]
        tabs["OEE"] = [{"Machine *": self.machine, "Calculation Type": "Standard"}]
        
        # Downtime Configuration tab (Alarms)
        downtime = []
        for r in self.alarms:
             downtime.append({
                 "Machine *": r.machine or self.machine,
                 "Reason 1 *": r.reason_level_1,
                 "Reason 2": r.reason_level_2,
                 "Reason 3": r.reason_level_3 or r.cause or "",
                 "Reason 4": r.reason_level_4 or r.action or "",
                 "Category Type *": r.category_type,
                 "Fault Code *": str(r.alarm_id).zfill(4),
                 "Fault Name *": r.description
             })
        tabs["Downtime Configuration"] = downtime
        
        # Parameter Specifications
        specs = []
        for p in self.parameters:
             specs.append({
                 "Machine *": p.machine or self.machine,
                 "Parameter Desc *": p.description,
                 "Product Desc *": p.product_desc or "All",
                 "LRL": p.lrl,
                 "LSL": p.lsl,
                 "LWL": p.lwl,
                 "Target": p.target,
                 "UWL": p.uwl,
                 "USL": p.usl,
                 "URL": p.url
             })
        tabs["Parameter Specifications"] = specs

    def _build_phase2(self, tabs: dict) -> None:
        pass # To be implemented in Q2 2026

    def _build_phase3(self, tabs: dict) -> None:
        pass # To be implemented in Q4 2026
