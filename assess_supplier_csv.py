import argparse
import csv
import json
from pathlib import Path

from scope3_freight import assess_declaration, train_freight_model


def assess_csv(path):
    groups = {"train": [], "holdout": [], "review": []}
    seen_ids = set()
    periods = {}
    required = {"record_id", "split", "tonne_km", "declared_kg_co2e"}

    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        if not required.issubset(rows.fieldnames or []):
            raise ValueError("CSV must contain record_id, split, tonne_km, and declared_kg_co2e")

        for row in rows:
            record_id = (row["record_id"] or "").strip()
            split = (row["split"] or "").strip()
            if not record_id or record_id in seen_ids:
                raise ValueError(f"Line {rows.line_num}: record ID is missing or duplicated")
            if split not in groups:
                raise ValueError(f"Line {rows.line_num}: split must be train, holdout, or review")

            seen_ids.add(record_id)
            start = (row.get("period_start_utc") or "").strip()
            end = (row.get("period_end_utc") or "").strip()
            if bool(start) != bool(end):
                raise ValueError(f"Line {rows.line_num}: provide both reporting dates")
            periods[record_id] = (
                {"period_start_utc": start, "period_end_utc": end} if start else {}
            )
            groups[split].append((record_id, row["tonne_km"], row["declared_kg_co2e"]))

    if any(not records for records in groups.values()):
        raise ValueError("CSV needs at least one train, holdout, and review record")

    rate = train_freight_model((activity, declared) for _, activity, declared in groups["train"])
    report = {
        "input_file": path.name,
        "training_count": len(groups["train"]),
        "model_rate_kg_co2e_per_tonne_km": str(rate),
    }

    for split in ("holdout", "review"):
        report[split] = [
            {"record_id": record_id, "tonne_km": activity,
             **periods[record_id], **assess_declaration(rate, activity, declared)}
            for record_id, activity, declared in groups[split]
        ]
    return report


def main():
    parser = argparse.ArgumentParser(description="Assess a simulated supplier freight CSV")
    parser.add_argument("csv_file", type=Path)
    args = parser.parse_args()

    try:
        report = assess_csv(args.csv_file)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(1, f"CSV rejected: {error}\n")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
