"""Date arithmetic, independently of whether profile criteria match."""
from datetime import date
from time import perf_counter
from app.agents.common import trace
from app.models import Deadline, DeadlinesResult, Opportunity


def run(records: list[Opportunity], as_of: date) -> DeadlinesResult:
    start = perf_counter()
    items = []
    for record in records:
        # A missing date stays unknown, even when a study start date is available.
        days = (record.deadline - as_of).days if isinstance(record.deadline, date) else None
        if record.availability == "closed" or days is not None and days < 0:
            status = "closed"
        elif record.availability == "on_hold":
            status = "unknown"
        elif record.deadline == "rolling":
            status = "rolling"
        elif days is None:
            status = "unknown"
        else:
            status = "closing_soon" if days <= 14 else "open"
        items.append(Deadline(opportunity_id=record.id, deadline=record.deadline, status=status,
            days_remaining=days, stale_source=(as_of - record.source_checked_date).days > 30 or record.source_checked_date > as_of))
    return DeadlinesResult(as_of_date=as_of, items=items, trace=trace("Deadlines", "Check closing dates and when sources were checked",
        "Provider deadlines and the date shown above the results", f"Checked dates for {len(items)} records", start,
        status="uncertain" if any(i.status == "unknown" or i.stale_source for i in items) else "ok"))
