from pydantic import BaseModel


class AnalysisResponse(BaseModel):
    report: str
    # None means unlimited -- the requesting user is an admin, exempt from the daily quota.
    analyses_remaining_today: int | None


class AnalysisQuotaResponse(BaseModel):
    limit: int
    used_today: int
    # None means unlimited -- the requesting user is an admin, exempt from the daily quota.
    remaining: int | None


class DemoAnalysisResponse(BaseModel):
    report: str
    demo_analyses_remaining_today: int
