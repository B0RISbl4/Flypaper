import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .config import MAX_RATE_LIMIT_BACKOFF_S


def is_rate_limited(error: Exception | None) -> bool:
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None) == 429


def poll_delay(error: Exception | None, rate_limit_streak: int, base_interval: float) -> float:
    if not is_rate_limited(error):
        return base_interval

    response = getattr(error, "response")
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            seconds = float(retry_after)
            if math.isfinite(seconds):
                return max(0.0, seconds)
        except (TypeError, ValueError):
            pass
        try:
            retry_at = parsedate_to_datetime(retry_after)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            pass

    exponent = min(max(rate_limit_streak, 1), 10)
    return min(base_interval * 2**exponent, MAX_RATE_LIMIT_BACKOFF_S)
