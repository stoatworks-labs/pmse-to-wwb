import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import _parse_metadata, ParsedLicence, parse_pdf

from pdf_fixture import build_fixture_pdf


def test_parse_metadata_from_text():
    result = ParsedLicence()
    text = (
        "Licence No: 1/2345678 Notice of Variation No: 0012 Issued: 05 May 2026 "
        "Total assignments: 42 Total fees: £10.00\n"
        "Licence Start Date: 01 Jun 2026 Licence End Date: 31 May 2027\n"
        "Licensee's ref.: Some Ref 123 ; PMSE ref.: J123456\n"
    )
    _parse_metadata(text, result)
    assert result.licence_no == "1/2345678"
    assert result.notice_of_variation_no == "0012"
    assert result.total_assignments == 42
    assert result.licence_start == "01 Jun 2026"
    assert result.licence_end == "31 May 2027"
    assert result.pmse_ref == "J123456"
    assert result.licensee_ref == "Some Ref 123"


def test_parse_pdf_fixture(tmp_path):
    pdf_path = tmp_path / "fixture.pdf"
    build_fixture_pdf(
        str(pdf_path),
        licence_no="1/1111111",
        notice_of_variation_no="0005",
        licensee_name="Fixture Co Ltd",
        licensee_address_lines=("42 Fixture Way", "FIXTONIA", "FX1 1FX"),
        frequencies_mhz=(471.375, 500.125, 634.775),
        model="G56",
    )

    result = parse_pdf(str(pdf_path))

    assert result.licence_no == "1/1111111"
    assert result.notice_of_variation_no == "0005"
    assert result.licensee == "Fixture Co Ltd"
    assert "42 Fixture Way" in result.licensee_address
    assert result.total_assignments == 3
    assert result.warnings == []

    assert len(result.assignments) == 3
    freqs = [a.frequency_mhz for a in result.assignments]
    assert freqs == [471.375, 500.125, 634.775]
    for a in result.assignments:
        assert a.model == "G56"
        assert a.equipment_type == "Wireless Microphone"
        assert a.ngr_transmit == "TQ 123 456"


def test_parse_pdf_no_assignments_warns(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    build_fixture_pdf(str(pdf_path), frequencies_mhz=())

    result = parse_pdf(str(pdf_path))

    assert result.assignments == []
    assert result.warnings
    assert "No frequency assignments" in result.warnings[0]
