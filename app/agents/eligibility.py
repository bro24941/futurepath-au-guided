"""Three-valued checks with evidence; missing facts cannot become eligibility."""
from datetime import date
from time import perf_counter

from app.agents.common import trace
from app.models import Criterion, EligibilityItem, EligibilityResult, Opportunity, Prerequisite, Profile


def check(prerequisite: Prerequisite, profile: Profile) -> str:
    """A missing answer stays unknown unless another answer settles the requirement."""
    if prerequisite.no_formal_requirement:
        return "met"
    values = []
    for condition in prerequisite.checks:
        actual = getattr(profile, condition.field)
        if actual is None:
            values.append("cannot_tell")
        else:
            matched = actual == condition.value if condition.operator == "eq" else actual >= condition.value
            values.append("met" if matched else "not_met")
    if not values:
        return "cannot_tell"
    if prerequisite.mode == "any":
        return "met" if "met" in values else "cannot_tell" if "cannot_tell" in values else "not_met"
    return "not_met" if "not_met" in values else "cannot_tell" if "cannot_tell" in values else "met"


def run(records: list[Opportunity], profile: Profile, as_of: date) -> EligibilityResult:
    start = perf_counter()
    items = []
    for record in records:
        unavailable = record.verification_status in {"unverified", "source_unavailable"}
        stale = (as_of - record.source_checked_date).days > 30 or record.source_checked_date > as_of
        criteria = [Criterion(id=p.id, label=p.label, status="cannot_tell" if unavailable or stale else check(p, profile),
                              evidence_note=p.evidence_note) for p in record.prerequisites]
        if record.eligible_cohorts:
            # Use self-declared identity only for this published requirement.
            cohort = {"yes": "met", "no": "not_met", "prefer_not_to_say": "cannot_tell"}[profile.indigenous_identity]
            criteria.append(Criterion(id="published-cohort", label="Published First Nations cohort rule (self-declared only)",
                status="cannot_tell" if unavailable or stale else cohort,
                evidence_note="Provider publishes a First Nations cohort rule; provider evidence checks remain separate."))
        uncertainty = []
        if record.verification_status != "verified_against_source":
            uncertainty.append("Some provider details still need checking.")
        if stale:
            uncertainty.append("Recheck the provider page. The recorded check is outside the 30-day review window.")
        if record.deadline is None:
            uncertainty.append("Exact application deadline is unknown.")
        statuses = [c.status for c in criteria]
        status = "not_met" if "not_met" in statuses else "cannot_tell" if "cannot_tell" in statuses or stale or record.verification_status != "verified_against_source" else "met"
        items.append(EligibilityItem(opportunity_id=record.id, status=status, criteria=criteria, uncertainties=uncertainty))
    return EligibilityResult(items=items, trace=trace("Eligibility", "Compare profile details with published requirements",
        "Entry requirements and provider evidence in each record", f"Checked {len(items)} records", start,
        status="uncertain" if any(i.status == "cannot_tell" for i in items) else "ok"))
