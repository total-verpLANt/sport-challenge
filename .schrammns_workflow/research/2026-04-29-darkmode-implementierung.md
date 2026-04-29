# Research: Darkmode-Implementierung sport-challenge

**Date:** 2026-04-29
**Scope:** app/templates/, app/static/, app/__init__.py, app/extensions.py, tests/

## Executive Summary

- Bootstrap 5.3.3 (CDN) ist bereits installiert und unterstützt nativ `data-bs-theme="dark|light"` — kein Zusatz-Framework nötig.
- Es gibt **ein einziges** Base-Template (`base.html`), von dem alle 20 Child-Templates direkt erben. Ein Eingriff in `base.html` wirkt projektweit.
- Keinerlei vorhandene Theme-Infrastruktur (kein Toggle, kein Cookie, keine CSS-Variablen) — grüne Wiese.
- Hardcodierte Farbklassen (`navbar-dark bg-dark`, `thead.table-dark`, `bg-warning text-dark`, `bg-light`-JS-Toggle) müssen gezielt angepasst werden — kein Inline-CSS.
- Bestehende Tests prüfen keine CSS-Klassen, keine CSP-Header, keine Cookies — Risiko bestehender Testbreaks: **niedrig**.

## Key Files

| File | Purpose |
|------|---------|
| `app/templates/base.html` | Einziges Base-Template, enthält Navbar, Bootstrap-CDN-Imports, Inline-Script (mit Nonce) |
| `app/__init__.py` | App-Factory, Talisman CSP-Konfiguration (script-src nonce, style-src unsafe-inline) |
| `app/extensions.py` | Talisman-Instanz; csp_nonce() Jinja-Helper wird hier registriert |
| `app/templates/challenges/detail.html` | Viele Farbklassen (bg-warning text-dark, bg-success text-white, text-muted) |
| `app/templates/dashboard/index.html` | thead.table-dark, text-muted, bg-secondary bg-opacity-25 |
| `app/templates/admin/users.html` | thead.table-dark, diverse Badge-Farben |
| `app/templates/activities/my_week.html` | Dynamische Farbklassen via Jinja (bg-success/warning/danger in Progress-Bar) |
| `app/templates/activities/log.html` | JS toggelt bg-light an Drag&Drop-Zone |
| `app/templates/activities/add_media.html` | JS toggelt bg-light an Drag&Drop-Zone |
| `app/static/` | Leer (außer User-Uploads) — neue CSS/JS-Dateien können ohne Konflikte angelegt werden |
| `tests/conftest.py` | Test-Fixtures: session-scoped App, In-Memory-SQLite, WTF_CSRF disabled |

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| Bootstrap | 5.3.3 (CDN jsDelivr) | UI-Framework, native `data-bs-theme`-Unterstützung seit 5.3 |
| GLightbox | 3.3.1 (CDN) | Lightbox für Medien — kein Dark-Mode-Problem, passt sich an |
| Flask-Talisman | ≥1.0 | CSP-Middleware, stellt csp_nonce() bereit |
| Flask-Login | 0.6.3 | Session-Management — für serverseitigen Theme-Cookie optional nutzbar |
| pytest | ≥8.0 (aktuell 9.0.3) | Kein CSS/Header-Assertions → geringes Bruchrisiko |

## Findings

### F-01: Bootstrap 5.3.3 native Dark Mode

Bootstrap 5.3+ unterstützt `data-bs-theme="dark|light"` am `<html>`-Tag. Damit schalten **alle** Bootstrap-Utilities automatisch um: Hintergründe, Texte, Borders, Shadows.

```html
<!-- base.html:2 — aktuell: -->
<html lang="de">
<!-- gewünschter Zustand: -->
<html lang="de" data-bs-theme="light">
```

Das Attribut wird durch JavaScript dynamisch auf `"dark"` gesetzt, per `localStorage` persistiert.
**Citation:** `app/templates/base.html:2`

### F-02: Einziger Eingriffspunkt — base.html

Alle 20 Templates erben via `{% extends "base.html" %}`. Globale Änderungen (Toggle-Button, Theme-Init-Script, `data-bs-theme`-Attribut) nur in `base.html` nötig.
**Citation:** Alle Templates in `app/templates/` (rekursiv), jedes mit `{% extends "base.html" %}`

### F-03: Hardcodierte Farbklassen — Kritische Hotspots

Nicht alle Bootstrap-Klassen schalten automatisch mit `data-bs-theme` um. Diese müssen manuell angepasst werden:

| Klasse | Templates | Problem im Dark Mode | Lösung |
|---|---|---|---|
| `navbar-dark bg-dark` | base.html:17 | Navbar bleibt schwarz auch im Light-Mode | → `bg-body-tertiary` (Bootstrap 5.3 theme-aware) |
| `thead.table-dark` | dashboard, admin, week | Explizite Dark-Klasse überschreibt Theme | → Entfernen; Bootstrap übernimmt Auto-Coloring |
| `thead.table-light` | bonus, import | Im Dark-Mode weißer Kopf auf dunklem Hintergrund | → Ebenfalls entfernen |
| `bg-warning text-dark` | challenges, activities | `text-dark` erzwingt schwarzen Text — bricht im Dark Mode | → `text-body` oder Bootstrap 5.3 `text-emphasis-warning` |
| `bg-info text-dark` | challenges, detail | Wie oben | → `text-body` |
| `bg-light text-dark` (Badges) | challenges/detail:158 | `bg-light` im Dark Mode sehr hell | → `bg-secondary-subtle text-secondary-emphasis` |
| `btn-outline-light` | base.html:47,72,75 | Unsichtbar im Light-Mode wenn Navbar hell wird | → Dynamisch via CSS oder Navbar bleibt dunkel |
| JS: `bg-light` toggle | log.html:51-55, add_media.html:51-57 | Drag&Drop-Zone immer hell | → `bg-body-secondary` oder CSS-Var nutzen |

**Citation:** `app/templates/base.html:17,47,72,75`; `app/templates/challenges/detail.html:44,72,152,154,158`; `app/templates/dashboard/index.html:26`; `app/templates/activities/log.html:51`; `app/templates/activities/add_media.html:51`

### F-04: CSP-Nonce-Mechanismus (Flask-Talisman)

- `script-src`: Nonce-basiert + `cdn.jsdelivr.net` whitelist. **Neue Inline-Scripts brauchen `nonce="{{ csp_nonce() }}"`.**
- `style-src`: `'unsafe-inline'` + `cdn.jsdelivr.net`. Inline-Styles sind erlaubt ohne Nonce.
- Das Theme-Init-Script (FOUC-Prevention, muss vor dem CSS-Load laufen) braucht zwingend den Nonce.
- Muster aus `base.html:99`: `<script nonce="{{ csp_nonce() }}">…</script>` — direkt übertragbar.

**Citation:** `app/__init__.py:17-27`, `app/extensions.py:21`, `app/templates/base.html:99`

### F-05: FOUC-Prevention (Flash Of Unstyled Content)

Ohne FOUC-Guard: Bei `localStorage`-gespeichertem Dark-Theme würde beim Laden kurz das Light-Theme aufflackern. Lösung: Inline-Script **vor** dem Bootstrap-CSS eingebunden (im `<head>`), der sofort `data-bs-theme` auf `<html>` setzt.

```html
<!-- MUSS vor dem Bootstrap-CSS-Link stehen, im <head>: -->
<script nonce="{{ csp_nonce() }}">
  (function() {
    var t = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-bs-theme', t);
  })();
</script>
```

**Citation:** `app/templates/base.html:7` (Bootstrap-CSS-Link — Script muss davor kommen)

### F-06: Navbar-Strategie

Zwei Optionen:
1. **Navbar bleibt immer dunkel:** `navbar-dark bg-dark` behalten, nur den Toggle-Button hinzufügen. Einfachster Weg, `btn-outline-light` bleibt korrekt.
2. **Navbar passt sich an:** `bg-body-tertiary` + `navbar-expand-lg` (ohne `navbar-dark`), data-bs-theme-aware. Komplexer, weil `btn-outline-light` im Light-Mode unsichtbar wird.

**Empfehlung:** Option 1 (Navbar immer dunkel) für V1. Kein Risiko, kein Klassenwirrwar.

### F-07: Toggle-Button Platzierung

Idealer Ort: `base.html:44` — rechter Flex-Container (`ms-auto d-flex align-items-center gap-3`), als erstes Kind **vor** dem `{% if current_user.is_authenticated %}`-Block. Damit ist der Toggle für eingeloggte und anonyme User sichtbar.

**Citation:** `app/templates/base.html:44`

### F-08: Test-Risiko

- Keine CSS-Klassen-Assertions in Tests.
- Alle HTML-Assertions sind Text-Substring-Checks (deutschsprachige Strings).
- **Mittleres Risiko:** Jinja-Syntaxfehler in `base.html` würde ~90% aller Tests kippen (alle rendern Templates die base.html erben). Sorgfältiger Syntax-Check nach jeder Änderung an base.html nötig.
- Neue Tests empfohlen für: Theme-Cookie-Persistenz, Toggle-Render.

**Citation:** `tests/conftest.py:1-50`, alle Testdateien mit `.assert` auf `b"..."` Strings

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Bootstrap 5.3 data-bs-theme API | 3 | Vollständig verstanden, Natives Attribut, gut dokumentiert |
| Template-Vererbungsstruktur | 4 | Trivial flach, ein Base-Template, vollständig kartiert |
| CSP-Nonce-Mechanismus | 4 | Flask-Talisman, Nonce-Scope klar, Muster vorhanden |
| Hardcodierte Farbklassen | 3 | Vollständig inventarisiert mit Zeilen; Behebung bekannt |
| FOUC-Prevention | 3 | Strategie bekannt, Script-Position klar |
| Test-Impact | 3 | Kein CSS-Assert, Risiko nur bei Jinja-Syntaxfehlern |
| Drag&Drop-Zonen (JS bg-light) | 2 | Lokalisiert, Lösung skizziert, nicht tief analysiert |
| User-Preference-Persistenz (serverseitig) | 1 | Kein Backend vorhanden; für V1 localStorage ausreichend |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| GLightbox Dark-Mode-Verhalten | nice-to-have | GLightbox 3.3 Docs prüfen — hat eigene Theme-Option? |
| Serverseitige Theme-Persistenz (nach Login) | nice-to-have | User-Model + Migration + Before-Request-Hook; für V2 |
| Print-Stylesheet / Print-Media dark override | nice-to-have | `@media print { }` in custom CSS |
| prefers-color-scheme auto-Detection | nice-to-have | Für "System"-Option im Toggle (light/dark/auto) |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Bootstrap 5.3 data-bs-theme schaltet alle Utilities um | Yes | Bootstrap 5.3 Docs + CDN-Version in base.html:7 |
| Alle Templates erben von genau einem base.html | Yes | grep über alle Templates, je 1x `{% extends "base.html" %}` |
| style-src 'unsafe-inline' erlaubt Inline-Styles ohne Nonce | Yes | app/__init__.py:17-27 |
| script-src benötigt Nonce für Inline-Scripts | Yes | app/__init__.py:17-27 + base.html:99 als Beweis |
| localStorage verfügbar (kein Private-Browsing-Fix nötig) | No | Übliche Annahme; try/catch empfohlen |
| Navbar kann dunkel bleiben ohne visuelle Inkonsistenz | No | Design-Entscheidung — nur Implementierungsempfehlung |

## Recommendations

### Implementierungsplan (Reihenfolge wichtig wegen FOUC)

1. **`app/static/js/` anlegen**, `theme.js` mit Toggle-Logik + localStorage-Persistenz
2. **`base.html` — FOUC-Prevention-Script** im `<head>` VOR Bootstrap-CSS (Nonce!)
3. **`base.html` — `data-bs-theme` Attribut** auf `<html>` (initial "light")
4. **`base.html` — Toggle-Button** in rechtem Navbar-Flex, ruft `theme.js` auf
5. **`base.html` — Navbar** entweder dunkel lassen (einfach) oder auf `bg-body-tertiary` umstellen
6. **Alle Templates** — `thead.table-dark` / `thead.table-light` entfernen (Bootstrap übernimmt)
7. **Alle Templates** — `text-dark` an farbigen Badges (`bg-warning`, `bg-info`) durch `text-body` ersetzen
8. **log.html, add_media.html** — JS `bg-light` → `bg-body-secondary` in Drag&Drop-Toggling
9. **Tests schreiben** für Toggle-Render + Theme-Cookie (optional)
10. **CHANGELOG + version.py** (minor bump) aktualisieren

### Scope-Entscheidung für V1

- **Minimal (empfohlen):** Schritte 1–5 → funktionaler Toggle, 95% der App sieht korrekt aus
- **Vollständig:** Schritte 1–9 → alle Farbklassen-Hotspots behoben, production-ready
- **V2 (später):** serverseitige Persistenz via User-Model, System-Auto-Detection
