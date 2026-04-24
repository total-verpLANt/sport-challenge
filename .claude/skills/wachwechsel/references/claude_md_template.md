# CLAUDE.md – Abschnitt "Aktueller Stand"

Dieser Abschnitt wird automatisch in den Kontext geladen, wenn eine neue Session startet. Er ist der wichtigste Landeplatz für den nächsten Agenten.

## Platzierung

Nach dem Beads-Integration-Block, **vor** "Build & Test". Wenn der Abschnitt bereits existiert, vollständig ersetzen – nicht anhängen.

## Struktur (Markdown-Template)

```markdown
## Aktueller Stand (YYYY-MM-DD)

**Aktive Arbeit:** <kurze Beschreibung, z.B. "Multi-User Rebuild mit Connector-Architektur">

- **Epic:** `<bd-id>` – <Titel>
- **Plan:** `.schrammns_workflow/plans/<datei>.md` (<N> Issues, <M> Waves)
- **Research:** `.schrammns_workflow/research/<datei>.md`
- **Quellen-Nachweis** (falls vorhanden): `.schrammns_workflow/research/<websearch>.md`
- **Git-Anker:** Tag `<tag-name>` (Rollback via `git reset --hard <tag-name>`)

### Einstieg für neue Sessions

```bash
bd prime                              # Workflow-Kontext
bd memories <keyword>                 # gespeicherter Pointer mit allen IDs
bd ready                              # aktuelle Wave
bd show <erstes-ready-issue>          # Details zum ersten Ticket
```

**Plan-ID → bd-ID Quick-Map:**
`I-01→<id> · I-02→<id> · I-03→<id> · ...`
```

## Regeln für den Inhalt

- **Datum immer aktualisieren** – spiegelt Stand wider, nicht Ersterstellung
- **Epic-ID voll qualifiziert** (z.B. `sport-challenge-79s`, nicht nur `79s`) – damit `bd show` ohne Prefix-Raten funktioniert
- **Plan-Datei mit relativem Pfad** – damit Copy-Paste ins Terminal funktioniert
- **Quick-Map als EINE Zeile** – wenn sie umbricht, ist das OK, aber kein Listen-Format (spart Platz und liest sich schneller)
- **Kein Piratensprech** in diesem Abschnitt – das ist technisches Reference-Material

## Wenn mehrere Epics aktiv sind

Sehr selten, aber möglich. Dann:

```markdown
## Aktueller Stand (YYYY-MM-DD)

**Parallele Arbeit:**

### Epic 1: <Titel>
- **Epic:** `<bd-id>` ... (wie oben)

### Epic 2: <Titel>
- **Epic:** `<bd-id>` ...
```

Der `bd ready`-Einstieg zeigt ohnehin issues aus beiden, also reicht eine gemeinsame "Einstieg"-Sektion am Ende.

## Wenn keine aktive Arbeit läuft

Dann schreibt der Wachwechsel-Skill stattdessen:

```markdown
## Aktueller Stand (YYYY-MM-DD)

Keine aktive Arbeit. Letzter abgeschlossener Meilenstein: <commit-hash> – <message>.

Nächste mögliche Schritte: siehe `bd list --status=open` oder offene Ideen unter `.schrammns_workflow/`.
```
