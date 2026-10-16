# Credits and third-party components

The handbook asks teams to credit third-party code and templates. MedPassport uses:

**Libraries**
- [FastAPI](https://fastapi.tiangolo.com/) (MIT) and Starlette (BSD-3): web framework
- [Uvicorn](https://www.uvicorn.org/) (BSD-3): web server
- [HTTPX](https://www.python-httpx.org/) (BSD-3): HTTP client
- [Pydantic](https://docs.pydantic.dev/) (MIT): input validation
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (MIT): MCP server
- [python-multipart](https://github.com/Kludex/python-multipart) (Apache-2.0): photo uploads
- [pytest](https://pytest.org/) (MIT): tests

**Data and APIs**
- [RxNorm API](https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html), US National Library of Medicine: brand to ingredient lookup
- Country rules compiled from official regulator websites and government travel advice; each rule links to its source in `app/data/country_rules.json`
- AI models: Google Gemini or an OpenAI-compatible API (e.g. Groq), chosen by environment variable

**Fonts**
- Bricolage Grotesque and Instrument Sans via Google Fonts (SIL Open Font License)

**AI assistance**
- Parts of the code and documentation were written with the help of an AI assistant (Claude by Anthropic) and reviewed by the team.
