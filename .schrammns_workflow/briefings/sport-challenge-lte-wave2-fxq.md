# Briefing: 2.2 Challenge-Routes (Admin-CRUD + Einladungen)

## Mission
Epic: Challenge-System — Challenge-Verwaltung Routes + Templates.

## Your Task
Erstelle `app/routes/challenges.py` mit allen Challenge-Verwaltungs-Routes UND die zugehörigen Templates. Da Routes und Templates eng gekoppelt sind, baust du beides in einem Schritt.

## Cross-Cutting Constraints
- Alle POST-Forms enthalten `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
- Admin-Routes nutzen `@admin_required` (from app.utils.decorators)
- User-Routes nutzen `@login_required` (from flask_login)
- Templates erben von `base.html` mit `{% block content %}`
- Responsive Design: Bootstrap Grid, touch-freundliche Inputs
- German UI labels

## Existing Patterns

### Route Pattern (from app/routes/admin.py):
```python
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models.user import User
from app.utils.decorators import admin_required

admin_bp = Blueprint("admin", __name__, template_folder="../templates")

@admin_bp.route("/users")
@admin_required
def users():
    ...
    return render_template("admin/users.html", ...)
```

### Template Pattern (from base.html):
```html
{% extends "base.html" %}
{% block content %}
<h2>Title</h2>
...
{% endblock %}
```

### Flash messages:
```python
flash("Message text.")  # No category — renders as alert-info in base.html
```

## Models Available
```python
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.sick_week import SickWeek
from app.models.user import User
```

## Deliverable

### File 1: `app/routes/challenges.py` (NEW)

Blueprint: `challenges_bp = Blueprint("challenges", __name__, template_folder="../templates")`

Routes:

1. **`GET /`** — Challenge-Übersicht
   - If user has pending invitation: show it prominently
   - Show active challenge details if participant
   - If admin and no active challenge: show "Create" button
   - Template: `challenges/index.html`

2. **`GET /create`** — Challenge erstellen (Admin only)
   - Form: name, start_date, end_date, penalty_per_miss (default 5), bailout_fee (default 25)
   - Template: `challenges/create.html`

3. **`POST /create`** — Challenge speichern (Admin only)
   - Validate: name not empty, start_date < end_date, start_date >= today
   - Create Challenge with created_by_id = current_user.id
   - Flash success, redirect to challenge detail

4. **`GET /<int:challenge_id>`** — Challenge-Detail
   - Show participants with status, weekly_goal
   - If admin: show invite form (dropdown of approved users not yet in challenge)
   - If participant: show Accept/Decline buttons (if invited), Bailout button (if accepted), Sick button
   - Template: `challenges/detail.html`

5. **`POST /<int:challenge_id>/invite`** — User einladen (Admin only)
   - Create ChallengeParticipation(status="invited")
   - Flash success, redirect to detail

6. **`POST /<int:challenge_id>/accept`** — Einladung annehmen
   - Set status="accepted", accepted_at=now
   - Read weekly_goal from form (2 or 3, default 3)
   - Flash success, redirect to detail

7. **`POST /<int:challenge_id>/decline`** — Einladung ablehnen
   - Delete the ChallengeParticipation record
   - Flash info, redirect to challenges index

8. **`POST /<int:challenge_id>/bailout`** — Aus Challenge austreten
   - Set status="bailed_out", bailed_out_at=now
   - Flash info, redirect to detail

9. **`POST /<int:challenge_id>/sick`** — Krankheitsmeldung
   - Create SickWeek for current week (Monday)
   - Prevent duplicates (check if already exists)
   - Flash success, redirect to detail

### File 2: `app/templates/challenges/index.html` (NEW)
- Show pending invitation with Accept/Decline buttons and weekly_goal selector
- Show active challenge card if participant
- Admin: "Neue Challenge erstellen" button if no active challenge
- If no challenge and no invitation: info message

### File 3: `app/templates/challenges/create.html` (NEW)
- Form with inputs: Name (text), Startdatum (date), Enddatum (date), Strafe pro Versäumnis (number, default 5), Bailout-Gebühr (number, default 25)
- All inputs with Bootstrap form-control classes
- Submit button "Challenge erstellen"

### File 4: `app/templates/challenges/detail.html` (NEW)
- Challenge name, dates, rules summary
- Participant table: Name (email), Ziel, Status, Beigetreten am
- Admin section: Invite form with user select dropdown
- User section (if invited): Accept with goal selector + Decline buttons
- User section (if accepted): Bailout button (with confirm), Sick week button
- User section (if bailed_out): show bailed_out status

### Responsive notes:
- Use `table-responsive` wrapper on participant tables
- Use `col-12 col-md-6` for form columns
- Date inputs: `type="date"` (native mobile datepicker)

## File Ownership
- Create: `app/routes/challenges.py` (NEW)
- Create: `app/templates/challenges/index.html` (NEW)
- Create: `app/templates/challenges/create.html` (NEW)
- Create: `app/templates/challenges/detail.html` (NEW)
- Do NOT modify `app/__init__.py` or `base.html` — that's for later waves

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.routes.challenges import challenges_bp; print(f'Routes: {len(challenges_bp.deferred_functions)}'); print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/routes/challenges.py, app/templates/challenges/index.html, app/templates/challenges/create.html, app/templates/challenges/detail.html
SUMMARY: Created challenge routes and templates
RESULT_END
```
