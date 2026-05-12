from __future__ import annotations

from urllib.parse import quote


def share_links_for_url(article_url: str, title: str) -> dict[str, str]:
    """Outbound share URLs (track shares via /v1/users/.../events with event_type=share)."""
    u = quote(article_url, safe="")
    t = quote(title[:200], safe="")
    return {
        "twitter": f"https://twitter.com/intent/tweet?url={u}&text={t}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={u}",
        "linkedin": f"https://www.linkedin.com/sharing/share-offsite/?url={u}",
    }
