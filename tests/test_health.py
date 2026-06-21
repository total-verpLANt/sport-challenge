"""Tests für die Liveness-Probe /health und die TRUSTED_HOSTS-Härtung (Ticket tjs)."""
import importlib

from app import create_app


def test_health_returns_ok_without_login(client, db):
    """/health antwortet ohne Login mit 200 'ok' (Liveness-Probe)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "ok"


def _config_with_trusted_hosts(monkeypatch, value):
    """Lädt config.Config mit gesetzter TRUSTED_HOSTS-Env neu."""
    monkeypatch.setenv("TRUSTED_HOSTS", value)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-for-production")
    import config as config_module
    importlib.reload(config_module)
    return config_module.Config


def test_trusted_hosts_auto_adds_localhost(monkeypatch):
    """Gesetztes TRUSTED_HOSTS ergänzt automatisch localhost + 127.0.0.1."""
    cfg = _config_with_trusted_hosts(monkeypatch, "sport.example.com")
    assert "sport.example.com" in cfg.TRUSTED_HOSTS
    assert "localhost" in cfg.TRUSTED_HOSTS
    assert "127.0.0.1" in cfg.TRUSTED_HOSTS
    # Wieder neu laden ohne Env, damit andere Tests sauber bleiben:
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    import config as config_module
    importlib.reload(config_module)


def test_trusted_hosts_none_when_unset(monkeypatch):
    """Ohne TRUSTED_HOSTS bleibt die Validierung aus (None) – lokale Dev unberührt."""
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-for-production")
    import config as config_module
    importlib.reload(config_module)
    assert config_module.Config.TRUSTED_HOSTS is None


def test_health_passes_host_gate_with_localhost(monkeypatch):
    """Mit aktivem TRUSTED_HOSTS kommt der Healthcheck-Host 'localhost' durch (200)."""
    cfg = _config_with_trusted_hosts(monkeypatch, "sport.example.com")
    app = create_app(cfg)
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()
    # Fremder Host wird weiterhin mit 400 abgewiesen:
    resp_bad = client.get("/health", headers={"Host": "evil.example.com"})
    assert resp_bad.status_code == 400
    # Container-interner Healthcheck-Host kommt durch:
    resp_ok = client.get("/health", headers={"Host": "localhost:5000"})
    assert resp_ok.status_code == 200
    monkeypatch.delenv("TRUSTED_HOSTS", raising=False)
    import config as config_module
    importlib.reload(config_module)
