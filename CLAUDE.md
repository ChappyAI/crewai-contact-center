# CrewAI Contact Center — Project Memory

## What It Is
Con.Nexus Contact Center AI Crew — a self-hosted HTTP service running 5 CrewAI agents for:
- Lead scoring & qualification
- Call quality analysis (QA)
- Routing optimization
- Campaign performance optimization
- Real-time sentiment tracking

## Deployed
- **Fly.io**: `https://crewai-contact-center.fly.dev`
- **Auth**: Currently disabled (no CREWAI_API_KEY set — add one for production)
- **Region**: iad (us-east-1)
- **Machine**: 6835e7ebd69658, shared CPU 1, 1GB RAM
- **Docker**: `Dockerfile` builds from `python:3.11-slim`, installs deps, runs `crewai_contact_center_api`

## API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Liveness probe, returns active kickoffs |
| GET | `/inputs` | Bearer | Lists required input keys (24 fields) |
| POST | `/kickoff` | Bearer | Starts crew run, returns `kickoff_id` |
| GET | `/status/{id}` | Bearer | Polls run status and result |

## Environment (`.env` — gitignored)
- MODEL=gpt-4-turbo
- OPENAI_API_KEY — set in Fly secrets and .env
- LANGSMITH_API_KEY — set in Fly secrets and .env
- PORT=8000, LOG_LEVEL=info, CREW_MAX_WORKERS=4

## Fly Secrets
Set via `flyctl secrets set`:
- MODEL, OPENAI_API_KEY, LANGSMITH_API_KEY, PORT, LOG_LEVEL, CREW_MAX_WORKERS, LANGSMITH_PROJECT, LANGSMITH_TRACING

## Key Files
- `src/crewai_contact_center/api.py` — FastAPI app, entrypoint `serve()`, loads `.env` via `load_dotenv()`
- `src/crewai_contact_center/crew.py` — CrewAI crew definition with 5 agents/tasks
- `src/crewai_contact_center/tools.py` — Custom tools: transcript analysis, lead scoring, QA scoring
- `src/crewai_contact_center/config/agents.yaml` — Agent role/goal/backstory definitions
- `src/crewai_contact_center/config/tasks.yaml` — Task descriptions and expected outputs
- `pyproject.toml` — Package metadata, includes `package-data` for YAML config files
- `Dockerfile` — Multi-stage build for Fly.io deployment
- `fly.toml` — Fly.io app config (auto-stop enabled, min_machines=0)

## Recent Session History (May 19, 2026)
1. Merged stale branches into main: `chore/update-env-config` (env config) and `claude/codebase-reference-docs-Jaucc` (references.md)
2. Fixed `api.py` to call `load_dotenv()` at startup (PR #2)
3. Fixed `pyproject.toml` to bundle `config/*.yaml` as package data (PR #3) — critical fix, without this the crew errors with `KeyError: 'score_lead_task'`
4. Deployed to Fly.io with secrets
5. Set up ngrok tunnel for local testing (may still be running)
6. Removed CREWAI_API_KEY from secrets — API currently has no auth

## Local Dev
```bash
cd /Users/seanchapman/DDev/containers/telephony/luhx/crewai-contact-center
.venv/bin/pip install -e ".[dev]"
python -c "from crewai_contact_center.api import serve; serve()"  # starts on :8000
```

## Common Issues
- **KeyError on task names**: Config YAMLs not bundled in package. Fix: `pyproject.toml` needs `[tool.setuptools.package-data]`
- **401 OpenAI errors**: Check `OPENAI_API_KEY` in Fly secrets: `flyctl secrets list -a crewai-contact-center`
- **Auth 401**: If `CREWAI_API_KEY` is set in secrets, all endpoints except `/health` require `Authorization: Bearer <key>`
