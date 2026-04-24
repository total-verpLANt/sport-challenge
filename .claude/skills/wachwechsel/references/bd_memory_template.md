# bd-Memory – Format des Übergabe-Pointers

`bd remember` speichert einen frei formulierten Text unter einem automatisch generierten Key. Der nächste Agent ruft ihn per `bd memories <keyword>` ab (Suche im Text).

## Key-Strategie

`bd remember` leitet den Key selbst aus dem Text-Anfang ab. Damit Suchen greifen, sollte der erste Satz ein prägnantes Schlagwort enthalten (z.B. den Projekt- oder Epic-Namen).

**Beispiel-Suche:** `bd memories multi-user` findet alles mit "multi-user" im Text.

## Text-Template

```
<Projekt-/Epic-Schlagwort>: <bd-epic-id> (YYYY-MM-DD). Plan-Dokument: .schrammns_workflow/plans/<datei>.md mit <N> Issues in <M> Waves. Research: .schrammns_workflow/research/<datei>.md + .../<websearch>.md. Git-Anker: Tag <tag-name>. Wave 0 bereit zum Start: <issue-1> (<kurzbeschreibung>), <issue-2> (...), <issue-3> (...). Bestehende Issues eingewebt: <id1> (=<I-NN>), <id2> (=<I-NN>). <Zusatzinfos falls relevant, z.B. untracked files, pending decisions>.
```

## Regeln

- **Eine lange Zeile, keine Zeilenumbrüche** – bd speichert das 1:1, und Zeilenumbrüche im Terminal-Rendering variieren.
- **Absolute Fakten, keine Meinungen** – der nächste Agent braucht Pointer, keine Einschätzungen. Die gehören in CLAUDE.md oder den Commit.
- **Max. 500 Zeichen** – drüber wird die Memory-Liste unübersichtlich. Wenn mehr Info nötig ist: auf den Plan verweisen, nicht alles reinkopieren.
- **Deutsch oder Englisch konsistent** – nicht mischen. Bei Elbe-1-Projekt: Deutsch.

## Wann nicht speichern

- Wenn `bd memories <keyword>` bereits einen aktuelleren Eintrag zum selben Thema hat – dann stattdessen den alten löschen (`bd forget <key>`) und neu speichern, oder aktualisieren.
- Wenn die Info bereits in CLAUDE.md steht und sich beide Quellen synchron halten müssen – Memory soll **keine** Dublette sein, sondern ein **kompakter Pointer**, der auf CLAUDE.md und den Plan verweist.

## Mehrere gleichzeitige Memories

Für ein Projekt darf es mehrere Memories geben, z.B.:

- `multi-user-rebuild-epic-...` – aktueller Rebuild
- `garmin-mfa-spike-...` – paralleler Prototyp
- `projekt-conventions-...` – dauerhafte Konventionen

Beim Wachwechsel aktualisiert der Skill nur den **aktuellen Arbeits-Pointer**, nicht alle.
