"""End-to-end tests. Run with:  pytest -q
They run offline (no AI key, no internet needed)."""
import os
import tempfile
from datetime import date, timedelta

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["LLM_PROVIDER"] = "none"
os.environ["RXNORM_ENABLED"] = "false"
os.environ["SEED_DEMO"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.tools import ingredients, rules  # noqa: E402


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def trip(route, meds, days=20):
    return {"traveler": {"name": "Test Traveller",
                         "departure_date": (date.today() + timedelta(days=days)).isoformat()},
            "route": route, "medicines": [{"name": m} for m in meds]}


def status_of(case, med, code):
    return next(f["status"] for f in case["findings"] if f["medicine"] == med and f["country_code"] == code)


def test_ingredient_lookup_offline():
    assert ingredients.resolve("Actifed")["ingredients"] == ["pseudoephedrine", "triprolidine"]
    assert "codeine" in ingredients.resolve("Panadeine Forte 500/30mg")["ingredients"]
    assert ingredients.resolve("codeine phosphate 30mg")["ingredients"] == ["codeine"]
    unknown = ingredients.resolve("Zzqx Unknown")
    assert unknown["ingredients"] == [] and unknown["verified"] is False


def test_categories():
    assert ingredients.categorize(["pseudoephedrine"]) == ["decongestant_precursor"]
    assert ingredients.categorize(["codeine phosphate"]) == ["opioid"]
    assert ingredients.categorize(["metformin"]) == []


def test_demo_seeded_and_health(c):
    assert c.get("/api/health").json()["ok"]
    assert len(c.get("/api/cases").json()["cases"]) >= 1


def test_rules_and_plan(c):
    case = c.post("/api/cases", json=trip([{"code": "JP"}, {"code": "ID"}, {"code": "GB"}],
                                          ["Sudafed", "Ritalin", "Glucophage"])).json()
    assert status_of(case, "Sudafed", "JP") == "prohibited"
    assert status_of(case, "Ritalin", "ID") == "prohibited"
    assert status_of(case, "Ritalin", "GB") == "prescription_required"
    assert status_of(case, "Glucophage", "GB") == "allowed"
    assert case["risk"]["level"] == "high"
    assert any(p["kind"] == "stop" for p in case["plan"])
    assert case["status"] == "awaiting_traveler_review"
    assert len(case["trace"]) >= 6


def test_unknown_country_and_overdue_deadline(c):
    case = c.post("/api/cases", json=trip([{"code": "Atlantis"}, {"code": "JP"}],
                                          ["Panadeine"], days=5)).json()
    assert status_of(case, "Panadeine", "Atlantis") == "unverified"
    permit = next(f for f in case["findings"] if f["country_code"] == "JP")
    assert permit["status"] == "permit_required" and permit["deadline_passed"]
    assert any(p["title"].startswith("URGENT") for p in case["plan"])


def test_full_human_approval_flow(c):
    case = c.post("/api/cases", json=trip([{"code": "AE", "transit": True}, {"code": "JP"}],
                                          ["Panadeine Forte"])).json()
    cid = case["id"]
    assert "doctor_token" not in case

    # Gate: approval needs explicit confirmation
    assert c.post(f"/api/cases/{cid}/approve", json={"confirm": False}).status_code == 400

    # Traveller edits and approves
    letter = case["letter"] + "\nEdited by traveller."
    assert c.put(f"/api/cases/{cid}/letter", json={"letter": letter}).status_code == 200
    approved = c.post(f"/api/cases/{cid}/approve", json={"confirm": True}).json()
    assert approved["status"] == "awaiting_doctor"
    token = approved["doctor_link"].rsplit("/", 1)[1]

    # Letter is locked while the doctor reviews
    assert c.put(f"/api/cases/{cid}/letter", json={"letter": letter + " again"}).status_code == 409

    # Doctor must give name and registration to approve
    assert c.post(f"/api/doctor/{token}/decision", json={"decision": "approve"}).status_code == 422
    r = c.post(f"/api/doctor/{token}/decision",
               json={"decision": "approve", "doctor_name": "Dr Sana Khan", "registration_no": "PMDC-12345"})
    assert r.json()["status"] == "doctor_approved"

    final = c.get(f"/api/cases/{cid}").json()
    actions = [a["action"] for a in final["audit"]]
    assert "approved plan and sent letter for doctor review" in actions and "approved letter" in actions
    assert "Dr Sana Khan" in c.get(f"/api/cases/{cid}/letter").text
    ics = c.get(f"/api/cases/{cid}/calendar.ics").text
    assert ics.startswith("BEGIN:VCALENDAR") and "VEVENT" in ics

    # Doctor link cannot be reused
    assert c.post(f"/api/doctor/{token}/decision", json={"decision": "approve", "doctor_name": "x",
                                                         "registration_no": "y"}).status_code == 409


def test_doctor_requests_changes(c):
    cid = c.post("/api/cases", json=trip([{"code": "SG"}], ["Xanax"])).json()["id"]
    token = c.post(f"/api/cases/{cid}/approve", json={"confirm": True}).json()["doctor_link"].rsplit("/", 1)[1]
    r = c.post(f"/api/doctor/{token}/decision", json={"decision": "request_changes", "note": "Wrong dose"})
    assert r.json()["status"] == "changes_requested"
    assert c.get(f"/api/doctor/{token}").status_code == 404  # old link revoked
    again = c.post(f"/api/cases/{cid}/approve", json={"confirm": True}).json()
    assert again["status"] == "awaiting_doctor"


def test_input_validation_and_photo_without_ai(c):
    assert c.post("/api/cases", json={"traveler": {"name": "x"}, "route": [], "medicines": []}).status_code == 422
    bad_date = trip([{"code": "JP"}], ["Panadol"])
    bad_date["traveler"]["departure_date"] = "31-12-2026"
    assert c.post("/api/cases", json=bad_date).status_code == 422
    r = c.post("/api/extract-medicines", files={"file": ("a.png", b"123", "image/png")})
    assert r.status_code == 503


def test_every_rule_has_valid_status_and_source():
    for code, country in rules.RULES.items():
        assert country["official_source"].startswith("https://"), code
        assert country["general"]["status"] in rules.SEVERITY
        for cat, rule in country["categories"].items():
            assert rule["status"] in rules.SEVERITY, (code, cat)
            assert rule["source"].startswith("https://"), (code, cat)


def test_brand_variant_is_not_trusted_blindly():
    r = ingredients.resolve("Tylenol PM")
    assert r["verified"] is False  # variants can contain extra ingredients


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._p, self.status_code, self.text = payload, status, str(payload)

    def json(self):
        return self._p


def test_ai_paths_with_mocked_providers(monkeypatch):
    from app import agent, config
    from app.tools import llm

    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"], sent["body"], sent["headers"] = url, json, headers
        text = '{"medicines": [{"name": "Panadeine Forte", "ingredients": ["paracetamol", "codeine"], "dose": "500/30 mg"}]}'
        if "googleapis" in url:
            return _FakeResponse({"candidates": [{"content": {"parts": [{"text": text}]}}]})
        return _FakeResponse({"choices": [{"message": {"content": "```json\n" + text + "\n```"}}]})

    monkeypatch.setattr(llm.httpx, "post", fake_post)

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    meds = agent.extract_from_image(b"fake-bytes", "image/png")
    assert meds[0]["name"] == "Panadeine Forte" and "codeine" in meds[0]["ingredients"]
    assert sent["headers"]["x-goog-api-key"] == "test-key"
    assert sent["body"]["contents"][0]["parts"][1]["inline_data"]["mime_type"] == "image/png"

    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key-2")
    meds = agent.extract_from_image(b"fake-bytes", "image/jpeg")
    assert meds[0]["dose"] == "500/30 mg"
    assert sent["url"].endswith("/chat/completions")
    assert sent["headers"]["Authorization"] == "Bearer test-key-2"


def test_ai_failure_falls_back_to_template(monkeypatch):
    from app import agent, config
    from app.tools import llm

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "bad")
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _FakeResponse({"error": "quota"}, 429))
    case = agent.new_case({"name": "A", "departure_date": ""}, [{"code": "JP", "name": "Japan", "transit": False}],
                          [{"name": "Sudafed"}])
    agent.run(case)
    assert "Actifed" not in case["summary"] and "Sudafed" in case["summary"]
    assert any(t["tool"] == "write_summary" and "AI unavailable" in t["detail"] for t in case["trace"])


def test_mcp_tool_check_trip():
    from app.mcp_server import check_trip
    out = check_trip(["Sudafed"], ["JP", "GB"], "2030-01-01")
    statuses = {f["country"]: f["status"] for f in out["findings"]}
    assert statuses == {"Japan": "prohibited", "United Kingdom": "allowed"}


def test_gemini_retries_without_thinking_setting(monkeypatch):
    from app import config
    from app.tools import llm

    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(json.get("generationConfig", {}).get("thinkingConfig"))
        if len(calls) == 1:
            return _FakeResponse({"error": {"message": "Unknown field thinkingLevel"}}, 400)
        return _FakeResponse({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.generate("hi") == "OK"
    assert calls == [{"thinkingLevel": "low"}, None]


def test_gemini_400_retries_with_minimal_request(monkeypatch):
    from app import config
    from app.tools import llm

    bodies = []

    def fake_post(url, json=None, headers=None, timeout=None):
        bodies.append(json)
        if len(bodies) < 3:
            return _FakeResponse({"error": {"message": "Invalid argument"}}, 400)
        return _FakeResponse({"candidates": [{"content": {"parts": [{"text": '{"a": 1}'}]}}]})

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.generate("hi", want_json=True) == {"a": 1}
    assert "temperature" in bodies[0]["generationConfig"]
    assert bodies[1] == {"contents": bodies[0]["contents"], "generationConfig": {"responseMimeType": "application/json"}}
    assert bodies[2] == {"contents": bodies[0]["contents"]}


def test_gemini_timeout_message(monkeypatch):
    import httpx
    from app import config
    from app.tools import llm

    def slow(*a, **k):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(llm.httpx, "post", slow)
    try:
        llm.generate("hi")
        raise AssertionError("expected LLMError")
    except llm.LLMError as e:
        assert "in time" in str(e)


def test_gemini_busy_retries_then_fallback(monkeypatch):
    from app import config
    from app.tools import llm

    seen = []

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.append(url.split("/models/")[1].split(":")[0])
        if "backup" in url:
            return _FakeResponse({"candidates": [{"content": {"parts": [{"text": "OK"}]}}]})
        return _FakeResponse({"error": {"message": "high demand"}}, 503)

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GEMINI_MODEL", "main-model")
    monkeypatch.setattr(config, "GEMINI_FALLBACK_MODEL", "backup-model")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm.httpx, "post", fake_post)
    assert llm.generate("hi") == "OK"
    assert seen == ["main-model"] * 3 + ["backup-model"]


def test_gemini_busy_gives_friendly_message(monkeypatch):
    from app import config
    from app.tools import llm

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GEMINI_FALLBACK_MODEL", "")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: _FakeResponse({"error": {"message": "high demand"}}, 503))
    try:
        llm.generate("hi")
        raise AssertionError("expected LLMError")
    except llm.LLMError as e:
        assert "busy right now" in str(e)


def test_slow_ai_never_blocks_trip_check(monkeypatch):
    """Even if the AI hangs, checking a trip must finish quickly (gateway limit is ~30 s)."""
    import time as _t
    import httpx
    from app import agent, config
    from app.tools import llm

    def hang(url, json=None, headers=None, timeout=None):
        _t.sleep(min(timeout, 0.3))  # simulate waiting the whole allowed time (scaled down)
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(llm.httpx, "post", hang)
    case = agent.new_case({"name": "A", "departure_date": ""}, [{"code": "JP", "name": "Japan", "transit": False}],
                          [{"name": "Sudafed"}, {"name": "Unknownbrandxyz"}])
    start = _t.monotonic()
    agent.run(case)
    assert _t.monotonic() - start < 5
    assert case["status"] == "awaiting_traveler_review" and case["summary"]


def test_budget_stops_retries(monkeypatch):
    from app import config
    from app.tools import llm

    calls = []
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "k")
    monkeypatch.setattr(config, "GEMINI_FALLBACK_MODEL", "")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: calls.append(1) or _FakeResponse({"error": {"message": "busy"}}, 503))
    try:
        llm.generate("hi", budget=4)
    except llm.LLMError:
        pass
    assert len(calls) == 1  # 4 s budget leaves no room for a retry