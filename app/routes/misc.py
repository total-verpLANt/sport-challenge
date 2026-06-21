from pathlib import Path

import markdown
from flask import Blueprint, render_template
from markupsafe import Markup

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/health")
def health():
    """Leichtgewichtige Liveness-Probe für den Docker-Healthcheck.

    Bewusst ohne DB-Zugriff, Login oder Rate-Limit: prüft nur, ob der
    Prozess Requests beantwortet. Der container-interne Healthcheck spricht
    diesen Endpoint über `localhost` an – dafür sind `localhost`/`127.0.0.1`
    in der TRUSTED_HOSTS-Allowlist freigeschaltet (siehe config.py).
    """
    return "ok", 200, {"Content-Type": "text/plain; charset=utf-8"}


@misc_bp.route("/changelog")
def changelog():
    changelog_path = Path(__file__).parent.parent.parent / "CHANGELOG.md"
    raw = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
    html = Markup(markdown.markdown(raw, extensions=["tables", "fenced_code"]))  # nosec B704 – Quelle ist statische Projektdatei, kein User-Input
    return render_template("misc/changelog.html", changelog=html)
