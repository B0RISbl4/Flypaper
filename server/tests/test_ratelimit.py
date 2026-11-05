from types import SimpleNamespace

from flypaper.ratelimit import is_rate_limited, poll_delay


def http_error(status, headers=None):
    error = Exception("http")
    error.response = SimpleNamespace(status_code=status, headers=headers or {})
    return error


def test_no_error_uses_base_interval():
    assert poll_delay(None, 0, 10) == 10
    assert not is_rate_limited(None)


def test_other_http_errors_are_not_rate_limits():
    assert poll_delay(http_error(500), 3, 10) == 10


def test_retry_after_seconds_is_respected():
    assert poll_delay(http_error(429, {"Retry-After": "42"}), 1, 10) == 42


def test_backoff_grows_and_is_capped():
    assert poll_delay(http_error(429), 1, 10) == 20
    assert poll_delay(http_error(429), 3, 10) == 80
    assert poll_delay(http_error(429), 50, 10) == 15 * 60
