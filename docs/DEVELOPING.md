# pmse-to-wwb — Developing

FastAPI backend, static frontend, Docker packaging.

---

## 1. Read this first: this tool has a successor

The functionality was merged into **[RFutils](https://github.com/allansargeant/RFutils)** as
**Convert › Ofcom PMSE licence**, where **the PDF parser has been validated against a real Ofcom
licence.**

**Before adding a feature here, check whether it belongs in RFutils instead.** This repo is still
a working standalone web app, but RFutils is where the unified suite lives — and the more they
both grow, the more likely a fix lands in only one.

---

## 2. The format warning that must not be softened

> **The WWB `.shw` show-file format is undocumented and reverse-engineered.**

The README tells users to open the output in Wireless Workbench and check it carefully before
relying on it for a real show. **Keep that warning, and keep the same posture in new text.**

`show_generator.py` is where that reverse-engineered format is written.

> **Treat changes there as higher-risk than changes to the CSV/text exporters.** A malformed
> `.shw` may **load and look plausible while carrying wrong frequencies**, which in this domain
> means radio-mic interference at a live event. There is no error to catch — the failure is
> silent and downstream.

### How it works, and why

It **clones real, structurally-verified XML fragments** extracted from a working **WWB7 7.8.1**
show file for a **Shure AD4Q-A quad receiver in the G56 band**, and substitutes only frequency,
name and identity fields. Everything else is copied **verbatim**.

That's a deliberate strategy, not laziness: **unedited boilerplate is far less likely to break
WWB's parser than a hand-built equivalent.** If you find yourself generating a section from
scratch rather than substituting into a captured one, that's a departure from the design and
needs justifying.

Templates live in `backend/templates/` — `skeleton`, `device_shell_ad4q_a`, `channel_ad4q_a`,
`profile_ad4q_a`, `freq_entry_ad4q_a`.

### The parts that are guesses, and are labelled as such

- **The IP address fields.** The real sample **never had a device with a real IP configured**, so
  the `ip_mode`/`ip_address` encoding — packed 32-bit IPv4, `ip_mode=1` for static — is a
  best-effort guess, **not something WWB has been seen to accept.**
- **`MAX_CHANNELS_PER_RECEIVER = 8`** matches the template's `regtx1..8` slots. It is a **sanity
  ceiling from the template**, not a verified hardware limit.
- **`SUPPORTED_BAND = "G56"`** is the only band, because it's the only band the sample covered.
  Supporting another means capturing another real file, not extrapolating.

**Preserve those labels.** They are the difference between a known limit and an assumed one.

---

## 3. Layout

```
backend/
  main.py             FastAPI app — routes, upload limits, request models
  parser.py           Ofcom PMSE PDF parsing (pdfplumber + regexes)
  exporters.py        WWB frequency list + reference CSV
  show_generator.py   WWB .shw generation — THE reverse-engineered format
  templates/          the captured XML fragments
  tests/
    pdf_fixture.py    fixture support for PDF-driven tests
    test_parser.py  test_exporters.py  test_show_generator.py  test_main.py
frontend/index.html   the single-page UI
Dockerfile, docker-compose.yml, render.yaml
```

CI: `.github/workflows/test.yml` and `docker-publish.yml`.

---

## 4. The two output paths have different risk

| Path | Basis | Risk |
|---|---|---|
| `to_wwb_frequency_list()` | **Shure's documented** WWB6/7 import format — bare MHz, ≤ 3 decimals, one per line, de-duplicated | Low. This is the safe default. |
| `to_reference_csv()` | our own format, for humans | None — it isn't imported anywhere |
| `generate_show()` | **reverse-engineered `.shw`** | **High** (§2) |

When adding an export, put it on the right side of that line and say which side it's on.

---

## 5. Parsing

`parser.py` is regex-over-`pdfplumber`. The named patterns — NGR + site, `… MHz`, the fee block,
the licence period — encode the layout of real Ofcom schedules.

Two things a caller depends on:

- **`ParsedLicence.total_assignments` is what the licence claims**, separate from how many
  `Assignment`s were actually built. `/api/convert` returns both, and a mismatch is how a missed
  row becomes visible.
- **`warnings` carries what couldn't be made sense of.** Keep populating it rather than silently
  skipping — a partial parse that reports nothing is indistinguishable from a complete one.

RFutils' port of this parser **has been validated against a real Ofcom licence**; this one was
built from the same material but carries no such claim. Don't restate it as validated.

---

## 6. API behaviour to preserve

- The upload size check happens **while streaming**, so an oversized file is cut off rather than
  buffered into memory.
- **A PDF that parses cleanly but yields zero assignments is a 422**, not an empty 200. That
  distinction is what tells a user they uploaded the wrong document.
- `channel_count` is bounded **1–8 in the Pydantic model**, so it fails as a validation error
  before reaching the generator; band and receiver problems raise `UnsupportedBandError` /
  `ReceiverConfigError` and surface as **422**.
- **There is no authentication** on any endpoint. Licence schedules contain the licensee's name
  and address; a public deployment exposes an upload endpoint to anyone who finds it.

---

## 7. Conventions

Public repo. "Commit" means commit **and** push.

---

## See also

- [API.md](API.md) — endpoints, limits, error codes, the show-file constraints
- [USER-GUIDE.md](USER-GUIDE.md) — the operator view
- [`AGENTS.md`](../AGENTS.md) — LLM onboarding
