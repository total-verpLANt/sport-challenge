# Research: Stored XSS via original_filename im AJAX-Feed-Card-Builder

**Date:** 2026-04-29
**Scope:** dashboard/index.html AJAX-Pfad, challenge_activities.py Upload, dashboard.py Feed-API, uploads.py, alle Templates die original_filename rendern

---

## Executive Summary

- **Bestätigte Stored-XSS-Lücke** in `app/templates/dashboard/index.html:248`: Die JS-Funktion `esc()` escaped keine doppelten Anführungszeichen (`"`); `original_filename` wird per String-Konkatenation in ein `alt="..."`-Attribut eingebaut → Attribut-Breakout möglich.
- **Wurzel in der Persistenzschicht**: `f.filename` (Browser-Rohwert) wird ohne Sanitierung gespeichert (`app/routes/challenge_activities.py:109, 127, 482`); `werkzeug.utils.secure_filename` wird im gesamten Projekt nicht eingesetzt.
- **Server-Side-Rendering ist sicher**: Alle Jinja2-Ausgaben von `original_filename` nutzen Auto-Escape → kein XSS auf SSR-Pfaden.
- **Weitere Risiken gering, aber beachtenswert**: `file_path` in `src`-Attribut (aktuell sicher, fragiles Pattern), Self-XSS via Drag-Drop-Preview (kein Cross-User-Impact), `data-csrf`-Attribut (CSRF-Token ist sicher, aber gleiches fragile Pattern).
- **Empfohlener Fix (Option A)**: DOM-API statt innerHTML-Konkatenation für Image/Video-Karten im AJAX-Card-Builder.
- **Empfohlener Fix (Option B, Defense-in-Depth)**: `secure_filename()` oder Regex-Strip bei Upload-Speicherung als zweite Verteidigungslinie.

---

## Key Files

| File | Purpose |
|------|---------|
| `app/templates/dashboard/index.html` | AJAX-Feed-Card-Builder + `esc()`-Definition + SSR-Feed |
| `app/routes/challenge_activities.py` | Upload-Routes: `log_submit` (`:109`), `add_media` (`:482`) |
| `app/routes/dashboard.py` | JSON-Feed-Endpoint: `original_filename` in Response (`:185`) |
| `app/utils/uploads.py` | `save_upload()`: UUID-Pfad, KEIN `secure_filename` |
| `app/models/activity.py` | `ActivityMedia`-Model: `original_filename String(255)` |
| `app/templates/activities/detail.html` | SSR `data-title` + `alt` mit `original_filename` (sicher) |
| `tests/test_activities_log.py` | Alle Upload-Tests – keine XSS-Edge-Cases |
| `tests/test_auth.py` | Einziger XSS-Test im Projekt (nur E-Mail) |

---

## Technology Stack

| Library/Framework | Version (if known) | Role |
|-------------------|--------------------|------|
| Jinja2 | Flask-Default | SSR-Escaping (Auto-Escape aktiv) |
| Flask-Talisman | – | CSP-Header + Nonce-Management |
| werkzeug | Flask-Dependency | `secure_filename()` verfügbar, aber **nicht genutzt** |
| Bootstrap 5.3.3 | 5.3.3 | Frontend-Framework |
| Vanilla JS | – | AJAX-Card-Builder in dashboard/index.html |

---

## Findings

### F-01 · Stored XSS via `original_filename` im AJAX-Pfad (KRITISCH)

**Sink:** `app/templates/dashboard/index.html:248`
```js
mediaHtml += '<img src="' + url + '" alt="' + esc(m.original_filename) + '" class="img-thumbnail" ...>';
```

**Schwachstelle `esc()`:** `app/templates/dashboard/index.html:177-181`
```js
function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s || '');
  return d.innerHTML;   // escaped nur <, >, & — NICHT "
}
```
`textContent → innerHTML`-Roundtrip liefert HTML-Escaping nur für `<`, `>`, `&`. Das doppelte Anführungszeichen `"` wird **nicht** escaped. Das `alt`-Attribut ist doppelt-gequotet → Breakout möglich.

**Source:** `app/routes/challenge_activities.py:109`
```python
saved_media.append((path, get_media_type(f.filename), f.filename))  # f.filename roh
```
`app/routes/challenge_activities.py:127`
```python
original_filename=orig_name   # ungesäubert in DB
```
Zweiter Eintrittspunkt: `app/routes/challenge_activities.py:482` (add_media)

**Transport:** `app/routes/dashboard.py:185`
```python
"original_filename": m.original_filename   # JSON ohne serverseitiges Escape
```

**Exploit-Payload:** Dateiname `photo.jpg" onerror="alert(document.cookie)` → beliebiges JS bei jedem Teilnehmer, der „Mehr laden" klickt.

**Auslöser:** Nur der AJAX-Pfad (ab Eintrag 11, `?page=` > 1). Die ersten 10 Einträge werden via SSR gerendert und sind sicher.

---

### F-02 · `file_path` in `src`-Attribut (GERING, fragiles Pattern)

`app/templates/dashboard/index.html:244-246`
```js
const url = '/static/' + esc(m.file_path);
mediaHtml += '<video src="' + url + '" ...>';
```
`file_path` wird serverseitig als `uploads/<uuid>.<ext>` generiert (`app/utils/uploads.py:27`) – aktuell kein User-Einfluss. Trotzdem gleiche Schwachstelle in `esc()` (kein `"` escape). Kein akutes Risiko, aber fragil wenn Generierungslogik sich ändert.

---

### F-03 · Alle SSR-Ausgaben von `original_filename` sind sicher

| Stelle | Template | Jinja-Ausdruck | Status |
|--------|----------|----------------|--------|
| `:137` | dashboard/index.html | `{{ m.original_filename }}` | ✅ Auto-Escape |
| `:68` | activities/detail.html | `data-title="{{ m.original_filename }}"` | ✅ Auto-Escape |
| `:70` | activities/detail.html | `alt="{{ m.original_filename }}"` | ✅ Auto-Escape |

Keine `| safe`-Filter im gesamten Projekt (verifiziert durch grep). Jinja2 Auto-Escape aktiv (Flask-Default, kein Override in `app/__init__.py`).

---

### F-04 · Self-XSS in Drag-Drop-Vorschau (KEIN Cross-User-Impact)

`app/templates/activities/add_media.html:67-69` und `app/templates/activities/log.html:78-80`:
```js
innerHTML += `<li>${f.name}</li>`;
```
`f.name` kommt vom lokalen `File`-Objekt des Browsers (vor Upload). Self-XSS möglich, aber kein Persistence-XSS und kein anderer User betroffen.

---

### F-05 · `file_size_bytes` wird immer als `0` gespeichert (BUG, off-topic aber bemerkenswert)

`app/routes/challenge_activities.py:128` und `:483`:
```python
file_size_bytes=0   # TODO: real size
```
Kein Test deckt diesen Bug auf.

---

### F-06 · Dokumentations-Lücke: esc()-Strategie nicht architektonisch abgesichert

Der Plan I-01 (`2026-04-26-security-fixes-xss-email-validation.md:29`) fordert `|tojson` als Standard für alle Inline-JS-Handler. Der AJAX-Feed-Card-Builder nutzt stattdessen eine selbstgebaute `esc()`-Funktion ohne Begründung – diese Abweichung ist in keiner ADR dokumentiert.

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| `esc()`-Implementierung | 4 | Vollständig gelesen, Verhalten klar |
| AJAX-Card-Builder (`dashboard/index.html`) | 4 | Alle innerHTML-Stellen analysiert |
| Upload-Persistierung (`challenge_activities.py`) | 4 | Beide Eintrittspunkte verifiziert |
| JSON-Feed-Endpoint (`dashboard.py`) | 3 | Ausgabepfad klar, keine tiefen Query-Checks |
| SSR-Templates | 3 | Alle `original_filename`-Stellen gefunden, Auto-Escape bestätigt |
| CSP-Konfiguration | 2 | Bekannt via vorherige Research; nicht neu verifiziert |
| Test-Coverage | 4 | Vollständig inventarisiert, alle Lücken dokumentiert |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| MIME-Type-Validierung serverseitig | nice-to-have | Magic-Byte-Check via `python-magic` prüfen |
| Nonce-Rotation pro Request testen | nice-to-have | Response-Header in Pytest prüfen |
| Ob GLightbox `data-title` auch client-seitig nutzt | nice-to-have | GLightbox-Source auf innerHTML-Zugriff prüfen |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Jinja2 Auto-Escape ist global aktiv | Yes | `app/__init__.py` + Research `2026-04-26` |
| `secure_filename` wird nicht genutzt | Yes | grep im gesamten Projekt – kein Treffer |
| CSP blockiert `unsafe-inline` scripts | Yes | `app/__init__.py:19` laut vorheriger Research |
| `esc()` nutzt `textContent→innerHTML` Roundtrip | Yes | `dashboard/index.html:177-181` direkt gelesen |
| AJAX-Feed startet ab Eintrag 11 (page > 0) | Yes | SSR rendert erste 10, AJAX lädt Rest |

---

## Recommendations

### Fix 1 (SOFORT · Option A – DOM-API, bevorzugt)
`app/templates/dashboard/index.html:240-260`: Image- und Video-Elemente via `document.createElement()` + Property-Assignment erstellen. Der Browser escaped Attribute automatisch – kein `"` kann ausbrechen.

```js
// Statt: mediaHtml += '<img alt="' + esc(m.original_filename) + '" ...>';
const img = document.createElement('img');
img.alt = m.original_filename;   // Browser escaped automatisch
img.className = 'img-thumbnail ...';
img.src = '/static/' + m.file_path;
mediaEl.appendChild(img);
```

### Fix 2 (SOFORT · Option B – Defense-in-Depth)
`app/routes/challenge_activities.py:109` und `:482`: `werkzeug.utils.secure_filename(f.filename)` vor Persistierung anwenden. Eliminiert `"`, `<`, `>`, Pfad-Separatoren aus dem gespeicherten Klartextnamen.

**Empfehlung:** Beide Fixes zusammen implementieren – Option A schützt den Render-Pfad, Option B die Datenpipeline. Separate Commits (atomare Arbeitsweise).

### Fix 3 (Mittelfristig · Tests)
Mindestens folgende Test-Szenarien zu `tests/test_activities_log.py` hinzufügen:
- Upload mit `original_filename` enthält `"` → DB-Eintrag und Feed-Response prüfen
- Upload mit `"><script>alert(1)</script>.jpg` → Response enthält kein ungescaptes `<script>`
- CSP-Header-Smoke-Test für `/dashboard/` Response

### Fix 4 (Nice-to-have)
`esc()` in `dashboard/index.html` um `"` und `'` escaping erweitern oder durch `DOMPurify` ersetzen, als Fallback-Schutz für alle zukünftigen innerHTML-Verwendungen.
