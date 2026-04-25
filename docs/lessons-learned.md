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

### 2026-04-24: Stumme Sicherheitslücke – TypeDecorator definiert aber nicht gebunden

**Erkenntnis:** `_fernet_field()` war in `connector.py` definiert und korrekt implementiert, aber `credentials` nutzte `String(2048)` – der Decorator wurde nie an die Column gebunden. Credentials wurden unverschlüsselt gespeichert, ohne Fehler, ohne Test-Failure. Erst ein Code-Review beim Schreiben der Connector-Tests deckte das auf.

**Warum relevant:** TypeDecorator-Verschlüsselung ist keine Magie – sie muss explizit in `mapped_column(...)` eingetragen sein. Fehlt sie, speichert SQLAlchemy still Klartext. Tests prüfen typischerweise das Verhalten, nicht ob eine Column den richtigen Typ hat.

**Wie vermeiden:** Bei Security-relevanten Feldern immer prüfen: steht der TypeDecorator tatsächlich in `mapped_column(...)`? `grep -n "mapped_column" app/models/` reicht als Schnellcheck.

**Quelle:** Wachwechsel #3, 2026-04-24. Fix in Commit `899d5db`.

---

### 2026-04-24: FernetField Lazy-Init – kein App-Context bei Model-Definition

**Erkenntnis:** `FernetField.__init__` mit direktem `Fernet(derive_fernet_key(secret_key))`-Aufruf funktioniert nicht ohne App-Context. SQLAlchemy-Models werden beim Import initialisiert, `current_app` ist dort nicht verfügbar. Lösung: `secret_key` optional machen, `_get_fernet()` lazy aus `current_app.config` lesen.

**Warum relevant:** Der `TypeDecorator`-Ansatz ist korrekt – aber der `secret_key` darf erst beim ersten echten DB-Zugriff (innerhalb eines Request-Contexts) gelesen werden.

**Wo sichtbar:** `app/utils/crypto.py` → `FernetField._get_fernet()`, `app/models/connector.py` → `_JsonFernetField()`

**Quelle:** Commit `899d5db`, Wachwechsel #3 2026-04-24.

---

## Konfiguration & Infrastruktur

### 2026-04-24: Env-Var-Name stumm ignoriert – Fallback greift immer

**Erkenntnis:** `config.py` las `GARMINTOKENS`, alle anderen Stellen (README, CLAUDE.md, Tests) nutzten `GARMIN_TOKEN_DIR`. Wer den dokumentierten Namen setzte, hatte ihn stillschweigend ignoriert – der Fallback `~/.garminconnect` griff immer, ohne Fehler oder Warnung.

**Warum relevant:** Falsche Env-Var-Namen sind schwer zu debuggen: Tests bleiben grün (Fallback funktioniert), Deployment-Probleme treten erst in Produktion auf wenn der Fallback-Pfad nicht existiert.

**Wie vermeiden:** `/doc-sync-check` nach Config-Änderungen ausführen. Env-Var-Namen in `config.py`, README, `.env.example` und Tests müssen identisch sein.

**Quelle:** Wachwechsel #4, 2026-04-24. Fix in Commit `9811fae`.

---

### 2026-04-24: SRI-Hash-Mismatch blockt gesamtes Frontend-JavaScript

**Erkenntnis:** Ein Zeichen Unterschied im Bootstrap SRI-Hash (`Xc4s9b` statt `Xc5s9f`) in `base.html` ließ den Browser das gesamte JS-Bundle blockieren. Unit-Tests blieben vollständig grün. Erst der Playwright-Smoke-Test deckte den Console-Error auf.

**Warum relevant:** SRI-Hashes können bei CDN-Versionsänderungen oder Tippfehlern bei manueller Einbindung stillschweigend falsch sein. Der Fehler ist nicht im Code sichtbar – nur im Browser.

**Wie vermeiden:** Bootstrap-CDN-Links immer von `getbootstrap.com/docs/x.y/getting-started/introduction/` kopieren, nie manuell tippen. Hash per `curl ... | openssl dgst -sha384 -binary | openssl base64 -A` verifizieren. Playwright-Smoke-Test auf Console-Errors prüfen.

**Quelle:** Wachwechsel #4, 2026-04-24. Fix in Commit `92eab14`.

---

## Konfiguration & Infrastruktur (Fortsetzung)

### 2026-04-24: python-dotenv Import-Order – load_dotenv() vor App-Import

**Erkenntnis:** `load_dotenv()` muss in `run.py` **vor** `from app import create_app` stehen. `Config.SECRET_KEY = os.environ.get("SECRET_KEY")` wird beim Klassen-Import ausgewertet – nicht erst bei `create_app()`. Steht `load_dotenv()` danach, erhält CSRF-Middleware `None` als Key und wirft `RuntimeError: The session is unavailable because no secret key was set` beim ersten Request, obwohl `.env` korrekt befüllt ist.

**Warum relevant:** Der Fehler tritt erst zur Laufzeit auf, nicht beim Start des Servers. Tests laufen durch (Fixture setzt den Key direkt). Nur im Browser sichtbar.

**Wie vermeiden:** Reihenfolge in `run.py` ist fest: `load_dotenv()` → dann alle App-Imports.

**Wo sichtbar:** `run.py` Zeile 5 (`load_dotenv()`) muss vor Zeile 7 (`from app import create_app`) stehen.

**Quelle:** Wachwechsel #5, 2026-04-24. Fix in Commit `09c9dc0`.

---

## Security: Fernet-Credentials

### 2026-04-26: Fernet-Token-Mismatch bei SECRET_KEY-Wechsel

**Erkenntnis:** Wechselt der `SECRET_KEY` (oder lief `load_dotenv()` beim Speichern zu spät), ist der abgeleitete Fernet-Key ein anderer als beim Lesen. Die DB-Zeile in `connector_credentials` ist dann nicht mehr entschlüsselbar → `cryptography.fernet.InvalidToken` beim ersten Request nach Login.

**Warum relevant:** Der Fehler tritt erst nach dem Login auf (nicht beim Server-Start), ist ohne Kenntnis der HKDF-Ableitung schwer zu diagnostizieren, und sieht für den User wie ein App-Absturz aus.

**Wie lösen:** `sqlite3 instance/sport-challenge.db "DELETE FROM connector_credentials;"` + Connector neu verbinden. Keine Daten gehen verloren (Aktivitäten werden live von Garmin abgerufen).

**Wie vermeiden:** `SECRET_KEY` nie wechseln, wenn Credentials in der DB liegen. Vor Key-Rotation alle `connector_credentials`-Zeilen exportieren, neu verschlüsseln und re-importieren.

**Wo sichtbar:** `app/utils/crypto.py` → `FernetField.process_result_value()`, `app/models/connector.py` → `_JsonFernetField`

**Quelle:** Session 2026-04-26, Diagnose nach Fernet-Fehler nach Datenbankproblem.

---

## Tooling: Playwright-Test-Agents

### 2026-04-26: Playwright-Agent legt echte User in Produktions-DB an

**Erkenntnis:** Ein Haiku-Playwright-Agent zum UI-Test hat `testuser@localhost.test` in der laufenden SQLite-DB registriert und 4 Fehlversuche auf den Admin-Account hinterlassen. Der Agent war angewiesen, nur zu testen – aber der Registrierungsflow war für ihn erreichbar.

**Warum relevant:** Testdaten in der Produktions-DB können den Login-Lockout-Zähler verfälschen und hinterlassen unapproved User, die den Admin-Überblick stören.

**Wie vermeiden:** Playwright-Test-Agents explizit anweisen: „Lege KEINE neuen User an". Alternativ: Tests immer gegen einen separaten Testserver mit Wegwerf-DB (via `FLASK_TESTING=1` + In-Memory-SQLite). Cleanup nach jedem Playwright-Test via `DELETE FROM users WHERE email LIKE '%test%'`.

**Wo sichtbar:** `app/routes/auth.py` → `register()` – kein Guard gegen Playwright-Agents.

**Quelle:** Session 2026-04-26, Wachwechsel #6.

---

## Externe APIs: Garmin Connect (Fortsetzung)

### 2026-04-24: garminconnect In-Memory-Token-API – kein Disk-Pfad für Reconnect

**Erkenntnis:** `garminconnect` speichert Tokens in Memory als JSON-String (`client.dumps()`). Für den Reconnect reicht `Garmin().login(tokenstore=token_json)` – Strings >512 Zeichen werden von der Library automatisch als Inline-Token-Daten erkannt (kein Pfad nötig). Nur der **Erstlogin** braucht ein Verzeichnis für die OAuth-Session-Dateien; dieses wird via `tempfile.mkdtemp()` angelegt und im `finally`-Block bereinigt.

**Warum relevant:** Tokens mussten bisher als Dateien auf Disk liegen (Sicherheitsrisiko bei Multi-User). Mit der In-Memory-API können sie Fernet-verschlüsselt in der Datenbank gespeichert werden – keine Disk-Isolation pro User nötig.

**Wo sichtbar:** `app/garmin/client.py` – `login()` nutzt `tempfile.mkdtemp()` + `finally: shutil.rmtree()`, `reconnect()` nutzt `Garmin().login(tokenstore=token_json)`. `app/connectors/garmin.py` – `credentials["_garmin_tokens"]` enthält den Token-String.

**Quelle:** Wachwechsel #5, 2026-04-24. Umgesetzt in I-01 bis I-06 (Commits `12cc765`–`e5016b2`).
