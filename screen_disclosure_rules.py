import argparse
import json
from pathlib import Path


def screen_rules(profile):
    employees = profile.get("average_employees")
    turnover = profile.get("net_turnover_eur")
    eu_entity = profile.get("eu_entity_in_screen")
    registrant = profile.get("sec_registrant")

    if eu_entity is not True or type(employees) is not int or type(turnover) is not int:
        eu_status = "entity_details_require_review"
    elif employees < 0 or turnover < 0:
        raise ValueError("Employees and turnover must be non-negative")
    elif employees > 1000 and turnover > 450_000_000:
        eu_status = "size_screen_triggered"
    else:
        eu_status = "size_screen_not_triggered"

    if registrant is True:
        sec_status = "current_rule_status_requires_review"
    elif registrant is False:
        sec_status = "registrant_screen_not_triggered"
    else:
        sec_status = "registrant_status_requires_review"

    return {
        "rules_snapshot_date": "2026-11-27",
        "company": profile["company"],
        "sec_climate_disclosure": {
            "screen_status": sec_status,
            "source": "https://www.sec.gov/rules-regulations/2026/05/s7-2026-19",
            "source_event": "Proposed rescission, issued 2026-05-29",
            "review_action": "Confirm registrant status and check the latest SEC rule and litigation status.",
        },
        "eu_csrd": {
            "screen_status": eu_status,
            "source": "https://eur-lex.europa.eu/eli/dir/2026/470/oj/eng",
            "review_action": "Confirm entity and group scope, reporting year, and national implementation.",
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Attach a dated rules screen to a disclosure draft")
    parser.add_argument("draft", type=Path)
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()

    try:
        draft = json.loads(args.draft.read_text(encoding="utf-8"))
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        draft["disclosure_rules_screen"] = screen_rules(profile)
        print(json.dumps(draft, indent=2))
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, f"Disclosure screening failed: {error}\n")
