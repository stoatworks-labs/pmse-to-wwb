import csv
import io


def suggested_names(assignments) -> list:
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
