import re

def extract(text):
    # Match basic parameter: Desc Target Unit
    # Match range: Desc Min - Max Unit
    # Match tolerance: Desc Target +- Tol Unit
    
    # We'll use a few patterns or a combined one.
    
    # Pattern 1: target ± tolerance
    p_tol = re.compile(r'([A-Za-z\s]+)\s+(\d+(?:\.\d+)?)\s*(?:±|\+/-)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z%]+(?:/[a-zA-Z]+)?)')
    
    # Pattern 2: min - max OR min ... max OR min to max
    p_range = re.compile(r'([A-Za-z\s]+)\s+(\d+(?:\.\d+)?)\s*(?:-|to|\.\.\.)\s*(\d+(?:\.\d+)?)\s*([a-zA-Z%]+(?:/[a-zA-Z]+)?)')
    
    # Pattern 3: single target (fallback)
    p_single = re.compile(r'([A-Za-z\s]+)\s+(\d+(?:\.\d+)?)\s*([a-zA-Z%]+(?:/[a-zA-Z]+)?)')

    results = []
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        
        m = p_tol.search(line)
        if m:
            desc, target, tol, unit = m.groups()
            results.append({
                "desc": desc.strip(),
                "target": float(target),
                "lsl": float(target) - float(tol),
                "usl": float(target) + float(tol),
                "unit": unit.strip()
            })
            continue
            
        m = p_range.search(line)
        if m:
            desc, vmin, vmax, unit = m.groups()
            target = (float(vmin) + float(vmax)) / 2
            results.append({
                "desc": desc.strip(),
                "target": target,
                "lsl": float(vmin),
                "usl": float(vmax),
                "unit": unit.strip()
            })
            continue

        m = p_single.search(line)
        if m:
            desc, target, unit = m.groups()
            results.append({
                "desc": desc.strip(),
                "target": float(target),
                "unit": unit.strip()
            })
            continue
            
    return results

test_text = """
Clamping force 2000 kN
Temperature range 180 - 220 C
Tolerance +- 5 mm
Pressure 50.5 to 60.0 bar
Speed 100 ± 10 rpm
Some noise line 123
"""

for r in extract(test_text):
    print(r)
