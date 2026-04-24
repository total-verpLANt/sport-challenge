# Lessons Learned – Struktur für `docs/lessons-learned.md`

Das Dokument ist eine **kuratierte Wissensbasis** – nicht das Änderungsprotokoll. Es soll einen neuen Kollegen (Mensch oder AI) vor bekannten Fallstricken warnen und Entscheidungshintergründe liefern, die aus dem Code nicht ablesbar sind.

## Struktur

```markdown
# Lessons Learned – <Projekt-Name>

Dieses Dokument sammelt Erkenntnisse aus der Projektarbeit, die aus dem Code nicht direkt ablesbar sind. Pro Eintrag: **was** wir gelernt haben, **warum** es relevant ist, und **wo** das im Projekt Konsequenzen hat.

Aktualisiert bei jedem Wachwechsel (Skill `/wachwechsel`). Alter Einträge nicht löschen – nur als "überholt" markieren, falls sich die Lage ändert.

---

## <Thema 1 – z.B. "Externe APIs: Garmin Connect">

### YYYY-MM-DD: <Kurz-Titel der Lesson>

**Erkenntnis:** <Was ist der Sachverhalt?>

**Warum relevant:** <Welche Konsequenz hat das für die Entwicklung?>

**Wo sichtbar:** <Konkrete Datei, Config, Issue, Plan-Sektion>

**Quelle:** <Link, Research-Datei, Commit-Hash, Issue-URL>

---

### YYYY-MM-DD: <nächste Lesson>

...

## <Thema 2 – z.B. "Security: Password Hashing">

...
```

## Themen-Beispiele (projektabhängig)

- Externe APIs (Garmin, Strava, Komoot, etc.)
- Security (Hashing, Encryption, CSRF, Rate-Limits)
- Dependencies (deprecated, Nachfolger, Version-Pins)
- Architektur-Entscheidungen (was wir verworfen haben)
- Performance-Beobachtungen
- Plattform-Quirks (macOS/Linux, Python-Versionen)

## Regeln für gute Einträge

1. **Datum immer voranstellen** – damit spätere Leser sehen, ob der Eintrag noch aktuell ist
2. **Quelle verlinken** – idealerweise Primärquelle (GitHub-Issue, offizielle Doku), nicht nur "ich habe gehört"
3. **Kurz halten** – 4–6 Zeilen pro Eintrag. Tiefere Analyse gehört in `.schrammns_workflow/research/`
4. **Nicht doppeln** – wenn es schon in CLAUDE.md "Conventions" oder im Plan als Design Decision steht, nicht erneut abschreiben. Nur verlinken.
5. **Überholte Einträge markieren**, nicht löschen:
   ```markdown
   > ⚠️ **Überholt (YYYY-MM-DD):** Diese Erkenntnis galt für Version X. Seit Y stimmt sie nicht mehr – siehe [neuer Eintrag].
   ```
   Das Wissen "das war mal so" ist oft selbst wertvoll.

## Was NICHT reingehört

- Trivialität ("Typo in Variable X" – im Commit-Log)
- Subjektive Vorlieben ("Ich mag keine Emoji" – in CLAUDE.md)
- Flüchtiges Status-Wissen ("Wave 3 läuft" – in bd-Memory)
- Vollständige Research-Reports – nur das Fazit, nicht die Analyse

## Initial-Befüllung durch den Wachwechsel

Wenn das Dokument neu angelegt wird, schlägt der Wachwechsel-Skill vor, diese Quellen zu scannen und Kandidaten zu extrahieren:

- `.schrammns_workflow/research/*.md` – Gaps, Assumptions, Recommendations
- Git-History: Commits mit "fix:" / "chore: upgrade" und deren Messages
- Abgelehnte Design-Decisions aus Plan-Dokumenten

Der Kapitän wählt aus den Kandidaten, was in die Lessons-Liste soll.
