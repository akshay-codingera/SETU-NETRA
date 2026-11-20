import pypdfium2 as pdfium
import os

pdf_files = [
    "output/e2e_acceptance_multipage.pdf",
    "output/test_multipage.pdf",
    "output/uploads/5c4224e8/Track-2 Report.pdf"
]

for p in pdf_files:
    if os.path.exists(p):
        try:
            pdf = pdfium.PdfDocument(p)
            print(f"{p}: {len(pdf)} pages, size {os.path.getsize(p)} bytes")
        except Exception as e:
            print(f"{p}: Error reading PDF: {e}")
    else:
        print(f"{p}: File does not exist")
