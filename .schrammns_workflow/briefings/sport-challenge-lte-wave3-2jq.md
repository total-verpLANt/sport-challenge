# Briefing: 3.1 Manuelle Aktivitäts-Eingabe + Screenshot-Upload

## Mission
Epic: Challenge-System — Manuelle Aktivitäts-Eingabe mit optionalem Screenshot-Upload.

## Your Task
Erstelle `app/routes/challenge_activities.py` mit Routes für manuelle Aktivitäts-Eingabe, Wochenübersicht und Löschen. Erstelle die zugehörigen Templates.

## Cross-Cutting Constraints
- POST-Forms mit CSRF-Token
- @login_required auf allen Routes
- Responsive: Bootstrap Grid, touch-freundlich
- Upload: `enctype="multipart/form-data"`, `accept="image/*"` für Kamera auf Mobile
- German UI labels

## Available Models & Utils
```python
from app.models.activity import Activity
# id, user_id, challenge_id, activity_date (Date), duration_minutes (Integer), 
# sport_type (String), source (String, default="manual"), external_id, screenshot_path, created_at

from app.models.challenge import Challenge, ChallengeParticipation
# ChallengeParticipation: user_id, challenge_id, weekly_goal, status (invited/accepted/bailed_out)

from app.utils.uploads import save_upload, delete_upload, allowed_file
# save_upload(file) -> str|None (relative path "uploads/uuid.ext")
# delete_upload(relative_path) -> None

from app.extensions import db
```

## Existing Route Pattern (from app/routes/admin.py)
```python
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db

bp = Blueprint("name", __name__, template_folder="../templates")

@bp.route("/path", methods=["POST"])
@login_required
def handler():
    ...
    db.session.commit()
    flash("Erfolgreich.")
    return redirect(url_for("name.other"))
```

## Deliverable

### File 1: `app/routes/challenge_activities.py` (NEW)

Blueprint: `challenge_activities_bp = Blueprint("challenge_activities", __name__, template_folder="../templates")`

Routes:

1. **`GET /log`** — Aktivitäts-Eingabeformular
   - Find user's active challenge participation (status="accepted")
   - If no active participation: flash warning, redirect to challenges index
   - Template: `activities/log.html`
   - Pass today's date as default for the date field

2. **`POST /log`** — Aktivität speichern
   - Read from form: activity_date, duration_minutes, sport_type
   - Optional: screenshot file from request.files
   - Validate: date within challenge period, duration > 0, sport_type not empty
   - Save screenshot via save_upload() if provided
   - Create Activity(user_id, challenge_id, activity_date, duration_minutes, sport_type, source="manual", screenshot_path)
   - Flash success, redirect to my_week

3. **`GET /my-week`** — Meine Aktivitäten dieser Woche
   - Show activities for current week (Monday-Sunday)
   - Support `?offset=N` for week navigation (same pattern as existing activities/week route)
   - Calculate daily totals (sum duration_minutes per day)
   - Show warning if any day has < 30 min total
   - Show fulfilled day count vs weekly_goal
   - Template: `activities/my_week.html`

4. **`POST /<int:activity_id>/delete`** — Aktivität löschen
   - Only own activities (check user_id == current_user.id)
   - Delete screenshot file if exists
   - Delete Activity from DB
   - Flash success, redirect to my_week

### File 2: `app/templates/activities/log.html` (NEW)
```html
{% extends "base.html" %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-12 col-md-8 col-lg-6">
    <h2>Aktivität eintragen</h2>
    <form method="post" enctype="multipart/form-data">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <div class="mb-3">
        <label for="activity_date" class="form-label">Datum</label>
        <input type="date" class="form-control" id="activity_date" name="activity_date" 
               value="{{ today }}" required max="{{ today }}">
      </div>
      <div class="mb-3">
        <label for="duration_minutes" class="form-label">Dauer (Minuten)</label>
        <input type="number" class="form-control" id="duration_minutes" name="duration_minutes" 
               min="1" required placeholder="z.B. 30">
      </div>
      <div class="mb-3">
        <label for="sport_type" class="form-label">Sportart</label>
        <input type="text" class="form-control" id="sport_type" name="sport_type" 
               required placeholder="z.B. Laufen, Krafttraining, Schwimmen">
      </div>
      <div class="mb-3">
        <label for="screenshot" class="form-label">Screenshot/Foto (optional)</label>
        <input type="file" class="form-control" id="screenshot" name="screenshot" 
               accept="image/*">
        <div class="form-text">Max. 5 MB, JPG/PNG/WebP</div>
      </div>
      <button type="submit" class="btn btn-primary w-100">Eintragen</button>
    </form>
  </div>
</div>
{% endblock %}
```

### File 3: `app/templates/activities/my_week.html` (NEW)
- Week navigation (previous/current/next) with offset parameter
- Summary card: "X von Y Tagen geschafft" with progress bar
- Per-day breakdown: date, activities list, daily total
- Warning badge if day total < 30 min: "⚠ Noch X Minuten bis 30 Min"
- Each activity: sport_type, duration, source badge, screenshot thumbnail (if exists), delete button
- Screenshot displayed as small thumbnail linking to full image: `{{ url_for('static', filename=activity.screenshot_path) }}`
- Responsive: stacked cards on mobile

## File Ownership
- Create: `app/routes/challenge_activities.py` (NEW)
- Create: `app/templates/activities/log.html` (NEW)
- Create: `app/templates/activities/my_week.html` (NEW)
- Do NOT modify `app/__init__.py` or any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.routes.challenge_activities import challenge_activities_bp; print(f'Routes: {len(challenge_activities_bp.deferred_functions)}'); print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/routes/challenge_activities.py, app/templates/activities/log.html, app/templates/activities/my_week.html
SUMMARY: Created activity logging routes and templates
RESULT_END
```
