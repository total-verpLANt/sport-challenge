# Doku-Checkliste für den Wachwechsel

Arbeite diese Liste systematisch ab. Pro Punkt: **prüfen**, dann entscheiden, ob der aktuelle Stand den Punkt erfüllt, oder ob ein Update nötig ist.

## README.md

| Prüfpunkt | Soll-Zustand |
|-----------|--------------|
| **Existiert** | Ja, als `README.md` im Repo-Root |
| **Projekt-Name und Einzeiler-Beschreibung** | In den ersten 5 Zeilen klar erkennbar |
| **Setup-Anleitung** | Kopierbare Befehle für Dependencies, `.env`, erstes Hochfahren |
| **Aktuelle Dependencies** | requirements.txt / package.json / etc. stimmen mit README überein |
| **Dev-Server-Befehl** | Beispiel wie `FLASK_DEBUG=1 python run.py` – aktuelle env-Variablen |
| **Minimaler Beispiel-Flow** | "So benutzt du die App" – 2–4 Schritte, was der User tut |
| **Links auf weiterführende Doku** | CLAUDE.md, docs/, .schrammns_workflow/ |
| **Lizenz / Autor** | Falls gewollt |

**Red Flags:**
- README ist leer oder steht nur "# Projektname"
- Setup-Befehle verweisen auf veraltete Dependencies oder entfernte env-Variablen
- Beschreibung passt nicht mehr zum aktuellen Feature-Stand

## docs/ (falls vorhanden)

| Prüfpunkt | Soll-Zustand |
|-----------|--------------|
| **Architektur-Übersicht** | Grobe Modul-Struktur, Datenfluss – aktuell zum Code |
| **API-Referenz** | Falls das Projekt APIs hat: Endpunkte stimmen mit Code |
| **Entscheidungshistorie** | ADRs oder equivalent, die wichtige Architektur-Entscheidungen festhalten |

Falls `docs/` nicht existiert und das Projekt noch klein ist: OK, kein Zwang. Bei größeren Projekten bei erster Gelegenheit anlegen.

## CLAUDE.md

| Prüfpunkt | Soll-Zustand |
|-----------|--------------|
| **"Aktueller Stand"-Abschnitt** | Aktualisiert via Wachwechsel (siehe [claude_md_template.md](claude_md_template.md)) |
| **"Build & Test"** | Aktuelle Befehle, nicht die von vor 3 Waves |
| **"Architecture Overview"** | Ist- und Ziel-Zustand, wenn im Rebuild |
| **"Conventions & Patterns"** | Commit-Format, Branch-Strategie, atomare Commits, Test-Richtlinien |
| **Beads-Integration** | Bleibt wie sie vom `bd init` gesetzt wurde – nicht modifizieren |

## `.env.example`

| Prüfpunkt | Soll-Zustand |
|-----------|--------------|
| **Alle Variablen dokumentiert**, die der Code liest | grep das Repo nach `os.environ` / `process.env` und vergleiche |
| **Beispielwerte, keine echten Secrets** | `SECRET_KEY=aendere-mich`, nicht der echte Key |
| **Kommentare bei nicht-offensichtlichen Variablen** | z.B. Pfad-Defaults, Format-Hinweise |

Wenn eine Variable im Code eingeführt wurde, aber nicht in `.env.example` dokumentiert ist: Red Flag, ergänzen.

## Changelog / Release-Notes

| Prüfpunkt | Soll-Zustand |
|-----------|--------------|
| **CHANGELOG.md oder äquivalent** | Optional – nur wenn das Projekt Releases hat |
| **Aktueller Eintrag für aktuelle Arbeit** | Ein Satz pro Feature/Fix, Verweise auf Issue-IDs |

Für kleine Hobby-Projekte ohne Release-Rhythmus: ignorieren.

## Entscheidungsgrundlage

Nicht jeder Punkt muss bei jedem Wachwechsel aktualisiert werden. Faustregel:

- **Immer prüfen:** README-Setup-Anleitung (weil sie am schnellsten veraltet)
- **Bei Architektur-Changes:** CLAUDE.md "Architecture Overview" und `docs/`
- **Bei neuen env-Variablen:** README-Setup und `.env.example`
- **Bei Konventions-Änderungen:** CLAUDE.md "Conventions & Patterns"
- **Bei Release-Projekten:** CHANGELOG.md

## Wenn der `doc-sync-check`-Skill verfügbar ist

Direkt aufrufen – er tut genau diese Arbeit und ist wahrscheinlich gründlicher als manuelle Prüfung. Die Ergebnisse fließen in den Freigabe-Vorschlag ein.
