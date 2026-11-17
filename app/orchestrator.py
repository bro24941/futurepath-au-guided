"""Typed, in-memory handoffs between six agents."""
from datetime import date

from app.agents import deadlines, eligibility, goals, opportunities, pathway_planner, skills
from app.llm import GoalLLM
from app.models import Opportunity, PathwayRequest, PathwayResponse


def build_pathway(request: PathwayRequest, records: list[Opportunity], llm: GoalLLM, as_of: date) -> PathwayResponse:
    # Only the goal interpreter receives the goal text. Later agents use structured results.
    goal = goals.run(request.goal, llm)
    skill = skills.run(goal.goal, request.profile)
    found = opportunities.run(goal.goal, records)
    by_id = {record.id: record for record in records}
    selected = [by_id[match.opportunity_id] for match in found.matches]
    checked = eligibility.run(selected, request.profile, as_of)
    dates = deadlines.run(selected, as_of)
    plan = pathway_planner.run(selected, skill, checked, dates)
    notices = ["Check places, funding and enrolment details with the provider before you apply."]
    if goal.notice:
        notices.insert(0, goal.notice)
    if not selected:
        notices.append("We couldn’t find a matching opportunity in the cybersecurity catalogue.")
    return PathwayResponse(goal=goal.goal, skills=skill, opportunities=selected, matches=found.matches,
        eligibility=checked.items, deadlines=dates, plan=plan,
        trace=[goal.trace, skill.trace, found.trace, checked.trace, dates.trace, plan.trace], notices=notices)
