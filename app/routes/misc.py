from pathlib import Path

import markdown
from flask import Blueprint, render_template
from markupsafe import Markup

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/changelog")
def changelog():
    changelog_path = Path(__file__).parent.parent.parent / "CHANGELOG.md"
    raw = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
    html = Markup(markdown.markdown(raw, extensions=["tables", "fenced_code"]))  # nosec B704 – Quelle ist statische Projektdatei, kein User-Input
    return render_template("misc/changelog.html", changelog=html)
