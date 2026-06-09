import PyPDF2
with open(r'c:\Users\Tulio225\Desktop\PROJETOS GR ANTIGRAVITY\PROJETO SUPER GR\scratch\AE_36243826_REAL_OPENTECH.pdf', 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    print(pdf.pages[0].extract_text().encode('ascii', 'ignore').decode('ascii')[:1000])
