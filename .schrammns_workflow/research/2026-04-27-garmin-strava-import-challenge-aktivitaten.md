# Research: Garmin/Strava-Import von Aktivitäten in das Challenge-System

**Date:** 2026-04-27
**Scope:** Import-Flow, Connector-Architektur, Activity-Model, Templates, Tests

---

## Executive Summary

- **Der Import-Flow ist vollständig implementiert** – `import_form` (GET) und `import_submit` (POST) in `app/routes/challenge_activities.py` existieren und funktionieren für Garmin und Strava.
- **Beide Provider werden unterstützt** – `GarminConnector` und `StravaConnector` sind in `PROVIDER_REGISTRY` registriert; Strava normalisiert sein Format via `_to_activity_dict()` auf dasselbe Dict wie Garmin.
- **Deduplizierung ist nur per Laufzeit-Query implementiert** – kein DB-UniqueConstraint auf `external_id`, was Race-Conditions (doppelter Submit) theoretisch erlaubt.
- **Der Submit-Endpoint holt Aktivitäten ein zweites Mal vom Provider** – kein serverseitiges Caching zwischen GET und POST; Zuordnung via Array-Index ist fragil bei gleichzeitigen Änderungen.
- **Kritische Testlücken:** Kein einziger Test für `import_form`/`import_submit`, `external_id`-Deduplizierung oder `source`-Feld bei importierten Aktivitäten.
- **Nächster Schritt:** Hauptsächlich Bugfixes/Härtung nötig (UniqueConstraint, Index-Fragility), kein großes New Feature – die UI und Logik sind fertig.

---

## Key Files

| File | Purpose |
|------|---------|
| `app/routes/challenge_activities.py` | Alle 6 Import/Log-Routen; gesamte Import-Logik (kein Service-Layer) |
| `app/connectors/garmin.py` | GarminConnector; delegiert an GarminClient; `@retry_on_rate_limit` |
| `app/connectors/strava.py` | StravaConnector; OAuth2; `_to_activity_dict()` normalisiert Strava-Format |
| `app/connectors/base.py` | BaseConnector ABC; Pflichtmethoden connect/get_activities/disconnect |
| `app/connectors/__init__.py` | PROVIDER_REGISTRY; `@register`-Decorator |
| `app/garmin/client.py` | GarminClient; ruft `garminconnect` API auf; `get_week_activities()` |
| `app/models/activity.py` | Activity-Model mit source, external_id (nullable, kein UniqueConstraint) |
| `app/templates/activities/import.html` | Checkbox-Tabelle mit "Bereits importiert"-Badge, Wochennavigation |
| `app/templates/activities/my_week.html` | Wochenuebersicht; enthält "Import"-Button |
| `tests/test_strava.py` | Connector-Tests (connect/refresh/get_activities); kein Import-Submit-Test |
| `tests/test_connectors.py` | Garmin Connector-Tests (connect/token-handling); kein Import-Submit-Test |
| `tests/test_activities_log.py` | Manuelles Logging Tests; kein Import-Test |

---

## Technology Stack

| Library/Framework | Version (if known) | Role |
|-------------------|--------------------|------|
| garminconnect | aktuell (lessons-learned) | Garmin API-Wrapper; `get_activities_by_date()` |
| stravalib | unbekannt | Strava API-Wrapper; `get_activities(after, before)` |
| Flask | 3.x | Routing, Blueprints |
| SQLAlchemy | 2.x | ORM; Activity-Model |
| Flask-Login | aktuell | `current_user` in Routes |
| Fernet (cryptography) | aktuell | Connector-Credentials verschlüsselt in DB |

---

## Findings

### 1. Import-Flow (vollständig dokumentiert)

**`import_form` (GET `/challenge-activities/import`)** – `app/routes/challenge_activities.py:175-262`:

1. `_active_participation()` → prüft akzeptierte ChallengeParticipation des Users
2. `ConnectorCredential.query.filter_by(user_id=...).all()` → `credentials[0]` (erstes verfügbares)
3. `PROVIDER_REGISTRY[provider_type]()` → Connector-Instanz
4. `connector.connect(cred.credentials)` → einloggen / Token aus DB laden
5. `connector.get_token_updates()` → Token-Refresh persistieren (Garmin: meist leer; Strava: neues access_token)
6. `connector.get_activities(monday, sunday)` → Liste roher Aktivitäts-Dicts
7. Bestehende `external_id`s aus DB laden → `already_imported`-Flag setzen
8. Render `activities/import.html` mit Checkbox-Tabelle

**`import_submit` (POST `/challenge-activities/import`)** – `app/routes/challenge_activities.py:265-356`:

1. Identischer Connector-Setup (connect + get_activities werden **erneut** aufgerufen)
2. `request.form.getlist("selected")` → Liste von String-Indizes
3. Pro Index: `ext_id = f"{provider_type}:{startTimeLocal}"` → DB-Query auf `external_id`
4. Falls nicht vorhanden: `Activity` erstellen mit `source=provider_type`, `external_id=ext_id`
5. `activity_date = date.fromisoformat(startTimeLocal[:10])`
6. `duration_minutes = max(1, int(duration_sec) // 60)`
7. `sport_type = activityType.typeKey` (Garmin-Format; Strava normalisiert via `_to_activity_dict()`)
8. Commit + Flash + Redirect zu `my_week`

### 2. Connector-Architektur

**PROVIDER_REGISTRY** – `app/connectors/__init__.py`:
```python
{"garmin": GarminConnector, "strava": StravaConnector}
```

**Rückgabeformat `get_activities()`** – normalisiertes Dict:
```python
{
    "startTimeLocal": "2026-04-21 08:30:00",
    "activityName": "Morgenrunde",
    "activityType": {"typeKey": "running"},
    "duration": 3600.0,  # Sekunden
    "distance": 10000.0  # Meter
}
```
Garmin gibt dieses Format nativ zurück; Strava wird via `_to_activity_dict()` (`app/connectors/strava.py:92-102`) normalisiert.

**external_id-Format:** `"garmin:2026-04-21 08:30:00"` oder `"strava:2026-04-21 08:30:00"`

### 3. Activity-Model

**`app/models/activity.py`** – alle Felder:

| Feld | Typ | Constraints |
|------|-----|-------------|
| `id` | int | PK |
| `user_id` | int | FK users.id, NOT NULL |
| `challenge_id` | int | FK challenges.id, NOT NULL |
| `activity_date` | date | NOT NULL |
| `duration_minutes` | int | NOT NULL |
| `sport_type` | str(100) | NOT NULL |
| `source` | str(20) | NOT NULL, default="manual" |
| `external_id` | str(255) | NULLABLE, **kein UniqueConstraint** |
| `screenshot_path` | str(500) | NULLABLE |
| `created_at` | datetime(tz) | NOT NULL, default=utcnow |

**⚠️ Kein UniqueConstraint auf `external_id`** – Deduplizierung nur per Laufzeit-Query möglich; Double-Submit oder Race-Condition kann Duplikate erzeugen.

### 4. Bekannte Schwächen

**Schwäche 1 – Doppelter API-Call in import_submit:**
GET und POST rufen beide `connect()` + `get_activities()` auf. Zuordnung erfolgt via Array-Index (`raw[idx]`). Falls sich die Aktivitätenliste zwischen GET und POST ändert (neue Aktivität sync'd), kann falscher Datensatz importiert werden.
*Lösung: Aktivitäten-Cache in Session oder Deduplizierung ausschließlich via `external_id` statt Index.*

**Schwäche 2 – Kein DB-UniqueConstraint auf `external_id`:**
Race-Condition bei Doppelklick oder parallelem Submit erzeugt doppelte Activity-Rows.
*Lösung: `UniqueConstraint("user_id", "external_id")` in Activity-Model + Migration.*

**Schwäche 3 – Nur `credentials[0]` genutzt:**
Falls ein User sowohl Garmin als auch Strava verbunden hat, wird immer nur der erste Connector genutzt. Kein Provider-Auswahl-UI.
*Lösung: Import-Formular mit Provider-Auswahl oder separater Import-URL pro Provider.*

**Schwäche 4 – Keine Sport-Typ-Filterung:**
Alle Aktivitäten werden angezeigt, unabhängig davon ob sie für die Challenge relevant sind (z.B. Garmin-Schlafdaten könnten theoretisch auftauchen).
*Hinweis: Garmin `get_activities_by_date()` gibt nur echte Sportaktivitäten zurück; Schlafdaten sind separater Endpoint – kein akutes Problem.*

### 5. Test-Abdeckung

| Bereich | Abgedeckt | Lücke |
|---------|-----------|-------|
| GarminConnector connect/reconnect | ✅ test_connectors.py | – |
| StravaConnector connect/refresh/disconnect | ✅ test_strava.py | – |
| Manuelles Aktivitäten-Logging | ✅ test_activities_log.py | – |
| import_form GET | ❌ | Kein Test |
| import_submit POST | ❌ | Kein Test |
| external_id Deduplizierung | ❌ | Kein Test |
| source="garmin"/"strava" | ❌ | Kein Test |

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| import_form/import_submit Logik | 4 | Vollständig gelesen, Schwächen dokumentiert |
| Connector-Architektur (Garmin+Strava) | 4 | Beide Connectoren vollständig analysiert |
| Activity-Model | 4 | Alle Felder, Constraints bekannt |
| Template (import.html) | 3 | Struktur bekannt, JS-"Select All" vorhanden |
| Test-Abdeckung Import | 4 | Lücken vollständig kartiert |
| Sport-Typ-Filterlogik | 2 | Keine explizite Filterung im Code; Garmin-API liefert nur Sportaktivitäten |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Strava `_to_activity_dict()` mappt `activityType` auf welche typeKey-Werte? | nice-to-have | `app/connectors/strava.py:92-102` lesen |
| Was passiert wenn Garmin-Token abgelaufen ist während import_submit? | must-fill | Error-Handling in Route prüfen |
| Verhalten bei 0 Aktivitäten in der Woche (leere Liste von get_activities) | nice-to-have | Manuell testen |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| `credentials[0]` ist immer Garmin oder Strava (nie ein unbekannter Provider) | Yes | PROVIDER_REGISTRY enthält nur garmin+strava |
| Garmin `get_activities_by_date` liefert keine Schlafdaten | Yes | Garmin API: separater Endpoint für Sleep |
| Strava normalisiert auf identisches Dict-Format wie Garmin | Yes | `app/connectors/strava.py:92-102` via Agent B bestätigt |
| `startTimeLocal` ist immer im Format `"YYYY-MM-DD HH:MM:SS"` | Unverified | Nur aus external_id-Konstruktion geschlossen |

---

## Recommendations

### Sofort (vor Feature-Release):
1. **UniqueConstraint auf `external_id` + `user_id`** in Activity-Model hinzufügen + Migration – verhindert Duplikate bei Double-Submit.
2. **Index-basierte Zuordnung in import_submit durch external_id-basierte ersetzen** – Formular sendet `external_id` statt Array-Index; POST sucht Aktivität via external_id in der frisch geholten Liste.

### Kurzfristig:
3. **Provider-Auswahl-UI** wenn mehrere Connectoren verbunden – aktuell immer `credentials[0]`.
4. **Tests für import_submit** mit gemocktem Connector (mindestens: Normalfall, Duplikat-Skip, kein Credential).

### Optional:
5. **Session-Caching der Aktivitätenliste** zwischen GET und POST (z.B. in Flask-Session als JSON) – eliminiert doppelten API-Call und Index-Fragility auf einmal.
