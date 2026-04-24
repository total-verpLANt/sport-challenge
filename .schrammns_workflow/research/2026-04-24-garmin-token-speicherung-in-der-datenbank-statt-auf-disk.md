# Research: Garmin-Token-Speicherung in der Datenbank statt auf Disk

**Date:** 2026-04-24
**Scope:** app/connectors/, app/models/, app/utils/crypto.py, app/garmin/, app/routes/, config.py, garminconnect-Library-Internals

---

## Executive Summary

- **Die garminconnect-Library unterstützt In-Memory-Token-Handling nativ:** `Garmin.login(tokenstore)` akzeptiert entweder einen Dateipfad ODER einen JSON-String direkt (Heuristik: `len(tokenstore) > 512`). `client.dumps()` serialisiert Tokens als JSON-String, `client.loads(str)` lädt sie zurück – **komplett ohne Dateisystem**.
- **Tokens sind heute unverschlüsselt auf Disk:** `GARMIN_TOKEN_DIR/<user_id>/garmin_tokens.json` liegt im Klartext mit `di_token`, `di_refresh_token`, `di_client_id`. Das `credentials`-Feld (Email/Passwort) ist Fernet-verschlüsselt in der DB – die Tokens hingegen nicht.
- **Die Lösung ist minimal-invasiv:** Das bestehende `_JsonFernetField` in `ConnectorCredential.credentials` kann einfach erweitert werden, um `{"email": "...", "password": "...", "_garmin_tokens": "{...json-string...}"}` zu speichern. Kein neues DB-Feld, keine Migration nötig.
- **`reconnect()` in `GarminClient` ist toter Code** – wird nirgendwo aufgerufen. Der neue Flow nutzt stattdessen `login(tokenstore=token_json_string)` mit dem aus der DB geladenen Token-String.
- **Risiken:** Token-Refresh schreibt neue Tokens nicht automatisch in die DB zurück (nur auf Disk). Das muss im neuen Flow explizit behandelt werden.

---

## Key Files

| File | Purpose |
|------|---------|
| [config.py](../../config.py) | `GARMIN_TOKEN_DIR` Env-Var – wird nach diesem Change überflüssig |
| [app/connectors/garmin.py](../../app/connectors/garmin.py) | `GarminConnector`: `_token_dir()`, `connect()`, `get_activities()`, `disconnect()` |
| [app/garmin/client.py](../../app/garmin/client.py) | `GarminClient`: `login()`, `reconnect()` – Wrapper um garminconnect.Garmin |
| [app/models/connector.py](../../app/models/connector.py) | `ConnectorCredential` mit `_JsonFernetField` – hier landen die Tokens |
| [app/utils/crypto.py](../../app/utils/crypto.py) | `FernetField` TypeDecorator + `derive_fernet_key()` HKDF |
| [app/routes/connectors.py](../../app/routes/connectors.py) | `connect_save()` – Credentials-Upsert; muss nach Login Tokens zurückspeichern |
| [app/routes/activities.py](../../app/routes/activities.py) | `week_view()` – ruft `connector.connect(cred.credentials)` auf |
| `.venv/.../garminconnect/__init__.py` | `Garmin.login(tokenstore)` – akzeptiert Pfad oder JSON-String (>512 Zeichen) |
| `.venv/.../garminconnect/client.py` | `client.dumps()` → JSON-String; `client.loads(str)` ← JSON-String |

---

## Technology Stack

| Library/Framework | Version (if known) | Role |
|-------------------|--------------------|------|
| garminconnect | 0.3.3 | Garmin Connect API-Wrapper; Token-Persistenz via `dump()`/`load()` oder `dumps()`/`loads()` |
| cryptography (Fernet) | aktuell | Verschlüsselung der Credentials + Token-Blobs in der DB |
| SQLAlchemy | aktuell | ORM; `TypeDecorator` (`_JsonFernetField`) für transparente Verschlüsselung |
| Flask-Login | aktuell | Session-Management; `current_user.id` für Token-Isolation |

---

## Findings

### 1. garminconnect-Library: In-Memory-Token-API existiert bereits

Die Library `garminconnect` 0.3.3 hat eine native In-Memory-Token-API:

**Serialisierung** (`client.py:1067-1074`):
```python
def dumps(self) -> str:
    data = {
        "di_token": self.di_token,
        "di_refresh_token": self.di_refresh_token,
        "di_client_id": self.di_client_id,
    }
    return json.dumps(data)
```
→ Gibt JSON-String zurück; Länge liegt typischerweise bei 800-1200 Zeichen.

**Deserialisierung** (`client.py:1096-1107`):
```python
def loads(self, tokenstore: str) -> None:
    data = json.loads(tokenstore)
    self.di_token = data.get("di_token")
    self.di_refresh_token = data.get("di_refresh_token")
    self.di_client_id = data.get("di_client_id")
```
→ Lädt Tokens direkt aus String – kein Dateisystem.

**Login-Heuristik** (`__init__.py:545-547`):
```python
if len(tokenstore) > 512:
    self.client.loads(tokenstore)   # String-Modus
else:
    self.client.load(normalized_path)  # Datei-Modus
```
→ Wenn wir den serialisierten Token-String (>512 Zeichen) an `Garmin.login()` übergeben, geht die Library automatisch in den dateifreien Modus.

**Wichtig:** Beim Token-Refresh (`__init__.py:560-568`) werden neue Tokens nur dann auf Disk geschrieben, wenn `tokenstore_path` gesetzt ist. Im String-Modus passiert das **nicht** – wir müssen nach dem Aufruf `client.dumps()` erneut aufrufen und das Ergebnis in die DB schreiben.

### 2. Aktueller Ist-Stand: Zwei getrennte Speicherschichten

| Was | Wo | Verschlüsselt? | Risiko |
|-----|----|----------------|--------|
| Email + Passwort | `ConnectorCredential.credentials` (SQLite) | Ja (Fernet via HKDF) | Niedrig |
| Garmin OAuth-Tokens (`di_token`, `di_refresh_token`, `di_client_id`) | `GARMIN_TOKEN_DIR/<user_id>/garmin_tokens.json` (Disk) | **Nein (Klartext!)** | **Hoch** |

Tokens auf Disk erlauben direkten Garmin-API-Zugriff ohne Passwort, solange der Refresh-Token gültig ist (Laufzeit: ca. 1 Jahr).

### 3. Minimaler Umbau: Tokens in bestehendes credentials-Dict

Das `credentials`-Feld ist ein JSON-Dict, das durch `_JsonFernetField` transparent verschlüsselt/entschlüsselt wird. Es enthält aktuell:
```json
{"email": "user@example.com", "password": "geheimes_passwort"}
```

Nach dem Umbau enthält es zusätzlich:
```json
{
  "email": "user@example.com",
  "password": "geheimes_passwort",
  "_garmin_tokens": "{\"di_token\": \"...\", \"di_refresh_token\": \"...\", \"di_client_id\": \"...\"}"
}
```

`_garmin_tokens` ist ein JSON-String (escaptes JSON-in-JSON), Fernet-verschlüsselt zusammen mit den übrigen Credentials. **Kein neues Datenbankfeld, keine Migration.**

Der Underscore-Prefix (`_garmin_tokens`) signalisiert, dass dies ein internes Feld ist, das nicht im UI-Formular erscheint.

### 4. Neuer Connect-Flow

**Erstverbindung (kein Token in DB):**
1. Route `connect_save()` ruft Garmin-Login mit Email + Passwort auf
2. Nach erfolgreichem Login: `api.client.dumps()` → Token-JSON-String
3. `credentials["_garmin_tokens"] = token_json_string` → in DB speichern

**Folgeverbindungen (Token in DB vorhanden):**
1. `activities.py`: `cred.credentials` enthält `_garmin_tokens`
2. `GarminConnector.connect()`: wenn `_garmin_tokens` vorhanden → `Garmin.login(tokenstore=token_json_string)`
3. Falls Token abgelaufen (Exception) → Fallback auf Email+Passwort → neue Tokens speichern
4. Nach connect: `api.client.dumps()` → aktualisierte Tokens zurück in DB

### 5. GarminClient-Umbau

Der bestehende `GarminClient` muss umgebaut werden:
- `__init__`: kein `token_dir` mehr, stattdessen direkter `Garmin`-Client
- `login(email, password)`: nach Login `self._api.client.dumps()` zurückgeben
- `reconnect(token_json)`: `Garmin()` + `login(tokenstore=token_json)` aufrufen
- `get_token_json()`: Hilfsmethode, um aktuelle Tokens nach jedem Aufruf abzugreifen (für Refresh-Persistenz)

### 6. `GARMIN_TOKEN_DIR` wird überflüssig

Mit dem Umbau kann `GARMIN_TOKEN_DIR` aus `config.py`, `.env.example`, README und allen Tests entfernt werden. Kein permanentes Token-Verzeichnis mehr auf Disk.

### 7. Token-Refresh-Problem

**Kritisch:** Wenn die Library den Token proaktiv refresht (`__init__.py:563-568`), schreibt sie die neuen Tokens nur auf Disk (wenn `tokenstore_path` gesetzt). Im String-Modus passiert das nicht. Lösung: Nach jedem `connect()` und `get_activities()` `client.dumps()` aufrufen und das Ergebnis mit der DB vergleichen; wenn abweichend → Credential aktualisieren.

Praktischer Ansatz: `GarminConnector.get_activities()` ruft nach Abschluss `self._api.client.dumps()` auf und gibt neben den Aktivitäten auch den aktuellen Token-String zurück. Die Route speichert ihn.

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| garminconnect In-Memory-Token-API (`dumps`/`loads`) | 4 | Library-Quellcode gelesen, Heuristik (>512) verifiziert |
| Token-Format auf Disk (`garmin_tokens.json`) | 4 | Exakte Felder bekannt: `di_token`, `di_refresh_token`, `di_client_id` |
| `_JsonFernetField` / `FernetField` Encrypt-Pipeline | 4 | Vollständig gelesen inkl. Lazy-Init-Pattern |
| `ConnectorCredential` DB-Schema | 3 | Schema bekannt; keine Migration nötig (JSON-Dict erweiterbar) |
| Token-Refresh-Persistenz (nach proaktivem Refresh) | 3 | Logik in `__init__.py` gelesen; Behandlung im neuen Flow ist Design-Entscheidung |
| MFA-Handling | 1 | `return_on_mfa=True` existiert in Library; Flask-Umsetzung nicht prototypisiert |
| Test-Abdeckung des neuen Flows | 0 | Noch nicht vorhanden |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Token-Länge im Praxisbetrieb (ist >512 Zeichen garantiert?) | must-fill | Test-Login durchführen und `len(client.dumps())` messen |
| Verhalten bei Token-Refresh mitten in `get_activities()` (werden interne Felder aktualisiert, ohne dass `dump()` aufgerufen wird?) | must-fill | Library-Quellcode `_refresh_session()` prüfen; ggf. nach jedem API-Call `client.dumps()` aufrufen |
| MFA-Unterbrechung im Flask-Request-Cycle | nice-to-have | `return_on_mfa=True` mit Session-Speicherung prototypisieren |
| Performance-Impact: Token-Update bei jedem Aktivitäten-Request | nice-to-have | Nur schreiben wenn `dumps()` != gespeicherter String |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| `client.dumps()` produziert immer >512 Zeichen | Nein | Typische JWT-Längen legen das nahe; muss gemessen werden |
| Kein neues DB-Feld nötig (Token im credentials-Dict erweiterbar) | Ja | `_JsonFernetField` serialisiert beliebiges dict; Schema hat kein strict typing |
| Token-Refresh schreibt nur auf Disk, nicht automatisch in Memory-Variablen | Ja | `__init__.py:600-602`: `client.dump(tokenstore_path)` nur wenn `tokenstore_path is not None` |
| `reconnect()` in `GarminClient` ist toter Code | Ja | Grep über gesamtes Projekt – kein Caller außer der Definition selbst |
| `GARMIN_TOKEN_DIR` kann vollständig entfernt werden | Ja | Nach Umbau kein Pfad mehr benötigt |

---

## Recommendations

### Implementierungsplan (atomare Issues)

**Issue 1: GarminClient umbau (Kern)**
- `app/garmin/client.py`: `token_dir`-Parameter entfernen; `login()` gibt `token_json: str` zurück; neue Methode `reconnect(token_json: str)` via `login(tokenstore=token_json)`; `get_token_json()` Hilfsmethode
- Ändert: `app/garmin/client.py`

**Issue 2: GarminConnector umbau**
- `app/connectors/garmin.py`: `_token_dir()` entfernen; `connect()` speichert Token-String in `self._token_json`; `get_activities()` ruft `client.get_token_json()` ab und gibt es zurück (für DB-Update)
- Ändert: `app/connectors/garmin.py`

**Issue 3: connect_save()-Route: Token nach Erstverbindung in DB speichern**
- `app/routes/connectors.py`: Nach erfolgreichem Connect `credentials["_garmin_tokens"]` setzen und DB-Commit
- Ändert: `app/routes/connectors.py`

**Issue 4: activities.py: Token nach Aktivitäten-Abruf aktualisieren**
- `app/routes/activities.py`: Nach `get_activities()` prüfen ob Tokens aktualisiert wurden; wenn ja → Credential updaten
- Ändert: `app/routes/activities.py`

**Issue 5: Config und Cleanup**
- `config.py`: `GARMIN_TOKEN_DIR` entfernen
- `.env.example`: `GARMIN_TOKEN_DIR` entfernen
- `README.md`: Tabelle aktualisieren
- Ändert: `config.py`, `.env.example`, `README.md`

**Issue 6: Tests aktualisieren**
- `tests/test_connectors.py`: `test_garmin_connector_token_path_per_user` durch Token-DB-Roundtrip ersetzen; Neuer Test: `connect()` speichert `_garmin_tokens`; `reconnect()` nutzt Token-String
- Ändert: `tests/test_connectors.py`, `tests/conftest.py`

### Reihenfolge
Issues 1 → 2 → 3 → 4 → 5 → 6 (strikt sequenziell, da Abhängigkeiten)

### TODO für Kapitän
- `TODO (must-fill)`: Vor Implementierung prüfen ob `client.dumps()` wirklich >512 Zeichen liefert. Ein kurzer Test-Login im REPL genügt.
- `TODO (security)`: Nach Disconnect den `_garmin_tokens`-Eintrag aus `credentials` löschen (nicht nur die DB-Zeile, sondern sicherstellen dass kein Token-String im Log landet).
