# PlaqueTracker — Prototype Monorepo

This repository contains prototype components for the PlaqueTracker oral health platform: device ingestion, hydrogel CV, analytics, reporting, and rewards.

Quickstart (run ingest service locally):

```powershell
docker-compose up --build
# then POST sample JSON to http://localhost:8080/v1/ingest
```

Hydrogel CV (train and run demo):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r hydrogel_cv/requirements.txt
python hydrogel_cv/model_train.py --out hydrogel_cv/model.pkl
python hydrogel_cv/scan.py --image path/to/scan.jpg --model hydrogel_cv/model.pkl
```

Analytics: see `services/analytics` for examples of feature extraction, model training, and plaque risk scoring.

Auth & Security: prototype auth service in `services/auth` (JWT), and security notes in `security/README.md`.

## Deploy (single public link on Render)

This repo now includes `render.yaml` for one-click deployment of the web app.

1. Push this repo to GitHub.
2. In Render, click **New +** → **Blueprint**.
3. Select your repo and deploy.
4. In Render service settings, set secret env vars:
	- `OPENROUTER_API_KEY`
	- `DEVICE_INGEST_KEY` (optional)

Render will provide one public URL for the full web UI (dashboard, trends, recommendations, etc.).

## Hydrogel AI Scan — Required Env Vars

The hydrogel scan page uses a vision-capable AI model (Option B) to analyse uploaded images and return real pH estimates, plaque zone scores, and brushing recommendations.

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes (for AI) | — | OpenAI or OpenRouter API key. Falls back to `OPENROUTER_API_KEY` if not set. |
| `OPENAI_MODEL` | No | `openai/gpt-4o-mini` | Vision-capable model name (OpenRouter or OpenAI model ID). |
| `OPENAI_BASE_URL` | No | `https://openrouter.ai/api/v1/chat/completions` | OpenAI-compatible endpoint. Change to `https://api.openai.com/v1/chat/completions` for direct OpenAI. |
| `OPENAI_TIMEOUT_SEC` | No | `30` | Request timeout in seconds for the AI vision call. |

**Quick setup on Render:**
- If you already have `OPENROUTER_API_KEY` set in Render, the hydrogel AI scan will automatically use it — no extra configuration needed.
- To use OpenAI directly, set `OPENAI_API_KEY` to your OpenAI key and `OPENAI_BASE_URL` to `https://api.openai.com/v1/chat/completions`.
- Never commit API keys to source code. Always use Render's secret env var panel.
