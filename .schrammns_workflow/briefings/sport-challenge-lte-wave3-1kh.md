# Briefing: 4.2 Dashboard-Route + Template

## Mission
Epic: Challenge-System — Dashboard/Leaderboard als Startseite.

## Your Task
Erstelle `app/routes/dashboard.py` und `app/templates/dashboard/index.html` für das Leaderboard.

## Business Rules
- Tabelle: Zeilen = Teilnehmer, Spalten = Wochen
- Zellen zeigen Anzahl erfüllter Tage (≥30 Min Gesamtdauer)
- "3+" bei Übererfüllung (mehr Tage als Ziel)
- Krankheitswochen markiert (z.B. Kranken-Icon)
- Strafstand pro Teilnehmer sichtbar (Gesamt-€)
- Bailout-User ausgegraut mit Gesamtstrafe + Gebühr
- Alle Teilnehmer sehen den Fortschritt aller anderen
- Responsive: horizontales Scrollen auf Mobile

## Available Service
```python
from app.services.weekly_summary import get_challenge_summary

# Returns:
# {
#     "challenge": Challenge object,
#     "weeks": [date, ...],  # Monday dates
#     "participants": [
#         {
#             "user": User object (.email),
#             "weekly_goal": int,
#             "status": str,  # accepted, bailed_out
#             "weeks": {
#                 date: {
#                     "fulfilled_days": int,
#                     "is_sick": bool,
#                     "penalty": float,
#                     "overachieved": bool,  # fulfilled_days > weekly_goal
#                 },
#                 ...
#             },
#             "total_penalty": float,
#         },
#         ...
#     ]
# }
```

## Available Models
```python
from app.models.challenge import Challenge, ChallengeParticipation
from app.extensions import db
```

## Existing Patterns
```python
from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
```

## Deliverable

### File 1: `app/routes/dashboard.py` (NEW)

Blueprint: `dashboard_bp = Blueprint("dashboard", __name__, template_folder="../templates")`

Routes:

1. **`GET /`** — Dashboard/Leaderboard
   - Find active challenge (most recent or where today is between start/end)
   - If no active challenge: show "Keine aktive Challenge" message
   - Call get_challenge_summary(challenge) for data
   - Template: `dashboard/index.html`

### File 2: `app/templates/dashboard/index.html` (NEW)

Layout:
```
Challenge: "Name" (DD.MM.YYYY – DD.MM.YYYY)

+---------------+------+--------+--------+--------+--------+--------+
| Teilnehmer    | Ziel | KW 1   | KW 2   | KW 3   | ...    | Strafe |
+---------------+------+--------+--------+--------+--------+--------+
| user@mail.com | 3x   | 3      | 🤒     | 2      |        | 5,00€  |
| jane@mail.com | 2x   | 3+     | 2      | 2      |        | 0,00€  |
| bail@mail.com | 3x   | 1      | -      | -      |        | 35,00€ |
+---------------+------+--------+--------+--------+--------+--------+
```

Implementation details:
- Use `<div class="table-responsive">` wrapper for horizontal scroll on mobile
- Bootstrap `table table-bordered table-hover`
- Week columns: show KW number (e.g., "KW 18") as header, with date range on hover (title attribute)
- Cell content:
  - Number of fulfilled days (0, 1, 2, 3)
  - If fulfilled_days > weekly_goal: show with "+" suffix and green background (e.g., "3+" with `class="table-success"`)
  - If fulfilled_days >= weekly_goal: green background (`table-success`)
  - If 0 < fulfilled_days < weekly_goal: yellow (`table-warning`)
  - If fulfilled_days == 0 and not sick: red (`table-danger`)
  - If sick: show "🤒" with gray background
- Penalty column: formatted as "X,XX €" (German number format)
- Bailed-out users: row with `class="text-muted"` or `opacity-50`, penalty includes bailout fee
- Below table: Summary card with total penalty sum (Spendentopf)
- Quick action links: "Aktivität eintragen", "Meine Woche", "Bonus-Challenges"

Responsive:
- `table-responsive` wrapper enables horizontal scroll
- On mobile: sticky first column (participant name) if possible, or just scroll
- Quick links as Bootstrap button group

## File Ownership
- Create: `app/routes/dashboard.py` (NEW)
- Create: `app/templates/dashboard/index.html` (NEW)
- Do NOT modify `app/__init__.py` or any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.routes.dashboard import dashboard_bp; print(f'Routes: {len(dashboard_bp.deferred_functions)}'); print('OK')"
```

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/routes/dashboard.py, app/templates/dashboard/index.html
SUMMARY: Created dashboard route and leaderboard template
RESULT_END
```
