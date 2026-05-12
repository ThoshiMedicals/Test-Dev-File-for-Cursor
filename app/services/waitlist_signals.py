from __future__ import annotations


def sentiment_from_reaction(emoji_or_label: str | None) -> tuple[str, float] | None:
    if not emoji_or_label:
        return None
    raw = str(emoji_or_label).strip().lower()
    positive = {"😊", "🙂", "👍", "❤️", "🔥", "positive", "love", "great"}
    negative = {"😞", "☹️", "👎", "😠", "negative", "bad", "confused"}
    neutral = {"😐", "🤷", "neutral", "meh", "ok"}
    if raw in positive:
        return "positive", 0.85
    if raw in negative:
        return "negative", 0.85
    if raw in neutral:
        return "neutral", 0.6
    return "neutral", 0.5
