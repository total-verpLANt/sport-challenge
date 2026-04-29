# Research: Passwort-Bestätigung im Registrierungsprozess

**Date:** 2026-04-29
**Scope:** app/routes/auth.py, app/templates/auth/register.html, tests/test_auth.py

## Executive Summary

- Der Registrierungsprozess nutzt **manuelles `request.form`-Parsing** (kein Flask-WTF Forms), CSRF-Token wird manuell eingebunden
- Es existiert **kein Passwort-Bestätigungsfeld** – nur E-Mail + Passwort
- Die Änderung ist minimal und atomar: **1 Template-Feld + 1 Server-Validierung + 1 Testfall**
- Kein Migrations-Risiko: Rein UI/Route-seitige Änderung, kein DB-Schema-Touch
- Empfehlung: Serverseitige Validierung ist Pflicht; clientseitige HTML5-Validierung als UX-Bonus optional

## Key Files

| File | Purpose |
|------|---------|
| `app/routes/auth.py` | Register-Route (Zeile 67–111), POST-Handler mit Passwort-Längen-Check |
| `app/templates/auth/register.html` | Bootstrap-5-Formular mit E-Mail + Passwort-Feld |
| `tests/test_auth.py` | 12 Auth-Tests, davon 2 für Passwort-Länge |

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| Flask | 3.x | Routing, request.form |
| Flask-WTF | 1.3.0 | Nur CSRF-Token (kein WTForms.Form genutzt) |
| Bootstrap | 5.3.3 | Formular-UI |
| email_validator | ≥2.0 | E-Mail-Normalisierung |

## Findings

### 1. Register-Route (auth.py:67–111)

- POST-Handler liest `email` und `password` aus `request.form`
- Validierungsreihenfolge: leer → Länge < 8 → E-Mail-Format → Duplikat
- **Kein `password_confirm`-Feld** – weder gelesen noch validiert
- Änderungspunkt: nach `len(password) < _MIN_PASSWORD_LENGTH` (Zeile 79), vor Email-Validierung

```python
# Einzufügen zwischen Zeile 80 und 81:
password_confirm = request.form.get("password_confirm", "")
if password != password_confirm:
    error = "Passwörter stimmen nicht überein."
```

### 2. Template (register.html:27–36)

- Aktuell: Ein `<input type="password" name="password">` Feld
- Einzufügen: zweites Feld `name="password_confirm"` nach dem Passwort-Block

### 3. Tests (test_auth.py)

- Bestehende Tests für `/register` POST: ~8 Tests
- Neuer Test nötig: `test_register_rejects_mismatched_passwords`

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Register-Route Logik | 4 | Vollständig gelesen, Zeile für Zeile |
| Template-Struktur | 4 | Vollständig gelesen |
| Test-Coverage | 3 | Tests bekannt, neuer Testfall klar definiert |
| DB/Migration-Impact | 4 | Kein Impact – rein UI/Controller |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Client-seitige Passwort-Stärke-Anzeige gewünscht? | nice-to-have | Käpt'n fragen |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Kein Flask-WTF Form-Klasse für Register | Yes | `auth.py:74-76` – nur `request.form.get()` |
| CSRF-Token manuell im Template | Yes | `register.html:15` |
| Test-Datei heißt test_auth.py | Assumed | Aus Explore-Agent-Ergebnis |

## Recommendations

**Atomare Änderung in 3 Schritten:**

1. **auth.py (Zeile 74–80):** `password_confirm` aus `request.form` lesen, Vergleich vor Längen-Check oder danach
2. **register.html:** Neues `<input type="password" name="password_confirm">` Feld nach dem Passwort-Block einfügen
3. **test_auth.py:** `test_register_rejects_mismatched_passwords` hinzufügen

**Reihenfolge der Server-Validierung (empfohlen):**
```
leer? → Länge < 8? → Passwörter gleich? → E-Mail-Format → Duplikat
```

**Security-Hinweis:** Die Passwort-Bestätigung ist eine UX-Maßnahme, keine Security-Maßnahme. Server-seitig muss der Check trotzdem erfolgen (Bypass via direktem POST möglich).
