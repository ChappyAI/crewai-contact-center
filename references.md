# crewai-contact-center — Codebase Reference

> Comprehensive reference for the `crewai-contact-center` repository (GitHub: `chappyai/crewai-contact-center`).
> Generated against branch `claude/codebase-reference-docs-Jaucc` on 2026-05-15.
> Supersedes the lightweight `INDEX.md` summary with full per-agent, per-task, per-tool, and per-config detail.

---

## 1. Purpose & Scope

`crewai-contact-center` defines the **Con.Nexus Contact Center AI Crew** — a multi-agent [CrewAI](https://docs.crewai.com) application that provides intelligence functions for the broader Chappy / Con.Nexus telephony platform. The crew is intended to be **deployed as a managed service on CrewAI Enterprise** and consumed as an HTTP API by the NestJS backend `con-nexus-telephony` (the `telephony-service` Fly app) via its pluggable AI-agency external connector layer.

The crew exposes five specialized agents that collectively cover the AI surface area of a contact center:

| Domain                | Agent                       | Backing task                  |
| --------------------- | --------------------------- | ----------------------------- |
| Lead scoring          | `lead_scoring_agent`        | `score_lead_task`             |
| Call quality / QA     | `call_quality_analyst`      | `evaluate_call_quality_task`  |
| Routing optimization  | `routing_strategist`        | `optimize_routing_task`       |
| Campaign optimization | `campaign_optimizer`        | `optimize_campaign_task`      |
| Real-time sentiment   | `sentiment_tracker`         | `analyze_sentiment_task`      |

The repository is intentionally tiny — five Python source files plus two YAML config files. All of the heavy lifting (LLM orchestration, tool execution, telemetry, REST surface) is delegated to the CrewAI framework and the CrewAI Enterprise hosting layer.

Out of scope:
- Persistent storage of results (consumed by upstream services).
- Tenant isolation, authn/authz (handled by the calling NestJS app).
- Realtime streaming (the crew is batch / request-response; streaming sentiment is approximated via small `transcript_chunk` invocations).
- Tests (none ship with the repo — see Section 13).

Source refs: [pyproject.toml](./pyproject.toml), [README.md](./README.md), [INDEX.md](./INDEX.md), [src/crewai_contact_center/crew.py](./src/crewai_contact_center/crew.py).

---

## 2. Tech Stack

| Layer                | Choice                                       | Notes                                                                                            |
| -------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Language             | Python `>=3.10`                              | Set in `pyproject.toml`. CrewAI 1.11 requires modern Python.                                     |
| Framework            | `crewai[tools] >= 1.11.0`                    | Single runtime dep. `[tools]` extra pulls the official tool catalog (although none used here).   |
| Decorator API        | `@CrewBase`, `@agent`, `@task`, `@crew`      | From `crewai.project`. YAML-config driven crew assembly.                                         |
| Process model        | `Process.sequential`                         | Tasks execute one-after-another using the framework's default manager.                           |
| LLM                  | Configured via env (`MODEL`, `OPENAI_API_KEY`) | Default `gpt-4-turbo` (from `.env.example`).                                                    |
| Tracing / observability | LangSmith via env (`LANGSMITH_API_KEY`)   | Optional; project name `con.nexus-telephony-agents`.                                             |
| Packaging            | `setuptools` / `setup.py`-free `pyproject`   | `packages.find` under `src/`. Console script `crewai_contact_center` → `main:run`.               |
| Lockfile             | `uv.lock` (`uv` package manager)             | Single `uv.lock` is the source of truth for reproducible installs (~900 KB).                     |
| Build / deploy       | CrewAI Enterprise CLI (`crewai deploy`)      | Builds a managed deployment exposing the standard CrewAI Enterprise REST surface.                |

Source refs: [pyproject.toml](./pyproject.toml), [.env.example](./.env.example).

---

## 3. Repository Layout (annotated tree)

```
crewai-contact-center/
├── .env                                       # Local env (gitignored in practice; example values committed)
├── .env.example                               # Required env vars for local run + tracing
├── .gitignore                                 # Standard Python, env, IDE, OS, plus .claude/.iceteam/etc tool dirs
├── INDEX.md                                   # Short overview (superseded by this references.md)
├── README.md                                  # CrewAI Enterprise deploy quickstart + agent list + API examples
├── pyproject.toml                             # Project metadata, single dep, console entrypoint, setuptools cfg
├── uv.lock                                    # uv-resolved lockfile (~900 KB; binary-equivalent dependency tree)
└── src/
    └── crewai_contact_center/                 # Importable package
        ├── __init__.py                        # Empty marker
        ├── main.py                            # `run()` entry — builds sample inputs, kicks off the crew
        ├── crew.py                            # ContactCenterCrew class — agent + task assembly
        ├── tools.py                           # Three @tool functions: analyze_transcript, score_lead, calculate_qa_score
        └── config/
            ├── agents.yaml                    # Role/goal/backstory for each of the five agents
            └── tasks.yaml                     # Description/expected_output/agent for each of the five tasks
```

What is intentionally **absent**:

- No `tests/` directory.
- No `Dockerfile` / `fly.toml` / Kubernetes manifests — CrewAI Enterprise owns the runtime.
- No `requirements.txt` — `pyproject.toml` + `uv.lock` are canonical.
- No `Makefile` / `tox.ini` / `noxfile.py`.
- No CI workflow files.

Source refs: filesystem listing under `/home/user/crewai-contact-center`.

---

## 4. Entry Point (`main.py` — inputs, outputs, invocation modes)

File: [`src/crewai_contact_center/main.py`](./src/crewai_contact_center/main.py)

```python
#!/usr/bin/env python
from crewai_contact_center.crew import ContactCenterCrew


def run():
    """Run the contact center crew."""
    inputs = { ... }                # 23-key dict (full list below)
    ContactCenterCrew().crew().kickoff(inputs=inputs)


if __name__ == "__main__":
    run()
```

### Invocation modes

| Mode                                | Command / trigger                                                | What happens                                                                 |
| ----------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Local CLI (console script)          | `crewai_contact_center` (after `pip install -e .` / `uv sync`)   | Calls `main.run()` with the hardcoded sample-inputs dictionary.              |
| Local CLI (module)                  | `python -m crewai_contact_center.main`                           | Same as above.                                                               |
| CrewAI CLI                          | `crewai run` (inside this project dir)                           | CrewAI auto-discovers `crew.py` decorators and runs the `@crew` callable.    |
| CrewAI Enterprise REST              | `POST /kickoff` with `{ "inputs": { ... } }`                     | Production path — see Section 11.                                            |
| Programmatic                        | `ContactCenterCrew().crew().kickoff(inputs={...})`               | Importable for embedding inside another Python process.                      |

### Sample inputs (from `main.py`)

The `run()` function ships a **representative payload** so the crew can be exercised end-to-end with a single command. Every key here corresponds to one or more `{placeholder}` slots in `tasks.yaml`:

| Input key            | Sample value                                                  | Consumed by task(s)                  |
| -------------------- | ------------------------------------------------------------- | ------------------------------------ |
| `call_id`            | `"example-call-001"`                                          | score_lead, evaluate_call_quality, analyze_sentiment |
| `tenant_id`          | `"tenant-001"`                                                | score_lead                           |
| `transcript`         | `"Customer: I want to cancel..."` (short string)              | score_lead, evaluate_call_quality    |
| `duration_seconds`   | `120`                                                         | score_lead, evaluate_call_quality    |
| `sentiment`          | `"negative"`                                                  | score_lead                           |
| `agent_notes`        | `"Customer considering cancellation"`                         | score_lead                           |
| `disposition`        | `"retention_attempt"`                                         | evaluate_call_quality                |
| `agent_id`           | `"agent-42"`                                                  | evaluate_call_quality, analyze_sentiment |
| `caller_number`      | `"+15551234567"`                                              | optimize_routing                     |
| `caller_history`     | `"3 previous calls, 2 complaints"`                            | optimize_routing                     |
| `available_agents`   | `"agent-1 (sales), agent-2 (retention), agent-3 (support)"`   | optimize_routing                     |
| `queue_depths`       | `"sales: 2, retention: 0, support: 5"`                        | optimize_routing                     |
| `sla_metrics`        | `"target: 30s, current avg: 22s"`                             | optimize_routing                     |
| `campaign_id`        | `"camp-001"`                                                  | optimize_campaign                    |
| `analysis_period`    | `"last 7 days"`                                               | optimize_campaign                    |
| `contact_rate`       | `"45"`                                                        | optimize_campaign                    |
| `answer_rate`        | `"32"`                                                        | optimize_campaign                    |
| `conversion_rate`    | `"8"`                                                         | optimize_campaign                    |
| `abandon_rate`       | `"3"`                                                         | optimize_campaign                    |
| `avg_handle_time`    | `"240"`                                                       | optimize_campaign                    |
| `list_remaining`     | `"5000"`                                                      | optimize_campaign                    |
| `transcript_chunk`   | `"I want to cancel"`                                          | analyze_sentiment                    |
| `previous_sentiment` | `"neutral"`                                                   | analyze_sentiment                    |
| `elapsed_seconds`    | `"60"`                                                        | analyze_sentiment                    |

All values are passed verbatim into the Jinja-style `{placeholder}` substitution that CrewAI applies to each task's `description` string before the LLM call.

### Outputs

`Crew.kickoff()` returns a `CrewOutput` whose `.raw` field carries the **final task's** output by default (with sequential process). With the current task order, that is the `analyze_sentiment_task` JSON. Intermediate task outputs are still emitted to stdout/logs because every agent is built with `verbose=True` and the crew with `verbose=True`.

`main.run()` itself **discards the return value** — it is a smoke-test entry point. Production callers (see Section 11) consume the result through the REST API and the polling pattern documented there.

Source refs: [main.py](./src/crewai_contact_center/main.py), [crew.py](./src/crewai_contact_center/crew.py), [tasks.yaml](./src/crewai_contact_center/config/tasks.yaml).

---

## 5. Crew Definition (`crew.py` — agents, tasks, process, manager)

File: [`src/crewai_contact_center/crew.py`](./src/crewai_contact_center/crew.py)

The crew is assembled with the CrewAI decorator API:

```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from crewai_contact_center.tools import analyze_transcript, calculate_qa_score, score_lead


@CrewBase
class ContactCenterCrew:
    agents_config = "config/agents.yaml"
    tasks_config  = "config/tasks.yaml"

    @agent
    def lead_scoring_agent(self) -> Agent: ...
    @agent
    def call_quality_analyst(self) -> Agent: ...
    @agent
    def routing_strategist(self) -> Agent: ...
    @agent
    def campaign_optimizer(self) -> Agent: ...
    @agent
    def sentiment_tracker(self) -> Agent: ...

    @task
    def score_lead_task(self) -> Task: ...
    @task
    def evaluate_call_quality_task(self) -> Task: ...
    @task
    def optimize_routing_task(self) -> Task: ...
    @task
    def optimize_campaign_task(self) -> Task: ...
    @task
    def analyze_sentiment_task(self) -> Task: ...

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
```

### Mechanics
- `@CrewBase` reads `agents_config` / `tasks_config` paths relative to the package directory and exposes the parsed YAML as `self.agents_config` / `self.tasks_config` dicts (keyed by the top-level YAML keys).
- Each `@agent` method returns an `Agent` whose `config=` parameter receives the matching dict from `agents.yaml`. CrewAI then populates `role`, `goal`, `backstory` (and any additional supported keys) from that dict.
- Each `@task` method returns a `Task` whose `config=` parameter receives the matching dict from `tasks.yaml`. The dict supplies `description`, `expected_output`, and `agent` (a string referencing the `@agent` method name on the same class — CrewAI resolves it).
- `@crew` aggregates **the order in which `@agent` / `@task` methods are declared** into `self.agents` / `self.tasks` lists. The task order is therefore the execution order under `Process.sequential`.

### Process & manager
- **Process**: `Process.sequential`. Tasks fire in declaration order:
  1. `score_lead_task`
  2. `evaluate_call_quality_task`
  3. `optimize_routing_task`
  4. `optimize_campaign_task`
  5. `analyze_sentiment_task`
- **Manager agent**: none configured. Sequential process does not require a manager; an LLM-driven manager would be set via `manager_agent=` or `manager_llm=` on the `Crew(...)` constructor for `Process.hierarchical`.
- **Context wiring**: no explicit `context=` is set on any task. Each task therefore runs with only the kickoff `inputs` plus its agent's tool outputs — there is no automatic chaining of "task N's output is task N+1's context". (This is a deliberate design choice — each task is independent and answers a different analytical question; see Section 7 for the per-task description payloads.)
- **Verbose**: all five agents and the crew itself are `verbose=True`, which makes the CrewAI logger emit per-step thoughts and tool calls. This is helpful in dev and acceptable in CrewAI Enterprise (the platform captures these logs); it can be flipped off when stricter production logging is desired.

### Tool wiring (summary)

| Agent                  | Attached tools                                  |
| ---------------------- | ----------------------------------------------- |
| `lead_scoring_agent`   | `analyze_transcript`, `score_lead`              |
| `call_quality_analyst` | `analyze_transcript`, `calculate_qa_score`      |
| `routing_strategist`   | *(none — pure LLM reasoning)*                   |
| `campaign_optimizer`   | *(none — pure LLM reasoning)*                   |
| `sentiment_tracker`    | `analyze_transcript`                            |

The two tool-less agents are intentionally **LLM-only** reasoners over the structured inputs supplied by the task description — they don't need a computation helper.

Source refs: [crew.py](./src/crewai_contact_center/crew.py), [tools.py](./src/crewai_contact_center/tools.py).

---

## 6. Agents

Every agent is sourced from `config/agents.yaml` (see Section 9 for the raw file). The `Agent(...)` constructor uses `config=self.agents_config[<key>]` plus optional `tools=` / `verbose=True` overrides in `crew.py`.

### 6.1 `lead_scoring_agent`

| Field         | Value |
| ------------- | ----- |
| **YAML key**  | `lead_scoring_agent` |
| **Role**      | "Lead Scoring Specialist" |
| **Goal**      | Score and qualify inbound/outbound leads based on call data, sentiment, and engagement signals. |
| **Backstory** | Expert lead scoring analyst for a contact center. Analyzes caller data, transcripts, sentiment, and engagement patterns to assign lead quality scores. Prioritizes leads most likely to convert and flags high-value opportunities. |
| **Tools**     | `analyze_transcript`, `score_lead` |
| **Verbose**   | `True` |
| **LLM**       | Inherits crew default (env `MODEL`, default `gpt-4-turbo`) |
| **Assigned task** | `score_lead_task` |
| **Source**    | [agents.yaml L1-7](./src/crewai_contact_center/config/agents.yaml), [crew.py L22-28](./src/crewai_contact_center/crew.py) |

### 6.2 `call_quality_analyst`

| Field         | Value |
| ------------- | ----- |
| **YAML key**  | `call_quality_analyst` |
| **Role**      | "Call Quality Analyst" |
| **Goal**      | Evaluate call quality, agent performance, and compliance adherence from call transcripts and metadata. |
| **Backstory** | Seasoned QA analyst. Scores calls on greeting quality, active listening, problem resolution, compliance, and professionalism. Identifies coaching opportunities and compliance risks. |
| **Tools**     | `analyze_transcript`, `calculate_qa_score` |
| **Verbose**   | `True` |
| **LLM**       | Inherits crew default |
| **Assigned task** | `evaluate_call_quality_task` |
| **Source**    | [agents.yaml L9-15](./src/crewai_contact_center/config/agents.yaml), [crew.py L30-36](./src/crewai_contact_center/crew.py) |

### 6.3 `routing_strategist`

| Field         | Value |
| ------------- | ----- |
| **YAML key**  | `routing_strategist` |
| **Role**      | "Routing Strategy Specialist" |
| **Goal**      | Optimize call routing decisions based on caller history, agent skills, queue metrics, and predicted outcomes. |
| **Backstory** | Workforce-optimization expert. Analyzes real-time queue depths, agent skills, caller history, and predicted handle times to recommend optimal routing. Balances service levels with agent utilization. |
| **Tools**     | *(none)* |
| **Verbose**   | `True` |
| **LLM**       | Inherits crew default |
| **Assigned task** | `optimize_routing_task` |
| **Source**    | [agents.yaml L17-23](./src/crewai_contact_center/config/agents.yaml), [crew.py L38-40](./src/crewai_contact_center/crew.py) |

### 6.4 `campaign_optimizer`

| Field         | Value |
| ------------- | ----- |
| **YAML key**  | `campaign_optimizer` |
| **Role**      | "Campaign Performance Optimizer" |
| **Goal**      | Analyze outbound campaign metrics and recommend dial strategy, timing, and list adjustments. |
| **Backstory** | Predictive-dialing expert. Analyzes contact rates, answer rates, abandonment rates, and time-of-day patterns to optimize campaign performance. Recommends list segmentation and dial pacing adjustments. |
| **Tools**     | *(none)* |
| **Verbose**   | `True` |
| **LLM**       | Inherits crew default |
| **Assigned task** | `optimize_campaign_task` |
| **Source**    | [agents.yaml L25-31](./src/crewai_contact_center/config/agents.yaml), [crew.py L42-44](./src/crewai_contact_center/crew.py) |

### 6.5 `sentiment_tracker`

| Field         | Value |
| ------------- | ----- |
| **YAML key**  | `sentiment_tracker` |
| **Role**      | "Real-Time Sentiment Analyst" |
| **Goal**      | Monitor caller sentiment in real-time and trigger escalation or coaching interventions. |
| **Backstory** | Conversation-intelligence specialist. Detects frustration, satisfaction, confusion, and urgency in real time from transcript chunks. Triggers supervisor alerts for at-risk calls and provides de-escalation coaching tips. |
| **Tools**     | `analyze_transcript` |
| **Verbose**   | `True` |
| **LLM**       | Inherits crew default |
| **Assigned task** | `analyze_sentiment_task` |
| **Source**    | [agents.yaml L33-39](./src/crewai_contact_center/config/agents.yaml), [crew.py L46-52](./src/crewai_contact_center/crew.py) |

> **Note on LLM selection.** Neither `crew.py` nor `agents.yaml` sets `llm=` on any agent, so each falls back to CrewAI's default LLM resolution. CrewAI looks at the `MODEL` env var (set by `.env.example` to `gpt-4-turbo`) and selects the matching provider client (here, OpenAI via `OPENAI_API_KEY`). Different agents can be pinned to different models by adding `llm:` keys to `agents.yaml`, but this repo does not.

---

## 7. Tasks

Every task is sourced from `config/tasks.yaml`. Each `Task(...)` constructor uses `config=self.tasks_config[<key>]`, no `context=` chains, and no overrides.

### 7.1 `score_lead_task`

| Field             | Value |
| ----------------- | ----- |
| **YAML key**      | `score_lead_task` |
| **Agent**         | `lead_scoring_agent` |
| **Description**   | Analyze the following call data and score the lead on a 1-100 scale. Consider: caller engagement level, sentiment trajectory, call duration, questions asked, buying signals, and objections raised. Substituted placeholders: `{call_id}`, `{tenant_id}`, `{transcript}`, `{duration_seconds}`, `{sentiment}`, `{agent_notes}`. |
| **Expected output** | JSON with: `score (1-100)`, `qualification (hot/warm/cold)`, `reasoning`, `recommended_action (schedule_callback/send_collateral/close/nurture)`, `priority_rank`, `key_signals`. |
| **Context**       | *(none — independent task)* |
| **Source**        | [tasks.yaml L1-17](./src/crewai_contact_center/config/tasks.yaml), [crew.py L54-56](./src/crewai_contact_center/crew.py) |

### 7.2 `evaluate_call_quality_task`

| Field             | Value |
| ----------------- | ----- |
| **YAML key**      | `evaluate_call_quality_task` |
| **Agent**         | `call_quality_analyst` |
| **Description**   | Score this completed call against QA criteria. Substituted placeholders: `{call_id}`, `{transcript}`, `{duration_seconds}`, `{disposition}`, `{agent_id}`. |
| **Expected output** | JSON with: `overall_score (1-100)`, per-criterion scores (`greeting`, `listening`, `problem_id`, `solution`, `compliance`, `professionalism`, `efficiency`, `resolution`), `strengths`, `improvements`, `compliance_flags`, `coaching_recommendations`. |
| **Context**       | *(none)* |
| **Source**        | [tasks.yaml L19-32](./src/crewai_contact_center/config/tasks.yaml), [crew.py L58-60](./src/crewai_contact_center/crew.py) |

> **Schema-vs-tool gap (informational).** The expected_output mentions 8 criteria (greeting, listening, problem_id, solution, compliance, professionalism, efficiency, resolution), while the `calculate_qa_score` tool only takes 5 (greeting_quality, active_listening, problem_resolution, compliance, professionalism). The LLM will need to reason about the additional axes or call the tool for a subset. See Section 13.

### 7.3 `optimize_routing_task`

| Field             | Value |
| ----------------- | ----- |
| **YAML key**      | `optimize_routing_task` |
| **Agent**         | `routing_strategist` |
| **Description**   | Recommend optimal routing for this incoming call. Substituted placeholders: `{caller_number}`, `{caller_history}`, `{available_agents}`, `{queue_depths}`, `{sla_metrics}`. |
| **Expected output** | JSON with: `recommended_queue`, `recommended_agent_id`, `priority (1-10)`, `reasoning`, `estimated_wait_seconds`, `skill_match_score`. |
| **Context**       | *(none)* |
| **Source**        | [tasks.yaml L34-46](./src/crewai_contact_center/config/tasks.yaml), [crew.py L62-64](./src/crewai_contact_center/crew.py) |

### 7.4 `optimize_campaign_task`

| Field             | Value |
| ----------------- | ----- |
| **YAML key**      | `optimize_campaign_task` |
| **Agent**         | `campaign_optimizer` |
| **Description**   | Analyze campaign performance and recommend optimizations. Substituted placeholders: `{campaign_id}`, `{analysis_period}`, `{contact_rate}`, `{answer_rate}`, `{conversion_rate}`, `{abandon_rate}`, `{avg_handle_time}`, `{list_remaining}`. |
| **Expected output** | JSON with: `recommendations` (`dial_rate_adjustment`, `best_call_times`, `list_segmentation_suggestions`, `agent_allocation`), `predicted_improvement`, `risk_factors`, `priority_actions`. |
| **Context**       | *(none)* |
| **Source**        | [tasks.yaml L48-64](./src/crewai_contact_center/config/tasks.yaml), [crew.py L66-68](./src/crewai_contact_center/crew.py) |

### 7.5 `analyze_sentiment_task`

| Field             | Value |
| ----------------- | ----- |
| **YAML key**      | `analyze_sentiment_task` |
| **Agent**         | `sentiment_tracker` |
| **Description**   | Analyze real-time sentiment from this transcript chunk. Substituted placeholders: `{call_id}`, `{agent_id}`, `{transcript_chunk}`, `{previous_sentiment}`, `{elapsed_seconds}`. |
| **Expected output** | JSON with: `sentiment (positive/neutral/negative)`, `score (0-1)`, `emotions`, `trend (improving/stable/declining)`, `alert (true/false)`, `coaching_tip` (if needed). |
| **Context**       | *(none)* |
| **Source**        | [tasks.yaml L66-79](./src/crewai_contact_center/config/tasks.yaml), [crew.py L70-72](./src/crewai_contact_center/crew.py) |

---

## 8. Custom Tools (`tools.py` — every tool, signature, what it does)

File: [`src/crewai_contact_center/tools.py`](./src/crewai_contact_center/tools.py)

All three tools are defined with the `@tool("<display name>")` decorator from `crewai.tools`. The decorator wraps the function so CrewAI can present it to the LLM with its docstring as the description and its type hints as the schema.

### 8.1 `analyze_transcript`

```python
@tool("Analyze Call Transcript")
def analyze_transcript(transcript: str) -> str:
    """Analyze a call transcript for key topics, sentiment indicators, and action items.
    Returns structured analysis."""
```

- **Inputs**: `transcript: str`.
- **Algorithm**:
  1. Counts occurrences of two fixed word lists (`negative_words`, `positive_words`) — keyword sentiment.
     - Negative list: `frustrated, angry, cancel, terrible, worst, complaint, waiting`.
     - Positive list: `thank, great, excellent, happy, appreciate, resolved, helpful`.
  2. Computes sentiment label by majority count (`positive` / `negative` / `neutral`).
  3. Extracts up to 10 "topics" — unique lowercased tokens longer than 7 chars after stripping `.,!?`.
  4. Reports word count and char count.
- **Output**: Multi-line string with `Sentiment`, `Key topics`, `Word count`, `Transcript length`.
- **Used by**: `lead_scoring_agent`, `call_quality_analyst`, `sentiment_tracker`.

### 8.2 `score_lead`

```python
@tool("Score Lead Quality")
def score_lead(
    engagement_level: str,
    call_duration_seconds: int,
    sentiment: str,
    questions_asked: int = 0,
) -> str:
    """Score a lead based on engagement metrics. Returns a quality score 1-100."""
```

- **Inputs**: `engagement_level` (expected `"high"` / `"low"` / other), `call_duration_seconds: int`, `sentiment` (`"positive"` / `"negative"` / other), `questions_asked: int = 0`.
- **Algorithm (numeric)**:
  - Base: `50`.
  - Engagement: `+20` for `high`, `-15` for `low`, else `0`.
  - Duration tiers: `> 300s → +15`, `> 120s → +10`, `< 30s → -10`, else `0`.
  - Sentiment: `+15` for positive, `-10` for negative.
  - Questions: `+5 per question`, capped at `+20`.
  - Clamped to `[1, 100]`.
- **Bucketing**: `> 75 → hot`, `> 45 → warm`, else `cold`.
- **Recommended action**: `> 75 → schedule_callback`, `> 45 → nurture`, else `low_priority`.
- **Output**: Three-line string `Lead Score: NN/100`, `Qualification: ...`, `Recommended Action: ...`.
- **Used by**: `lead_scoring_agent`.

### 8.3 `calculate_qa_score`

```python
@tool("Calculate QA Score")
def calculate_qa_score(
    greeting_quality: int,
    active_listening: int,
    problem_resolution: int,
    compliance: int,
    professionalism: int,
) -> str:
    """Calculate overall QA score from individual criteria (each 1-10). Returns detailed scorecard."""
```

- **Inputs**: Five `int` criteria each on `1-10`.
- **Algorithm**:
  - `total = sum(criteria.values())`.
  - `overall = int(total / 5 * 10)` → projects onto a `1-100` scale.
  - Strengths: criteria with score `>= 8`. Improvements: criteria with score `<= 5`.
  - Renders each criterion as a 10-cell unicode bar (`U+2588` filled, `U+2591` empty).
- **Output**: Multi-line scorecard with header, bars, and (optional) Strengths / Needs Improvement lines.
- **Used by**: `call_quality_analyst`.

> **Tool-vs-task surface area**. The `calculate_qa_score` tool only covers five of the eight QA dimensions promised by `evaluate_call_quality_task.expected_output` (it omits `problem_id`, `solution`, `efficiency`, `resolution` — note `problem_resolution` collapses two of those). The agent therefore must reason qualitatively to fill the gap. This is a known divergence (Section 13).

Source ref: [tools.py](./src/crewai_contact_center/tools.py).

---

## 9. Configuration (`agents.yaml`, `tasks.yaml` — full content references)

### 9.1 `config/agents.yaml`

Five top-level keys, each with `role`, `goal`, `backstory`. No tools, no LLM, no `allow_delegation`, no `max_iter`, no `memory`. All such defaults are inherited from CrewAI.

| Key                     | Role label                       | One-line goal                                                                |
| ----------------------- | -------------------------------- | ---------------------------------------------------------------------------- |
| `lead_scoring_agent`    | Lead Scoring Specialist          | Score/qualify leads from call data, sentiment, engagement.                   |
| `call_quality_analyst`  | Call Quality Analyst             | Score calls on greeting, listening, resolution, compliance, professionalism. |
| `routing_strategist`    | Routing Strategy Specialist      | Optimize routing using queues, skills, history, predicted outcomes.          |
| `campaign_optimizer`    | Campaign Performance Optimizer   | Tune dial strategy, timing, list segmentation.                               |
| `sentiment_tracker`     | Real-Time Sentiment Analyst      | Detect frustration / satisfaction / urgency; trigger alerts and coaching.    |

Full text: [agents.yaml](./src/crewai_contact_center/config/agents.yaml).

### 9.2 `config/tasks.yaml`

Five top-level keys, each with `description`, `expected_output`, `agent`. All `description` blocks include literal `{placeholder}` slots that get substituted from `kickoff(inputs=...)` (see Section 4).

| Key                            | Agent                  | Inputs consumed                                                                                          | Output schema (high level)                                                            |
| ------------------------------ | ---------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `score_lead_task`              | lead_scoring_agent     | call_id, tenant_id, transcript, duration_seconds, sentiment, agent_notes                                | score, qualification, reasoning, recommended_action, priority_rank, key_signals       |
| `evaluate_call_quality_task`   | call_quality_analyst   | call_id, transcript, duration_seconds, disposition, agent_id                                            | overall_score, 8 criteria, strengths, improvements, compliance_flags, coaching         |
| `optimize_routing_task`        | routing_strategist     | caller_number, caller_history, available_agents, queue_depths, sla_metrics                              | recommended_queue, recommended_agent_id, priority, reasoning, est_wait, skill_match    |
| `optimize_campaign_task`       | campaign_optimizer     | campaign_id, analysis_period, contact_rate, answer_rate, conversion_rate, abandon_rate, avg_handle_time, list_remaining | recommendations(4 sub-keys), predicted_improvement, risk_factors, priority_actions     |
| `analyze_sentiment_task`       | sentiment_tracker      | call_id, agent_id, transcript_chunk, previous_sentiment, elapsed_seconds                                | sentiment, score, emotions, trend, alert, coaching_tip                                 |

Full text: [tasks.yaml](./src/crewai_contact_center/config/tasks.yaml).

---

## 10. Environment Variables

Defined in `.env.example`:

| Variable               | Default / example                | Required? | Purpose                                                                                  |
| ---------------------- | -------------------------------- | --------- | ---------------------------------------------------------------------------------------- |
| `MODEL`                | `gpt-4-turbo`                    | Yes (effective) | LLM model identifier consumed by CrewAI's default LLM resolution.                  |
| `OPENAI_API_KEY`       | *(secret)*                       | Yes       | OpenAI auth — required when `MODEL` resolves to an OpenAI model.                         |
| `LANGSMITH_API_KEY`    | *(secret)*                       | Optional  | Enables LangSmith tracing of CrewAI runs.                                                |
| `LANGSMITH_PROJECT`    | `con.nexus-telephony-agents`     | Optional  | LangSmith project bucket.                                                                |

> `.env` in the repo currently mirrors a subset of `.env.example` with placeholder values. `.gitignore` excludes `.env`, `.env.local`, `.env.production` from future commits, but the placeholder `.env` already in the repo is harmless (no real secrets).

When deployed on CrewAI Enterprise, these env vars are set through the CrewAI Enterprise dashboard / CLI rather than `.env`.

Additional implicit env vars (set by CrewAI / dependencies as needed): `OTEL_*`, `LITELLM_*`, `CREW_*`. None are hardcoded by this repo.

Source refs: [.env.example](./.env.example), [.env](./.env), [.gitignore](./.gitignore).

---

## 11. Deployment (CrewAI Enterprise — login/deploy/run flow, REST API surface)

### 11.1 Build / publish flow

From [README.md](./README.md):

```bash
# 1. Install CrewAI CLI (Rust toolchain required for some sub-deps)
pip install crewai

# 2. Authenticate with CrewAI Enterprise
crewai login

# 3. Deploy this directory
cd /path/to/crewai-contact-center
crewai deploy

# 4. Copy the new deployment URL and update the consumer's .env.local:
#    CREWAI_API_URL=https://<new-crew-subdomain>.crewai.com
```

`crewai deploy` packages the project (`pyproject.toml` + `src/`), uploads to CrewAI Enterprise, builds the container, and provisions a managed REST endpoint. Each deploy produces a **new subdomain** under `*.crewai.com` that the consumer must pin via env. No CI is wired up — deploys are operator-initiated.

### 11.2 REST surface exposed by CrewAI Enterprise

The CrewAI Enterprise runtime auto-generates these endpoints from the `@CrewBase` class:

| Method | Path                       | Purpose                                                                            | Auth                                |
| ------ | -------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------- |
| GET    | `/inputs`                  | Discover the input keys the crew expects.                                          | Bearer token (deployment API key)   |
| POST   | `/kickoff`                 | Start an asynchronous crew run. Body must include every key returned by `GET /inputs` under `inputs`; `inputs.tenant_id` must match `x-tenant-id`. Returns `{ kickoff_id }`. | Bearer token + `x-tenant-id` |
| GET    | `/status/{kickoff_id}`     | Poll tenant-scoped status. Returns `{ state, result }`. `state` ∈ `pending`, `running`, `completed`, `error`. | Bearer token + `x-tenant-id` |
| GET    | `/health`                  | Liveness probe (used by consumer connector's `healthCheck()`).                     | None                                |

The consumer integration (NestJS `CrewAiConnector`, see Section 12) uses the kickoff-then-poll pattern with a 2s poll interval and up to 60 attempts (~2 minutes total) before timing out.

### 11.3 Example end-to-end call

```bash
# Find required inputs
curl -H "Authorization: Bearer $CREWAI_API_KEY" \
  "$CREWAI_API_URL/inputs"

# Kick off the crew
curl -X POST "$CREWAI_API_URL/kickoff" \
  -H "Authorization: Bearer $CREWAI_API_KEY" \
  -H "x-tenant-id: $TENANT_ID" \
  -H "Content-Type: application/json" \
  -d @payload.json
# → { "kickoff_id": "kid_..." }

# Poll until terminal
curl -H "Authorization: Bearer $CREWAI_API_KEY" \
  -H "x-tenant-id: $TENANT_ID" \
  "$CREWAI_API_URL/status/kid_..."
# → { "state": "completed", "result": "..." }
```

`payload.json` must contain every required input returned by `GET /inputs`; missing or blank required fields are rejected, and `inputs.tenant_id` must match `x-tenant-id`.

Source refs: [README.md](./README.md), `con-nexus-telephony/src/modules/ai-agency/connectors/crewai-connector.ts`.

---

## 12. Internal Dependencies & Consumers

### 12.1 Producer (this repo)

`crewai-contact-center` has **no internal dependencies** — it does not import from any sibling project in the `telephony-service-bundle` monorepo and only depends on PyPI (`crewai[tools]`). It is a leaf service.

### 12.2 Consumer: `con-nexus-telephony` (NestJS backend, Fly app `telephony-service`)

The primary consumer is the NestJS app that runs the contact center. It wires the deployed CrewAI Enterprise endpoint in two places:

1. **Env vars** (`con-nexus-telephony/.env.example`):
   ```
   CREWAI_API_URL=http://localhost:8000      # or https://<crew>.crewai.com
   CREWAI_API_KEY=your-crewai-key
   ```
2. **Constants loader** (`con-nexus-telephony/src/config/env.constants.ts`):
   ```ts
   AI.EXTERNAL.CREWAI_URL: process.env.CREWAI_API_URL,
   AI.EXTERNAL.CREWAI_KEY: process.env.CREWAI_API_KEY,
   ```
3. **Connector**: `con-nexus-telephony/src/modules/ai-agency/connectors/crewai-connector.ts` (`CrewAiConnector`).
4. **Registration**: `con-nexus-telephony/src/modules/ai-agency/connectors/external-agency.service.ts` registers the connector at startup **only when `CREWAI_API_URL` is set**. Each connector is wrapped in a per-name circuit breaker (`ext-connector:crewai`) using the global `CIRCUIT_BREAKER.*` thresholds.
5. **Interfaces**: `con-nexus-telephony/src/modules/ai-agency/interfaces/external-connector.interface.ts` declares the connector type union as `"crewai" | "langgraph" | "custom"`; the agent interface (`ai-agent.interface.ts`) accepts `connector: "langgraph" | "crewai" | string` so any AI agent record can route to this crew.

### 12.3 HTTP invocation pattern (from the `CrewAiConnector`)

```ts
// 1. POST /kickoff with inputs
fetch(`${baseUrl}/kickoff`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
  body: JSON.stringify({
    inputs: {
      tenant_id: request.tenantId,
      call_id: request.callId,
      agent_id: request.agentId,
      ...request.inputs,
    },
  }),
  signal: controller.signal,        // AbortController, default 120s timeout
});

// 2. Poll GET /status/{kickoff_id} every 2s, up to 60 attempts
//    Returns when state === "completed" | "error", else timeout.

// Auxiliary:
//   GET /inputs   — connector.getInputs()
//   GET /health   — connector.healthCheck()
```

Default request timeout: `120_000 ms` (overridable per request). The connector returns an `ExternalAgencyResponse` shaped `{ success, output, latencyMs, error?, metadata? }`.

### 12.4 Use cases the consumer routes through this crew

Per the `con-nexus-telephony` AI module conventions and feature-flag map (see super-repo CLAUDE.md), the use cases enabled when `CREWAI_API_URL` is configured are:

- **Lead scoring** — invoked post-call or mid-call to populate dialer prioritization.
- **Call quality / QA** — invoked on hangup events (`FEATURE_QUALITY_SCORING`).
- **Routing optimization** — invoked on inbound call ringing to recommend queue / agent (`FEATURE_REALTIME_COACHING` adjacent).
- **Campaign optimization** — invoked on a schedule (campaign worker tick) to retune dial pacing.
- **Sentiment analysis** — invoked per transcript chunk during a call (`FEATURE_SENTIMENT_ANALYSIS`).

Each use case maps 1:1 to one of the five tasks defined in this repo. Because the `Process.sequential` crew runs *all five tasks per kickoff*, the consumer in practice supplies all 23 input keys even when it only wants one answer; the irrelevant outputs are discarded. (A future refactor could split the crew into five smaller crews — see Section 13.)

### 12.5 Other potential consumers

- `telephony-service-frontend` (sibling SPA + Express) — no direct calls; AI features flow through the NestJS backend.
- `langgraph-contact-center` (sibling LangGraph project) — independent. The connector union accepts `"langgraph"` so both can coexist.
- `agent-website-service` — no references found.

Search across the monorepo confirms `CREWAI_API_URL` / `crewai-contact-center` references appear only in `con-nexus-telephony` (env + connector + interfaces), `telephony-service-bundle` (top-level docs), and `telephony-service-frontend` (a planning doc, no code).

Source refs: `con-nexus-telephony/src/modules/ai-agency/connectors/crewai-connector.ts`, `con-nexus-telephony/src/modules/ai-agency/connectors/external-agency.service.ts`, `con-nexus-telephony/src/config/env.constants.ts`, `con-nexus-telephony/.env.example`.

---

## 13. Known Gaps

| # | Gap                                                                                                                | Impact                                                                                                                | Suggested fix                                                                                              |
| - | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 1 | **No tests.** Repo contains no `tests/`, no `pytest` invocation, no fixtures.                                       | Behavior changes in `tools.py` or YAML can silently regress.                                                          | Add `pytest` + offline tests for the three deterministic tools; record CrewAI runs with VCR / cassettes.    |
| 2 | **No CI.** No GitHub Actions, no pre-commit hooks.                                                                 | Style/quality drift; nothing prevents merging broken YAML.                                                            | Add CI to run `python -m crewai_contact_center.main --dry-run`, lint with `ruff`, validate YAML.            |
| 3 | **Process is monolithic-sequential.** Every kickoff runs all five tasks even if the caller only needs sentiment.   | Wasted LLM tokens / latency for narrow use cases.                                                                     | Split into five crews (one per task) or use `Process.hierarchical` with a manager that picks branches.     |
| 4 | **No `context=` chaining between tasks.**                                                                          | Tasks can't reuse upstream output (e.g., sentiment score from analyzed transcript) without re-deriving.               | Where helpful, add `context=[score_lead_task]` etc. to downstream tasks.                                   |
| 5 | **Tool surface narrower than task `expected_output`.** `calculate_qa_score` covers 5/8 criteria.                   | The LLM must hallucinate or infer the other three criteria.                                                           | Either reduce the expected_output to 5 criteria or expand the tool to 8 numeric inputs.                    |
| 6 | **Keyword-only sentiment in `analyze_transcript`.**                                                                | Brittle for any non-English transcript and for polite phrasings (e.g., "I am not happy" trips no keyword).            | Switch to a small classifier or use the LLM itself; mark the function as heuristic-only.                   |
| 7 | **No LLM pinning per agent.**                                                                                      | All agents use the same `MODEL`, regardless of cost/latency profile (sentiment chunks are tiny, QA is heavy).         | Add `llm:` keys in `agents.yaml`; cheap model for `sentiment_tracker`, larger for `call_quality_analyst`.   |
| 8 | **No structured output validation.**                                                                               | Consumer treats JSON returned in `result` as a string; malformed JSON would slip through.                              | Use CrewAI `output_json=` / Pydantic models on each Task to enforce schemas.                                |
| 9 | **`.env` committed with placeholders.**                                                                            | Cosmetic; the file is in `.gitignore` for future updates but already present in history.                              | Remove `.env` from the tree; leave only `.env.example`.                                                    |
| 10 | **No request/agent observability surfaced from the crew side.**                                                   | Only LangSmith (if configured) sees inside the crew; consumer relies on CrewAI Enterprise dashboard for failures.     | Emit structured `print()` / logger calls into each tool; expose tool-level metrics if CrewAI supports it.   |
| 11 | **Hard-coded sample inputs in `main.py`.**                                                                        | The local entry point is a demo; real local runs require editing the source.                                          | Accept inputs from CLI args / a JSON file.                                                                  |
| 12 | **CrewAI version pin is permissive (`>=1.11.0`).**                                                                | A future CrewAI 2.x could break the `@CrewBase` decorator surface.                                                    | Pin to `~=1.11` or `>=1.11,<2`.                                                                            |

---

## 14. File Index

Absolute paths within this repo (all paths relative to repo root `/home/user/crewai-contact-center`):

| Path                                                            | Type    | Bytes/Lines      | What it is                                                                          |
| --------------------------------------------------------------- | ------- | ---------------- | ----------------------------------------------------------------------------------- |
| `pyproject.toml`                                                | TOML    | 19 lines         | Project metadata, single dep `crewai[tools]>=1.11.0`, console script, setuptools.   |
| `README.md`                                                     | Markdown | 38 lines         | Deploy quickstart + agent list + REST API examples.                                 |
| `INDEX.md`                                                      | Markdown | 56 lines         | Original short overview (kept for legacy).                                          |
| `references.md`                                                 | Markdown | *(this file)*    | This comprehensive reference doc.                                                   |
| `.env.example`                                                  | dotenv  | 4 lines          | `MODEL`, `OPENAI_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.                |
| `.env`                                                          | dotenv  | 2 lines          | Local placeholders; gitignored going forward.                                       |
| `.gitignore`                                                    | text    | 32 lines         | Python, env, IDE, OS, agent-tool dot-dirs.                                          |
| `uv.lock`                                                       | uv lock | ~900 KB          | Reproducible resolved dependency tree.                                              |
| `src/crewai_contact_center/__init__.py`                         | Python  | 1 line (empty)   | Package marker.                                                                     |
| `src/crewai_contact_center/main.py`                             | Python  | 38 lines         | `run()` builds sample inputs and calls `ContactCenterCrew().crew().kickoff(...)`.   |
| `src/crewai_contact_center/crew.py`                             | Python  | 82 lines         | `ContactCenterCrew` class, five `@agent`, five `@task`, one `@crew` (sequential).   |
| `src/crewai_contact_center/tools.py`                            | Python  | 102 lines        | `analyze_transcript`, `score_lead`, `calculate_qa_score` (decorated with `@tool`).  |
| `src/crewai_contact_center/config/agents.yaml`                  | YAML    | 39 lines         | Role/goal/backstory for the five agents.                                            |
| `src/crewai_contact_center/config/tasks.yaml`                   | YAML    | 79 lines         | Description/expected_output/agent for the five tasks.                               |

---

### Quick map: agent → task → tool

```
                ┌──────────────────────────────┐
inputs ────►    │  ContactCenterCrew.crew()    │  ← Process.sequential, verbose
                │  (5 tasks, run in order)     │
                └──────────────────────────────┘
                              │
   ┌──────────────────────────┼──────────────────────────────────────────────┐
   │                          │                                              │
   ▼                          ▼                                              ▼
score_lead_task ──► lead_scoring_agent ──► analyze_transcript, score_lead
evaluate_call_quality_task ──► call_quality_analyst ──► analyze_transcript, calculate_qa_score
optimize_routing_task ──► routing_strategist ──► (no tools — LLM reasoning)
optimize_campaign_task ──► campaign_optimizer ──► (no tools — LLM reasoning)
analyze_sentiment_task ──► sentiment_tracker ──► analyze_transcript
```

### Quick map: consumer flow (production)

```
con-nexus-telephony (NestJS)
   │  CrewAiConnector.execute(request)
   ▼
POST  https://<crew>.crewai.com/kickoff   { "inputs": "<all GET /inputs keys>" } + x-tenant-id
   │
   ▼
{ "kickoff_id": "kid_..." }
   │  poll every 2s up to 60 times
   ▼
GET   https://<crew>.crewai.com/status/kid_... + x-tenant-id
   │
   ▼
{ "state": "completed", "result": "<final task output>" }
   │
   ▼
ExternalAgencyResponse { success, output, latencyMs, metadata: { kickoffId, state } }
```

---

*End of references.md.*
