# Briefing: 3.2 Connector-Import (Garmin/Strava → Challenge-Activity)

## Mission
Epic: Challenge-System — Import von Connector-Aktivitäten in die Challenge.

## Your Task
Erweitere `app/routes/challenge_activities.py` um Import-Routes. Erstelle ein Import-Template.

## Business Rules
- User wählt aus seinen Garmin/Strava-Aktivitäten aus, welche importiert werden
- Kein Vollautomatik – bewusste Auswahl
- Duplikate verhindern via external_id (z.B. Garmin Activity ID)
- Source wird auf "garmin" oder "strava" gesetzt

## Available Code

### Existing Connector System
```python
from app.connectors import PROVIDER_REGISTRY
# PROVIDER_REGISTRY = {"garmin": GarminConnector, "strava": StravaConnector}

from app.models.connector import ConnectorCredential
# ConnectorCredential: user_id, provider_type, credentials (Fernet-encrypted dict)

# Usage pattern (from app/routes/activities.py):
cred = ConnectorCredential.query.filter_by(user_id=current_user.id, provider_type=provider_type).first()
connector_cls = PROVIDER_REGISTRY.get(provider_type)
connector = connector_cls(user_id=current_user.id)
connector.connect(cred.credentials)
updates = connector.get_token_updates()
if updates:
    updated = dict(cred.credentials)
    updated.update(updates)
    cred.credentials = updated
    db.session.commit()
raw = connector.get_activities(monday, sunday)
# raw = list of dicts with keys: startTimeLocal, activityName, activityType.typeKey, duration (seconds), distance, averageHR, calories
```

### Existing challenge_activities.py (just created in 3.1)
The file already has `challenge_activities_bp` with routes for /log, /my-week, /delete.
You need to ADD routes to this existing file. Read it first to understand the structure.

### Activity Model
```python
from app.models.activity import Activity
# source: "manual", "garmin", "strava"
# external_id: String(255), nullable — used for deduplication
```

## Deliverable

### Modify: `app/routes/challenge_activities.py` — ADD these routes:

1. **`GET /import`** — Show Connector activities for selection
   - Find user's ConnectorCredentials
   - If no credentials: flash info "Verbinde zuerst einen Connector", redirect to connectors
   - Get current week's activities from connector (reuse existing pattern)
   - Support `?offset=N` for week navigation
   - Filter out already-imported activities (check external_id in DB)
   - Pass to template as selectable list
   - For external_id generation: use a composite key like "{provider}:{startTimeLocal}" or the raw ID if available

2. **`POST /import`** — Import selected activities
   - Read selected activity indices from form checkboxes
   - For each selected: create Activity with source=provider_type, external_id, duration converted from seconds to minutes
   - Skip if external_id already exists in DB (double-check)
   - Flash success with count, redirect to my-week

### Create: `app/templates/activities/import.html` (NEW)
- Week navigation (same offset pattern as my_week)
- If no connector configured: info message with link to connectors page
- Checkbox list of available activities:
  - Each row: checkbox, date, name, type, duration (formatted), distance
  - Already-imported activities: shown disabled/grayed with "Bereits importiert" badge
- "Ausgewählte importieren" submit button
- Responsive: table-responsive or card layout on mobile
- Form with CSRF token

## File Ownership
- Modify: `app/routes/challenge_activities.py` (ADD routes)
- Create: `app/templates/activities/import.html` (NEW)
- Do NOT modify any other files

## Verification
```bash
SECRET_KEY=test .venv/bin/python -c "from app.routes.challenge_activities import challenge_activities_bp; print(f'Routes: {len(challenge_activities_bp.deferred_functions)}'); print('OK')"
```
Should show 6 routes now (4 existing + 2 new).

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/routes/challenge_activities.py, app/templates/activities/import.html
SUMMARY: Added connector import routes and template
RESULT_END
```
