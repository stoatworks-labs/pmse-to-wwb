import re
from dataclasses import dataclass, field

import pdfplumber

NGR_SITE_RE = re.compile(r"^([A-Z]{2}\s?\d{3}\s?\d{3})\s+(.*)$")
FREQ_RE = re.compile(r"([\d.]+)\s*MHz")
FEE_RE = re.compile(r"([A-Z0-9*]+)\s*\n?\(([^)]+)\)\s*\n?£?([\d.]+)")
PERIOD_RE = re.compile(
    r"([\d:]+),\s*([\d]+\s+\w+\s+[\d]+)\s*\nto\s*\n([\d:]+),\s*([\d]+\s+\w+\s+[\d]+)",
    re.MULTILINE,
)


@dataclass
class Assignment:
    equipment_type: str
    model: str
    frequency_mhz: float
    bandwidth: str
    max_power: str
    emission_class: str
    ngr_transmit: str
    site: str
    restrictions: str
    period_start: str
    period_end: str
    fee_category: str
    fee_type: str
    fee_amount: str


@dataclass
class ParsedLicence:
    licence_no: str = ""
    notice_of_variation_no: str = ""
    licensee: str = ""
    licensee_address: str = ""
    licence_start: str = ""
    licence_end: str = ""
    pmse_ref: str = ""
    licensee_ref: str = ""
    total_assignments: int = 0
    assignments: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _clean(cell):
    return (cell or "").replace("\n", " ").strip()


def _parse_metadata(page_text: str, result: ParsedLicence):
    m = re.search(r"Licence No:\s*([\w/]+)", page_text)
    if m:
        result.licence_no = m.group(1)
    m = re.search(r"Notice of Variation No:\s*(\d+)", page_text)
    if m:
        result.notice_of_variation_no = m.group(1)
    m = re.search(r"Total assignments:\s*(\d+)", page_text)
    if m:
        result.total_assignments = int(m.group(1))
    m = re.search(r"Licence Start Date:\s*([\d]+\s+\w+\s+[\d]+)", page_text)
    if m:
        result.licence_start = m.group(1)
    m = re.search(r"Licence End Date:\s*([\d]+\s+\w+\s+[\d]+)", page_text)
    if m:
        result.licence_end = m.group(1)
    m = re.search(r"PMSE ref\.?:\s*(\S+)", page_text)
    if m:
        result.pmse_ref = m.group(1)
    m = re.search(r"Licensee.s ref\.?:\s*(.+?)\s*;\s*PMSE", page_text)
    if m:
        result.licensee_ref = m.group(1).strip()


def _parse_licensee_box(page) -> tuple:
    """The licensee name/address sits in a box in the top-right corner of
    the first schedule page. Plain text extraction interleaves it with the
    main paragraph because they share vertical bands, so crop by position
    instead. Returns (name, address)."""
    box = page.crop((605, 0, page.width, 130))
    text = box.extract_text() or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    lines = [l for l in lines if l != "Licensee:"]
    if not lines:
        return "", ""
    return lines[0], ", ".join(lines[1:])


def parse_pdf(path: str) -> ParsedLicence:
    result = ParsedLicence()
    with pdfplumber.open(path) as pdf:
        if pdf.pages:
            _parse_metadata(pdf.pages[0].extract_text() or "", result)

        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if not result.licence_no:
                _parse_metadata(page_text, result)
            if not result.licensee and "Licensee:" in page_text:
                result.licensee, result.licensee_address = _parse_licensee_box(page)

            for table in page.find_tables():
                rows = table.extract()
                if not rows:
                    continue
                header_cells = [(_clean(c)) for c in rows[0]]
                if "Radio Equipment" not in " ".join(header_cells) and len(rows) > 0:
                    # find the header row within this table instead of assuming row 0
                    header_idx = None
                    for i, r in enumerate(rows):
                        joined = " ".join(_clean(c) for c in r)
                        if "Radio Equipment" in joined:
                            header_idx = i
                            break
                    if header_idx is None:
                        continue
                    data_rows = rows[header_idx + 1 :]
                else:
                    data_rows = rows[1:]

                for row in data_rows:
                    if row is None or len(row) < 12:
                        continue
                    col0 = row[0] or ""
                    freq_match = FREQ_RE.search(row[1] or "")
                    if not freq_match:
                        continue
                    equip_lines = [l.strip() for l in col0.splitlines() if l.strip()]
                    equipment_type = equip_lines[0] if equip_lines else ""
                    model = equip_lines[1] if len(equip_lines) > 1 else ""

                    ngr_site_raw = row[9] or ""
                    site_lines = [l for l in ngr_site_raw.splitlines() if l.strip()]
                    ngr = ""
                    site = ""
                    restrictions = ""
                    if site_lines:
                        m = NGR_SITE_RE.match(site_lines[0].strip())
                        if m:
                            ngr, site = m.group(1), m.group(2)
                        else:
                            site = site_lines[0].strip()
                        extra = [
                            l.strip()
                            for l in site_lines[1:]
                            if l.strip() and l.strip() != "-"
                        ]
                        restrictions = " ".join(extra)

                    period_start = period_end = ""
                    pm = PERIOD_RE.search(row[10] or "")
                    if pm:
                        period_start = f"{pm.group(1)} {pm.group(2)}"
                        period_end = f"{pm.group(3)} {pm.group(4)}"

                    fee_category = fee_type = fee_amount = ""
                    fm = FEE_RE.search(row[11] or "")
                    if fm:
                        fee_category, fee_type, fee_amount = fm.groups()

                    result.assignments.append(
                        Assignment(
                            equipment_type=equipment_type,
                            model=model,
                            frequency_mhz=round(float(freq_match.group(1)), 3),
                            bandwidth=_clean(row[2]),
                            max_power=_clean(row[3]),
                            emission_class=_clean(row[4]).split(" ")[0]
                            if row[4]
                            else "",
                            ngr_transmit=ngr,
                            site=site,
                            restrictions=restrictions,
                            period_start=period_start,
                            period_end=period_end,
                            fee_category=fee_category,
                            fee_type=fee_type,
                            fee_amount=fee_amount,
                        )
                    )

    if not result.assignments:
        result.warnings.append(
            "No frequency assignments could be found in this PDF. "
            "It may not be an Ofcom PMSE schedule, or its layout is unrecognized."
        )
    elif result.total_assignments and len(result.assignments) != result.total_assignments:
        result.warnings.append(
            f"PDF header states {result.total_assignments} assignments but "
            f"{len(result.assignments)} were parsed. Please verify the output before use."
        )

    return result
