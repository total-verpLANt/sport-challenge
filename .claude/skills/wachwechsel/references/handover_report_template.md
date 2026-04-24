# Übergabe-Report – Format

Der Abschluss-Bericht, den der Wachwechsel-Skill an den Kapitän ausgibt. Piraten-Deutsch erlaubt.

## Struktur

```markdown
## 🏴‍☠️ Übergabe abgeschlossen, Käpt'n

### Endstand

| Check | Status |
|-------|--------|
| Git Working Tree | ✅ clean |
| Letzter Commit | `<hash>` <subject> |
| Pre-Rebuild-Tag | ✅ `<tag>` auf `<hash>` (oder: – nicht gesetzt) |
| `bd ready` | ✅ <N> Issues bereit |
| CLAUDE.md | ✅ Abschnitt "Aktueller Stand" aktualisiert |
| README.md | ✅ Setup aktuell / ⚠️ Gerüst erstellt / – unverändert |
| docs/ | ✅ aktualisiert / – nicht betroffen |
| `.env.example` | ✅ synchron mit Code / ⚠️ ergänzt um X, Y |
| bd-Memory | ✅ Key: `<key-prefix>` |
| `.gitignore` | ✅ (oder: ergänzt um X, Y) |

### Einstiegsweg für die neue Session

Drei redundante Pfade – falls einer nicht greift, führen die anderen zum Ziel:

1. **Via CLAUDE.md** – wird automatisch geladen, Abschnitt "Aktueller Stand"
2. **Via bd-Memory** – `bd memories <keyword>` liefert Epic-ID, Plan-Pfad, nächste Issues
3. **Via `bd ready`** – zeigt die offenen Wave-<N>-Tickets direkt

### Erster Befehl für die neue Session

```bash
bd update <erstes-ready-issue> --claim   # Nächstes Issue klammern
bd show <erstes-ready-issue>              # Details
# Dann atomarer Fix nach Pflicht-Reihenfolge aus CLAUDE.md
```

### Sicherheits-Erinnerung

- ⚠️ **Rollback-Pfad**: `git reset --hard <tag>` (falls Tag gesetzt)
- ⚠️ **Irreversible Issues im Plan**: <Liste aus dem Plan, z.B. Migrationen>
- ⚠️ **Points of no return**: <Liste, z.B. Activities-Refactor>

Alle Flaggen gehisst, Kurs abgesteckt. Die nächste Wache kann direkt entern. 🌊
```

## Regeln

- **Tabelle statt Prosa** für den Endstand – schnell scanbar
- **Konkrete IDs und Pfade** – keine Platzhalter, keine Andeutungen
- **"Erster Befehl" als echten Copy-Paste-Block** – nicht "führe `bd update aus`", sondern den vollständigen Befehl
- **Sicherheits-Erinnerung immer mit dabei** – auch wenn kurz. Der nächste Agent soll wissen, wo die Klippen sind.

## Kürzere Variante (leichte Übergabe)

Wenn kein Epic/Plan aktiv war und nur ein Status-Commit gemacht wurde:

```markdown
## ⚓ Leichte Übergabe, Käpt'n

Stand ist committet (`<hash>`), CLAUDE.md und bd-Memory aktualisiert. Keine offene Epic-Arbeit – die neue Session kann ein neues Vorhaben beginnen via `bd create` oder eigenem Plan.

Letzter Commit: <hash> <subject>
```
