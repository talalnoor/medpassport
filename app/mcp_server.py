"""MedPassport tools exposed over the Model Context Protocol (MCP).

Any MCP client (Claude, Cursor, an n8n MCP node...) can call these read-only tools.
They never send, submit or approve anything; approvals stay with humans in the web app.

- Hosted:  https://<your-app>/mcp   (streamable HTTP, mounted by app/main.py)
- Local:   python -m app.mcp_server  (stdio)
"""
from datetime import date

from mcp.server import MCPServer

from .tools import ingredients, rules

mcp = MCPServer(
    name="medpassport",
    instructions="Check whether medicines are legal in the countries on a travel route. "
                 "Results come from a curated rules file with sources; always tell the user to confirm "
                 "with their doctor and the embassy.",
)


@mcp.tool()
def lookup_ingredients(medicine: str) -> dict:
    """Find the active ingredients of a medicine brand or generic name, and its controlled-drug categories."""
    res = ingredients.resolve(medicine[:80])
    return {"medicine": medicine, "ingredients": res["ingredients"], "verified": res["verified"],
            "source": res["source"], "categories": ingredients.categorize(res["ingredients"])}


@mcp.tool()
def list_supported_countries() -> dict:
    """List the countries with verified medicine rules (ISO codes)."""
    return {"countries": rules.countries(), "last_reviewed": rules.LAST_REVIEWED}


@mcp.tool()
def check_trip(medicines: list[str], country_codes: list[str], departure_date: str = "",
               transit_codes: list[str] | None = None) -> dict:
    """Check each medicine against each country. Codes are ISO 3166 alpha-2 (e.g. JP, AE).
    departure_date is YYYY-MM-DD and is used to compute paperwork deadlines."""
    try:
        departure = date.fromisoformat(departure_date) if departure_date else None
    except ValueError:
        return {"error": "departure_date must be YYYY-MM-DD"}
    transit = {c.upper() for c in (transit_codes or [])}
    meds = []
    for name in medicines[:15]:
        res = ingredients.resolve(name[:80])
        meds.append({"name": name, "ingredients": res["ingredients"],
                     "categories": ingredients.categorize(res["ingredients"])})
    findings = []
    for code in country_codes[:8]:
        code = code.strip().upper()
        stop = {"code": code, "name": rules.country_name(code), "transit": code in transit}
        for med in meds:
            f = rules.check(med, stop, departure)
            findings.append({k: f[k] for k in ("medicine", "country", "status", "details", "source", "deadline")})
    return {"findings": findings,
            "note": "Information, not legal advice. A doctor must review any travel letter."}


if __name__ == "__main__":
    mcp.run("stdio")
