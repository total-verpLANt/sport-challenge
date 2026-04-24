# Lessons Learned – Sport Challenge

Dieses Dokument sammelt Erkenntnisse aus der Projektarbeit, die aus dem Code nicht direkt ablesbar sind. Pro Eintrag: **was** wir gelernt haben, **warum** es relevant ist, und **wo** das im Projekt Konsequenzen hat.

Aktualisiert bei jedem Wachwechsel (Skill `/wachwechsel`). Alte Einträge nicht löschen – nur als "überholt" markieren, falls sich die Lage ändert.

---

## Externe APIs: Garmin Connect

### 2026-04-24: garminconnect 0.3.2 → 0.3.3 wegen Breaking Change

**Erkenntnis:** Garmin hat am 17.03.2026 eine Breaking Change eingeführt, die `garminconnect 0.3.2` inkompatibel macht. Die Community hat das in Issue #332 des Python-Clients dokumentiert und mit 0.3.3 gefixt.

**Warum relevant:** Wer von einem älteren Checkout startet oder requirements.txt zurücksetzt, hat sofort kaputte Garmin-Aufrufe – ohne offensichtliche Fehlermeldung.

**Wo sichtbar:** `requirements.txt` – Pin auf `garminconnect==0.3.3` ist Pflicht, kein `>=`.

**Quelle:** [cyberjunky/python-garminconnect Issue #332](https://github.com/cyberjunky/python-garminconnect/issues/332), Commit `d3ad8b5`

---

## Tooling: Alembic + SQLAlchemy

### 2026-04-24: db.create_all() im Test kontaminiert flask db migrate

**Erkenntnis:** Wenn `db.create_all()` (z.B. in einem manuellen Test oder Smoke-Test) alle Modelle in die SQLite-DB schreibt, erkennt Alembic beim nächsten `flask db migrate` die Tabellen als "bereits vorhanden" und generiert dafür DROP-Statements oder ignoriert sie falsch.

**Warum relevant:** Eine so generierte Migration löscht Tabellen (`op.drop_table('connector_credentials')` statt sie anzulegen) – ohne Warnung beim Generieren, erst beim Upgrade.

**Wie vermeiden:** Vor `flask db migrate` immer `rm -f instance/*.db` ausführen. Migrations ausschließlich auf sauberem DB-Stand generieren, nie nach manuellem `create_all()`.

**Wo sichtbar:** `migrations/versions/` – geschah bei I-10, falsche Migration musste gelöscht und neu generiert werden.

**Quelle:** Commit `bab2f6c`, interner Fehler beim Wachwechsel 2026-04-24

---

## Tooling: Claude Sub-Agents

### 2026-04-24: Sub-Agents haben keine Bash-Berechtigung ohne explizite Freigabe

**Erkenntnis:** Wenn parallele Sub-Agents gestartet werden, erben sie **nicht** automatisch die Bash-Erlaubnis der übergeordneten Session. Sie brechen dann ohne Ergebnis ab oder fragen nach manueller Freigabe.

**Warum relevant:** Der Effizienzgewinn paralleler Agents entfällt komplett, wenn jeder Agent manuell freigegeben werden muss. Alle Wave-1-Issues mussten deshalb direkt im Hauptagent abgearbeitet werden.

**Wie lösen:** Skill `/fewer-permission-prompts` ausführen, um Bash-Calls in `.claude/settings.json` zu allowlisten, bevor Parallel-Agent-Arbeit geplant wird.

**Quelle:** Wave-1-Session 2026-04-24

---

## Security: Passwort-Hashing

### 2026-04-24: Werkzeug-scrypt-Default liegt unter OWASP-Empfehlung

**Erkenntnis:** `generate_password_hash(..., method="scrypt")` aus Werkzeug nutzt Defaults, die nicht zwingend OWASP-konform sind (N=32768, r=8, p=1 – OWASP empfiehlt höhere Werte für 2025+). Der Feinschliff ist als separates Issue `gvl` erfasst.

**Warum relevant:** Wer `set_password` nutzt, ohne `gvl` umgesetzt zu haben, erzeugt ggf. zu schwache Hashes. Die Hashes sind korrekt (Roundtrip funktioniert), aber möglicherweise nicht OWASP-2025-konform.

**Wo sichtbar:** `app/models/user.py` → `set_password()`, Issue `sport-challenge-gvl`

**Quelle:** Issue `sport-challenge-gvl`, `.schrammns_workflow/research/2026-04-23-architektur-best-practices-rebuild-sport-challenge-flask.md`

---

## Tooling: Python venv

### 2026-04-24: venv nach Projektumzug mit gebrochenen Shebangs

**Erkenntnis:** Ein `python3 -m venv .venv` (oder `uv venv`) speichert den absoluten Pfad des Projekts in die Shebangs aller Scripts unter `.venv/bin/`. Nach einem Projektumzug (Ordner umbenennen oder verschieben) sind diese Shebangs ungültig – alle `.venv/bin/*`-Binaries werfen sofort `bad interpreter: no such file or directory`.

**Warum relevant:** Das `.venv` erscheint vorhanden (`ls .venv/` zeigt Dateien), ist aber komplett unbrauchbar. Die Fehlermeldung ist irreführend – man sucht zunächst nach falschen Paketen statt nach dem Pfad.

**Wie lösen:** `uv venv .venv --clear --python 3.14 && uv pip install -r requirements.txt`. Mit `uv` gebaute venvs nutzen symlink-basierte Interpreter – nach dem nächsten Umzug kein erneutes `--clear` nötig, solange Python unter demselben Homebrew-Pfad liegt.

**Wie vermeiden:** Projekt-Verzeichnis nicht umbenennen/verschieben. Falls doch: venv immer neu aufbauen, nie kopieren.

**Wo sichtbar:** `.venv/bin/` – Shebang-Zeile der Scripts (`head -1 .venv/bin/flask`)

**Quelle:** Session 2026-04-24, Wachwechsel #2

---

## Architektur-Entscheidungen

### 2026-04-24: FernetField als SQLAlchemy-TypeDecorator (kein Column-Event)

**Erkenntnis:** Die Fernet-Verschlüsselung für `ConnectorCredential.credentials` läuft als `TypeDecorator` (transparente Ver-/Entschlüsselung beim DB-Zugriff), nicht als SQLAlchemy-Event-Listener oder Property.

**Warum relevant:** Der `TypeDecorator`-Ansatz erfordert den `SECRET_KEY` zur Instanzierungszeit des Feldtyps, was im App-Context passieren muss. Wer das Modell außerhalb eines App-Contexts importiert, bekommt keinen Fehler beim Import – aber einen beim ersten DB-Zugriff.

**Wo sichtbar:** `app/utils/crypto.py` → `FernetField`, `app/models/connector.py` → `_JsonFernetField`

**Quelle:** Commit `99fe575`, `16ac948`
