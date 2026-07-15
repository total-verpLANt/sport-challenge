"""Unit-Tests fuer app.utils.urls.is_safe_external_url (reine Unit-Tests, keine App-Fixture)."""

from app.utils.urls import is_safe_external_url


def test_is_safe_external_url_accepts_http_https():
    assert is_safe_external_url("http://example.org") is True
    assert is_safe_external_url("https://example.org/pfad?x=1") is True
    # urlparse lowercased das Scheme automatisch -> Grossschreibung ist ok
    assert is_safe_external_url("HTTP://example.org") is True
    assert is_safe_external_url("HTTPS://example.org/pfad") is True


def test_is_safe_external_url_rejects_javascript_data_scheme():
    assert is_safe_external_url("javascript:alert(1)") is False
    assert is_safe_external_url("data:text/html;base64,x") is False
    assert is_safe_external_url("ftp://x.de") is False
    assert is_safe_external_url("mailto:a@b.de") is False


def test_is_safe_external_url_rejects_relative_and_empty():
    assert is_safe_external_url("") is False
    assert is_safe_external_url("/relativ") is False
    assert is_safe_external_url("example.com") is False
    assert is_safe_external_url("https://") is False  # kein netloc
    assert is_safe_external_url(None) is False
    # Hinweis: urlparse (Python >=3.12, WHATWG) strippt fuehrende
    # Space-/C0-Zeichen selbst -> " https://..." wird als https erkannt.
    # Das ist unkritisch (Ergebnis bleibt eine http(s)-URL); die Route
    # strippt Eingaben ohnehin vor der Pruefung.
    assert is_safe_external_url(" https://example.org") is True
    # Trailing Whitespace landet im Pfad, nicht im Scheme -> ebenfalls ok
    assert is_safe_external_url("https://example.org ") is True


def test_is_safe_external_url_rejects_overlong():
    assert is_safe_external_url("https://example.org/" + "a" * 500) is False
    # Genau am Limit (500 Zeichen) ist noch erlaubt
    url_at_limit = "https://example.org/" + "a" * (500 - len("https://example.org/"))
    assert len(url_at_limit) == 500
    assert is_safe_external_url(url_at_limit) is True
