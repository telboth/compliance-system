"""
Genererer en fiktiv test-faktura som skal trigge sanksjonsscreening.

Scenario:
  Norsk eksportor (NorNav Instruments AS) selger navigasjonsutstyr
  (maritime GPS-mottakere og radarenheter) til et kinesisk selskap
  (Dalian Pacific Trading Co.) som handler pa vegne av en nordkoreansk
  sluttbruker (Korea Maritime Administration, Pyongyang).

  Varene er lisenspliktige under:
    ECCN 7A994 (navigasjonsutstyr, EAR)
    HS 8526.91 (GPS-mottakere)
    HS 9014.10 (kompassutstyr / navigasjonsinstrumenter)

  Destinasjonsland: KP (Nord-Korea) - under FN Sikkerhetsrads-sanksjoner,
  EU FSF, US OFAC og norske sanksjoner.

Filen lagres som test_nordkorea_navigasjon.pdf i prosjektmappen.
"""

from fpdf import FPDF
from pathlib import Path

OUT = Path(__file__).parent / "test_nordkorea_navigasjon.pdf"

# ── Farge-plett ──────────────────────────────────────────────────────────────
DARK_BLUE = (15, 40, 80)
MID_BLUE  = (30, 90, 160)
LIGHT_BG  = (245, 247, 250)
RED_WARN  = (180, 30, 30)
GREY_LINE = (200, 205, 210)

class InvoicePDF(FPDF):
    def header(self):
        pass  # Manuell header nedenfor

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, "STRICTLY CONFIDENTIAL - Export-controlled goods. "
                  "Subject to Norwegian Export Control Regulations and EAR.",
                  align="C")

def h_line(pdf, r=None, g=None, b=None, lw=0.3):
    if r is not None:
        pdf.set_draw_color(r, g, b)
    pdf.set_line_width(lw)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(1)

pdf = InvoicePDF(orientation="P", unit="mm", format="A4")
pdf.set_auto_page_break(auto=True, margin=16)
pdf.add_page()
pdf.set_margins(12, 10, 12)

# ═══════════════════════════════════════════════════════════════
# HEADER - logo-blokk
# ═══════════════════════════════════════════════════════════════
pdf.set_fill_color(*DARK_BLUE)
pdf.rect(0, 0, 210, 28, "F")

pdf.set_font("Helvetica", "B", 16)
pdf.set_text_color(255, 255, 255)
pdf.set_xy(12, 7)
pdf.cell(120, 8, "NorNav Instruments AS", ln=0)

pdf.set_font("Helvetica", "", 8)
pdf.set_xy(12, 16)
pdf.cell(120, 4, "Navigasjonsvn. 14  |  4085 Hundvag, Norway  |  Org.nr. 987 654 321", ln=0)

# Faktura-tittel hoyre
pdf.set_font("Helvetica", "B", 22)
pdf.set_text_color(200, 220, 255)
pdf.set_xy(130, 5)
pdf.cell(68, 12, "COMMERCIAL INVOICE", align="R", ln=0)

pdf.set_font("Helvetica", "", 8)
pdf.set_text_color(180, 200, 240)
pdf.set_xy(130, 17)
pdf.cell(68, 4, "ORIGINAL", align="R", ln=0)

pdf.set_y(32)

# ═══════════════════════════════════════════════════════════════
# REF-BLOKK  (Invoice no, date, PO, terms)
# ═══════════════════════════════════════════════════════════════
pdf.set_fill_color(*LIGHT_BG)
pdf.rect(12, 32, 186, 18, "F")

fields = [
    ("Invoice No.:",    "NNI-20241118KP-E04"),
    ("Invoice Date:",   "18 November 2024"),
    ("PO / Order No.:", "DPT-2024-8831"),
    ("Payment Terms:",  "30 days net / T/T"),
    ("Currency:",       "USD"),
]
pdf.set_font("Helvetica", "B", 8)
pdf.set_text_color(*DARK_BLUE)
col_w = 186 / len(fields)
for i, (label, value) in enumerate(fields):
    x = 12 + i * col_w
    pdf.set_xy(x, 34)
    pdf.cell(col_w - 1, 4, label, ln=0)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_xy(x, 38.5)
    pdf.cell(col_w - 1, 4, value, ln=0)
    pdf.set_font("Helvetica", "B", 8)

pdf.set_y(54)

# ═══════════════════════════════════════════════════════════════
# PARTER  (Seller | Buyer | Consignee / End-User)
# ═══════════════════════════════════════════════════════════════
pdf.set_font("Helvetica", "B", 9)
pdf.set_text_color(*MID_BLUE)

BOX_TOP = 54
BOX_H   = 36
COL1_X  = 12
COL2_X  = 78
COL3_X  = 143

def party_box(pdf, x, y, w, title, lines):
    pdf.set_fill_color(*LIGHT_BG)
    pdf.set_draw_color(*GREY_LINE)
    pdf.set_line_width(0.2)
    pdf.rect(x, y, w, BOX_H, "FD")
    pdf.set_xy(x + 2, y + 2)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*MID_BLUE)
    pdf.cell(w - 4, 4, title.upper(), ln=1)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(40, 40, 40)
    for line in lines:
        pdf.set_xy(x + 2, pdf.get_y())
        pdf.cell(w - 4, 3.8, line, ln=1)

party_box(pdf, COL1_X, BOX_TOP, 62, "Seller / Exporter",
    ["NorNav Instruments AS",
     "Navigasjonsvn. 14",
     "4085 Hundvag",
     "NORWAY",
     "VAT: NO987654321MVA",
     "contact@nornav.no"])

party_box(pdf, COL2_X, BOX_TOP, 62, "Buyer / Invoice To",
    ["Dalian Pacific Trading Co., Ltd.",
     "No. 88 Gangwan Street",
     "Dalian, Liaoning 116011",
     "CHINA (PRC)",
     "Contact: Mr. Chen Wei",
     "chen.wei@dalianpacific.cn"])

party_box(pdf, COL3_X, BOX_TOP, 55, "Consignee / End-User",
    ["Korea Maritime Administration",
     "Ryugyong-dong, Potonggang",
     "Pyongyang",
     "DEMOCRATIC PEOPLE'S",
     "REPUBLIC OF KOREA (KP)",
     "Attn: Capt. Kim Sung-il"])

pdf.set_y(BOX_TOP + BOX_H + 4)

# ═══════════════════════════════════════════════════════════════
# SHIPPING  (Incoterms, transport, destination)
# ═══════════════════════════════════════════════════════════════
pdf.set_fill_color(*MID_BLUE)
pdf.set_text_color(255, 255, 255)
pdf.set_font("Helvetica", "B", 8)
pdf.rect(12, pdf.get_y(), 186, 6, "F")
pdf.set_xy(14, pdf.get_y() + 1)
ship_fields = [
    ("Incoterms:", "CIP Nampo Port, DPRK"),
    ("Transport:", "Sea Freight"),
    ("Port of Loading:", "Stavanger, Norway"),
    ("Port of Discharge:", "Nampo, DPRK"),
    ("Destination Country:", "KP - North Korea"),
]
cw = 186 / len(ship_fields)
for i, (lbl, val) in enumerate(ship_fields):
    pdf.set_xy(14 + i * cw, pdf.get_y())
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(cw / 2, 4, lbl, ln=0)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(cw / 2, 4, val, ln=0)

pdf.ln(8)

# ═══════════════════════════════════════════════════════════════
# LINJE-TABELL
# ═══════════════════════════════════════════════════════════════
COLS = [
    ("Line", 8,  "C"),
    ("Description of Goods", 62, "L"),
    ("Model / Part No.", 28, "L"),
    ("HS Code", 20, "C"),
    ("ECCN", 14, "C"),
    ("Qty", 9,  "R"),
    ("UoM", 10, "C"),
    ("Unit Price\nUSD", 18, "R"),
    ("Total\nUSD", 17, "R"),
]
COL_XS = []
x = 12
for _, w, _ in COLS:
    COL_XS.append(x)
    x += w

# Header
pdf.set_fill_color(*DARK_BLUE)
pdf.set_text_color(255, 255, 255)
pdf.set_font("Helvetica", "B", 7.5)
row_y = pdf.get_y()
max_hdr_h = 8
pdf.rect(12, row_y, 186, max_hdr_h, "F")
for i, (title, w, align) in enumerate(COLS):
    pdf.set_xy(COL_XS[i] + 1, row_y + 0.5)
    pdf.multi_cell(w - 2, 3.5, title, align=align, border=0)
pdf.set_y(row_y + max_hdr_h)

# Data rows
LINES = [
    (1,
     "Maritime GPS Navigation Receiver, IMO-certified,\n"
     "dual-frequency L1/L2, GLONASS/GPS, IP67, with\n"
     "AIS integration module",
     "NNI-GPS-2400M",
     "8526.91.20", "7A994", 6, "pcs", 18_500, 111_000),
    (2,
     "Solid-State Marine Radar System, X-band 9 GHz,\n"
     "48 NM range, IMO MSC.192(79) compliant,\n"
     "including antenna, display unit and power supply",
     "NNI-RAD-X48S",
     "8526.10.00", "7A994", 3, "sets", 42_800, 128_400),
    (3,
     "Inertial Navigation System (INS), fibre-optic\n"
     "gyroscope, 0.01 deg/hr bias stability,\n"
     "MIL-STD-810G, with installation kit",
     "NNI-INS-FOG3",
     "9014.10.90", "7A001", 3, "sets", 31_200,  93_600),
    (4,
     "Electronic Chart Display and Information System\n"
     "(ECDIS), IHO S-52/S-57, SOLAS compliant,\n"
     "including 24\" high-brightness display",
     "NNI-ECDIS-24P",
     "9014.80.00", "EAR99", 6, "pcs",  9_750,  58_500),
    (5,
     "Spare Parts Kit for NNI-GPS-2400M and\n"
     "NNI-RAD-X48S (2-year service pack), including\n"
     "circuit boards, connectors, fuses, manuals",
     "NNI-SPARE-KIT2",
     "8529.90.92", "EAR99", 2, "kits", 4_200,   8_400),
]

pdf.set_font("Helvetica", "", 7.5)
for idx, (line_no, desc, model, hs, eccn, qty, uom, unit, total) in enumerate(LINES):
    row_y = pdf.get_y()
    fill = idx % 2 == 0
    if fill:
        pdf.set_fill_color(*LIGHT_BG)
    else:
        pdf.set_fill_color(255, 255, 255)

    # Mal hoyden ved a telle linjeskift i description
    n_lines = desc.count("\n") + 1
    row_h = max(n_lines * 3.8 + 2, 11)

    pdf.rect(12, row_y, 186, row_h, "F")
    pdf.set_text_color(30, 30, 30)

    cells = [
        str(line_no),
        desc,
        model,
        hs,
        eccn,
        str(qty),
        uom,
        f"{unit:,.0f}",
        f"{total:,.0f}",
    ]
    for i, (text, (_, w, align)) in enumerate(zip(cells, COLS)):
        pdf.set_xy(COL_XS[i] + 1, row_y + 1)
        pdf.multi_cell(w - 2, 3.8, text, align=align, border=0)
    pdf.set_y(row_y + row_h)

# Separator
h_line(pdf, *GREY_LINE)

# ═══════════════════════════════════════════════════════════════
# SUMMER / TOTALS (hoyrejustert)
# ═══════════════════════════════════════════════════════════════
SUBTOTAL = 111_000 + 128_400 + 93_600 + 58_500 + 8_400   # 399 900
FREIGHT   =   4_800
INSURANCE =   1_200
TOTAL_USD = SUBTOTAL + FREIGHT + INSURANCE                 # 405 900
VAT_RATE  = 0   # Eksport - 0% MVA
VAT_AMT   = 0

sum_rows = [
    ("Subtotal (goods):", f"USD {SUBTOTAL:>12,.2f}"),
    ("Ocean Freight (CIP):", f"USD {FREIGHT:>12,.2f}"),
    ("Insurance (CIP):", f"USD {INSURANCE:>12,.2f}"),
    ("VAT / Moms (0 % - export):", f"USD {VAT_AMT:>12,.2f}"),
]
pdf.ln(1)
for label, amount in sum_rows:
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(60, 60, 60)
    pdf.set_x(130)
    pdf.cell(48, 5, label, align="R", ln=0)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(20, 5, amount, align="R", ln=1)

# Total-linje
pdf.set_fill_color(*DARK_BLUE)
pdf.set_text_color(255, 255, 255)
pdf.set_font("Helvetica", "B", 9)
pdf.set_x(130)
pdf.cell(68, 7, f"TOTAL AMOUNT DUE:   USD {TOTAL_USD:>10,.2f}", align="R",
         fill=True, ln=1)

pdf.ln(2)

# ═══════════════════════════════════════════════════════════════
# EXPORT CONTROL / INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════
pdf.set_font("Helvetica", "B", 8)
pdf.set_text_color(*MID_BLUE)
pdf.cell(0, 5, "Export Control Classification & Instructions", ln=1)
h_line(pdf, *MID_BLUE, lw=0.5)

pdf.set_font("Helvetica", "", 7.5)
pdf.set_text_color(30, 30, 30)
instructions = (
    "These goods are subject to Norwegian export control regulations (Forskrift om eksport av "
    "forsvarsmateriell, 2013) and the U.S. Export Administration Regulations (EAR, 15 CFR 730-774). "
    "Export, re-export or transfer without prior written authorisation from the Norwegian Ministry of "
    "Foreign Affairs and, where applicable, the U.S. Bureau of Industry and Security (BIS) is strictly "
    "prohibited.\n\n"
    "ECCN classifications: 7A994 (GPS receiver, radar system) | 7A001 (INS) | EAR99 (ECDIS, spare parts). "
    "HS codes verified per Norwegian Customs Tariff 2024. Country of origin: NORWAY.\n\n"
    "The buyer and end-user confirm that the goods will be used solely for the stated civilian maritime "
    "navigation purposes and will not be diverted, re-exported or used for any military, WMD or "
    "prohibited end-use without obtaining all required licences. Violation may result in criminal "
    "prosecution under Norwegian Penal Code s. 133 and U.S. law."
)
pdf.multi_cell(0, 3.8, instructions)

pdf.ln(2)

# ═══════════════════════════════════════════════════════════════
# SIGNATUR / DECLARATIONS
# ═══════════════════════════════════════════════════════════════
pdf.set_font("Helvetica", "B", 8)
pdf.set_text_color(*MID_BLUE)
pdf.cell(0, 5, "Certification & Authorised Signature", ln=1)
h_line(pdf, *MID_BLUE, lw=0.5)

pdf.set_font("Helvetica", "", 7.5)
pdf.set_text_color(30, 30, 30)
pdf.multi_cell(0, 3.8,
    "I, the undersigned, declare that the information in this invoice is true and correct "
    "and that all goods comply with the requirements of the importing country.")

pdf.ln(4)
sig_y = pdf.get_y()
pdf.set_draw_color(*GREY_LINE)
pdf.line(12, sig_y + 10, 85, sig_y + 10)
pdf.line(100, sig_y + 10, 170, sig_y + 10)
pdf.set_font("Helvetica", "", 7.5)
pdf.set_xy(12, sig_y + 11)
pdf.cell(73, 4, "Signature / Date: Stavanger, 18.11.2024", ln=0)
pdf.set_xy(100, sig_y + 11)
pdf.cell(70, 4, "Name / Title: Lars Eriksen, Export Manager", ln=0)

# ═══════════════════════════════════════════════════════════════
# BANK / PAYMENT DETAILS
# ═══════════════════════════════════════════════════════════════
pdf.set_y(sig_y + 20)
pdf.set_fill_color(*LIGHT_BG)
pdf.rect(12, pdf.get_y(), 186, 18, "F")
pdf.set_xy(14, pdf.get_y() + 2)
pdf.set_font("Helvetica", "B", 8)
pdf.set_text_color(*DARK_BLUE)
pdf.cell(0, 4, "Bank / Payment Details", ln=1)
pdf.set_font("Helvetica", "", 7.5)
pdf.set_text_color(30, 30, 30)
bank_info = [
    ("Bank:", "DNB Bank ASA, Bjergsted, 4007 Stavanger, Norway"),
    ("Account Name:", "NorNav Instruments AS"),
    ("IBAN:", "NO93 1503 0000 0000"),
    ("SWIFT/BIC:", "DNBANOKKXXX"),
    ("Reference:", "NNI-20241118KP-E04 / DPT-2024-8831"),
]
for lbl, val in bank_info:
    pdf.set_x(14)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.cell(30, 3.5, lbl, ln=0)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(0, 3.5, val, ln=1)

pdf.output(str(OUT))
print(f"Generert: {OUT}")
print(f"Storrelse: {OUT.stat().st_size / 1024:.1f} kB")
