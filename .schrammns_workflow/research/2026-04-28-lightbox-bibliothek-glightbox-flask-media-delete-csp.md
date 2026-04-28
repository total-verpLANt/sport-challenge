# Research: Lightbox-Bibliothek + Flask Media-Delete

**Date:** 2026-04-28
**Scope:** Lightbox-Integration (GLightbox vs. Alternativen) + Per-Media-Delete-Route in sport-challenge
**Depth:** deep
**Semantic Analysis:** Degraded – Serena MCP nicht verfügbar; Fallback über Read/Grep/Bash

---

## Executive Summary

- **GLightbox ist die richtige Wahl**: Vanilla JS, kein npm, CDN via `cdn.jsdelivr.net` (bereits in CSP whitelisted), guter Video-Support für lokale Dateien, minimale Integration. Das GitHub-Issue #402 (CSP-Nonce) betrifft nur Strict-Dynamic-CSPs – unser Host-Whitelist-Ansatz ist nicht betroffen.
- **CSP-Anpassung minimal**: `script-src` und `style-src` erlauben bereits `cdn.jsdelivr.net`. Das GLightbox-Init-Script ist inline und braucht `nonce="{{ csp_nonce() }}"`. Kein weiterer CSP-Edit nötig.
- **Delete-Route** folgt exakt dem etablierten Muster aus `delete_activity` und `add_media`: `@login_required`, Owner-Check via `activity.user_id != current_user.id`, dann zusätzlicher Check `media.activity_id != activity_id`. Disk-Delete vor DB-Delete.
- **UI-Muster** für Delete existiert bereits: Mini-POST-Form mit `csrf_token` + `data-confirm` (my_week.html:104–110). Kann direkt übernommen werden.
- **Keine neuen Tests-Muster nötig**: Alle Fixtures und Hilfsfunktionen für ActivityMedia-Tests existieren in `test_activities_log.py`. Drei neue Tests reichen (happy path, non-owner, media-not-found).

---

## Key Files

| File | Purpose |
|------|---------|
| `app/__init__.py` | Talisman CSP-Konfiguration (Z. 17–29) |
| `app/templates/base.html` | CDN-Einbindung, Nonce-Script-Block (Z. 88–101) |
| `app/templates/activities/detail.html` | Medien-Galerie, zu erweitern |
| `app/routes/challenge_activities.py` | delete_activity (Z. 367), add_media (Z. 456) – Muster für neue Route |
| `app/models/activity.py` | ActivityMedia-Modell (Z. 39–53) |
| `app/utils/uploads.py` | delete_upload() (Z. 35–44), delete_media_files() (Z. 47–50) |
| `app/templates/activities/my_week.html` | Vorhandenes Delete-Button-Muster (Z. 104–110) |
| `tests/test_activities_log.py` | ActivityMedia-Testmuster (Z. 338–413) |

---

## Technology Stack

| Library/Framework | Version | Role |
|-------------------|---------|------|
| GLightbox | 3.x (aktuell 3.0.9+) | Lightbox/Overlay für Bilder |
| Bootstrap | 5.3.3 | CSS-Framework (bereits vorhanden) |
| Flask-Talisman | — | CSP-Header + Nonce-Generierung |
| Flask-WTF (CSRF) | — | CSRF-Schutz für Delete-Route |
| SQLAlchemy 2.x | — | ORM, `db.session.get()` + `db.session.delete()` |

---

## Findings

### 1. CSP-Analyse: Neue CDN-Ressourcen

**`app/__init__.py:17–23` – aktuelle CSP:**

```python
csp = {
    "default-src": "'self'",
    "script-src": "'self' cdn.jsdelivr.net",    # Z. 19
    "style-src":  "'self' 'unsafe-inline' cdn.jsdelivr.net",  # Z. 20
    "img-src":    "'self' data:",               # Z. 21
    "media-src":  "'self'",                     # Z. 22
}
content_security_policy_nonce_in=["script-src"] # Z. 27
```

**Konsequenzen für GLightbox:**
- GLightbox-CSS von `cdn.jsdelivr.net` → `style-src` erlaubt es ✅
- GLightbox-JS von `cdn.jsdelivr.net` → `script-src` erlaubt externe Scripts vom Host ✅ (Nonce nur für inline nötig)
- Init-Script `GLightbox({...})` → inline → **braucht `nonce="{{ csp_nonce() }}"`** ✅ (handhabbar)
- GLightbox generiert zur Laufzeit `<style>`-Elemente → `style-src 'unsafe-inline'` ✅ erlaubt das

**Kein CSP-Edit nötig.** Neue Bibliothek läuft out-of-the-box.

---

### 2. GLightbox vs. Alternativen

| Kriterium | GLightbox 3.x | PhotoSwipe 5 | SimpleLightbox |
|-----------|--------------|-------------|----------------|
| jQuery-Abhängigkeit | keins | keins | keins |
| CDN verfügbar | ✅ jsDelivr | ✅ jsDelivr | ✅ jsDelivr |
| SRI-Hash auf jsDelivr | ✅ | ✅ | ✅ |
| Video (lokale Dateien) | ✅ nativ | ✅ mit Plugin | ⚠️ nur Bilder |
| Bootstrap 5 kompatibel | ✅ | ✅ | ✅ |
| Setup-Aufwand | minimal (1 Klasse) | mittel (HTML-Struktur) | minimal |
| CSP-Nonce-Issue | #402 (nur strict-dynamic) | keins bekannt | keins bekannt |
| Galerie-Navigation | ✅ | ✅ | ✅ |
| Mobile/Touch | ✅ | ✅ (Swipe) | ⚠️ begrenzt |
| Weekly Downloads (npm) | ~200k | ~460k | ~6k |

**Empfehlung: GLightbox**
- Einfachste Integration: `class="glightbox"` + `data-gallery="..."` auf dem `<a>`-Tag
- Video-Support für lokale Dateien (mp4/webm/mov) eingebaut
- Das CSP-Issue #402 (GitHub biati-digital/glightbox) betrifft nur Setups mit `'nonce-xxx'`-only in script-src (kein Host-Whitelist). Unser Setup hat `cdn.jsdelivr.net` whitelisted → External Script lädt ohne Nonce ✅

---

### 3. GLightbox CDN-Integration

**CDN-URLs (jsDelivr):**
```
CSS: https://cdn.jsdelivr.net/npm/glightbox/dist/css/glightbox.min.css
JS:  https://cdn.jsdelivr.net/npm/glightbox/dist/js/glightbox.min.js
```

**Pinned Version empfohlen** (z. B. `glightbox@3.0.9`):
```
CSS: https://cdn.jsdelivr.net/npm/glightbox@3.0.9/dist/css/glightbox.min.css
JS:  https://cdn.jsdelivr.net/npm/glightbox@3.0.9/dist/js/glightbox.min.js
```

**SRI-Hash**: jsDelivr generiert SRI-Hashes per Versionsseite unter https://www.jsdelivr.com/package/npm/glightbox – **vor Implementierung verifizieren und eintragen** (Sicherheitshärtung, wie Bootstrap bereits gemacht).

**Einbindung in `base.html`:**
```html
<!-- im <head> -->
<link href="https://cdn.jsdelivr.net/npm/glightbox@3.0.9/dist/css/glightbox.min.css"
      rel="stylesheet"
      integrity="sha384-HASH"
      crossorigin="anonymous">

<!-- vor </body>, nach Bootstrap-Bundle -->
<script src="https://cdn.jsdelivr.net/npm/glightbox@3.0.9/dist/js/glightbox.min.js"
        integrity="sha384-HASH"
        crossorigin="anonymous"></script>
```

**Init-Script in `{% block scripts %}` des Templates (mit Nonce!):**
```html
{% block scripts %}
<script nonce="{{ csp_nonce() }}">
  GLightbox({ selector: '.glightbox', touchNavigation: true });
</script>
{% endblock %}
```

**Galerie-Link in `detail.html`:**
```html
<a href="{{ url_for('static', filename=m.file_path) }}"
   class="glightbox"
   data-gallery="activity-media"
   data-title="{{ m.original_filename }}">
  <img src="..." class="img-fluid rounded w-100" style="max-height:200px;object-fit:cover">
</a>
```

---

### 4. Delete-Route: Design

**Neue Route:**
```
POST /challenge-activities/<activity_id>/media/<media_id>/delete
```

**Owner-Check-Muster** (identisch zu `delete_activity:371` und `add_media:460`):
```python
activity = db.session.get(Activity, activity_id)
if activity is None or activity.user_id != current_user.id:
    flash("Keine Berechtigung.", "danger")
    return redirect(url_for("challenge_activities.my_week"))

media = db.session.get(ActivityMedia, media_id)
if media is None or media.activity_id != activity_id:
    flash("Medium nicht gefunden.", "warning")
    return redirect(url_for("challenge_activities.activity_detail", activity_id=activity_id))
```

**Wichtig**: Doppelter Check (1) Activity gehört dem User, (2) Media gehört zur Activity. Ohne Check 2 könnte ein Owner einer anderen Aktivität fremde Medien löschen.

**Disk → DB-Reihenfolge** (wie `delete_activity:375–380`):
```python
delete_upload(media.file_path)   # Disk zuerst
db.session.delete(media)         # DB danach
db.session.commit()
```

---

### 5. Delete-UI: Template-Muster

Bestehendes Pattern aus `my_week.html:104–110`:
```html
<form method="post"
      action="{{ url_for('challenge_activities.delete_activity', activity_id=activity.id) }}"
      data-confirm="Aktivität wirklich löschen?"
      class="d-inline">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit" class="btn btn-outline-danger btn-sm">Löschen</button>
</form>
```

Für Einzel-Medium (in der Galerie als Overlay-Button):
```html
{% if is_owner %}
<form method="post"
      action="{{ url_for('challenge_activities.delete_media', activity_id=activity.id, media_id=m.id) }}"
      data-confirm="Dieses Medium löschen?"
      class="position-absolute top-0 end-0 m-1">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit" class="btn btn-danger btn-sm py-0 px-1" title="Löschen">×</button>
</form>
{% endif %}
```
Wrapper-Div braucht `position-relative` (Bootstrap-Klasse).

---

### 6. Test-Muster für neue Route

Aus `test_activities_log.py:389–413` (non-owner redirect):
```python
# Fixture-Muster für ActivityMedia:
from app.models.activity import ActivityMedia
media = ActivityMedia(
    activity_id=activity.id,
    file_path="uploads/test.jpg",
    media_type="image",
    original_filename="test.jpg",
    file_size_bytes=0,
)
db.session.add(media)
db.session.commit()

# Delete POST:
resp = client.post(f"/challenge-activities/{activity.id}/media/{media.id}/delete",
                   follow_redirects=False)
assert resp.status_code == 302
# Verifizieren dass Medium weg ist:
result = db.session.get(ActivityMedia, media.id)
assert result is None
```

Benötigte Tests:
1. `test_delete_media_happy_path` – Owner löscht eigenes Medium → 302, DB-Row weg
2. `test_delete_media_non_owner` – Fremder User → Redirect zu my_week
3. `test_delete_media_wrong_activity` – media.activity_id ≠ activity_id → Redirect zu detail

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| CSP-Kompatibilität GLightbox | 4 | Vollständig: CSP-Dict gelesen, Issue #402 analysiert, Konsequenzen klar |
| GLightbox API & Integration | 3 | Dokumentation + CDN-URLs klar; kein Live-Test |
| Delete-Route-Muster (Flask) | 4 | Identisches Muster 2× im Code vorhanden, vollständig nachvollzogen |
| Delete-UI-Muster (Template) | 4 | Exakt gleiches Muster in my_week.html vorhanden |
| Test-Muster für neue Route | 3 | Fixtures klar; kein Disk-Mock vorhanden (tests schreiben in tmp-Verzeichnis) |
| GLightbox Video-Support | 2 | Dokumentation sagt "ja", kein Live-Test lokaler Videos |
| SRI-Hash GLightbox | 1 | URL bekannt, Hash muss vor Implementierung abgerufen werden |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| SRI-Hash für GLightbox 3.0.9 | must-fill | jsDelivr-Seite aufrufen vor Implementierung |
| Exakte GLightbox-Version (latest stable) | must-fill | npmjs.com/package/glightbox prüfen |
| Verhalten von GLightbox bei lokalen Videos (mp4) | nice-to-have | Playwright-Test nach Integration |
| `delete_upload()` bei Test: Datei existiert nicht (file not found) | nice-to-have | uploads.py:43 – `unlink()` prüft `exists()` vorher ✅ bereits sicher |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| External scripts von cdn.jsdelivr.net laden ohne Nonce | Yes | base.html:88–90 (Bootstrap-Bundle ohne Nonce, läuft) |
| GLightbox generiert keine `<script>`-Elemente für lokale Dateien | Partial | GitHub-Issue nur bei YouTube/Vimeo erwähnt; lokale Dateien via `<video>` |
| `style-src 'unsafe-inline'` erlaubt GLightbox-Style-Injection | Yes | app/__init__.py:20 |
| `data-confirm`-Handler in base.html funktioniert für Media-Delete-Forms | Yes | base.html:92–95 – Handler ist global für alle `[data-confirm]`-Forms |
| `delete_upload()` ist sicher bei nicht-existierender Datei | Yes | uploads.py:42–43 – `if path.exists(): path.unlink()` |

---

## Recommendations

### Implementierungsreihenfolge (ein Epic, 3 atomare Commits)

**Commit 1 – GLightbox CDN + Basis-Integration:**
- `base.html`: GLightbox CSS im `<head>`, JS vor `</body>`
- `detail.html`: `<a class="glightbox" data-gallery="...">` um Bilder; Videos bleiben `<video controls>`
- `detail.html`: `{% block scripts %}` mit GLightbox-Init (Nonce!)
- SRI-Hash vor Commit von jsDelivr eintragen

**Commit 2 – Delete-Route:**
- `challenge_activities.py`: `delete_media(activity_id, media_id)` Route
- `detail.html`: Delete-Button (position-relative Wrapper, position-absolute Button), nur für `is_owner`

**Commit 3 – Tests:**
- `tests/test_activities_log.py`: 3 neue Tests für delete_media

---

## Quellen

- [GLightbox GitHub – biati-digital/glightbox](https://github.com/biati-digital/glightbox)
- [GLightbox CSP-Issue #402](https://github.com/biati-digital/glightbox/issues/402)
- [GLightbox jsDelivr CDN](https://www.jsdelivr.com/package/npm/glightbox)
- [GLightbox Dokumentation](https://biati-digital.github.io/glightbox/)
- [npm-compare: glightbox vs photoswipe vs simplelightbox](https://npm-compare.com/glightbox,lightbox2,lightgallery.js,magnific-popup,photoswipe,viewerjs)
- [MDN: Content-Security-Policy script-src](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/script-src)
