# Briefing: I-04 – challenges.py + admin.py – Legacy-Route + Cascade-Deletes

**Mission:** SickWeek → SickPeriod Epic (sport-challenge-3vc)
**Your Task:** sport-challenge-oab

## Context

Der Import ist bereits auf `SickPeriod` umgestellt. Es gibt aber noch SickWeek-Referenzen
in der Logik. Diese Datei behandelt:
1. Die Legacy-`sick()`-Route (L361–403) die SickWeek direkt nutzt → durch Redirect ersetzen
2. Die `delete_challenge()`-Funktion die `SickWeek.query.filter_by(...).delete()` nutzt
3. admin.py hat `SickWeek.query.filter_by(user_id=user.id).delete()` am L193

## File Ownership

**WRITE:** `app/routes/challenges.py`
**WRITE:** `app/routes/admin.py`

## Was zu tun ist

### 1. challenges.py – Legacy sick()-Route ersetzen

Lese zunächst `app/routes/challenges.py` komplett (oder zumindest L355–405).

Die Funktion `sick()` (L361–403) komplett durch einen einfachen Redirect ersetzen:

```python
@challenges_bp.route("/<string:public_id>/sick", methods=["POST"])
@login_required
def sick(public_id):
    return redirect(url_for("challenge_activities.log_form"))
```

Die URL-Route bleibt erhalten (Backward-Compat), nur der Body ändert sich.

### 2. challenges.py – delete_challenge() Cascade-Delete fixen

Finde die Zeile `SickWeek.query.filter_by(challenge_id=challenge.id).delete()` (ca. L426)
und ersetze sie durch:

```python
SickPeriod.query.filter_by(challenge_id=challenge.id).delete()
```

Prüfe auch ob in der Umgebung dieser Zeile noch andere SickWeek-Referenzen stehen
(z.B. Kommentare wie `# 4. SickWeek`). Diese Kommentare auf `# 4. SickPeriod` anpassen.

### 3. admin.py – User-Cascade-Delete fixen

Lese `app/routes/admin.py` (mindestens L185–205).

Finde `SickWeek.query.filter_by(user_id=user.id).delete()` (ca. L193) und ersetze durch:

```python
SickPeriod.query.filter_by(user_id=user.id).delete()
```

### 4. Bereinigung

Stelle sicher, dass keine `SickWeek`-Referenzen in beiden Dateien verbleiben.
Der Import `from app.models.sick_period import SickPeriod` ist in challenges.py bereits vorhanden.
In admin.py muss ggf. der Import geprüft werden – falls `from app.models.sick_period import SickPeriod`
dort noch nicht steht (es war `from app.models.sick_week import SickWeek` und wurde auf SickPeriod umgestellt),
ist der Import bereits korrekt.

## Verification

```bash
grep -n "SickWeek" app/routes/challenges.py  # muss leer sein
grep -n "SickWeek" app/routes/admin.py       # muss leer sein
```

## Cross-Cutting Constraints

- Legacy-URL `POST /<public_id>/sick` bleibt erhalten (Redirect, kein 404)
- Keine SickWeek-Referenzen in den Dateien
- Kein Entfernen von nicht-sick-relevanten Code

## Result Format

```
RESULT_START
STATUS: COMPLETE
FILES_MODIFIED: app/routes/challenges.py, app/routes/admin.py
SUMMARY: sick()-Route auf Redirect umgestellt. delete_challenge() und admin user-delete auf SickPeriod.query umgestellt. Keine SickWeek-Referenzen mehr.
RESULT_END
```
