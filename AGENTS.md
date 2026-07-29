# AGENTS.md — bringing an LLM up to speed on pmse-to-wwb

Orientation for an AI assistant (or a new human) picking this project up cold. There is no
`CLAUDE.md` here; this is the entry point.

---

## 1. Read this first: this tool has a successor

This functionality was merged into **`RFutils`** as **Convert › Ofcom PMSE licence**, where
the PDF parser has been **validated against a real Ofcom licence**.

**Before adding a feature here, check whether it belongs in RFutils instead.** This repo is
still a working standalone web app, but RFutils is where the unified suite lives.

## 2. What this is

A small web app that converts an **Ofcom PMSE radio-microphone licence schedule (PDF)** into
files for importing frequencies into **Shure Wireless Workbench**.

Python backend. Public repo.

Context for anyone unfamiliar with the domain: in the UK, PMSE licences allocate specific
radio frequencies for wireless microphone use at a venue or event. Ofcom issues the schedule
as a PDF. Retyping those frequencies into coordination software by hand is slow and
error-prone — hence this tool.

## 3. The format warning that must not be softened

**The WWB `.shw` show-file format is undocumented and reverse-engineered.**

The README tells users to open the output in Wireless Workbench and check it carefully before
relying on it for a real show. Keep that warning, and keep the same posture in new text.

`show_generator.py` is where that reverse-engineered format is written. Treat changes there
as higher-risk than changes to the CSV/text exporters — a malformed `.shw` may load and look
plausible while carrying wrong frequencies, which in this domain means radio-mic
interference at a live event.

## 4. Layout

```
backend/
  main.py             Web app entry point
  parser.py           Ofcom PMSE PDF parsing
  exporters.py        Output formats
  show_generator.py   WWB .shw generation - the reverse-engineered format
  tests/
    pdf_fixture.py    Fixture support for PDF-driven tests
    test_parser.py, test_exporters.py, test_show_generator.py, test_main.py
```

## 5. Working on it

```bash
pytest backend/tests/
```

`pdf_fixture.py` exists so parser tests run against realistic PDF input rather than mocked
text. Use it — a parser test that bypasses PDF extraction doesn't exercise the part most
likely to break when Ofcom changes its layout.

## 6. Conventions

- Public repo. "Commit" means commit **and** push.

## Diagnostics

Log via `diag.log`, not `print`. `diag.init(...)` goes before anything that can fail. Tk
apps must also call `diag.install_tk_excepthook(root)` before any callback can run —
Tkinter swallows callback exceptions, so without it a fault in a button handler never
reaches the crash handler. See [docs/diagnostics.md](docs/diagnostics.md).
