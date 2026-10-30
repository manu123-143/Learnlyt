"""Spaced-repetition and retention calculations for LearnLyt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ReviewResult:
    repetitions: int
    interval_days: int
    ease_factor: float
    next_review: str
    remembered: bool


def schedule_review(
    quality: int,
    repetitions: int,
    interval_days: int,
    ease_factor: float,
    today: date | None = None,
) -> ReviewResult:
    """Return the next SM-2-inspired schedule for a 0–5 recall rating."""
    if quality not in range(6):
        raise ValueError("Review quality must be between 0 and 5.")

    current_day = today or date.today()
    remembered = quality >= 3

    if not remembered:
        new_repetitions = 0
        new_interval = 1
    else:
        new_repetitions = repetitions + 1
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = max(1, round(interval_days * ease_factor))

    difference = 5 - quality
    new_ease = ease_factor + 0.1 - difference * (0.08 + difference * 0.02)
    new_ease = round(max(1.3, new_ease), 2)
    next_review = current_day + timedelta(days=new_interval)

    return ReviewResult(
        repetitions=new_repetitions,
        interval_days=new_interval,
        ease_factor=new_ease,
        next_review=next_review.isoformat(),
        remembered=remembered,
    )


def retention_percentage(correct: int, incorrect: int) -> int:
    total = correct + incorrect
    return round(correct / total * 100) if total else 0
