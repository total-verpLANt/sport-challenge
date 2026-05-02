# Plan: Garmin-Token-Speicherung in DB statt Disk

**Datum:** 2026-04-24
**Ziel:** Garmin OAuth-Tokens (di_token, di_refresh_token, di_client_id) Fernet-verschlüsselt
in `ConnectorCredential.credentials["_garmin_tokens"]` speichern statt als Klartext-JSON auf Disk.
`GARMIN_TOKEN_DIR` und alle Token-Verzeichnisse werden vollständig eliminiert.
**Research:** `.schrammns_workflow/research/2026-04-24-garmin-token-speicherung-in-der-datenbank-statt-auf-disk.md`

---

## Baseline (verifiziert 2026-04-24)

| Metrik | Wert | Verifizierungsbefehl |
|--------|------|----------------------|
| Betroffene Produktionsdateien | 7 | `ls app/garmin/client.py app/connectors/garmin.py app/routes/connectors.py config.py .env.example README.md CLAUDE.md` |
| Betroffene Test-Dateien | 1 | `ls tests/test_connectors.py` |
| GARMIN_TOKEN_DIR Vorkommen (Produktionscode) | 4 | `grep -rn "GARMIN_TOKEN_DIR" . --include="*.py" --include="*.md" --include=".env*" \| grep -v ".venv\|__pycache__\|.schrammns_workflow"` |
| token_dir/_token_dir Vorkommen in app/ | 10 | `grep -rn "token_dir\|_token_dir" app/` |
| Aktuelle Testanzahl | 17 | `.venv/bin/pytest tests/ -q --tb=no 2>&1 \| tail -1` |
| Alle Tests grün | Ja | `.venv/bin/pytest tests/ -q --tb=no` |
| Git-Branch | main | `git branch --show-current` |
| Uncommitted changes | Research-MD | `git status --short` |

---

## Boundaries

**Always:**
- Credentials (Email, Passwort, Token-String) dürfen nie im Log oder in Flash-Messages erscheinen
- `_garmin_tokens` ist ein interner Schlüssel – niemals in credential_fields oder UI-Formularen
- Token-String muss nach dem Schreiben in die DB sofort aus Variablen gelöscht werden (kein Verbleib im Request-Scope nach Commit)
- Alle Disk-basierten Token-Verzeichnisse werden entfernt (kein fallback auf GARMIN_TOKEN_DIR)
- Nach jedem `connect()` werden ggf. refreshte Tokens in die DB zurückgeschrieben (Refresh-Persistenz)

**Never:**
- `GARMIN_TOKEN_DIR` als Konfigurationsvariable weiterführen
- Token-Dateien dauerhaft auf Disk speichern
- `reconnect()` (toter Code) in der alten Form weiterführen
- Credentials ohne Fernet-Verschlüsselung in die DB schreiben

**Ask First:** keine offenen Entscheidungen (alle durch Research geklärt)

---

## Design Decisions

| Entscheidung | Gewählt | Verworfen | Begründung |
|---|---|---|---|
| Token-Speicherort | `credentials["_garmin_tokens"]` im bestehenden Feld | Neues DB-Feld `garmin_token_blob` | Kein Schema-Change, keine Migration; `_JsonFernetField` verschlüsselt automatisch das gesamte Dict |
| Temp-Dir bei Erstlogin | `tempfile.mkdtemp()` + sofortiger Cleanup | Festes `instance/garmin_tokens/` | garminconnect braucht Pfad für credential-basierten Login; temp ist sicherer (kein dauerhafter State) |
| Token-Refresh-Persistenz | `client.dumps()` nach jedem `connect()`, DB-Update nur bei Änderung | Kein Update nach Reconnect | Proaktiver Refresh in Library (`__init__.py:563-568`) würde sonst veraltete Tokens in DB hinterlassen |
| In-Memory-Token-Modus | `Garmin.login(tokenstore=token_json_string)` | Pfad-basiertes temp-Dir | Library erkennt Strings >512 Zeichen automatisch als Token-Daten (verifiziert: `__init__.py:545`) |

---

## Files to Modify

| File | Change | LOC |
|------|--------|-----|
| `app/garmin/client.py` | Umbau: token_dir entfernen, login() gibt token_json zurück, neue reconnect(token_json) | 43 |
| `app/connectors/garmin.py` | Umbau: _token_dir() löschen, connect() zwei-Pfad-Logik, disconnect() ohne shutil | 70 |
| `app/routes/connectors.py` | connect_save() triggert Login + Token-Speicherung, disconnect() vereinfacht | 136 |
| `app/routes/activities.py` | week_view() Token-Refresh nach connect() persistieren | 79 |
| `config.py` | GARMIN_TOKEN_DIR entfernen | 13 |
| `.env.example` | GARMIN_TOKEN_DIR-Zeile entfernen | 3 |
| `README.md` | Startup-Befehl, Env-Tabelle, Architektur-Beschreibung anpassen | 99 |
| `CLAUDE.md` | Architektur-Beschreibung GarminConnector aktualisieren | – |
| `tests/test_connectors.py` | test_garmin_connector_token_path_per_user ersetzen, neue Token-Tests | 90 |

---

## Implementation Detail

### I-01: GarminClient umbau (`app/garmin/client.py`)

**Design Brief:** `GarminClient` ist der direkte Wrapper um `garminconnect.Garmin`.
Er muss zwei Modi unterstützen: (1) Erstlogin mit Email+Passwort via temp-Dir,
Token-String zurückgeben; (2) Reconnect mit Token-String ohne Passwort und ohne Disk.
Nach dem Change gibt `login()` den Token-JSON-String zurück und `reconnect()` nimmt
ihn als Parameter.

**Neue Klasse (`app/garmin/client.py` – vollständig neu):**
```python
import json
import os
import tempfile
import shutil
from datetime import date
from garminconnect import Garmin

class GarminClient:
    def __init__(self) -> None:
        self._api: Garmin | None = None

    def login(self, email: str, password: str) -> str:
        """Erstlogin mit Credentials. Gibt token_json-String zurück."""
        tmp = tempfile.mkdtemp(prefix="garmin_login_")
        try:
            self._api = Garmin(email=email, password=password)
            self._api.login(tmp)
            return self._api.client.dumps()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def reconnect(self, token_json: str) -> str:
        """Token-basierter Reconnect. Gibt ggf. refreshten token_json zurück."""
        self._api = Garmin()
        self._api.login(tokenstore=token_json)  # >512 Zeichen → loads() intern
        return self._api.client.dumps()

    def get_week_activities(self, start: date, end: date) -> list[dict]:
        if self._api is None:
            raise RuntimeError("Nicht eingeloggt.")
        return self._api.get_activities_by_date(start.isoformat(), end.isoformat())

    @staticmethod
    def format_duration(seconds: float) -> str:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def format_distance(meters: float) -> str:
        return f"{meters / 1000:.2f} km"
```

**Entfernte Imports:** `os`, `Path` → nur noch `tempfile`, `shutil`
**Entfernte Methoden:** `__init__(token_dir)`, altes `reconnect(email)`

**Verifikation:**
```bash
python -c "from app.garmin.client import GarminClient; c = GarminClient(); print('OK')"
```

---

### I-02: GarminConnector umbau (`app/connectors/garmin.py`)

**Zwei-Pfad-Logik in `connect()`:**
- Wenn `credentials.get("_garmin_tokens")` vorhanden → `client.reconnect(token_json)`
- Sonst → `client.login(email, password)` → Token-String in Instanzvariable speichern

**Neue Token-String-Rückgabe:** `connect()` speichert den (ggf. refreshten) Token-String
in `self._current_token_json: str | None`. Die Route liest diesen Wert und entscheidet,
ob ein DB-Update nötig ist.

```python
class GarminConnector(BaseConnector):
    provider_type = "garmin"
    display_name = "Garmin Connect"
    credential_fields = ["email", "password"]

    def __init__(self, user_id: int) -> None:
        self._user_id = user_id
        self._client: GarminClient | None = None
        self._current_token_json: str | None = None

    @retry_on_rate_limit()
    def connect(self, credentials: dict) -> None:
        self._client = GarminClient()
        existing_tokens = credentials.get("_garmin_tokens")
        if existing_tokens:
            self._current_token_json = self._client.reconnect(existing_tokens)
        else:
            self._current_token_json = self._client.login(
                email=credentials["email"],
                password=credentials["password"],
            )

    def get_fresh_token_json(self) -> str | None:
        """Gibt ggf. refreshten Token-String zurück (für DB-Update)."""
        return self._current_token_json

    @retry_on_rate_limit()
    def get_activities(self, start: datetime, end: datetime) -> list:
        if self._client is None:
            raise RuntimeError("GarminConnector nicht verbunden.")
        return self._client.get_week_activities(start, end)

    def disconnect(self) -> None:
        self._client = None
        self._current_token_json = None
```

**Entfernte Imports:** `shutil`, `Path`, `current_app`
**Entfernte Methoden:** `_token_dir()`

---

### I-03: `connect_save()` – Token nach Erstlogin in DB (`app/routes/connectors.py`)

**Änderung:** Nach dem Speichern der Basis-Credentials (Email/Passwort) wird ein
Test-Login durchgeführt, der Token-String zurückgegeben und in `credentials["_garmin_tokens"]`
ergänzt. Dann nochmal commit.

```python
@connectors_bp.route("/<provider>/connect", methods=["POST"])
@login_required
def connect_save(provider: str):
    cls = _get_provider_cls(provider)
    credentials = {
        field: request.form.get(field, "")
        for field in cls.credential_fields
    }
    if any(v == "" for v in credentials.values()):
        flash("Bitte alle Felder ausfüllen.", "danger")
        return redirect(url_for("connectors.connect_form", provider=provider))

    # Erst verbinden, um Tokens zu bekommen
    connector = cls(user_id=current_user.id)
    try:
        connector.connect(credentials)
    except Exception as exc:
        flash(f"Verbindung fehlgeschlagen: {exc}", "danger")
        return redirect(url_for("connectors.connect_form", provider=provider))

    # Token-String in Credentials einbetten (wird Fernet-verschlüsselt gespeichert)
    token_json = connector.get_fresh_token_json()
    if token_json:
        credentials["_garmin_tokens"] = token_json

    existing = _get_credential(current_user.id, provider)
    if existing is None:
        cred = ConnectorCredential(
            user_id=current_user.id,
            provider_type=provider,
            credentials=credentials,
        )
        db.session.add(cred)
    else:
        existing.credentials = credentials
    db.session.commit()

    flash(f"{cls.display_name} erfolgreich verbunden.", "success")
    return redirect(url_for("connectors.index"))
```

**Disconnect-Vereinfachung** (Zeilen 116-136): Das garmin-spezifische `if`-Block
(Zeilen 128-130) entfällt komplett. `db.session.delete(cred)` + `commit()` reicht.

---

### I-04: Token-Refresh-Persistenz in `week_view()` (`app/routes/activities.py`)

Nach `connector.connect()` prüfen ob ein neuer Token-String vorliegt und ob er vom
gespeicherten abweicht. Falls ja → DB-Update.

```python
connector.connect(cred.credentials)
# Refresh-Persistenz: Token ggf. aktualisiert
fresh_token = connector.get_fresh_token_json()
stored_token = cred.credentials.get("_garmin_tokens")
if fresh_token and fresh_token != stored_token:
    updated = dict(cred.credentials)
    updated["_garmin_tokens"] = fresh_token
    cred.credentials = updated
    db.session.commit()
```

Einfügen nach Zeile 40 (nach `connector.connect(...)`), vor `raw = connector.get_activities(...)`.

---

### I-05: Config und Cleanup

**`config.py`** – Zeilen 6-8 entfernen:
```python
# VOR:
GARMIN_TOKEN_DIR = os.environ.get(
    "GARMIN_TOKEN_DIR", os.path.expanduser("~/.garminconnect")
)
# NACH: (Zeilen komplett löschen)
```

**`.env.example`** – Zeile 3 entfernen:
```
# GARMIN_TOKEN_DIR=/pfad/zu/tokens   ← löschen
```

**`README.md`** – drei Stellen:
1. Zeile 30: `GARMIN_TOKEN_DIR=./garmin_tokens ` aus Startup-Befehl entfernen
2. Zeilen 36-38: Tabellenzeile `GARMIN_TOKEN_DIR` entfernen
3. Zeile 70: `GarminConnector (Token-Dir pro User isoliert...)` → `GarminConnector (Tokens Fernet-verschlüsselt in DB)`
4. Datenfluss Zeile 91: Schritt 4+5 aktualisieren

---

### I-06: Tests aktualisieren (`tests/test_connectors.py`)

**Zu löschen:** `test_garmin_connector_token_path_per_user` (Zeilen 44-59)

**Neue Tests:**

```python
tests/test_connectors.py — neue Funktionen:

def test_garmin_connector_connect_triggers_login_on_first_connect(app):
    """connect() ohne _garmin_tokens ruft GarminClient.login() auf"""

def test_garmin_connector_connect_uses_reconnect_with_existing_tokens(app):
    """connect() mit _garmin_tokens ruft GarminClient.reconnect() auf"""

def test_garmin_connector_get_fresh_token_json_after_connect(app):
    """get_fresh_token_json() gibt Token-String zurück nach connect()"""

def test_garmin_connector_disconnect_clears_client(app):
    """disconnect() setzt _client und _current_token_json auf None"""

def test_garmin_client_login_returns_token_json():
    """GarminClient.login() gibt JSON-String zurück (gemockt)"""

def test_garmin_client_reconnect_uses_token_string():
    """GarminClient.reconnect() übergibt Token-String an Garmin.login()"""
```

Mock-Strategie: `unittest.mock.patch("app.garmin.client.Garmin")` für alle Tests
die externe Garmin-API-Aufrufe verhindern sollen.

**Verifikation:**
```bash
.venv/bin/pytest tests/ -v --tb=short
# Erwartung: ≥19 Tests, alle grün (17 bestehende + min. 2 neue)
```

---

## Wave-Struktur

```
Wave 1 (parallel):
  I-01  GarminClient umbau         (app/garmin/client.py)
  I-05  Config + Cleanup           (config.py, .env.example, README.md)

Wave 2 (parallel, nach I-01):
  I-02  GarminConnector umbau      (app/connectors/garmin.py)  ← nutzt neues GarminClient-Interface

Wave 3 (parallel, nach I-02):
  I-03  connect_save() Token-Speicherung   (app/routes/connectors.py) ← nutzt get_fresh_token_json()
  I-04  Token-Refresh-Persistenz          (app/routes/activities.py)  ← nutzt get_fresh_token_json()

Wave 4 (nach I-01, I-02, I-03, I-04):
  I-06  Tests aktualisieren        (tests/test_connectors.py)
```

**Abhängigkeiten validiert:**
- I-02 → I-01: `GarminConnector` importiert und instanziiert `GarminClient` (file dep)
- I-03 → I-02: `connect_save()` ruft `connector.get_fresh_token_json()` (interface dep)
- I-04 → I-02: `week_view()` ruft `connector.get_fresh_token_json()` (interface dep)
- I-06 → alle: Tests verifizieren alle Änderungen (logisch + file dep)
- I-05 → I-01: keine echte Abhängigkeit (nur Cleanup) → Wave 1 parallel ok

---

## Risikobewertung

| Issue | Reversibility | Impact | Authorization |
|-------|--------------|--------|---------------|
| I-01 GarminClient | reversible | local (1 Datei) | autonomous-ok |
| I-02 GarminConnector | reversible | local (1 Datei) | autonomous-ok |
| I-03 connect_save() | reversible | system (Route + DB) | autonomous-ok |
| I-04 week_view() | reversible | system (Route + DB) | autonomous-ok |
| I-05 Config/Cleanup | reversible | system (Config, Docs) | autonomous-ok |
| I-06 Tests | reversible | local (Test-Datei) | autonomous-ok |

**Kein Issue ist irreversibel** – alle Änderungen sind via `git revert` rückgängig zu machen.
Keine DB-Migration nötig (Schema unverändert).

---

## Invalidierungsrisiken

| Risiko | Betroffene Issues | Mitigation |
|--------|-------------------|------------|
| `client.dumps()` liefert <512 Zeichen (Heuristik bricht) | I-01, I-02 | Vor Implementierung: manuellen Login einmal durchführen und `len(client.dumps())` prüfen |
| garminconnect-Library-Update ändert `dumps()`/`loads()`-Format | I-01, I-02 | Versionspin in requirements.txt prüfen |
| Bestehende User haben `credentials` ohne `_garmin_tokens` → müssen sich re-verbinden | I-03 | Akzeptabel: `connect()` erkennt fehlende Tokens und führt Erstlogin durch |

---

## Rollback-Strategie

```bash
# Git-Checkpoint vor Start
git stash  # oder: git commit -m "wip: vor garmin-token-db-umbau"

# Pro Wave rollback
git diff HEAD~1 -- app/garmin/client.py  # prüfen
git checkout HEAD~1 -- app/garmin/client.py  # einzelne Datei zurück

# Vollständig rückgängig
git revert HEAD  # wenn committed
```

---

## Acceptance Criteria (gesamt)

```bash
# 1. Keine GARMIN_TOKEN_DIR mehr in Produktionscode
grep -rn "GARMIN_TOKEN_DIR" app/ config.py .env.example
# Erwartung: 0 Treffer

# 2. Keine token_dir-Referenzen mehr in app/
grep -rn "token_dir\|_token_dir" app/
# Erwartung: 0 Treffer

# 3. Alle Tests grün
.venv/bin/pytest tests/ -v --tb=short
# Erwartung: ≥19 Tests, 0 failures

# 4. GarminClient ohne token_dir instanziierbar
python -c "from app.garmin.client import GarminClient; c = GarminClient(); print('OK')"
# Erwartung: OK

# 5. config.py hat kein GARMIN_TOKEN_DIR mehr
python -c "from config import Config; assert not hasattr(Config, 'GARMIN_TOKEN_DIR'), 'FAIL'; print('OK')"
# Erwartung: OK
```

---

## Issue-Größen

| Issue | Größe | Dateien | Kommentar |
|-------|-------|---------|-----------|
| I-01 | S | 1 | Klarer Umbau, kurze Datei |
| I-02 | S | 1 | Zwei-Pfad-Logik, klar spezifiziert |
| I-03 | S | 1 | Erweiterung connect_save(), ein Block |
| I-04 | S | 1 | 5 Zeilen einfügen |
| I-05 | S | 3 | Reine Cleanup/Lösch-Operationen |
| I-06 | M | 1 | Mock-basierte Tests, neue Fixtures |
