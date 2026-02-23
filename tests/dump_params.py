import sys
import os
import io

sys.path.insert(0, os.path.abspath(r'd:\OneDrive - Obeikan Investment Group\desktop\Industrail_App'))

from core.pdf_processor import PDFProcessor
from extractors.parameter_specs_extractor import ParameterSpecsExtractor

pdf_path = r'd:\OneDrive - Obeikan Investment Group\desktop\Industrail_App\doc\ARBURG_ALLROUNDER_570A_TD_680092_en_GB.pdf'
print(f"Loading {pdf_path}")

with open(pdf_path, 'rb') as f:
    data = f.read()

print(f"Data length: {len(data)}")
proc = PDFProcessor(data)
text = proc.extract_text()
print(f"Text length: {len(text)}")

ext = ParameterSpecsExtractor()
params = ext.extract_parameters(text)

with open('params_output.txt', 'w', encoding='utf-8') as f:
    f.write(f"Total params extracted: {len(params)}\n")
    for p in params:
        f.write(str(p) + '\n')
print(f"Done. Extracted {len(params)} parameters. Check params_output.txt")
