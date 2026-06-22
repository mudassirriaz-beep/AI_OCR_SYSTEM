"""
Generate professional PDF report for OCR System project — compact 5-page version.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.pdfgen import canvas
import os

OUTPUT = r"C:\Users\ZAH\Documents\AI_Document_System - Copy - Copy - Copy\OCR_System_Report.pdf"
LOGO   = r"C:\Users\ZAH\Pictures\logo.png"

DARK_TEAL  = colors.HexColor("#0d4f5c")
TEAL       = colors.HexColor("#1a7a8a")
LIGHT_TEAL = colors.HexColor("#e8f4f6")
ACCENT     = colors.HexColor("#2ecc71")
DARK_GREY  = colors.HexColor("#2c3e50")
MID_GREY   = colors.HexColor("#7f8c8d")
LIGHT_GREY = colors.HexColor("#f5f6fa")
WHITE      = colors.white
W, H = A4


def add_footer(cv, doc):
    cv.saveState()
    cv.setFillColor(DARK_TEAL)
    cv.rect(0, 0, W, 1.1*cm, fill=1, stroke=0)
    cv.setFillColor(WHITE)
    cv.setFont("Helvetica", 8)
    cv.drawString(2*cm, 0.38*cm, "Al-Khair Institute of Technology  |  OCR System — Internal Technical Report  |  June 2026")
    cv.drawRightString(W - 2*cm, 0.38*cm, f"Page {doc.page}")
    cv.restoreState()


def S(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=10, textColor=DARK_GREY, leading=14, spaceAfter=4)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


def sec(title):
    t = Table([[Paragraph(title, S("sh", fontName="Helvetica-Bold", fontSize=13,
                textColor=DARK_TEAL, spaceAfter=0))]], colWidths=[17*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT_TEAL),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LINEBELOW",     (0,0), (-1,-1), 2, TEAL),
    ]))
    return t


def tbl(data, widths, header=True):
    t = Table(data, colWidths=widths)
    style = [
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#cde8ec")),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GREY]),
    ]
    if header:
        style += [
            ("BACKGROUND", (0,0), (-1,0), DARK_TEAL),
            ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("ALIGN",      (0,0), (-1,0), "CENTER"),
        ]
    t.setStyle(TableStyle(style))
    return t


def build():
    doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm,
        title="OCR System — Technical Report",
        author="Al-Khair Institute of Technology")

    body  = S("b", alignment=TA_JUSTIFY, leading=13, spaceAfter=5)
    h2    = S("h2", fontName="Helvetica-Bold", fontSize=10, textColor=TEAL, spaceBefore=6, spaceAfter=3)
    cell  = S("c", fontSize=9, leading=12)
    hdr   = S("hdr", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE, alignment=TA_CENTER)
    story = []

    # ═══════════════════════════════════════════
    #  PAGE 1 — COVER
    # ═══════════════════════════════════════════

    # Logo on WHITE background so no clash
    logo_img = Image(LOGO, width=5*cm, height=3.2*cm, kind="proportional") if os.path.exists(LOGO) else Paragraph("AIT", S("l", fontSize=20, textColor=DARK_TEAL, alignment=TA_CENTER))

    logo_block = Table([
        [Paragraph("Al-Khair Institute of Technology", S("co", fontName="Helvetica-Bold", fontSize=11, textColor=DARK_TEAL, alignment=TA_CENTER))],
        [logo_img],
    ], colWidths=[17*cm])
    logo_block.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), WHITE),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
    ]))
    story.append(logo_block)

    # Dark teal title band — no logo here
    title_block = Table([
        [Paragraph("OCR System", S("t", fontName="Helvetica-Bold", fontSize=32, textColor=WHITE, alignment=TA_CENTER, spaceAfter=4))],
        [Paragraph("AI-Powered Document Extraction Platform", S("st", fontSize=13, textColor=colors.HexColor("#d0f0f5"), alignment=TA_CENTER, spaceAfter=2))],
        [Paragraph("CNIC &amp; Driving License — Automated Data Extraction", S("st2", fontSize=10, textColor=colors.HexColor("#a8d8e0"), alignment=TA_CENTER))],
    ], colWidths=[17*cm])
    title_block.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), DARK_TEAL),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0), (-1,-1), 16),
        ("BOTTOMPADDING", (0,0), (-1,-1), 16),
    ]))
    story.append(title_block)

    accent_bar = Table([[""]], colWidths=[17*cm])
    accent_bar.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),ACCENT),
                                    ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(accent_bar)
    story.append(Spacer(1, 0.5*cm))

    meta = [
        ["Organization",  "Al-Khair Institute of Technology (AIT)"],
        ["Product Name",  "OCR System"],
        ["Document Type", "Internal Technical Report"],
        ["Version",       "V4.0 — Current Stable Release"],
        ["Report Date",   "June 19, 2026"],
        ["Status",        "Confidential — Internal Use Only"],
    ]
    mt = Table(meta, colWidths=[4.5*cm, 12.5*cm])
    mt.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(0,-1),"Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1),9),
        ("TEXTCOLOR",     (0,0),(0,-1),DARK_TEAL),
        ("TEXTCOLOR",     (1,0),(1,-1),DARK_GREY),
        ("TOPPADDING",    (0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",   (0,0),(-1,-1),10),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[LIGHT_TEAL, WHITE]),
        ("GRID",          (0,0),(-1,-1),0.4,colors.HexColor("#cde8ec")),
    ]))
    story.append(mt)
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Project Team", h2))
    team = [
        [Paragraph("Name", hdr), Paragraph("Role", hdr)],
        [Paragraph("Muhammad Khurram Aimad", cell), Paragraph("Team Lead", cell)],
        [Paragraph("Syed Mudassir Ali",      cell), Paragraph("Main Developer", cell)],
        [Paragraph("Nehal Ansari",           cell), Paragraph("Assistant Developer", cell)],
    ]
    story.append(tbl(team, [8.5*cm, 8.5*cm]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════
    #  PAGE 2 — OVERVIEW + ARCHITECTURE
    # ═══════════════════════════════════════════
    story.append(sec("1.  Executive Summary &amp; Project Overview"))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "The <b>OCR System</b> is an AI-powered platform developed by Al-Khair Institute of Technology "
        "to automate data extraction from Pakistani identity documents (CNIC and Driving License). "
        "The system uses a fine-tuned <b>Donut</b> (Document Understanding Transformer) model to "
        "extract all key fields and automatically populate HTML forms — eliminating manual data entry, "
        "reducing errors, and accelerating document processing. Delivered as a standalone Windows "
        "desktop application, it requires no internet, no GPU, and no external installations on the client machine.",
        body))

    highlights = [
        ["✓ 90.5% field-level accuracy (V4)", "✓ Supports CNIC and Driving License"],
        ["✓ Fills all HTML input types (text, date, number, email)", "✓ Extracts photograph from document"],
        ["✓ Fully offline — no internet required", "✓ Single 871 MB installer EXE"],
    ]
    ht = Table(highlights, colWidths=[8.5*cm, 8.5*cm])
    ht.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),9), ("TEXTCOLOR",(0,0),(-1,-1),DARK_GREY),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),8),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[LIGHT_TEAL, WHITE, LIGHT_TEAL]),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.35*cm))

    story.append(sec("2.  System Architecture &amp; Technology Stack"))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Processing Pipeline", h2))
    pipeline = [
        [Paragraph("Step", hdr), Paragraph("Component", hdr), Paragraph("Description", hdr)],
        [Paragraph("1–2", cell), Paragraph("Image Input", cell),      Paragraph("Accepts JPEG, PNG, WebP, PDF, HEIC. Auto-converts to JPEG.", cell)],
        [Paragraph("3",   cell), Paragraph("Donut Inference", cell),  Paragraph("Fine-tuned transformer reads image → outputs structured JSON with all fields.", cell)],
        [Paragraph("4",   cell), Paragraph("Photo Extraction", cell), Paragraph("OpenCV face detection crops the photograph. Fallback to fixed top-right region.", cell)],
        [Paragraph("5",   cell), Paragraph("Field Matching", cell),   Paragraph("RapidFuzz fuzzy matching maps extracted fields to HTML form inputs.", cell)],
        [Paragraph("6",   cell), Paragraph("Value Formatting", cell), Paragraph("Dates → ISO 8601, numbers → digits only, checkboxes → checked if truthy.", cell)],
        [Paragraph("7",   cell), Paragraph("Form Output", cell),      Paragraph("Filled HTML form saved and viewable in browser or in-app preview panel.", cell)],
    ]
    story.append(tbl(pipeline, [1.2*cm, 3.5*cm, 12.3*cm]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Technology Stack", h2))
    tech = [
        [Paragraph("Category", hdr), Paragraph("Technology", hdr), Paragraph("Notes", hdr)],
        [Paragraph("AI Model",      cell), Paragraph("Donut (naver-clova-ix/donut-base)", cell), Paragraph("Fine-tuned on Pakistani CNIC/DL dataset", cell)],
        [Paragraph("Framework",     cell), Paragraph("PyTorch (CPU) + HuggingFace Transformers 4.46.3", cell), Paragraph("CPU-only — no GPU required on client", cell)],
        [Paragraph("Image",         cell), Paragraph("OpenCV, Pillow, PyMuPDF", cell), Paragraph("Processing, face detection, PDF conversion", cell)],
        [Paragraph("Form Parsing",  cell), Paragraph("BeautifulSoup4 + RapidFuzz", cell), Paragraph("HTML parsing, fuzzy field matching", cell)],
        [Paragraph("UI",            cell), Paragraph("Tkinter (Python built-in)", cell), Paragraph("Desktop GUI, no web server needed", cell)],
        [Paragraph("Packaging",     cell), Paragraph("PyInstaller + Inno Setup 6", cell), Paragraph("871 MB self-contained installer EXE", cell)],
        [Paragraph("Platform",      cell), Paragraph("Windows 10 / 11  (64-bit)", cell), Paragraph("Python 3.11", cell)],
    ]
    story.append(tbl(tech, [3*cm, 7*cm, 7*cm]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════
    #  PAGE 3 — AI MODEL + TRAINING HISTORY
    # ═══════════════════════════════════════════
    story.append(sec("3.  AI Model — Donut"))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "<b>Donut</b> (Document Understanding Transformer) is an end-to-end transformer model that reads "
        "a document image and outputs structured text — with no traditional OCR engine. It uses a "
        "<b>Swin Transformer</b> image encoder and a <b>BART-based decoder</b> to generate structured "
        "JSON directly from the image. This makes it robust to poor image quality, worn cards, and "
        "varying camera angles. The fine-tuned model checkpoint is <b>777 MB</b>, bundled inside the "
        "installer. No download is required on the client machine.",
        body))

    story.append(Paragraph("Why Donut was chosen over traditional OCR + SLM pipeline:", h2))
    reasons = [
        ["End-to-end learning — reads and parses in one step, no separate OCR engine",
         "Robust to poor lighting, camera angles, worn cards"],
        ["Fine-tunable on custom data (Pakistani CNIC/DL)",
         "CPU inference — no GPU required on client"],
        ["Replaces entire OCR + rules + SLM chain with a single model",
         "Structured JSON output — no regex post-processing needed"],
    ]
    rt = Table(reasons, colWidths=[8.5*cm, 8.5*cm])
    rt.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),9), ("TEXTCOLOR",(0,0),(-1,-1),DARK_GREY),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),8),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[LIGHT_GREY, WHITE, LIGHT_GREY]),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cde8ec")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    story.append(rt)
    story.append(Spacer(1, 0.35*cm))

    story.append(sec("4.  Training History &amp; Accuracy"))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "The model was fine-tuned in four iterative rounds on a dataset of <b>1,177 human-reviewed</b> "
        "CNIC and Driving License images (1,001 train / 176 validation). Each round built on the "
        "previous checkpoint. Training used an NVIDIA GeForce RTX 5050 GPU.",
        body))

    train = [
        [Paragraph("Round", hdr), Paragraph("Version", hdr), Paragraph("Accuracy", hdr),
         Paragraph("Key Changes", hdr)],
        [Paragraph("1", cell), Paragraph("V1", cell), Paragraph("0%", cell),
         Paragraph("Model failed to converge — task token format was incorrect.", cell)],
        [Paragraph("2", cell), Paragraph("V2", cell), Paragraph("81.5%", cell),
         Paragraph("Fixed task token format. Model successfully learned document structure.", cell)],
        [Paragraph("3", cell), Paragraph("V3", cell), Paragraph("89.4%", cell),
         Paragraph("Expanded dataset with diverse samples. Improved date field accuracy.", cell)],
        [Paragraph("4", cell), Paragraph("V4  ★", cell), Paragraph("90.5%", cell),
         Paragraph("Further data expansion. Best checkpoint Epoch 1 (val_loss=0.0373). Current stable release.", cell)],
    ]
    tt = Table(train, colWidths=[1.5*cm, 2*cm, 2.5*cm, 11*cm])
    tt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  DARK_TEAL),
        ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("ALIGN",         (0,0), (-1,0),  "CENTER"),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GREY, WHITE, colors.HexColor("#e8f8ee")]),
        ("FONTNAME",      (0,4), (1,4),   "Helvetica-Bold"),
        ("TEXTCOLOR",     (2,4), (2,4),   colors.HexColor("#1a7a4a")),
        ("FONTNAME",      (2,4), (2,4),   "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 9),
        ("TOPPADDING",    (0,0), (-1,-1), 6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#cde8ec")),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(tt)
    story.append(Paragraph("★  V4 is the current stable release shipped to clients.",
        S("cap", fontSize=8, textColor=MID_GREY, alignment=TA_CENTER, spaceBefore=4)))
    story.append(PageBreak())

    # ═══════════════════════════════════════════
    #  PAGE 4 — FEATURES + RESULTS
    # ═══════════════════════════════════════════
    story.append(sec("5.  Features &amp; Capabilities"))
    story.append(Spacer(1, 0.2*cm))

    features = [
        [Paragraph("Area", hdr), Paragraph("Capability", hdr)],
        [Paragraph("Document Support", cell),
         Paragraph("Pakistani CNIC and Driving License  |  JPEG, PNG, WebP, BMP, TIFF, HEIC, GIF, PDF", cell)],
        [Paragraph("Extracted Fields", cell),
         Paragraph("Full Name, Father Name, Gender, ID/License Number, DOB, Date of Issue, "
                   "Date of Expiry, Country, Province, Vehicle Category, Photograph", cell)],
        [Paragraph("Form Filling", cell),
         Paragraph("Fills any HTML form — text, date (ISO conversion), number, email, tel, "
                   "select, radio, checkbox, textarea  |  Fuzzy field-name matching", cell)],
        [Paragraph("UI Features", cell),
         Paragraph("Real-time processing log  |  Extracted fields sidebar  |  'View Extracted Data' "
                   "in-app popup (photo + all fields)  |  Open filled form in browser", cell)],
        [Paragraph("Deployment", cell),
         Paragraph("Fully offline  |  No GPU required  |  No Python/Ollama installs  |  "
                   "Single 871 MB EXE installer  |  Windows 10/11 (64-bit)", cell)],
    ]
    story.append(tbl(features, [3.5*cm, 13.5*cm]))
    story.append(Spacer(1, 0.35*cm))

    story.append(sec("6.  Results &amp; Performance"))
    story.append(Spacer(1, 0.2*cm))

    results = [
        [Paragraph("Metric", hdr), Paragraph("Value", hdr)],
        [Paragraph("Overall field accuracy (V4)", cell),       Paragraph("90.5%", cell)],
        [Paragraph("Total labeled dataset", cell),             Paragraph("1,177 documents  (1,001 train / 176 validation)", cell)],
        [Paragraph("Confidence threshold for review flag", cell), Paragraph("Below 70% → flagged for human verification", cell)],
        [Paragraph("Best validation loss (V4)", cell),         Paragraph("0.0373  (Epoch 1 of 7)", cell)],
        [Paragraph("Inference speed — CPU only", cell),        Paragraph("8–15 seconds per document", cell)],
        [Paragraph("Inference speed — GPU", cell),             Paragraph("2–4 seconds per document", cell)],
        [Paragraph("Installer size", cell),                    Paragraph("871 MB  (self-contained, no internet required)", cell)],
    ]
    story.append(tbl(results, [6*cm, 11*cm]))
    story.append(PageBreak())

    # ═══════════════════════════════════════════
    #  PAGE 5 — TEAM + CONCLUSION
    # ═══════════════════════════════════════════
    story.append(sec("7.  Team Members &amp; Roles"))
    story.append(Spacer(1, 0.2*cm))

    team_detail = [
        [Paragraph("Name", hdr), Paragraph("Role", hdr), Paragraph("Responsibilities", hdr)],
        [Paragraph("Muhammad Khurram Aimad", cell),
         Paragraph("Team Lead", cell),
         Paragraph("Project leadership, technical direction, architecture decisions, "
                   "AI model strategy, fine-tuning roadmap, client requirements, quality assurance.", cell)],
        [Paragraph("Syed Mudassir Ali", cell),
         Paragraph("Main Developer", cell),
         Paragraph("Donut model integration and fine-tuning, training scripts, form-filling engine, "
                   "desktop application, PyInstaller packaging, Inno Setup installer.", cell)],
        [Paragraph("Nehal Ansari", cell),
         Paragraph("Assistant Developer", cell),
         Paragraph("Dataset preparation, image labeling and review, testing and validation, "
                   "UI enhancements, bug verification, and documentation support.", cell)],
    ]
    story.append(tbl(team_detail, [4*cm, 3.5*cm, 9.5*cm]))
    story.append(Spacer(1, 0.4*cm))

    story.append(sec("8.  Conclusion &amp; Future Work"))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "The OCR System successfully delivers a production-ready AI document extraction solution "
        "achieving <b>90.5% field-level accuracy</b> — improved from 0% in Round 1 to a robust "
        "stable release in Round 4 through iterative fine-tuning. The product is delivered as a "
        "self-contained 871 MB Windows installer, immediately deployable in banks, hospitals, "
        "HR departments, and government offices without any client-side setup.",
        body))

    story.append(Paragraph("Future Roadmap", h2))
    future = [
        [Paragraph("Further fine-tuning (2,000–3,000 samples) — target 94–96% accuracy", cell),
         Paragraph("Expansion to Passport, Birth Certificate, Utility Bills", cell)],
        [Paragraph("SaaS web platform with user accounts, billing, and REST API", cell),
         Paragraph("Mobile application for on-device document capture", cell)],
    ]
    ft = Table(future, colWidths=[8.5*cm, 8.5*cm])
    ft.setStyle(TableStyle([
        ("FONTSIZE",(0,0),(-1,-1),9),("TEXTCOLOR",(0,0),(-1,-1),DARK_GREY),
        ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("LEFTPADDING",(0,0),(-1,-1),8),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[LIGHT_TEAL, WHITE]),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cde8ec")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    story.append(ft)
    story.append(Spacer(1, 0.5*cm))

    end = Table([[Paragraph(
        "Al-Khair Institute of Technology (AIT)  ·  OCR System v4.0  ·  Internal Technical Report  ·  June 2026  ·  Confidential",
        S("end", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE, alignment=TA_CENTER))]],
        colWidths=[17*cm])
    end.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),DARK_TEAL),
                              ("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12)]))
    story.append(end)

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    print(f"Report generated: {OUTPUT}")


if __name__ == "__main__":
    build()
