import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from exporters import to_reference_csv, to_wwb_frequency_list
from parser import parse_pdf

app = FastAPI(title="PMSE to Wireless Workbench")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    return (FRONTEND_DIR / "index.html").read_text()


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(400, "Please upload a PDF file.")

    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        contents = await file.read()
        tmp.write(contents)
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
            }
            for a in result.assignments
        ],
        "wwb_frequency_list": to_wwb_frequency_list(result.assignments),
        "reference_csv": to_reference_csv(result.assignments),
    }


@app.get("/health")
def health():
    return {"status": "ok"}
