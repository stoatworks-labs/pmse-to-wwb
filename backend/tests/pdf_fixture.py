"""Builds a minimal synthetic PDF that mimics the layout of a real Ofcom
PMSE licence schedule closely enough to exercise parser.py's table
extraction and licensee-box cropping, without using any real licensee's
data. Column boundaries and the licensee-box position match parser.py's
assumptions (in particular the (605, 0, width, 130) crop for the licensee
box), since those were reverse-engineered from one real document's layout.
"""

from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)

# Column boundary lines -- 13 lines define the real document's 12 data
# columns (equipment, freq, bandwidth, power, emission, int/ext, signalling,
# polarisation, duplex, ngr/site, period, fee).
COL_X = [40, 120, 195, 235, 275, 335, 375, 405, 435, 470, 640, 730, 820]

HEADERS = [
    "Radio Equipment\n& Specification",
    "Licensed\nFrequency",
    "Band\nwidth",
    "Max\nPower\nerp",
    "Class\nof\nEmission",
    "Internal\nExternal\nAirborne",
    "Signal-\nling",
    "Pol-\narisat-\nion",
    "Duplex\nFrequency\nChannel",
    "NGR / Licensed Area and other Restrictions",
    "Period of Use\nTime, Date",
    "Fee\nCategory\nFee £",
]


def _draw_grid(c, top_y, row_height, n_rows):
    """Draw a ruled grid so pdfplumber's default line-based table
    detector can find it (text position alone isn't enough)."""
    left = COL_X[0]
    right = COL_X[-1]
    bottom_y = top_y - row_height * n_rows
    for x in COL_X:
        c.line(x, top_y, x, bottom_y)
    for i in range(n_rows + 1):
        y = top_y - row_height * i
        c.line(left, y, right, y)


def _draw_row_text(c, y_top, row_height, cells, font_size=6):
    c.setFont("Helvetica", font_size)
    for x, text in zip(COL_X, cells):
        for i, line in enumerate(text.split("\n")):
            c.drawString(x + 2, y_top - 8 - i * (font_size + 1), line)


def build_fixture_pdf(
    path,
    licence_no="9/9999999",
    notice_of_variation_no="0001",
    licensee_name="Test Fixture Productions Ltd",
    licensee_address_lines=("1 Test Street", "TESTVILLE", "TE5 7ST"),
    licence_start="01 Jan 2026",
    licence_end="31 Dec 2026",
    pmse_ref="X000000",
    licensee_ref="Fixture ref",
    frequencies_mhz=(471.375, 471.950, 472.775),
    model="G56",
):
    c = canvas.Canvas(path, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))

    # Licensee box, top-right -- must land inside parser._parse_licensee_box's
    # crop of (605, 0, page.width, 130) in top-down coordinates.
    box_x = 610
    box_top_y = PAGE_HEIGHT - 20
    c.setFont("Helvetica", 8)
    c.drawString(box_x, box_top_y, "Licensee:")
    for i, line in enumerate([licensee_name, *licensee_address_lines]):
        c.drawString(box_x, box_top_y - (i + 1) * 10, line)

    # Main heading / metadata text, kept left of x=605 so it doesn't bleed
    # into the licensee crop.
    c.setFont("Helvetica", 8)
    meta_lines = [
        f"Licence No: {licence_no}   Notice of Variation No: {notice_of_variation_no}   "
        f"Issued: 01 Jan 2026   Total assignments: {len(frequencies_mhz)}   Total fees: £0.00",
        f"Licence Start Date: {licence_start}  Licence End Date: {licence_end}",
        f"Licensee's ref.: {licensee_ref} ; PMSE ref.: {pmse_ref}",
    ]
    for i, line in enumerate(meta_lines):
        c.drawString(40, PAGE_HEIGHT - 40 - i * 12, line)

    # Table: header row + one row per frequency. Kept well below y=130
    # (in pdfplumber's top-down coords) so its header text can't bleed
    # into the licensee-box crop above.
    table_top_y = PAGE_HEIGHT - 160
    row_height = 40
    n_rows = 1 + len(frequencies_mhz)
    _draw_grid(c, table_top_y, row_height, n_rows)
    _draw_row_text(c, table_top_y, row_height, HEADERS)

    for i, freq in enumerate(frequencies_mhz):
        row_y = table_top_y - row_height * (i + 1)
        cells = [
            f"Wireless Microphone\n{model}",
            f"{freq:.5f}\nMHz",
            "200k0",
            "10\nmW",
            "F3E\n-",
            "Internal\n0",
            "-",
            "-",
            "",
            "TQ 123 456 TESTVILLE, Test Venue\n-",
            "00:00, 01 Jan 2026\nto\n23:59, 02 Jan 2026",
            f"21NB1*{i + 1}\n(Normal)\n£0.00",
        ]
        _draw_row_text(c, row_y, row_height, cells)

    c.showPage()
    c.save()
