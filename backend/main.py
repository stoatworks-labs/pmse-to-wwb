import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from exporters import suggested_names, to_reference_csv, to_wwb_frequency_list
from parser import parse_pdf
from show_generator import (
    MAX_CHANNELS_PER_RECEIVER,
    ReceiverConfigError,
    UnsupportedBandError,
    generate_show,
)

app = FastAPI(title="PMSE to Wireless Workbench")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # Ofcom schedules are typically <1MB; well clear of that.


@app.get("/", response_class=HTMLResponse)
def index():
    return (FRONTEND_DIR / "index.html").read_text()


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(400, "Please upload a PDF file.")

    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        total = 0
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    413, f"PDF exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit."
                )
            tmp.write(chunk)
        tmp.flush()
        try:
            result = parse_pdf(tmp.name)
        except Exception as exc:
            raise HTTPException(422, f"Could not parse this PDF: {exc}") from exc

    if not result.assignments:
        raise HTTPException(
            422,
            "No frequency assignments were found in this PDF. "
            "It may not be an Ofcom PMSE licence schedule.",
        )

    names = suggested_names(result.assignments)

    return {
        "metadata": {
            "licence_no": result.licence_no,
            "notice_of_variation_no": result.notice_of_variation_no,
            "licensee": result.licensee,
            "licensee_address": result.licensee_address,
            "licence_start": result.licence_start,
            "licence_end": result.licence_end,
            "pmse_ref": result.pmse_ref,
            "licensee_ref": result.licensee_ref,
            "total_assignments": result.total_assignments,
        },
        "warnings": result.warnings,
        "assignment_count": len(result.assignments),
        "assignments": [
            {
                "frequency_mhz": a.frequency_mhz,
                "equipment_type": a.equipment_type,
                "model": a.model,
                "fee_category": a.fee_category,
                "site": a.site,
                "suggested_name": name,
            }
            for a, name in zip(result.assignments, names)
        ],
        "wwb_frequency_list": to_wwb_frequency_list(result.assignments),
        "reference_csv": to_reference_csv(result.assignments),
        "max_channels_per_receiver": MAX_CHANNELS_PER_RECEIVER,
    }


class ChannelIn(BaseModel):
    frequency_mhz: float
    name: str = ""
    band: str = "G56"


class ReceiverIn(BaseModel):
    name: str = ""
    channel_count: int = Field(ge=1, le=MAX_CHANNELS_PER_RECEIVER)
    ip_address: Optional[str] = None
    channels: list[ChannelIn]


class GenerateShowRequest(BaseModel):
    show_name: str = "PMSE Licence Import"
    customer: str = ""
    poc_name: str = ""
    venue_name: str = ""
    venue_address: str = ""
    receivers: list[ReceiverIn]


@app.post("/api/generate-show")
def generate_show_endpoint(payload: GenerateShowRequest):
    receivers = [
        {
            "name": r.name,
            "channel_count": r.channel_count,
            "ip_address": r.ip_address,
            "channels": [
                {"frequency_mhz": c.frequency_mhz, "name": c.name, "band": c.band}
                for c in r.channels
            ],
        }
        for r in payload.receivers
    ]
    try:
        show_file = generate_show(
            receivers,
            show_name=payload.show_name,
            customer=payload.customer,
            poc_name=payload.poc_name,
            venue_name=payload.venue_name,
            venue_address=payload.venue_address,
        )
    except (UnsupportedBandError, ReceiverConfigError) as exc:
        raise HTTPException(422, str(exc)) from exc

    return {"wwb_show_file": show_file}


@app.get("/health")
def health():
    return {"status": "ok"}
