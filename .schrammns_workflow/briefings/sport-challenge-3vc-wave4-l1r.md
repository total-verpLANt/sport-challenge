# Briefing: I-06 – log.html + detail.html – Zukunft erlauben

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-l1r

## File Ownership

**WRITE:** `app/templates/activities/log.html`
**WRITE:** `app/templates/challenges/detail.html`

## Was zu tun ist

### 1. log.html – Zukunfts-Sperre entfernen + Form-Action korrigieren

Lese `app/templates/activities/log.html` (mindestens L77–100).

**Änderung 1:** Form-Action von `sick_week_submit` auf `sick_period_submit` ändern:
```
action="{{ url_for('challenge_activities.sick_week_submit') }}"
→
action="{{ url_for('challenge_activities.sick_period_submit') }}"
```

**Änderung 2:** `max="{{ today }}"` von BEIDEN Date-Inputs entfernen:
- `sick_from`-Input: `max="{{ today }}"` entfernen
- `sick_to`-Input: `max="{{ today }}"` entfernen

Die `value="{{ today }}"` bleiben erhalten (sinnvoller Default).

**Änderung 3:** Hilfstext aktualisieren – statt "Zeiträume über Wochengrenzen werden automatisch aufgeteilt" (das gilt nicht mehr, es gibt keine Aufteilung):
```
Pro 2 Krankentage wird eine benötigte Aktivität abgezogen.
Auch zukünftige Krankheitszeiträume können eingetragen werden.
```

### 2. detail.html – Legacy-Button durch Link ersetzen

Lese `app/templates/challenges/detail.html` (mindestens L70–90).

Den alten "Krank melden (diese Woche)"-Form-Button ersetzen durch einen Link:
```html
<a href="{{ url_for('challenge_activities.log_form') }}#sick-panel"
   class="btn btn-outline-warning">Krankmeldung eintragen</a>
```

Das ersetzt den gesamten `<form method="post" action="{{ url_for('challenges.sick', ...) }}">...</form>`-Block.

## Verification

```bash
grep -n "sick_week_submit\|max=.*today\|Wochengrenzen" app/templates/activities/log.html  # muss leer sein
grep -n "challenges.sick\|Krank melden (diese" app/templates/challenges/detail.html  # muss leer sein
```

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/templates/activities/log.html, app/templates/challenges/detail.html
SUMMARY: log.html: max-Attribute entfernt, Form-Action auf sick_period_submit, Hilfstext aktualisiert. detail.html: Legacy-Button durch Link zur log_form ersetzt.
RESULT_END
```
