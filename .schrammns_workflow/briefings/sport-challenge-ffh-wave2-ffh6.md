# Briefing: ffh.6 – Retroaktiver Upload: Route + Template

**Epic:** Multimedia-Upload für Aktivitäten (sport-challenge-ffh)
**Issue:** sport-challenge-ffh.6
**Wave:** 2

## Kontext

Wave 1 ist abgeschlossen:
- `ActivityMedia`-Model existiert in `app/models/activity.py`
- `get_media_type()` + `save_upload()` existieren in `app/utils/uploads.py`

## Deine Aufgabe

### 1. Neue Route in app/routes/challenge_activities.py

Lies `app/routes/challenge_activities.py` vollständig. Füge am Ende der Datei (vor dem letzten Funktionsabschluss oder als letzte Route) eine neue Route hinzu:

```python
@bp.route("/<int:activity_id>/media/add", methods=["GET", "POST"])
@login_required
def add_media(activity_id: int) -> str | Response:
    activity = db.session.get(Activity, activity_id)
    if activity is None or activity.user_id != current_user.id:
        flash("Keine Berechtigung.", "danger")
        return redirect(url_for("challenge_activities.my_week"))
    if request.method == "POST":
        media_files = request.files.getlist("media")
        any_saved = False
        for f in media_files:
            if f and f.filename:
                path = save_upload(f)
                if path is None:
                    flash("Ungültiges Dateiformat (erlaubt: JPG, PNG, WebP, MP4, MOV, WebM, max. 50 MB).", "danger")
                    return redirect(request.url)
                db.session.add(ActivityMedia(
                    activity_id=activity.id,
                    file_path=path,
                    media_type=get_media_type(f.filename),
                    original_filename=f.filename,
                    file_size_bytes=0,
                ))
                any_saved = True
        if any_saved:
            db.session.commit()
            flash("Medien erfolgreich hinzugefügt.", "success")
        return redirect(url_for("challenge_activities.activity_detail", activity_id=activity_id))
    return render_template("activities/add_media.html", activity=activity)
```

Stelle sicher dass alle nötigen Imports vorhanden sind (ActivityMedia, get_media_type, save_upload – ggf. schon von ffh.3 ergänzt, falls parallel).

**WICHTIG:** Prüfe die vorhandenen Imports. Falls `ActivityMedia` und `get_media_type` noch nicht importiert sind, ergänze sie.

### 2. Neues Template: app/templates/activities/add_media.html

Erstelle das Template. Schau dir zuerst `app/templates/activities/log.html` an um den Basis-Layout-Extend zu kennen.

```html
{% extends "base.html" %}
{% block title %}Medien hinzufügen{% endblock %}
{% block content %}
<div class="container mt-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2>Medien hinzufügen</h2>
    <a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}"
       class="btn btn-outline-secondary btn-sm">← Zurück zur Aktivität</a>
  </div>

  <div class="card mb-4">
    <div class="card-body">
      <p class="text-muted mb-1">
        {{ activity.activity_date.strftime('%d.%m.%Y') }} –
        {{ activity.sport_type }} –
        {{ activity.duration_minutes }} Min.
      </p>
    </div>
  </div>

  <form method="post" enctype="multipart/form-data">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <div class="mb-3">
      <label class="form-label fw-semibold">Fotos / Videos</label>
      <div id="drop-zone"
           class="border border-2 rounded p-4 text-center text-muted"
           style="cursor:pointer;min-height:120px;border-style:dashed!important">
        <div id="drop-label">
          <span class="fs-5">📎</span><br>
          Dateien hier ablegen oder klicken
        </div>
        <small class="d-block mt-1">JPG, PNG, WebP, MP4, MOV, WebM · max. 50 MB pro Datei</small>
        <input type="file" id="media-input" name="media" multiple
               accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm"
               class="d-none">
      </div>
      <div id="file-list" class="mt-2 small text-muted"></div>
    </div>
    <button type="submit" class="btn btn-primary">Hochladen</button>
    <a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}"
       class="btn btn-outline-secondary ms-2">Abbrechen</a>
  </form>
</div>

<script>
(function () {
  const zone = document.getElementById('drop-zone');
  const input = document.getElementById('media-input');
  const list = document.getElementById('file-list');
  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('bg-light'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('bg-light'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('bg-light');
    input.files = e.dataTransfer.files;
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
{% endblock %}
```

## File Ownership

**Nur diese Dateien ändern/erstellen:**
- `app/routes/challenge_activities.py` (Route anhängen + ggf. Imports)
- `app/templates/activities/add_media.html` (NEU)

## Acceptance Criteria

- [ ] `GET /activities/<id>/media/add` → 200 für Owner
- [ ] Nicht-Owner → 302 Redirect zu my_week
- [ ] Template rendert ohne Fehler
- [ ] Drag-n-Drop Zone ist vorhanden (id="drop-zone")
- [ ] Form hat `enctype="multipart/form-data"` und `name="media"`

## Boundaries

- Nur Owner darf eigene Activity-Medien hochladen (activity.user_id == current_user.id)
- Kein Committen

## Output-Format

RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/routes/challenge_activities.py, app/templates/activities/add_media.html
SUMMARY: <1-2 Sätze>
BLOCKERS: <leer oder Beschreibung>
RESULT_END
