# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Aktueller Stand (2026-07-15, Wachwechsel #22)

**Aktive Arbeit:** Keine. **v1.9.1**, gepusht auf `origin/main`. **338 Tests grün.**

**Oberstes Prinzip:** Änderungen dürfen die laufende Prod-Instanz **nie** gefährden (nur additiv/non-destruktiv). Erfordert eine Änderung einen Eingriff in Prod (z. B. neue `.env`-Var, Image-Rebuild, Migration), muss das im Abschluss-Report **explizit hervorgehoben** werden.

**Abgeschlossen diese Wache (#22):**
- `yyo3` → **Bugfix v1.9.1:** Kommentar-Button im Feed reagierte nicht. Ursache: `{% block scripts %}` war in `dashboard/index.html` **innerhalb** von `{% block content %}` verschachtelt → Jinja2 renderte das Feed-Script **doppelt**, doppelte Click-Delegation togglete den Kommentarbereich auf+zu. Fix: ein `endblock` verschoben (Commit `5a5cea3`). Verifiziert: 338 pytest + Playwright-E2E (Toggle, Senden, Lazy-Load, kein Doppel-Submit). Siehe lessons-learned (Jinja2-Templates).
- **dolt-Lock gelöst + bd-Buchungen nachgeholt:** Alle Closes aus Wache #21 gebucht (`8kr1.3`–`.7`, Epic `8kr1`, `yyo3`), bd-Schema-Migration v49→v53 als einziger Clone durchgeführt, `bd remember`-Pointer gesetzt.

**Vorherige Wache (#21, kompakt):** `uat2` → Long-Life-Login („Angemeldet bleiben", 30 Tage) **v1.8.0**; Session/Remember-Token ans Passwort gebunden **v1.8.1** (ohne Migration). `8kr1` (Epic) → Kommentarfunktion im Social-Feed (Aktivitäten + Abwesenheiten, gebündelte Notification, 6 Routen, IDOR-403, Lazy-Load, nonce-Script) **v1.9.0** – neue Migration `sick_period_comments`.

**⚠️ Prod-Eingriffe bei den ausstehenden Deploys (explizit):**
- **Eine additive Migration** `sick_period_comments` (v1.9.0) → läuft **automatisch** beim Container-Start (entrypoint.sh). Non-destruktiv.
- **Einmaliger Sammel-Logout** beim ersten Deploy mit v1.8.1: das `User.get_id`-Format ändert sich → alle bestehenden Sessions werden **einmalig** ungültig (danach 30-Tage-Remember). Keine Datengefahr.
- Kein Env-/Dependency-/Dockerfile-Eingriff diese Wache.

**⚠️ Einziger offener Punkt (bd-Sync):** `bd dolt push` muss noch **im externen Terminal** ausgeführt werden (synchronisiert Closes + Schema-Migration nach `refs/dolt/data` im GitHub-Repo). **Regel: `bd dolt push` NIE aus der Claude-Session** – der Sandbox-Proxy lässt `git-remote-http` sterben (TCP CLOSED), der Zombie hält `noms/LOCK` und blockiert danach jede bd-Operation. Diagnose bei Hänger: `lsof .beads/embeddeddolt/sport_challenge/.dolt/noms/LOCK`, Zombies extern killen. Lokale bd-Writes (create/close/remember) sind unkritisch. Details: lessons-learned (Beads/Dolt).

**Bestehende Konvention:** **Keine inline-Event-Handler** (`onchange`/`onclick`/…) in Templates – CSP blockiert sie. Stattdessen nonce-signiertes `<script>` mit `addEventListener`. CSP **nie** mit `unsafe-inline` aufweichen. (Erneut bestätigt in `8kr1.5`.)

**Optimierungs-Backlog (für die geplante große Runde):**
- **Tests/Quality:** `r96z` (Route-Smoke ≠ 500) · `w7e1` (Playwright-E2E in CI) · `fzku` (`scalar_one_or_none`-Audit) · `wkvn` (Migrations-Drift) · `w5os` (vulture+mypy+coverage) · `iofv` (Security-Header-Test)
- **Performance:** `379m` (Slow-Endpoints, N+1, Profiling) · `qt72` (DB-Index-Audit)
- **Security:** `izas` (IDOR/Autorisierung) · `b2u0` (CSP-Audit) · `j0b5` (Upload-Härtung) · `ytum` (Dependency/Secret-Hygiene)

**Restliche offene Queue:** `kfzb` (Notif Challenge start/ende – **ZEITbasiert, kein Scheduler** → Mechanik offen) · `2ar3` (PayPal-Spendenlink – **braucht Migration** `donation_url`) · `g6lz` (/challenges alle Einladungen, Plural) · `na54` (Menü-Link `/challenges` fehlt) · `tjs` (Rest: 404/500-Seiten, Limiter-Backend, robots.txt) · `4t4`/`18t` (KI-Screenshot).

**Bestehender Grenzfall (unverändert):** Aktivität exakt um 00:00 Uhr fällt im `_ranking`-Filter (`if v`) beim Frühaufsteher raus – bewusst nicht gefixt (siehe `docs/lessons-learned.md`).

### Einstieg für neue Sessions

```bash
./scripts/verify-handover.sh          # Schnell-Check: Umgebung ok?
bd prime                              # Workflow-Kontext
bd ready                              # nächste Issues (Optimierungs-Backlog, kein aktiver Epic)
```

## Build & Test

```bash
# venv neu aufbauen (bei Pfadproblemen nach Projektumzug)
uv venv .venv --python 3.14 --clear
uv pip install -r requirements-dev.txt

# Dev-Server starten
SECRET_KEY=<dein-key> FLASK_DEBUG=1 .venv/bin/python run.py  # PFLICHT: ohne SECRET_KEY RuntimeError

# Migrationen anwenden
FLASK_APP=run.py .venv/bin/flask db upgrade

# Tests ausführen
.venv/bin/pytest -v
```

**Hinweis Pfade:** Alle Pfade im Projekt müssen relativ sein. `.venv/bin/` statt absolutem Pfad.
Falls das venv nach einem Projektumzug gebrochen ist (Shebang-Fehler), einfach `uv venv .venv --clear` ausführen.

## Architecture Overview

**Phase 1 (erledigt):** Single-User Flask-App mit Wochenansicht für Garmin-Aktivitäten.
- `app/garmin/client.py` – Wrapper um `garminconnect`-Lib; `login()` gibt Token-JSON zurück, `reconnect(token_json)` ohne Disk
- `app/routes/activities.py` – `/activities/week` mit Wochennavigation und 30-Min-Filter

**Phase 2 (abgeschlossen):** Multi-User mit Connector-Architektur.
- `app/__init__.py` – App Factory mit Extensions-Init + user_loader + 9 Blueprints
- `app/extensions.py` – db, migrate, login_manager, csrf, limiter (Instanzen, kein init_app hier)
- `app/models/user.py` – User + UserMixin, scrypt N=2^17 (OWASP), is_admin-Property
- `app/models/connector.py` – ConnectorCredential mit `_JsonFernetField()` (Lazy-Init), UniqueConstraint(user_id, provider_type)
- `app/connectors/base.py` – BaseConnector ABC; `app/connectors/__init__.py` – PROVIDER_REGISTRY + @register
- `app/connectors/garmin.py` – GarminConnector, Tokens Fernet-verschlüsselt in `credentials["_garmin_tokens"]` (DB), `@retry_on_rate_limit` auf connect + get_activities
- `app/utils/crypto.py` – HKDF-Key-Derivation + FernetField TypeDecorator (Lazy-Init via `_get_fernet()`)
- `app/utils/retry.py` – `@retry_on_rate_limit(max_retries=2, base_delay=60)`, nur `GarminConnectTooManyRequestsError`
- `app/utils/decorators.py` – admin_required (verkettet login_required intern)
- `app/routes/auth.py` – Login/Register/Logout mit Flask-Login + Rate-Limit (5/min, 3/min)
- `app/routes/connectors.py` – /connectors/ Index + Connect + Disconnect (login_required, CSRF)
- `app/routes/activities.py` – /activities/week via Connector-Abstraction, Redirect bei fehlendem Credential
- `migrations/` – users + connector_credentials (Alembic)

**Phase 3 (abgeschlossen):** Challenge-System mit Leaderboard.
- `app/models/challenge.py` – Challenge (name, start/end_date, penalty_per_miss=5.0, bailout_fee=25.0) + ChallengeParticipation (user_id, challenge_id, weekly_goal 2|3, status invited|accepted|bailed_out)
- `app/models/activity.py` – Activity (user_id, challenge_id, activity_date, duration_minutes, sport_type, source manual|garmin|strava, external_id, screenshot_path) + ActivityMedia (1:n, file_path, media_type image|video, original_filename, file_size_bytes)
- `app/models/sick_week.py` – SickWeek (user_id, challenge_id, week_start, UniqueConstraint)
- `app/models/penalty.py` – PenaltyOverride (user_id, challenge_id, week_start, override_amount, reason, set_by_id)
- `app/models/bonus.py` – BonusChallenge (challenge_id, scheduled_date, description) + BonusChallengeEntry (user_id, bonus_challenge_id, time_seconds, UniqueConstraint)
- `app/utils/uploads.py` – Medien-Upload: IMAGE_EXTENSIONS + VIDEO_EXTENSIONS, UUID-Naming, 50 MB Limit, `get_media_type()`, `delete_media_files()`, Path-Traversal-Guard (`is_relative_to`)
- `app/services/penalty.py` – get_week_mondays(), count_fulfilled_days() (SQL GROUP BY/HAVING ≥30 min), calculate_weekly_penalty() (SickWeek→0, Override→amount, sonst missed×penalty), calculate_total_penalty() (Summe + Bailout-Fee)
- `app/services/weekly_summary.py` – get_challenge_summary() → Wochen, Teilnehmer, fulfilled_days, is_sick, penalty, overachieved, total_penalty (sortiert nach Strafe ASC)
- `app/routes/challenges.py` – 9 Routen: index, create (admin), detail, invite (admin), accept, decline, bailout, sick
- `app/routes/challenge_activities.py` – 7 Routen: log_form, log_submit, my_week, delete_activity, import_form, import_submit, add_media
- `app/routes/dashboard.py` – Leaderboard mit aktiver Challenge, Farbcodierung (success/warning/danger), Spendentopf
- `app/routes/bonus.py` – 4 Routen: index (mit Inline-Entry + Ranking), create (admin), entry
- `app/templates/` – challenges/ (3), activities/ (4: detail, log, my_week, add_media), dashboard/ (1), bonus/ (2) – alle Bootstrap 5.3.3, responsive
- `migrations/versions/2307226a4e48_*.py` – 7 neue Tabellen; `149d8863712f_*.py` – activity_media + Legacy-Datenmigration
- `tests/` – 94 Tests: pytest, conftest.py mit app/client/db-Fixture (In-Memory-SQLite)

## Conventions & Patterns

- **Atomare Arbeitsweise:** ein Issue = ein Fix = ein Commit (siehe user-global CLAUDE.md)
- **Vor Implementation:** Ansatz beschreiben, auf Freigabe warten
- **Commit-Referenzen:** Titel enthält Plan-Issue-ID (z.B. `feat(I-01): FLASK_DEBUG env-basiert`)
- **Credentials:** nie hardcoden, nie loggen, Fernet-Field-Encryption für Connector-Daten
- **Migrationen:** `irreversible / requires-approval` – vor Wave 2 und Wave 4 SQLite-Backup
- **Tests:** Playwright-Aufgaben immer via Haiku-Sub-Agent (siehe user-global CLAUDE.md)
- **Git-Remote:** `github.com/total-verpLANt/sport-challenge` – `git push` nach jedem Commit
- **CHANGELOG endnutzerfreundlich:** `CHANGELOG.md` wird auf der Webseite unter `/changelog` für die **App-Nutzer (Nicht-Techniker)** angezeigt. Einträge daher in einfacher Alltagssprache aus Nutzersicht schreiben – KEINE Ticket-IDs, Parameter, Funktions-/Datei-/Tabellennamen, Test-/Zeilenzahlen oder Implementierungsdetails (kein „N+1", „Migration", „Fernet" etc.). Kategorien: `### Neu`, `### Verbessert`, `### Behoben`, `### Sicherheit`. Versions-Überschrift bleibt `## [x.y.z] – JJJJ-MM-TT`. Technische Details gehören in die **Commit-Message** (für Entwickler/Agenten), nicht ins CHANGELOG.
- **Keine inline-Event-Handler in Templates:** `onchange`/`onclick`/`onsubmit`/… werden von der Talisman-CSP (`script-src` ohne `unsafe-inline`, nonce-basiert) **blockiert** – die Aktion läuft stumm ins Leere und pytest sieht es nicht. Stattdessen ein nonce-signiertes Script (`<script nonce="{{ csp_nonce() }}">…addEventListener(...)…</script>`). Die CSP **niemals** mit `unsafe-inline` aufweichen (XSS-Schutz). Siehe `oa6n` / lessons-learned / Memory `feedback_no_inline_event_handlers`.
