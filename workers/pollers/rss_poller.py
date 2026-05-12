from __future__ import annotations

import os

from workers.tasks.ingest import rss_poll


def main() -> None:
    # Comma-separated list of RSS URLs.
    feeds = [f.strip() for f in os.environ.get("RSS_FEEDS", "").split(",") if f.strip()]
    if not feeds:
        raise SystemExit("RSS_FEEDS is empty. Set it to a comma-separated list of RSS URLs.")

    source_name = os.environ.get("RSS_SOURCE_NAME")
    max_entries = int(os.environ.get("RSS_MAX_ENTRIES", "25"))

    for feed_url in feeds:
        rss_poll.delay(feed_url, source_name=source_name, max_entries=max_entries)


if __name__ == "__main__":
    main()

