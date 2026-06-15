# Briefing — Wave 3, Issue 3: UI Challenge-Select

## Mission (Epic)
Multi-Challenge-Eingabe `0bv.1`. Backend (Issue 1+2) ist fertig: die 3 POST-Routen verlangen bei >1 akzeptierter Teilnahme ein `challenge_id`-Formularfeld; bei genau 1 Teilnahme greift ein Default. Jetzt liefern die Templates dieses Feld.

## Dein Task
Vier Dateien. **Keine Commits.**

### A) GET-Routen erweitern — `app/routes/challenge_activities.py`
Die GET-Routen müssen `participations` ans Template geben. Füge in jeder die Liste hinzu (Helfer `_accepted_participations()` existiert bereits):

1. **`log_form`** (Z. ~46-52): `participation = _active_participation()` bleibt (für die Gate-Prüfung). Ergänze davor/danach `participations = _accepted_participations()` und gib es an `render_template(...)` mit: `participations=participations`.
2. **`import_form`** (Z. ~319): analog `participations = _accepted_participations()` ergänzen und an `render_template("activities/import.html", ...)` als `participations=participations` übergeben.
3. **`my_week`** (Z. ~151): `participation = _active_participation()` bleibt unverändert. Hier ist KEIN `participations` nötig (my_week nutzt nur Hidden-Field mit der Default-`participation` — voller Selektor ist 0bv.2).

### B) `app/templates/activities/log.html` — Select in BEIDE Tabs
Das Select-Snippet (Vorbild: weekly_goal in `challenges/index.html:32-35`) in **Tab 1 (Aktivität-Form, nach dem csrf_token Z. 29)** UND **Tab 2 (Abwesenheit-Form, nach csrf_token Z. 80)** einfügen:

```html
        {% if participations and participations|length > 1 %}
        <div class="mb-3">
          <label for="challenge_id{{ suffix }}" class="form-label">Challenge</label>
          <select name="challenge_id" id="challenge_id{{ suffix }}" class="form-select" required>
            {% for p in participations %}
              <option value="{{ p.challenge_id }}">{{ p.challenge.name }}</option>
            {% endfor %}
          </select>
        </div>
        {% elif participations %}
        <input type="hidden" name="challenge_id" value="{{ participations[0].challenge_id }}">
        {% endif %}
```
**Wichtig — eindeutige IDs:** `id` muss pro Tab eindeutig sein. Nutze für Tab 1 `id="challenge_id_act"` und für Tab 2 `id="challenge_id_sick"` (label `for` entsprechend). Das `name="challenge_id"` bleibt in beiden gleich.

### C) `app/templates/activities/import.html` — Select im POST-Form
Gleiches Snippet (id=`challenge_id_import`) direkt nach `<input type="hidden" name="offset" ...>` (Z. 40) innerhalb des `<form>` (Z. 38). **Achtung:** Das Form steht in `{% if activities %}`. Falls keine Aktivitäten da sind, gibt es kein Form — das ist ok (nichts zu importieren).

### D) `app/templates/activities/my_week.html` — Hidden-Field in BEIDE Sick-Forms
Da my_week nur die Default-`participation` kennt, ein simples Hidden-Field (kein Select). In beide Forms direkt nach dem `offset`-Hidden-Field:
- **Edit-Form** nach Z. 76 (`<input type="hidden" name="offset" ...>`):
- **Neu-Form** nach Z. 116 (`<input type="hidden" name="offset" ...>`):
```html
        {% if participation %}<input type="hidden" name="challenge_id" value="{{ participation.challenge_id }}">{% endif %}
```

## File Ownership
`app/routes/challenge_activities.py` (nur GET-Routen log_form/import_form), `app/templates/activities/log.html`, `app/templates/activities/import.html`, `app/templates/activities/my_week.html`.

## Guardrails
- POST-Routen (log_submit/sick_period_submit/import_submit) NICHT anfassen — die sind fertig (Issue 2).
- Bootstrap 5.3.3, `form-select`-Muster wie weekly_goal.
- Rein additiv. Nicht committen.

## Deliverable & Meldung
```
RESULT_START
STATUS: COMPLETE | BLOCKED | DESIGN_DECISION_REQUIRED
FILES_MODIFIED: <Liste>
SUMMARY: <2-3 Sätze>
RESULT_END
```

## Verifikation (selbst ausführen)
```bash
cd /Users/schrammn/Documents/VSCodium/sport-challenge
.venv/bin/python -c "import ast; ast.parse(open('app/routes/challenge_activities.py').read()); print('py ok')"
# challenge_id muss jetzt in den Templates auftauchen:
grep -rn "challenge_id" app/templates/activities/
# participations in GET-Routen:
grep -n "participations" app/routes/challenge_activities.py
```
Jinja-Render-Smoke (optional, falls schnell): App-Import testen.
