# Briefing — Wave 1, Issue 1: Helfer + deterministischer Default

## Mission (Epic)
Multi-Challenge-Eingabe `0bv.1`: Eingabe-Pfade auf explizite, verifizierte `challenge_id` umstellen, sodass bei ≥2 akzeptierten Teilnahmen keine Aktivität in der falschen Challenge landet. Plan: `.schrammns_workflow/plans/2026-06-13-multi-challenge-eingabe-0bv1.md`.

## Dein Task (NUR dieser Issue)
Füge in `app/routes/challenge_activities.py` zwei neue Helfer hinzu und mache `_active_participation()` deterministisch. **Keine Aufrufer ändern. Keine Commits.** Rein additive Erweiterung.

### 1. `_active_participation()` (Z. 30-41) — deterministisch machen
Die Funktion existiert bereits. Ergänze ein deterministisches `ORDER BY`, sonst unverändert:

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
        )
        .scalars()
        .first()
    )
```

### 2. Neue Helfer direkt NACH `_active_participation()` einfügen

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
        )
        .scalars()
        .all()
    )


def _resolve_participation(challenge_id):
    """Verifizierte Teilnahme für (current_user, challenge_id, accepted) oder None.

    challenge_id: roher Form-Wert (str|None). Gibt None zurück bei
    fehlendem/ungültigem Wert ODER wenn keine akzeptierte Teilnahme existiert.
    Vorbild: bonus._user_is_accepted_participant (app/routes/bonus.py:30).
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

## Vorbild (lesen, nicht ändern)
- `app/routes/bonus.py:30-39` — `_user_is_accepted_participant(challenge_id)`, das saubere Verifikations-Muster.
- `Challenge` + `ChallengeParticipation`: `app/models/challenge.py` (Felder, Status invited|accepted|bailed_out).

## File Ownership
- **Nur** `app/routes/challenge_activities.py`. Sonst nichts.

## Guardrails
- Rein additiv/non-destruktiv. Keine Migration, keine `.env`-Var, keine Dependency.
- Status-Filter bleibt `accepted` (nicht `bailed_out`).
- Imports prüfen: `Challenge` ist bereits importiert (Z. 11) — kein neuer Import nötig.
- **Nicht committen.** Der Team-Lead reviewt Diff, testet und committet.

## Deliverable
Die 3 Funktionen im finalen Zustand (1 geänderte + 2 neue) in `challenge_activities.py`. Melde am Ende im Format:
```
RESULT_START
STATUS: COMPLETE | BLOCKED | DESIGN_DECISION_REQUIRED
FILES_MODIFIED: app/routes/challenge_activities.py
SUMMARY: <2-3 Sätze was geändert wurde>
RESULT_END
```

## Verifikation (selbst ausführen vor Meldung)
```bash
cd /Users/schrammn/Documents/VSCodium/sport-challenge
.venv/bin/python -c "import ast; ast.parse(open('app/routes/challenge_activities.py').read()); print('syntax ok')"
grep -n "_accepted_participations\|_resolve_participation\|order_by" app/routes/challenge_activities.py
```
