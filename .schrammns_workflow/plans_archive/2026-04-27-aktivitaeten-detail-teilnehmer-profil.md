# Plan: Aktivitäten-Detailansicht & Teilnehmer-Profil im Dashboard

**Date:** 2026-04-27
**Goal:** Aktivitäten anklickbar (Detailansicht mit Screenshot) + Dashboard-Teilnehmer anklickbar (deren Aktivitäten anzeigen)
**Research:** `.schrammns_workflow/research/2026-04-27-aktivitaeten-detail-teilnehmer-profil.md`

---

## Executive Summary

5 Issues in 3 Waves. Beide Features bauen auf vorhandener Infrastruktur auf (Static-Serving für Screenshots, `_active_participation()`, `ChallengeParticipation`-Queries). Kein neues Model, keine Migration nötig.

**Wichtig:** Der dokumentierte Dashboard-Template-Bug (`url_for('challenge_activities.log')`) ist **bereits gefixt** – `log_form` steht korrekt auf Zeile 92. Der Test-Docstring in `test_dashboard.py` ist veraltet.

**Policy (entschieden):** Activity-Details sichtbar für alle Challenge-Teilnehmer derselben Challenge (nicht nur Eigentümer).

---

## Baseline Audit

| Metrik | Wert | Verifikation |
|--------|------|-------------|
| Betroffene Dateien | 7 | s. Files to Modify |
| challenge_activities.py LOC | 371 | `wc -l` |
| Tests in test_activities_log.py | 4 | `grep -c "^def test_"` |
| Tests in test_dashboard.py | 3 | `grep -c "^def test_"` |
| Git-Status | sauber (1 untracked research-Datei) | `git status` |
| Dashboard-Bug | bereits gefixt (Zeile 92: log_form) | `grep -n url_for dashboard/index.html` |

---

## Files to Modify

| File | Change |
|------|--------|
| `app/routes/challenge_activities.py` | `User`-Import hinzufügen + 2 neue GET-Routen anhängen |
| `app/templates/activities/detail.html` | **NEU** – Activity-Detailansicht mit Screenshot |
| `app/templates/activities/my_week.html` | sport_type-Text in Link auf Detail-Route umwandeln |
| `app/templates/activities/user_activities.html` | **NEU** – Aktivitätsliste eines Teilnehmers |
| `app/templates/dashboard/index.html` | Teilnehmernamen in Links umwandeln |
| `tests/test_activities_log.py` | 3 neue Tests: Detail-Route (owner, other participant, non-participant) |
| `tests/test_dashboard.py` | 2 neue Tests: user_activities-Route + Dashboard-Rendering reparieren |

---

## Implementation Detail

### I-01: Activity-Detail Route + Template

#### `app/routes/challenge_activities.py` – Änderungen

**Neuer Import** (nach Zeile 12 einfügen):
```python
from app.models.user import User
```

**Neue Route** (anhängen nach Zeile 371):
```python
@challenge_activities_bp.route("/<int:activity_id>", methods=["GET"])
@login_required
def activity_detail(activity_id):
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        flash("Aktivität nicht gefunden.", "danger")
        return redirect(url_for("challenge_activities.my_week"))
    # Berechtigungscheck: Eigentümer ODER akzeptierter/ausgestiegener Challenge-Teilnehmer
    is_owner = activity.user_id == current_user.id
    participation = db.session.scalar(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == activity.challenge_id,
            ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
        )
    )
    if not is_owner and participation is None:
        flash("Keine Berechtigung für diese Aktivität.", "danger")
        return redirect(url_for("challenge_activities.my_week"))
    challenge = db.session.get(Challenge, activity.challenge_id)
    owner = db.session.get(User, activity.user_id)
    return render_template(
        "activities/detail.html",
        activity=activity,
        challenge=challenge,
        owner=owner,
        is_owner=is_owner,
    )
```

#### `app/templates/activities/detail.html` – NEU

Bootstrap 5.3.3, extends `base.html`. Zeigt:
- Breadcrumb: Challenge-Name → Meine Woche → Aktivität
- Karte mit: Datum, Sportart, Dauer (Min), Quelle (manual/garmin/strava als Badge), Erstellt-Zeitstempel
- Screenshot groß (max 100% Breite, falls vorhanden) + Link zum Original in neuem Tab
- Falls nicht Eigentümer: "Aktivität von `{{ owner.display_name }}`" als Badge
- Zurück-Button: `url_for('challenge_activities.my_week')`

---

### I-02: Links in my_week.html

**Datei:** `app/templates/activities/my_week.html`, Zeile 73

Vorher:
```html
<strong>{{ activity.sport_type }}</strong>
```

Nachher:
```html
<a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}"
   class="text-decoration-none text-body fw-bold">{{ activity.sport_type }}</a>
```

Kein weiterer Eingriff nötig – Thumbnail (Zeile 77-84) bleibt unverändert, verlinkt weiterhin auf Vollbild in neuem Tab.

---

### I-03: User-Aktivitäten Route + Template

#### `app/routes/challenge_activities.py` – neue Route (nach I-01 anhängen)

```python
@challenge_activities_bp.route("/user/<int:user_id>", methods=["GET"])
@login_required
def user_activities(user_id):
    target_user = db.session.get(User, user_id)
    if target_user is None:
        flash("Benutzer nicht gefunden.", "danger")
        return redirect(url_for("dashboard.index"))
    # Aktive Challenge des aktuellen Users
    my_participation = _active_participation()
    if my_participation is None:
        flash("Du nimmst an keiner aktiven Challenge teil.", "warning")
        return redirect(url_for("dashboard.index"))
    challenge = db.session.get(Challenge, my_participation.challenge_id)
    # Ziel-User muss dieselbe Challenge haben
    target_participation = db.session.scalar(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == user_id,
            ChallengeParticipation.challenge_id == challenge.id,
        )
    )
    if target_participation is None:
        flash("Dieser Benutzer nimmt nicht an deiner Challenge teil.", "warning")
        return redirect(url_for("dashboard.index"))
    activities = db.session.scalars(
        db.select(Activity)
        .where(
            Activity.user_id == user_id,
            Activity.challenge_id == challenge.id,
        )
        .order_by(Activity.activity_date.desc(), Activity.created_at.desc())
    ).all()
    return render_template(
        "activities/user_activities.html",
        target_user=target_user,
        target_participation=target_participation,
        challenge=challenge,
        activities=activities,
    )
```

#### `app/templates/activities/user_activities.html` – NEU

Bootstrap 5.3.3, extends `base.html`. Zeigt:
- Header: „Aktivitäten von `{{ target_user.display_name }}`" + Challenge-Name als Untertitel
- Wochenziel + Status-Badge (accepted/bailed_out)
- Aktivitätsliste (nach Datum gruppiert oder einfache Liste absteigend):
  - Datum, Sportart, Dauer, Quelle-Badge
  - Screenshot-Thumbnail falls vorhanden (gleicher Pattern wie my_week.html:77-84), verlinkt auf `activity_detail`
- Zurück-Button: `url_for('dashboard.index')`
- Leermeldung falls keine Aktivitäten

---

### I-04: Dashboard-Links

**Datei:** `app/templates/dashboard/index.html`, Zeile ~46

Vorher (innerhalb `<td class="text-nowrap">`):
```html
{{ p.user.display_name }}
```

Nachher:
```html
<a href="{{ url_for('challenge_activities.user_activities', user_id=p.user.id) }}"
   class="text-decoration-none text-body">{{ p.user.display_name }}</a>
```

`is_bailed`-Check bleibt unverändert (Strikethrough `<s>` drum herum – Link bleibt trotzdem aktiv).

---

### I-05: Tests

#### `tests/test_activities_log.py` – neue Tests (ab Zeile 145)

```
test_activity_detail_owner:
  GET /challenge-activities/<id> als Eigentümer → 200, sport_type im HTML

test_activity_detail_other_participant:
  GET als zweiter User in derselben Challenge → 200 (Teilnehmer darf sehen)

test_activity_detail_non_participant:
  GET als User nicht in Challenge → 302 + flash "Keine Berechtigung"
```

Alle drei nutzen `_create_and_login()` + `_create_challenge_with_participation()` aus derselben Datei.

#### `tests/test_dashboard.py` – Erweiterungen (ab Zeile 106)

```
test_user_activities_as_participant:
  GET /challenge-activities/user/<id> als Teilnehmer derselben Challenge → 200, display_name im HTML

test_user_activities_as_non_participant:
  GET als User ohne Participation → 302 zu /dashboard/

test_dashboard_renders_with_challenge [Update]:
  Bestehenden test_dashboard_with_challenge erweitern: veralten Docstring entfernen,
  tatsächlich GET /dashboard/ rendern (client-Fixture statt app-Fixture) und 200 + HTML-Inhalt prüfen.
```

---

## Verification Procedures

```bash
# Nach jeder Wave: vollständige Test-Suite
.venv/bin/pytest -v

# Nach I-01: neue Route ladbar
.venv/bin/python -c "from app.routes.challenge_activities import activity_detail; print('OK')"

# Nach I-05: neue Tests gezielt
.venv/bin/pytest tests/test_activities_log.py -v -k "detail"
.venv/bin/pytest tests/test_dashboard.py -v

# Browser-Smoke (Playwright/Haiku-Subagent):
# - /challenge-activities/<id> mit bekannter ID → Detailansicht sichtbar
# - /dashboard/ → Teilnehmernamen sind Links
# - /challenge-activities/user/<id> → Aktivitätsliste sichtbar
```

---

## Wave Structure

```
Wave 1 ──────────────────────────────────────
  I-01  Activity-Detail Route + Template
        (challenge_activities.py + detail.html)
        Risiko: reversible / local / autonomous-ok
        Größe: S

Wave 2 ──────────────────────────────────────  (depends: I-01)
  I-02  Links in my_week.html → Detail-Route
        (my_week.html)
        Risiko: reversible / local / autonomous-ok
        Größe: S

  I-03  User-Aktivitäten Route + Template      (depends: I-01 – shared file)
        (challenge_activities.py + user_activities.html)
        Risiko: reversible / local / autonomous-ok
        Größe: S

Wave 3 ──────────────────────────────────────  (depends: I-02, I-03)
  I-04  Dashboard-Links → User-Profil
        (dashboard/index.html)
        Risiko: reversible / local / autonomous-ok
        Größe: S

  I-05  Tests für beide Features
        (test_activities_log.py + test_dashboard.py)
        Risiko: reversible / local / autonomous-ok
        Größe: S
```

**Kritischer Pfad:** I-01 → I-03 → I-04 (3 Waves, sequenziell)

---

## Boundaries

**Always:**
- `login_required` auf allen neuen Routen
- Berechtigungscheck: Activity-Detail nur für Challenge-Teilnehmer oder Eigentümer
- User-Aktivitäten nur für Teilnehmer derselben Challenge
- Screenshots via `url_for('static', filename=activity.screenshot_path)` (kein neuer Serving-Mechanismus)
- `User`-Import in challenge_activities.py hinzufügen (aktuell nicht importiert)
- Bootstrap 5.3.3-Pattern wie in bestehenden Templates
- Atomare Commits pro Issue (I-01 bis I-05 je ein Commit)

**Never:**
- Kein neues Model, keine Alembic-Migration
- Keine CSRF-Token auf GET-Routen
- Keine Screenshots für nicht-autorisierte User servieren (Static-Serving ist bereits ohne Auth – akzeptiert, UUID-Dateinamen schützen)

**Ask First:** (leer – alle Entscheidungen getroffen)

---

## Design Decisions

| Entscheidung | Gewählt | Abgelehnt | Grund |
|---|---|---|---|
| Sichtbarkeit Activity-Detail | Alle Challenge-Teilnehmer | Nur Eigentümer | Soziale Funktion: Teilnehmer sollen gegenseitig Aktivitäten sehen |
| User-Aktivitäten-Route Ort | `challenge_activities_bp` (`/challenge-activities/user/<id>`) | Eigener Blueprint | Vermeidet Blueprint-Proliferation, passt thematisch |
| Screenshot-Auth | Keine (Static-Serving, UUID-Namen) | Eigene Auth-Route | UUID-Namen sind ausreichende Obscurity, kein Overhead |
| Dashboard-Bug | Kein Handlungsbedarf (bereits gefixt) | Separater Fix-Commit | Bug ist in Zeile 92 bereits korrekt |

---

## Invalidation Risks

| Annahme | Risiko wenn falsch | Betroffene Issues |
|---|---|---|
| `_active_participation()` gibt Participation zur aktuellen Challenge zurück | I-03 würde falsche Challenge laden | I-03 |
| `User`-Import fehlt in challenge_activities.py | ImportError bei I-01 | I-01 |
| Dashboard-Bug bereits gefixt | Test-Erweiterung in I-05 würde weiter scheitern | I-05 |

---

## Rollback

```bash
# Checkpoint vor Start
git tag pre-aktivitaeten-detail-$(date +%Y%m%d)

# Per Issue rollback (atomare Commits):
git revert HEAD     # letzten Commit rückgängig
git revert HEAD~2   # zwei Commits rückgängig

# Alles rückgängig bis zum Tag:
git reset --hard pre-aktivitaeten-detail-<datum>
```
