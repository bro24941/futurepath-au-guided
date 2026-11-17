"""Typed boundaries shared by the six agents and the API."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


Skill = Literal["digital_literacy", "networking", "linux", "security_basics", "python", "incident_response", "risk_management"]
Category = Literal["course", "traineeship", "apprenticeship", "cadetship", "scholarship", "mentoring"]
Status = Literal["met", "not_met", "cannot_tell"]
Verification = Literal["verified_against_source", "partially_verified", "unverified", "source_unavailable"]
ProfileField = Literal["age", "citizen", "year12", "it_certificate", "it_experience", "network_os", "stem_enrolled", "semesters_completed", "months_remaining", "credit_average", "security_assessment", "institution", "commencing", "domestic", "atar", "commonwealth_supported", "state", "digital_literacy", "study_level"]


class Profile(Model):
    # A tester’s adult consent does not provide an age for their fictitious profile.
    age: int | None = Field(default=None, ge=18, le=120)
    indigenous_identity: Literal["prefer_not_to_say", "yes", "no"] = "prefer_not_to_say"
    skills: list[Skill] = Field(default_factory=list, max_length=7)
    skills_known: bool = False
    citizen: bool | None = None
    year12: bool | None = None
    it_certificate: bool | None = None
    it_experience: bool | None = None
    network_os: bool | None = None
    stem_enrolled: bool | None = None
    study_level: Literal["undergraduate", "postgraduate_coursework", "other"] | None = None
    semesters_completed: int | None = Field(default=None, ge=0, le=30)
    months_remaining: int | None = Field(default=None, ge=0, le=120)
    credit_average: bool | None = None
    security_assessment: bool | None = None
    institution: Literal["ANU", "Monash", "Adelaide", "QUT", "other"] | None = None
    commencing: bool | None = None
    domestic: bool | None = None
    atar: float | None = Field(default=None, ge=0, le=99.95)
    commonwealth_supported: bool | None = None
    state: Literal["NSW", "VIC", "QLD", "TAS", "SA", "WA", "ACT", "NT"] | None = None
    digital_literacy: bool | None = None


class PathwayRequest(Model):
    goal: str = Field(min_length=3, max_length=500)
    adult_tester: Literal[True]
    fictitious_profile: Literal[True]
    privacy_consent: Literal[True]
    profile: Profile = Field(default_factory=Profile)

    @field_validator("goal")
    @classmethod
    def meaningful_goal(cls, value: str) -> str:
        if len(value.strip()) < 3:
            raise ValueError("Enter a goal of at least three characters.")
        return value.strip()


class Check(Model):
    field: ProfileField
    operator: Literal["eq", "gte"] = "eq"
    value: bool | int | float | str


class Prerequisite(Model):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str = Field(min_length=3, max_length=220)
    checks: list[Check] = Field(default_factory=list)
    mode: Literal["all", "any"] = "all"
    no_formal_requirement: bool = False
    evidence_note: str = Field(min_length=3, max_length=240)


class Opportunity(Model):
    id: str = Field(pattern=r"^fp-[0-9]{2}$")
    title: str
    provider: str
    category: Category
    location: str
    description: str
    prerequisites: list[Prerequisite] = Field(min_length=1)
    eligible_cohorts: list[Literal["First Nations"]] = Field(default_factory=list)
    deadline: date | Literal["rolling"] | None = None
    study_commencement: str | None = None
    next_steps: list[str] = Field(min_length=1)
    source_url: HttpUrl
    source_checked_date: date
    verification_status: Verification
    evidence_note: str
    notes: str
    availability: Literal["closed", "on_hold", "unknown", "open"] = "unknown"
    skill_tags: list[Skill] = Field(min_length=1)

    @field_validator("evidence_note")
    @classmethod
    def short_evidence(cls, value: str) -> str:
        if len(value.split()) >= 15:
            raise ValueError("Evidence note must contain fewer than 15 words.")
        return value


class Trace(Model):
    agent: str
    task: str
    source: str
    result: str
    status: Literal["ok", "uncertain", "no_match", "fallback"] = "ok"
    duration_ms: float = Field(ge=0)
    method: Literal["rules", "LLM"] = "rules"
    model: str | None = None


class Goal(Model):
    in_scope: bool
    track: Literal["general", "security_operations", "network_security", "governance"]
    category: Category | None = None


class GoalsResult(Model):
    goal: Goal
    notice: str | None = None
    trace: Trace


class SkillsResult(Model):
    required: list[Skill]
    gaps: list[Skill]
    unknown: bool
    trace: Trace


class Match(Model):
    opportunity_id: str
    score: int
    reason: str


class OpportunitiesResult(Model):
    matches: list[Match]
    trace: Trace


class Criterion(Model):
    id: str
    label: str
    status: Status
    evidence_note: str


class EligibilityItem(Model):
    opportunity_id: str
    status: Status
    criteria: list[Criterion]
    uncertainties: list[str]


class EligibilityResult(Model):
    items: list[EligibilityItem]
    trace: Trace


class Deadline(Model):
    opportunity_id: str
    deadline: date | Literal["rolling"] | None
    status: Literal["closed", "closing_soon", "open", "rolling", "unknown"]
    days_remaining: int | None
    stale_source: bool


class DeadlinesResult(Model):
    as_of_date: date
    items: list[Deadline]
    trace: Trace


class Step(Model):
    id: str
    opportunity_id: str | None = None
    title: str
    detail: str
    depends_on: list[str] = Field(default_factory=list)
    criterion_id: str | None = None
    deadline: date | None = None


class PlanResult(Model):
    steps: list[Step]
    summary: str
    trace: Trace


class PathwayResponse(Model):
    goal: Goal
    skills: SkillsResult
    opportunities: list[Opportunity]
    matches: list[Match]
    eligibility: list[EligibilityItem]
    deadlines: DeadlinesResult
    plan: PlanResult
    trace: list[Trace]
    notices: list[str]
