from pathlib import Path
import win32com.client

root = Path.cwd()
docx = root / 'submissions/lab01/01_实验报告/实验报告_何嘉欣_2410311411.docx'
pdf = root / 'submissions/lab01/01_实验报告/实验报告_何嘉欣_2410311411.pdf'
word = None
doc = None
try:
    word = win32com.client.DispatchEx('Word.Application')
    word.Visible = False
    word.DisplayAlerts = 0
    doc = word.Documents.Open(str(docx), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False)
    doc.ExportAsFixedFormat(
        OutputFileName=str(pdf), ExportFormat=17, OpenAfterExport=False,
        OptimizeFor=0, Range=0, Item=0, IncludeDocProps=True, KeepIRM=True,
        CreateBookmarks=0, DocStructureTags=True, BitmapMissingFonts=True,
        UseISO19005_1=False,
    )
    print('EXPORTED', pdf)
finally:
    if doc is not None:
        doc.Close(False)
    if word is not None:
        word.Quit()
