from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.article import Category


DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("politics", "Politics"),
    ("technology", "Technology"),
    ("health", "Health"),
    ("entertainment", "Entertainment"),
    ("sports", "Sports"),
    ("business", "Business"),
    ("science", "Science"),
    ("world", "World"),
    ("climate", "Climate"),
]


async def seed() -> None:
    async with SessionLocal() as db:
        existing = set((await db.execute(select(Category.slug))).scalars().all())
        for slug, name in DEFAULT_CATEGORIES:
            if slug in existing:
                continue
            db.add(Category(slug=slug, name=name))
        await db.commit()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

