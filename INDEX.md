# crewai-contact-center - Development Overview

## 1. Purpose and Scope
This project defines a multi-agent "crew" using the CrewAI framework. The crew is designed for a contact center environment and consists of several specialized AI agents that perform tasks like lead scoring, call quality assurance, routing strategy optimization, campaign optimization, and sentiment analysis.

## 2. Key Technologies and Dependencies
- **Language/Runtime**: Python (>=3.10)
- **Framework**: CrewAI
- **Key Libraries**:
    - `crewai`: The core framework for orchestrating autonomous AI agents.
    - `crewai[tools]`: Provides additional tools for the CrewAI agents.
- **Internal Dependencies**: This is a self-contained project with no dependencies on the other sub-projects in the monorepo.

(Reference: [pyproject.toml](file:///Users/seanchapman/DDev/containers/telephony/luhx/crewai-contact-center/pyproject.toml))

## 3. Architecture and Core Components
- **Entry Points**: The main script to run the crew is `src/crewai_contact_center/main.py`.
- **Core Components**:
    - `src/crewai_contact_center/crew.py`: Defines the Crew, including the agents and tasks.
    - `src/crewai_contact_center/tools.py`: Defines custom tools that the agents can use.
    - `src/crewai_contact_center/config/`: Contains YAML files (`agents.yaml`, `tasks.yaml`) that configure the agents and tasks for the crew.

## 4. Setup and Local Development Environment
- **Prerequisites**: Python 3.10+, Rust toolchain (for CrewAI CLI).
- **Installation/Build**:
    ```bash
    pip install crewai
    ```
- **Running Locally/Deployment**:
    The project is designed to be deployed to CrewAI Enterprise.
    ```bash
    crewai login
    crewai deploy
    ```

## 5. Important Documentation Links
- [README.md](file:///Users/seanchapman/DDev/containers/telephony/luhx/crewai-contact-center/README.md): Provides instructions for deploying the crew to CrewAI Enterprise, lists the agents in the crew, and shows example API usage.

## 6. Testing Strategy
There are no tests included in this project. Testing would involve running the crew with sample inputs and verifying the output of the agents.

## 7. Potential Areas for Improvement / Future Work
- Add a testing framework to automate the validation of the crew's behavior.
- Expand the set of tools available to the agents in `tools.py`.
- Add more specialized agents to the crew for other contact center tasks.

## 8. Codebase Structure (Top 4 Levels)
```
.
├── src/
│   └── crewai_contact_center/
│       └── config/
├── .env.example
├── README.md
└── pyproject.toml
```
