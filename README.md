# Con.Nexus Contact Center AI Crew

Self-hosted CrewAI multi-agent crew exposed as an HTTP service. API surface
matches CrewAI Enterprise so consumers can swap `CREWAI_API_URL` without code
changes.

## Agents

- **Lead Scoring** — Score/qualify leads from call data
- **Call Quality** — QA scoring against 8 criteria
- **Routing Strategy** — Optimal call routing recommendations
- **Campaign Optimizer** — Outbound campaign tuning
- **Sentiment Tracker** — Real-time sentiment analysis

## Run locally

```bash
cp .env.example .env   # then fill in OPENAI_API_KEY + CREWAI_API_KEY
pip install -e .
crewai_contact_center_api    # uvicorn on :8000
```

Or one-shot CLI (no HTTP):

```bash
crewai_contact_center
```

## Deploy to Fly.io

```bash
fly launch --no-deploy --copy-config       # first time only
fly secrets set OPENAI_API_KEY=sk-... CREWAI_API_KEY=$(openssl rand -hex 32) -a crewai-contact-center
fly deploy -a crewai-contact-center
```

Point `telephony-service` at the deploy:

```bash
fly secrets set CREWAI_API_URL=https://crewai-contact-center.fly.dev \
                CREWAI_API_KEY=<same-token> -a telephony-service
```

## API

`CREWAI_API_KEY` is **required** — the service refuses to start without it
(raises `RuntimeError` at import time). All endpoints except `/health` require
`Authorization: Bearer $CREWAI_API_KEY`. `POST /kickoff` and
`GET /status/{kickoff_id}` also require `x-tenant-id`.

```bash
# 1. List required inputs
curl -H "Authorization: Bearer $CREWAI_API_KEY" \
     https://crewai-contact-center.fly.dev/inputs

# 2. Kick off a run (returns kickoff_id immediately)
curl -X POST https://crewai-contact-center.fly.dev/kickoff \
     -H "Authorization: Bearer $CREWAI_API_KEY" \
     -H "x-tenant-id: $TENANT_ID" \
     -H "Content-Type: application/json" \
     -d @payload.json

# 3. Poll status
curl -H "Authorization: Bearer $CREWAI_API_KEY" \
     -H "x-tenant-id: $TENANT_ID" \
     https://crewai-contact-center.fly.dev/status/<kickoff_id>

# 4. Health (unauthenticated, for Fly checks)
curl https://crewai-contact-center.fly.dev/health
```

`payload.json` must include every key returned by `GET /inputs` under the
top-level `inputs` object. Its `inputs.tenant_id` must match the `x-tenant-id`
header.

Status values: `running`, `completed`, `failed`. Run state is in-memory; if
the machine restarts mid-run, the kickoff is lost and the parent must retry.

## Required inputs

See `GET /inputs` or the `REQUIRED_INPUTS` list in `src/crewai_contact_center/api.py`.
Missing or blank required keys are rejected with `422`; production callers must
send explicit real values instead of relying on synthetic defaults.
