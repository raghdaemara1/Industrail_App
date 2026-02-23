import re
from config import PARAMETER_NOISE_PATTERNS

class ParameterSpecsExtractor:
    def __init__(self):
        self.noise_patterns = [re.compile(p) for p in PARAMETER_NOISE_PATTERNS]

    def extract_parameters(self, text: str) -> list:
        parameters = []
        lines = text.split('\n')
        # E.g. "Clamping force 2000.0 kN" -> desc: Clamping force, target: 2000.0, unit: kN
        # E.g. "Temperature 180 - 220 C" -> desc: Temperature, lsl: 180, usl: 220
        # E.g. "Speed 100 ± 10 rpm" -> desc: Speed, target: 100, lsl: 90, usl: 110
        
        p_tol = re.compile(r'([A-Za-z\s]+)\s+(\d+(?:\.\d+)?)\s*(?:±|\+/-)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z%]+(?:\/[a-zA-Z]+)?)')
        p_range = re.compile(r'([A-Za-z\s]+)\s+(\d+(?:\.\d+)?)\s*(?:-|to|\.\.\.)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z%]+(?:\/[a-zA-Z]+)?)')
        p_single = re.compile(r'([A-Za-z\s]+)\s+(\d+(?:\.\d+)?)\s*([a-zA-Z%]+(?:\/[a-zA-Z]+)?)')
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Noise filter
            if any(p.search(line) for p in self.noise_patterns):
                continue
                
            desc = tag = unit = None
            target = lsl = usl = None
            
            # 1. Try Tolerance Pattern
            m_tol = p_tol.search(line)
            if m_tol:
                desc = m_tol.group(1).strip()
                val = float(m_tol.group(2))
                tol = float(m_tol.group(3))
                unit = m_tol.group(4).strip()
                target = val
                lsl = val - tol
                usl = val + tol
            else:
                # 2. Try Range Pattern
                m_range = p_range.search(line)
                if m_range:
                    desc = m_range.group(1).strip()
                    vmin = float(m_range.group(2))
                    vmax = float(m_range.group(3))
                    unit = m_range.group(4).strip()
                    target = (vmin + vmax) / 2.0
                    lsl = vmin
                    usl = vmax
                else:
                    # 3. Try Single Value Pattern
                    m_single = p_single.search(line)
                    if m_single:
                        desc = m_single.group(1).strip()
                        val = float(m_single.group(2))
                        unit = m_single.group(3).strip()
                        target = val
            
            if desc and target is not None:
                # If too short, probably not a real parameter
                if len(desc) < 3: continue
                
                # Try to avoid extracting typical English sentences
                if " " in desc and len(desc.split()) > 5:
                    continue
                    
                parameters.append({
                    "description": desc,
                    "target": target,
                    "unit": unit,
                    "lsl": lsl,
                    "usl": usl,
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
