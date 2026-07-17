import csv
import io
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from exporters import suggested_names, to_reference_csv, to_wwb_frequency_list


@dataclass
class FakeAssignment:
    frequency_mhz: float
    model: str = "G56"
    equipment_type: str = "Wireless Microphone"
    fee_category: str = "21NB1*1"
    site: str = "Test Venue"
    ngr_transmit: str = "TQ 123 456"
    period_start: str = "00:00 01 Jan 2026"
    period_end: str = "23:59 02 Jan 2026"
    restrictions: str = ""


def test_suggested_names_are_sequential_and_use_model():
    assignments = [FakeAssignment(471.0, model="G56") for _ in range(3)]
    names = suggested_names(assignments)
    assert names == ["G56-01", "G56-02", "G56-03"]


def test_suggested_names_falls_back_to_equipment_type():
    a = FakeAssignment(471.0, model="")
    a.equipment_type = "Wireless Microphone"
    assert suggested_names([a]) == ["Wireless Microphone-01"]


def test_wwb_frequency_list_formats_three_decimals():
    assignments = [FakeAssignment(471.375), FakeAssignment(500.0)]
    out = to_wwb_frequency_list(assignments)
    lines = out.strip().splitlines()
    assert lines == ["471.375", "500.000"]


def test_wwb_frequency_list_deduplicates():
    assignments = [FakeAssignment(471.375), FakeAssignment(471.375), FakeAssignment(472.0)]
    out = to_wwb_frequency_list(assignments)
    lines = out.strip().splitlines()
    assert lines == ["471.375", "472.000"]


def test_reference_csv_has_expected_columns_and_rows():
    assignments = [FakeAssignment(471.375, fee_category="21NB1*1"), FakeAssignment(472.0, fee_category="21NB1*2")]
    csv_text = to_reference_csv(assignments)
    rows = list(csv.reader(io.StringIO(csv_text)))

    assert rows[0] == [
        "Index",
        "Suggested Name",
        "Frequency (MHz)",
        "Equipment Type",
        "Model",
        "Coordination/Fee Group",
        "Site",
        "NGR",
        "Period Start",
        "Period End",
        "Restrictions",
    ]
    assert rows[1][0:3] == ["1", "G56-01", "471.375"]
    assert rows[2][0:3] == ["2", "G56-02", "472.000"]
