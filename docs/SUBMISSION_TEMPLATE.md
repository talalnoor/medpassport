# Agentika 2.0 submission: MedPassport

> Fill in every `[ ]` field, then export this page to PDF. One PDF per team, submitted by one teammate before **17 October, 12:45 PM PKT**. Check the Alternate Futures Discord announcement for where to send it.

## 1. Team details

- **Team name:** [ ]
- **Member 1:** [full name] · [email] · Discord: [registered username]
- **Member 2:** [full name] · [email] · Discord: [registered username]
- **Team WhatsApp contact:** [ ]

## 2. About the project

**Project name:** MedPassport

**One-line pitch:** [write your own one line]

**The problem and who it is for (2–3 lines):** [write in your own words: travellers carry medicines that are legal at home but banned or permit-only abroad; rules are scattered; permits take weeks]

**Where the human comes in (Theme: Human + AI: Better Together):**
- The traveller checks the medicine names the AI read from a photo before analysis.
- The traveller reviews the findings, edits the drafted letter and must explicitly confirm before it is sent to a doctor.
- The doctor reviews, edits, and approves the letter with their name and registration number, or sends it back with changes.
- Why: legal and medical decisions can't be left to AI. A mistake could mean detention at a border or a missed treatment, so the AI prepares and the humans decide. Every decision is recorded in an audit log.

**What we built with:**
- Custom code: Python (FastAPI), HTML/CSS/JavaScript, SQLite, Docker
- AI model: [Gemini model name / Groq model name you used], for reading medicine photos and writing summaries
- APIs: RxNorm (US National Library of Medicine) for brand → ingredient lookup; SMTP email [if used]
- MCP: the agent's tools (`lookup_ingredients`, `check_trip`, `list_supported_countries`) are served as an MCP server at `/mcp`
- Curated rules engine for 11 countries, each rule linked to its source

## 3. Required links

- **Live Alternate Clouds deployment:** [https://...-app.alternatefutures.ai]
- **GitHub repository:** [https://github.com/...]
- **Demo video (2–3 min):** [unlisted YouTube or Drive link set to "anyone with the link"]
- **Original LinkedIn post:** [ ]
- **Teammate's reshare:** [ ]
- **X / Twitter post (optional):** [ ]

## 4. Proof screenshots

- [Paste screenshot: both teammates in the Alternate Futures Discord server]
- [Paste screenshot: Alternate Clouds dashboard showing the MedPassport service and Active deployment status, with no keys visible]

**Access for judges:** no login is needed. Open the live link and click "Fill sample trip", or open the sample trip in the left column. To test the doctor step, approve a trip and open the doctor link it shows.

## 5. Confirmations

- [ ] We wrote our LinkedIn post ourselves. Only grammar-only tools were used.
- [ ] Our project is deployed on Alternate Clouds.
- [ ] No API keys or personal or production passwords appear in our repository, video or screenshots.
- [ ] We have credited third-party code and templates (see CREDITS.md in the repository).
- [ ] We will not change our code or deployment after 12:45 PM PKT on 17 October.
