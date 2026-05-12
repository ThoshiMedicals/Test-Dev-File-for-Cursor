from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import Envelope

router = APIRouter(prefix="/v1/legal", tags=["legal"])


@router.get("/privacy", response_model=Envelope[dict])
async def privacy_notice() -> Envelope[dict]:
    """High-level GDPR-oriented disclosure for pseudonymous analytics and optional email waitlist."""
    return Envelope(
        data={
            "version": "2026-05-12",
            "controller": "Configure in deployment (see privacy policy URL).",
            "data_collected": [
                "Pseudonymous user id you supply in the feed UI for personalization and engagement events.",
                "Article interaction events (click, dwell, save, share) with timestamps for ranking and recommendations.",
                "Optional waitlist email and interests when submitted on the Coming Soon page (encrypted at rest when keys are configured).",
            ],
            "purposes": [
                "Operate the news feed, recommendations, sentiment-aware ranking, and in-app notifications.",
                "Improve collaborative and content-based models from aggregate implicit feedback.",
            ],
            "retention": "Interaction events are retained according to RETENTION_DAYS_EVENTS (default 90 days).",
            "rights": [
                "Export or delete pseudonymous profile and events via the user APIs when enabled by your deployment.",
                "Withdraw personalization or marketing notifications in user preferences.",
            ],
            "legal_basis": "Legitimate interests for product analytics; consent for marketing email when explicitly collected.",
            "contact": "Provide a DPO or privacy inbox URL in your production deployment.",
        }
    )
