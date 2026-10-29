"""The demonstration personas a visitor can ask as (a demo selector, not a login)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from navigator.api.deps import get_personas
from navigator.api.personas import Persona
from navigator.api.rate_limit import READ_RATE_LIMIT, limiter
from navigator.api.schemas import PersonaHistory, PersonaResponse

router = APIRouter(prefix="/personas", tags=["personas"])


def to_response(persona: Persona) -> PersonaResponse:
    h = persona.history
    return PersonaResponse(
        patient_id=persona.patient_id,
        role=persona.role,
        name=persona.name,
        age=persona.age,
        gender=persona.gender,
        language=persona.language,
        literacy=persona.literacy,
        headline=persona.headline,
        blurb=persona.blurb,
        history=PersonaHistory(
            labs=h.labs,
            analytes=h.analytes,
            medications=h.medications,
            conditions=h.conditions,
            encounters=h.encounters,
            notes=h.notes,
        ),
    )


@router.get("")
@limiter.limit(READ_RATE_LIMIT)
async def list_personas(
    request: Request,
    personas: Annotated[tuple[Persona, ...], Depends(get_personas)],
) -> list[PersonaResponse]:
    return [to_response(p) for p in personas]
