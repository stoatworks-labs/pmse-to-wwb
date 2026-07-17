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
    assert data["wwb_show_file"] is not None
    assert data["warnings"] == []


def test_convert_omits_show_file_for_unsupported_band(tmp_path):
    pdf_path = tmp_path / "fixture_other_band.pdf"
    build_fixture_pdf(str(pdf_path), frequencies_mhz=(700.125,), model="H50")

    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/convert",
            files={"file": ("fixture.pdf", f, "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["wwb_show_file"] is None
    assert any("H50" in w for w in data["warnings"])


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
