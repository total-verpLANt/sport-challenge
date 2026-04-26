# Briefing: 4.3 Bonus-Challenge-Routes + Templates

## Mission
Epic: Challenge-System — Bonus-Challenge-Verwaltung mit Rangliste.

## Your Task
Erstelle `app/routes/bonus.py` mit Routes für Bonus-Challenge-Übersicht, Zeiteingabe und Admin-Erstellung. Erstelle die zugehörigen Templates.

## Cross-Cutting Constraints
- POST-Forms mit CSRF-Token
- Admin-Routes: @admin_required, User-Routes: @login_required
- Responsive: Bootstrap Grid, touch-freundlich
- German UI labels

## Available Models
```python
from app.models.bonus import BonusChallenge, BonusChallengeEntry
# BonusChallenge: id, challenge_id (FK), scheduled_date (Date), description (String), created_at
# BonusChallengeEntry: id, user_id (FK), bonus_challenge_id (FK), time_seconds (Float), created_at
#   UniqueConstraint("user_id", "bonus_challenge_id") — one entry per user per bonus challenge

from app.models.challenge import Challenge, ChallengeParticipation
from app.models.user import User
from app.extensions import db
```

## Existing Patterns
```python
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.utils.decorators import admin_required
```

## Deliverable

### File 1: `app/routes/bonus.py` (NEW)

Blueprint: `bonus_bp = Blueprint("bonus", __name__, template_folder="../templates")`

Routes:

1. **`GET /`** — Bonus-Challenge-Übersicht
   - List all bonus challenges for the active challenge, sorted by scheduled_date
   - For each: show description, date, and ranking (entries sorted by time_seconds ASC)
   - Show user names (email) in ranking
   - Highlight current user's entry
   - If admin: show "Neue Bonus-Challenge" button
   - Template: `bonus/index.html`

2. **`GET /create`** — Bonus-Challenge erstellen (Admin only)
   - Form: scheduled_date, description (default "50 Squat Jumps")
   - Need active challenge to exist
   - Template: `bonus/entry.html` (reuse for create form, or make a separate `bonus/create.html`)

3. **`POST /create`** — Bonus-Challenge speichern (Admin only)
   - Validate: date not empty, description not empty
   - Find active challenge (most recent, or only one)
   - Create BonusChallenge(challenge_id, scheduled_date, description)
   - Flash success, redirect to bonus index

4. **`POST /<int:bonus_id>/entry`** — Zeit eintragen
   - User must be accepted participant in the challenge
   - Read time_seconds from form (could be entered as minutes:seconds, convert to total seconds)
   - Check UniqueConstraint: if entry exists, flash error
   - Create BonusChallengeEntry(user_id, bonus_challenge_id, time_seconds)
   - Flash success, redirect to bonus index

### File 2: `app/templates/bonus/index.html` (NEW)
- Page title: "Bonus-Challenges"
- Admin button: "Neue Bonus-Challenge" (link to create)
- For each BonusChallenge, a card:
  - Header: description + date
  - Rangliste table: Platz, Name, Zeit (formatted mm:ss)
  - If user hasn't entered yet: inline form with time input + submit button
  - Highlight user's own entry with a badge
- If no bonus challenges: info message
- Responsive: cards stack on mobile

### File 3: `app/templates/bonus/create.html` (NEW)
- Form: Datum (date input), Beschreibung (text, default "50 Squat Jumps")
- Submit: "Bonus-Challenge erstellen"
- Responsive

### Time formatting helper
In the route file, add a helper or pass formatted times:
```python
def format_time(seconds: float) -> str:
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins}:{secs:02d}"
```

### Time input
For the entry form, accept input as minutes:seconds (e.g., "2:35" = 155 seconds).
Parse in the route:
```python
time_str = request.form.get("time", "").strip()
# Parse "M:SS" or just seconds
if ":" in time_str:
    parts = time_str.split(":")
    total_seconds = int(parts[0]) * 60 + int(parts[1])
else:
    total_seconds = float(time_str)
```

## File Ownership
- Create: `app/routes/bonus.py` (NEW)
- Create: `app/templates/bonus/index.html` (NEW)
- Create: `app/templates/bonus/create.html` (NEW)
- Do NOT modify `app/__init__.py` or any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.routes.bonus import bonus_bp; print(f'Routes: {len(bonus_bp.deferred_functions)}'); print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/routes/bonus.py, app/templates/bonus/index.html, app/templates/bonus/create.html
SUMMARY: Created bonus challenge routes and templates with ranking
RESULT_END
```
