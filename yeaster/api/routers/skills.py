"""Strategy skills — discovery (manifest) + invocation. The Track-2 surface.

These endpoints are for EXTERNAL consumers. The autonomous pipeline never calls
them — it uses the underlying modules in-process — so this surface adds no latency
to the trade loop.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

import yeaster.skills.catalog  # noqa: F401  (registers the five skills on import)
from yeaster.skills import base as skills

router = APIRouter(prefix="/skills", tags=["skills"])


class InvokeRequest(BaseModel):
    parameters: Optional[dict[str, Any]] = None


@router.get("")
def list_skills() -> dict:
    return {"count": len(skills.all_skills()), "skills": skills.manifest()}


@router.post("/{unique_name}")
def invoke(unique_name: str, req: InvokeRequest) -> dict:
    return skills.invoke(unique_name, req.parameters or {})
