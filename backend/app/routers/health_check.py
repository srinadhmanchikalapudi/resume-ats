from __future__ import annotations

from fastapi import APIRouter

from ..health.analyzer import analyze
from ..health.models import HealthReport, HealthRequest

router = APIRouter(prefix="/health-check", tags=["health"])


@router.post("", response_model=HealthReport)
def check_health(body: HealthRequest) -> HealthReport:
    """Scores a resume for impact, verbs, clarity, specificity and completeness. No model calls, nothing is stored."""
    return analyze(body.profile)
