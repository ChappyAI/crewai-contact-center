"""Custom tools for Contact Center AI agents."""
from crewai.tools import tool


@tool("Analyze Call Transcript")
def analyze_transcript(transcript: str) -> str:
    """Analyze a call transcript for key topics, sentiment indicators, and action items.
    Returns structured analysis."""
    # Count sentiment indicators
    negative_words = ["frustrated", "angry", "cancel", "terrible", "worst", "complaint", "waiting"]
    positive_words = ["thank", "great", "excellent", "happy", "appreciate", "resolved", "helpful"]

    neg_count = sum(1 for w in negative_words if w in transcript.lower())
    pos_count = sum(1 for w in positive_words if w in transcript.lower())

    sentiment = "negative" if neg_count > pos_count else "positive" if pos_count > neg_count else "neutral"

    words = transcript.split()
    topics = list(set(w.lower().strip(".,!?") for w in words if len(w) > 7))[:10]

    return (
        f"Sentiment: {sentiment} (positive indicators: {pos_count}, negative: {neg_count})\n"
        f"Key topics: {', '.join(topics)}\n"
        f"Word count: {len(words)}\n"
        f"Transcript length: {len(transcript)} chars"
    )


@tool("Score Lead Quality")
def score_lead(
    engagement_level: str,
    call_duration_seconds: int,
    sentiment: str,
    questions_asked: int = 0,
) -> str:
    """Score a lead based on engagement metrics. Returns a quality score 1-100."""
    score = 50  # baseline

    # Engagement
    if engagement_level == "high":
        score += 20
    elif engagement_level == "low":
        score -= 15

    # Duration (longer = more engaged, up to a point)
    if call_duration_seconds > 300:
        score += 15
    elif call_duration_seconds > 120:
        score += 10
    elif call_duration_seconds < 30:
        score -= 10

    # Sentiment
    if sentiment == "positive":
        score += 15
    elif sentiment == "negative":
        score -= 10

    # Questions asked (buying signals)
    score += min(questions_asked * 5, 20)

    score = max(1, min(100, score))
    qualification = "hot" if score > 75 else "warm" if score > 45 else "cold"

    return f"Lead Score: {score}/100\nQualification: {qualification}\nRecommended Action: {'schedule_callback' if score > 75 else 'nurture' if score > 45 else 'low_priority'}"


@tool("Calculate QA Score")
def calculate_qa_score(
    greeting_quality: int,
    active_listening: int,
    problem_resolution: int,
    compliance: int,
    professionalism: int,
) -> str:
    """Calculate overall QA score from individual criteria (each 1-10). Returns detailed scorecard."""
    criteria = {
        "Greeting Quality": greeting_quality,
        "Active Listening": active_listening,
        "Problem Resolution": problem_resolution,
        "Compliance": compliance,
        "Professionalism": professionalism,
    }

    total = sum(criteria.values())
    overall = int(total / len(criteria) * 10)

    strengths = [k for k, v in criteria.items() if v >= 8]
    improvements = [k for k, v in criteria.items() if v <= 5]

    scorecard = f"Overall QA Score: {overall}/100\n\nCriteria Breakdown:\n"
    for k, v in criteria.items():
        bar = "\u2588" * v + "\u2591" * (10 - v)
        scorecard += f"  {k}: {bar} {v}/10\n"

    if strengths:
        scorecard += f"\nStrengths: {', '.join(strengths)}"
    if improvements:
        scorecard += f"\nNeeds Improvement: {', '.join(improvements)}"

    return scorecard
