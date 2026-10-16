"""Tool: check each medicine against each country on the route.

Decisions come only from the curated rules file (with sources). Countries that
are not in the file are marked "unverified" so a human must check them.
"""
import json
from datetime import date, timedelta

from .. import config

_raw = json.loads((config.DATA_DIR / "country_rules.json").read_text(encoding="utf-8"))
RULES = _raw["countries"]
LAST_REVIEWED = _raw.get("last_reviewed", "")

SEVERITY = {"prohibited": 5, "permit_required": 4, "unverified": 3, "caution": 3,
            "prescription_required": 2, "allowed": 1}

STATUS_LABEL = {
    "prohibited": "Not allowed",
    "permit_required": "Permit needed before travel",
    "prescription_required": "Allowed with prescription",
    "caution": "Check before travel",
    "allowed": "Allowed",
    "unverified": "Not verified - check embassy",
}


def countries() -> list[dict]:
    items = [{"code": code, "name": c["name"]} for code, c in RULES.items()]
    return sorted(items, key=lambda x: x["name"])


def country_name(code: str) -> str:
    return RULES.get(code, {}).get("name", code)


def check(medicine: dict, stop: dict, departure: date | None) -> dict:
    """medicine: {name, ingredients, categories}; stop: {code, name, transit}."""
    code = stop["code"]
    rule_set = RULES.get(code)
    base = {"medicine": medicine["name"], "country_code": code,
            "country": stop.get("name") or country_name(code), "transit": bool(stop.get("transit"))}

    if rule_set is None:
        return {**base, "status": "unverified", "category": None,
                "details": "MedPassport has no verified rules for this country yet. Contact the embassy or health regulator before travel.",
                "source": None, "lead_days": 14, **_deadline(departure, 14)}

    matched = None
    for cat in medicine.get("categories", []):
        rule = rule_set["categories"].get(cat)
        if rule and (matched is None or SEVERITY[rule["status"]] > SEVERITY[matched[1]["status"]]):
            matched = (cat, rule)

    if not medicine.get("ingredients"):
        result = {**base, "status": "unverified", "category": None,
                  "details": "Active ingredient unknown, so this medicine cannot be checked. Ask your pharmacist for the active ingredient.",
                  "source": rule_set["official_source"], "lead_days": 0}
    elif matched:
        cat, rule = matched
        result = {**base, "status": rule["status"], "category": cat, "details": rule["details"],
                  "source": rule.get("source") or rule_set["official_source"],
                  "lead_days": rule.get("lead_days", rule_set["general"].get("lead_days", 0))}
    else:
        g = rule_set["general"]
        result = {**base, "status": g["status"], "category": None, "details": g["details"],
                  "source": rule_set["official_source"], "lead_days": g.get("lead_days", 0)}

    if result["transit"] and result["status"] in ("prohibited", "permit_required"):
        result["details"] += (" You are only transiting here: rules usually apply if you pass through"
                              " immigration (for example a long layover or leaving the airport). Stay airside or get approval.")
    needs_deadline = result["status"] in ("permit_required", "unverified")
    result.update(_deadline(departure, result["lead_days"]) if needs_deadline else {"deadline": None, "deadline_passed": False})
    return result


def _deadline(departure: date | None, lead_days: int) -> dict:
    if not departure or not lead_days:
        return {"deadline": None, "deadline_passed": False}
    d = departure - timedelta(days=lead_days)
    return {"deadline": d.isoformat(), "deadline_passed": d < date.today()}
