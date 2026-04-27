# Research: XSS-Fix & E-Mail-Validierung – Umsetzungsstrategie

**Date:** 2026-04-26
**Scope:** Stored XSS in Admin-Template + fehlende E-Mail-Validierung bei Registrierung

## Executive Summary

- **Stored XSS** in `admin/users.html:48`: `user.email` wird in `onsubmit`-JS-Kontext eingefügt. Jinja2 HTML-Escaping schützt nicht, da Browser HTML-Entities in Attributen dekodiert bevor JS ausgeführt wird.
- **Zwei weitere Inline-Handler** mit Template-Variablen gefunden: `challenges/detail.html:83` (numerisch, geringes Risiko) und `connectors/index.html:34` (hardcoded, sicher).
- **Keine E-Mail-Validierung** bei Registrierung – beliebige Strings werden akzeptiert und gespeichert.
- **Empfohlener Fix:** `|tojson`-Filter für alle JS-Kontexte + `email-validator`-Library für Registrierung.
- **Testlücken:** Keine Tests für E-Mail-Validierung, XSS-Prävention oder Sonderzeichen in E-Mails.

## Key Files

| File | Purpose |
|------|---------|
| `app/templates/admin/users.html` | Admin-Benutzerverwaltung – XSS-Schwachstelle Zeile 48 |
| `app/templates/challenges/detail.html` | Challenge-Detail – `bailout_fee` in JS-Kontext Zeile 83 |
| `app/templates/connectors/index.html` | Connector-Liste – `display_name` in JS-Kontext Zeile 34 |
| `app/routes/auth.py` | Registrierung ohne E-Mail-Validierung, Zeilen 69-80 |
| `app/models/user.py` | User-Model, `email: String(255)`, keine Validierung |
| `tests/test_auth.py` | 6 Auth-Tests, keine E-Mail-Validierungstests |
| `tests/test_approval.py` | 9 Admin-Tests, keine XSS-Tests |
| `tests/conftest.py` | Fixtures: app, client, db (In-Memory-SQLite) |
| `requirements.txt` | Abhängigkeiten – `email-validator` fehlt noch |

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| Flask | (in requirements.txt) | Web-Framework mit Jinja2-Templating |
| Flask-WTF | 1.3.0 | CSRF-Schutz (bereits installiert) |
| Jinja2 | (Flask-Dependency) | Template-Engine mit HTML-Auto-Escaping |
| email-validator | **nicht installiert** | Empfohlene neue Dependency für E-Mail-Validierung |
| pytest | (in requirements.txt) | Test-Framework |

## Findings

### 1. XSS-Schwachstelle: Inline-JS-Handler mit Template-Variablen

**Alle Inline-Event-Handler mit Template-Variablen:**

| Datei | Zeile | Handler | Variable | Risiko |
|---|---|---|---|---|
| `admin/users.html` | 48 | `onsubmit="return confirm('{{ user.email }}...')"` | `user.email` (user-controlled) | **KRITISCH** |
| `challenges/detail.html` | 83 | `onsubmit="return confirm('...{{ bailout_fee }}...')"` | `challenge.bailout_fee` (Float, admin-set) | GERING |
| `connectors/index.html` | 34 | `onsubmit="return confirm('{{ provider.display_name }}...')"` | `provider.display_name` (hardcoded) | KEINS |

**Weitere Inline-Handler (ohne Template-Variablen, sicher):**
- `activities/week.html:24` – `onchange="this.form.submit()"`
- `activities/my_week.html:85` – `onsubmit="return confirm('...')"`  (statischer String)

**Kein `|safe`-Filter** im gesamten Projekt verwendet.
**Kein `|tojson`-Filter** im gesamten Projekt verwendet.
**Keine `<script>`-Blöcke** mit Template-Variablen.

### 2. Analyse: Warum Jinja2 Auto-Escaping hier nicht schützt

Jinja2 HTML-Auto-Escaping wandelt `'` in `&#x27;` um. Aber in HTML-Attributen wie `onsubmit="..."`:

1. Browser **HTML-dekodiert** den Attribut-Wert (`&#x27;` → `'`)
2. Browser **führt** den resultierenden String als JavaScript aus

Ergebnis: Ein Single-Quote in der E-Mail bricht aus dem JS-String-Literal aus.

**Quelle:** [Flask Security Docs](https://flask.palletsprojects.com/en/stable/web-security/), [Semgrep Flask XSS Cheat Sheet](https://semgrep.dev/docs/cheat-sheets/flask-xss)

### 3. Fix-Optionen für JS-Kontext

#### Option A: `|tojson` Filter (empfohlen)

```html
<!-- VORHER (verwundbar): -->
onsubmit="return confirm('{{ user.email }} wirklich ablehnen?')"

<!-- NACHHER (sicher): -->
onsubmit="return confirm({{ user.email|tojson }} + ' wirklich ablehnen?')"
```

**Vorteile:**
- Flask-offiziell empfohlen für JS-Kontexte
- Konvertiert zu JSON, escaped `<`, `>`, `&` als Unicode-Escapes (`<` etc.)
- Produziert einen gequoteten String – kein manuelles Quoting nötig
- Keine neue Dependency
- Einfachste Änderung (1 Zeile pro Stelle)

**Nachteile:**
- Inline-JS bleibt bestehen → blockiert strikte CSP

#### Option B: `data`-Attribute + addEventListener

```html
<!-- Template: -->
<form ... data-email="{{ user.email }}">

<!-- Separater Script-Block: -->
<script>
document.querySelectorAll('[data-email]').forEach(form => {
  form.addEventListener('submit', e => {
    if (!confirm(form.dataset.email + ' wirklich ablehnen?')) e.preventDefault();
  });
});
</script>
```

**Vorteile:**
- CSP-kompatibel (kein Inline-JS in Attributen)
- `data`-Attribute sind reiner HTML-Kontext → Auto-Escaping schützt
- Saubere Trennung von Markup und Verhalten

**Nachteile:**
- Mehr Code-Änderung
- Braucht `<script>`-Block (oder externe JS-Datei)
- Für eine kleine App mit 3 confirm-Dialogen etwas over-engineered

#### Empfehlung

**Option A (`|tojson`) für den sofortigen Fix.** Minimale Änderung, maximale Sicherheit. CSP kann als separate Härtungsmaßnahme später eingeführt werden (TODO).

### 4. E-Mail-Validierung: Ansatz-Vergleich

| Ansatz | Sicherheit | Aufwand | Dependencies | Empfehlung |
|---|---|---|---|---|
| Simple Regex | Schwach – RFC-Edge-Cases, keine Normalisierung | ~5 Zeilen | Keine | ❌ Nicht empfohlen |
| `email-validator` Library | Stark – RFC-konform, Normalisierung, Längenlimits | ~8 Zeilen | 1 Paket | ✅ **Empfohlen** |
| WTForms `Email()` | Gleich wie `email-validator` (delegiert intern) | Höher (Form-Klassen nötig) | Gleich | ❌ Overhead |
| Manuell (`@` + Länge) | Minimal | ~3 Zeilen | Keine | ❌ Zu schwach |

**Empfohlene Implementierung:**

```python
from email_validator import validate_email, EmailNotValidError

# In register():
try:
    result = validate_email(email, check_deliverability=False)
    email = result.normalized  # lowercase domain, NFKC
except EmailNotValidError as e:
    error = str(e)
```

**`check_deliverability=False`** ist angemessen: kleine App, wenige User, Admin-Approval-Flow. DNS-Checks würden nur Latenz und transiente Fehler bringen.

**Normalisierung** ist ein Bonus: verhindert Duplikat-Accounts via `User@Example.COM` vs `user@example.com`.

### 5. Test-Abdeckung: Ist-Stand und Lücken

**Existierende Tests (15 relevant):**
- 6 Auth-Tests: Register-Flow, Login-Flow, Lockout, CSRF
- 9 Admin-Tests: Approval-Flow, Reject, Access-Control

**Kritische Lücken für die Fixes:**
- ❌ Registrierung mit ungültiger E-Mail-Adresse
- ❌ Registrierung mit XSS-Payload in E-Mail
- ❌ Registrierung mit Sonderzeichen (`'`, `"`, `<`, `>`)
- ❌ E-Mail-Normalisierung (Duplikat-Erkennung)
- ❌ Admin-Template XSS-Prävention (Rendering-Test)

**Empfohlene neue Tests (mindestens):**
1. `test_register_rejects_invalid_email` – ungültige Formate werden abgelehnt
2. `test_register_rejects_xss_email` – XSS-Payloads werden abgelehnt
3. `test_register_normalizes_email` – E-Mail wird normalisiert gespeichert

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| XSS-Mechanismus (HTML→JS) | 4 | Vollständig verstanden, Exploit-Pfad verifiziert |
| Template-Landschaft | 4 | Alle 16 Templates gescannt, alle Handler identifiziert |
| `|tojson` Sicherheit | 3 | Flask-Docs + Semgrep-Referenz, Standard-Empfehlung |
| `email-validator` Library | 3 | API, Verhalten, Kompatibilität recherchiert |
| Test-Infrastruktur | 3 | conftest.py, Fixture-Muster, bestehende Tests gelesen |
| CSP-Integration | 2 | Prinzip verstanden, Flask-Talisman identifiziert, nicht tief untersucht |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| `email-validator` Verhalten bei Edge-Cases (IDN, very long local parts) | nice-to-have | Library-Tests lesen oder manuell testen |
| CSP-Header-Integration mit Flask-Talisman | nice-to-have | Separate Research bei CSP-Einführung |
| `|tojson` Verhalten bei Unicode/Emoji in E-Mail | nice-to-have | Manueller Test nach Implementation |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Jinja2 Auto-Escaping ist aktiv (Flask-Default) | Yes | Kein `autoescape`-Override in `app/__init__.py`, keine `.env`-Konfiguration |
| `email-validator` ist Python-3.14-kompatibel | Yes | Supports 3.8+, pure Python (WebSearch-Ergebnis) |
| `|tojson` escaped `'` korrekt für JS-String-Kontext | Yes | Flask Security Docs + Semgrep Cheat Sheet |
| CSRF-Schutz bleibt nach Fix intakt | Yes | Fix ändert nur Attribut-Value, nicht Form-Struktur |
| `check_deliverability=False` ist akzeptabel | Yes | Admin-Approval-Flow, kleine User-Basis |

## Recommendations

### Sofortige Fixes (2 Issues)

**Fix 1 – XSS in Inline-JS-Handlern:**
- `admin/users.html:48`: `{{ user.email }}` → `{{ user.email|tojson }}`
- `challenges/detail.html:83`: `{{ "%.2f"|format(challenge.bailout_fee) }}` → `{{ ("%.2f"|format(challenge.bailout_fee))|tojson }}` (Defense-in-Depth, auch wenn numerisch)
- `connectors/index.html:34`: Optional, da hardcoded – aber konsistenter mit `|tojson`

**Fix 2 – E-Mail-Validierung:**
- `email-validator` zu `requirements.txt` hinzufügen
- In `auth.py:register()` validieren + normalisieren
- `check_deliverability=False`

**Fix 3 – Tests:**
- Mindestens 3 neue Tests für E-Mail-Validierung + XSS-Ablehnung

### TODO (spätere Härtung)
- `TODO:` CSP-Header via Flask-Talisman einführen (blockiert restliche Inline-JS)
- `TODO:` Alle `confirm()`-Dialoge zu `addEventListener()` migrieren (CSP-Voraussetzung)
- `TODO:` Passwort-Stärke-Validierung bei Registrierung
