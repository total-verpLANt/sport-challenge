# Research: Aktivitäten-Detailansicht & Teilnehmer-Profil im Dashboard

**Date:** 2026-04-27
**Scope:** `app/routes/`, `app/models/`, `app/templates/`, `app/services/`, `app/utils/uploads.py`, `tests/`

---

## Executive Summary

- Beide Features müssen **komplett neu gebaut** werden – keine Detail-Route für Aktivitäten, keine User-Profil-Route existiert
- Screenshots sind bereits als `uploads/{uuid}.ext` unter `app/static/uploads/` gespeichert und via Flask Static serviert – kein neuer Serving-Mechanismus nötig
- `get_challenge_summary()` liefert bereits vollständige `User`-Objekte (inkl. `user.id`) – direkt für Dashboard-Links nutzbar
- **Bekannter Bug im Dashboard-Template:** `url_for('challenge_activities.log')` statt `log_form` → Dashboard mit echten Daten crasht und ist deshalb in Tests nicht abgedeckt – muss vor oder zusammen mit Feature 2 gefixt werden
- Screenshot-Upload/-Serving ist **komplett ungetestet** – für Feature 1 sollten Tests nachgeliefert werden

---

## Key Files

| File | Purpose |
|------|---------|
| `app/models/activity.py` | Activity-Model (alle Felder inkl. screenshot_path) |
| `app/models/user.py` | User-Model (display_name Property) |
| `app/routes/challenge_activities.py` | Alle Aktivitäts-Routen (log, my-week, import, delete) |
| `app/routes/dashboard.py` | Dashboard-Route (index, GET /dashboard/) |
| `app/services/weekly_summary.py` | get_challenge_summary() → Participant-Daten |
| `app/services/penalty.py` | count_fulfilled_days(), calculate_total_penalty() |
| `app/utils/uploads.py` | save_upload(), delete_upload() |
| `app/templates/activities/my_week.html` | Wochen-Ansicht mit Thumbnail-Pattern (Vorlage) |
| `app/templates/dashboard/index.html` | Dashboard-Leaderboard (Teilnehmernamen als Text, Zeile 45) |
| `tests/conftest.py` | App/DB/Client-Fixtures, TestConfig |
| `tests/test_activities_log.py` | Bestehende Aktivitäts-Tests (Log, Delete, Zugriffskontrolle) |
| `tests/test_dashboard.py` | Dashboard-Tests (Service-Layer, Route mit Summary ungetestet) |

---

## Technology Stack

| Library/Framework | Version (if known) | Role |
|-------------------|--------------------|------|
| Flask | 3.x | Routing, Static File Serving |
| SQLAlchemy (Flask-SQLAlchemy) | 3.x | ORM, Queries |
| Bootstrap | 5.3.3 | UI-Layout in Templates |
| Flask-Login | - | current_user, login_required |
| Flask-WTF / CSRF | - | CSRF-Schutz auf POST-Routen |

---

## Findings

### Activity-Model (vollständig)

`app/models/activity.py`

| Feld | Typ | Constraints |
|------|-----|-------------|
| `id` | int | Primary Key |
| `user_id` | int | FK → users.id, NOT NULL |
| `challenge_id` | int | FK → challenges.id, NOT NULL |
| `activity_date` | date | NOT NULL |
| `duration_minutes` | int | NOT NULL |
| `sport_type` | str | String(100), NOT NULL |
| `source` | str | String(20), default "manual" (manual/garmin/strava) |
| `external_id` | str\|None | String(255), nullable |
| `screenshot_path` | str\|None | String(500), nullable |
| `created_at` | datetime | UTC, NOT NULL |

**Keine SQLAlchemy-Relationships** auf dem Model definiert – nur FK-Werte.

### Screenshot-Pfad-Aufbau

`app/utils/uploads.py`, `config.py:15-16`

- Physisch gespeichert: `{Projektroot}/app/static/uploads/{uuid4hex}.{ext}`
- DB-Wert (screenshot_path): `"uploads/{uuid4hex}.{ext}"`
- Template-Aufruf: `url_for('static', filename=activity.screenshot_path)`
- Max. Dateigröße: 5 MB; Erlaubt: jpg, jpeg, png, webp
- Löschen: `delete_upload(activity.screenshot_path)` baut Pfad via `Path(current_app.static_folder) / relative_path`

**Thumbnail-Pattern** in `my_week.html:77-84` als Vorlage bereits vorhanden – zeigt Thumbnail (max 80x120px) mit Link zum Vollbild in neuem Tab.

### Vorhandene Routen (challenge_activities_bp, Prefix `/challenge-activities`)

| URL | Methode | Funktion | Zeile |
|-----|---------|----------|-------|
| `/log` | GET | `log_form()` | :42 |
| `/log` | POST | `log_submit()` | :53 |
| `/my-week` | GET | `my_week()` | :119 |
| `/import` | GET | `import_form()` | :181 |
| `/import` | POST | `import_submit()` | :271 |
| `/<int:activity_id>/delete` | POST | `delete_activity()` | :356 |

**Keine GET-Route für Einzel-Aktivität** (`/<int:activity_id>`) vorhanden.

### Dashboard-Route

`app/routes/dashboard.py:15` – nur `/dashboard/` (GET), ruft `get_challenge_summary()` auf.

`app/templates/dashboard/index.html:45` – Teilnehmernamen als reiner Text:
```html
{{ p.user.display_name }}
```
→ kein `<a href>`-Tag.

### get_challenge_summary()-Datenstruktur

`app/services/weekly_summary.py` – Rückgabe:
```python
{
    "challenge": Challenge,
    "weeks": [date, ...],
    "participants": [
        {
            "user": User,           # user.id, user.display_name verfügbar
            "weekly_goal": int,
            "status": str,
            "weeks": { date: {"fulfilled_days": int, "is_sick": bool, "penalty": float, "overachieved": bool} },
            "total_penalty": float,
        }
    ]
}
```

### Bekannter Template-Bug (Dashboard)

`app/templates/dashboard/index.html` enthält `url_for('challenge_activities.log')` – dieser Endpoint-Name existiert nicht (korrekt: `challenge_activities.log_form`). Deshalb crasht das Dashboard-Template wenn eine Challenge mit Teilnehmern vorhanden ist. **Tests umgehen das durch direkten Service-Aufruf.**

### Test-Infrastruktur

- **conftest.py:** Minimal – nur `app` (session), `db` (function), `client` (function) Fixtures
- **Kein zentrales User/Challenge/Activity-Fixture** – jede Testdatei hat eigene `_create_and_login()`-Helper
- **Login-Pattern:** Echter POST auf `/auth/login` mit Session-Cookie (kein Mock)
- **CSRF:** In Tests deaktiviert (`WTF_CSRF_ENABLED = False`)

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Activity-Model & Felder | 4 | Vollständig gelesen, alle Felder bekannt |
| Screenshot-Speicherung & Serving | 4 | UUID-Pfad, Static-Serving, delete_upload() klar |
| Vorhandene Aktivitäts-Routen | 4 | Alle Routen bekannt, Berechtigungslogik gelesen |
| Dashboard-Route & Template | 3 | Datenfluss klar, Template-Bug identifiziert |
| get_challenge_summary() | 3 | Rückgabestruktur vollständig bekannt |
| Test-Infrastruktur | 3 | Fixtures + Patterns klar, Lücken dokumentiert |
| Berechtigungskonzept (wer darf was sehen) | 1 | Nur Delete-Schutz bekannt, keine View-Policy definiert |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Wer darf Activity-Detail sehen? (Nur Eigentümer? Alle Challenge-Teilnehmer? Admins?) | must-fill | Kapitän entscheidet (Policy-Frage) |
| Wer darf Aktivitäten anderer User sehen? (Alle Eingeloggten? Nur Challenge-Teilnehmer?) | must-fill | Kapitän entscheidet (Policy-Frage) |
| Screenshot-Zugriff für andere User – soll das erlaubt sein? | must-fill | Policy-Entscheidung |
| Dashboard-Template-Bug: wird er als Teil dieses Features gefixt oder separat? | must-fill | Sollte vor Feature 2 gefixt werden |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Screenshots werden via Flask Static ohne eigene Auth serviert | Yes | `url_for('static', ...)` in my_week.html:77 |
| Activity hat keine SQLAlchemy-Relationship zu User | Yes | activity.py vollständig gelesen |
| Dashboard zeigt immer die "aktive" Challenge (neueste mit Participations) | Partial | weekly_summary.py gelesen, genaue Logik nicht vollständig geprüft |
| CSRF-Token wird für alle POST-Routen benötigt | Yes | conftest.py:WTF_CSRF_ENABLED=False in Tests |

---

## Recommendations

### Feature 1: Aktivitäten-Detailansicht

**Neu zu bauen:**
1. Route `GET /challenge-activities/<int:activity_id>` in `app/routes/challenge_activities.py`
   - Berechtigungs-Check: Mindestens Eigentümer oder Challenge-Teilnehmer
   - Liefert Activity-Objekt + Challenge-Kontext ans Template
2. Template `app/templates/activities/detail.html`
   - Großes Screenshot-Bild (via `url_for('static', filename=activity.screenshot_path)`)
   - Metadaten: Sportart, Dauer, Datum, Quelle (manual/garmin/strava)
   - Zurück-Link zur `my_week`-Ansicht
3. In `app/templates/activities/my_week.html`: Aktivitäts-Einträge auf Detail-Route verlinken (z.B. Sport-Typ als Link)

**Wiederverwendbar:**
- Thumbnail-Pattern aus `my_week.html:77-84`
- Berechtigungslogik aus `delete_activity()` als Ausgangspunkt
- `url_for('static', filename=activity.screenshot_path)` für Bild-Serving

### Feature 2: Teilnehmer-Profil im Dashboard

**Neu zu bauen:**
1. Route `GET /challenge-activities/user/<int:user_id>` in `app/routes/challenge_activities.py` (oder neuer Blueprint)
   - Lädt User + Challenge-Participation + Aktivitäten dieses Users
   - Query: `Activity.user_id == user_id AND Activity.challenge_id == challenge_id`
   - Wochen-Statistiken via bestehenden `count_fulfilled_days()` / `calculate_total_penalty()`
2. Template `app/templates/activities/user_activities.html`
   - Display-Name, Wochenziel, Gesamtstrafe
   - Aktivitätsliste (mit Screenshot-Thumbnails falls vorhanden)
3. `app/templates/dashboard/index.html:45` – `{{ p.user.display_name }}` als Link rendern

**Template-Bug fix (Voraussetzung für Feature 2):**
- `dashboard/index.html`: `url_for('challenge_activities.log')` → `url_for('challenge_activities.log_form')` reparieren

**Wiederverwendbar:**
- `count_fulfilled_days()` und `calculate_total_penalty()` aus `app/services/penalty.py`
- Aktivitäts-Query-Pattern aus `my_week()` (`:133-141`)
- User-Objekte bereits in `get_challenge_summary()` vorhanden

### Neue Tests erforderlich
- `test_activity_detail_view` – eigene Activity anzeigen, Screenshot sichtbar
- `test_activity_detail_other_user` – Zugriffskontrolle für fremde Activity
- `test_dashboard_user_activities` – Aktivitäten anderer User anzeigen
- `test_screenshot_upload_and_delete` – Upload-Utility (fehlende Coverage)
