# Plan: Security-Fixes – XSS & E-Mail-Validierung

**Date:** 2026-04-26
**Goal:** Stored XSS in Admin-Template fixen, E-Mail-Validierung einführen, Tests ergänzen
**Research:** `.schrammns_workflow/research/2026-04-26-xss-email-validation-fix-strategy.md`

## Baseline

| Metric | Value | Command |
|--------|-------|---------|
| Tests gesamt | 68 | `SECRET_KEY=test pytest --co -q` |
| Dateien zu ändern | 6 (+ 1 neue Dependency) | siehe Files to Modify |
| Git-Status | clean (nur Research-File untracked) | `git status` |
| `email-validator` installiert | Nein | `grep email requirements.txt` |

## Files to Modify

| File | Change |
|------|--------|
| `app/templates/admin/users.html` | Zeile 48: `{{ user.email }}` → `{{ user.email\|tojson }}` im onsubmit |
| `app/templates/challenges/detail.html` | Zeile 83: bailout_fee im onsubmit → `\|tojson` (Defense-in-Depth) |
| `app/templates/connectors/index.html` | Zeile 34: display_name im onsubmit → `\|tojson` (Konsistenz) |
| `requirements.txt` | `email-validator>=2.0` hinzufügen |
| `app/routes/auth.py` | `validate_email()` in `register()` einbauen, Zeilen 69-80 |
| `tests/test_auth.py` | 4 neue Tests: invalid email, XSS email, normalization, valid email still works |

## Implementation

### I-01: XSS-Fix – `|tojson` in allen Inline-JS-Handlern

**3 Template-Änderungen, je 1 Zeile:**

**`app/templates/admin/users.html:48`** (KRITISCH – user-controlled):
```html
<!-- VORHER: -->
onsubmit="return confirm('{{ user.email }} wirklich ablehnen und löschen?')"

<!-- NACHHER: -->
onsubmit="return confirm({{ user.email|tojson }} + ' wirklich ablehnen und löschen?')"
```

**`app/templates/challenges/detail.html:83`** (Defense-in-Depth):
```html
<!-- VORHER: -->
onsubmit="return confirm('Wirklich aus der Challenge austreten? Bailout-Gebühr: {{ \"%.2f\"|format(challenge.bailout_fee) }} €')"

<!-- NACHHER: -->
onsubmit="return confirm('Wirklich aus der Challenge austreten? Bailout-Gebühr: ' + {{ (\"%.2f\"|format(challenge.bailout_fee))|tojson }} + ' €')"
```

**`app/templates/connectors/index.html:34`** (Konsistenz):
```html
<!-- VORHER: -->
onsubmit="return confirm('{{ provider.display_name }} wirklich trennen?');"

<!-- NACHHER: -->
onsubmit="return confirm({{ provider.display_name|tojson }} + ' wirklich trennen?');"
```

**Acceptance Criteria:**
- `grep -n "tojson" app/templates/admin/users.html` → Zeile 48
- `grep -n "tojson" app/templates/challenges/detail.html` → Zeile 83
- `grep -n "tojson" app/templates/connectors/index.html` → Zeile 34
- Keine `onsubmit`-Attribute mehr mit `{{ ... }}` ohne `|tojson`

**Risk:** reversible / local / autonomous-ok
**Size:** S

### I-02: E-Mail-Validierung bei Registrierung

**2 Dateien: `requirements.txt` + `app/routes/auth.py`**

**`requirements.txt`** – neue Zeile:
```
email-validator>=2.0
```

**`app/routes/auth.py`** – Import hinzufügen:
```python
from email_validator import validate_email, EmailNotValidError
```

**`app/routes/auth.py:register()`** – nach `email = request.form.get("email", "").strip()` und der Leer-Prüfung, VOR dem DB-Lookup:
```python
try:
    result = validate_email(email, check_deliverability=False)
    email = result.normalized
except EmailNotValidError:
    error = "Ungültige E-Mail-Adresse."
```

**Reuse:** Bestehende `error`-Variable und Template-Rendering (`auth/register.html`) – keine neuen Patterns nötig.

**Acceptance Criteria:**
- `grep "email_validator" app/routes/auth.py` → Import vorhanden
- `grep "email-validator" requirements.txt` → Dependency vorhanden
- `pip install email-validator` erfolgreich
- POST `/auth/register` mit `email=notvalid` → Fehlermeldung
- POST `/auth/register` mit `email=Test@Example.COM` → gespeichert als `test@example.com`

**Risk:** reversible / local / autonomous-ok
**Size:** S

### I-03: Security-Tests für E-Mail-Validierung und XSS-Prävention

**1 Datei: `tests/test_auth.py`** – 4 neue Testfunktionen:

```python
def test_register_rejects_invalid_email(client, db):
    """Ungültige E-Mail-Formate werden abgelehnt."""
    # POST mit "notanemail" → error response, kein User in DB

def test_register_rejects_xss_email(client, db):
    """XSS-Payloads in E-Mail werden abgelehnt."""
    # POST mit "x');alert(1);//@evil.com" → error response, kein User in DB

def test_register_normalizes_email(client, db):
    """E-Mail-Adresse wird normalisiert gespeichert."""
    # POST mit "Test@Example.COM" → User.email == "test@example.com"

def test_register_accepts_valid_email(client, db):
    """Gültige E-Mail mit Sonderzeichen wird akzeptiert."""
    # POST mit "user+tag@example.co.uk" → User in DB vorhanden
```

**Reuse:** Bestehendes Pattern aus `test_auth.py:test_register_creates_user` (Zeile 68-84) – gleiche Fixtures (`client`, `db`), gleicher POST-Aufruf.

**Acceptance Criteria:**
- `SECRET_KEY=test pytest tests/test_auth.py -v` → alle Tests grün
- `SECRET_KEY=test pytest -v` → 72 Tests gesamt (68 + 4 neue), alle grün

**Risk:** reversible / local / autonomous-ok
**Size:** S

## Waves

### Wave 1 (parallel)
- **I-01** – XSS-Fix Templates (keine Dependencies)
- **I-02** – E-Mail-Validierung (keine Dependencies)

### Wave 2 (nach Wave 1)
- **I-03** – Tests (braucht I-02 für email-validator Import + Validierungslogik)

## Boundaries

**Always:**
- `|tojson` für ALLE Template-Variablen in JS-Kontexten (auch wenn aktuell sicher)
- `check_deliverability=False` bei email-validator
- Normalisierte E-Mail in DB speichern

**Never:**
- Inline-JS ohne `|tojson` bei Template-Variablen
- Regex statt `email-validator` für E-Mail-Validierung
- `|safe` Filter auf user-controlled Daten

## Design Decisions

| Decision | Chosen | Rejected | Rationale |
|----------|--------|----------|-----------|
| JS-Escaping | `\|tojson` Filter | `data`-Attribute + addEventListener | Minimale Änderung, Flask-offiziell empfohlen. CSP-Migration als separates TODO. |
| E-Mail-Validierung | `email-validator` Library | Regex, WTForms, manuell | RFC-konform, Normalisierung, wenig Code, aktiv maintained |
| Deliverability-Check | Deaktiviert | Aktiviert | Kleine App, Admin-Approval, DNS-Latenz vermeiden |

## Invalidation Risks

| Assumption | Affected Issues | Check |
|------------|----------------|-------|
| `\|tojson` verfügbar in Jinja2 | I-01 | Ja – Jinja2 built-in seit 2.9 |
| `email-validator>=2.0` Python-3.14-kompatibel | I-02 | Ja – pure Python, 3.8+ |
| Tests laufen mit In-Memory-SQLite | I-03 | Ja – conftest.py bestätigt |

## Rollback

- **Git Checkpoint:** `git stash` oder neuer Branch vor Start
- **I-01:** `git checkout -- app/templates/` revertiert alle Template-Änderungen
- **I-02:** `git checkout -- app/routes/auth.py requirements.txt` + `pip install -r requirements.txt`
- **I-03:** `git checkout -- tests/test_auth.py`

## Verification

```bash
# Nach allen Fixes:
SECRET_KEY=test .venv/bin/pytest -v          # 72 Tests, alle grün
grep -rn "tojson" app/templates/             # 3 Treffer
grep "email-validator" requirements.txt      # vorhanden
grep "validate_email" app/routes/auth.py     # vorhanden
```
