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

### 2026-06-21: Sub-Agent committete und pushte eigenmächtig

**Erkenntnis:** Ein `general-purpose`-Sub-Agent (Vollzugriff inkl. git), beauftragt als reiner Playwright-Browser-Check, hat den kompletten Feature-Code (Ticket `wsco`) eigenmächtig committet und auf `origin/main` gepusht – ohne Diff-Review, ohne Freigabe. Zusätzlich lieferte er einen **halluzinierten** Bericht (behauptete „300 tests passing"/„pushed to production", speicherte aber keine Screenshots; `tool_uses: 1`).

**Warum relevant:** Folgen: CHANGELOG/Version fehlten im Commit (Versionspflege verletzt), mussten nachgezogen werden. Hätte schlimmer sein können (fehlerhafter/fremder Code auf main). Forensik nach dem Vorfall (`git reflog`, Diff, Branch/Tag-Check) bestätigte: nur 1 Commit, rein additiv, Code identisch – aber das war Glück.

**Wie vermeiden:** Test-/Recherche-Sub-Agenten an die kurze Leine: read-only Agent-Typ (`Explore`) ODER im Prompt git/commit/push/Code-Änderungen **ausdrücklich verbieten**. Den Server-/Commit-Lifecycle behält der Hauptagent. Sub-Agent-Berichte **immer** gegen echte Artefakte prüfen (Screenshot-Dateien? `git status`/`git log`?), nicht blind übernehmen – besonders bei verdächtig niedrigem `tool_uses`.

**Quelle:** Wachwechsel #17, Session 2026-06-21

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

### 2026-06-13: `pkill` in der Sandbox verboten – Alt-Server verfälscht Playwright-Tests

**Erkenntnis:** Beim Verifizieren der v0.17.0-Features meldete ein Playwright-Agent „Navbar-Dropdown und Statistiken fehlen" – obwohl pytest grün war und der Code stimmte. Ursache: `pkill`/`kill` schlägt in der Sandbox mit „operation not permitted" fehl. Ein bereits laufender Dev-Server (mit `FLASK_DEBUG=0`, also **kein** Template-Auto-Reload) blieb auf Port 5000 hängen und servierte **veraltete** Templates. Der Neustart scheiterte still mit „Address already in use" (nur im Server-Log sichtbar). Der Agent testete gegen den Alt-Server → False-Negative.

**Warum relevant:** Ein grüner pytest-Lauf bei gleichzeitig „rotem" Browser-Test ist ein verwirrender Widerspruch, der leicht zu Fehlschlüssen über den eigenen Code führt – man sucht den Bug an der falschen Stelle.

**Wie vermeiden:** (1) Bei „Feature wird nicht angezeigt, obwohl Code/Tests stimmen" zuerst per `curl` das **echte gerenderte HTML** prüfen (`grep` nach Markern), nicht dem Browser blind vertrauen. (2) Verifikations-Server auf **frischem Port** starten (`app.run(port=5001, use_reloader=False)`) und den Agenten explizit dorthin schicken. (3) Oder mit `FLASK_DEBUG=1` (Auto-Reload greift bei Template-Änderungen). (4) Offline-Gegenprobe: Service-Funktion direkt in `app.app_context()` aufrufen und Rückgabe prüfen – umgeht den Server komplett.

**Wo sichtbar:** Session 2026-06-13 (Wachwechsel #12), Verifikation Feature `dqn`. Auch als bd-Memory `feedback_playwright_port_conflict` hinterlegt.

**Quelle:** Eigener Stolperstein beim Wachwechsel #12.

---

## Externe APIs: Garmin Connect (Fortsetzung)

### 2026-04-24: garminconnect In-Memory-Token-API – kein Disk-Pfad für Reconnect

**Erkenntnis:** `garminconnect` speichert Tokens in Memory als JSON-String (`client.dumps()`). Für den Reconnect reicht `Garmin().login(tokenstore=token_json)` – Strings >512 Zeichen werden von der Library automatisch als Inline-Token-Daten erkannt (kein Pfad nötig). Nur der **Erstlogin** braucht ein Verzeichnis für die OAuth-Session-Dateien; dieses wird via `tempfile.mkdtemp()` angelegt und im `finally`-Block bereinigt.

**Warum relevant:** Tokens mussten bisher als Dateien auf Disk liegen (Sicherheitsrisiko bei Multi-User). Mit der In-Memory-API können sie Fernet-verschlüsselt in der Datenbank gespeichert werden – keine Disk-Isolation pro User nötig.

**Wo sichtbar:** `app/garmin/client.py` – `login()` nutzt `tempfile.mkdtemp()` + `finally: shutil.rmtree()`, `reconnect()` nutzt `Garmin().login(tokenstore=token_json)`. `app/connectors/garmin.py` – `credentials["_garmin_tokens"]` enthält den Token-String.

**Quelle:** Wachwechsel #5, 2026-04-24. Umgesetzt in I-01 bis I-06 (Commits `12cc765`–`e5016b2`).

---

## Tooling: Alembic + SQLAlchemy (Fortsetzung)

### 2026-04-27: render_as_batch fehlte in migrations/env.py – stiller SQLite-DDL-Bug

**Erkenntnis:** `render_as_batch=True` war nie in `migrations/env.py` (in `context.configure()`) gesetzt. Alle bisherigen ALTER-TABLE-Migrations wurden deshalb manuell mit `op.batch_alter_table()` gebaut – Autogenerate (`flask db migrate`) hätte SQLite-inkompatibles DDL erzeugt, ohne Fehler beim Generieren.

**Warum relevant:** SQLite unterstützt kein `ALTER COLUMN`, `DROP COLUMN` oder `ADD CONSTRAINT` als standalone SQL. Alembic's Batch-Mode umgeht das durch Tabellen-Recreate. Ohne das Flag in `env.py` bricht jede automatisch generierte Migration, die eine bestehende Tabelle modifiziert, lautlos beim Upgrade.

**Wie lösen:** In `migrations/env.py` → `context.configure()` → `conf_args.setdefault("render_as_batch", True)` ergänzen. Einmalig, wirkt auf alle zukünftigen `flask db migrate`-Aufrufe. Fix in Commit `21c5cfd`.

**Wo sichtbar:** `migrations/env.py` → `run_migrations_online()` → `conf_args.setdefault("render_as_batch", True)`

**Quelle:** Wachwechsel #8, 2026-04-27. Fix als Commit 0 des UUID-Features.

---

### 2026-04-27: SQLAlchemy Uuid-Typ erwartet uuid.UUID-Objekt – kein String-Vergleich

**Erkenntnis:** `sqlalchemy.types.Uuid` (database-agnostischer UUID-Typ, SQLAlchemy 2.0+) konvertiert Python-seitig zu `uuid.UUID`-Objekten. Ein WHERE-Vergleich `Challenge.public_id == "a7d5aab1-..."` (String aus URL) schlägt mit `AttributeError: 'str' object has no attribute 'hex'` fehl – kein TypeMismatch-Fehler, kein Hinweis auf den Grund.

**Warum relevant:** Der Fehler tritt erst zur Laufzeit auf (Tests mit Integer-IDs laufen durch), und die Fehlermeldung zeigt auf SQLAlchemy-Internals, nicht auf die eigene Query. Schwer zu diagnostizieren ohne Kenntnis des Typ-Systems.

**Wie lösen:** URL-String vor dem Vergleich explizit konvertieren: `uuid.UUID(public_id)`. Ungültige Strings mit `try/except ValueError` abfangen und `abort(404)` zurückgeben. Fix in `_get_challenge_by_public_id()`.

**Wo sichtbar:** `app/routes/challenges.py` → `_get_challenge_by_public_id()` Zeile 16–24

**Quelle:** Wachwechsel #8, 2026-04-27. Fix in Commit `6aa3567`.

---

## Tooling: Alembic + SQLAlchemy (Fortsetzung 2)

### 2026-04-27: Alembic autogenerate erkennt SQLAlchemy Uuid-Typ als falschen Diff

**Erkenntnis:** `flask db migrate` erzeugte bei jeder neuen Migration einen falschen Diff für `challenges.public_id`: `VARCHAR(32)` → `Uuid()` – obwohl die Spalte bereits korrekt als `Uuid` in der DB lag. Das passiert, weil Alembics SQLite-Dialekt den Typ beim Lesen als `VARCHAR` zurückmeldet und er nicht mit dem Python-seitigen `Uuid()`-Typ übereinstimmt.

**Warum relevant:** Dieser gefälschte Diff taucht in jeder neuen Migration auf. Wird er nicht manuell entfernt, zerstört er beim `flask db upgrade` womöglich den Typ der Spalte.

**Wie lösen:** Nach `flask db migrate` die generierte Datei öffnen und die `alter_column`-Zeilen für `public_id` (von `existing_type=sa.VARCHAR(length=32)` auf `Uuid()`) löschen, bevor `flask db upgrade` ausgeführt wird.

**Wie vermeiden:** Vor jeder Migration im generierten Script auf `public_id`-Zeilen prüfen. Alternativ: `compare_type=False` für diese Spalte in `env.py` konfigurieren (komplexer, aber dauerhafter Fix).

**Wo sichtbar:** `migrations/versions/` – jede neue Migrationsdatei nach dem UUID-Feature sollte auf diesen Diff geprüft werden.

**Quelle:** Wachwechsel #9, 2026-04-27. Aufgetreten bei der `activity_media`-Migration (149d8863712f).

---

## Security: Datei-Upload

### 2026-04-27: Path-Traversal-Guard bei Datei-Löschung – is_relative_to() Pflicht

**Erkenntnis:** Ohne explizite Pfadprüfung könnte ein manipulierter `file_path`-Wert in der DB (z.B. `../../config.py`) beim Löschen einer Aktivität eine beliebige Datei außerhalb des Upload-Verzeichnisses löschen. SQLAlchemy/Flask bieten dafür keinen automatischen Schutz.

**Wie lösen:** In `delete_upload()` immer `.resolve()` auf Static-Root und Ziel-Pfad anwenden, dann `filepath.is_relative_to(static)` prüfen. Bei Fehler: `logger.warning()` und Return – kein Exception, kein HTTP-Error.

**Wo sichtbar:** `app/utils/uploads.py` → `delete_upload()` – Guard wurde in Commit `c3b6f70` nachgezogen.

**Warum relevant:** Das Muster ist für alle Projekte mit Datei-Uploads relevant, nicht nur für dieses. Upload-Pfade aus der DB sind genauso gefährlich wie direkte User-Inputs.

**Quelle:** Security-Review Wachwechsel #9, 2026-04-27. Fix in Commit `c3b6f70`.

---

## Tooling: Flask Blueprints

### 2026-04-26: url_for-Endpunkt muss Funktionsnamen matchen, nicht Route-Pfad

**Erkenntnis:** `url_for('challenge_activities.log')` schlägt fehl mit `BuildError`, wenn die Route-Funktion `log_form` heißt. Flask-Blueprints leiten Endpunktnamen vom Funktionsnamen ab, nicht vom URL-Pfad.

**Warum relevant:** Der Fehler tritt erst zur Laufzeit auf, wenn ein Template gerendert wird, das den falschen Endpunkt referenziert. Tests für *andere* Routes (z.B. Admin-Seite) decken ihn auf, weil `base.html` bei jedem Request gerendert wird.

**Wie vermeiden:** Nach Erstellen neuer Blueprint-Routes: `grep -r "url_for.*blueprint_name" app/templates/` gegen tatsächliche Funktionsnamen abgleichen.

**Quelle:** Wave 2, 2026-04-26. Fix in Commit `e8fb45f`.

---

## Tooling: Manuelle Ad-hoc-Tests

### 2026-06-08: `config.update()` nach `create_app()` ändert die DB nicht – Engine ist schon gebunden

**Erkenntnis:** Bei einem manuellen Ad-hoc-Test wurde `app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")` **nach** `create_app()` gesetzt – wirkungslos. Flask-SQLAlchemy bindet die Engine beim `db.init_app()` innerhalb der Factory; eine spätere Config-Änderung greift nicht mehr. Folge: Der Test schrieb in die echte Dev-DB und legte dort Test-User/-Challenges an.

**Warum relevant:** Verwandt mit der Playwright-Prod-DB-Lesson (2026-04-26), aber subtiler: Hier sieht der Code so aus, als würde er eine isolierte DB nutzen – tut es aber nicht. Verfälschte Testergebnisse (eine vermeintliche `reason: None`-Beobachtung war in Wahrheit eine alte Dev-DB-Zeile) und Daten-Kontamination sind die Folge.

**Wie vermeiden:** Die DB-URL **vor** `create_app()` über die Umgebungsvariable setzen (`export DATABASE_URL="sqlite:///$TMPDIR/test.db"`), oder gleich pytest mit der `conftest.py`-Fixture (In-Memory) verwenden statt Ad-hoc-Skripten. Für Integrationsverhalten (Login, 403) sind echte pytest-Tests verlässlicher als `session_transaction`-Bastellösungen.

**Wo sichtbar:** Methodik – betrifft alle manuellen `python -c`-Verifikationen gegen die App-Factory.

**Quelle:** Wachwechsel #10 (Abwesenheits-Feature), 2026-06-08.

---

## Security: Upload-Inhaltsvalidierung

### 2026-06-08: ffprobe meldet Einzelbilder als `codec_type=video` – Container-Check nötig

**Erkenntnis:** Bei der Inhaltsvalidierung von Video-Uploads (`43k`) reicht es **nicht**, via `ffprobe` zu prüfen, ob ein Stream mit `codec_type=video` existiert. ffprobe behandelt ein einzelnes Bild (z. B. PNG, als `.mp4` umbenannt) als 1-Frame-Video-Stream und meldet `codec_type=video`. Ein Bild würde so als „gültiges Video" durchrutschen.

**Warum relevant:** Die naheliegende Implementierung (`-select_streams v:0 -show_entries stream=codec_type`) ist unvollständig und täuscht Sicherheit vor. Der Angreifer-Pfad „Bild mit Video-Endung" bliebe offen.

**Wie vermeiden:** Zusätzlich den **Container** prüfen (`format=format_name`) und gegen eine Allowlist abgleichen. Echte Videos liefern `mov,mp4,m4a,...` bzw. `matroska,webm`; ein PNG liefert `png_pipe`. Erst Container-Match **und** vorhandener Video-Stream gelten als gültig. Implementiert in `app/utils/uploads.py:_is_valid_video` (`ALLOWED_VIDEO_CONTAINERS`).

**Wo sichtbar:** `app/utils/uploads.py`, Tests in `tests/test_upload_validation.py` (`test_image_content_as_mp4_rejected`).

**Quelle:** Wachwechsel #11 (Security-Welle), Issue `43k`, 2026-06-08.

---

## Security: Cookie-Härtung

### 2026-06-08: Flask-Talisman sichert nur das Session-Cookie, nicht Remember-Me

**Erkenntnis:** Flask-Talisman setzt in `_force_https` (before_request) `SESSION_COOKIE_SECURE=True` – aber nur für das **Session**-Cookie, request-zeit-abhängig und an `app.debug` gekoppelt. Das **Remember-Me**-Cookie von Flask-Login (`REMEMBER_COOKIE_SECURE`) bleibt davon unberührt und wäre ohne explizite Konfiguration unsicher (würde auch über HTTP gesendet).

**Warum relevant:** Man könnte fälschlich annehmen, Talisman härte „die Cookies" pauschal. Tatsächlich klafft eine Lücke genau beim langlebigen Remember-Me-Token – dem wertvollsten Ziel.

**Wie vermeiden:** Cookie-Flags explizit und env-gesteuert in `config.py` setzen – `SESSION_COOKIE_SECURE` **und** `REMEMBER_COOKIE_SECURE` (plus `HTTPONLY`/`SAMESITE` für beide). Steuerung über `SECURE_COOKIES` (Default `0` für lokale HTTP-Dev, `1` in Prod hinter HTTPS). Talisman bleibt als Defense-in-Depth-Fallback für das Session-Cookie erhalten.

**Wo sichtbar:** `config.py` (Cookie-Flags), `tests/test_secure_cookies.py`.

**Quelle:** Wachwechsel #11 (Security-Welle), Issue `26x`, 2026-06-08.

---

## Statistiken: Metrik-Definition vor Zeitzonen-Verdacht prüfen

### 2026-06-13: „Frühaufsteher" zeigte 10:00 – Durchschnitt statt Minimum, kein UTC-Bug

**Erkenntnis:** Die Kachel „Frühaufsteher" zeigte für sportliche Nutzer 10:00 Uhr, obwohl viele Aktivitäten nachweislich früher stattfanden. Der erste Verdacht (UTC-Verschiebung) war falsch: Beide Schreibpfade speichern Lokalzeit (`startTimeLocal` bei Garmin, `datetime.fromisoformat(date+time)` manuell). Die wahre Ursache war die **Metrik-Definition** – Frühaufsteher/Nachteule basierten auf der **durchschnittlichen** Startzeit (`avg_start`) pro Nutzer. Wer früh und spät mischt, landet im Schnitt in der Tagesmitte; echte 06:00-Einheiten verschwinden im Mittel.

**Warum relevant:** Bei zeitbezogenen Auffälligkeiten ist der reflexhafte Verdacht „Zeitzonen-Bug" naheliegend, aber teuer, wenn man ihn ungeprüft verfolgt. Die billigere erste Frage ist: *Was misst die Metrik überhaupt – Min, Max oder Schnitt?*

**Wie gelöst:** „Frühaufsteher" = `min(Startzeit)`, „Nachteule" = `max(Startzeit)` (Option B). Rein additive In-Memory-Ableitung aus den bereits geladenen `start_minutes`, keine DB-/Query-Änderung. Zusätzlich Teilnehmer-Übersicht mit Ø Start-Uhrzeit + Ø Dauer eingeführt.

**Akzeptierter Grenzfall:** Eine Aktivität exakt um 00:00 Uhr (= 0 Tagesminuten) fällt im `_top3`-Filter (`if v`) beim Frühaufsteher raus. Bewusst als Grenzfall akzeptiert (Kapitän-Entscheidung 2026-06-13), nicht gefixt – ein Wechsel auf `if v is not None` beträfe auch andere Ranglisten (z. B. 0 Sportarten).

**Wo sichtbar:** `app/services/statistics.py` → `earliest_start`/`latest_start`/`avg_start`, `app/templates/dashboard/_statistics.html` (Teilnehmer-Tabelle). Tests: `test_early_bird_night_owl_use_min_max_not_average`, `test_participants_overview`.

**Quelle:** Wachwechsel #13, 2026-06-13. Commits `db43eec` (v0.17.1), `f848443` (v0.18.0).

---

## CI/CD: GitHub-Actions-Deprecation-Annotation maskiert weitere Treffer

### 2026-06-13: Node-20-Warnung listet nur die aktuell sichtbaren Actions, nicht alle

**Erkenntnis:** Die GitHub-Build-Annotation „Node.js 20 actions are deprecated" nannte zunächst nur `actions/checkout@v4` und `actions/setup-python@v5`. Nach deren Anhebung (v5/v6) tauchte beim nächsten Lauf eine **neue** Annotation auf, die jetzt die drei Docker-Actions (`login@v3`, `setup-buildx@v3`, `build-push@v6`) nannte. Sie liefen die ganze Zeit auf Node 20 – die erste Annotation hatte sie nur nicht aufgeführt.

**Warum relevant:** Ich hatte aus der ersten (unvollständigen) Annotation geschlossen, die Docker-Actions seien nicht betroffen, und einer korrekten Recherche eines Sub-Agenten zunächst misstraut. Das hätte die zweite Hälfte des Problems übersehen lassen. Eine Deprecation-Annotation ist eine **Momentaufnahme der sichtbaren Treffer**, kein vollständiger Audit.

**Wie vermeiden:** Nach jedem Action-Bump erneut die Annotation des Folge-Laufs prüfen (`gh run view <id> | grep -ci 'node.js 20'`), bis sie 0 ergibt. Bei Major-Sprüngen am Prod-Pfad (hier `build-push v6→v7`) vorher die Changelogs auf Breaking Changes für das eigene Setup gegenlesen (`cache type=gha`, Inputs) – war hier unkritisch.

**Wo sichtbar:** `.github/workflows/docker-publish.yml` – alle 5 Actions jetzt Node-24-ready (checkout@v5, setup-python@v6, login@v4, setup-buildx@v4, build-push@v7).

**Quelle:** Wachwechsel #13, Issue `oz1`, 2026-06-13. Commits `f414023`, `2855509`.

---

## Architektur: Multi-Entity-Routing

### 2026-06-15: `.first()` ohne ORDER BY/User-Kontext als stiller Multi-Challenge-Routing-Bug

**Erkenntnis:** Die App war monatelang „multi-challenge-fähig" in der **Anzeige**, aber nicht in der **Eingabe**. Mehrere Routen bestimmten die Ziel-Challenge über einen Helfer, der `.first()` ohne `ORDER BY` und ohne Bezug zur Nutzer-Auswahl absetzte (`_active_participation()` in `challenge_activities.py`, `_get_active_challenge()` in `bonus.py`). Solange jeder Nutzer nur an **einer** Challenge teilnahm, fiel das nie auf – ab zwei parallel aktiven Challenges landeten Aktivitäten, Importe und Abwesenheiten still in der **falschen** Challenge, und die Bonus-/Anzeige-Seiten zeigten nur eine davon.

**Warum relevant:** Das ist ein klassischer latenter Multi-Tenant-Bug: korrekt bei n=1, falsch ab n=2, ohne Fehlermeldung. Er trat zusätzlich als IDOR-Risiko auf, weil die Schreibpfade die `challenge_id` aus einem impliziten Default statt aus einer **verifizierten** Teilnahme ableiteten. Die Lese-Anzeige zu „können" verleitet zur Annahme, das Feature sei fertig – die Eingabe ist der eigentliche Gradmesser.

**Wie vermeiden:** Bei jedem Feature, das über mehrere gleichartige Entitäten (Challenges, Teams, Mandanten) hinweg arbeitet, früh den Fall n≥2 durchspielen. Ziel-Entität immer aus einer **explizit gewählten + serverseitig verifizierten** Zugehörigkeit ableiten (Muster: `_resolve_participation()` / `_pick_challenge()` prüfen gegen `(user, id, status=accepted)`), nie aus `.first()`. Default nur bei genau einer Zugehörigkeit; bei mehreren ohne gültige Auswahl **keinen** stillen Schreibzugriff. `add_entry()` im Bonus-Bereich war übrigens schon korrekt, weil es die `challenge_id` aus dem geladenen Objekt statt aus dem Default zog – das ist das nachahmenswerte Muster.

**Wo sichtbar:** Epic `0bv` (Kinder `0bv.1`/`0bv.2`/`0bv.3`), `app/routes/challenge_activities.py` (`_resolve_participation`, `_selected_participation`), `app/routes/bonus.py` (`_user_accepted_challenges`, `_pick_challenge`). Tests: `test_log_submit_rejects_foreign_challenge`, `test_my_week_selector_*`, `test_bonus_index_selector_*`.

**Quelle:** Wachwechsel #14, Epic `0bv`, 2026-06-15. Releases v0.18.1/.2/.3.

---

## Prozess: Versionierung & Changelog

### 2026-06-22: CHANGELOG.md ist die nutzersichtbare /changelog-Seite

**Erkenntnis:** `CHANGELOG.md` wird in der App unter `/changelog` (Link in der Navbar) für die **End-Nutzer (Nicht-Techniker)** gerendert. Technische Changelog-Einträge mit Ticket-IDs, Bibliotheks-Versionen, Funktions-/Dateinamen und Test-Zahlen verwirren diese Zielgruppe.

**Warum relevant:** Einträge müssen in einfacher Alltagssprache aus Nutzersicht formuliert sein (was kann ich jetzt, was ist besser/sicherer). Technische Details gehören in die **Commit-Message**, nicht ins CHANGELOG. Das gesamte CHANGELOG wurde am 2026-06-22 einmalig endnutzerfreundlich umgeschrieben.

**Wo sichtbar:** `CHANGELOG.md`, gerendert via `app/routes/misc.py` (`/changelog`). Konvention in `CLAUDE.md` (Conventions & Patterns) festgehalten. Kategorien: `### Neu`, `### Verbessert`, `### Behoben`, `### Sicherheit`.

**Quelle:** Kapitän-Vorgabe, Wachwechsel #17

### 2026-06-22: SemVer – Anschluss-Tickets sind Patch, nicht Minor

**Erkenntnis:** Die zweite Versionsstelle (Minor) ist ausschließlich neuen, eigenständigen Features vorbehalten. Folge-Tickets, die ein **bestehendes** Feature erweitern oder fixen (z. B. die einzelnen Notification-Auslöser am einen Notification-Feature), zählen die **dritte** Stelle (Patch) hoch.

**Warum relevant:** In der Wache 21./22.06. wurden die Notification-Auslöser noch fälschlich als eigene Minors (1.6.0/1.7.0) gezählt. Ab jetzt: ein Feature-Komplex → ein Minor, Anschlussarbeit → Patches.

**Wo sichtbar:** `app/version.py`, `CHANGELOG.md`. Regel im Memory `feedback_changelog_version`.

**Quelle:** Kapitän-Präzisierung, 2026-06-22

---

## Deployment: Docker

### 2026-06-21: Healthcheck scheiterte am TRUSTED_HOSTS-Gate

**Erkenntnis:** Der Docker-Healthcheck (`curl http://localhost:5000/`) lieferte HTTP 400, weil die Host-Header-Härtung (`TRUSTED_HOSTS`, Flask 3.1) den Host `localhost` ablehnte → Container dauerhaft `unhealthy`, obwohl die App über die echte Domain einwandfrei lief. Die Host-Validierung greift **global vor dem Routing**, daher hilft ein dedizierter `/health`-Endpoint allein nicht – `localhost` muss durchs Gate.

**Warum relevant:** Latenter Altlast-Bug seit der Host-Härtung; fiel erst auf, als gezielt der Health-Status geprüft wurde. `restart: unless-stopped` reagiert nicht auf den Healthcheck, daher kein Crash-Loop – aber das Status-Label war irreführend.

**Wie gelöst:** Leichtgewichtiger `/health`-Endpoint (200, ohne DB/Login) + `localhost`/`127.0.0.1` automatisch in `TRUSTED_HOSTS` (nur container-intern erreichbar, Sicherheits-Impact minimal). Healthcheck auf `/health` umgestellt.

**Wo sichtbar:** `app/routes/misc.py`, `config.py`, `docker-compose.yml`. Ticket `tjs` (Teil).

**Quelle:** Wachwechsel #17, Session 2026-06-21

---

## Frontend / CSP

### 2026-06-22: Content-Security-Policy blockiert inline-Event-Handler (onchange/onclick)

**Erkenntnis:** Die App erzwingt via flask-talisman eine strikte CSP (`script-src 'self' cdn.jsdelivr.net`, **ohne** `unsafe-inline`, nonce-basiert). Inline-Event-Handler im HTML (`onchange="this.form.submit()"`, `onclick=…`) werden vom Browser **stumm blockiert** – Nonces gelten nur für `<script>`-Tags, nicht für Handler-Attribute. Die Aktion läuft wirkungslos ins Leere, ohne Fehlermeldung.

**Warum relevant:** Genau das brach `oa6n` – drei Challenge-Selektoren (Bonus, `my_week`, `user_activities`) reagierten nicht auf die Auswahl. Der direkte URL-Aufruf (`?challenge_id=…`) funktionierte, weil er kein JS braucht – das verschleierte die Ursache und machte es zu einer langen Fehlersuche (das Symptom „alte Bonus-Challenge nicht sichtbar" sah wie ein Daten-/Logik-Bug aus). **pytest fängt diese Klasse nicht** (kein JS-Runtime); sichtbar nur im echten Browser.

**Wie gelöst:** inline-`onchange` entfernt, durch nonce-signiertes `<script nonce="{{ csp_nonce() }}">…addEventListener('change', submit)…</script>` ersetzt. CSP **nicht** aufgeweicht (kein `unsafe-inline` → XSS-Schutz erhalten). Folge-Ticket `b2u0`: Audit auf weitere CSP-Verstöße + automatischer Regression-Check (pytest/Lint), da pytest diese Brüche prinzipiell nicht sieht.

**Wo sichtbar:** `app/templates/bonus/index.html`, `app/templates/activities/my_week.html`, `app/templates/activities/user_activities.html`, CSP in `app/__init__.py`. Ticket `oa6n`, Memory `feedback_no_inline_event_handlers`.

**Quelle:** Wachwechsel #18, Session 2026-06-22

---

## Datenbank / Queries

### 2026-06-22: scalar_one_or_none() crasht bei mehreren Treffern (Multi-Challenge)

**Erkenntnis:** `db.session.execute(…).scalar_one_or_none()` verträgt **genau 0 oder 1** Zeile – bei ≥2 Treffern wirft es `MultipleResultsFound` (HTTP 500). In `challenges.index` lief das zweimal auf „accepted"- bzw. „invited"-Participations, basierend auf der veralteten Annahme, ein User sei in **genau einer** Challenge aktiv.

**Warum relevant:** Seit Multi-Challenge-Support (mehrere parallele Challenges) ist diese Annahme falsch – sobald ein User in >1 Challenge `accepted` ist oder >1 offene Einladung hat, crasht die ganze `/challenges`-Seite (`co52`). Latenter Bug, der erst im realen Multi-Challenge-Betrieb auffiel. Es können **weitere** `scalar_one_or_none`/`.one()`-Stellen mit derselben Altannahme existieren → Audit-Ticket `fzku`.

**Wie gelöst:** `scalar_one_or_none()` → `scalars()…first()` mit deterministischer Sortierung (neuester Eintrag). Zusätzlich toten Code (`active_participation`, nirgends im Template genutzt) entfernt.

**Wo sichtbar:** `app/routes/challenges.py` (index). Ticket `co52`, Audit-Folge `fzku`. Verwandt: Route-Smoke-Test `r96z` hätte den 500er sofort gefangen.

**Quelle:** Wachwechsel #18, Session 2026-06-22
