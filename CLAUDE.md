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


## Aktueller Stand (2026-06-22, Wachwechsel #17)

**Aktive Arbeit:** Keine. **v1.7.0**, gepusht auf `origin/main`.

- **Version:** 1.7.0 (gepusht; milestone-Tag `milestone-v1.7.0` auf `1137837`)
- **304 Tests grün**, bandit + pip-audit + CI grün.
- **Kein offener** `.env`-/Migrations-/Dependency-Eingriff. Die einzige Migration dieser Wache (Tabelle `notifications`) ist **bereits deployed**.

**Oberstes Prinzip:** Änderungen dürfen die laufende Prod-Instanz **nie** gefährden (nur additiv/non-destruktiv). Erfordert eine Änderung einen Eingriff in Prod (z. B. neue `.env`-Var, Image-Rebuild, Migration), muss das im Abschluss-Report **explizit hervorgehoben** werden.

**Abgeschlossen diese Wache (Notification-System + Hygiene):**
- `7y6` → Dashboard zeigt offene Challenge-Einladungen prominent ganz oben (vor dem Leaderboard), plural-fähig.
- crypto-CVE → `cryptography` 46.0.7→48.0.1 (CI-Gate `pip-audit` war durch GHSA-537c-gmf6-5ccf rot).
- `gau4` → **Notification-Fundament**: Modell `Notification` (app/models/notification.py), Service (app/services/notifications.py), Migration `notifications`-Tabelle. **deployed**.
- `tjs` (Teil) → Docker-Healthcheck grün: `/health`-Endpoint (app/routes/misc.py) + `localhost`/`127.0.0.1` automatisch in `TRUSTED_HOSTS` (config.py). **deployed**.
- `wsco` → **Navbar-Glocke**: Badge (Ungelesen-Zähler), Dropdown, ungelesene hervorgehoben, Einzel-/Alle-Löschen (app/routes/notifications.py, app/static/js/notifications.js). Klick liest einzeln.
- `vj7q` → Notification bei Challenge-Einladung (erster aktiver Auslöser; auth in challenges.py create_post + invite).
- `bqf5` → Notification an Admins bei Neuregistrierung (in `_notify_admins_new_user`, auth.py).
- CHANGELOG.md **komplett endnutzerfreundlich** umgeschrieben (es ist die `/changelog`-Webseite für Nutzer).

**Neue Konventionen (diese Wache, in CLAUDE.md Conventions & Patterns + lessons-learned):**
- **CHANGELOG endnutzerfreundlich:** keine Ticket-IDs/Parameter/Funktionsnamen; Technik gehört in die Commit-Message.
- **SemVer:** Anschluss-Tickets an einem bestehenden Feature → **Patch** (3. Stelle); nur neue eigenständige Features → Minor. HINWEIS: Die Notification-Auslöser dieser Wache wurden noch fälschlich als Minors (1.6.0/1.7.0) gezählt – ab jetzt korrekt als Patch.
- **Subagenten:** Test-/Recherche-Späher dürfen **nie** committen/pushen (ein general-purpose-Subagent tat es eigenmächtig). Read-only/git-Verbot im Prompt; Berichte gegen echte Artefakte verifizieren.

**Deploy-Stand:** Live ≈ **v1.4.1** auf `stonbgsport01` (zuletzt nach Healthcheck-Fix deployed, Container „healthy"). **v1.5.0–1.7.0 ausstehend** – rein additiv (UI + Auslöser), **keine** Migration/`.env`: `git pull && docker compose pull && docker compose up -d`. (Die `notifications`-Migration lief bereits beim `gau4`-Deploy.)

**Offene Queue (`bd ready`):**
- `oa6n` (P2, **Bug**) – Bonus-Challenge fehlerhaft im Multi-Challenge-Kontext (Repro/Diagnose vom Kapitän noch offen)
- `co52` (P2, **Bug**) – `challenges.index` crasht bei >1 gleichzeitiger Einladung (`scalar_one_or_none`)
- `ngk0` (P2) – Notification: „X hat deinen Beitrag geliked" (Lärm-Risiko bedacht)
- `kfzb` (P2) – Notification: Challenge startet/endet (**ZEITbasiert, kein Scheduler** → Mechanik-Entscheidung nötig)
- `2ar3` (P2) – PayPal-Spendenlink (**braucht Migration**: `donation_url`-Spalte!)
- `tjs` (P3, Rest) – 404/500-Seiten, Limiter-Backend, robots.txt
- `4t4` / `18t` (P3) – KI-Screenshot-Features (Kalorien / Sportart)

**Bestehender Grenzfall (unverändert):** Aktivität exakt um 00:00 Uhr fällt im `_ranking`-Filter (`if v`) beim Frühaufsteher raus – bewusst nicht gefixt (siehe `docs/lessons-learned.md`).

### Einstieg für neue Sessions

```bash
./scripts/verify-handover.sh          # Schnell-Check: Umgebung ok?
bd prime                              # Workflow-Kontext
bd memories "wachwechsel-17"          # Pointer für diesen Wachwechsel (#17)
bd ready                              # nächste Issues
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
