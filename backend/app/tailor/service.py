from __future__ import annotations

from .. import llm
from ..jobs.models import AnalysisResult
from ..profile.models import Profile
from . import prompt, verify
from .models import Length, TailoredResume, TailorReply


async def tailor_resume(
    profile: Profile,
    analysis: AnalysisResult,
    length: Length,
    *,
    base_url: str,
    api_key: str,
    model: str,
) -> TailoredResume:
    caps = prompt.role_caps(profile, length)
    reply = await llm.complete_json(
        base_url=base_url,
        api_key=api_key,
        model=model,
        system=prompt.SYSTEM_PROMPT,
        user=prompt.build_user_message(profile, analysis, caps),
        schema=TailorReply,
    )
    return verify.build_resume(profile, analysis, reply, length)
