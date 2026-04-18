# Con.Nexus Contact Center AI Crew

## Deploy to CrewAI Enterprise

```bash
# 1. Install CrewAI CLI (requires Rust toolchain)
pip install crewai

# 2. Login to CrewAI
crewai login

# 3. Deploy
cd /Users/seanchapman/telephony/Alltalkpro/crewai-contact-center
crewai deploy

# 4. Copy the new deployment URL and update .env.local:
#    CREWAI_API_URL=https://<new-crew-subdomain>.crewai.com
```

## Agents
- **Lead Scoring** - Score/qualify leads from call data
- **Call Quality** - QA scoring against 8 criteria
- **Routing Strategy** - Optimal call routing recommendations
- **Campaign Optimizer** - Outbound campaign tuning
- **Sentiment Tracker** - Real-time sentiment analysis

## API (once deployed)
```bash
# Get required inputs
GET /inputs

# Kick off crew
POST /kickoff
{"inputs": {"call_id": "...", "transcript": "...", ...}}

# Check status
GET /status/{kickoff_id}
```
