import os
from core.phase_engine import PhaseEngine
from core.spreadsheet_generator import SpreadsheetGenerator

class ExtractionAgent:
    """
    Service Layer: ExtractionAgent
    Receives JSON records from the Document Intelligence layer.
    Classifies document type, maps JSON fields to tab rows,
    and fills the schema per tab to generate the final .xlsx file.
    """
    def generate_excel(self, machine: str, source_text: str, alarms: list, parameters: list) -> str:
        # Step 1: Initialize PhaseEngine (maps JSON to tabs)
        pe = PhaseEngine(machine, source_text, alarms, parameters)
        
        # Step 2: Build tab rows based on configurations (Phases 1, 2, 3 as per architecture)
        tabs_data = pe.build(phases=[1, 2, 3])
        
        # Step 3: Populate Spreadsheet 
        sg = SpreadsheetGenerator()
        for tname, rows in tabs_data.items():
            sg.populate_rows(tname, rows)
            
        # Step 4: Save & Return file path
        out_path = sg.save(machine)
        return out_path
