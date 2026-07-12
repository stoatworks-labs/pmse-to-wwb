import csv
import io


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
    group_seq = {}
    for i, a in enumerate(assignments, start=1):
        group_seq[a.fee_category] = group_seq.get(a.fee_category, 0) + 1
        model_part = a.model or a.equipment_type or "Ch"
        suggested_name = f"{model_part}-{i:02d}"
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
