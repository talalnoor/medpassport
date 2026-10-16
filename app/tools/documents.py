"""Tools: draft the doctor's travel letter and build a calendar (.ics) of deadlines.

The letter is generated from verified facts only (no AI free-writing), so the
doctor reviews a predictable document. The doctor edits and approves it.
"""
import html
from datetime import date, datetime, timezone

from . import ingredients as ing_tool


def draft_letter(case: dict) -> str:
    t = case["traveler"]
    route = " → ".join(s["name"] + (" (transit)" if s.get("transit") else "") for s in case["route"])
    lines = [
        "TO WHOM IT MAY CONCERN / CUSTOMS AND BORDER OFFICIALS",
        "",
        f"Date: {date.today().strftime('%d %B %Y')}",
        "",
        f"This letter confirms that {t['name']}"
        + (f" (passport number {t['passport']})" if t.get("passport") else " (passport number: ______)")
        + " is under my medical care and has been prescribed the medicines listed below for personal use only.",
        "",
        f"Travel route: {route}",
        f"Departure date: {t.get('departure_date') or '______'}",
        "",
        "Medicines:",
    ]
    for i, m in enumerate(case["medicines"], 1):
        ingredients = ", ".join(m["ingredients"]) if m["ingredients"] else "active ingredient: ______"
        lines.append(
            f"{i}. {m['name']} ({ingredients})"
            f" - dose: {m.get('dose') or '______'}"
            f" - quantity for the trip: {m.get('days_supply') or '___'} days"
        )
    lines += [
        "",
        "Medical condition / reason for treatment: ______________________",
        "",
        "These medicines are required for the traveller's ongoing treatment, are carried in their original "
        "packaging, and are not for sale or distribution. Please contact me if you need further information.",
        "",
        "Doctor's name: ______________________",
        "Registration / licence number: ______________________",
        "Clinic and contact details: ______________________",
        "",
        "Signature and stamp: ______________________",
    ]
    return "\n".join(lines)


def letter_html(case: dict) -> str:
    approval = case.get("doctor_review") or {}
    approved = case["status"] == "doctor_approved"
    body = html.escape(case.get("letter", "")).replace("\n", "<br>")
    badge = (
        f"<p class='ok'>Reviewed and approved electronically by {html.escape(approval.get('doctor_name', ''))}"
        f" (registration {html.escape(approval.get('registration_no', ''))}) on {html.escape(approval.get('at', ''))}."
        " Please sign and stamp the printed copy.</p>"
        if approved else
        "<p class='warn'>DRAFT - not yet approved by a doctor. Do not use for travel.</p>"
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Travel medicine letter</title>
<style>body{{font-family:Georgia,serif;max-width:720px;margin:40px auto;line-height:1.55;color:#111;padding:0 16px}}
.ok{{border:1px solid #1b7f4b;color:#1b7f4b;padding:8px 12px;font-family:sans-serif;font-size:14px}}
.warn{{border:1px solid #b42318;color:#b42318;padding:8px 12px;font-family:sans-serif;font-size:14px}}
@media print{{button{{display:none}}}}</style></head><body>
<button onclick="window.print()">Print / Save as PDF</button>{badge}<div>{body}</div>
<p style="font-family:sans-serif;font-size:12px;color:#555;margin-top:32px">Prepared with MedPassport. Case {html.escape(case['id'])}.</p>
</body></html>"""


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar_ics(case: dict) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    events = []
    for i, task in enumerate(case.get("plan", [])):
        if not task.get("due"):
            continue
        day = task["due"].replace("-", "")
        events.append(
            "BEGIN:VEVENT\r\n"
            f"UID:{case['id']}-{i}@medpassport\r\nDTSTAMP:{stamp}\r\n"
            f"DTSTART;VALUE=DATE:{day}\r\n"
            f"SUMMARY:{_ics_escape('MedPassport: ' + task['title'])}\r\n"
            f"DESCRIPTION:{_ics_escape(task.get('detail', ''))}\r\n"
            "BEGIN:VALARM\r\nTRIGGER:-P2D\r\nACTION:DISPLAY\r\nDESCRIPTION:Reminder\r\nEND:VALARM\r\n"
            "END:VEVENT\r\n"
        )
    dep = case["traveler"].get("departure_date")
    if dep:
        events.append(
            "BEGIN:VEVENT\r\n"
            f"UID:{case['id']}-departure@medpassport\r\nDTSTAMP:{stamp}\r\n"
            f"DTSTART;VALUE=DATE:{dep.replace('-', '')}\r\n"
            "SUMMARY:Departure - carry prescriptions and the signed doctor's letter\r\n"
            "END:VEVENT\r\n"
        )
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//MedPassport//EN\r\nCALSCALE:GREGORIAN\r\n"
            + "".join(events) + "END:VCALENDAR\r\n")


def category_labels(keys: list[str]) -> list[str]:
    return [ing_tool.category_label(k) for k in keys]
