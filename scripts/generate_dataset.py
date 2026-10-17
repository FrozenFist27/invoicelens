"""Generate 50 synthetic invoice/PO documents + labels + splits.

Seed 42. Mix: 13 text PDF, 13 scanned PDF, 12 spreadsheet, 12 email (4 with an
attachment, 8 body-only). ~70% invoices, ~30% POs. Synthetic only (Faker company
names). Injected difficulty: ~15% ambiguous number formats, ~10% inconsistent totals.
"""

from __future__ import annotations

import email
import email.message
import json
import random
import shutil
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from faker import Faker

fake = Faker("en_US")
Faker.seed(42)

CURRENCIES = ["USD", "EUR", "GBP", "INR", "AUD"]
ITEM_POOL = [
    "Monthly hosting subscription", "Annual software licence", "Consulting hours",
    "Hardware purchase", "Network equipment", "Office supplies", "Cloud storage plan",
    "Support retainer", "Training workshop", "Travel expenses", "Printing services",
    "Translation services", "Data plan", "Security audit", "Maintenance contract",
    "Server rack", "Laptop docking station", "Ergonomic chair", "Desk lamp",
    "Whiteboard markers", "USB-C cables", "Backup generator service",
]

DATE_STYLES = ["iso", "slash_dmy", "slash_mdy", "long"]
NUMBER_STYLES = ["plain", "comma", "euro"]


def money(x) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def make_truth(rng: random.Random, doc_id: str) -> dict:
    kind = "invoice" if rng.random() < 0.7 else "purchase_order"
    n_items = rng.randint(1, 8)
    currency = rng.choice(CURRENCIES)
    issue = date(2026, rng.randint(1, 12), rng.randint(1, 28))
    due = issue + timedelta(days=rng.choice([14, 30, 45, 60])) if rng.random() < 0.85 else None
    supplier = fake.company()
    has_tax_id = rng.random() < 0.7
    tax_id = f"TAX-{rng.randint(100000, 999999)}" if has_tax_id else None
    doc_no = f"{('INV' if kind=='invoice' else 'PO')}-{rng.randint(1000, 99999)}"

    line_items = []
    for _ in range(n_items):
        desc = rng.choice(ITEM_POOL)
        qty = rng.randint(1, 20)
        unit = money(rng.uniform(5, 500))
        amt = money(qty * unit)
        line_items.append(
            {"description": desc, "quantity": qty, "unit_price": unit, "amount": amt}
        )
    subtotal = money(sum(li["amount"] for li in line_items))
    has_tax = rng.random() < 0.8
    if has_tax:
        rate = rng.choice([Decimal("0.05"), Decimal("0.10"), Decimal("0.18"), Decimal("0.20")])
        tax = money(subtotal * rate)
    else:
        tax = None
    total = money(subtotal + (tax or Decimal(0)))

    inconsistent = rng.random() < 0.10
    if inconsistent:
        # printed total does NOT equal subtotal + tax; keep the printed value as truth
        total = money(total + Decimal(rng.choice(["5.00", "12.50", "-3.25", "100.00"])))

    ambiguous = rng.random() < 0.15

    return {
        "doc_id": doc_id,
        "doc_kind": kind,
        "supplier_name": supplier,
        "supplier_tax_id": tax_id,
        "document_number": doc_no,
        "issue_date": issue,
        "due_date": due,
        "currency": currency,
        "line_items": line_items,
        "subtotal": subtotal,
        "tax_total": tax,
        "total": total,
        "ambiguous_numbers": ambiguous,
        "inconsistent_total": inconsistent,
        "date_style": rng.choice(DATE_STYLES),
        "number_style": "euro" if ambiguous else rng.choice(["plain", "comma"]),
    }


def fmt_date(d: date | None, style: str) -> str:
    if d is None:
        return ""
    if style == "iso":
        return d.isoformat()
    if style == "slash_dmy":
        return d.strftime("%d/%m/%Y")
    if style == "slash_mdy":
        return d.strftime("%m/%d/%Y")
    if style == "long":
        return d.strftime("%d %B %Y")
    return d.isoformat()


def fmt_num(x: Decimal, style: str) -> str:
    if x is None:
        return ""
    s = f"{x:,.2f}"
    if style == "plain":
        return s.replace(",", "")
    if style == "comma":
        return s
    if style == "euro":
        # 1.234,56
        int_part, _, frac = s.partition(".")
        int_part = int_part.replace(",", ".")
        return f"{int_part},{frac}"
    return s


def _truth_to_label(truth: dict, source_pages: dict[str, str]) -> dict:
    def dec_or_none(x):
        return float(x) if x is not None else None

    return {
        "doc_id": truth["doc_id"],
        "doc_kind": truth["doc_kind"],
        "supplier_name": truth["supplier_name"],
        "supplier_tax_id": truth["supplier_tax_id"],
        "document_number": truth["document_number"],
        "issue_date": truth["issue_date"].isoformat(),
        "due_date": truth["due_date"].isoformat() if truth["due_date"] else None,
        "currency": truth["currency"],
        "line_items": [
            {
                "description": li["description"],
                "quantity": li["quantity"],
                "unit_price": dec_or_none(li["unit_price"]),
                "amount": dec_or_none(li["amount"]),
            }
            for li in truth["line_items"]
        ],
        "subtotal": dec_or_none(truth["subtotal"]),
        "tax_total": dec_or_none(truth["tax_total"]),
        "total": dec_or_none(truth["total"]),
        "source_pages": source_pages,
        "inconsistent_total": truth["inconsistent_total"],
        "ambiguous_numbers": truth["ambiguous_numbers"],
    }


# ---------- PDF rendering ----------

def _pdf_pages_count(text: str, items_per_page: int) -> int:
    return 1


def render_text_pdf(truth: dict, path: Path, rng: random.Random) -> dict[str, str]:
    """Render a text-based PDF. Returns source_pages map (best-effort page refs)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)
    W, H = A4
    src_pages: dict[str, str] = {}
    page_no = 1
    y = H - 25 * mm

    def new_page():
        nonlocal y, page_no
        c.showPage()
        page_no += 1
        y = H - 25 * mm

    def line(text: str, x=20 * mm, dy=6 * mm, font="Helvetica", size=10):
        nonlocal y
        if y < 20 * mm:
            new_page()
        c.setFont(font, size)
        c.drawString(x, y, text)
        y -= dy

    # header (template varies by doc_id hash for layout diversity)
    template = hash(truth["doc_id"]) % 4
    if template == 0:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(20 * mm, y, truth["supplier_name"])
        y -= 10 * mm
    elif template == 1:
        c.setFont("Helvetica-Bold", 18)
        c.drawRightString(W - 20 * mm, y, truth["supplier_name"])
        y -= 12 * mm
    else:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(20 * mm, y, truth["supplier_name"])
        y -= 8 * mm

    label = "INVOICE" if truth["doc_kind"] == "invoice" else "PURCHASE ORDER"
    line(label, font="Helvetica-Bold", size=12)
    src_pages["doc_kind"] = f"p{page_no}"
    src_pages["supplier_name"] = f"p{page_no}"

    if truth["supplier_tax_id"]:
        line(f"Tax ID: {truth['supplier_tax_id']}")
        src_pages["supplier_tax_id"] = f"p{page_no}"
    line(f"Document No: {truth['document_number']}")
    src_pages["document_number"] = f"p{page_no}"
    line(f"Date: {fmt_date(truth['issue_date'], truth['date_style'])}")
    src_pages["issue_date"] = f"p{page_no}"
    if truth["due_date"]:
        line(f"Due: {fmt_date(truth['due_date'], truth['date_style'])}")
        src_pages["due_date"] = f"p{page_no}"
    line(f"Currency: {truth['currency']}")
    src_pages["currency"] = f"p{page_no}"
    y -= 4 * mm

    # line items table
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Description")
    c.drawString(90 * mm, y, "Qty")
    c.drawString(115 * mm, y, "Unit")
    c.drawString(150 * mm, y, "Amount")
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    for i, li in enumerate(truth["line_items"]):
        if y < 30 * mm:
            new_page()
            c.setFont("Helvetica", 9)
        c.drawString(20 * mm, y, li["description"][:40])
        c.drawString(90 * mm, y, str(li["quantity"]))
        c.drawString(115 * mm, y, fmt_num(li["unit_price"], truth["number_style"]))
        c.drawString(150 * mm, y, fmt_num(li["amount"], truth["number_style"]))
        for sub, x in (("description", 20), ("quantity", 90), ("unit_price", 115), ("amount", 150)):
            src_pages[f"line_items[{i}].{sub}"] = f"p{page_no}"
        y -= 6 * mm

    y -= 4 * mm
    c.setFont("Helvetica", 10)
    c.drawString(120 * mm, y, f"Subtotal: {fmt_num(truth['subtotal'], truth['number_style'])}")
    src_pages["subtotal"] = f"p{page_no}"
    y -= 6 * mm
    if truth["tax_total"] is not None:
        c.drawString(120 * mm, y, f"Tax: {fmt_num(truth['tax_total'], truth['number_style'])}")
        src_pages["tax_total"] = f"p{page_no}"
        y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(120 * mm, y, f"TOTAL: {fmt_num(truth['total'], truth['number_style'])}")
    src_pages["total"] = f"p{page_no}"

    c.save()
    return src_pages


def render_scanned_pdf(truth: dict, path: Path, rng: random.Random) -> dict[str, str]:
    """Text PDF -> rasterize -> degrade (rotation/noise/JPEG) -> image-only PDF."""
    import fitz
    from PIL import Image, ImageFilter

    tmp = path.with_suffix(".tmp.pdf")
    src_pages = render_text_pdf(truth, tmp, rng)

    src = fitz.open(str(tmp))
    out = fitz.open()
    for page in src:
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        # rotate +-2 degrees
        angle = rng.uniform(-2, 2)
        img = img.rotate(angle, expand=True, fillcolor=(255, 255, 255))
        # gaussian noise
        img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
        # jpeg artefacts
        import io

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=55)
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
        # write image onto a new page
        new_page = out.new_page(width=img.width, height=img.height)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=85)
        new_page.insert_image(new_page.rect, stream=img_bytes.getvalue())
    out.save(str(path))
    out.close()
    src.close()
    tmp.unlink(missing_ok=True)
    return src_pages


def render_spreadsheet(truth: dict, path: Path, rng: random.Random) -> dict[str, str]:
    """xlsx with cell coordinates; source_pages uses the sheet name."""
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice"
    ws["A1"] = truth["supplier_name"]
    ws["A2"] = "INVOICE" if truth["doc_kind"] == "invoice" else "PURCHASE ORDER"
    ws["A3"] = f"Document No: {truth['document_number']}"
    ws["B3"] = truth["document_number"]
    ws["A4"] = "Date"
    ws["B4"] = fmt_date(truth["issue_date"], truth["date_style"])
    if truth["due_date"]:
        ws["A5"] = "Due"
        ws["B5"] = fmt_date(truth["due_date"], truth["date_style"])
    ws["A6"] = "Currency"
    ws["B6"] = truth["currency"]
    if truth["supplier_tax_id"]:
        ws["A7"] = "Tax ID"
        ws["B7"] = truth["supplier_tax_id"]
    row = 9
    ws[f"A{row}"] = "Description"
    ws[f"B{row}"] = "Qty"
    ws[f"C{row}"] = "Unit Price"
    ws[f"D{row}"] = "Amount"
    row += 1
    for li in truth["line_items"]:
        ws[f"A{row}"] = li["description"]
        ws[f"B{row}"] = li["quantity"]
        ws[f"C{row}"] = float(li["unit_price"])
        ws[f"D{row}"] = float(li["amount"])
        row += 1
    row += 1
    ws[f"C{row}"] = "Subtotal"
    ws[f"D{row}"] = float(truth["subtotal"])
    row += 1
    if truth["tax_total"] is not None:
        ws[f"C{row}"] = "Tax"
        ws[f"D{row}"] = float(truth["tax_total"])
        row += 1
    ws[f"C{row}"] = "TOTAL"
    ws[f"D{row}"] = float(truth["total"])
    wb.save(str(path))

    sheet = "Invoice"
    src = {
        "supplier_name": sheet, "doc_kind": sheet, "document_number": sheet,
        "issue_date": sheet, "currency": sheet, "total": sheet, "subtotal": sheet,
    }
    if truth["due_date"]:
        src["due_date"] = sheet
    if truth["supplier_tax_id"]:
        src["supplier_tax_id"] = sheet
    if truth["tax_total"] is not None:
        src["tax_total"] = sheet
    for i in range(len(truth["line_items"])):
        for sub in ("description", "quantity", "unit_price", "amount"):
            src[f"line_items[{i}].{sub}"] = sheet
    return src


def render_email(truth: dict, path: Path, rng: random.Random, with_attachment: Path | None = None) -> dict[str, str]:
    """Body-only or with a PDF/xlsx attachment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    msg = email.message.EmailMessage()
    msg["From"] = "ap@supplier-demo.example"
    msg["To"] = "accounting@buyer-demo.example"
    kind = "Invoice" if truth["doc_kind"] == "invoice" else "Purchase Order"
    msg["Subject"] = f"{kind} {truth['document_number']} from {truth['supplier_name']}"

    body_lines = [
        f"Please find our {kind.lower()} below.",
        "",
        f"Supplier: {truth['supplier_name']}",
    ]
    if truth["supplier_tax_id"]:
        body_lines.append(f"Tax ID: {truth['supplier_tax_id']}")
    body_lines += [
        f"Document No: {truth['document_number']}",
        f"Date: {fmt_date(truth['issue_date'], truth['date_style'])}",
    ]
    if truth["due_date"]:
        body_lines.append(f"Due: {fmt_date(truth['due_date'], truth['date_style'])}")
    body_lines.append(f"Currency: {truth['currency']}")
    body_lines.append("")
    body_lines.append("Items:")
    for li in truth["line_items"]:
        body_lines.append(
            f"- {li['description']} x{li['quantity']} @ {fmt_num(li['unit_price'], truth['number_style'])} "
            f"= {fmt_num(li['amount'], truth['number_style'])}"
        )
    body_lines.append("")
    body_lines.append(f"Subtotal: {fmt_num(truth['subtotal'], truth['number_style'])}")
    if truth["tax_total"] is not None:
        body_lines.append(f"Tax: {fmt_num(truth['tax_total'], truth['number_style'])}")
    body_lines.append(f"TOTAL: {fmt_num(truth['total'], truth['number_style'])}")
    msg.set_content("\n".join(body_lines))

    if with_attachment is not None and with_attachment.exists():
        data = with_attachment.read_bytes()
        ext = with_attachment.suffix.lower()
        mime = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        msg.add_attachment(data, maintype=mime.split("/")[0], subtype=mime.split("/")[1], filename=with_attachment.name)

    path.write_bytes(bytes(msg))
    src = {
        "supplier_name": "body", "doc_kind": "body", "document_number": "body",
        "issue_date": "body", "currency": "body", "total": "body", "subtotal": "body",
    }
    if truth["due_date"]:
        src["due_date"] = "body"
    if truth["supplier_tax_id"]:
        src["supplier_tax_id"] = "body"
    if truth["tax_total"] is not None:
        src["tax_total"] = "body"
    for i in range(len(truth["line_items"])):
        for sub in ("description", "quantity", "unit_price", "amount"):
            src[f"line_items[{i}].{sub}"] = "body"
    return src


def generate(seed: int = 42, out_root: Path | None = None) -> None:
    out_root = out_root or (Path(__file__).resolve().parents[1] / "data")
    rng = random.Random(seed)
    syn = out_root / "synthetic"
    labels = out_root / "labels"
    if syn.exists():
        shutil.rmtree(syn)
    if labels.exists():
        shutil.rmtree(labels)
    syn.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)

    # plan the mix
    types = ["text_pdf"] * 13 + ["scanned_pdf"] * 13 + ["spreadsheet"] * 12 + ["email"] * 12
    rng.shuffle(types)

    doc_types: dict[str, str] = {}
    for i, dtype in enumerate(types):
        doc_id = f"doc_{i:03d}"
        truth = make_truth(rng, doc_id)
        doc_types[doc_id] = dtype

        if dtype == "text_pdf":
            src_pages = render_text_pdf(truth, syn / f"{doc_id}.pdf", rng)
        elif dtype == "scanned_pdf":
            src_pages = render_scanned_pdf(truth, syn / f"{doc_id}.pdf", rng)
        elif dtype == "spreadsheet":
            src_pages = render_spreadsheet(truth, syn / f"{doc_id}.xlsx", rng)
        else:  # email
            attach_path = None
            if i % 3 == 0:  # ~4 of 12 emails have an attachment
                attach_path = syn / f"{doc_id}_att.pdf"
                render_text_pdf(truth, attach_path, rng)
            src_pages = render_email(truth, syn / f"{doc_id}.eml", rng, with_attachment=attach_path)

        label = _truth_to_label(truth, src_pages)
        (labels / f"{doc_id}.json").write_text(json.dumps(label, indent=2), encoding="utf-8")

    # stratified split: 40 dev / 10 heldout, by doc type
    by_type: dict[str, list[str]] = {}
    for did, dt in doc_types.items():
        by_type.setdefault(dt, []).append(did)
    dev: list[str] = []
    heldout: list[str] = []
    for dt, ids in by_type.items():
        ids_sorted = sorted(ids)
        rng.shuffle(ids_sorted)
        n_held = max(1, round(len(ids_sorted) * 0.2))
        heldout.extend(ids_sorted[:n_held])
        dev.extend(ids_sorted[n_held:])
    splits = {"dev": sorted(dev), "heldout": sorted(heldout), "doc_types": doc_types}
    (out_root / "splits.json").write_text(json.dumps(splits, indent=2), encoding="utf-8")
    print(f"generated {len(types)} docs: {len(dev)} dev / {len(heldout)} heldout")


if __name__ == "__main__":
    generate()
