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


## Aktueller Stand (2026-07-16, Wachwechsel #23)

**Aktive Arbeit:** Keine. **v1.10.2**, gepusht auf `origin/main`, **deployed & vom Kapitän bestätigt**. **376 Tests grün**, CI (Docker Publish) grün. Git-Tag `v1.10.2` auf `134e233`.

**Oberstes Prinzip:** Änderungen dürfen die laufende Prod-Instanz **nie** gefährden (nur additiv/non-destruktiv). Erfordert eine Änderung einen Eingriff in Prod (z. B. neue `.env`-Var, Image-Rebuild, Migration), muss das im Abschluss-Report **explizit hervorgehoben** werden.

**Abgeschlossen diese Wache (#23):**
- **Epic `1t8s` → Spenden-Voting v1.10.0** (7 Issues, 5 Waves via make-it-so): Teilnehmer (accepted **und** bailed_out) schlagen Spendenziele vor (Name Pflicht, Beschreibung/Link optional); Admin öffnet nach `end_date` die Abstimmung mit einstellbarem `max_votes_per_user`, Live-Zwischenstand ohne Voter-Namen, Admin schließt manuell (Gleichstand → Radio-Auswahl unter Punktgleichen, serverseitig validiert). Neu: `app/models/donation.py` (3 Tabellen, Migration `1e5248e475d7` — **in Prod ausgerollt**), `app/routes/donation.py` (7 Routen), `app/utils/urls.py::is_safe_external_url` (http/https-Whitelist), `donation/index.html` (rein Form-basiert, kein JS), Dashboard-Banner/Gewinner-Anzeige, Notification `donation_poll_opened`. Security-Audit: PASS_WITH_NOTES. Plan/Research archiviert unter `.schrammns_workflow/plans_archive/` bzw. `research/2026-07-15-spenden-voting-feature.md`.
- **`fix(security)` → v1.10.1:** garminconnect 0.3.3→0.3.5 (CVE-2026-54447). CI-pip-audit hatte 3 Läufe rot gefärbt — Ursache war die frisch veröffentlichte CVE, nicht der Feature-Code. Siehe lessons-learned (CI/pip-audit).
- **`vnjb` + `qe46` → v1.10.2:** Dashboard-Link „Spendenziel vorschlagen" in der Vorschlagsphase (aktive + Abschluss-Karte, nur Teilnehmer, nur solange kein Poll) und Admin-Notification `donation_proposal_created` bei neuem Vorschlag (Vorschlags-Name als User-Freitext bewusst NICHT in der Message — XSS-Invariante).

**Prod-Status:** v1.10.2 ist ausgerollt, Migration `1e5248e475d7` gelaufen. **Keine ausstehenden Prod-Eingriffe.**

**⚠️ Einziger offener Punkt (bd-Sync):** `bd dolt push` **im externen Terminal** ausführen (Closes dieser Wache: Epic `1t8s` + `.1`–`.7`, `vnjb`, `qe46`; neue Tickets `m70u`, plus `bd remember`). **Regel: `bd dolt push` NIE aus der Claude-Session** (Sandbox-Proxy killt `git-remote-http`, Zombie hält `noms/LOCK`). Details: lessons-learned (Beads/Dolt).

**Bestehende Konventionen (bestätigt):** Keine inline-Event-Handler (CSP, nonce-Scripts); `{% block scripts %}` nie in `{% block content %}` verschachteln; Subagenten committen/pushen NIE (Lead reviewt, testet, committet atomar pro Issue).

**Optimierungs-Backlog (für die geplante große Runde):**
- **Tests/Quality:** `r96z` (Route-Smoke ≠ 500) · `w7e1` (Playwright-E2E in CI) · `fzku` (`scalar_one_or_none`-Audit) · `wkvn` (Migrations-Drift) · `w5os` (vulture+mypy+coverage) · `iofv` (Security-Header-Test)
- **Performance:** `379m` (Slow-Endpoints, N+1, Profiling) · `qt72` (DB-Index-Audit)
- **Security:** `izas` (IDOR/Autorisierung) · `b2u0` (CSP-Audit) · `j0b5` (Upload-Härtung) · `ytum` (Dependency/Secret-Hygiene) · **neu:** `m70u` (Spenden-Voting Härtung: Vote-Limit-TOCTOU + Waisen-Votes bei Admin-Löschung, 2× LOW aus Audit, P3)

**Restliche offene Queue:** `kfzb` (Notif Challenge start/ende – **ZEITbasiert, kein Scheduler** → Mechanik offen) · `2ar3` (PayPal-Spendenlink – **braucht Migration** `donation_url`; Hinweis: Voting-Gewinner aus `1t8s` kann den Link künftig speisen) · `g6lz` (/challenges alle Einladungen, Plural) · `na54` (Menü-Link `/challenges` fehlt) · `tjs` (Rest: 404/500-Seiten, Limiter-Backend, robots.txt) · `4t4`/`18t` (KI-Screenshot).

**Bestehender Grenzfall (unverändert):** Aktivität exakt um 00:00 Uhr fällt im `_ranking`-Filter (`if v`) beim Frühaufsteher raus – bewusst nicht gefixt (siehe `docs/lessons-learned.md`).

### Nachricht vom scheidenden Wachoffizier (2026-07-16)

> Zwei Dinge, die diese Wache gelehrt hat: Erstens, wenn die CI plötzlich rot wird, prüfe zuerst den pip-audit-Step, bevor du deinen eigenen Code verdächtigst — bei uns war es eine über Nacht veröffentlichte CVE in `garminconnect`, drei Läufe sahen nach Feature-Bruch aus und waren keiner. Zweitens: `bd dep add A B` heißt „A hängt von B ab", genau andersherum als das Beispiel in der set-course-Skill-Doku — ich habe die Kanten des Epics einmal komplett falsch herum verdrahtet und erst `bd ready` hat es verraten; verifiziere Dependency-Verdrahtung immer damit. Das Spenden-Voting ist bewusst komplett Form-basiert ohne JavaScript gebaut — wer dort UI nachrüstet, sollte das nicht ohne Not aufgeben, es hat uns die ganze CSP-/Doppel-Script-Problematik von yyo3 erspart.

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
