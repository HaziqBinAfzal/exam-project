import argparse
import json
from pathlib import Path


def render_disclosure(report):
    screen = report["disclosure_rules_screen"]
    lines = [
        "# Climate Disclosure Draft",
        "",
        f"**Company:** {screen['company']}",
        f"**Period:** {report['period_start']} to {report['period_end']}",
        f"**Status:** {report['status']}",
        "",
        "## Governance",
        "",
        "Board oversight and oversight evidence are pending.",
        "",
        "## Strategy",
        "",
        "Climate risk scenarios and financial impacts are pending.",
        "",
        "## Risk Management",
        "",
    ]

    reviews = report["open_reviews"]
    lines.extend(
        f"- Meter review required for `{item['reading_id']}` ({item['reason']})."
        for item in reviews
    )
    if not reviews:
        lines.append("- No open meter reviews in the supplied draft.")

    lines.extend([
        "",
        "## Metrics and Targets",
        "",
        f"- Scope 1: {report['scope_1_kg_co2e']} kg CO₂e",
        f"- Scope 2: {report['scope_2_kg_co2e']} kg CO₂e",
        f"- Combined Scope 1 and 2: {report['combined_scope_1_and_2_kg_co2e']} kg CO₂e",
        "- Climate targets and progress against targets are pending.",
    ])

    freight = report.get("scope_3_freight", {})
    for item in freight.get("declarations", []):
        review = "review required" if item["review_required"] else "within demo tolerance"
        lines.append(
            f"- Supplemental Scope 3 freight estimate `{item['record_id']}`: "
            f"{item['estimated_kg_co2e']} kg CO₂e ({review}, reporting dates unassigned)."
        )

    credit = report.get("retired_credit")
    if credit:
        lines.append(
            f"- Retired credit `{credit['credit_id']}`: {credit['quantity_tonnes_co2e']} "
            f"tonnes CO₂e. Fabric transaction `{credit['retirement_transaction_id']}`."
        )

    lines.extend(["", "## Evidence and Disclosure Screening", ""])
    for reference in report["evidence_references"]:
        lines.append(
            f"- Scope {reference['scope']}: reading `{reference['reading_id']}`, "
            f"factor `{reference['factor_id']}`."
        )
    lines.append(f"- Rules snapshot: {screen['rules_snapshot_date']}.")
    for label, key in (("SEC", "sec_climate_disclosure"), ("EU CSRD", "eu_csrd")):
        result = screen[key]
        lines.append(f"- {label}: `{result['screen_status']}`. {result['review_action']}")
        lines.append(f"  [Source]({result['source']})")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render a screened disclosure as Markdown")
    parser.add_argument("screened_report", type=Path)
    args = parser.parse_args()

    try:
        report = json.loads(args.screened_report.read_text(encoding="utf-8"))
        print(render_disclosure(report))
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Report export failed: {error}\n")
