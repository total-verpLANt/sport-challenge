# Research: Garmin-Connector Login – Loading-Feedback nach Form-Submit

**Date:** 2026-04-26
**Scope:** app/routes/connectors.py, app/templates/connectors/, app/templates/base.html, app/connectors/garmin.py

## Executive Summary

- Der Garmin-Connect-Flow ist ein synchroner POST-Form-Submit ohne jegliches JS-Feedback; der User kann den Button mehrfach klicken.
- Bootstrap 5.3.3 ist bereits im base.html geladen – Spinner-Komponenten sind **ohne zusätzliche Dependencies** verfügbar.
- base.html hat keinen `{% block scripts %}`-Hook; JS muss entweder inline in connect.html oder über einen neuen Block-Hook eingebracht werden.
- Die Lösung ist rein clientseitig: Form-Submit-Event → Button deaktivieren + Spinner + Text ändern.
- Kein Backend-Aufwand nötig; kein Sicherheitsrisiko.

## Key Files

| File | Purpose |
|------|---------|
| `app/templates/connectors/connect.html` | Garmin-Credentials-Formular (Ziel der Änderung) |
| `app/templates/base.html` | Base-Template mit Bootstrap 5.3.3; kein `{% block scripts %}` |
| `app/routes/connectors.py` | POST /connectors/<provider>/connect → connect_save() |
| `app/connectors/garmin.py` | GarminConnector.connect() – der langsame Schritt |

## Technology Stack

| Library/Framework | Version | Role |
|-------------------|---------|------|
| Bootstrap | 5.3.3 | CSS + JS (Spinner-Komponente verfügbar) |
| Jinja2 | Flask-Standard | Templating |
| Flask-WTF/CSRF | aktuell | CSRF-Token im Form |

## Findings

### Connect-Flow (synchron)

1. User öffnet `GET /connectors/garmin/connect` → `connect.html` rendert Formular
2. User füllt Email + Passwort, klickt "Verbinden"
3. `POST /connectors/garmin/connect` → `connect_save()` ruft `GarminConnector.connect()` auf
4. `connect()` → `GarminClient.login(email, password)` → **Garmin-API (langsam, 5–15s)**
5. Tokens werden Fernet-verschlüsselt in DB gespeichert
6. Redirect zu `/connectors/` mit Flash-Nachricht

**Problem:** Schritt 4 dauert lang, der User sieht keinerlei Feedback. Der Submit-Button bleibt aktiv → Doppelklick-Risiko.

### Aktueller Button (connect.html:46)

```html
<button type="submit" class="btn btn-primary">Verbinden</button>
```

- Kein `disabled`, kein Spinner, kein JS.
- Form hat `id`-Attribut nicht gesetzt → muss für JS-Targeting ergänzt werden (oder Button direkt per `form.addEventListener`).

### Bootstrap 5.3.3 Spinner

Bereits per CDN in `base.html:7-10` und `base.html:45-47` geladen. Inline-Spinner:

```html
<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
Verbindung wird hergestellt…
```

### base.html – kein scripts-Block

`base.html` hat **keinen** `{% block scripts %}{% endblock %}`-Hook vor `</body>`.
Bootstrap-Bundle steht in Zeile 45-47. Optionen:
- **Option A (minimal):** `<script>`-Block direkt am Ende von `connect.html` – kein base.html-Eingriff
- **Option B (sauber):** `{% block scripts %}{% endblock %}` in base.html vor `</body>` einfügen → `connect.html` nutzt den Block

Option B ist sauberer (wiederverwendbar für künftige Templates), erfordert aber einen Eingriff in base.html.

### Sicherheit

- Keine Sicherheitsbedenken: rein clientseitig, kein Datentransfer
- CSRF-Token bleibt im Form, wird normal mitgeschickt
- `disabled` auf Button verhindert nur erneuten Klick im Browser; serverseitig hat connect_save() bereits idempotente Upsert-Logik

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Connect-Route (connectors.py) | 4 | Vollständig gelesen, verstanden |
| connect.html Template | 4 | Vollständig gelesen |
| base.html Struktur | 4 | Vollständig gelesen |
| Bootstrap Spinner API | 3 | Gut bekannt, keine Gaps |
| JS-Integrationspunkt | 3 | Klar: Form-submit-Event |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| base.html `{% block scripts %}` – ob andere Templates ihn brauchen | nice-to-have | Grep auf alle Templates |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Bootstrap 5.3.3 liefert Spinner-Komponente ohne Extra-Import | Yes | Bootstrap-Docs + CDN-Bundle |
| form-submit-Event feuert vor Navigation | Yes | HTML-Standard |
| base.html hat keinen scripts-Block | Yes | base.html:1-50 gelesen |
| connect.html wird nur für Credentials-Provider (Garmin) gerendert | Yes | connectors.py:70-80, oauth_flow-Check |

## Recommendations

### Implementierungsplan (2 Schritte, atomar)

**Schritt 1 – base.html: `{% block scripts %}` einfügen**
- Vor `</body>` (nach Bootstrap-Bundle, Zeile 47) einfügen
- Einmalige Änderung, keine funktionale Auswirkung auf bestehende Templates

**Schritt 2 – connect.html: Loading-Feedback**
- Form erhält `id="connect-form"` (oder Button direkt targeten)
- `{% block scripts %}` Block mit inline JS:
  - Event: `form.addEventListener('submit', ...)`
  - Button deaktivieren: `btn.disabled = true`
  - Button-Inhalt ersetzen: Bootstrap-Spinner + "Verbindung wird hergestellt…"
  - Kein Timeout nötig – Browser setzt Button-State zurück bei Redirect/Reload

**Beispiel-JS:**
```javascript
document.getElementById('connect-form').addEventListener('submit', function() {
  const btn = this.querySelector('[type="submit"]');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Verbindung wird hergestellt…';
});
```
