"""Scored dataset retrieval. Identity and eligibility never enter the score."""
from time import perf_counter
from app.agents.common import trace
from app.agents.skills import REQUIREMENTS
from app.models import Goal, Match, Opportunity, OpportunitiesResult


def run(goal: Goal, records: list[Opportunity]) -> OpportunitiesResult:
    start = perf_counter()
    matches = []
    # Use the goal and catalogue tags, so changing a profile does not rerank the results.
    if goal.in_scope:
        for record in records:
            if goal.category and record.category != goal.category:
                continue
            overlap = set(REQUIREMENTS[goal.track]).intersection(record.skill_tags)
            if overlap:
                matches.append(Match(opportunity_id=record.id, score=len(overlap) * 10,
                    reason="Relevant learning areas: " + ", ".join(sorted(overlap)).replace("_", " ")))
    matches.sort(key=lambda match: (-match.score, match.opportunity_id))
    matches = matches[:6]
    return OpportunitiesResult(matches=matches, trace=trace("Opportunities", "Find options that match the goal",
        "Catalogue categories and skills", f"{len(matches)} matching records", start,
        status="ok" if matches else "no_match"))
