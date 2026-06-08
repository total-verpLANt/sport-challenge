"""Secure-Cookie-Konfiguration (Issue 26x)

Abdeckung:
  1. test_secure_cookies_enabled  – SECURE_COOKIES=1 → Session- UND Remember-Me-Cookie Secure
  2. test_secure_cookies_default  – ohne SECURE_COOKIES → Secure-Flags False (lokale HTTP-Dev)
  3. test_cookie_hardening_always – HTTPONLY/SAMESITE unabhängig vom Transport gesetzt

Hinweis: config.py liest die Umgebungsvariablen zur Import-Zeit. Deshalb wird das
Modul je Testfall via importlib.reload mit gesetztem Environment neu geladen und
anschließend in try/finally wieder in den Ausgangszustand zurückgeladen.
"""

import importlib

import pytest

import config as config_module


def _reload_config(monkeypatch, secure_cookies_value):
    # SECRET_KEY ist Pflicht – sonst RuntimeError beim Import.
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-for-production")
    if secure_cookies_value is None:
        monkeypatch.delenv("SECURE_COOKIES", raising=False)
    else:
        monkeypatch.setenv("SECURE_COOKIES", secure_cookies_value)
    importlib.reload(config_module)
    return config_module.Config


@pytest.fixture()
def restore_config():
    """Stellt nach dem Test den ursprünglichen Modulzustand wieder her."""
    yield
    importlib.reload(config_module)


def test_secure_cookies_enabled(monkeypatch, restore_config):
    cfg = _reload_config(monkeypatch, "1")
    assert cfg.SESSION_COOKIE_SECURE is True
    assert cfg.REMEMBER_COOKIE_SECURE is True


def test_secure_cookies_default(monkeypatch, restore_config):
    # Ohne SECURE_COOKIES (lokale Dev über HTTP) dürfen Cookies NICHT Secure sein,
    # sonst sendet der Browser sie über HTTP nicht → Login kaputt.
    cfg = _reload_config(monkeypatch, None)
    assert cfg.SESSION_COOKIE_SECURE is False
    assert cfg.REMEMBER_COOKIE_SECURE is False


def test_secure_cookies_explicit_zero(monkeypatch, restore_config):
    cfg = _reload_config(monkeypatch, "0")
    assert cfg.SESSION_COOKIE_SECURE is False
    assert cfg.REMEMBER_COOKIE_SECURE is False


def test_cookie_hardening_always(monkeypatch, restore_config):
    # HTTPONLY (XSS) und SAMESITE=Lax (CSRF) sind transport-unabhängig immer gesetzt.
    cfg = _reload_config(monkeypatch, "0")
    assert cfg.SESSION_COOKIE_HTTPONLY is True
    assert cfg.REMEMBER_COOKIE_HTTPONLY is True
    assert cfg.SESSION_COOKIE_SAMESITE == "Lax"
    assert cfg.REMEMBER_COOKIE_SAMESITE == "Lax"
