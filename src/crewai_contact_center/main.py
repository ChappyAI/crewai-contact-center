#!/usr/bin/env python
from crewai_contact_center.crew import ContactCenterCrew


def run():
    """Run the contact center crew."""
    inputs = {
        "call_id": "example-call-001",
        "tenant_id": "tenant-001",
        "transcript": "Customer: I want to cancel my subscription. Agent: I understand. May I ask what prompted this?",
        "duration_seconds": 120,
        "sentiment": "negative",
        "agent_notes": "Customer considering cancellation",
        "disposition": "retention_attempt",
        "agent_id": "agent-42",
        "caller_number": "+15551234567",
        "caller_history": "3 previous calls, 2 complaints",
        "available_agents": "agent-1 (sales), agent-2 (retention), agent-3 (support)",
        "queue_depths": "sales: 2, retention: 0, support: 5",
        "sla_metrics": "target: 30s, current avg: 22s",
        "campaign_id": "camp-001",
        "analysis_period": "last 7 days",
        "contact_rate": "45",
        "answer_rate": "32",
        "conversion_rate": "8",
        "abandon_rate": "3",
        "avg_handle_time": "240",
        "list_remaining": "5000",
        "transcript_chunk": "I want to cancel",
        "previous_sentiment": "neutral",
        "elapsed_seconds": "60",
    }
    ContactCenterCrew().crew().kickoff(inputs=inputs)


if __name__ == "__main__":
    run()
