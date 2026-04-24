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


## Aktueller Stand (2026-04-24, Wachwechsel)

**Aktive Arbeit:** Multi-User Rebuild – Wave 0–3 abgeschlossen, Wave 4/5 als nächstes

- **Epic:** `sport-challenge-79s` – Rebuild vom Single-User-Prototyp zur Multi-User-Flask-App
- **Fortschritt:** 21 von 25 Plan-Issues erledigt (+ 6 Altissues), 4 Issues ready
- **Plan:** `.schrammns_workflow/plans/2026-04-23-sport-challenge-multi-user-rebuild.md` (25 Issues, 8 Waves)
- **Research:** `.schrammns_workflow/research/2026-04-23-architektur-best-practices-rebuild-sport-challenge-flask.md`
- **Git-Anker:** Tag `pre-rebuild-2026-04-24` (Rollback via `git reset --hard pre-rebuild-2026-04-24`)
- **Lessons Learned:** `docs/lessons-learned.md` (Alembic-Fallstrick, Sub-Agent-Permissions, scrypt-Defaults)

### Einstieg für neue Sessions

```bash
./scripts/verify-handover.sh          # Schnell-Check: Umgebung ok?
bd prime                              # Workflow-Kontext
bd memories multi-user                # gespeicherter Pointer mit allen IDs
bd ready                              # nächste Issues
```

**Nächste Issues (ready):**
- `i7k` – I-16: Migration connector_credentials-Tabelle ← **hier einsteigen**
- `q7a` – I-17: GarminConnector-Implementation mit Per-User-Token-Isolation
- `nmu` – I-21: Flask-Limiter am Login-Endpoint aktivieren
- `6n2` – I-23: pytest + Flask-Fixtures Setup
- `gvl` – OWASP-konforme scrypt-Parameter

**Plan-ID → bd-ID Quick-Map:**
`I-01→gxc · I-02→om6 · I-03→0fd · I-04→25e · I-05→cjx · I-06→99s · I-07→4qi · I-08→bmu · I-09→l6s · I-10→p67 · I-11→xta · I-12→uwg · I-13=t65 · I-14→tya · I-15→tjp · I-16→i7k · I-17→q7a · I-18=gdc · I-19→4p5 · I-20→58h · I-21→nmu · I-22=gvl · I-23→6n2 · I-24→k7x · I-25→0jp`

## Build & Test

```bash
# Virtualenv aktivieren
source .venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt

# Dev-Server starten (Debug nur wenn FLASK_DEBUG=1 nach I-01)
FLASK_DEBUG=1 python run.py

# Tests (ab I-23 verfügbar)
# pytest
```

## Architecture Overview

**Phase 1 (erledigt):** Single-User Flask-App mit Wochenansicht für Garmin-Aktivitäten.
- `app/garmin/client.py` – Wrapper um `garminconnect`-Lib (Token-Reuse in `~/.garminconnect/`)
- `app/routes/activities.py` – `/activities/week` mit Wochennavigation und 30-Min-Filter

**Phase 2 (in Arbeit, Wave 0–3 done):** Multi-User mit Connector-Architektur.
- `app/__init__.py` – App Factory mit Extensions-Init + user_loader
- `app/extensions.py` – db, migrate, login_manager, csrf, limiter (Instanzen, kein init_app hier)
- `app/models/user.py` – User + UserMixin, scrypt-Hashing, is_admin-Property
- `app/models/connector.py` – ConnectorCredential mit JSON-FernetField, UniqueConstraint(user_id, provider_type)
- `app/connectors/base.py` – BaseConnector ABC; `app/connectors/__init__.py` – PROVIDER_REGISTRY + @register
- `app/utils/crypto.py` – HKDF-Key-Derivation + FernetField TypeDecorator
- `app/utils/decorators.py` – admin_required (verkettet login_required intern)
- `app/routes/auth.py` – Login/Register/Logout mit Flask-Login; Logout POST-only
- `migrations/` – Alembic initialisiert, users-Tabelle migriert
- **Noch offen:** GarminConnector-Impl (I-17), connector_credentials-Migration (I-16), Activities-Route auf Connector-Abstraction (I-20), Auth-Flow-Tests (I-24)

## Conventions & Patterns

- **Atomare Arbeitsweise:** ein Issue = ein Fix = ein Commit (siehe user-global CLAUDE.md)
- **Vor Implementation:** Ansatz beschreiben, auf Freigabe warten
- **Commit-Referenzen:** Titel enthält Plan-Issue-ID (z.B. `feat(I-01): FLASK_DEBUG env-basiert`)
- **Credentials:** nie hardcoden, nie loggen, Fernet-Field-Encryption für Connector-Daten
- **Migrationen:** `irreversible / requires-approval` – vor Wave 2 und Wave 4 SQLite-Backup
- **Tests:** Playwright-Aufgaben immer via Haiku-Sub-Agent (siehe user-global CLAUDE.md)
- **Kein Git-Remote konfiguriert:** `git push` entfällt, Issues sind lokal
