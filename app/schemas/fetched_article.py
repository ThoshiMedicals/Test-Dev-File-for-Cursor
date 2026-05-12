from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class FetchedArticle:
    url: str
    title: str
    lead_text: str | None
    image_url: str | None
    source_name: str | None
    published_at: datetime | None
    author: str | None
