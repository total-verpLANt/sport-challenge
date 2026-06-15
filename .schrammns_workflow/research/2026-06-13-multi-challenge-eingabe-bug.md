# Research: Multi-Challenge-Eingabe-Bug (`_active_participation()`)

**Date:** 2026-06-13
**Scope:** Code-Pfad rund um `_active_participation()` in `app/routes/challenge_activities.py`; alle Eingabe-Schreibpfade (log/import/sick-period), zugehörige Datenmodelle, Templates und Tests. Grundlage für Epic `sport-challenge-0bv` / Kind `0bv.1`.
**Web Research:** Bewusst minimal — reines internes Auswahl-/Autorisierungs-Problem mit etabliertem Standardmuster (OWASP IDOR/BOLA: serverseitige Objekt-Autorisierung gegen den eingeloggten Nutzer). Keine Library-Frage, daher kein Context7/WebSearch-Budget verbraucht.
**Semantic Analysis:** Vollständig (Read/Grep über das gesamte Projekt; Aufrufer projektweit verifiziert).

## Executive Summary

- **Bug bestätigt:** `_active_participation()` (`app/routes/challenge_activities.py:30-41`) selektiert akzeptierte Teilnahmen mit `.first()` **ohne `ORDER BY` und ohne Datumsfilter**. Bei ≥2 gleichzeitig `accepted` Teilnahmen ist die gewählte Challenge **nicht-deterministisch** → stiller Daten-Bug.
- **3 Schreibpfade betroffen:** `log_submit` (FK-Write `:126`), `import_submit` (`:479`), `sick_period_submit` (`:302`). Alle leiten die Ziel-Challenge ausschließlich aus dem willkürlichen `.first()` ab — **kein** Request-Parameter steuert die Challenge.
- **Perfides Folgeproblem:** Die Datums-Validierung in `log_submit:81` prüft gegen die Periode der *willkürlich* gewählten Challenge. Bei nicht-überlappenden Perioden (Übergangs-Szenario) wird ein korrekter Eintrag für Challenge B abgelehnt, weil er außerhalb der Periode von Challenge A liegt — Nutzer kann nichts eintragen und versteht nicht warum.
- **Kein `challenge_id`-Übergabemechanismus existiert** (kein Hidden-Field, kein Select, keine Session). Muss neu gebaut werden — Vorbild liegt bereits im Code: `bonus._user_is_accepted_participant(challenge_id)` (`app/routes/bonus.py:30-39`) ist das saubere "explizite challenge_id + Backend-Verifikation"-Muster.
- **Test-Lücke:** Null Tests mit zwei aktiven Challenges für Eingabe-Pfade; `sick_period_submit` (POST) ist komplett ungetestet. Fixture-Vorbild existiert in `tests/test_dashboard.py:256-272`.
- **Non-destruktiv umsetzbar:** Alle `challenge_id`-Spalten existieren bereits (`Activity`, `SickPeriod`). **Keine Migration, keine `.env`-Var, keine Dependency** nötig — rein Code + Template-Felder.

## Key Files

| File | Purpose |
|------|---------|
| `app/routes/challenge_activities.py` | **Bug-Herd.** `_active_participation()` (`:30-41`) + 7 Aufrufer + 3 Schreibpfade |
| `app/models/challenge.py` | `Challenge` (`:11-31`), `ChallengeParticipation` (`:34-53`); Status `invited\|accepted\|bailed_out` (`:42-43`) |
| `app/models/activity.py` | `Activity` mit `challenge_id` FK (`:14`); `UniqueConstraint(user_id, external_id)` (`:42-44`) |
| `app/models/sick_period.py` | `SickPeriod` mit `challenge_id` FK (`:14`) — Datei heißt `sick_period.py`, nicht `sick_week.py` |
| `app/routes/dashboard.py` | **Vorbild Anzeige:** `_build_dashboard_boards` lädt ALLE aktiven Challenges via `.all()` (`:182-191`) |
| `app/routes/bonus.py` | **Vorbild Verifikation:** `_user_is_accepted_participant(challenge_id)` (`:30-39`); eigener (ebenfalls fragwürdiger) `_get_active_challenge()` (`:23-27`) |
| `app/routes/challenges.py` | `index` baut Participation-Map aller Teilnahmen (`:78-85`); fragwürdiges `scalar_one_or_none()` (`:62-67`) |
| `app/__init__.py` | `inject_nav_challenges()` Context-Processor liefert ALLE Challenges fürs Navbar-Dropdown (`:140-164`) |
| `app/templates/activities/log.html` | Eingabe-Form Aktivität (Tab 1) + Abwesenheit (Tab 2); **kein** `challenge_id`-Feld |
| `app/templates/activities/import.html` | Import-Form; **kein** `challenge_id`-Feld |
| `app/templates/activities/my_week.html` | Sick-Period inline; **kein** `challenge_id`-Feld |
| `app/templates/challenges/index.html` | **Select-Vorbild:** `weekly_goal`-Dropdown (`:32-35`) |
| `tests/test_dashboard.py` | **Fixture-Vorbild:** zwei aktive Challenges + zwei accepted Participations (`:251-272`) |
| `tests/test_activities_log.py` | Log/Sick-Tests; Helfer `_create_challenge_with_participation` (`:23`) — nur EINE Challenge |
| `tests/test_import.py` | Import-Tests; Helfer (`:42`) — nur EINE Challenge |
| `tests/conftest.py` | app/db/client-Fixtures; CSRF & Rate-Limit aus; **keine** Challenge-Fixtures |

## Technology Stack

| Library/Framework | Version | Role |
|-------------------|---------|------|
| Flask + Flask-Login | — | Routen, `current_user`, `login_required` |
| SQLAlchemy 2.x | — | `db.select(...).scalars().first()` — die fehlerhafte Auswahl |
| Flask-WTF (CSRF) | — | CSRF-Token in allen Forms; in Tests deaktiviert (`conftest.py:19`) |
| Bootstrap | 5.3.3 | `form-select`-Pattern für künftiges Challenge-Dropdown |

## Findings

### F1 — Die Bug-Quelle: `_active_participation()`

`app/routes/challenge_activities.py:30-41`:
```python
def _active_participation():
    """Return the current user's accepted ChallengeParticipation, or None."""
    return (
        db.session.execute(
            db.select(ChallengeParticipation).where(
                ChallengeParticipation.user_id == current_user.id,
                ChallengeParticipation.status == "accepted",
            )
        ).scalars().first()
    )
```
Zwei Defekte:
1. **`.first()` ohne `ORDER BY`** → bei ≥2 `accepted` Teilnahmen nicht-deterministisch (faktisch meist niedrigste `id`).
2. **Kein Datumsfilter** (`start_date`/`end_date`) → eine bereits beendete oder noch nicht gestartete Teilnahme zählt weiterhin als "aktiv". Steht im Kontrast zum Dashboard, das zeitraumbasiert filtert (`dashboard.py:182-186`).

`ChallengeParticipation` erlaubt explizit mehrere `accepted` pro User: `UniqueConstraint("user_id", "challenge_id")` (`challenge.py:36`) verhindert nur Duplikate **pro** Challenge, nicht mehrere Challenges gleichzeitig.

### F2 — Aufrufer (projektweit, alle in `challenge_activities.py`)

| file:line | Funktion | Nutzung |
|---|---|---|
| `:47` | `log_form` (GET) | Gate + `participation` ans Template |
| `:58` | `log_submit` (POST) | **Schreibt** Ziel-Challenge |
| `:152` | `my_week` (GET) | Filtert Wochenansicht/SickPeriods |
| `:241` | `sick_period_submit` (POST) | **Schreibt** Challenge der Abwesenheit |
| `:320` | `import_form` (GET) | Gate + Template |
| `:410` | `import_submit` (POST) | **Schreibt** Ziel-Challenge des Imports |
| `:583` | `user_activities` (GET) | Bestimmt "meine" Challenge zum Vergleich |

`delete_activity` (`:498`) und `add_media` (`:615`) nutzen `_active_participation()` **nicht** — sie arbeiten über `activity_id`/`activity.challenge_id`. Keine externen Aufrufer außerhalb der Datei.

### F3 — Schreibpfade im Detail (der Daten-Bug)

**`log_submit`** (`:55-146`): `participation = _active_participation()` (`:58`) → `challenge = participation.challenge` (`:80`) → Datums-Check `if not (challenge.start_date <= activity_date <= challenge.end_date)` (`:81`) → FK-Write `challenge_id=participation.challenge_id` (`:126`).

**`import_submit`** (`:407-495`): `participation = _active_participation()` (`:410`) → pro Aktivität `challenge = db.session.get(Challenge, participation.challenge_id)` (`:468`) → Periodenprüfung mit `continue` (`:469`) → FK-Write `:479`.

**`sick_period_submit`** (`:238-314`): `participation = _active_participation()` (`:241`) → `challenge = participation.challenge` (`:246`) → Clamping `max(sick_from, challenge.start_date)`/`min(sick_to, challenge.end_date)` (`:268-269`), Reject nur wenn `clamped_start > clamped_end` (`:271`) → Overlap-Check scoped auf `SickPeriod.challenge_id == challenge.id` (`:278`) → FK-Write `challenge_id=challenge.id` (`:302`).

In allen drei Fällen: Challenge **nie** aus dem Request, immer aus dem willkürlichen `.first()`.

### F4 — Kein `challenge_id`-Übergabemechanismus

Grep über `app/templates/` und `app/` bestätigt: **kein** Hidden-Field `name="challenge_id"`, **kein** Select, **keine** `session["challenge_id"]`-Nutzung. Die einzige Challenge-Referenz in Templates ist die Sichtbarkeitsbedingung `my_week.html:55`. Die Ziel-Challenge wird ausschließlich serverseitig abgeleitet → Nutzer hat keinerlei Steuerung.

### F5 — Vorbilder im Bestand (Wiederverwendung statt Neuerfindung)

- **Liste aller Teilnahmen:** `challenges.index` baut `participation_by_challenge` aus **allen** Teilnahmen des Users (`challenges.py:78-85`) — fast die gesuchte `_accepted_participations()`, filtert nur nicht auf `accepted`.
- **Alle aktiven Challenges (zeitraumbasiert):** `dashboard._build_dashboard_boards` (`dashboard.py:182-191`) gibt `.all()` zurück.
- **Explizite challenge_id + Verifikation:** `bonus._user_is_accepted_participant(challenge_id)` (`bonus.py:30-39`) — **das saubere Zielmuster**: challenge_id als Parameter, Backend verifiziert Teilnahme+Status.
- **Select-UI:** `weekly_goal`-Dropdown in `challenges/index.html:32-35` und `challenges/detail.html:53` — Bootstrap `form-select` mit `<label>` + `<div class="mb-3">`.

### F6 — Status-Asymmetrie (bewusst beachten)

Anzeige/Services filtern auf `status.in_(["accepted","bailed_out"])` (`weekly_summary.py:111`, `statistics.py:138`, `challenge_activities.py:558`). Die **Eingabe** filtert nur `status == "accepted"` (`:36`) — bewusst, da nur aktive Teilnehmer eintragen dürfen. Diese Asymmetrie beim Umbau **beibehalten** (ein `bailed_out`-Nutzer soll nicht rückwirkend eintragen).

### F7 — Paralleler Bug im Bonus-Pfad (`0bv.3`, separat)

`bonus._get_active_challenge()` (`bonus.py:23-27`) nimmt die global neueste Challenge (`order_by created_at.desc()).first()`) **ohne User-Bezug und ohne Zeitraum** — ein eigenständiger Defekt, im Epic als `0bv.3` getrennt. Nicht Teil von `0bv.1`.

### F8 — Test-Lage

- `conftest.py` bietet **keine** Challenge-Fixtures; jede Testdatei dupliziert `_create_challenge_with_participation` (`test_activities_log.py:23`, `test_import.py:42`) — immer **genau eine** Challenge.
- **Null Tests** mit zwei `accepted` Teilnahmen für log/sick/import → `.first()`-Verhalten dort komplett ungetestet.
- `sick_period_submit` (POST: Anlegen/Update/Clamping/Overlap) ist **vollständig ungetestet**; nur Delete-Pfade existieren (`test_activities_log.py:555-619`).
- Fixture-Vorbild für zwei aktive Challenges: `test_dashboard.py:256-272` (`test_dashboard_two_active_challenges_two_boards`).

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| `_active_participation()` + Defekt | 4 | Body gelesen, beide Defekte (Ordering + Datum) verstanden, Constraint-Implikation geklärt |
| Aufrufer-Graph | 4 | Projektweit verifiziert, alle 7 + 2 Nicht-Nutzer dokumentiert |
| Schreibpfade (log/import/sick) | 3 | Exakte Zeilen für Wahl, Validierung, FK-Write; Clamping-Logik verstanden |
| Datenmodelle | 4 | Felder, Status-Werte, Constraints, FKs belegt |
| Vorbilder (Helfer + UI + Verifikation) | 3 | Konkrete Pattern-Quellen identifiziert |
| Templates / `challenge_id`-Übergabe | 3 | Bestätigt: existiert nicht; Select-Vorbild gefunden |
| Test-Lage & Fixtures | 3 | Lücke + Vorbild präzise lokalisiert |
| Web/OWASP-Best-Practice | 2 | Bewusst flach: Standardmuster (serverseitige Objekt-Autorisierung) bekannt, kein externes Budget |

Alle kritischen Bereiche ≥ 2, mehrere ≥ 3 → **Quality Gate erfüllt**, bereit für Planung.

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Quelle des Selektors: eigener user-gefilterter `_accepted_participations()` vs. Wiederverwendung `inject_nav_challenges` | must-fill | Design-Entscheidung in `/set-course` — Empfehlung: eigener Helfer (Navbar liefert ALLE, auch fremde Challenges; Eingabe braucht nur eigene `accepted`) |
| UI bei mehreren aktiven Challenges: Dropdown vs. Tabs in `log`/`my_week` | must-fill | Festlegen in Planung; Dropdown nach `weekly_goal`-Muster ist der schlankste Weg |
| Soll `_active_participation()` zusätzlich nach Datum filtern (beendete Challenge ausblenden)? | nice-to-have | Klären: schränkt Nach-Eintragen für beendete Challenges ein — evtl. unerwünscht. Konservativ: bei Eingabe nur Datumsvalidierung gegen gewählte Challenge, kein globaler Datumsfilter |
| `import`: Connector pro Challenge oder global? | nice-to-have | Vermutlich global (Garmin user-gebunden); im Plan kurz festhalten |
| `user_activities` (`0bv.2`): Schnittmenge gemeinsamer Challenges zweier User | nice-to-have | Gehört zu `0bv.2`, nicht `0bv.1` — hier nur erwähnen |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Ein User kann mehrere `accepted` Teilnahmen gleichzeitig haben | Yes | `UniqueConstraint(user_id, challenge_id)` nur pro Challenge (`challenge.py:36`) |
| `challenge_id`-Spalten existieren bereits auf allen Ziel-Tabellen | Yes | `activity.py:14`, `sick_period.py:14` |
| Kein bestehender `challenge_id`-Request-Parameter | Yes | Grep über `app/` + Templates, 0 Treffer |
| `.first()` liefert in der Praxis niedrigste `id` | No | DB-abhängig; nicht garantiert (genau das ist der Bug) |
| Kein Prod-Eingriff (Migration/.env/Dependency) nötig | Yes (vorbehaltlich Planung) | Alle Spalten vorhanden; Fix ist Code + Template — bei Form-Validierung keine DB-Constraint-Änderung |
| Status-Filter `accepted` (nicht `bailed_out`) bei Eingabe ist beabsichtigt | Yes | Konsistent in Eingabe-Code (`:36`); Anzeige nutzt bewusst `accepted+bailed_out` |

## Recommendations

**Reihenfolge für `/set-course` (atomar, ein Fix = ein Commit):**

1. **Helfer `_accepted_participations()`** neu (Liste aller `accepted` Teilnahmen des Users), plus `_resolve_participation(challenge_id)` der eine challenge_id gegen den User verifiziert (Vorbild: `bonus._user_is_accepted_participant`). `_active_participation()` als Rückwärtskompatibilitäts-Default (genau 1 Teilnahme) behalten.
2. **Backend-Härtung der 3 Schreibpfade** (`log_submit`, `import_submit`, `sick_period_submit`): `challenge_id` aus `request.form` lesen → gegen `_accepted_participations()` verifizieren → bei Fehlen/Fremd-Challenge `403`/Flash. **Datums-Validierung gegen die gewählte Challenge.** Das ist der sicherheitskritische Kern (IDOR-Schutz) — sollte **vor** dem UI committed werden, damit das Backend nie einem Form-Parameter blind vertraut.
3. **UI: Challenge-Select** in `log.html`, `import.html`, `my_week.html` — nur rendern, wenn > 1 aktive Teilnahme (sonst Hidden-Field mit der einzigen `challenge_id`; kein UX-Regress). Bootstrap `form-select` nach `weekly_goal`-Muster.
4. **Tests:** geteilte Fixture `_create_two_active_challenges` (Vorbild `test_dashboard.py:256-272`); Tests für deterministische Zuordnung in allen 3 Pfaden + nicht-überlappende Perioden (Übergangs-Szenario) + erstmals `sick_period_submit`-POST-Coverage.

**Sicherheits-Hinweis (Käpt'n, wichtig):** Schritt 2 ist eine **Autorisierungsgrenze**. Sobald `challenge_id` aus dem Formular kommt, ist es ein nutzerkontrollierter Parameter — ohne serverseitige Verifikation (Teilnahme + `accepted`) entstünde ein IDOR (Eintrag in fremde Challenge). Backend-Check ist Pflicht, das Dropdown ist nur Komfort.

**TODO (nicht Teil `0bv.1`, separat verfolgen):**
- `challenges.py:62-67` nutzt `scalar_one_or_none()` für `active_participation` → würde bei 2 `accepted` einen `MultipleResultsFound`-**Crash** werfen (härter als der stille `.first()`-Bug). Sollte im selben Epic mitgehärtet werden (eigenes Ticket erwägen).
- `bonus._get_active_challenge()` (`bonus.py:23-27`) — separater Defekt, bereits als `0bv.3` erfasst.

**Verifikations-Hinweis (aus `docs/lessons-learned.md:187-197`):** Bei UI-Verifikation Dev-Server auf frischem Port starten und gerendertes HTML per `curl` gegenprüfen — nicht dem Browser gegen einen evtl. hängenden Alt-Server vertrauen.
