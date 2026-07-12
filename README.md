# PMSE Licence → Wireless Workbench

A small web app that converts an Ofcom PMSE radio microphone licence schedule (PDF) into files
for importing frequencies into Shure Wireless Workbench.

## AI disclosure

**This project was built with the help of AI (Claude, by Anthropic)**, working interactively with
the repository owner. AI wrote the majority of the code, including the PDF parser, the WWB export
logic, and the experimental show-file generator. It was directed and reviewed by a human throughout,
but the code has not been independently audited, and the WWB `.shw` show-file format in particular
is an undocumented, reverse-engineered format — see the warning below before relying on it.

If you're evaluating this code (for security, correctness, or anything else), treat it as
AI-assisted rather than fully hand-reviewed production software.

## What it does

Upload an Ofcom PMSE licence schedule PDF and the app generates:

- **WWB frequency list** (`.txt`) — a bare list of licensed frequencies in Shure's documented
  import format (MHz, ≤3 decimals, one per line). This is the safe, standards-based option:
  import it into WWB via *Import frequencies from file*.
- **Reference sheet** (`.csv`) — maps each frequency to a suggested channel name and its Ofcom
  coordination/fee group, since the licence itself has no per-mic names. Use it to manually label
  channels in WWB.
- **WWB7 show file** (`.shw`, **experimental**) — a native Wireless Workbench show file with
  channels already named and frequencies already assigned, simulating Shure AD4Q-A quad receivers.
  Shure does not publish this file format; it was reverse-engineered from a real working show file
  and has not been validated by Shure. **Open it in WWB and check it carefully before relying on it
  for a real show.**

## Running locally

```
python3 -m venv venv
./venv/bin/pip install -r backend/requirements.txt
./venv/bin/uvicorn main:app --reload --port 8420 --app-dir backend
```

Then open http://localhost:8420.

## Deploying

The repo includes a `Dockerfile` and `render.yaml` for deploying to [Render](https://render.com)
via its Blueprint feature (New → Blueprint, pick this repo).
