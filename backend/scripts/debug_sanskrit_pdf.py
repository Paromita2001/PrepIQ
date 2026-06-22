"""Debug: check what text pdfplumber extracts from a Sanskrit SQP PDF."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pdfplumber
from pathlib import Path

pdf_path = Path(__file__).parent.parent.parent / "data" / "pyq" / "sanskrit" / "sqp_2023_sanskrit.pdf"
print(f"Reading: {pdf_path}")

with pdfplumber.open(str(pdf_path)) as pdf:
    print(f"Pages: {len(pdf.pages)}")
    for i, page in enumerate(pdf.pages[:3]):
        t = page.extract_text()
        if t:
            preview = t[:500].encode("utf-8", errors="replace").decode("utf-8")
            print(f"\n--- Page {i+1} (first 500 chars) ---")
            print(repr(preview[:200]))
        else:
            print(f"\n--- Page {i+1}: NO TEXT ---")
