"""Validate the checked dataset without network access: python -m data.validate."""
import json
import sys
from datetime import date
from pathlib import Path

from app.models import Opportunity

DATA_PATH = Path(__file__).resolve().parent / "opportunities.json"


def load_records(path: Path = DATA_PATH) -> list[Opportunity]:
    return [Opportunity.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def validate(path: Path = DATA_PATH, as_of: date | None = None) -> tuple[list[str], list[str]]:
    """Staleness is a warning, not a reason to hide a real archived opportunity."""
    errors, warnings = [], []
    try:
        records = load_records(path)
    except (ValueError, OSError) as exc:
        return [str(exc)], []
    today = as_of or date.today()
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate opportunity ids.")
    if len(records) != 24:
        errors.append(f"Expected 24 records, found {len(records)}.")
    for record in records:
        if record.source_url.scheme != "https":
            errors.append(f"{record.id}: source must use HTTPS.")
        if record.source_checked_date > today:
            errors.append(f"{record.id}: source check is in the future.")
        if (today - record.source_checked_date).days > 30:
            warnings.append(f"{record.id}: stale source; recheck before relying on it.")
        criteria = [item.id for item in record.prerequisites]
        if len(criteria) != len(set(criteria)):
            errors.append(f"{record.id}: duplicate prerequisite ids.")
    return errors, warnings


if __name__ == "__main__":
    problems, notices = validate()
    for message in problems + notices:
        print(message)
    print(f"Dataset: {len(problems)} errors, {len(notices)} warnings.")
    sys.exit(bool(problems))
