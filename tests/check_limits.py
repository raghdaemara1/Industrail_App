import sys
import os

sys.path.insert(0, os.path.abspath(r'd:\OneDrive - Obeikan Investment Group\desktop\Industrail_App'))

from core.pdf_processor import PDFProcessor
from extractors.parameter_specs_extractor import ParameterSpecsExtractor
import pprint

pdf_path = r'd:\OneDrive - Obeikan Investment Group\desktop\Industrail_App\doc\ARBURG_ALLROUNDER_570A_TD_680092_en_GB.pdf'
with open(pdf_path, 'rb') as f:
    text = PDFProcessor(f.read()).extract_text()

params = ParameterSpecsExtractor().extract_parameters(text)
with_limits = [p for p in params if p.get('lsl') is not None or p.get('usl') is not None]

print(f"Total params: {len(params)}")
print(f"With limits: {len(with_limits)}")
pprint.pprint(with_limits[:10])
