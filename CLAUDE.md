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


## Aktueller Stand (2026-04-24)

**Aktive Arbeit:** Multi-User Rebuild mit Connector-Architektur

- **Epic:** `sport-challenge-79s` – Rebuild vom Single-User-Prototyp zur Multi-User-Flask-App
- **Plan:** `.schrammns_workflow/plans/2026-04-23-sport-challenge-multi-user-rebuild.md` (25 Issues, 8 Waves)
- **Research:** `.schrammns_workflow/research/2026-04-23-architektur-best-practices-rebuild-sport-challenge-flask.md`
- **Quellen-Nachweis:** `.schrammns_workflow/research/2026-04-23-websearch-ergebnisse.md`
- **Git-Anker:** Tag `pre-rebuild-2026-04-24` (vor Wave 0 gesetzt, Rollback via `git reset --hard <tag>`)

### Einstieg für neue Sessions

```bash
bd prime                              # Workflow-Kontext
bd memories multi-user                # gespeicherter Pointer mit allen IDs
bd ready                              # aktuelle Wave (Start: I-01, I-02, I-03)
bd show sport-challenge-gxc           # erstes Wave-0-Issue im Detail
```

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

**Phase 1 (Ist-Zustand):** Single-User Flask-App mit Wochenansicht für Garmin-Aktivitäten.
- `app/__init__.py` – App Factory mit 2 Blueprints (auth, activities)
- `app/garmin/client.py` – Wrapper um `garminconnect`-Lib (Token-Reuse in `~/.garminconnect/`)
- `app/routes/auth.py` – Session-basierter Login mit custom `login_required` (wird in Wave 3 durch Flask-Login ersetzt)
- `app/routes/activities.py` – `/activities/week` mit Wochennavigation und 30-Min-Filter

**Phase 2 (Ziel, in Arbeit):** Multi-User mit Connector-Architektur.
- `app/extensions.py` – Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF, Flask-Limiter (ab I-05)
- `app/models/` – User + ConnectorCredential mit Fernet-Feldverschlüsselung
- `app/connectors/` – BaseConnector ABC + Provider-Registry, GarminConnector wrapt den bestehenden Client
- `app/utils/crypto.py` – HKDF-Key-Derivation aus SECRET_KEY

## Conventions & Patterns

- **Atomare Arbeitsweise:** ein Issue = ein Fix = ein Commit (siehe user-global CLAUDE.md)
- **Vor Implementation:** Ansatz beschreiben, auf Freigabe warten
- **Commit-Referenzen:** Titel enthält Plan-Issue-ID (z.B. `feat(I-01): FLASK_DEBUG env-basiert`)
- **Credentials:** nie hardcoden, nie loggen, Fernet-Field-Encryption für Connector-Daten
- **Migrationen:** `irreversible / requires-approval` – vor Wave 2 und Wave 4 SQLite-Backup
- **Tests:** Playwright-Aufgaben immer via Haiku-Sub-Agent (siehe user-global CLAUDE.md)
- **Kein Git-Remote konfiguriert:** `git push` entfällt, Issues sind lokal
