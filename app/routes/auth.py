from __future__ import annotations

from functools import wraps

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.garmin.client import GarminClient

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "garmin_email" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "garmin_email" in session:
        return redirect(url_for("activities.week_view"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            error = "E-Mail und Passwort sind erforderlich."
        else:
            try:
                client = GarminClient(current_app.config["GARMIN_TOKEN_DIR"])
                client.login(email, password)
                session["garmin_email"] = email
                return redirect(url_for("activities.week_view"))
            except Exception as exc:
                error = f"Garmin-Login fehlgeschlagen: {exc}"

    return render_template("auth/login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
