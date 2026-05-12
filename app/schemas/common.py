from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class EnvelopeMeta(BaseModel):
    next_cursor: str | None = None
    model_versions: dict[str, str] = Field(default_factory=dict)


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: EnvelopeMeta = Field(default_factory=EnvelopeMeta)


class ErrorEnvelope(BaseModel):
    detail: Any

