from __future__ import annotations

import asyncio
import os
import pickle

import numpy as np
import scipy.sparse as sp
from celery import shared_task
from implicit.als import AlternatingLeastSquares
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.user import UserEvent


@shared_task(name="recs.train_als")
def train_als(factors: int = 64, iterations: int = 20, regularization: float = 0.05) -> dict:
    async def _run() -> dict:
        async with SessionLocal() as db:
            rows = (
                await db.execute(
                    select(UserEvent.user_external_id, UserEvent.article_id, UserEvent.event_type)
                    .where(UserEvent.event_type.in_(["click", "save", "dwell"]))
                )
            ).all()

        if not rows:
            return {"trained": False, "reason": "no_events"}

        users = sorted({r[0] for r in rows})
        items = sorted({str(r[1]) for r in rows})
        u_index = {u: i for i, u in enumerate(users)}
        i_index = {it: i for i, it in enumerate(items)}

        data = []
        row_idx = []
        col_idx = []
        for u, aid, et in rows:
            w = 1.0
            if et == "save":
                w = 3.0
            elif et == "dwell":
                w = 1.5
            row_idx.append(u_index[u])
            col_idx.append(i_index[str(aid)])
            data.append(w)

        mat = sp.csr_matrix((np.asarray(data, dtype=np.float32), (row_idx, col_idx)), shape=(len(users), len(items)))
        model = AlternatingLeastSquares(factors=factors, iterations=iterations, regularization=regularization)
        model.fit(mat)

        os.makedirs(os.path.join("ml", "artifacts"), exist_ok=True)
        path = os.path.join("ml", "artifacts", "als.pkl")
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "users": users,
                    "items": items,
                    "user_factors": model.user_factors,
                    "item_factors": model.item_factors,
                    "params": {"factors": factors, "iterations": iterations, "regularization": regularization},
                },
                f,
            )

        return {"trained": True, "users": len(users), "items": len(items), "path": path}

    return asyncio.run(_run())

