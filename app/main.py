"""MedPassport web server (FastAPI).

Human approval gates:
  1. Traveller confirms the medicines read from a photo before analysis.
  2. Traveller reviews findings and the drafted letter, then approves sending it to a doctor.
  3. The doctor reviews, edits and approves (or requests changes) on their own page.
Nothing is sent or finalised without these approvals, and every decision is logged.
A letter that names a medicine not allowed on the route is never saved, sent or approved.
"""
import logging
import re
import secrets
import time
from datetime import date, timedelta
from typing import Literal

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import agent, config, db
from .mcp_server import mcp
from .tools import documents, llm, notify, rules

# MCP endpoint (read-only tools) served at /mcp on the same deployment
mcp_app = mcp.streamable_http_app(streamable_http_path="/", stateless_http=True,
                                  json_response=True, host="0.0.0.0")

@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    if config.SEED_DEMO and db.count_cases() == 0:
        seed_demo()
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="MedPassport", version="1.0.0", lifespan=lifespan,
              description="Travel-medicine compliance agent with human approval")


# ---------- request models ----------
class Stop(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str | None = Field(default=None, max_length=60)
    transit: bool = False


class Medicine(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    dose: str = Field(default="", max_length=40)
    days_supply: int | None = Field(default=None, ge=1, le=365)
    ingredients_override: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("ingredients_override")
    @classmethod
    def clean(cls, v):
        return [i.strip().lower()[:40] for i in v if i and i.strip()]


class Traveler(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(default="", max_length=120)
    passport: str = Field(default="", max_length=30)
    departure_date: str = Field(default="", max_length=10)

    @field_validator("departure_date")
    @classmethod
    def valid_date(cls, v):
        if v:
            date.fromisoformat(v)
        return v


class CaseIn(BaseModel):
    traveler: Traveler
    route: list[Stop] = Field(min_length=1, max_length=config.MAX_COUNTRIES)
    medicines: list[Medicine] = Field(min_length=1, max_length=config.MAX_MEDICINES)


class LetterIn(BaseModel):
    letter: str = Field(min_length=20, max_length=8000)


class ApproveIn(BaseModel):
    doctor_email: str = Field(default="", max_length=120)
    confirm: bool = False


class DoctorDecisionIn(BaseModel):
    decision: Literal["approve", "request_changes"]
    doctor_name: str = Field(default="", max_length=80)
    registration_no: str = Field(default="", max_length=40)
    note: str = Field(default="", max_length=1000)
    letter: str | None = Field(default=None, max_length=8000)


log = logging.getLogger("medpassport")
logging.basicConfig(level=logging.INFO)
_ai_check_cache: dict = {}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- helpers ----------
def _route(stops: list[Stop]) -> list[dict]:
    out = []
    for s in stops:
        code = s.code.strip().upper()
        known = code in rules.RULES
        out.append({"code": code if known else s.code.strip(),
                    "name": rules.country_name(code) if known else (s.name or s.code).strip(),
                    "transit": s.transit})
    return out


def _public(case: dict) -> dict:
    """Hide the doctor token from the traveller API (it is shown only as a link after approval)."""
    data = {k: v for k, v in case.items() if k != "doctor_token"}
    data["audit"] = db.get_audit(case["id"])
    return data


def _load(case_id: str) -> dict:
    case = db.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


def _base_url(request: Request) -> str:
    return config.PUBLIC_BASE_URL or str(request.base_url).rstrip("/")


def _require_letter_needed(case: dict):
    """Older cases have no 'letter_needed' field; treat them as needing a letter."""
    if not case.get("letter_needed", True):
        raise HTTPException(409, "No doctor's letter is needed: none of the medicines on this trip "
                                 "can be carried on your route.")


def _block_banned(case: dict, text: str, actor: str, action: str):
    """Refuse a letter that names a medicine (or its ingredient) that is not allowed on the route."""
    hits = agent.find_banned_in_letter(case, text)
    if hits:
        db.add_audit(case["id"], actor, f"blocked: {action}",
                     f"letter mentions {', '.join(hits)}, not allowed on route")
        raise HTTPException(422, f"The letter mentions {', '.join(hits)}, which is not allowed on this "
                                 "route. Remove it before continuing.")


# ---------- demo data ----------
def demo_payload() -> dict:
    return {
        "traveler": {"name": "Ali Raza", "email": "", "passport": "",
                     "departure_date": (date.today() + timedelta(days=20)).isoformat()},
        "route": [{"code": "AE", "transit": True}, {"code": "JP", "transit": False}],
        "medicines": [
            {"name": "Actifed", "dose": "60 mg", "days_supply": 10},
            {"name": "Panadeine Forte", "dose": "500/30 mg", "days_supply": 10},
            {"name": "Lyrica", "dose": "75 mg", "days_supply": 14},
            {"name": "Glucophage", "dose": "500 mg", "days_supply": 14},
        ],
    }


def seed_demo():
    payload = CaseIn(**demo_payload())
    case = agent.new_case(payload.traveler.model_dump(), _route(payload.route),
                          [m.model_dump() for m in payload.medicines])
    agent.run(case, use_ai=False)  # no AI call at startup: boots fast, works even if the AI is down
    db.save_case(case)
    db.add_audit(case["id"], "system", "demo case created", "Sample trip Dubai (transit) → Tokyo")


# ---------- API ----------
@app.get("/api/health")
def health():
    return {"ok": True, "ai_provider": llm.provider(), "ai_model": llm.model_name(),
            "email_enabled": notify.email_configured(), "rules_last_reviewed": rules.LAST_REVIEWED,
            "countries_verified": len(rules.RULES)}


@app.get("/api/ai-check")
def ai_check():
    """Makes one tiny call to the AI model and reports the exact error, if any. Cached for 60 s."""
    if _ai_check_cache and time.time() - _ai_check_cache["at"] < 60:
        return _ai_check_cache["result"]
    result = {"provider": llm.provider(), "model": llm.model_name()}
    if not llm.available():
        result.update(ok=False, error="No AI key configured (check LLM_PROVIDER and the API key variable).")
    else:
        start = time.perf_counter()
        try:
            reply = llm.generate("Reply with the single word OK.", budget=15)
            result.update(ok=True, reply=reply[:20])
        except llm.LLMError as e:
            result.update(ok=False, error=str(e)[:400])
        result["seconds"] = round(time.perf_counter() - start, 1)
    _ai_check_cache.update(at=time.time(), result=result)
    log.info("ai-check: %s", result)
    return result


@app.get("/api/countries")
def list_countries():
    return {"countries": rules.countries(), "last_reviewed": rules.LAST_REVIEWED}


@app.get("/api/demo")
def get_demo():
    return demo_payload()


@app.post("/api/extract-medicines")
async def extract_medicines(file: UploadFile = File(...)):
    """Human gate 1: the AI reads the photo, the traveller confirms the list before analysis."""
    if not llm.available():
        raise HTTPException(503, "Photo reading needs an AI key (see setup guide). Please type the medicines instead.")
    mime = file.content_type or "image/jpeg"
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "Please upload a JPG, PNG or WEBP photo.")
    data = await file.read(config.MAX_IMAGE_BYTES + 1)
    if len(data) > config.MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 6 MB).")
    try:
        meds = agent.extract_from_image(data, mime)
    except llm.LLMError as e:
        log.warning("photo reading failed: %s", e)
        # 422, not 502: some hosting gateways replace 5xx bodies, which would hide this message
        raise HTTPException(422, f"Could not read the photo: {e}. Please type the medicines instead.")
    return {"medicines": meds, "note": "Read by AI. Please check every name before continuing."}


@app.post("/api/cases")
def create_case(body: CaseIn):
    case = agent.new_case(body.traveler.model_dump(), _route(body.route),
                          [m.model_dump() for m in body.medicines])
    agent.run(case)
    db.save_case(case)
    db.add_audit(case["id"], "agent", "analysis completed",
                 f"risk={case['risk']['level']}; {len(case['plan'])} tasks")
    return _public(case)


@app.get("/api/cases")
def cases():
    return {"cases": [{"id": c["id"], "traveler": c["traveler"]["name"], "status": c["status"],
                       "risk": c.get("risk", {}).get("level"), "created_at": c["created_at"],
                       "route": [s["name"] for s in c["route"]]} for c in db.list_cases()]}


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    return _public(_load(case_id))


@app.put("/api/cases/{case_id}/letter")
def edit_letter(case_id: str, body: LetterIn):
    case = _load(case_id)
    if case["status"] not in ("awaiting_traveler_review", "changes_requested"):
        raise HTTPException(409, "The letter can only be edited before it is sent to the doctor.")
    _require_letter_needed(case)
    _block_banned(case, body.letter, "traveller", "letter edit")
    case["letter"] = body.letter
    db.save_case(case)
    db.add_audit(case_id, "traveller", "edited letter")
    return _public(case)


@app.post("/api/cases/{case_id}/approve")
def traveller_approve(case_id: str, body: ApproveIn, request: Request):
    """Human gate 2: only an explicit confirmation sends the draft to the doctor."""
    case = _load(case_id)
    if not body.confirm:
        raise HTTPException(400, "Explicit confirmation is required.")
    if case["status"] not in ("awaiting_traveler_review", "changes_requested"):
        raise HTTPException(409, f"Case is '{case['status']}', it cannot be approved again.")
    _require_letter_needed(case)
    _block_banned(case, case.get("letter", ""), "agent", "send to doctor")
    if body.doctor_email and not EMAIL_RE.match(body.doctor_email):
        raise HTTPException(422, "Doctor email looks invalid.")
    case["doctor_token"] = secrets.token_urlsafe(18)
    case["status"] = "awaiting_doctor"
    case["doctor_email"] = body.doctor_email
    link = f"{_base_url(request)}/doctor/{case['doctor_token']}"
    case["doctor_link"] = link
    db.add_audit(case_id, "traveller", "approved plan and sent letter for doctor review")
    sent, info = (False, "No doctor email given; share the link manually.")
    if body.doctor_email:
        sent, info = notify.send_email(
            body.doctor_email, f"Please review a travel medicine letter for {case['traveler']['name']}",
            f"Hello Doctor,\n\n{case['traveler']['name']} has asked you to review a travel medicine letter "
            f"prepared with MedPassport.\n\nReview, edit and approve it here:\n{link}\n\n"
            "Nothing is final until you approve it.\n\nMedPassport")
    case["notification"] = info
    db.add_audit(case_id, "agent", "doctor notified" if sent else "doctor link created", info)
    db.save_case(case)
    return _public(case)


@app.post("/api/cases/{case_id}/cancel")
def cancel(case_id: str):
    case = _load(case_id)
    if case["status"] == "doctor_approved":
        raise HTTPException(409, "Already approved by a doctor.")
    case["status"] = "cancelled"
    case.pop("doctor_token", None)
    db.save_case(case)
    db.add_audit(case_id, "traveller", "cancelled case")
    return _public(case)


@app.get("/api/cases/{case_id}/calendar.ics")
def calendar(case_id: str):
    case = _load(case_id)
    return Response(documents.calendar_ics(case), media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="medpassport-{case_id}.ics"'})


@app.get("/api/cases/{case_id}/letter", response_class=HTMLResponse)
def letter(case_id: str):
    return documents.letter_html(_load(case_id))


# ---------- doctor review (separate page, opened by secret link) ----------
@app.get("/api/doctor/{token}")
def doctor_view(token: str):
    case = db.get_case_by_token(token)
    if not case:
        raise HTTPException(404, "This review link is invalid or has expired.")
    keep = ("id", "status", "traveler", "route", "medicines", "findings", "letter", "risk", "doctor_review")
    data = {k: case.get(k) for k in keep}
    data["traveler"] = {"name": case["traveler"]["name"], "departure_date": case["traveler"].get("departure_date")}
    return data


@app.post("/api/doctor/{token}/decision")
def doctor_decision(token: str, body: DoctorDecisionIn):
    """Human gate 3: the doctor approves or sends the letter back."""
    case = db.get_case_by_token(token)
    if not case:
        raise HTTPException(404, "This review link is invalid or has expired.")
    if case["status"] != "awaiting_doctor":
        raise HTTPException(409, f"This case is '{case['status']}' and cannot be reviewed now.")
    actor = f"doctor:{body.doctor_name.strip() or 'unnamed'}"
    if body.letter:
        _block_banned(case, body.letter, actor, "doctor letter edit")
        case["letter"] = body.letter
    if body.decision == "approve":
        if not body.doctor_name.strip() or not body.registration_no.strip():
            raise HTTPException(422, "Doctor name and registration number are required to approve.")
        _block_banned(case, case.get("letter", ""), actor, "doctor approval")
        case["status"] = "doctor_approved"
        case["doctor_review"] = {"doctor_name": body.doctor_name.strip(),
                                 "registration_no": body.registration_no.strip(),
                                 "note": body.note, "at": db.now_iso()}
        db.add_audit(case["id"], f"doctor:{body.doctor_name.strip()}", "approved letter", body.note)
    else:
        case["status"] = "changes_requested"
        case["doctor_review"] = {"doctor_name": body.doctor_name.strip(), "note": body.note, "at": db.now_iso()}
        case.pop("doctor_token", None)
        db.add_audit(case["id"], actor, "requested changes", body.note)
    db.save_case(case)
    return {"ok": True, "status": case["status"]}


# ---------- pages ----------
@app.get("/doctor/{token}", response_class=HTMLResponse)
def doctor_page(token: str):
    return FileResponse(config.STATIC_DIR / "doctor.html")


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return "User-agent: *\nDisallow: /doctor/\n"


app.mount("/mcp", mcp_app)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")