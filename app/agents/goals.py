"""Interpret only the supported cybersecurity vocabulary, with a safe fallback."""
import re
from time import perf_counter

from app.agents.common import trace
from app.llm import GoalLLM
from app.models import Goal, GoalsResult

CATEGORIES = {"course": ("course", "study", "certificate", "degree", "training"),
              "traineeship": ("trainee", "traineeship"), "apprenticeship": ("apprentice", "apprenticeship"),
              "cadetship": ("cadet", "cadetship"), "scholarship": ("scholarship", "funding"),
              "mentoring": ("mentor", "mentoring")}
SAFE_TERMS = {"cyber", "cybersecurity", "security", "network", "networking", "soc", "pentesting", "analyst", "incident", "governance", "risk", "compliance", "monitoring", "threat", "audit", "policy", "defence", "penetration", "testing", "linux", "beginner"}


def run(text: str, llm: GoalLLM) -> GoalsResult:
    start = perf_counter()
    words = set(re.findall(r"[a-z]+", text.lower()))
    scope = bool(words & {"cyber", "cybersecurity", "network", "networking", "soc", "pentesting"}) or {"information", "security"} <= words
    track = "general"
    if words & {"soc", "incident", "analyst"}:
        track = "security_operations"
    elif words & {"network", "networking", "pentesting"}:
        track = "network_security"
    elif words & {"governance", "risk", "compliance"}:
        track = "governance"
    # People search for a scholarship or scholarships. Both use the same category.
    category_words = words | {word.removesuffix("s") for word in words}
    category = next((key for key, synonyms in reversed(CATEGORIES.items()) if category_words.intersection(synonyms)), None)
    goal = Goal(in_scope=scope, track=track, category=category)
    candidate, model, notice = llm.extract(goal, sorted(words & SAFE_TERMS)) if scope else (None, None, None)
    track = (candidate or goal).track
    interpretation = f"{track.replace('_', ' ').capitalize()} · {category or 'any opportunity type'}" if scope else "Goal outside the cybersecurity catalogue"
    return GoalsResult(goal=candidate or goal, notice=notice, trace=trace("Goals", "Work out what to look for",
        "Selected cybersecurity terms and optional Gemini classification", interpretation, start,
        status="no_match" if not scope else "fallback" if notice else "ok", method="LLM" if model else "rules", model=model))
