# What your team needs to do

Everything in the code is ready. These steps need your own accounts, so only you can do them. Times are rough.

## Accounts and keys

| # | What | Where | Needed? | Time |
|---|---|---|---|---|
| 1 | **Alternate Clouds account** + event credits | clouds.alternatefutures.ai (ask organisers about credits) | **Required** | 5 min |
| 2 | **GitHub account** + public repo | github.com | **Required** (code link for judges, and builds the image) | 5 min |
| 3 | **AI key: Google Gemini** | https://aistudio.google.com/apikey → "Create API key" | Strongly recommended (photo reading + AI summaries) | 3 min |
| 3b | or **AI key: Groq** (alternative) | https://console.groq.com/keys | Only if Gemini doesn't work for you | 3 min |
| 4 | Docker Hub account | hub.docker.com | Only if you build with Docker Desktop instead of GitHub | 3 min |
| 5 | Gmail **App Password** for emailing doctors | Google Account → Security → 2-Step Verification → App passwords | Optional (otherwise you copy the doctor link) | 5 min |
| 6 | YouTube or Google Drive | for the 2–3 minute demo video | **Required** | |

### Where each key goes

- **Locally:** copy `.env.example` to `.env` and paste the key after `GEMINI_API_KEY=`.
- **On Alternate Clouds:** add it as an environment variable on the service (see the deploy guide).
- **Never:** in GitHub, in the video, in screenshots, or in the submission PDF. The handbook says no API keys anywhere, and you confirm this in section 5.

### If the AI model gives an error

Model names change. If `/api/health` works but photo reading says "HTTP 404", open Google AI Studio, copy a current "Flash" model name, and set `GEMINI_MODEL` to it. For Groq, pick current text and vision models from their models page and set `OPENAI_MODEL` and `OPENAI_VISION_MODEL`.

Without any key the app still runs (offline mode): the rules engine, deadlines, letter, approvals and MCP all work. Only photo reading and AI summaries switch off.

## Tonight (16 October)

- [ ] Discord display name: `YourFirstName [Participant/TeamName]` (handbook page 3)
- [ ] Both teammates are in the Alternate Futures Discord server
- [ ] Run locally once (`README.md` → Run locally), try "Fill sample trip"
- [ ] Get the Gemini key and test reading a photo of a real medicine box
- [ ] Push to GitHub, build the image, **deploy on Alternate Clouds** (`docs/DEPLOY_ALTERNATE_CLOUDS.md`)
- [ ] Open the live URL on a phone and run the full flow, including the doctor page
- [ ] Ask technical support about anything that fails, early

## Tomorrow morning (17 October)

- [ ] Record the demo video (`docs/DEMO_SCRIPT.md`), upload as **unlisted** YouTube or Drive "anyone with the link"
- [ ] **Write your LinkedIn post yourselves** (AI-written posts are disqualified; grammar-only tools are fine). Structure from the handbook: project name and problem, what you built and your contributions, how you used Alternate Clouds and what you learned, screenshot or demo, project link, hashtags `#AgentikaAIHackathon #AIAutomation #AIHackathon #BuildInPublic`. One teammate posts, the other reshares.
- [ ] Take proof screenshots: Discord (both teammates) and Alternate Clouds dashboard (service + Active status, no keys visible)
- [ ] Fill `docs/SUBMISSION_TEMPLATE.md`, export to PDF, check every link opens in a private browser window
- [ ] Submit **before 12:45 PM PKT**. After that, don't change code or redeploy
- [ ] Keep the deployment running until the closing ceremony ends (6:00 PM)

## Rules to remember

- Communicate in **English** around moderators.
- Credit third-party code: `CREDITS.md` is included; mention AI assistance honestly.
- Practise the 6-minute finalist demo.
