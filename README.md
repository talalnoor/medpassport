# MedPassport

**Your cold medicine can get you arrested in Japan.** MedPassport is an AI agent that checks whether the medicines you carry are legal in every country on your route (including transit stops), plans the permits and deadlines, and drafts the letter your doctor signs. **Nothing is sent or finalised without human approval: first the traveller's, then the doctor's.**

Built for Agentika 2.0 (NaSCon 2026, FAST University Islamabad). Theme: **Human + AI: Better Together**. Deployed on **Alternate Clouds**.

---

## The problem

Medicines that are normal at home can be banned abroad. Common cold remedies containing pseudoephedrine are treated as stimulant raw material in Japan; codeine, ADHD medicines and sleeping tablets are illegal in Indonesia; the UAE controls painkillers such as codeine, Tramadol and Pregabalin. A prescription from home often does not protect the traveller. The rules are spread across dozens of government websites in different languages, permits must be requested weeks in advance, and most travellers never check.

This affects every international traveller: students, pilgrims, migrant workers, patients with chronic conditions and business travellers.

## What the agent does

| Step | Tool the agent uses | Human gate |
|---|---|---|
| 1. Read medicine names from a photo of a box or prescription | Vision AI model (Gemini or any OpenAI-compatible model) | **Traveller checks every name** before analysis |
| 2. Find active ingredients | Local brand database → **RxNorm API** (US National Library of Medicine) → AI suggestion marked "verify" | Unverified ingredients become "confirm with pharmacist" tasks |
| 3. Classify controlled substances | Ingredient → legal category mapping | |
| 4. Check every country on the route | **Curated rules engine with official sources** (11 countries) | Unknown countries are marked "not verified - check embassy", never guessed |
| 5. Plan permits and deadlines | Deadline calculator, `.ics` calendar export | |
| 6. Draft the doctor's letter | Template filled from verified facts only | **Traveller edits and explicitly approves** sending it |
| 7. Doctor review | Private review link (optionally emailed via SMTP) | **Doctor edits, then approves with name + registration number, or sends it back** |
| 8. Audit | Decision log of every action and approval | |

**Why the AI does not decide legality:** legal and medical facts must be exact. The AI reads photos, suggests unknown ingredients and writes plain-language summaries; the yes/no answer always comes from the curated rules file, with a source link. If the AI is unavailable, the agent falls back to templates and keeps working.

**MCP:** the agent's read-only tools (`lookup_ingredients`, `check_trip`, `list_supported_countries`) are also served over the Model Context Protocol at `/mcp`, so other AI assistants and automation tools can use them.

## Architecture

```
Browser (dashboard)  ──►  FastAPI app (one container on Alternate Clouds)
Doctor review page   ──►    ├─ agent.py          workflow + trace
MCP clients          ──►    ├─ tools/ingredients  local DB → RxNorm API → AI
                            ├─ tools/rules        curated country rules (JSON, with sources)
                            ├─ tools/llm          Gemini / OpenAI-compatible (Groq)
                            ├─ tools/documents    doctor letter, calendar (.ics)
                            ├─ tools/notify       SMTP email (after approval only)
                            ├─ mcp_server.py      MCP tools at /mcp
                            └─ db.py              SQLite: cases + audit log
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env        # then add your GEMINI_API_KEY (optional)
uvicorn app.main:app --reload
# open http://localhost:8000
pytest -q                   # 13 tests, run offline
```

With Docker:

```bash
docker build -t medpassport:1.0.0 .
docker run -p 8000:8000 --env-file .env medpassport:1.0.0
```

## Deploy on Alternate Clouds

See [docs/DEPLOY_ALTERNATE_CLOUDS.md](docs/DEPLOY_ALTERNATE_CLOUDS.md).

## API overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status, AI model, rule coverage |
| POST | `/api/extract-medicines` | Read names from a photo (traveller confirms) |
| POST | `/api/cases` | Run the agent on a trip |
| GET | `/api/cases/{id}` | Case with findings, plan, letter, trace, audit |
| PUT | `/api/cases/{id}/letter` | Traveller edits the letter |
| POST | `/api/cases/{id}/approve` | Traveller approval (requires `confirm: true`) |
| GET/POST | `/api/doctor/{token}` and `/decision` | Doctor review and decision |
| GET | `/api/cases/{id}/calendar.ics` | Deadlines for any calendar app |
| GET | `/api/cases/{id}/letter` | Printable letter |
| POST | `/mcp/` | MCP endpoint (streamable HTTP) |

## Limitations (honest)

- The rules file covers 11 countries and was compiled on 2026-10-16 from official regulator sites and government travel advice. Rules change, so every result links to its source and the app tells users to confirm with the embassy.
- MedPassport is an information and paperwork tool, not legal or medical advice. A doctor must review and sign the letter.
- Data is stored in SQLite inside the container, which is fine for a demo; a production version would use a managed database and user accounts.

## Credits

See [CREDITS.md](CREDITS.md).
