import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from main import app
from pdf_fixture import build_fixture_pdf

client = TestClient(app)


def test_rejects_non_pdf_upload():
    resp = client.post(
        "/api/convert",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_convert_happy_path(tmp_path):
    pdf_path = tmp_path / "fixture.pdf"
    build_fixture_pdf(str(pdf_path), frequencies_mhz=(471.375, 500.0), model="G56")

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/convert",
            files={"file": ("fixture.pdf", f, "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["assignment_count"] == 2
    assert "471.375" in data["wwb_frequency_list"]
    assert data["warnings"] == []
    assert data["max_channels_per_receiver"] >= 4
    assert all(a["suggested_name"] for a in data["assignments"])


def test_convert_does_not_reject_other_bands(tmp_path):
    """/api/convert just parses -- band support is only enforced at
    /api/generate-show time, since the frequency list/reference sheet
    outputs work for any band."""
    pdf_path = tmp_path / "fixture_other_band.pdf"
    build_fixture_pdf(str(pdf_path), frequencies_mhz=(700.125,), model="H50")

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/convert",
            files={"file": ("fixture.pdf", f, "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["assignments"][0]["model"] == "H50"


def test_convert_rejects_oversized_upload(monkeypatch):
    import main

    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    resp = client.post(
        "/api/convert",
        files={"file": ("big.pdf", b"x" * 1000, "application/pdf")},
    )
    assert resp.status_code == 413


def test_convert_rejects_empty_pdf(tmp_path):
    pdf_path = tmp_path / "no_assignments.pdf"
    build_fixture_pdf(str(pdf_path), frequencies_mhz=())

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/convert",
            files={"file": ("fixture.pdf", f, "application/pdf")},
        )

    assert resp.status_code == 422


def _receiver(name="Rack 1", channel_count=4, ip_address=None, channels=None):
    return {
        "name": name,
        "channel_count": channel_count,
        "ip_address": ip_address,
        "channels": channels or [{"frequency_mhz": 471.375, "name": "Ch1", "band": "G56"}],
    }


def test_generate_show_happy_path():
    resp = client.post(
        "/api/generate-show",
        json={"show_name": "Test Show", "receivers": [_receiver(ip_address="192.168.1.101")]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["wwb_show_file"]
    assert "192.168.1.101" not in data["wwb_show_file"]  # stored packed, not as dotted-quad text


def test_generate_show_rejects_unsupported_band():
    resp = client.post(
        "/api/generate-show",
        json={
            "receivers": [
                _receiver(channels=[{"frequency_mhz": 700.0, "name": "Ch1", "band": "H50"}])
            ]
        },
    )
    assert resp.status_code == 422
    assert "H50" in resp.json()["detail"]


def test_generate_show_rejects_over_capacity():
    resp = client.post(
        "/api/generate-show",
        json={
            "receivers": [
                _receiver(
                    channel_count=1,
                    channels=[
                        {"frequency_mhz": 471.0, "name": "Ch1", "band": "G56"},
                        {"frequency_mhz": 472.0, "name": "Ch2", "band": "G56"},
                    ],
                )
            ]
        },
    )
    assert resp.status_code == 422


def test_generate_show_rejects_channel_count_out_of_pydantic_range():
    resp = client.post(
        "/api/generate-show",
        json={"receivers": [_receiver(channel_count=0)]},
    )
    assert resp.status_code == 422
