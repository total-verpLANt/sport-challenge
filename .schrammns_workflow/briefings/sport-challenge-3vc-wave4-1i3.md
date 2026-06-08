# Briefing: I-07 – my_week.html – SickPeriod-Anzeige und Kürzen

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-1i3

## Context

`my_week()` übergibt jetzt `sick_period` (SickPeriod-Objekt oder None) und `sick_days_val` (int 0-7)
statt dem alten `sick_week`. Das Template muss auf die neuen Variablen umgestellt werden.

## File Ownership

**WRITE:** `app/templates/activities/my_week.html`

## Was zu tun ist

**ZUERST:** Lese `app/templates/activities/my_week.html` komplett.

### 1. Fortschritts-Card (ca. L35–51) – sick_week → sick_period

**Alter Code:**
```html
{% if sick_week %}
  {% set eff_goal = [0, weekly_goal - (sick_week.sick_days // 2)]|max %}
  <strong>{{ fulfilled_days }} von {{ eff_goal }} Tagen</strong> mit mindestens 30 Minuten
  <small class="text-muted">({{ sick_week.sick_days }} Krankentag(e), effektives Ziel)</small>
{% else %}
```

**Neuer Code:**
```html
{% if sick_period %}
  {% set eff_goal = [0, weekly_goal - (sick_days_val // 2)]|max %}
  <strong>{{ fulfilled_days }} von {{ eff_goal }} Tagen</strong> mit mindestens 30 Minuten
  <small class="text-muted">({{ sick_days_val }} Krankentag(e) diese Woche, effektives Ziel)</small>
{% else %}
```

### 2. Progress-Bar (ca. L44–50) – eff_goal kommt aus obiger Berechnung, bleibt unverändert

Nur sicherstellen dass `eff_goal` aus dem neuen `sick_period`-Block kommt. Der Rest der Progress-Bar ist unverändert.

### 3. Krankmeldungs-Card (ca. L54–101) – komplett ersetzen

**Alter Code (ca. L55–101):**
```html
{% if participation and participation.status == "accepted" and offset <= 0 %}
<div class="card mb-4 {% if sick_week %}border-warning{% endif %}">
  <div class="card-header {% if sick_week %}bg-warning text-dark{% endif %}">
    <strong>Krankheit melden</strong>
    {% if sick_week %}
      <span class="ms-2 small">– {{ sick_week.sick_days }} Tag(e) eingetragen</span>
    {% endif %}
  </div>
  <div class="card-body">
    <form method="post"
          action="{{ url_for('challenge_activities.sick_week_submit') }}"
          class="row g-2 align-items-end">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <input type="hidden" name="offset" value="{{ offset }}">
      <div class="col-12 col-sm-6">
        <label for="sick_days" class="form-label">
          Krankentage diese Woche <small class="text-muted">(1–7)</small>
        </label>
        <select name="sick_days" id="sick_days" class="form-select">
          {% for d in range(1, 8) %}
          <option value="{{ d }}"
            {% if sick_week and sick_week.sick_days == d %}selected{% endif %}>
            {{ d }} Tag{% if d > 1 %}e{% endif %}{% if d >= 2 %} (–{{ d // 2 }} Aktivität{% if d // 2 > 1 %}en{% endif %}){% endif %}
          </option>
          {% endfor %}
        </select>
      </div>
      <div class="col-12 col-sm-6">
        <button type="submit" class="btn btn-outline-warning w-100">
          {% if sick_week %}Krankmeldung aktualisieren{% else %}Krank melden{% endif %}
        </button>
      </div>
    </form>
    {% if sick_week %}
    <div class="mt-3">
      <form method="post"
            action="{{ url_for('challenge_activities.delete_sick_week', sick_week_id=sick_week.id) }}"
            data-confirm="Krankmeldung für diese Woche wirklich löschen? Die Wochenzählung wird wieder aktiviert."
            class="d-inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="btn btn-outline-danger btn-sm">Krankmeldung löschen</button>
      </form>
    </div>
    {% endif %}
  </div>
</div>
{% endif %}
```

**Neuer Code:**
```html
{% if participation and participation.status == "accepted" %}
<div class="card mb-4 {% if sick_period %}border-warning{% endif %}">
  <div class="card-header {% if sick_period %}bg-warning text-dark{% endif %}">
    <strong>Krankmeldung</strong>
    {% if sick_period %}
      <span class="ms-2 small">– {{ sick_period.start_date.strftime('%d.%m.%Y') }} bis {{ sick_period.end_date.strftime('%d.%m.%Y') }}</span>
    {% endif %}
  </div>
  <div class="card-body">
    <form method="post"
          action="{{ url_for('challenge_activities.sick_period_submit') }}"
          class="row g-2 align-items-end">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <input type="hidden" name="offset" value="{{ offset }}">
      {% if sick_period %}
      <input type="hidden" name="sick_period_id" value="{{ sick_period.id }}">
      {% endif %}
      <div class="col-12 col-sm-5">
        <label for="sick_from" class="form-label">Von</label>
        <input type="date" class="form-control" id="sick_from" name="sick_from"
               value="{{ sick_period.start_date.isoformat() if sick_period else '' }}" required>
      </div>
      <div class="col-12 col-sm-5">
        <label for="sick_to" class="form-label">Bis</label>
        <input type="date" class="form-control" id="sick_to" name="sick_to"
               value="{{ sick_period.end_date.isoformat() if sick_period else '' }}" required>
      </div>
      <div class="col-12 col-sm-2">
        <button type="submit" class="btn btn-outline-warning w-100">
          {% if sick_period %}Aktualisieren{% else %}Eintragen{% endif %}
        </button>
      </div>
    </form>
    <div class="form-text mt-1">Pro 2 Krankentage wird eine benötigte Aktivität abgezogen.</div>
    {% if sick_period %}
    <div class="mt-3">
      <form method="post"
            action="{{ url_for('challenge_activities.delete_sick_period', sick_period_id=sick_period.id) }}"
            data-confirm="Krankmeldung wirklich löschen?"
            class="d-inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="btn btn-outline-danger btn-sm">Krankmeldung löschen</button>
      </form>
    </div>
    {% endif %}
  </div>
</div>
{% endif %}
```

**Wichtig:** Die `offset <= 0`-Bedingung in der Card-Bedingung entfernen (jetzt: alle Wochen können Krankmeldungen haben).

## Verification

```bash
grep -n "sick_week\|sick_week_submit\|delete_sick_week\|sick_days\b" app/templates/activities/my_week.html
# Darf KEINE Treffer für sick_week, sick_week_submit, delete_sick_week zeigen
# sick_days_val ist OK
```

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/templates/activities/my_week.html
SUMMARY: sick_week → sick_period. Fortschrittsanzeige nutzt sick_days_val. Krankmeldungs-Card: statt 1-7-Dropdown jetzt Von/Bis-Datumseingabe pre-filled, sick_period_id für Updates, delete_sick_period. offset<=0-Bedingung entfernt.
RESULT_END
```
