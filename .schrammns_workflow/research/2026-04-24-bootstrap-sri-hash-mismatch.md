# Research: Bootstrap SRI-Hash Mismatch in Flask-Templates

**Date:** 2026-04-24
**Scope:** `app/templates/` – CDN-Einbindung, SRI-Hashes, Security-Header-Setup

## Executive Summary

- **Einziger Fehler:** Der SRI-Hash für `bootstrap.bundle.min.js` 5.3.3 in `base.html:33` ist falsch. Der Browser blockiert dadurch das gesamte Bootstrap-JavaScript auf allen Seiten.
- **Ursache:** Hash-Tippfehler bei der initialen Einbindung (`Xc4s9b...` statt `Xc5s9f...`).
- **Korrekter Hash (dreifach verifiziert):** `sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz`
- **CSS-Hash ist korrekt** – kein Handlungsbedarf.
- **Kein CSP-Header gesetzt** – keine Security-Header-Library installiert (Flask-Talisman fehlt).

## Key Files

| File | Purpose |
|------|---------|
| `app/templates/base.html` | Einziges Template mit CDN-Links, alle anderen erben davon |
| `app/__init__.py` | App-Factory – kein Security-Header-Setup vorhanden |
| `app/extensions.py` | Extensions (CSRF, Limiter, Login) – kein Talisman |
| `config.py` | Konfiguration – keine CDN/CSP-Einträge |

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| Bootstrap | 5.3.3 | CSS/JS-Framework, nur per CDN eingebunden |
| jsDelivr | – | CDN-Provider für Bootstrap |
| Flask-WTF | 1.3.0 | CSRF-Schutz (aktiv) |
| Flask-Limiter | 4.1.1 | Rate-Limiting (aktiv) |

## Findings

### 1. Template-Vererbungsstruktur

Alle 5 Child-Templates erben direkt von `base.html` via `{% extends "base.html" %}`:
```
app/templates/base.html
 ├── auth/login.html
 ├── auth/register.html
 ├── connectors/index.html
 ├── connectors/connect.html
 └── activities/week.html
```
**Konsequenz:** Ein Fix in `base.html` wirkt auf alle Seiten. ([app/templates/base.html:1](../../../app/templates/base.html))

### 2. Aktueller Ist-Zustand (base.html)

**CSS (korrekt):**
```html
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
      rel="stylesheet"
      integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH"
      crossorigin="anonymous">
```
Quelle: `app/templates/base.html:7-10`

**JS Bundle (FALSCH – wird geblockt):**
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-YvpcrYf0tY3lHB60NNkmXc4s9bIOgUxi8T/jzmS6BMRRpo5bG90KU4mIPiLCn/oe"
        crossorigin="anonymous"></script>
```
Quelle: `app/templates/base.html:32-34`

### 3. Hash-Vergleich (JS Bundle)

| | Hash |
|---|---|
| **In base.html (falsch)** | `sha384-YvpcrYf0tY3lHB60NNkmXc4s9bIOgUxi8T/jzmS6BMRRpo5bG90KU4mIPiLCn/oe` |
| **Korrekter Hash (berechnet)** | `sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz` |

Verifikationskommando: `curl -s "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" | openssl dgst -sha384 -binary | openssl base64 -A`
Ergebnis: `YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz` ✅

Browser-Fehlermeldung (aus Playwright-Logs): `Failed to find a valid digest in the 'integrity' attribute for resource ... with computed SHA-384 integrity YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz. The resource has been blocked.`

### 4. Auswirkung des Fehlers

Durch die JS-Blockierung sind folgende Bootstrap-Funktionen auf **allen Seiten** nicht verfügbar:
- Dropdowns, Modals, Tooltips, Collapse
- `data-bs-dismiss="alert"` (betroffen: `connectors/index.html:12`)
- Navbar-Expand auf mobilen Geräten

### 5. Fehlende Security-Features (Nebenbefunde)

- **Kein CSP-Header** (`app/__init__.py` – kein `after_request`-Hook, keine Middleware)
- **Flask-Talisman nicht installiert** (`requirements.txt` – nicht vorhanden)
- **Keine Tests für Template-Rendering oder SRI-Hashes** (`tests/` – alle 4 Test-Dateien prüfen nur Logik, nie HTML-Output auf SRI)

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Template-Vererbungsstruktur | 4 | Vollständig gelesen, flache Hierarchie, 1 Basis-Template |
| Bootstrap CDN-Einbindung (CSS) | 4 | Hash korrekt, kein Handlungsbedarf |
| Bootstrap CDN-Einbindung (JS) | 4 | Hash falsch, korrekter Wert dreifach verifiziert |
| CSP / Security-Header | 3 | Nicht vorhanden – Flask-Talisman fehlt |
| Test-Coverage für Templates | 3 | Keine SRI-Tests – strukturelles Gap |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Bootstrap-Version ggf. auf 5.3.8 upgraden | nice-to-have | CDN-Link + beide Hashes von getbootstrap.com holen |
| Flask-Talisman für CSP/HSTS | nice-to-have | `pip install flask-talisman`, Config-Klasse erweitern |
| Test für SRI-Hashes im gerenderten HTML | nice-to-have | `pytest` + `response.data` auf `integrity=` prüfen |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| CSS-Hash ist korrekt | Ja | Browser blockiert nur JS, nicht CSS (Playwright-Logs) |
| JS-Hash ist falsch | Ja | Browser-Fehlermeldung + lokale Hash-Berechnung |
| Bootstrap 5.3.3 ist die gewünschte Version | Ja | URL in base.html explizit `@5.3.3` |
| Nur base.html muss geändert werden | Ja | Alle anderen Templates erben, kein CDN-Link in Child-Templates |

## Recommendations

**Sofort (dieser Fix):**
1. `app/templates/base.html:33` – JS-SRI-Hash ersetzen:
   - Alt: `sha384-YvpcrYf0tY3lHB60NNkmXc4s9bIOgUxi8T/jzmS6BMRRpo5bG90KU4mIPiLCn/oe`
   - Neu: `sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz`

**Optional (separate Issues):**
- Flask-Talisman installieren für CSP, HSTS, X-Frame-Options
- Bootstrap auf 5.3.8 upgraden (aktuelle Stable-Version)
- Smoke-Test ergänzen, der SRI-Hash-Präsenz prüft
