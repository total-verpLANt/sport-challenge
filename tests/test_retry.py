"""Unit-Tests für app/utils/retry.py.

Prüft:
- Nach max_retries erschöpften Versuchen wird GarminConnectTooManyRequestsError geworfen.
- Andere Exceptions werden SOFORT weitergegeben (kein Retry).
- time.sleep wird korrekt mit dem exponentiellen Delay aufgerufen.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from garminconnect.exceptions import GarminConnectTooManyRequestsError

from app.utils.retry import retry_on_rate_limit


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def make_flaky(exc_class, fail_times: int):
    """Gibt eine Funktion zurück, die ``fail_times``-mal ``exc_class`` wirft,
    dann aber erfolgreich 'ok' zurückgibt."""
    calls = {"n": 0}

    @retry_on_rate_limit(max_retries=2, base_delay=60)
    def flaky():
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise exc_class("rate limit")
        return "ok"

    return flaky


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRetryOnRateLimit:
    def test_retries_twice_then_raises(self):
        """Nach 2 Retries (3 Versuche gesamt) wird die Exception geworfen."""
        always_fail = MagicMock(side_effect=GarminConnectTooManyRequestsError("limit"))
        always_fail.__qualname__ = "always_fail"

        @retry_on_rate_limit(max_retries=2, base_delay=60)
        def decorated():
            return always_fail()

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            with pytest.raises(GarminConnectTooManyRequestsError):
                decorated()

        assert always_fail.call_count == 3  # 1 Versuch + 2 Retries
        assert mock_sleep.call_count == 2

    def test_exponential_backoff_delays(self):
        """1. Retry nach 60s, 2. Retry nach 120s."""
        always_fail = MagicMock(side_effect=GarminConnectTooManyRequestsError("limit"))

        @retry_on_rate_limit(max_retries=2, base_delay=60)
        def decorated():
            return always_fail()

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            with pytest.raises(GarminConnectTooManyRequestsError):
                decorated()

        mock_sleep.assert_has_calls([call(60.0), call(120.0)])

    def test_other_exception_not_retried(self):
        """Andere Exceptions werden sofort weitergeworfen, kein sleep."""
        boom = MagicMock(side_effect=ValueError("boom"))

        @retry_on_rate_limit(max_retries=2, base_delay=60)
        def decorated():
            return boom()

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            with pytest.raises(ValueError, match="boom"):
                decorated()

        assert boom.call_count == 1  # kein Retry
        mock_sleep.assert_not_called()

    def test_succeeds_after_one_retry(self):
        """Wenn beim 2. Versuch Erfolg, wird 'ok' zurückgegeben."""
        with patch("app.utils.retry.time.sleep"):
            fn = make_flaky(GarminConnectTooManyRequestsError, fail_times=1)
            result = fn()

        assert result == "ok"

    def test_succeeds_after_two_retries(self):
        """Wenn beim 3. Versuch Erfolg, wird 'ok' zurückgegeben."""
        with patch("app.utils.retry.time.sleep"):
            fn = make_flaky(GarminConnectTooManyRequestsError, fail_times=2)
            result = fn()

        assert result == "ok"

    def test_no_sleep_on_success(self):
        """Ohne Fehler wird time.sleep nie aufgerufen."""
        @retry_on_rate_limit(max_retries=2, base_delay=60)
        def always_ok():
            return "ok"

        with patch("app.utils.retry.time.sleep") as mock_sleep:
            result = always_ok()

        assert result == "ok"
        mock_sleep.assert_not_called()
