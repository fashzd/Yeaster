"""The Skill contract + a tiny registry.

A Skill is a named, self-describing, JSON-in/evidence-pack-out unit. The
``cost`` hint (low/medium/high) lets a scheduler budget which skills to run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Skill:
    unique_name: str
    description: str
    input_schema: dict[str, Any]                  # JSON Schema for params
    run: Callable[[dict[str, Any]], dict[str, Any]]  # params -> data dict
    cost: str = "low"                             # latency hint: low | medium | high
    tags: tuple[str, ...] = field(default_factory=tuple)

    def manifest(self) -> dict[str, Any]:
        return {"unique_name": self.unique_name, "description": self.description,
                "input_schema": self.input_schema, "cost": self.cost, "tags": list(self.tags)}


def pack(skill: str, ok: bool, data: dict[str, Any], summary: str = "") -> dict[str, Any]:
    """Uniform evidence-pack envelope returned by every skill invocation."""
    return {"skill": skill, "ok": ok, "summary": summary, "data": data}


_REGISTRY: dict[str, Skill] = {}


def register(skill: Skill) -> Skill:
    _REGISTRY[skill.unique_name] = skill
    return skill


def get(name: str) -> Skill | None:
    return _REGISTRY.get(name)


def all_skills() -> list[Skill]:
    return list(_REGISTRY.values())


def manifest() -> list[dict[str, Any]]:
    return [s.manifest() for s in _REGISTRY.values()]


def invoke(name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    skill = get(name)
    if skill is None:
        return pack(name, False, {"error": f"unknown skill '{name}'"}, "not found")
    try:
        data = skill.run(params or {})
        return pack(name, True, data)
    except Exception as exc:  # never raise to the caller; surface as a failed pack
        return pack(name, False, {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}, "error")
