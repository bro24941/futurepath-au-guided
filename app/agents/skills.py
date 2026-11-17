"""Learning prompts, not claims about job readiness or formal admission."""
from time import perf_counter
from app.agents.common import trace
from app.models import Goal, Profile, SkillsResult

REQUIREMENTS = {
    "general": ["digital_literacy", "networking", "security_basics"],
    "security_operations": ["networking", "linux", "security_basics", "incident_response"],
    "network_security": ["networking", "linux", "security_basics"],
    "governance": ["security_basics", "risk_management"],
}


def run(goal: Goal, profile: Profile) -> SkillsResult:
    start = perf_counter()
    required = REQUIREMENTS[goal.track] if goal.in_scope else []
    # An unanswered skills question cannot tell us which skills someone needs to build.
    gaps = [skill for skill in required if skill not in profile.skills] if profile.skills_known else []
    return SkillsResult(required=required, gaps=gaps, unknown=not profile.skills_known,
        trace=trace("Skills", "Compare selected skills with the learning checklist", "The project’s cybersecurity skills checklist",
                    f"{len(gaps)} learning areas to explore" if profile.skills_known else "No skills supplied", start,
                    status="ok" if profile.skills_known else "uncertain"))
