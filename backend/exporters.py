import csv
import io


def suggested_names(assignments) -> list:
    """Generate a channel name per assignment, e.g. ``DSQD-01``.

    Ofcom schedules carry equipment model and type but no channel names, so
    these are invented for convenience and are safe to overwrite — nothing
    downstream depends on the format. Numbering is 1-based and follows the order
    assignments appear in the licence, so it stays stable across a re-parse of
    the same file.
    """
    return [
        f"{a.model or a.equipment_type or 'Ch'}-{i:02d}"
        for i, a in enumerate(assignments, start=1)
    ]


def to_wwb_frequency_list(assignments) -> str:
    """WWB6/7 documented import format: bare MHz values, <=3 decimals,
    one per line, no duplicates, no extra text."""
    seen = set()
    lines = []
    for a in assignments:
        freq = f"{a.frequency_mhz:.3f}"
        if freq in seen:
            continue
        seen.add(freq)
        lines.append(freq)
    return "\n".join(lines) + "\n"


def to_reference_csv(assignments) -> str:
    """Flatten every parsed field to CSV, for the operator's own records.

    Carries far more than the frequency list — site, NGR, power, emission class,
    licence period, fee detail — because this is the human-readable artefact.

    NOT AN IMPORT FORMAT. Nothing consumes it; Wireless Workbench cannot read
    it. ``to_wwb_frequency_list`` is the one output Shure documents as
    importable, and is the safe route into WWB.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
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
    )
    names = suggested_names(assignments)
    for i, (a, suggested_name) in enumerate(zip(assignments, names), start=1):
        writer.writerow(
            [
                i,
                suggested_name,
                f"{a.frequency_mhz:.3f}",
                a.equipment_type,
                a.model,
                a.fee_category,
                a.site,
                a.ngr_transmit,
                a.period_start,
                a.period_end,
                a.restrictions,
            ]
        )
    return buf.getvalue()
