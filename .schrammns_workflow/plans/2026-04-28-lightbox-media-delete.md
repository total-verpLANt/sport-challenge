# Plan: Lightbox + Einzelnes Medium löschen

**Erstellt:** 2026-04-28
**Research:** `.schrammns_workflow/research/2026-04-28-lightbox-bibliothek-glightbox-flask-media-delete-csp.md`
**Ziel:** Bilder öffnen als Overlay (GLightbox), einzelne Medien löschbar machen

---

## Baseline (verifiziert)

| Metrik | Wert | Befehl |
|--------|------|--------|
| Zu ändernde Dateien | 4 | `ls` |
| LOC challenge_activities.py | 484 | `wc -l` |
| LOC detail.html | 99 | `wc -l` |
| LOC base.html | 106 | `wc -l` |
| Tests test_activities_log.py | 14 (alle grün) | `pytest -q` |
| Per-Media-Delete-Route | nicht vorhanden | `grep delete_media` → leer |
| GLightbox-Version | 3.3.1 (latest) | jsDelivr API |

---

## Files to Modify

| File | Change | Issue |
|------|--------|-------|
| `app/templates/base.html` | GLightbox CSS + JS CDN-Tags | I-01 |
| `app/routes/challenge_activities.py` | Neue Route `delete_media()` | I-02 |
| `app/templates/activities/detail.html` | Lightbox-Links + Delete-Button | I-03 |
| `tests/test_activities_log.py` | 3 neue Tests für delete_media | I-04 |

---

## Design Decisions

| Entscheidung | Gewählt | Abgelehnt | Begründung |
|-------------|---------|-----------|------------|
| Lightbox-Bibliothek | GLightbox 3.3.1 | PhotoSwipe, SimpleLightbox | CDN jsdelivr.net bereits in CSP, Video-Support, minimale Integration |
| CSP-Anpassung | keine nötig | `unsafe-inline` für scripts | cdn.jsdelivr.net whitelisted; inline Init braucht Nonce |
| Delete-UI | Mini-Form + data-confirm | AJAX/Fetch | Konsistent mit bestehendem delete_activity-Muster (my_week.html:104) |
| SRI-Hashes | eingetragen (3.3.1) | ohne SRI | Talisman-Härtung, wie Bootstrap bereits gemacht |
| Videos im Lightbox | ausgelassen | GLightbox Video-Overlay | `<video controls>` bleibt inline; Overhead nicht nötig |

---

## Boundaries

**Always:**
- `nonce="{{ csp_nonce() }}"` auf JEDEM neuen inline `<script>`-Tag
- Doppelter Owner-Check: Activity gehört User UND Media gehört Activity
- Disk-Delete (`delete_upload`) vor DB-Delete (`db.session.delete`)
- SRI-Hashes (`integrity=`) auf allen CDN-Tags

**Never:**
- Kein `target="_blank"` mehr auf Bild-Links (Lightbox ersetzt das)
- Kein 403-Status-Code – bestehende Pattern nutzen Flash + Redirect

---

## Waves

### Wave 1 – Unabhängige Änderungen (parallel)

**I-01** und **I-02** berühren keine gemeinsamen Dateien → können parallel ausgeführt werden.

### Wave 2 – Template (abhängig von I-01 + I-02)

**I-03** setzt voraus, dass GLightbox CDN geladen wird (I-01) und die delete_media-Route URL-reversierbar ist (I-02).

### Wave 3 – Tests (abhängig von I-02)

**I-04** testet die neue Route aus I-02.

---

## Issues

### I-01 – GLightbox CDN in base.html einbinden [Wave 1]

**Typ:** task | **Priorität:** 2 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok

**Was:** GLightbox 3.3.1 CSS und JS als CDN-Tags in `base.html` einbinden.

**Implementierung:**

`app/templates/base.html` – im `<head>` nach Bootstrap-CSS (Z. 10):
```html
<link href="https://cdn.jsdelivr.net/npm/glightbox@3.3.1/dist/css/glightbox.min.css"
      rel="stylesheet"
      integrity="sha384-GPAzSuZc0kFvdIev6wm9zg8gnafE8tLso7rsAYQfc9hAdWCpOcpcNI5W9lWkYcsd"
      crossorigin="anonymous">
```

`app/templates/base.html` – nach Bootstrap-JS-Bundle (Z. 90):
```html
<script src="https://cdn.jsdelivr.net/npm/glightbox@3.3.1/dist/js/glightbox.min.js"
        integrity="sha384-MZZbZ6RXJudK43v1qY1zOWKOU2yfeBPatuFoKyHAaAgHTUZhwblRTc9CphTt4IGQ"
        crossorigin="anonymous"></script>
```

**Kein Init-Script hier** – Init erfolgt template-spezifisch via `{% block scripts %}`.

**Akzeptanzkriterien:**
- `base.html` enthält beide CDN-Tags mit korrekten `integrity`-Attributen
- `style-src cdn.jsdelivr.net` in CSP erlaubt CSS ✅ (keine CSP-Änderung nötig)
- `script-src cdn.jsdelivr.net` in CSP erlaubt JS ✅ (keine CSP-Änderung nötig)

**Verifikation:**
```bash
grep -c "glightbox" app/templates/base.html  # erwartet: 2
```

---

### I-02 – `delete_media`-Route in challenge_activities.py [Wave 1]

**Typ:** feature | **Priorität:** 2 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok

**Was:** Neue Route zum Löschen eines einzelnen `ActivityMedia`-Eintrags, inklusive Disk-Cleanup.

**Implementierung:**

`app/routes/challenge_activities.py` – neue Funktion nach `add_media` (nach Z. 484):

```python
@challenge_activities_bp.route(
    "/<int:activity_id>/media/<int:media_id>/delete", methods=["POST"]
)
@login_required
def delete_media(activity_id: int, media_id: int):
    activity = db.session.get(Activity, activity_id)
    if activity is None or activity.user_id != current_user.id:
        flash("Keine Berechtigung.", "danger")
        return redirect(url_for("challenge_activities.my_week"))

    media = db.session.get(ActivityMedia, media_id)
    if media is None or media.activity_id != activity_id:
        flash("Medium nicht gefunden.", "warning")
        return redirect(
            url_for("challenge_activities.activity_detail", activity_id=activity_id)
        )

    delete_upload(media.file_path)
    db.session.delete(media)
    db.session.commit()

    flash("Medium wurde gelöscht.")
    return redirect(
        url_for("challenge_activities.activity_detail", activity_id=activity_id)
    )
```

**Wiederverwendete Symbole:**
- `delete_upload` – bereits importiert in Z. 13
- `ActivityMedia` – bereits importiert in Z. 9
- Owner-Check-Muster – identisch zu `delete_activity` (Z. 370–373) und `add_media` (Z. 459–462)

**Akzeptanzkriterien:**
- Route `/<activity_id>/media/<media_id>/delete` ist POST-only
- Owner-Check: Activity gehört `current_user.id` (sonst → my_week)
- Media-Check: `media.activity_id == activity_id` (sonst → detail)
- `delete_upload()` wird vor `db.session.delete()` aufgerufen
- Nach Commit: Redirect zu `activity_detail`

**Verifikation:**
```bash
grep -n "def delete_media" app/routes/challenge_activities.py  # erwartet: 1 Treffer
```

---

### I-03 – detail.html: Lightbox-Links + Delete-Button [Wave 2]

**Typ:** feature | **Priorität:** 2 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Abhängig von:** I-01 (GLightbox geladen), I-02 (delete_media-URL auflösbar)

**Was:** Bilder in der Galerie werden zu GLightbox-Links, Videos bleiben inline. Owner sieht Delete-Button pro Medium. GLightbox wird im `{% block scripts %}`-Block initialisiert.

**Implementierung:**

`app/templates/activities/detail.html` – Galerie-Schleife (aktuell Z. 54–67) ersetzen:

```html
{% for m in activity.media %}
<div class="col-6 col-md-4 position-relative">
  {% if m.media_type == "video" %}
  <video src="{{ url_for('static', filename=m.file_path) }}"
         controls class="img-fluid rounded w-100" style="max-height:200px;object-fit:contain"></video>
  {% else %}
  <a href="{{ url_for('static', filename=m.file_path) }}"
     class="glightbox"
     data-gallery="activity-media"
     data-title="{{ m.original_filename }}">
    <img src="{{ url_for('static', filename=m.file_path) }}"
         alt="{{ m.original_filename }}"
         class="img-fluid rounded w-100" style="max-height:200px;object-fit:cover">
  </a>
  {% endif %}
  {% if is_owner %}
  <form method="post"
        action="{{ url_for('challenge_activities.delete_media', activity_id=activity.id, media_id=m.id) }}"
        data-confirm="Dieses Medium wirklich löschen?"
        class="position-absolute top-0 end-0 m-1">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="submit"
            class="btn btn-danger btn-sm py-0 px-1 lh-1"
            title="Medium löschen">&times;</button>
  </form>
  {% endif %}
</div>
{% endfor %}
```

`app/templates/activities/detail.html` – `{% block scripts %}` am Ende (vor `{% endblock %}`):

```html
{% block scripts %}
<script nonce="{{ csp_nonce() }}">
  GLightbox({ selector: '.glightbox', touchNavigation: true });
</script>
{% endblock %}
```

**Zu entfernen:** Das bisherige `<a href="..." target="_blank">` um Bilder (Z. 60–64 der alten Version) – Lightbox ersetzt es.

**Akzeptanzkriterien:**
- Bilder haben `class="glightbox"` und `data-gallery="activity-media"`
- Videos haben kein Lightbox-Attribut, bleiben `<video controls>`
- Delete-Button nur sichtbar wenn `is_owner`
- Delete-Form hat `csrf_token` und `data-confirm`
- `{% block scripts %}` enthält Init mit `nonce="{{ csp_nonce() }}"`
- `position-relative` auf Galerie-Item, `position-absolute` auf Delete-Button

**Verifikation:**
```bash
grep -c "glightbox" app/templates/activities/detail.html  # erwartet: ≥ 3
grep "delete_media" app/templates/activities/detail.html   # erwartet: 1 Treffer
grep "csp_nonce" app/templates/activities/detail.html      # erwartet: 1 Treffer
```

---

### I-04 – Tests für delete_media [Wave 3]

**Typ:** task | **Priorität:** 2 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Abhängig von:** I-02 (Route muss existieren)

**Was:** 3 neue Tests in `tests/test_activities_log.py`.

**Implementierung:**

Muster aus vorhandenen Tests (Z. 358–413) – gleiche Fixture-Funktionen `_create_and_login`, `_create_challenge_with_participation`.

```python
# ActivityMedia für Tests anlegen:
from app.models.activity import ActivityMedia

media = ActivityMedia(
    activity_id=activity.id,
    file_path="uploads/fake_test.jpg",
    media_type="image",
    original_filename="fake_test.jpg",
    file_size_bytes=0,
)
db.session.add(media)
db.session.commit()
```

**Testfunktionen:**

`tests/test_activities_log.py` – 3 neue Funktionen hinzufügen:

- `test_delete_media_happy_path(client, db)`:
  Owner postet zu `/<activity_id>/media/<media_id>/delete` → 302, `db.session.get(ActivityMedia, media_id)` ist `None`

- `test_delete_media_non_owner_redirected(client, db)`:
  User B postet auf Activity von User A → 302 zu `/challenge-activities/my-week` (Flash-Redirect)

- `test_delete_media_wrong_activity(client, db)`:
  Owner postet mit `media_id` einer anderen Activity → 302 zurück zu `activity_detail` (Medium-Check schlägt fehl)

**Akzeptanzkriterien:**
- 3 neue Tests vorhanden
- alle 17 Tests grün (14 bestehend + 3 neue)

**Verifikation:**
```bash
set -a && source .env && set +a
.venv/bin/pytest tests/test_activities_log.py -v -k "delete_media"  # 3 Tests grün
.venv/bin/pytest tests/test_activities_log.py -q                    # 17 Tests grün
```

---

## Rollback-Strategie

| Scope | Strategie |
|-------|-----------|
| Jedes Issue | `git revert <commit>` – alle Änderungen sind rein additiv |
| Gesamter Epic | `git revert HEAD~4..HEAD` |
| Datenbank | Keine Migrationen – kein Schema-Change, kein Rollback nötig |
| Uploaded Files | delete_upload() hinterlässt keine Dateileichen – bei Fehler bleibt Datei auf Disk (unkritisch) |

---

## Invalidierungsrisiken

| Risiko | Betroffenes Issue | Wahrscheinlichkeit |
|--------|------------------|--------------------|
| GLightbox 3.3.1 SRI-Hash veraltet (CDN-Änderung) | I-01 | sehr gering (gepinnte Version) |
| `csp_nonce()` nicht verfügbar in `{% block scripts %}` | I-03 | gering – in anderen Templates bereits genutzt |
| Bootstrap 5.3.3 CSS-Kollision mit GLightbox | I-03 | gering – bekannte Kompatibilität |

---

## Verifikation Gesamtplan

```bash
# Nach allen 4 Issues:
set -a && source .env && set +a

# Tests: alle grün
.venv/bin/pytest tests/test_activities_log.py -q  # 17 passed

# CDN-Tags in base.html
grep -c "glightbox" app/templates/base.html          # 2

# Route registriert
grep "def delete_media" app/routes/challenge_activities.py  # 1 Treffer

# Template-Attribute
grep -c "glightbox" app/templates/activities/detail.html     # ≥ 3
grep "csp_nonce" app/templates/activities/detail.html         # 1 Treffer
```
