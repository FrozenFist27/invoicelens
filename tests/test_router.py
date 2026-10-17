"""Router + loader tests."""

from invoicelens.ingest import router
from invoicelens.ingest import email_msg, spreadsheet, text_pdf


def test_detect_email(fixtures_dir):
    assert router.detect(fixtures_dir / "mail.eml") == "email"


def test_detect_spreadsheet(fixtures_dir):
    assert router.detect(fixtures_dir / "sheet.xlsx") == "spreadsheet"


def test_detect_text_pdf(fixtures_dir):
    assert router.detect(fixtures_dir / "text.pdf") == "text_pdf"


def test_detect_scanned_pdf(fixtures_dir):
    assert router.detect(fixtures_dir / "scanned.pdf") == "scanned_pdf"


def test_text_pdf_load_marks(fixtures_dir):
    doc = text_pdf.load(fixtures_dir / "text.pdf")
    assert doc.pages
    assert doc.pages[0].ref == "p1"
    marked = text_pdf.marked_text(doc)
    assert "[p1]" in marked
    assert "ACME" in marked


def test_spreadsheet_load(fixtures_dir):
    doc = spreadsheet.load(fixtures_dir / "sheet.xlsx")
    assert doc.doc_type == "spreadsheet"
    assert doc.pages[0].ref == "Invoice"
    assert "A1=ACME Supplies Ltd" in doc.pages[0].text


def test_email_load_body(fixtures_dir):
    doc, atts = email_msg.load(fixtures_dir / "mail.eml")
    assert doc.doc_type == "email"
    assert doc.pages[0].ref == "body"
    assert "INV-1001" in doc.pages[0].text
    assert atts == []
