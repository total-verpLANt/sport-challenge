# Plan: Multi-Challenge-Eingabe (`0bv.1`) — explizite `challenge_id`-Bindung

**Date:** 2026-06-13
**Goal:** `_active_participation()` + Eingabe-Pfade (log/sick/import) auf explizite, verifizierte `challenge_id` umstellen, sodass bei ≥2 gleichzeitig akzeptierten Teilnahmen Aktivitäten/Importe/Abwesenheiten deterministisch in der vom Nutzer **gewählten** Challenge landen.
**bd-Issue:** `sport-challenge-0bv.1` (Epic `sport-challenge-0bv`)
**Research:** [.schrammns_workflow/research/2026-06-13-multi-challenge-eingabe-bug.md](.schrammns_workflow/research/2026-06-13-multi-challenge-eingabe-bug.md)

## Problem

`_active_participation()` ([challenge_activities.py:30-41](app/routes/challenge_activities.py#L30-L41)) wählt akzeptierte Teilnahmen mit `.first()` **ohne `ORDER BY`** → bei ≥2 `accepted` Teilnahmen nicht-deterministisch. Die 3 Schreibpfade (`log_submit`, `import_submit`, `sick_period_submit`) leiten die Ziel-Challenge ausschließlich daraus ab; kein Request-Parameter steuert die Challenge. Folge: stiller Daten-Bug + bei nicht-überlappenden Perioden falsche Datums-Ablehnung.

## Baseline-Audit (verifiziert 2026-06-13)

| Metrik | Wert | Verifikation |
|--------|------|--------------|
| LOC `challenge_activities.py` | 687 | `wc -l` |
| Aufrufer `_active_participation()` | 7 | `grep -n` (Z. 47,58,152,241,320,410,583) |
| `challenge_id` in Templates | 0 | `grep -rn challenge_id app/templates/activities/` |
| Schreibpfade mit Bug | 3 | log_submit:125, import_submit:479, sick_period_submit:302 |
| `sick_period_submit`-POST-Tests | 0 | Research F8 |
| git-Status | clean (nur Research-Datei untracked) | `git status --short` |
| Branch | `main` | `git branch --show-current` |

## Constraints / Boundaries

- **Always:** Rein additiv/non-destruktiv — **keine** Migration, **keine** neue `.env`-Var, **keine** neue Dependency (alle `challenge_id`-Spalten existieren bereits: [activity.py:14](app/models/activity.py#L14), [sick_period.py:14](app/models/sick_period.py#L14)).
- **Always:** Status-Asymmetrie beibehalten — Eingabe nur für `status == "accepted"` (nicht `bailed_out`), wie bisher [challenge_activities.py:36](app/routes/challenge_activities.py#L36).
- **Always:** Backend verifiziert jede aus dem Formular gelesene `challenge_id` serverseitig gegen den eingeloggten Nutzer (IDOR-Schutz). Das UI-Dropdown ist nur Komfort, **nie** Autorisierung.
- **Always:** Bei genau 1 akzeptierter Teilnahme kein UX-Regress — kein sichtbares Auswahlfeld (Hidden-Field mit der einzigen `challenge_id`).
- **Never:** Das offene Lesemodell ("alle sehen alles") anfassen — betrifft nur Schreibpfade.
- **Never:** `bonus.py`-Pfad anfassen — das ist `0bv.3`, separat.
- **Decided (Step 7.5):** siehe Design Decisions.

## Files to Modify

| File | Change |
|------|--------|
| `app/routes/challenge_activities.py` | Neue Helfer `_accepted_participations()` + `_resolve_participation()`; `_active_participation()` deterministisch (`ORDER BY`); 3 Schreibpfade + 3 GET-Routen härten |
| `app/templates/activities/log.html` | Challenge-Select (Aktivität-Tab + Abwesenheit-Tab), bedingt sichtbar |
| `app/templates/activities/import.html` | Challenge-Select bzw. Hidden-Field |
| `app/templates/activities/my_week.html` | `challenge_id` als Hidden-Field in alle Sick-Period-Inline-Forms |
| `tests/test_activities_log.py` | Fixture `_create_two_active_challenges` + Multi-Challenge-Tests + erste `sick_period_submit`-POST-Tests |
| `tests/test_import.py` | Multi-Challenge-Import-Tests |

## Implementation Detail

### Issue 1 — Helfer + deterministischer Default (Wave 1)

**Datei:** [challenge_activities.py](app/routes/challenge_activities.py)

Neue Funktionen direkt nach `_active_participation()` (Z. 41):

```python
def _accepted_participations():
    """Alle akzeptierten Teilnahmen des Nutzers, deterministisch sortiert."""
    return list(
        db.session.execute(
            db.select(ChallengeParticipation)
            .join(Challenge)
            .where(
                ChallengeParticipation.user_id == current_user.id,
                ChallengeParticipation.status == "accepted",
            )
            .order_by(Challenge.start_date.desc(), ChallengeParticipation.id.desc())
        ).scalars().all()
    )


def _resolve_participation(challenge_id):
    """Verifizierte Teilnahme für (current_user, challenge_id, accepted) oder None.

    challenge_id: roher Form-Wert (str|None). Gibt None zurück bei
    fehlendem/ungültigem Wert ODER wenn keine akzeptierte Teilnahme existiert.
    Vorbild: bonus._user_is_accepted_participant (bonus.py:30).
    """
    try:
        cid = int(challenge_id)
    except (TypeError, ValueError):
        return None
    return db.session.execute(
        db.select(ChallengeParticipation).where(
            ChallengeParticipation.user_id == current_user.id,
            ChallengeParticipation.challenge_id == cid,
            ChallengeParticipation.status == "accepted",
        )
    ).scalar_one_or_none()
```

`_active_participation()` bleibt erhalten, bekommt aber deterministisches `ORDER BY` (gleiche Sortierung wie `_accepted_participations()`), damit der Single-Teilnahme-Default stabil ist:

```python
def _active_participation():
    """Default-Teilnahme (deterministisch). Rückwärtskompat für Single-Challenge-Fall."""
    return (
        db.session.execute(
            db.select(ChallengeParticipation)
            .join(Challenge)
            .where(
                ChallengeParticipation.user_id == current_user.id,
                ChallengeParticipation.status == "accepted",
            )
            .order_by(Challenge.start_date.desc(), ChallengeParticipation.id.desc())
        ).scalars().first()
    )
```

**Keine Aufrufer-Änderung in diesem Issue** — nur additive Helfer + Sortierung. Verhalten bleibt für Single-Challenge identisch.

**Reuse:** `bonus._user_is_accepted_participant` ([bonus.py:30](app/routes/bonus.py#L30)) als Muster.

### Issue 2 — Backend-Härtung der 3 Schreibpfade (Wave 2) **[sicherheitskritisch]**

**Datei:** [challenge_activities.py](app/routes/challenge_activities.py). Hängt von Issue 1 (nutzt neue Helfer).

Gemeinsames Auswahl-Muster für alle 3 POST-Routen (ersetzt `participation = _active_participation()`):

```python
participations = _accepted_participations()
if not participations:
    flash("Du nimmst aktuell an keiner Challenge teil.")
    return redirect(url_for("challenges.index"))

raw_cid = request.form.get("challenge_id")
if len(participations) == 1 and not raw_cid:
    participation = participations[0]          # Rückwärtskompat: Default
else:
    participation = _resolve_participation(raw_cid)
    if participation is None:
        flash("Bitte wähle eine gültige Challenge aus.")
        return redirect(url_for(<jeweilige_form_route>))
```

- **`log_submit`** (Z. 58): obiges Muster; Datums-Check Z. 81 bleibt, prüft jetzt gegen die **gewählte** `participation.challenge`. FK-Write Z. 125 unverändert (`challenge_id=participation.challenge_id`). Redirect-Ziel bei Fehler: `challenge_activities.log_form`.
- **`sick_period_submit`** (Z. 241): obiges Muster; `challenge = participation.challenge` (Z. 246) folgt der Wahl. Clamping/Overlap (Z. 268-285) gegen gewählte Challenge. Redirect-Ziel: `log_form` (bzw. `my_week` via `offset`, bestehende Logik Z. 311-314).
- **`import_submit`** (Z. 410): obiges Muster; `participation.challenge_id` in Periodenprüfung Z. 468 + FK-Write Z. 479 folgt der Wahl. Redirect-Ziel: `import_form`.

**Sicherheit:** `_resolve_participation()` verifiziert (user, challenge_id, accepted) per Query — eine fremde oder nicht-akzeptierte `challenge_id` liefert `None` → Flash+Redirect, **kein** Schreibzugriff. Kein stiller Fallback bei >1 Teilnahme ohne gültige Wahl (sonst wäre der Bug zurück).

### Issue 3 — UI Challenge-Select (Wave 3)

**Dateien:** [log.html](app/templates/activities/log.html), [import.html](app/templates/activities/import.html), [my_week.html](app/templates/activities/my_week.html) + GET-Routen in [challenge_activities.py](app/routes/challenge_activities.py). Hängt von Issue 2 (teilt `challenge_activities.py`, serialisiert).

GET-Routen `log_form` (Z. 46), `import_form` (Z. 319), `my_week` (Z. 151) übergeben zusätzlich `participations=_accepted_participations()` ans Template (für `my_week` den default-`participation` beibehalten — voller my_week-Selektor ist `0bv.2`).

**Select-Snippet** (nach `weekly_goal`-Muster [challenges/index.html:32-35](app/templates/challenges/index.html#L32-L35)), in `log.html` (beide Tabs) + `import.html`:

```html
{% if participations and participations|length > 1 %}
  <div class="mb-3">
    <label for="challenge_id" class="form-label">Challenge</label>
    <select name="challenge_id" id="challenge_id" class="form-select" required>
      {% for p in participations %}
        <option value="{{ p.challenge_id }}">{{ p.challenge.name }}</option>
      {% endfor %}
    </select>
  </div>
{% elif participations %}
  <input type="hidden" name="challenge_id" value="{{ participations[0].challenge_id }}">
{% endif %}
```

**`my_week.html`:** In jede Sick-Period-Inline-Form (Edit Z. ~72, Neu Z. ~112) ein Hidden-Field `<input type="hidden" name="challenge_id" value="{{ participation.challenge_id }}">` ergänzen, damit `sick_period_submit` die korrekte Challenge erhält. (my_week zeigt in `0bv.1` weiterhin nur die Default-Teilnahme; Multi-Selektor = `0bv.2`.)

**Konsistenz:** Jede Form, die an einen gehärteten POST-Endpunkt sendet, muss `challenge_id` mitgeben — sonst Flash bei >1 Teilnahme.

### Issue 4 — Tests (Wave 4)

**Dateien:** [tests/test_activities_log.py](tests/test_activities_log.py), [tests/test_import.py](tests/test_import.py). Hängt von Issue 2+3.

Fixture (Vorbild [test_dashboard.py:256-272](tests/test_dashboard.py#L256-L272)):

```python
def _create_two_active_challenges(db, user_id):
    """Zwei aktive Challenges mit je accepted ChallengeParticipation. Gibt (cA, cB) zurück."""
    # Challenge A: today-7 .. today+30, Challenge B: today-3 .. today+20 (überlappend)
    # + je ChallengeParticipation(user_id, status="accepted")
```

`test_activities_log.py` — neu:
- `test_log_submit_routes_to_selected_challenge`: 2 aktive Challenges, POST mit `challenge_id=B` → Activity.challenge_id == B.
- `test_log_submit_rejects_foreign_challenge`: `challenge_id` einer fremden/nicht-akzeptierten Challenge → kein Eintrag, Flash/Redirect.
- `test_log_submit_missing_challenge_id_with_multiple`: 2 aktive, kein `challenge_id` → Flash, kein Eintrag.
- `test_log_submit_single_challenge_no_field_still_works`: 1 Teilnahme, kein `challenge_id` → Default greift (Rückwärtskompat).
- `test_log_submit_non_overlapping_periods`: A beendet (today-30..today-1), B aktiv (today..today+30); Aktivität heute mit `challenge_id=B` → akzeptiert (nicht mehr fälschlich gegen A geprüft).
- `test_sick_period_submit_creates`: erster POST-Test überhaupt — anlegen, Clamping auf Challenge-Grenzen, Redirect.
- `test_sick_period_submit_routes_to_selected_challenge`: 2 aktive, `challenge_id=B` → SickPeriod.challenge_id == B.
- `test_sick_period_submit_overlap_rejected`: Overlap innerhalb gewählter Challenge → Flash.

`test_import.py` — neu:
- `test_import_submit_routes_to_selected_challenge`: 2 aktive, `challenge_id=B` → importierte Activity.challenge_id == B.

## Verification

```bash
# Pro Issue: betroffene Tests
set -a && source .env && set +a
.venv/bin/pytest tests/test_activities_log.py -v
.venv/bin/pytest tests/test_import.py -v
# Vollsuite (muss grün bleiben, Baseline 245)
.venv/bin/pytest -q
# Backend-Härtung manuell: fremde challenge_id wird abgelehnt
.venv/bin/pytest tests/test_activities_log.py -v -k "foreign or routes_to_selected"
```

## Issues & Waves

| # | Titel | Files | Größe | Risk | Wave | Dep |
|---|-------|-------|-------|------|------|-----|
| 1 | Helfer `_accepted_participations()`/`_resolve_participation()` + deterministischer Default | challenge_activities.py | S | reversible / local / autonomous-ok | 1 | — |
| 2 | Backend-Härtung 3 Schreibpfade (challenge_id verifizieren, Datums-Check gegen Wahl) | challenge_activities.py | M | reversible / system / requires-approval | 2 | 1 |
| 3 | UI Challenge-Select (log/import/my_week) + GET-Routen | challenge_activities.py, 3 Templates | M | reversible / local / autonomous-ok | 3 | 2 |
| 4 | Tests: 2-Challenge-Fixture, Routing/IDOR/Übergang, erste sick_period-POST-Coverage | 2 Testdateien | M | reversible / local / autonomous-ok | 4 | 2,3 |

**Waves seriell:** Alle Kern-Issues teilen `challenge_activities.py` → echte Parallelität gering. Passt zur atomaren Arbeitsweise (ein Fix = ein Commit). 4 Waves, je 1 atomarer Commit mit Test davor.

## Design Decisions

| Entscheidung | Gewählt | Verworfen | Begründung |
|--------------|---------|-----------|------------|
| Verhalten bei >1 Teilnahme ohne gültige `challenge_id` | Flash + Redirect, kein Schreibzugriff | Stiller Fallback auf Default | Stiller Fallback bringt den nicht-deterministischen Bug zurück; explizite Wahl ist Pflicht |
| my_week-Umfang in `0bv.1` | Nur Default-Teilnahme + Hidden-`challenge_id` in Sick-Forms | Voller Multi-Challenge-Selektor in my_week | Voller Selektor ist explizit `0bv.2`; `0bv.1` = Daten-Integrität der Schreibpfade |
| Sortier-Default | `Challenge.start_date DESC, participation.id DESC` | `id ASC` (Status quo de facto) | Neueste Challenge zuerst = intuitivster Default für Eintragen |

## Rollback

- Git-Checkpoint vor Wave 1 (`main`, clean). Jeder Commit atomar → `git revert <sha>` pro Issue.
- Keine DB-/Migrations-Änderung → kein Daten-Rollback nötig.
- Templates additiv → Revert ohne Seiteneffekt.

## Invalidation Risks

| Annahme | Bricht bei | Betroffen |
|---------|-----------|-----------|
| `participation.challenge.name` ist sicher gesetzt | Challenge ohne Name (unwahrscheinlich, NOT NULL) | Issue 3 |
| `sick_period_submit` nur aus log.html + my_week.html aufgerufen | Weiterer Aufrufer existiert | Issue 2/3 — `grep url_for.*sick_period_submit` vor Issue 3 |
| Vollsuite-Baseline 245 grün | Vorbestehender Flaky-Test | Issue 4 — bei Rot zuerst Baseline prüfen |
