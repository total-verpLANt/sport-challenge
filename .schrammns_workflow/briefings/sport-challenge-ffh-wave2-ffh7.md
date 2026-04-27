# Briefing: ffh.7 – my_week + user_activities Mediavorschau

**Epic:** Multimedia-Upload für Aktivitäten (sport-challenge-ffh)
**Issue:** sport-challenge-ffh.7
**Wave:** 2

## Kontext

Wave 1 abgeschlossen: `ActivityMedia`-Model existiert, `Activity.media` ist eine SQLAlchemy-Relation.

## Deine Aufgabe

### 1. app/templates/activities/my_week.html

Lies die Datei vollständig. Suche den Block mit `activity.screenshot_path` (Zeilen ~78-85).

Ersetze den alten Screenshot-Block:
```html
{% if activity.screenshot_path %}
<div class="mt-2">
  <a href="{{ url_for('static', filename=activity.screenshot_path) }}" target="_blank" rel="noopener">
    <img src="{{ url_for('static', filename=activity.screenshot_path) }}"
         alt="Screenshot" class="img-thumbnail" style="max-height: 80px; max-width: 120px;">
  </a>
</div>
{% endif %}
```

Durch folgenden Block ersetzen:
```html
{% if activity.media %}
  {% set first = activity.media[0] %}
  <div class="mt-2">
    {% if first.media_type == "video" %}
      <a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}"
         class="text-decoration-none">
        <span class="badge bg-secondary">🎥 Video</span>
      </a>
    {% else %}
      <a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}">
        <img src="{{ url_for('static', filename=first.file_path) }}"
             alt="Vorschau" class="img-thumbnail" style="max-height: 80px; max-width: 120px;">
      </a>
    {% endif %}
  </div>
{% elif activity.screenshot_path %}
  <div class="mt-2">
    <a href="{{ url_for('static', filename=activity.screenshot_path) }}" target="_blank" rel="noopener">
      <img src="{{ url_for('static', filename=activity.screenshot_path) }}"
           alt="Screenshot" class="img-thumbnail" style="max-height: 80px; max-width: 120px;">
    </a>
  </div>
{% endif %}
```

### 2. app/templates/activities/user_activities.html

Lies die Datei vollständig. Suche den Block mit `activity.screenshot_path` (Zeilen ~48-55).

Ersetze den alten Screenshot-Block:
```html
{% if activity.screenshot_path %}
<div class="mt-2">
  <a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}">
    <img src="{{ url_for('static', filename=activity.screenshot_path) }}"
         alt="Screenshot" class="img-thumbnail" style="max-height: 80px; max-width: 120px;">
  </a>
</div>
{% endif %}
```

Durch folgenden Block ersetzen:
```html
{% if activity.media %}
  {% set first = activity.media[0] %}
  <div class="mt-2">
    {% if first.media_type == "video" %}
      <a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}"
         class="text-decoration-none">
        <span class="badge bg-secondary">🎥 Video</span>
      </a>
    {% else %}
      <a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}">
        <img src="{{ url_for('static', filename=first.file_path) }}"
             alt="Vorschau" class="img-thumbnail" style="max-height: 80px; max-width: 120px;">
      </a>
    {% endif %}
  </div>
{% elif activity.screenshot_path %}
  <div class="mt-2">
    <a href="{{ url_for('challenge_activities.activity_detail', activity_id=activity.id) }}">
      <img src="{{ url_for('static', filename=activity.screenshot_path) }}"
           alt="Screenshot" class="img-thumbnail" style="max-height: 80px; max-width: 120px;">
    </a>
  </div>
{% endif %}
```

## File Ownership

**Nur diese Dateien ändern:**
- `app/templates/activities/my_week.html`
- `app/templates/activities/user_activities.html`

## Acceptance Criteria

- [ ] `activity.media` wird als primäre Vorschau-Quelle verwendet
- [ ] Bei Video: Badge "🎥 Video" als Link zur Detail-Seite
- [ ] Bei Bild: Thumbnail-img als Link zur Detail-Seite
- [ ] Legacy-`screenshot_path` bleibt als Fallback erhalten
- [ ] Bei keinen Medien und kein screenshot_path: kein Block

## Boundaries

- Kein Committen
- `screenshot_path` als Fallback erhalten

## Output-Format

RESULT_START
STATUS: COMPLETE|BLOCKED|DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/templates/activities/my_week.html, app/templates/activities/user_activities.html
SUMMARY: <1-2 Sätze>
BLOCKERS: <leer oder Beschreibung>
RESULT_END
