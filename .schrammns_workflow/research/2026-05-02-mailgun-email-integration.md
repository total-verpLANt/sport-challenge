# Research: Mailgun E-Mail-Integration in sport-challenge

**Date:** 2026-05-02
**Scope:** Mailgun REST API + bestehende Auth/User-Infrastruktur

## Executive Summary

- **Keine E-Mail-Infrastruktur vorhanden**: Weder Flask-Mail noch ein anderer Mail-Provider ist eingebunden. Nur `email-validator` für Adress-Validierung.
- **`is_approved`-Flow existiert bereits**: User-Model hat `is_approved`, `approved_at`, `approved_by_id` – Admin-Approval-UI ebenfalls. Ideal für Approval-Mail-Hook.
- **Kein Self-Service Passwort-Reset**: Nur Admin-seitiger Reset via `admin.py:110-121`. Kein Token-Mechanismus, kein "Passwort vergessen"-Link.
- **`itsdangerous` transitiv verfügbar** (via Flask) → stateless, signierte Reset-Tokens ohne DB-Migration möglich.
- **Mailgun EU-Region ist kritisch**: Bei EU-Domain MUSS `api.eu.mailgun.net` verwendet werden (häufige 401-Quelle).
- **Empfehlung**: `requests` direkt (kein SDK), Service-Klasse `app/services/mailer.py`, Config via Umgebungsvariablen.

## Key Files

| File | Purpose |
|------|---------|
| `app/routes/auth.py` | Login, Register, Logout – hier Register-Hook für Admin-Notification |
| `app/routes/admin.py:110-121` | Admin-Password-Reset + User-Approval-Route |
| `app/models/user.py` | User-Model mit `is_approved`, `approved_at`, `approved_by_id` |
| `app/extensions.py` | Extensions-Registrierung – kein Mail-Extension nötig (direkt requests) |
| `app/__init__.py:42-61` | App-Factory, Config-Loading – Mailgun-Config hier ergänzen |
| `app/services/penalty.py` | Referenz-Pattern für Service-Klassen |
| `requirements.txt` | Kein Mailgun/Flask-Mail – `requests` bereits transitiv vorhanden |

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| `requests` | transitiv via Flask | HTTP-Client für Mailgun REST API |
| `itsdangerous` | transitiv via Flask | Signierte, zeitlimitierte Reset-Tokens |
| `email-validator` | >=2.0 | Bereits vorhanden für Adress-Validierung |
| Mailgun REST API | v3 | E-Mail-Provider |

## Findings

### Mailgun REST API

**Endpunkt:** `POST https://api.mailgun.net/v3/{domain}/messages` (US) oder `https://api.eu.mailgun.net/v3/{domain}/messages` (EU-Region)

**Auth:** HTTP Basic Auth mit `api` als User und Private API Key als Passwort:
```python
auth=("api", "YOUR-PRIVATE-API-KEY")
```

**Pflichtparameter:** `from`, `to`, `subject`, mind. eines von `text`/`html`.

**Fehlercodes:**
- 200: OK, Mail in Queue
- 400: Pflichtfeld fehlt / Sandbox-Empfänger nicht autorisiert
- 401: Falscher Key oder falsche Region (EU vs. US)
- 429: Rate-Limit → Backoff nötig
- 500/502/503: Mailgun-seitig → Retry

**Sandbox-Restriktionen:** Max. 5 autorisierte Empfänger, ~5 Mails/Stunde, nur für Tests.

**Source:** [Mailgun API Reference](https://documentation.mailgun.com/docs/mailgun/api-reference/send/mailgun/messages/post-v3--domain-name--messages)

### Bestehender Auth-Flow

**Register** (`auth.py:67-111`):
- Erster User wird automatisch Admin + approved
- Alle weiteren landen mit `is_approved=False` und warten auf Freigabe
- Hier muss Admin-Notification-Mail eingefügt werden

**Login** (`auth.py:47-48`):
- Prüft `user.is_approved` – blockiert Login wenn False
- Fehlermeldung bereits: "Konto wartet auf Admin-Freigabe."

**Admin-Approval** (`admin.py`): Route vorhanden, kein Mail-Hook.

### Passwort-Reset-Plan

`itsdangerous.URLSafeTimedSerializer` (transitiv via Flask, kein neues Package):
```python
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
token = s.dumps(user.id, salt="password-reset")
user_id = s.loads(token, salt="password-reset", max_age=3600)  # 1h TTL
```

Kein DB-Feld nötig – Token ist stateless und signiert.

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Mailgun REST API | 3 | Endpunkt, Auth, Fehlercodes, Rate-Limits alle klar |
| Bestehender Auth-Flow | 4 | Vollständig gelesen: auth.py, admin.py, user.py |
| Passwort-Reset-Mechanik | 3 | itsdangerous-Pattern klar, keine DB-Migration nötig |
| Admin-Notification-Hook | 3 | Register-Route eindeutig, Einfüge-Punkt klar |
| User-Approval-Mail-Hook | 3 | Admin-Approval-Route klar, Hook-Punkt identifiziert |
| E-Mail-Templates | 1 | Noch keine Templates – müssen erstellt werden |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Welche Admin-Route approved User? Gibt es eine approve-Route in admin.py? | must-fill | admin.py vollständig lesen |
| Wie soll Mail bei Admin-Notification adressiert sein? Alle Admins? | nice-to-have | Mit Kapitän klären |
| EU- oder US-Mailgun-Region? | must-fill | Aus .env / Mailgun-Dashboard lesen |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| `requests` ist transitiv verfügbar | Yes | Flask depends on werkzeug/click, requests via garminconnect/stravalib |
| `itsdangerous` ist transitiv via Flask verfügbar | Yes | Flask core dependency |
| Admin-Approval sendet aktuell keine Mail | Yes | `admin.py:110-121` gelesen |
| Nur eine Admin-Route für Approval, nicht mehrere | Partially | admin.py grob gelesen |

## Recommendations

1. **`app/services/mailer.py`** – Service-Klasse mit `requests.Session`, lazy init via `get_mailer()`, `MailgunError` Exception
2. **Config-Variablen** in `.env`: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_SENDER`, `MAILGUN_BASE_URL` (EU: `https://api.eu.mailgun.net/v3`)
3. **Password Reset**: 3 neue Routes in `auth.py` + 2 Templates + `itsdangerous`-Token
4. **Admin-Notification**: Hook in `register`-Route, Query auf `User.query.filter_by(role="admin")`
5. **Approval-Mail**: Hook in Admin-Approval-Route
6. **Tests**: `pytest-mock` oder `responses`-Lib für Mailgun-Mocks
