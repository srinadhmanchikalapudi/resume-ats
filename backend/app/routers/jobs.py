from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .. import llm
from ..jobs import analyzer, matcher, profile_index, scoring
from ..jobs.models import AnalysisResult, AnalyzeIn
from ..profile import store
from ..tailor import service as tailor_service
from ..tailor.models import TailoredResume, TailorRequest
from .common import llm_access

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/tailor", response_model=TailoredResume)
async def tailor(request: Request, body: TailorRequest) -> TailoredResume:
    """A job-specific selection and rewording of the saved profile, verified against it."""
    profile, _ = store.load_profile()
    if profile.is_empty() or not profile.experience:
        raise HTTPException(status_code=400, detail="Save a master profile with work experience first.")
    if not body.analysis.job.requirements:
        raise HTTPException(status_code=422, detail="Analyse a job posting first.")

    access = llm_access(request, "rewrite")
    try:
        return await tailor_service.tailor_resume(
            profile,
            body.analysis,
            body.length,
            base_url=access.base_url,
            api_key=access.api_key,
            model=access.model,
        )
    except llm.LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(request: Request, body: AnalyzeIn) -> AnalysisResult:
    text = body.text.strip()
    if len(text) < 80:
        raise HTTPException(status_code=422, detail="Paste the full job posting.")

    profile, _ = store.load_profile()
    if profile.is_empty():
        raise HTTPException(status_code=400, detail="Create and save your master profile first.")

    extraction = llm_access(request, "extraction")
    judging = llm_access(request, "analysis")
    entries = profile_index.build_index(profile)

    try:
        job, warnings = await analyzer.analyze_job(
            text, base_url=extraction.base_url, api_key=extraction.api_key, model=extraction.model
        )
        if not job.requirements:
            raise HTTPException(
                status_code=422,
                detail="No requirements were found. Check that this is a full job posting.",
            )
        matches, match_warnings = await matcher.match_requirements(
            job, entries, base_url=judging.base_url, api_key=judging.api_key, model=judging.model
        )
    except llm.LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    years = scoring.candidate_years(profile)
    return AnalysisResult(
        job=job,
        matches=matches,
        keywords=scoring.check_keywords(job, profile_index.full_text(entries)),
        scores=scoring.compute_scores(job, matches, years),
        warnings=[*warnings, *match_warnings],
    )
