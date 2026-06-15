# Briefing — Wave 2, Issue 2: Backend-Härtung der 3 Schreibpfade (IDOR-Schutz)

## Mission (Epic)
Multi-Challenge-Eingabe `0bv.1`. Die Helfer `_accepted_participations()` und `_resolve_participation(challenge_id)` existieren bereits (Issue 1, committed). Jetzt die 3 Schreibpfade härten.

## Dein Task (NUR dieser Issue)
In `app/routes/challenge_activities.py` die Challenge-Auswahl in den **drei POST-Routen** auf explizite, verifizierte `challenge_id` umstellen. **Keine Commits.** Nur diese Datei.

### Gemeinsames Auswahl-Muster
Ersetze in jeder der 3 POST-Funktionen die Zeile `participation = _active_participation()` (samt direkt folgendem `if participation is None: ... return redirect(...)`) durch:

```python
    participations = _accepted_participations()
    if not participations:
        flash("Du nimmst aktuell an keiner Challenge teil.")
        return redirect(url_for("challenges.index"))

    raw_cid = request.form.get("challenge_id")
    if len(participations) == 1 and not raw_cid:
        participation = participations[0]
    else:
        participation = _resolve_participation(raw_cid)
        if participation is None:
            flash("Bitte wähle eine gültige Challenge aus.")
            return redirect(url_for("<FORM_ROUTE>"))
```

`<FORM_ROUTE>` je Funktion:
- `log_submit` → `challenge_activities.log_form`
- `sick_period_submit` → `challenge_activities.log_form`
- `import_submit` → `challenge_activities.import_form`

### Die 3 Stellen konkret

**1. `log_submit` (ab Z. 57/58):** Ersetze den Block
```python
    participation = _active_participation()
    if participation is None:
        flash("Du nimmst aktuell an keiner Challenge teil.")
        return redirect(url_for("challenges.index"))
```
durch das Muster (FORM_ROUTE = `log_form`). Der Rest bleibt: `challenge = participation.challenge` (Z. 80), Datums-Check Z. 81 (prüft nun gegen gewählte Challenge — gewollt), FK-Write `challenge_id=participation.challenge_id` (Z. 125) unverändert.

**2. `sick_period_submit` (ab Z. 240/241):** Gleiches Ersetzen (FORM_ROUTE = `log_form`). Danach `challenge = participation.challenge` (Z. 246) folgt der Wahl; Clamping/Overlap (Z. 268-285) unverändert.

**3. `import_submit` (ab Z. 409/410):** Gleiches Ersetzen (FORM_ROUTE = `import_form`). **Wichtig:** Die bestehende Connector-Prüfung `credentials = ConnectorCredential.query...` + `if not credentials:` (Z. 415-418) bleibt DIREKT DANACH erhalten. `participation.challenge_id` in Periodenprüfung (Z. 468) + FK-Write (Z. 479) folgt der Wahl.

## Sicherheits-Kern (NICHT aufweichen)
- `challenge_id` kommt aus `request.form` = nutzerkontrolliert. `_resolve_participation()` verifiziert serverseitig (user, challenge_id, accepted) → fremde/nicht-akzeptierte ID = None = Flash+Redirect, KEIN Schreibzugriff. Das ist der IDOR-Schutz.
- KEIN stiller Fallback auf `participations[0]` wenn >1 Teilnahme und keine/ungültige `challenge_id` → sonst kommt der nicht-deterministische Bug zurück.
- Bei genau 1 Teilnahme ohne `challenge_id`: Default greift (Rückwärtskompat, kein UX-Regress).

## File Ownership
- **Nur** `app/routes/challenge_activities.py`. Templates NICHT anfassen (das ist Issue 3).

## Guardrails
- Rein Code, keine Migration/.env/Dependency. Status bleibt `accepted`-only.
- GET-Routen (`log_form`, `import_form`, `my_week`) in DIESEM Issue NICHT ändern (Issue 3).
- Nicht committen.

## Deliverable & Meldung
```
RESULT_START
STATUS: COMPLETE | BLOCKED | DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/routes/challenge_activities.py
SUMMARY: <2-3 Sätze>
RESULT_END
```

## Verifikation (selbst ausführen vor Meldung)
```bash
cd /Users/schrammn/Documents/VSCodium/sport-challenge
.venv/bin/python -c "import ast; ast.parse(open('app/routes/challenge_activities.py').read()); print('syntax ok')"
# Muster muss 3x vorkommen, _active_participation in POST-Routen 0x:
grep -n "_accepted_participations()\|_resolve_participation\|raw_cid" app/routes/challenge_activities.py
# Gegenprobe: _active_participation darf nur noch in GET-Routen (log_form/my_week/import_form/user_activities) stehen
grep -n "_active_participation()" app/routes/challenge_activities.py
```
Erwartung: `_accepted_participations()` 3x (in den POST-Routen), `_active_participation()` nur noch in `log_form` (Z.47), `my_week` (Z.152), `import_form` (Z.320), `user_activities` (Z.583) — NICHT mehr in log_submit/sick_period_submit/import_submit.
