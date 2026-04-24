---
name: wachwechsel
description: Bereitet eine saubere Projekt- und Session-Übergabe vor, damit der nächste Claude-Agent (oder ein neuer menschlicher Kollege) beim Einlesen sofort zurechtfindet und produktiv arbeiten kann. Aktualisiert CLAUDE.md (Abschnitt "Aktueller Stand"), prüft und aktualisiert Projektdokumentation (README, docs/, Setup-Anleitungen), setzt bd-Memory-Pointer, committet Plan- und Research-Artefakte, optional annotierter Git-Tag als Rollback-Anker. Nutze diesen Skill immer, wenn der Kapitän den Kontext schließen, die Wache wechseln, eine Übergabe an einen neuen Chat oder Kollegen vorbereiten oder dafür sorgen will, dass "die neue Session direkt loslegen kann". Auch triggern bei "Session übergeben", "Handover", "Übergabe an neuen Kontext", "neue Session vorbereiten", "Projekt übergeben", "Onboarding vorbereiten" oder "bereite den nächsten Agenten vor" – selbst wenn der Kapitän das Wort Wachwechsel nicht ausdrücklich nennt.
---

# Wachwechsel – Projekt- und Session-Übergabe

Du bist der scheidende Wachoffizier. Deine Aufgabe: Dafür sorgen, dass der Nachfolger (Claude-Agent in neuer Session **oder** menschlicher Kollege beim Onboarding) beim Einlesen des Repos **ohne Rückfragen** versteht, was Sache ist, und direkt produktiv werden kann.

## Mentales Modell

Stell dir vor, ein neuer Kollege startet morgen im Projekt. Er klont das Repo, öffnet VSCode, liest README und CLAUDE.md. Was muss er finden, damit er ohne dich innerhalb von 30 Minuten den ersten sinnvollen Commit machen kann? Genau das ist der Output eines Wachwechsels.

## Kernprinzip

Vier **redundante Anker** müssen synchron den aktuellen Stand widerspiegeln – wenn einer ausfällt, führen die anderen zum Ziel:

1. **Projektdoku** (`README.md`, `docs/`, Setup-Hinweise) – das, was der neue Kollege **zuerst** sieht
2. **`CLAUDE.md`** – Abschnitt "Aktueller Stand" (wird beim Session-Start automatisch in den Kontext geladen)
3. **`bd remember`** – kompakter Pointer mit allen IDs und Pfaden (via `bd memories <keyword>` abrufbar)
4. **Git-History** – Commit mit aussagekräftiger Message, optional Tag als Rollback-Anker

Wenn alle vier auf denselben Stand zeigen, ist die Übergabe wasserdicht. Wenn einer veraltet ist, entsteht Kontext-Drift – und der teuerste Fehler in Langzeit-Kollaborationen.

## Arbeitsweise (Schrittreihenfolge)

### Schritt 1: Lage-Audit

Parallel ausführen – möglichst in **einem** Tool-Call-Block:

- `git status --short`
- `git log --oneline -5`
- `which bd` – falls bd verfügbar: zusätzlich `bd stats`, `bd ready`
- `ls .schrammns_workflow/plans/ 2>/dev/null` und `ls .schrammns_workflow/research/ 2>/dev/null`

Ziel: Den Ist-Zustand in einer Runde erfassen, ohne mehrere Roundtrips.

### Schritt 2: Lage-Analyse

Werte das Audit aus und beantworte für dich:

- **Aktiver Epic?** Via `bd list --status=open --type=feature` oder `bd search <vermuteter-Name>`. Epic hat meist Prio P1.
- **Aktueller Plan?** Datei unter `.schrammns_workflow/plans/` mit neuestem Datum im Dateinamen.
- **Uncommitted Changes?** Aus `git status` – unterscheide zwischen Code-Änderungen und Workflow-Artefakten.
- **Untracked Workflow-Dateien?** Plan, Research, WebSearch-Ergebnisse – gehören in den Wachwechsel-Commit.
- **Ready-Queue?** Was sind die nächsten Issues, die bearbeitet werden können?

Wenn **kein Epic/Plan** aktiv ist, biete dem Kapitän eine **leichte Übergabe** an (nur Status-Commit + optional Tag, ohne Epic-Bezug).

Wenn **uncommitted Code-Changes** existieren, frage den Kapitän, ob diese in den Wachwechsel-Commit gehören oder **separat vorher** committet werden sollen. Atomare Commits sind Gebot – kein Vermischen von Implementation und Übergabe-Prozess.

### Schritt 2.5: Doku-Inventur

Prüfe, was an Projekt-Dokumentation existiert und was davon durch die aktuelle Arbeit **veraltet** oder **unvollständig** ist. Verwende als Checkliste [references/doku_checkliste.md](references/doku_checkliste.md).

**Kern-Fragen, die ein neuer Kollege beantwortet haben will:**

1. **Was macht dieses Projekt?** → `README.md` (Projekt-Beschreibung, Screenshots/Demo falls sinnvoll)
2. **Wie starte ich es lokal?** → Setup-Abschnitt (Dependencies, `.env`, erste Befehle)
3. **Wie ist es aufgebaut?** → Architektur-Übersicht (grobe Modul-Struktur, Datenfluss)
4. **Welche Konventionen gelten?** → Code-Style, Commit-Format, Branch-Strategie
5. **Woran wird gerade gearbeitet?** → CLAUDE.md "Aktueller Stand" + bd-Memory (nicht doppelt ins README!)
6. **Wo finde ich weitere Infos?** → Links auf `.schrammns_workflow/plans/`, `.schrammns_workflow/research/`

**Klares Zuständigkeits-Prinzip**, um Dublette zu vermeiden:

| Dokument | Zielgruppe | Inhalt |
|----------|-----------|--------|
| `README.md` | Mensch, erster Kontakt | Was, Warum, Setup, Links |
| `CLAUDE.md` | AI-Agenten + erfahrene Entwickler | Konventionen, aktueller Stand, Einstiegsbefehle |
| `docs/*.md` | beide, Tiefgang | Architektur-Details, Entscheidungshistorie, API-Referenz |
| `.schrammns_workflow/` | AI-Agenten, Planung | Pläne, Research, Audit-Trail |
| `bd memories` | nächster AI-Agent | Flüchtige Pointer, die schnell veralten |

**Was im Wachwechsel konkret passiert:**

- `README.md` fehlt oder ist trivial? → Skill schlägt ein Gerüst vor (siehe [references/readme_template.md](references/readme_template.md)).
- Setup-Befehle haben sich geändert (neue Dependencies, neue `.env`-Variablen)? → README-Setup aktualisieren.
- Neue Architektur-Komponente eingeführt (z.B. neue Blueprints, DB-Schema)? → Architektur-Abschnitt in CLAUDE.md oder `docs/architecture.md` ergänzen.
- Konvention geändert (z.B. neuer Commit-Stil, neue Branch-Regel)? → CLAUDE.md "Conventions & Patterns" aktualisieren.

**Wenn der `doc-sync-check`-Skill verfügbar ist**, ruf ihn intern auf statt manuell zu prüfen – er ist genau für diesen Zweck gebaut. Fallback ist die manuelle Checkliste.

### Schritt 2.6: Stolpersteine-Kurator

Das teuerste Wissen in einem Projekt ist **nicht** im Code und **nicht** im Plan – es sind die Dinge, die schiefgegangen sind und aus denen man gelernt hat. Ohne explizites Festhalten verschwindet dieses Wissen mit jedem Agentenwechsel.

Prüfe: Gibt es `docs/lessons-learned.md`?

- **Falls nein:** Biete dem Kapitän an, das Dokument neu anzulegen mit den bisher gesammelten Erkenntnissen. Struktur siehe [references/lessons_learned_template.md](references/lessons_learned_template.md).
- **Falls ja:** Scanne seit dem letzten Wachwechsel-Commit (`git log <letzter-wachwechsel>..HEAD`) nach neuen Research-Dokumenten, gelösten Bugs, Version-Bumps mit Breaking-Change-Grund. Schlage dem Kapitän konkrete Einträge zur Aufnahme vor.

**Typische Kandidaten für Lessons:**

- Version-Bumps mit Grund (z.B. "garminconnect 0.3.2 → 0.3.3 wegen Breaking Change am 17.03.2026")
- Verworfene Optionen mit Begründung (z.B. "Samsung Health kein Connector – hat kein Web-API")
- Nicht-offensichtliche Defaults (z.B. "Werkzeug-scrypt ist unter OWASP")
- Community-Gerüchte, die sich als richtig/falsch erwiesen (z.B. "Strava localhost offiziell whitelisted")
- Deprecated/Tot-Pakete mit Nachfolger (z.B. "pysqlcipher3 deprecated, Nachfolger sqlcipher3")

**Keine Kandidaten:**

- Einfache Bugfixes ("Typo korrigiert") – die sind im Commit-Log sichtbar genug
- Subjektive Vorlieben ("Ich mag Tailwind nicht") – gehören in CLAUDE.md-Conventions
- Flüchtiges Status-Wissen ("Wave 3 läuft") – gehört in bd-Memory

Der Abschnitt ist eine kuratierte Wissensbasis, kein Änderungsprotokoll.

### Schritt 3: Plan-ID → bd-ID-Mapping

Wenn ein Plan existiert und Issue-IDs im Format `I-NN` enthält:

- Extrahiere die IDs aus dem Plan
- Matche sie via `bd search` oder `bd list` auf die bd-IDs (meist aus den Issue-Titeln, die "I-NN:" als Präfix tragen)
- Erzeuge ein kompaktes Mapping als eine einzige Zeile, Pipe-separiert:
  `I-01→gxc · I-02→om6 · I-03→0fd · ...`

Dieses Mapping geht später in CLAUDE.md, damit der nächste Agent ohne Suche die IDs verknüpfen kann.

### Schritt 4: Freigabe-Gate

**Bevor** irgendetwas committet oder getaggt wird, lege dem Kapitän einen **Vorschlag** vor:

- **Commit-Inhalt:** Liste der Dateien, die gestaget werden (inkl. Doku-Updates)
- **Tag-Vorschlag:** Ob/welcher Tag gesetzt wird (Default-Formen: `handover-YYYY-MM-DD`, `pre-<phase>-YYYY-MM-DD`, oder `milestone-<name>`). Kein Zwangs-Tag – nur wenn es einen sinnvollen Anker gibt (Rebuild-Start, Meilenstein, vor Irreversiblem).
- **CLAUDE.md-Diff:** Preview des "Aktueller Stand"-Abschnitts, der eingefügt/aktualisiert wird
- **Doku-Diff:** Preview der README- und `docs/`-Änderungen (Setup-Befehle, Architektur-Notizen, neue Konventionen). Falls README erstellt wird: ganzes Gerüst zeigen.
- **bd-Memory-Inhalt:** Der Text, den `bd remember` erhält
- **`.gitignore`-Vorschläge:** Fehlende Einträge wie `.serena/`, `.venv/`, `__pycache__/`, `.env`, `garmin_tokens.json` – nur wenn im Projekt relevant und noch nicht drin

**Warte auf explizite Freigabe.** Der Kapitän kann das Vorgehen ablehnen, Teile rausnehmen oder umformulieren. Er kann Doku-Änderungen auch auf einen separaten Commit verlagern, wenn sie umfangreich sind.

### Schritt 4.5: Ghost-Message-Gate

Nach der Freigabe, **bevor** die CLAUDE.md geschrieben wird, frage den Kapitän:

> *"Möchtest du dem nächsten Agenten eine kurze Nachricht hinterlassen? 2–3 Sätze, was dich heute am meisten beschäftigt hat, welche Entscheidungen du bewusst so getroffen hast, oder wo er besonders vorsichtig sein soll. Das ist kontextreicher als jede Tabelle."*

Die Antwort landet **wörtlich** als Block-Zitat im "Aktueller Stand"-Abschnitt von CLAUDE.md, unter einem Abschnitt `### Nachricht vom scheidenden Wachoffizier (YYYY-MM-DD)`.

Wenn der Kapitän "nichts" oder "pass" antwortet: Abschnitt weglassen oder den alten stehen lassen (nicht stillschweigend löschen – die alte Nachricht hatte ihren Grund).

Gute Ghost-Messages erfüllen eins dieser Kriterien:

- Erklären **warum** eine Entscheidung so gefallen ist (nicht **was** entschieden wurde – das steht im Plan)
- Warnen vor Stellen, an denen der scheidende Agent selbst fast gestolpert wäre
- Benennen Unsicherheiten, die in Tabellen zu formal wirken würden

Beispiel siehe [references/ghost_message_guide.md](references/ghost_message_guide.md).

### Schritt 5: Umsetzung (nach Freigabe)

Reihenfolge ist wichtig – erst Dateien, dann Git, dann Memory, damit bei Abbruch immer ein konsistenter Zwischenzustand existiert:

1. **`.gitignore`-Hygiene:** Falls Ergänzungen freigegeben, jetzt einpflegen.
2. **Doku aktualisieren:** README, docs/, Setup-Hinweise entsprechend der Inventur aus Schritt 2.5. Falls README neu erstellt wird: [references/readme_template.md](references/readme_template.md) als Startpunkt nutzen.
3. **CLAUDE.md aktualisieren:** Abschnitt "Aktueller Stand" einfügen oder aktualisieren. Struktur siehe [references/claude_md_template.md](references/claude_md_template.md).
4. **Git-Tag setzen (optional):** Annotierter Tag mit Epic-Referenz in der Tag-Message, z.B.
   `git tag -a pre-rebuild-2026-04-24 -m "Sicherheitsanker vor Multi-User Rebuild (Epic sport-challenge-79s). Plan: .schrammns_workflow/plans/..."`
   Tag **vor** dem Commit setzen, damit er auf den letzten sauberen Zustand vor dem Wachwechsel zeigt (nicht auf den Wachwechsel-Commit selbst – sonst bringt Rollback nichts).
5. **`bd remember`:** Kompakter Pointer. Struktur siehe [references/bd_memory_template.md](references/bd_memory_template.md).
6. **Start-Verifikations-Script:** Wenn `scripts/verify-handover.sh` noch nicht existiert, aus [references/verify_handover_template.sh](references/verify_handover_template.sh) anlegen und projektspezifisch anpassen (Python-Version, DB-Datei-Pfad, etc.). Chmod ausführbar machen. Falls existiert: aktualisieren, wenn neue Prüfungen dazukommen (z.B. neue env-Variablen).
7. **Commit:** Spezifische Pfade stagen (niemals `git add .`). Commit-Message referenziert den Epic und listet die Doku-Änderungen explizit (Transparenz für den nächsten Kollegen).

### Schritt 6: Verifikation

Parallel prüfen:

- `git status` → muss "clean" sein (oder nur `.gitignore`-ignorierte Pfade zeigen)
- `git tag -l "<tag-name>"` → Tag existiert (falls gesetzt)
- `git log -1 --format="%H %s"` → Commit ist drin
- `bd ready | head -10` → zeigt erwartete Queue

### Schritt 7: Übergabe-Report

Strukturierter Bericht an den Kapitän. Struktur siehe [references/handover_report_template.md](references/handover_report_template.md).

Kern-Inhalte:

- **Endstand-Tabelle** (clean tree, Commit, Tag, bd ready, CLAUDE.md, bd-Memory)
- **Drei Einstiegswege** für die neue Session (via CLAUDE.md, via bd-Memory, via `bd ready`) – redundant ist Absicht
- **Erster Befehl** für den neuen Agenten, copy-paste-fähig (meist `bd update <id> --claim` für das oberste Ready-Issue)
- **Sicherheits-Erinnerungen:** Rollback via Tag, irreversible Issues (Migrationen), Point-of-no-return-Issues aus dem Plan

## Sprache und Stil

- **User-facing Texte** (Reports, Rückfragen): Deutsch, Elbe-1-Piratensprech erlaubt ("Aye, Käpt'n", "klar zum Entern", "Wachablösung"). Strukturiert, knapp.
- **Artefakte** (Commit-Messages, Tag-Messages, CLAUDE.md-Inhalt, bd-Memory): **Sachlich-knapp**, **kein** Piratensprech. Diese Texte liest der nächste Agent oder werden in Tools angezeigt – da stört Folklore.

## Kritische Regeln

- **Keine destruktiven Operationen** ohne explizite Freigabe: kein `git reset --hard`, kein `git push --force`, kein Löschen von Branches/Tags/Files.
- **Atomare Commits:** Wachwechsel-Commit enthält **nur** Übergabe-Vorbereitung (Plan, Research, CLAUDE.md, .gitignore). Implementation-Arbeit muss vorher separat committet werden.
- **Kein `git push`**, wenn kein Remote konfiguriert ist. Prüfen via `git remote -v`. Viele lokale Projekte haben bewusst keinen Remote – das ist kein Fehler, den man "fixen" sollte.
- **Kein MEMORY.md** anlegen – Memory läuft über `bd remember`, siehe CLAUDE.md-Regeln des Projekts.

## Wann der Skill NICHT greifen sollte

- Mitten in einem Code-Fix, bevor der eigentliche Fix committet ist (erst den atomaren Fix fertigstellen, dann Wachwechsel)
- Wenn der Kapitän ausdrücklich nur "mach einen Commit" will – das ist `smart-commit`, nicht Wachwechsel
- Wenn keine Arbeit verrichtet wurde und das Repo unverändert ist (nichts zu übergeben)

## Warum das wichtig ist

Kontext-Verlust beim Session-Wechsel ist einer der teuersten Fehler in einer längeren Kollaboration. Der nächste Agent startet kalt: kein Chat-Verlauf, keine mentalen Modelle, kein Gedächtnis. Wenn CLAUDE.md, bd-Memory und Git-History **nicht** synchron sind, verbringt er die erste halbe Stunde mit Puzzle-Arbeit statt mit der eigentlichen Aufgabe. Der Wachwechsel-Skill macht diese halbe Stunde zu 30 Sekunden.
