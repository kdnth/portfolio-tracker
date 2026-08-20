from pydantic import BaseModel


class AnalysisResponse(BaseModel):
    report: str
