"""Conversational agent — talk to Yeaster or command it."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from yeaster.brain import chat as chat_mod

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    text: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: Optional[dict[str, Any]] = None


@router.post("")
def chat(req: ChatRequest) -> dict:
    return chat_mod.respond([m.model_dump() for m in req.messages], req.context or {})
