import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("output/uploads/5c4224e8/Track-2 Report.pdf")
print("Total pages:", len(pdf))
for i in range(min(5, len(pdf))):
    page = pdf[i]
    textpage = page.get_textpage()
    text = textpage.get_text_range()
    print(f"--- PAGE {i+1} ---")
    print(text[:300].strip())
