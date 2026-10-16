# Demo script

## A. 2–3 minute demo video (for shortlisting)

The Grayhat judges shortlist the top 10 mostly from this video, so show the working product quickly.

| Time | Show on screen | Say (in your own words) |
|---|---|---|
| 0:00–0:20 | Hero headline on the live Alternate Clouds URL | The problem: common medicines are illegal in some countries, rules are scattered, permits take weeks. Give one real example (pseudoephedrine in Japan). |
| 0:20–0:45 | Upload a photo of a real medicine box → "Read photo" → names appear | The AI reads the box, but **the traveller checks every name** before anything runs. |
| 0:45–1:15 | Route Lahore → Dubai (transit) → Tokyo, "Check my trip"; the agent trace appears | Each step is a tool: brand database, RxNorm drug API, rules engine, deadline planner. |
| 1:15–1:45 | The stamp matrix: red "Not allowed" in Japan, amber "Permit needed" in the UAE; click a stamp to show the source link | Legality comes from verified rules with sources, never from the AI's memory. Unknown countries are marked "not verified". |
| 1:45–2:10 | Plan with deadlines → "Add deadlines to calendar"; edit the letter; tick the confirmation; "Send to doctor" | **Human gate 1**: the traveller approves. |
| 2:10–2:40 | Open the doctor link (second browser or phone): edit, add name and registration, "Approve letter"; back in the dashboard the status turns green and the decision log shows both approvals | **Human gate 2**: the doctor approves. Everything is logged. |
| 2:40–2:55 | `/api/health` showing the app on Alternate Clouds; mention the MCP endpoint | Deployed on Alternate Clouds; tools also available over MCP. |

Tips: record at 1080p, zoom the browser to 110–125%, close other tabs, and **hide any keys** (don't show the Alternate Clouds environment variables page).

## B. 6-minute finalist demo (live)

1. **Hook (30 s):** hold up a box of a pseudoephedrine cold medicine. "This is legal in Pakistan. In Japan, carrying it can get you detained."
2. **Problem and who it's for (45 s):** every international traveller; scattered rules; permits weeks ahead; a prescription doesn't protect you.
3. **Live flow (3 min):** the same path as the video, with a teammate playing the doctor on a phone.
4. **Why Human + AI (45 s):** AI does the reading, lookup, cross-checking and paperwork; humans make the medical and legal decisions. Show the decision log.
5. **Business and next steps (45 s):** who pays (travellers per trip; travel insurers, airlines, travel clinics and pharmacies as partners), more countries, regulator data partnerships.
6. **Close (15 s):** one sentence on impact.

## Likely judge questions

- **"What if the rules are wrong?"** Every result links to its source and shows the review date; unknown countries are never guessed; the doctor and traveller confirm; it's an information tool, not legal advice.
- **"Why not let the AI decide?"** Legal facts must be exact and auditable, so the AI only reads, suggests and summarises. Try a fake brand: it shows "unknown - needs review" rather than inventing an answer.
- **"What if the AI API is down?"** The agent falls back to templates and the rules engine; the trace shows the fallback.
- **"How is this different from a chatbot?"** It runs a multi-step workflow with real tools (drug database, rules engine, calendar, email, MCP), with approval gates and an audit log.
