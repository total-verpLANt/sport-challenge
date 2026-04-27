# Research: Nickname-Feature – Benutzeranzeige

**Date:** 2026-04-27
**Scope:** User-Modell, Templates, Routes, Auth-Flow – alle Stellen wo Email angezeigt wird

## Executive Summary

- Benutzer werden **ausschließlich über ihre E-Mail-Adresse** identifiziert und angezeigt – kein `display_name`, `username` oder `nickname` Feld im User-Modell.
- **13 Stellen** im Code zeigen `.email` an (7 Templates, 5 Flash-Messages, 1 Python-Dict).
- Es gibt **weder eine Settings-Route** noch einen First-Login/Onboarding-Flow.
- Kernänderungen: neues DB-Feld `nickname`, Migration, `display_name`-Property am User-Modell, neue Settings-Route, Nickname-Eingabe nach erstem Login, alle Template-Stellen umstellen.
- Security-Risiken: Nickname-Eindeutigkeit nicht zwingend erforderlich, aber XSS-Schutz durch Jinja2-Autoescaping bereits vorhanden; CSRF-Schutz muss für Settings-Form ergänzt werden.

## Key Files

| File | Purpose |
|------|---------|
| `app/models/user.py` | User-Modell – hier wird `nickname` + `display_name`-Property hinzugefügt |
| `app/templates/base.html:44` | Navbar-Dropdown: `⚙ {{ current_user.email }}` → umstellen |
| `app/templates/dashboard/index.html:45` | Leaderboard: `{{ p.user.email }}` → umstellen |
| `app/templates/challenges/detail.html:112,142` | Einladungs-Dropdown + Teilnehmer-Tabelle |
| `app/templates/admin/users.html:25,48` | Admin-Benutzerliste + Bestätigungsdialog |
| `app/templates/bonus/index.html:52` | Bonus-Ranking |
| `app/routes/bonus.py:69` | Ranking-Dict baut `"email"` Key → auf `display_name` umstellen |
| `app/routes/challenges.py:187,198` | Flash-Messages mit `user.email` |
| `app/routes/admin.py:40,55,58` | Flash-Messages mit `user.email` |
| `app/routes/auth.py` | Login-Flow – hier First-Login-Redirect ergänzen |

## Technology Stack

| Library/Framework | Version (if known) | Role |
|-------------------|--------------------|------|
| Flask-Login | - | `current_user` Proxy, Login-Flow |
| SQLAlchemy | - | ORM, User-Modell |
| Flask-Migrate / Alembic | - | DB-Migration für neues `nickname` Feld |
| Flask-WTF / CSRF | - | CSRF-Schutz für Settings-Form |
| Jinja2 | - | Template-Rendering (Autoescaping aktiv) |

## Findings

### User-Modell (`app/models/user.py`)

Aktuelle Felder:
- `id`, `email` (unique, not null), `password_hash`, `role`
- `created_at`, `is_approved`, `approved_at`, `approved_by_id`
- `failed_login_attempts`, `locked_until`

Fehlend: `nickname` (String, nullable, max. z.B. 50 Zeichen)

Empfehlung: `display_name`-Property hinzufügen, die `nickname or email.split("@")[0]` zurückgibt – so ist überall eine sichere Fallback-Anzeige garantiert.

### Template-Stellen mit Email-Anzeige (7)

| Datei | Zeile | Code |
|-------|-------|------|
| `base.html` | 44 | `⚙ {{ current_user.email }}` |
| `dashboard/index.html` | 45 | `{{ p.user.email }}` |
| `challenges/detail.html` | 112 | `{{ user.email }}` (Einladungs-Dropdown) |
| `challenges/detail.html` | 142 | `{{ p.user.email }}` (Teilnehmer-Tabelle) |
| `admin/users.html` | 25 | `{{ user.email }}` |
| `admin/users.html` | 48 | `data-confirm="{{ user.email }} wirklich ablehnen..."` |
| `bonus/index.html` | 52 | `{{ rank_entry.email }}` |

### Python-Code-Stellen (5 + 1 Dict)

| Datei | Zeile | Code |
|-------|-------|------|
| `challenges.py` | 187 | `f"{user.email} ist bereits in dieser Challenge."` |
| `challenges.py` | 198 | `f"{user.email} wurde zur Challenge eingeladen."` |
| `admin.py` | 40 | `f"Benutzer {user.email} wurde freigeschaltet."` |
| `admin.py` | 55,58 | `f"Benutzer {email} wurde abgelehnt und gelöscht."` |
| `bonus.py` | 69 | `"email": user.email if user else "Unbekannt"` → Key-Name + Wert |

### Auth-Flow (`app/routes/auth.py`)

- **Erster User:** Auto-Admin + approved → direkter Login → redirect zu `activities.week_view`
- **Weitere User:** warten auf Admin-Freigabe
- **Nach Login:** immer redirect zu `activities.week_view` – kein Onboarding

Für First-Login-Flow: nach `login_user()` prüfen ob `user.nickname is None` → redirect zu `/settings` statt `activities.week_view`.

### Navbar (`base.html:40-60`)

Dropdown-Menü zeigt:
- Button-Text: `⚙ {{ current_user.email }}`
- Links: Challenges, Connectors, (Admin)
- **Kein Settings-Link** – muss ergänzt werden

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| User-Modell Felder | 4 | Vollständig gelesen, alle Felder bekannt |
| Template-Stellen | 4 | Alle 7 Stellen mit Zeile identifiziert |
| Flash-Messages Python | 4 | Alle 5 Stellen identifiziert |
| Auth-Flow | 3 | Login + Register vollständig, Redirect-Logik klar |
| Settings-Route | 4 | Existiert nicht – muss neu erstellt werden |
| First-Login-Onboarding | 4 | Existiert nicht – muss neu implementiert werden |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Soll `nickname` eindeutig (unique) sein? | must-fill | Kapitän entscheiden lassen |
| Validierungsregeln für Nickname (Länge, Zeichen) | must-fill | Kapitän entscheiden lassen |
| Soll die Email in Admin-Ansichten trotzdem sichtbar bleiben? | nice-to-have | Ja, empfohlen für Admin |
| Bonus.py `ranked`-Dict: Key-Name ändern oder Wert? | must-fill | Beides: Key → `display_name`, Wert → `user.display_name` |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Jinja2-Autoescaping schützt gegen XSS bei Nickname-Anzeige | Yes | Standard Flask/Jinja2 |
| CSRF ist global via Flask-WTF aktiv | Yes | `app/extensions.py` hat csrf-Instanz |
| `bonus/index.html:52` zeigt `rank_entry.email`, nicht `user.email` | Yes | `bonus.py:69` baut Dict mit `"email"` Key |
| Admin-Ansicht kann weiterhin Email anzeigen (Security-Grund) | No | Designentscheidung |

## Recommendations

**Implementierungsplan:**

1. **DB-Migration:** `nickname` Feld (String 50, nullable) zum User-Modell + Alembic-Migration
2. **display_name-Property:** `return self.nickname or self.email.split("@")[0]` am User-Modell
3. **Settings-Route:** `/settings` GET+POST, Formular mit Nickname-Feld, CSRF-geschützt
4. **Settings-Link in Navbar:** Link im Dropdown zu `/settings` ergänzen
5. **First-Login-Redirect:** In `auth.py` nach `login_user()`: wenn `user.nickname is None` → redirect zu `url_for('settings.profile')` mit Flash-Hinweis
6. **Templates umstellen (7 Stellen):** `.email` → `.display_name` (außer admin/users.html: dort ggf. beide anzeigen)
7. **Python-Code umstellen (5+1 Stellen):** Flash-Messages + bonus.py-Dict

**Reihenfolge:** 1 → 2 → 3 → 4 → 5 → 6 → 7 (jeder Schritt atomar committen)
