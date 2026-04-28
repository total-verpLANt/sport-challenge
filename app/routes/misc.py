from pathlib import Path

from flask import Blueprint, render_template

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/changelog")
def changelog():
    changelog_path = Path(__file__).parent.parent.parent / "CHANGELOG.md"
    content = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""
    return render_template("misc/changelog.html", changelog=content)
