"""A dependency plan for reviewing alternatives, never an automatic application."""
from time import perf_counter
from datetime import date

from app.agents.common import trace
from app.models import DeadlinesResult, EligibilityResult, Opportunity, PlanResult, SkillsResult, Step


def summary_for(steps: list[Step]) -> str:
    if not steps:
        return "A plan will appear once we find an opportunity that matches your goal."
    return "Work through the checks for the options that interest you. Review the plan yourself or with an adviser."


def verify_summary(text: str, steps: list[Step]) -> bool:
    """Exact allowlisting rejects invented ids, dates and requirements in optional prose."""
    return text == summary_for(steps)


def run(records: list[Opportunity], skills: SkillsResult, eligibility: EligibilityResult, deadlines: DeadlinesResult) -> PlanResult:
    start = perf_counter()
    steps = []
    if records:
        detail = "Skills were not supplied. Review the learning checklist with an adviser." if skills.unknown else (
            "Learning areas to explore: " + ", ".join(skills.gaps).replace("_", " ") if skills.gaps else "No gaps in the small project checklist; this does not establish job readiness.")
        steps.append(Step(id="skills-review", title="Review your learning needs", detail=detail))
    checked = {item.opportunity_id: item for item in eligibility.items}
    dates = {item.opportunity_id: item for item in deadlines.items}
    for record in records:
        # Put each provider action after the checks that support it.
        dependencies = ["skills-review"]
        for criterion in checked[record.id].criteria:
            id = f"{record.id}-{criterion.id}"
            outcome = {"met": "Meets this recorded requirement", "not_met": "Doesn’t meet this recorded requirement", "cannot_tell": "Needs a provider check"}[criterion.status]
            steps.append(Step(id=id, opportunity_id=record.id, title="Check: " + criterion.label,
                detail=f"{outcome}. {criterion.evidence_note}", criterion_id=criterion.id,
                depends_on=["skills-review"]))
            dependencies.append(id)
        review_id = f"{record.id}-review"
        steps.append(Step(id=review_id, opportunity_id=record.id, title="Review alternative: " + record.title,
            detail="Check the original provider information, availability, costs and unresolved criteria with an adviser. " + record.notes,
            depends_on=dependencies))
        blocked = dates[record.id].status == "closed" or record.availability == "on_hold" or checked[record.id].status != "met" or dates[record.id].stale_source
        steps.append(Step(id=f"{record.id}-action", opportunity_id=record.id,
            title="Check what’s unclear or ask about the next round" if blocked else "Confirm the intake with the provider",
            detail=" ".join(record.next_steps),
            depends_on=[review_id], deadline=record.deadline if isinstance(record.deadline, date) else None))
    summary = summary_for(steps)
    assert verify_summary(summary, steps)
    return PlanResult(steps=steps, summary=summary, trace=trace("Pathway Planner", "Put the checks and provider actions in order",
        "Skills, eligibility and deadlines", f"{len(steps)} steps across {len(records)} options", start))
