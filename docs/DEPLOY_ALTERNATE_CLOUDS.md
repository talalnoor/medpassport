# Deploying MedPassport on Alternate Clouds

Deployment on Alternate Clouds is **mandatory**: local-only demos or hosting elsewhere are disqualified. Do this **tonight**, not tomorrow morning.

## How Alternate Clouds runs your app (from their docs)

- A service is defined by: a **container image**, the **port** it listens on, CPU / memory / storage, a region (or "Any"), and **environment variables**.
- The image must be **public**. Images on GitHub Container Registry are **private by default**, so make the package public.
- Use a **version tag** such as `1.0.0`. The platform refuses `latest` and `main` when you change an image.
- Each service gets a URL like `https://<slug>-app.alternatefutures.ai`.
- Most deployments find a provider within a few minutes; one stuck for about 25 minutes is marked failed and not charged.
- Logs: `acc services logs <id>`.

Docs: https://docs.alternatefutures.ai/guides/how-deployments-work

## Step 1: Put the code on GitHub

1. Create a **public** repository called `medpassport` (or give judges access).
2. Upload this folder. Check that `.env` is **not** uploaded (it is in `.gitignore`).

## Step 2: Build the image (choose A or B)

### A. No Docker on your laptop: let GitHub build it

1. In the repo, the workflow `.github/workflows/docker-image.yml` is already included.
2. Create a version tag: on GitHub go to **Releases → Draft a new release → tag `v1.0.0` → Publish**
   (or in a terminal: `git tag v1.0.0 && git push origin v1.0.0`).
3. Wait for the **Actions** tab to show a green tick (tests run first, then the build).
4. Go to your GitHub profile → **Packages → medpassport → Package settings → Change visibility → Public**.
5. Your image is: `ghcr.io/<your-github-username>/medpassport:1.0.0` (username in lowercase).

### B. Docker Desktop installed: push to Docker Hub

```bash
docker login
docker build --platform linux/amd64 -t <dockerhub-username>/medpassport:1.0.0 .
docker run -p 8000:8000 <dockerhub-username>/medpassport:1.0.0   # quick local check, open http://localhost:8000
docker push <dockerhub-username>/medpassport:1.0.0
```
Docker Hub repositories are public by default on free accounts.

## Step 3: Create the service on Alternate Clouds

1. Sign in at **clouds.alternatefutures.ai** and confirm your event credits with the organisers.
2. Open your project → **Add Service** → choose the option for a **custom container / Docker image** (ask the on-site technical support team if the menu name differs).
3. Fill in:
   | Field | Value |
   |---|---|
   | Image | `ghcr.io/<username>/medpassport:1.0.0` or `<dockerhub-username>/medpassport:1.0.0` |
   | Port | `8000` |
   | CPU / memory | 0.5 CPU, 512 MB to 1 GB RAM is enough |
   | Storage | 1 GB |
   | Region | Any (or the cheapest available) |
4. Environment variables (add as secrets if the form offers that):
   | Name | Value |
   |---|---|
   | `LLM_PROVIDER` | `gemini` (or `openai` for Groq) |
   | `GEMINI_API_KEY` | your key |
   | `PUBLIC_BASE_URL` | your service URL, e.g. `https://medpassport-app.alternatefutures.ai` (add after first deploy, then redeploy) |
   | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | optional, for emailing the doctor link |
5. Click **Deploy** and wait for the status **Active**.
6. Open the URL. Check `<URL>/api/health`: it should show your AI model name, not "offline mode".

**If it fails:** take a screenshot of the error, run `acc services logs <service-id>` if you use the CLI, and go to the technical support team with the error and the steps you took (the handbook asks for this).

## Step 4: Proof for the submission PDF

- Screenshot of the Alternate Clouds dashboard showing the **service and Active deployment status**.
- **Do not** show API keys or environment variable values in the screenshot.
- Keep the service running until the end of the closing ceremony (6:00 PM on 17 October). Check your credits.
- After 12:45 PM on 17 October, **do not change the code or redeploy** (you confirm this in the submission).

## Updating

Change code → new tag (`v1.0.1`) → wait for the build → in Alternate Clouds change the image tag to `1.0.1` → redeploy. The URL stays the same.

Note: the demo database lives inside the container, so a redeploy starts fresh (the sample trip is re-created automatically).
