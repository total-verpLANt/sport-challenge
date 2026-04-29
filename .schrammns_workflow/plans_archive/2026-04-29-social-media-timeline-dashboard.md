# Plan: Social-Media-Timeline im Dashboard

**Date:** 2026-04-29  
**Goal:** Social-Media-Timeline unter dem Dashboard-Leaderboard: Top-5-Leaderboard, vollständiges Leaderboard als eigene Seite, Spendentopf + 3 Buttons, chronologischer Activity-Feed mit Likes und Kommentar-Rumpf  
**Research:** `.schrammns_workflow/research/2026-04-29-social-media-timeline-dashboard.md`

---

## Baseline Audit

| Metric | Value | Command |
|--------|-------|---------|
| Tests gesamt | 120 | `pytest --collect-only -q` |
| Dateien to modify | 6 | `ls app/routes/dashboard.py app/templates/...` |
| LOC gesamt (betroffene Dateien) | 883 | `wc -l` |
| Bestehende Like-/Feed-Routen | 0 | `grep -r like app/ -l` |
| Bestehende jsonify-Aufrufe | 0 | `grep -r jsonify app/ -l` |
| Bestehende Migrationen | 7 | `ls migrations/versions/*.py` |

---

## Files to Modify

| File | Change | Größe |
|------|--------|-------|
| `app/models/activity.py` | **NEU:** `ActivityLike`-Model + `ActivityComment`-Rumpf-Model | +30 LOC |
| `app/routes/dashboard.py` | Feed-Query (initiale 10 Activities) + neue `/feed`-JSON-Route | +60 LOC |
| `app/templates/dashboard/index.html` | Top-5-Slice, Feed-Section, Like-Button, Motivationssprüche | +120 LOC |
| `app/templates/base.html` | Navbar: "Leaderboard"-Link hinzufügen | +4 LOC |
| `app/__init__.py` | kein Änderungsbedarf (Blueprint-Registrierung für dashboard_bp besteht) | 0 |
| `app/utils/motivational_quotes.py` | **NEU:** 100 Sprüche + `get_random_quote()` | +110 LOC |
| `app/templates/dashboard/leaderboard.html` | **NEU:** Vollständiges Leaderboard-Template | +80 LOC |
| `migrations/versions/<hash>_add_activity_likes_and_comments.py` | **NEU:** Alembic-Migration | +50 LOC |
| `tests/test_dashboard.py` | Tests: Feed-Endpoint, Like-Toggle, Leaderboard-Seite | +80 LOC |

---

## Implementation Detail

### Issue I-01: ActivityLike + ActivityComment-Rumpf-Model + Migration

**Datei:** `app/models/activity.py`

Neue Klassen nach `ActivityMedia` einfügen:

```python
class ActivityLike(db.Model):
    __tablename__ = "activity_likes"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    activity: Mapped["Activity"] = relationship(back_populates="likes")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("activity_id", "user_id", name="uq_activity_like_user"),
    )


# Kommentar-Rumpf – NICHT in der UI sichtbar, nur Code-Struktur
class ActivityComment(db.Model):
    __tablename__ = "activity_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    activity: Mapped["Activity"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship()
```

**Relationship auf Activity ergänzen** (`app/models/activity.py:28-33`):
```python
likes: Mapped[list["ActivityLike"]] = relationship(
    "ActivityLike", back_populates="activity", cascade="all, delete-orphan"
)
comments: Mapped[list["ActivityComment"]] = relationship(
    "ActivityComment", back_populates="activity", cascade="all, delete-orphan"
)
```

**Migration:**
```bash
FLASK_APP=run.py .venv/bin/flask db migrate -m "add activity likes and comments"
```

Dann Migration prüfen – KEIN Uuid-Diff für `challenges.public_id` (bekanntes Problem, ggf. manuell entfernen, siehe Lessons Learned).

**Risiko:** `irreversible / external / requires-human` (DB-Migration)

---

### Issue I-02: Motivational Quotes Utility

**Neue Datei:** `app/utils/motivational_quotes.py`

```python
import random

QUOTES: list[str] = [
    "Jeder Schritt zählt – auch der erste!",
    "Du wirst es morgen nicht bereuen.",
    "Stark sein heißt weitermachen, wenn es schwer wird.",
    # ... 97 weitere Sprüche ...
]

def get_random_quote() -> str:
    return random.choice(QUOTES)
```

100 Sprüche auf Deutsch, motivierend, sport-bezogen. Funktion wird in der Dashboard-Route aufgerufen und als Teil der Feed-Daten an das Template übergeben.

**Risiko:** `reversible / local / autonomous-ok`

---

### Issue I-03: Dashboard-Route – Top-5 + Feed-Query + Leaderboard-Seite

**Datei:** `app/routes/dashboard.py`

**Neue Imports:**
```python
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from app.models.activity import Activity, ActivityLike
from app.models.challenge import Challenge, ChallengeParticipation
from app.utils.motivational_quotes import get_random_quote
```

**Modifizierte `index()`-Route** – bestehende Route erhält Feed-Query:
```python
# Activity-Feed: 10 neuste Activities aller Challenge-Teilnehmer laden
participant_ids = db.session.scalars(
    db.select(ChallengeParticipation.user_id).where(
        ChallengeParticipation.challenge_id == challenge.id,
        ChallengeParticipation.status.in_(["accepted", "bailed_out"]),
    )
).all()

feed_activities = db.session.scalars(
    db.select(Activity)
    .where(
        Activity.challenge_id == challenge.id,
        Activity.user_id.in_(participant_ids),
    )
    .order_by(Activity.created_at.desc())
    .limit(10)
    .options(selectinload(Activity.media), selectinload(Activity.likes))
).all()

# Sprüche pro Activity generieren
feed_quotes = {a.id: get_random_quote() for a in feed_activities}
```

**Neue Route `leaderboard()`:**
```python
@dashboard_bp.route("/leaderboard")
@login_required
def leaderboard():
    # Gleiche Challenge-Logik wie index()
    # Gibt summary mit ALLEN Teilnehmern zurück
    return render_template("dashboard/leaderboard.html", summary=summary, timedelta=timedelta)
```

**Neue AJAX-Route `feed()`:**
```python
@dashboard_bp.route("/feed")
@login_required
def feed():
    """JSON-Endpunkt für paginiertes Nachladen des Activity-Feeds."""
    challenge_id = request.args.get("challenge_id", type=int)
    page = request.args.get("page", 0, type=int)
    # ... Query mit offset(page*10).limit(10) ...
    # Gibt JSON zurück: list of activity-dicts
    return jsonify({"activities": [...], "has_more": bool})
```

**Neue Route `like_activity(activity_id)`:**
```python
@dashboard_bp.route("/activities/<int:activity_id>/like", methods=["POST"])
@login_required
def like_activity(activity_id: int):
    """AJAX-Like-Toggle: Like hinzufügen oder entfernen."""
    # Prüfe: Activity in derselben Challenge wie current_user
    # Toggle: existiert → DELETE, existiert nicht → INSERT
    # Gibt JSON zurück: {liked: bool, count: int}
    return jsonify({"liked": liked, "count": count})
```

**Blueprint-URL-Präfix:** `dashboard_bp` ist unter `/dashboard` registriert (`app/__init__.py:64`). Neue Routen sind automatisch unter `/dashboard/leaderboard`, `/dashboard/feed`, `/dashboard/activities/<id>/like` erreichbar.

**Risiko:** `reversible / system / requires-approval`

---

### Issue I-04: Dashboard-Template – Top-5, Buttons, Feed-Section

**Datei:** `app/templates/dashboard/index.html`

**Änderungen:**

1. **Leaderboard-Tabelle auf Top-5 begrenzen** (Zeile 40):
   ```jinja2
   {% for p in participants[:5] %}
   ```
   + Link unter der Tabelle:
   ```html
   <a href="{{ url_for('dashboard.leaderboard') }}" class="btn btn-outline-secondary btn-sm mt-2">
     Vollständiges Leaderboard anzeigen →
   </a>
   ```

2. **Spendentopf** (Zeile 79-90): bleibt unverändert

3. **3 Action-Buttons** (Zeile 92-102): bleiben unverändert

4. **Feed-Section** nach den Buttons:
   ```html
   <hr class="my-4">
   <h4>Aktivitäten-Feed</h4>
   <div id="activity-feed">
     {% for activity in feed_activities %}
     <div class="card mb-3" id="feed-post-{{ activity.id }}">
       <div class="card-body">
         <!-- Post-Text: "User X hat um HH:MM Uhr am TT.MM. SPORT gemacht." -->
         <p class="card-text">
           <strong>{{ activity.user_display_name }}</strong> hat um
           {{ activity.created_at.strftime('%H:%M') }} Uhr am
           {{ activity.activity_date.strftime('%d.%m.%Y') }}
           <em>{{ activity.sport_type }}</em> gemacht.
           Die Einheit hat <strong>{{ activity.duration_minutes }} Minuten</strong> gedauert.
         </p>
         <!-- Motivierender Spruch -->
         <p class="text-muted fst-italic small">💪 {{ feed_quotes[activity.id] }}</p>
         <!-- Multimedia (wenn vorhanden) -->
         {% if activity.media %}
           <!-- Thumbnail-Grid analog zu detail.html -->
         {% endif %}
         <!-- Notes/Trainingsnotiz (wenn vorhanden) -->
         {% if activity.notes %}
           <p class="card-text text-secondary mt-2">{{ activity.notes }}</p>
         {% endif %}
         <!-- Like-Button -->
         <button class="btn btn-outline-danger btn-sm like-btn"
                 data-activity-id="{{ activity.id }}"
                 data-liked="{{ 'true' if current_user.id in liked_ids[activity.id] else 'false' }}">
           ❤️ <span class="like-count">{{ activity.likes|length }}</span>
         </button>
       </div>
     </div>
     {% endfor %}
   </div>
   <!-- "Mehr laden"-Button -->
   <div id="load-more-container" class="text-center mt-3">
     <button id="load-more-btn" class="btn btn-outline-primary"
             data-challenge-id="{{ challenge.id }}" data-page="1">
       Mehr laden
     </button>
   </div>
   ```

5. **Inline-JavaScript** (mit CSP-Nonce):
   - `fetch('/dashboard/feed?challenge_id=X&page=N')` → append neue Posts
   - `fetch('/dashboard/activities/<id>/like', {method:'POST', headers: csrf})` → Like-Toggle
   - Bei 0 Ergebnissen "Mehr laden"-Button ausblenden

**Risiko:** `reversible / local / autonomous-ok`

---

### Issue I-05: Leaderboard-Template (neu) + Navbar-Link

**Neue Datei:** `app/templates/dashboard/leaderboard.html`

Kopiert die vollständige Tabelle aus `dashboard/index.html`, aber mit `{% for p in participants %}` (ohne `[:5]`-Slice). Eigene Seite mit Heading "Vollständiges Leaderboard".

**Modifizierte Datei:** `app/templates/base.html`

Navbar-Ergänzung (nach "Dashboard"-Link, Zeile 32):
```html
<li class="nav-item">
  <a class="nav-link" href="{{ url_for('dashboard.leaderboard') }}">Leaderboard</a>
</li>
```

**Risiko:** `reversible / local / autonomous-ok`

---

### Issue I-06: Tests

**Datei:** `tests/test_dashboard.py`

Neue Test-Funktionen:
- `test_leaderboard_full_shows_all_participants` – Leaderboard-Seite zeigt alle Teilnehmer (nicht nur Top-5)
- `test_feed_returns_json` – `/dashboard/feed?challenge_id=X&page=0` gibt JSON zurück
- `test_feed_pagination` – page=0 gibt erste 10, page=1 gibt nächste 10 (falls vorhanden)
- `test_feed_only_challenge_participants` – Feed enthält keine Activities fremder Challenges
- `test_like_toggle_adds_like` – POST auf `/dashboard/activities/<id>/like` erstellt ActivityLike
- `test_like_toggle_removes_like` – zweiter POST entfernt Like (Toggle)
- `test_like_requires_challenge_participation` – User außerhalb der Challenge kann nicht liken
- `test_dashboard_top5_only` – Dashboard zeigt höchstens 5 Teilnehmer in der Leaderboard-Tabelle

**Risiko:** `reversible / local / autonomous-ok`

---

## Wave Structure

```
Wave 1 (parallel):
  I-01  ActivityLike + ActivityComment-Modelle + Migration
  I-02  Motivational Quotes Utility

Wave 2 (nach I-01 + I-02):
  I-03  Dashboard-Route (Feed, Like-Route, Leaderboard-Route)

Wave 3 (nach I-03):
  I-04  Dashboard-Template (Feed-Section, Top-5, Like-Button JS)
  I-05  Leaderboard-Template + Navbar-Link

Wave 4 (nach I-03, I-04, I-05):
  I-06  Tests
```

**Dependency-Validierung:**
- I-01 → I-03: Route importiert `ActivityLike` Model ✓ (echter Code-Dep)
- I-02 → I-03: Route importiert `get_random_quote()` ✓ (echter Code-Dep)
- I-03 → I-04: Template nutzt neue Route-Variablen (`feed_activities`, `feed_quotes`, `liked_ids`) ✓
- I-03 → I-05: `url_for('dashboard.leaderboard')` setzt Route voraus ✓
- I-03, I-04, I-05 → I-06: Tests testen alle neuen Routen + Templates ✓

---

## Design Decisions

| Decision | Chosen | Rejected | Rationale |
|----------|--------|----------|-----------|
| Feed-Paginierung | `?page=N` mit `offset(N*10).limit(10)` | Cursor-basiert via `before_id` | Einfacher für MVP, kein Realtime-Updates nötig |
| Like-Berechtigung | Nur Challenge-Teilnehmer können liken | Alle authentifizierten User | Konsistent mit `user_activities`-Berechtigungsmodell |
| Sprüche: Server vs. Client | Server (Route) via `get_random_quote()` | Client-side JS `Math.random()` | CSP-kompatibel; kein JS-Array nötig |
| Kommentar-Rumpf | Model + Route-Stub, kein UI | Kein Code | Vorbereitung für spätere Implementierung ohne erneute Migration |
| Feed-Scope | Nur aktive Challenge (alle Teilnehmer inkl. bailed_out) | Challenge-übergreifend | Privacy: User sehen nur ihre eigene Challenge |
| AJAX-Like | `fetch()` mit CSRF-Header | Form-Submit mit Redirect | Social-Media-Feeling; sofortige Rückmeldung |
| User-Display im Feed | `activity.user_display_name` (Property auf User) | Direkter Zugriff auf email | Display-Name bevorzugt; Nickname oder E-Mail-Teil |

---

## Boundaries

**Always:**
- Alle POST-Routen müssen CSRF-Schutz haben (Flask-WTF `csrf_token()` oder `X-CSRFToken`-Header für AJAX)
- Feed-Query mit `selectinload(Activity.media)` und `selectinload(Activity.likes)` – kein N+1
- ActivityComment-Rumpf darf KEIN UI-Element erzeugen (kein Button, kein Formular im Template)
- Alle neuen Routen sind `@login_required`
- Motivationssprüche sind auf Deutsch und sport-bezogen
- Das Top-5-Leaderboard auf der Dashboard-Seite zeigt die 5 Besten (niedrigste Strafe)

**Never:**
- Keine Activity-Daten aus fremden Challenges im Feed anzeigen
- Kein Liken ohne Teilnahme an der aktiven Challenge
- Kein `<!-- Kommentar -->` im HTML für den Kommentar-Rumpf – nur Code (Model + Route)
- Keine Migration ohne vorherigen `flask db migrate`-Aufruf (kein manuelles SQL)
- Keine Sprüche auf Englisch

**Ask First:** (keine offenen Fragen – alle Entscheidungen oben dokumentiert)

---

## Invalidation Risks

| Assumption | Affected Issues | Verification |
|------------|-----------------|--------------|
| `activity.user` ist per ORM lazy-loadbar (kein explizites eager load nötig) | I-03, I-04 | Test ob Feed-Template `activity.user.display_name` aufrufen kann |
| `dashboard_bp` ist unter `/dashboard` registriert → neue Routen sind erreichbar | I-03, I-04, I-05 | `grep register_blueprint app/__init__.py` |
| `Activity.created_at` ist TZ-aware (für `strftime` im Template) | I-04 | Bereits verifiziert: `DateTime(timezone=True)` in `activity.py:24` |
| Keine weiteren Uuid-Diffs in der neuen Migration | I-01 | Nach `flask db migrate` prüfen; ggf. manuell entfernen |

---

## Rollback Strategy

**Git-Checkpoint** vor Wave 1:
```bash
git stash  # oder commit als WIP-Branch
```

**Per-Wave Rollback:**
- Wave 1: `flask db downgrade <vorherige-revision>` → Migration rückgängig; Model-Datei revert
- Wave 2: Route-Datei revert
- Wave 3-4: Template-Datei revert; keine DB-Auswirkungen

---

## Verification Commands

```bash
# Nach I-01: Migration prüfen
FLASK_APP=run.py .venv/bin/flask db upgrade && echo "Migration OK"

# Nach I-02: Sprüche testen
set -a && source .env && set +a
.venv/bin/python -c "from app.utils.motivational_quotes import get_random_quote; print(get_random_quote())"

# Nach I-03: Routen erreichbar
set -a && source .env && set +a
.venv/bin/pytest tests/test_dashboard.py -v

# Nach I-04/I-05: Playwright-Smoke-Test (Haiku-Sub-Agent)
# Dashboard lädt, Top-5 sichtbar, Feed-Section sichtbar, "Mehr laden"-Button

# Vollständige Test-Suite
set -a && source .env && set +a
.venv/bin/pytest -v

# Ziel: >= 128 Tests (120 bestehend + 8 neue)
```

---

## Issue Sizing

| Issue | Größe | Begründung |
|-------|-------|------------|
| I-01 | S | 2 neue Klassen + Migration, klares Schema |
| I-02 | S | 1 neue Datei, 100 Strings + 1 Funktion |
| I-03 | M | 1 Datei, 3 neue Routen, Query-Logik, JSON |
| I-04 | M | 1 Template, AJAX-JS, Feed-HTML-Struktur |
| I-05 | S | 1 neue Datei (Leaderboard), 4 LOC in Navbar |
| I-06 | S | 1 Datei, 8 neue Testfunktionen |
