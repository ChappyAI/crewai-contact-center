from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from crewai_contact_center.tools import analyze_transcript, calculate_qa_score, score_lead


@CrewBase
class ContactCenterCrew:
    """Con.Nexus Contact Center AI Crew

    Multi-agent crew for contact center intelligence:
    - Lead scoring and qualification
    - Call quality analysis
    - Routing optimization
    - Campaign performance optimization
    - Real-time sentiment tracking
    """

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def lead_scoring_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["lead_scoring_agent"],
            tools=[analyze_transcript, score_lead],
            verbose=True,
        )

    @agent
    def call_quality_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["call_quality_analyst"],
            tools=[analyze_transcript, calculate_qa_score],
            verbose=True,
        )

    @agent
    def routing_strategist(self) -> Agent:
        return Agent(config=self.agents_config["routing_strategist"], verbose=True)

    @agent
    def campaign_optimizer(self) -> Agent:
        return Agent(config=self.agents_config["campaign_optimizer"], verbose=True)

    @agent
    def sentiment_tracker(self) -> Agent:
        return Agent(
            config=self.agents_config["sentiment_tracker"],
            tools=[analyze_transcript],
            verbose=True,
        )

    @task
    def score_lead_task(self) -> Task:
        return Task(config=self.tasks_config["score_lead_task"])

    @task
    def evaluate_call_quality_task(self) -> Task:
        return Task(config=self.tasks_config["evaluate_call_quality_task"])

    @task
    def optimize_routing_task(self) -> Task:
        return Task(config=self.tasks_config["optimize_routing_task"])

    @task
    def optimize_campaign_task(self) -> Task:
        return Task(config=self.tasks_config["optimize_campaign_task"])

    @task
    def analyze_sentiment_task(self) -> Task:
        return Task(config=self.tasks_config["analyze_sentiment_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
