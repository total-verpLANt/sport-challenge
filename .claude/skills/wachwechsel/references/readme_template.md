# README-Gerüst für neue Projekte

Wenn beim Wachwechsel festgestellt wird, dass kein README existiert oder es trivial ist, schlage dem Kapitän dieses Gerüst vor. Es ist bewusst knapp – lieber weniger Text, der stimmt, als Marketing-Füllmaterial.

## Template

```markdown
# <Projekt-Name>

<Ein-Satz-Beschreibung, was das Projekt tut und für wen.>

## Voraussetzungen

- <Python/Node/etc.>-Version
- <Externe Dienste, z.B. Garmin-Konto>
- <OS-Hinweise falls relevant>

## Setup

```bash
# Repo klonen
git clone <repo-url>
cd <projekt>

# Virtualenv und Dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Environment-Variablen
cp .env.example .env
# .env nach eigenem Bedarf anpassen
```

## Starten

```bash
# Dev-Server
FLASK_DEBUG=1 python run.py

# Tests (falls vorhanden)
pytest
```

Die App läuft dann unter http://localhost:5000.

## Benutzung

1. <Erster Schritt aus User-Perspektive>
2. <Zweiter Schritt>
3. <Ergebnis>

## Projektstruktur

```
<tree-ähnliche Übersicht der Hauptordner>
```

## Weiterführende Dokumentation

- **Für Claude/AI-Agenten:** siehe `CLAUDE.md`
- **Architektur-Details:** siehe `docs/` (falls vorhanden)
- **Aktive Pläne und Research:** `.schrammns_workflow/`
- **Issue-Tracker:** `bd ready` / `bd list --status=open`

## Lizenz / Autor

<falls gewollt>
```

## Regeln

- **Keine Buzzwords**, keine "enterprise-grade", keine "blazingly fast".
- **Befehle 1:1 kopierbar** – wenn der neue Kollege sie markiert und in sein Terminal wirft, sollen sie funktionieren.
- **Knapp halten** – lange READMEs werden nicht gelesen. Alles Tiefere gehört in `docs/`.
- **Keine Doppelungen** mit CLAUDE.md – README ist für Menschen, CLAUDE.md ist für AI + technische Details.
- **Aktuell halten** – der Wachwechsel-Skill prüft das bei jeder Übergabe.

## Anti-Pattern

Ein typisches schlechtes README sieht so aus:

```markdown
# Projekt

Ein Projekt für Fitness-Tracking.

## Installation

`pip install -r requirements.txt`

## Lizenz

MIT
```

Das ist nicht falsch, aber hilft keinem neuen Kollegen. Setup-Kontext fehlt, Benutzung fehlt, Struktur fehlt. Das Gerüst oben verlangt minimal mehr – und liefert 10× mehr Nutzen.
