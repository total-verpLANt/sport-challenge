# Research: Upload-Bugs – Drag-Drop & Klick in Drop-Zone

**Date:** 2026-04-28
**Scope:** `app/templates/activities/log.html`, `app/templates/activities/add_media.html`, `app/__init__.py` (CSP), `app/templates/base.html`

---

## Executive Summary

- **Hauptfehler (Bug 0 – CSP-Nonce fehlt):** Die `<script>`-Blöcke in `log.html` und `add_media.html` tragen kein `nonce`-Attribut. Die CSP (Flask-Talisman, `script-src` mit Nonce-Mode) blockiert deshalb **sämtliches** inline JavaScript dieser Seiten → Klick und Drag-Drop tun buchstäblich nichts.
- **Bug 1 – Click-Bubbling:** `input.click()` löst ein Klick-Event aus, das durch das DOM zur Zone bubbelt und erneut `input.click()` aufruft. Moderne Browser brechen den Loop intern ab, aber das Verhalten ist instabil und der Dialog kann sofort geschlossen werden.
- **Bug 2 – `input.files`-Zuweisung:** Direkte Zuweisung `input.files = e.dataTransfer.files` funktioniert in Chrome 73+, Firefox 66+, Safari 14.1+, schlägt aber in älteren Safari-Versionen und WebViews lautlos fehl. Außerdem wird kein `change`-Event gefeuert.
- **Bug 3 – Kein document-level Drop-Guard:** Landet die Datei außerhalb der Drop-Zone, navigiert der Browser zum Bild/Video → Formulardaten gehen verloren.
- **Empfehlung:** Bug 0 zuerst fixen (ein Attribut, sofortiger Effekt), dann Bugs 1–3 im selben Commit.

---

## Key Files

| File | Purpose |
|------|---------|
| `app/templates/activities/log.html` | Aktivität eintragen + Drop-Zone JS (Z. 42–64) |
| `app/templates/activities/add_media.html` | Retroaktiver Upload + Drop-Zone JS (Z. 44–66) |
| `app/__init__.py` | Flask-Talisman CSP-Konfiguration (Z. 17–29) |
| `app/templates/base.html` | Globaler Script-Block mit `nonce="{{ csp_nonce() }}"` (Z. 91–100) |
| `app/utils/uploads.py` | Server-seitige Upload-Logik |
| `app/routes/challenge_activities.py` | Routen `log_submit` (Z. 53–127), `add_media` (Z. 456–484) |

---

## Technology Stack

| Library/Framework | Version | Role |
|-------------------|---------|------|
| Flask-Talisman | — | CSP-Header, Nonce-Generierung |
| Bootstrap | 5.3.3 | CSS-Framework, `d-none` für hidden Input |
| Vanilla JS | ES2020 | Drop-Zone-Handler, keine externe Lib |
| HTML5 Drag-and-Drop API | — | `dragover`, `dragleave`, `drop` Events |
| `DataTransfer` API | — | FileList-Manipulation in Drop-Handler |

---

## Findings

### Bug 0 — CSP-Nonce fehlt (HAUPTFEHLER) ⚠️

**Root Cause:**

`app/__init__.py:27` konfiguriert Talisman mit:
```python
content_security_policy_nonce_in=["script-src"]
```

Das bewirkt, dass Talisman bei jedem Request einen zufälligen Nonce generiert und ihn dem `script-src`-Header anhängt, z. B.:
```
Content-Security-Policy: script-src 'self' cdn.jsdelivr.net 'nonce-abc123'
```

Der Browser erlaubt dann **nur** `<script>`-Tags mit passendem `nonce="abc123"`. Inline-Scripts ohne Nonce werden **verworfen** – kein Fehler, keine Ausführung, stillesScheitern.

`base.html:91` hat den Nonce korrekt:
```html
<script nonce="{{ csp_nonce() }}">
```

`log.html:42` und `add_media.html:44` haben ihn **nicht**:
```html
<script>
```
→ Browser blockiert das gesamte Drop-Zone-Skript. Klick und Drag-Drop tun nichts.

**Fix:** Nonce-Attribut zu beiden `<script>`-Tags hinzufügen.

---

### Bug 1 — Click-Bubbling-Loop

**Datei/Zeilen:** `log.html:31,47` | `add_media.html:31,49`

Das `<input type="file" id="media-input" class="d-none">` liegt **innerhalb** des `#drop-zone`-Divs (Z. 25–34 / Z. 23–34).

```javascript
zone.addEventListener('click', () => input.click()); // log.html:47
```

Event-Flow:
1. Nutzer klickt Zone
2. Handler ruft `input.click()` auf
3. Der synthetische Click-Event des Inputs **bubblet** zur Zone hoch
4. Zone-Handler ruft erneut `input.click()` auf

Moderne Browser schützen dagegen über ein internes „click in progress"-Flag (HTML-Spec), aber das Verhalten ist browser-abhängig: Dialog kann sofort schließen oder sich seltsam verhalten.

**Fix:** Propagation auf dem Input stoppen:
```javascript
input.addEventListener('click', e => e.stopPropagation());
```

---

### Bug 2 — `input.files` Zuweisung & kein `change`-Event

**Datei/Zeilen:** `log.html:53` | `add_media.html:55`

```javascript
input.files = e.dataTransfer.files; // direkte FileList-Zuweisung
```

**Browser-Kompatibilität:**
- Chrome 73+, Firefox 66+, Safari 14.1+: ✅ funktioniert
- Ältere Safari (<14.1) / WKWebView: ❌ silently no-op → Formular ohne Dateien abgeschickt
- Safari war der letzte Browser, der den `DataTransfer`-Konstruktor in 14.1 implementierte

**Weiteres Problem:** Die Zuweisung feuert kein `change`-Event. Da `renderList()` im `drop`-Handler manuell aufgerufen wird, ist das im aktuellen Code harmlos – aber fragil.

**Fix:** DataTransfer-Workaround + manuelles `change`-Event:
```javascript
const dt = new DataTransfer();
for (const file of e.dataTransfer.files) dt.items.add(file);
input.files = dt.files;
input.dispatchEvent(new Event('change', { bubbles: true }));
```

---

### Bug 3 — Kein document-level Drop-Guard (Datenverlust)

**Datei:** `base.html` (fehlt), `log.html`, `add_media.html`

Fällt eine Datei **außerhalb** der Drop-Zone (z. B. auf den Seiten-Hintergrund), hat kein Element `e.preventDefault()` auf `dragover`/`drop` registriert → Browser-Default: Datei im Tab öffnen → Seite verlässt das Formular → Formulardaten (Datum, Dauer, Sportart) verloren.

**Fix in `base.html`** (global für alle Seiten, im existierenden Nonce-Script-Block):
```javascript
['dragover', 'drop'].forEach(ev =>
  document.addEventListener(ev, e => e.preventDefault())
);
```

---

### Nebenbeobachtung — `dragleave` verbessern

Aktuell:
```javascript
zone.addEventListener('dragleave', () => zone.classList.remove('bg-light'));
```
Verlässt der Cursor ein **Kind-Element** (z. B. den `<span>`), feuert `dragleave` auf der Zone, obwohl der Cursor noch innerhalb ist → Highlighting flackert.

**Fix:**
```javascript
zone.addEventListener('dragleave', e => {
  if (!zone.contains(e.relatedTarget)) zone.classList.remove('bg-light');
});
```

---

## Vollständiger korrigierter JS-Block

Beide Templates erhalten diesen identischen Block (mit Nonce):

```html
<script nonce="{{ csp_nonce() }}">
(function () {
  const zone  = document.getElementById('drop-zone');
  const input = document.getElementById('media-input');
  const list  = document.getElementById('file-list');

  input.addEventListener('click', e => e.stopPropagation()); // Bug 1 Fix
  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('bg-light'); });
  zone.addEventListener('dragleave', e => {                   // verbessertes dragleave
    if (!zone.contains(e.relatedTarget)) zone.classList.remove('bg-light');
  });
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('bg-light');
    const dt = new DataTransfer();                            // Bug 2 Fix
    for (const file of e.dataTransfer.files) dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    renderList();
  });
  input.addEventListener('change', renderList);

  function renderList() {
    const files = [...input.files];
    list.innerHTML = files.length
      ? files.map(f => `<span class="badge bg-secondary me-1">${f.name} (${(f.size/1024/1024).toFixed(1)} MB)</span>`).join('')
      : '';
  }
})();
</script>
```

`base.html` erhält im existierenden Nonce-Script-Block (Z. 91–100):
```javascript
// Bug 3 Fix: verhindert Browser-Navigation bei Drop außerhalb der Zone
['dragover', 'drop'].forEach(ev =>
  document.addEventListener(ev, e => e.preventDefault())
);
```

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| CSP-Nonce-Konfiguration (Talisman) | 4 | Vollständig nachvollzogen, Quelle: `__init__.py:17-29` + Talisman-Docs |
| HTML5 Drag-and-Drop Event-Flow | 4 | Bubbling-Verhalten verifiziert, Browser-Spec konsultiert |
| `input.files` Browser-Kompatibilität | 3 | MDN + Bugzilla-Einträge bestätigen; keine Live-Browser-Tests |
| document-level Drop-Guard | 3 | Logisch klar, Browser-Verhalten aus Spec abgeleitet |
| Test-Abdeckung (Backend) | 3 | Alle Test-Dateien gelesen, Lücken katalogisiert |
| Test-Abdeckung (Frontend/JS) | 1 | Null JS-Tests vorhanden; kein Playwright-Projekt |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Live-Browser-Test aller 4 Fixes | must-fill | Playwright-Sub-Agent nach Fix ausführen |
| Verhalten auf Safari < 14.1 / iOS WKWebView | nice-to-have | Manueller Test oder Browserstack |
| 50 MB-Limit server-seitig nicht durchgesetzt | must-fill | `save_upload()` erweitern oder Flask-Validator; eigenes Issue |
| `file_size_bytes` ist immer 0 gespeichert | nice-to-have | Eigenes Issue anlegen |
| `original_filename` XSS (wird in Templates ausgegeben) | nice-to-have | Jinja2-Autoescaping prüfen (aktuell vermutlich safe) |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Talisman mit Nonce blockiert Scripts ohne Nonce | Yes | `__init__.py:27` + MDN CSP-Spec |
| `base.html:91` nutzt Nonce korrekt | Yes | Template gelesen (`nonce="{{ csp_nonce() }}"`) |
| `log.html` und `add_media.html` haben keinen Nonce | Yes | Templates gelesen, `<script>` ohne Attribut |
| Kein anderer JS-Code überbrückt den Fehler | Yes | `app/static/` existiert nicht; kein externes JS-Bundle |
| DataTransfer-Zuweisung funktioniert in Projekt-Zielgruppe (Desktop-Browser) | Partial | MDN + Bugzilla belegen Chrome 73+, Firefox 66+, Safari 14.1+ |

---

## Recommendations

**Priorität 1 – Sofort (Bug 0, ein Commit):**
1. `log.html:42`: `<script>` → `<script nonce="{{ csp_nonce() }}">`
2. `add_media.html:44`: gleiche Änderung
3. Gleichzeitig Bugs 1–3 im selben Commit fixen (sind ohnehin nicht testbar ohne Bug 0)
4. `base.html:91–99`: document-level dragover/drop Guard im bestehenden Nonce-Block ergänzen

**Priorität 2 – Nächste Session (eigene Issues):**
- 50 MB-Limit server-seitig in `save_upload()` erzwingen
- `file_size_bytes` korrekt befüllen (aus `f.seek(0, 2)` + `f.tell()`)
- Playwright-Test für Drop-Zone nach dem Fix

---

## Quellen

- [MDN: HTMLInputElement.files](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/files)
- [MDN: DataTransfer](https://developer.mozilla.org/en-US/docs/Web/API/DataTransfer)
- [Mozilla Bugzilla #757664: Make files attribute writable](https://bugzilla.mozilla.org/show_bug.cgi?id=757664)
- [Flask-Talisman GitHub](https://github.com/GoogleCloudPlatform/flask-talisman)
- [PQINA: How to set the value of a file input](https://pqina.nl/blog/set-value-to-file-input/)
