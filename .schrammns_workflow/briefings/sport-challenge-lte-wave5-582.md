# Briefing: 5.2 Integrations-Tests

## Mission
Epic: Challenge-System — Umfassende Tests für das gesamte Challenge-System.

## Your Task
Erstelle Testdateien für die neuen Challenge-System-Komponenten. Bestehende 41 Tests dürfen NICHT brechen.

## Test Infrastructure (from tests/conftest.py)
```python
import pytest
from app import create_app
from app.extensions import db as _db

class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False

@pytest.fixture(scope="session")
def app():
    app = create_app(TestConfig)
    return app

@pytest.fixture()
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()

@pytest.fixture()
def client(app, db):
    return app.test_client()
```

IMPORTANT: Tests must use the existing fixtures. CSRF is disabled in tests.
For authenticated routes, create a user, approve them, then login:
```python
from app.models.user import User

def _create_and_login(client, db, email="test@test.com", password="testpass123", is_admin=False):
    user = User(email=email, is_approved=True)
    if is_admin:
        user.role = "admin"
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": password})
    return user
```

## Models Available
```python
from app.models.challenge import Challenge, ChallengeParticipation
from app.models.activity import Activity
from app.models.sick_week import SickWeek
from app.models.penalty import PenaltyOverride
from app.models.bonus import BonusChallenge, BonusChallengeEntry
```

## Route Endpoints (for reference)
- challenges_bp: /challenges/ (index, create, detail, invite, accept, decline, bailout, sick)
- challenge_activities_bp: /challenge-activities/ (log_form, log_submit, my_week, import_form, import_submit, delete_activity)
- dashboard_bp: /dashboard/ (index)
- bonus_bp: /bonus/ (index, create GET+POST, entry)

## Deliverable

Create these test files. Each should have focused, fast tests.

### File 1: `tests/test_challenge.py` (NEW)
```python
# Helper to create and login
# Helper to create a challenge

def test_admin_can_create_challenge(client, db):
    # Login as admin, POST /challenges/create with valid data
    # Assert redirect, challenge exists in DB

def test_non_admin_cannot_create_challenge(client, db):
    # Login as regular user, POST /challenges/create
    # Assert 403

def test_invite_user_to_challenge(client, db):
    # Admin creates challenge, invites another user
    # Assert ChallengeParticipation exists with status="invited"

def test_accept_invitation(client, db):
    # Create invitation, login as invited user, POST accept with weekly_goal=2
    # Assert status="accepted", weekly_goal=2

def test_decline_invitation(client, db):
    # Create invitation, login as invited user, POST decline
    # Assert ChallengeParticipation deleted

def test_bailout_from_challenge(client, db):
    # Accepted participant, POST bailout
    # Assert status="bailed_out", bailed_out_at set

def test_sick_week_creation(client, db):
    # Accepted participant, POST sick
    # Assert SickWeek created for current week's Monday

def test_duplicate_sick_week_rejected(client, db):
    # Already sick this week, POST sick again
    # Assert only one SickWeek exists (flash message)
```

### File 2: `tests/test_activities_log.py` (NEW)
```python
def test_log_manual_activity(client, db):
    # Login, have active challenge participation, POST /challenge-activities/log
    # Assert Activity created with correct fields

def test_log_activity_requires_participation(client, db):
    # Login without active participation, GET /challenge-activities/log
    # Assert redirect (no active challenge)

def test_delete_own_activity(client, db):
    # Create activity, POST delete
    # Assert Activity deleted from DB

def test_cannot_delete_others_activity(client, db):
    # Create activity for user A, login as user B, POST delete
    # Assert 403 or redirect with error
```

### File 3: `tests/test_penalty.py` (NEW)
```python
from datetime import date, timedelta
from app.services.penalty import get_week_mondays, count_fulfilled_days, calculate_weekly_penalty, calculate_total_penalty

def test_get_week_mondays(app):
    # Fixed date range, assert correct Monday list

def test_no_penalty_when_goal_met(app, db):
    # Create challenge + participation + 3 activities (each >=30 min on different days)
    # Assert calculate_weekly_penalty returns 0.0

def test_penalty_for_missed_days(app, db):
    # 1 of 3 days fulfilled → 2 × 5€ = 10€

def test_max_penalty_capped(app, db):
    # 0 of 3 → 3 × 5€ = 15€

def test_sick_week_no_penalty(app, db):
    # Create SickWeek → penalty = 0

def test_penalty_override_applied(app, db):
    # Create PenaltyOverride with 3.0 → returns 3.0

def test_two_per_week_goal(app, db):
    # weekly_goal=2, 0 fulfilled → 2 × 5€ = 10€

def test_day_aggregation(app, db):
    # Two 20-min activities on same day → day counts as fulfilled (40 min ≥ 30)
```

### File 4: `tests/test_dashboard.py` (NEW)
```python
def test_dashboard_requires_login(client, db):
    # GET /dashboard/ without login → redirect to login

def test_dashboard_no_challenge(client, db):
    # Login, GET /dashboard/ with no challenge → shows "keine aktive Challenge"

def test_dashboard_with_challenge(client, db):
    # Create challenge + participants + activities
    # GET /dashboard/ → 200, contains participant emails
```

### File 5: `tests/test_bonus.py` (NEW)
```python
def test_admin_can_create_bonus_challenge(client, db):
    # Login as admin, create challenge, POST /bonus/create
    # Assert BonusChallenge exists

def test_submit_bonus_entry(client, db):
    # Accepted participant, POST /bonus/<id>/entry with time
    # Assert BonusChallengeEntry created

def test_duplicate_entry_rejected(client, db):
    # Already submitted, POST again → IntegrityError handled gracefully

def test_bonus_requires_login(client, db):
    # GET /bonus/ without login → redirect
```

## IMPORTANT
- Use `with app.app_context():` when calling service functions directly
- For route tests, use the `client` fixture (already has app context)
- Date fields: use `date(2026, 5, 1)` style for reproducible tests
- All test functions MUST start with `test_`
- Run `SECRET_KEY=test .venv/bin/pytest -v` to verify ALL tests pass (old + new)

## File Ownership
- Create: `tests/test_challenge.py` (NEW)
- Create: `tests/test_activities_log.py` (NEW)
- Create: `tests/test_penalty.py` (NEW)
- Create: `tests/test_dashboard.py` (NEW)
- Create: `tests/test_bonus.py` (NEW)
- Do NOT modify any existing test files or app code

## Verification
```bash
SECRET_KEY=test .venv/bin/pytest -v --tb=short 2>&1 | tail -10
```
ALL tests must pass (41 existing + new ones).

## Output Format
```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: tests/test_challenge.py, tests/test_activities_log.py, tests/test_penalty.py, tests/test_dashboard.py, tests/test_bonus.py
SUMMARY: Created integration tests for challenge system
RESULT_END
```
