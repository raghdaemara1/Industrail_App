import re
from config import PARAMETER_NOISE_PATTERNS

class ParameterSpecsExtractor:
    def __init__(self):
        self.noise_patterns = [re.compile(p) for p in PARAMETER_NOISE_PATTERNS]

    def extract_parameters(self, text: str) -> list:
        parameters = []
        lines = text.split('\n')
        # Simple extraction looking for Parameter XYZ or P-XYZ with values 
        # For demo purposes, we do a basic regex 
        # E.g. "Clamping force 2000.0 kN" -> desc: Clamping force, target: 2000.0, unit: kN
        
        param_pattern = re.compile(r'([A-Za-z\s]+)\s+(\d+(\.\d+)?)\s*([a-zA-Z%]+(?:\/[a-zA-Z]+)?)')
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Noise filter
            if any(p.search(line) for p in self.noise_patterns):
                continue
                
            match = param_pattern.search(line)
            if match:
                desc = match.group(1).strip()
                # If too short, probably not a real parameter
                if len(desc) < 3: continue
                val = float(match.group(2))
                unit = match.group(4).strip()
                
                # Try to avoid extracting typical English sentences
                if " " in desc and len(desc.split()) > 5:
                    continue
                    
                parameters.append({
                    "description": desc,
                    "target": val,
                    "unit": unit,
                    "machine": None,
                    "parameter_code": None,
                    "section": None,
                    "product_desc": None
                })
        
        # Deduplicate
        unique_params = {}
        for p in parameters:
            unique_params[p["description"]] = p
            
        return list(unique_params.values())
