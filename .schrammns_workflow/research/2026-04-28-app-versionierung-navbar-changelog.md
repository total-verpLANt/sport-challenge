# Research: App-Versionierung und Navbar-Changelog

**Date:** 2026-04-28
**Scope:** Versionsnummer, Navbar-Struktur, CHANGELOG-Seite, Blueprint-Registrierung

## Executive Summary

- **Keine Versionsnummer** im Code vorhanden: weder `__version__`, noch `app.config["VERSION"]`, noch `pyproject.toml`, noch CHANGELOG.md. Einzige Versions-Anker sind 3 Git-Milestone-Tags (nicht semver).
- **Navbar** liegt vollständig inline in `app/templates/base.html:17-78` (Bootstrap 5.3.3, dark). Kein Partial, kein Include.
- **Kein Context-Processor** vorhanden — eine Versionsvariable muss via `@app.context_processor` ins Template injiziert werden.
- **Implementierungsstrategie:** `app/version.py` als Single Source of Truth → Context-Processor in `app/__init__.py` → Badge neben Brand in `base.html` → neue Route `/changelog` (leichtgewichtig in `app/routes/misc.py` oder als eigenständiger Blueprint) → `CHANGELOG.md` als Daten-Quelle.
- **Versionsvorschlag:** `0.6.0` (6 abgeschlossene Milestones: Single-User, Multi-User, Challenge-System, UUID, Multimedia, Lightbox+Delete).

## Key Files

| File | Purpose |
|------|---------|
| `app/templates/base.html:17-78` | Navbar-Definition (Bootstrap 5.3.3, inline) |
| `app/__init__.py:6-80` | `create_app()`, Blueprint-Registrierung, kein Context-Processor |
| `config.py` | App-Konfiguration (kein VERSION-Feld) |
| `app/routes/settings.py` | Settings-Blueprint (möglicher Heimat für Changelog-Route) |

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| Flask | >=3.0 | App-Framework |
| Bootstrap | 5.3.3 | CSS/Navbar |
| Flask-Talisman | aktuell | CSP (nonce für inline scripts) |
| Jinja2 | Flask-intern | Templates, context_processor |

## Findings

### Navbar-Struktur

`app/templates/base.html:17-78` — einzige Navbar-Definition:
- Brand: `🏃 Sport Challenge` → `dashboard.index` (Zeile 19)
- Linke Nav (auth): Dashboard, Meine Woche, Eintragen, Bonus (Zeilen 27-40)
- Rechtes Dropdown (auth): ⚙ `display_name`, Profil, Challenge, Connectors, Admin (Zeilen 44-68)
- Logout-POST-Form + Login-Button (Zeilen 69-75)
- CSP-Nonce Inline-Script am Ende (Zeile 98)

**Einfügepunkt für Version:** Neben oder unter dem Brand (`<a class="navbar-brand"...>`, Zeile 19) als `<small>` Badge oder `<span class="badge">`.

### Context-Processor

`app/__init__.py` hat **keinen** `@app.context_processor`. Globale Template-Variablen kommen ausschließlich von Extensions (Flask-Login: `current_user`, Flask-WTF: `csrf_token()`, Flask-Talisman: `csp_nonce()`).

Für eine Versionsvariable im Template braucht es:
```python
@app.context_processor
def inject_version():
    from app.version import __version__
    return {"app_version": __version__}
```

### Blueprint-Registrierung

10 Blueprints in `app/__init__.py:43-71`:
- auth `/auth`, activities `/activities`, connectors `/connectors`, admin `/admin`
- strava_oauth (kein Prefix), challenges `/challenges`, challenge_activities `/challenge-activities`
- bonus `/bonus`, dashboard `/dashboard`, settings `/settings`

Ein neuer `misc_bp` oder Inline-Route in `create_app()` wäre am leichtgewichtigsten für `/changelog`.

### Versionierungs-Status

- `requirements.txt`: nur Library-Pins, keine App-Version
- Kein `pyproject.toml`, kein `setup.py`
- Git-Tags: `pre-rebuild-2026-04-24`, `milestone-multi-user-rebuild-2026-04-24`, `milestone-uuid-visibility-2026-04-27`
- Conventional Commits sind durchgängig genutzt (`feat:`, `fix:`, `chore:`, `test:`) — gute Basis für CHANGELOG

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Navbar-Struktur | 4 | Vollständig gelesen, alle Zeilen bekannt |
| Context-Processor-Mechanismus | 4 | Kein vorhandener, Einfügepunkt klar |
| Blueprint-Registrierung | 4 | Alle 10 Blueprints inventarisiert |
| Versionierungs-Status | 4 | Vollständig: kein Semver, 3 Git-Tags |
| CHANGELOG-Format-Best-Practice | 2 | Conventional Commits vorhanden, kein Auto-Tool evaluiert |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Format des CHANGELOG (Markdown vs. DB vs. git-cliff) | nice-to-have | keepachangelog.com-Format ist Standard |
| Auto-Changelog-Generation (git-cliff, release-please) | nice-to-have | Nur relevant bei häufigerem Release-Rhythmus |
| CSP: Nonce-freier `<a>` für Badge — sicher? | must-fill | Badge ist reiner Anker, kein Script → kein Nonce nötig ✅ |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Kein Context-Processor vorhanden | Yes | grep nach `context_processor` lieferte 0 Treffer |
| Navbar nur in base.html | Yes | Agent B + direkte Read-Analyse |
| 10 Blueprints registriert | Yes | `app/__init__.py:43-71` gelesen |
| Semver `0.6.0` als Startversion sinnvoll | No | Urteil basiert auf 6 Wachwechsel-Milestones |

## Recommendations

1. **`app/version.py`** anlegen mit `__version__ = "0.6.0"` — Single Source of Truth
2. **Context-Processor** in `create_app()` (`app/__init__.py`) einfügen — `app_version` ans Template
3. **Navbar-Badge** in `base.html:19` neben dem Brand: `<small class="text-muted ms-2">v{{ app_version }}</small>` oder Bootstrap-Badge, als Link zu `/changelog`
4. **Changelog-Route** `/changelog` — leichtgewichtig als Inline-Route in `create_app()` oder neuer `misc_bp`; rendert ein neues Template `misc/changelog.html`
5. **`CHANGELOG.md`** anlegen (keepachangelog.com-Format), rückwirkend ab Phase 1 befüllen
6. **Tests:** mindestens 1 Smoke-Test `GET /changelog` → 200 hinzufügen
