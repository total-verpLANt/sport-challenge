# Research: Social-Media-Timeline im Dashboard

**Date:** 2026-04-29  
**Scope:** Dashboard, Activity-Model, ActivityMedia, Leaderboard-Logik, Navbar, Paginierung, Like/Heart-Mechanismus

---

## Executive Summary

- Das Dashboard ist ein reines Leaderboard (tabellarisch, wochenbasiert) – kein Activity-Feed existiert
- Das `Activity`-Model hat bereits ein `notes`-Textfeld (nullable, max 2000 Zeichen) und eine 1:n-Beziehung zu `ActivityMedia` – beides kann sofort als "Post"-Inhalt genutzt werden
- Die App ist eine klassische MPA ohne AJAX; ein "Mehr laden"-Button erfordert einen neuen JSON-Endpunkt oder eine Server-Side-Rendered Partial-Route
- Kein Like-/Heart-System vorhanden – ein neues `ActivityLike`-Model + Route muss von Grund auf gebaut werden
- Leaderboard auf Top-5 begrenzen + vollständiges Leaderboard als eigene Seite: minimalinvasiver Eingriff ins Dashboard-Template und die Navbar

---

## Key Files

| File | Purpose |
|------|---------|
| [app/models/activity.py](app/models/activity.py) | Activity + ActivityMedia Models |
| [app/routes/dashboard.py](app/routes/dashboard.py) | Dashboard-Route (einzige Route, GET /) |
| [app/templates/dashboard/index.html](app/templates/dashboard/index.html) | Leaderboard-Template |
| [app/templates/base.html](app/templates/base.html) | Navbar + Layout |
| [app/services/weekly_summary.py](app/services/weekly_summary.py) | Leaderboard-Logik (`get_challenge_summary`) |
| [app/routes/challenge_activities.py](app/routes/challenge_activities.py) | Bestehende Activity-Routen (Pattern für neue Routen) |
| [app/extensions.py](app/extensions.py) | db, migrate, login_manager, csrf, limiter |

---

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| Flask | ~3.x | Web-Framework |
| Flask-SQLAlchemy | ~3.x | ORM, SQLAlchemy 2.0 Style |
| SQLite (Dev) / PostgreSQL-ready | - | Datenbank |
| Bootstrap | 5.3.3 CDN | CSS-Framework |
| GLightbox | 3.3.1 CDN | Medien-Lightbox |
| Flask-WTF (CSRF) | - | CSRF-Schutz auf allen POSTs |
| Flask-Login | - | Session-Auth |

---

## Findings

### 1. Activity-Model (`app/models/activity.py:9-37`)

Alle relevanten Felder für einen "Post" im Feed:

```
activity.id               → Eindeutige ID
activity.user_id          → FK → users.id
activity.activity_date    → date (für "am <Tag>")
activity.created_at       → datetime TZ-aware (für "um <Uhrzeit>")
activity.sport_type       → String(100) (für "hat X gemacht")
activity.duration_minutes → int (für "<Dauer> Minuten")
activity.notes            → Text nullable (Kommentarfeld = Post-Text)
activity.media            → list[ActivityMedia] (Multimedia, eager ladbar)
```

`created_at` (Zeile 23-27) ist TZ-aware und eignet sich für eine chronologische Timeline. Kein separates `updated_at`.

### 2. ActivityMedia-Model (`app/models/activity.py:40-54`)

```
media.file_path           → String(500), relativer Pfad
media.media_type          → "image" | "video"
media.original_filename   → String(255)
```

Im Template kann `url_for('static', filename=media.file_path)` oder der Upload-Folder-Pfad genutzt werden – gleich prüfen wie `detail.html` Medien rendert.

### 3. Dashboard-Route (`app/routes/dashboard.py:13-38`)

Aktuell nur eine Route: `GET /` mit `get_challenge_summary(challenge)`. Die Route liefert alle Teilnehmer an das Template – für Top-5 reicht ein Template-Filter oder Slicing im Template.

Für den Activity-Feed braucht das Dashboard zwei neue Dinge:
- Initiale Activity-Abfrage (limit=10, order_by created_at DESC) für den ersten Render
- Eine separate AJAX-Route `GET /feed?offset=<n>&challenge_id=<id>` für "Mehr laden"

### 4. Leaderboard auf Top-5 begrenzen

Das Template (Zeile 40: `{% for p in participants %}`) kann einfach auf `{% for p in participants[:5] %}` begrenzt werden. Vollständiges Leaderboard → neue Route `/leaderboard` oder neues Template mit allen Teilnehmern.

### 5. Navbar – neuer "Leaderboard"-Link (`app/templates/base.html:30-44`)

Der `me-auto`-Block enthält 4 `<li class="nav-item">` Einträge. Ein fünfter Eintrag "Leaderboard" wird direkt nach "Dashboard" eingefügt.

### 6. Keine AJAX-Endpunkte

Die gesamte App ist server-side rendered (kein `jsonify`, kein fetch). Für "Mehr laden" gibt es zwei Optionen:
- **Option A (einfacher):** Klassisches Full-Page-Load mit `?offset=10` Parameter auf einer dedizierten Feed-Seite
- **Option B (UX besser):** AJAX-Endpunkt `GET /dashboard/feed` gibt JSON zurück, JS appended neue Posts – erfordert einen neuen JSON-Blueprint und Inline-JS

Empfehlung: Option B für ein echtes "social media"-Feeling. Die bestehende Architektur kann einen JSON-Endpunkt problemlos aufnehmen.

### 7. Kein Like-System vorhanden

Kein `ActivityLike`-Model, keine entsprechende Route. Vollständig neu zu bauen:
- Neues Model `ActivityLike(user_id FK, activity_id FK, UniqueConstraint)`
- Route `POST /activities/<id>/like` (toggle-Semantik: Like hinzufügen oder entfernen)
- CSRF-Schutz für den POST
- Frontend: Herz-Button mit fetch() + optimistic UI oder klassischer Form-Submit

### 8. Kommentarfunktion als Rumpf

Das Kapitel verlangt einen Code-Rumpf (nicht im UI sichtbar):
- Model: `ActivityComment(id, activity_id FK, user_id FK, body Text, created_at)` – in `app/models/activity.py` definieren
- Route: `POST /activities/<id>/comment` – in `app/routes/challenge_activities.py` als Stub (flash "nicht implementiert")
- Template: kein UI, Stub nur im Code

### 9. Motivierende Sprüche

100 Sprüche können als Python-Liste in einem neuen Utility-Modul `app/utils/motivational_quotes.py` abgelegt werden. Template-Rendering via `random.choice(quotes)` in der Route oder via Jinja2-Global.

Sicherer Ansatz: Sprüche in der Route generieren (nicht im Template, da `random` kein Jinja2-Built-in ist).

### 10. Paginierungsmuster

Bestehend: Wochenbasierter Offset (`?offset=N`). Für den Feed: cursor-basierter Offset via `?before_id=<last_activity_id>` oder simpler `?page=<n>` mit `limit=10`.

Einfachste Option für das MVP: `?page=N`, Query mit `.offset(page*10).limit(10)`.

---

## Implementierungsplan (Zusammenfassung)

1. **Migration:** Neues `ActivityLike`-Model (user_id, activity_id, UniqueConstraint, created_at) + `ActivityComment`-Rumpf-Model
2. **Route dashboard.py:** Activity-Feed-Query (10 Activities, nach `created_at DESC`, gefiltert auf aktive Challenge-Teilnehmer)
3. **Route dashboard/feed (AJAX):** `GET /feed?page=N&challenge_id=ID` → JSON mit Activity-Daten
4. **Route `/activities/<id>/like`:** POST, Toggle-Semantik, JSON-Antwort `{liked: bool, count: int}`
5. **Template dashboard/index.html:** Leaderboard auf `[:5]` begrenzen, Spendentopf bleibt, 3 Buttons bleiben, Feed-Section darunter
6. **Template leaderboard/index.html** (neu): Vollständige Teilnehmer-Tabelle
7. **Navbar base.html:** "Leaderboard"-Link einfügen
8. **app/utils/motivational_quotes.py:** 100 Sprüche als Liste, `get_random_quote()` Funktion
9. **Tests:** Route-Tests für Like-Toggle, Feed-Paginierung, Berechtigungsgrenzen

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Activity-Model + Felder | 4 | Vollständig gelesen, alle Felder bekannt |
| Dashboard-Route + Template | 4 | Vollständig gelesen |
| Navbar-Struktur | 4 | Vollständig gelesen |
| AJAX / Fetch-Patterns | 3 | Keine AJAX-Patterns vorhanden – Neubau nötig |
| Paginierungs-Muster | 3 | Wochenoffset bekannt, Feed-Paginierung neu |
| ActivityMedia-Rendering | 2 | Pattern aus detail.html bekannt, aber nicht vollständig gelesen |
| Like-System | 1 | Nicht vorhanden, Neubau |
| Kommentar-Rumpf | 1 | Nicht vorhanden, Neubau |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Wie rendert `detail.html` Media (Pfad zu Uploads)? | must-fill | `app/templates/activities/detail.html` lesen |
| Upload-Folder-Konfiguration (BASE_DIR, UPLOAD_FOLDER) | must-fill | `app/utils/uploads.py` + `app/__init__.py` lesen |
| Wird `created_at` in Templates via `strftime` formatiert? | nice-to-have | Im Detail-Template prüfen |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| `notes` max. 2000 Zeichen nur per Formvalidierung, DB hat kein Hard-Limit | Yes | `activity.py:22` – Text ohne max_length; CHANGELOG v0.7.7 |
| Activity-Feed soll auf aktive Challenge-Teilnehmer der aktuellen Challenge begrenzt sein | No | Aus Kontext erschlossen – Berechtigungsmodell muss geklärt werden |
| "Herz" ist Toggle (zweites Klicken = Unlike) | No | Aus Benutzeranfrage erschlossen |
| Motivierende Sprüche werden serverseitig (in der Route) per `random.choice` ausgewählt | No | Pragmatische Annahme für CSP-Kompatibilität |

---

## Recommendations

1. **Sofort implementierbar** (kein neues Model): Leaderboard auf Top-5, Navbar-Link "Leaderboard", vollständige Leaderboard-Seite
2. **Migration nötig** (neues Model): ActivityLike + ActivityComment-Rumpf → Alembic-Migration erstellen
3. **AJAX-Route** für "Mehr laden": Ein neuer `GET /dashboard/feed` Endpunkt mit `jsonify`
4. **Sicherheit:** Like-Route muss CSRF-Schutz erhalten, auch wenn es ein AJAX-POST ist (CSRF-Token im Header oder Body)
5. **Scope:** Feed nur für Challenge-Teilnehmer der aktiven Challenge sichtbar (wie user_activities.html) – keine Cross-Challenge-Sichtbarkeit
