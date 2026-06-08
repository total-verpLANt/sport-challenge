# Research: SickWeek-Modell – Umbau auf SickPeriod (Von-Bis)

**Date:** 2026-05-04
**Scope:** Vollständige Impact-Analyse für den Umbau von `SickWeek` (week_start + sick_days) auf ein Von-Bis-Datumsmodell (`SickPeriod`). Untersucht: Model, Services, Routen, Templates, Tests, Migrationen, Cascade-Deletes.

---

## Executive Summary

- **Von/Bis-Eingabe existiert bereits** – `log.html` hat bereits ein Von/Bis-Formular (Path A in `sick_week_submit`). Was fehlt, ist die Erlaubnis für Zukunfts-Daten und ein "Gesund melden"-Mechanismus.
- **Das Modell ist wochenbasiert**, nicht datumsbasiert – eine Von/Bis-Eingabe wird via `_sick_days_per_week()` in mehrere Zeilen (eine pro Montag) aufgesplittet. Das ist für die Strafberechnung effizient, aber für "Kürzen" und Zukunft umständlich.
- **Drei Einstiegspunkte** mit unterschiedlichen Fähigkeiten (Legacy-Button, log.html Von/Bis, my_week.html Offset) – uneinheitliche Validierung, redundante Logik.
- **Empfehlung:** Modell auf `SickPeriod` (start_date, end_date nullable) umbauen. Das macht "Gesund melden" = `end_date = gestern` und Zukunftseintrag trivial; der Penalty-Service berechnet den Wochenschnitt per Overlap-Funktion.
- **Aufwand:** Mittel. 1 Migration, 1 neues Model, Anpassung von 2 Services, 3 Routen, 5 Templates, ~20 Tests.

---

## Key Files

| File | Purpose |
|------|---------|
| `app/models/sick_week.py` | Aktuelles SickWeek-Model (zu ersetzen) |
| `app/services/penalty.py` | Strafberechnung; `calculate_weekly_penalty` nutzt SickWeek |
| `app/services/weekly_summary.py` | Dashboard-Aggregat; fetcht alle SickWeeks für eine Challenge |
| `app/routes/challenges.py` | Legacy-`sick`-Route (L361–403) + Challenge-Cascade-Delete (L426) |
| `app/routes/challenge_activities.py` | `sick_week_submit` (L233–337), `_sick_days_per_week` (L222), `delete_sick_week` (L549), `my_week` (L198) |
| `app/routes/admin.py` | User-Cascade-Delete L193 |
| `app/__init__.py` | Model-Import L87 |
| `app/templates/challenges/detail.html` | Legacy-"Krank melden"-Button L78 |
| `app/templates/activities/log.html` | Von/Bis-Formular mit Zukunfts-Sperre |
| `app/templates/activities/my_week.html` | Offset + sick_days-Dropdown + Delete |
| `app/templates/dashboard/index.html` | `wd.is_sick`-Icon L53 |
| `app/templates/dashboard/leaderboard.html` | `wd.is_sick`-Icon L54 |
| `migrations/versions/2307226a4e48_*.py` | Initiale `sick_weeks`-Tabelle |
| `migrations/versions/fbfc6792eaa5_*.py` | `sick_days`-Spalte (server_default '7') |
| `tests/test_penalty.py` | Penalty-Unit-Tests inkl. SickWeek-Szenarien (L141, L247–282) |
| `tests/test_challenge.py` | Route-Integration für sick_week_submit (L280–519) |
| `tests/test_activities_log.py` | Delete-Autorisierung (L553–614) |
| `tests/test_challenge_delete.py` | Cascade-Verification (L60–89) |

---

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| SQLAlchemy | ~2.x (Mapped) | ORM; `Date` Column, `UniqueConstraint`, `mapped_column` |
| Alembic | via Flask-Migrate | Migrationen; SQLite erfordert `render_as_batch=True` |
| Flask-Login | – | `current_user` in Routes |

---

## Findings

### F-01: Von/Bis-Eingabe existiert bereits – Zukunft ist das einzige Blocker

In `app/routes/challenge_activities.py:256–258` wird `sick_to > today` hart abgelehnt:

```python
if sick_to > today:
    flash("Krankmeldungen für zukünftige Tage sind nicht möglich.")
```

Und in `challenge_activities.py:297–299` für Path B:

```python
if offset > 0:
    flash("Krankmeldungen für zukünftige Wochen sind nicht möglich.")
```

Das `log.html`-Formular und die Route-Logik sind konzeptuell bereits "Von/Bis-fähig" – nur die Validierungen blockieren Zukunft. **Der einfachste Fix wäre, diese Schranken zu entfernen.** Aber dann entstehen bei Kürzen/Gesund-Melden mehrere Zeilen, die manuell verwaltet werden müssen.

### F-02: Splitting-Logik erzeugt N Zeilen für N Wochen

`_sick_days_per_week(sick_from, sick_to)` (`challenge_activities.py:222–230`) iteriert tageweise über den Zeitraum und summiert pro Montag die Krankentage. Ergebnis: für eine 3-Wochen-Krankmeldung entstehen 3 SickWeek-Zeilen.

**Problem für "Gesund melden":** Um eine laufende Krankmeldung zu kürzen, müsste man:
1. Die letzte betroffene Zeile updaten (`sick_days` reduzieren)
2. Alle Zeilen für noch-nicht-begonnene Wochen löschen

Das ist möglich, aber fehleranfällig – besonders wenn der User mehrere separate Krankmeldungen eingetragen hat (keine Möglichkeit, Perioden zu unterscheiden, da nur `week_start` als Key gilt).

### F-03: Drei Einstiegspunkte, inkonsistente Validierung

| Einstiegspunkt | Zukunft erlaubt? | Update möglich? | sick_days wählbar? |
|---|---|---|---|
| `challenges.sick` (L361) | Nein (implizit: immer today) | Nein | Nein (immer 7) |
| `sick_week_submit` Path A (L242) | Nein (`sick_to > today`) | Ja (upsert) | Ja (von/bis) |
| `sick_week_submit` Path B (L292) | Nein (`offset > 0`) | Ja (upsert) | Ja (1–7) |

Die Legacy-Route `challenges.sick` ist redundant mit Path A und sollte mit dem Umbau konsolidiert werden.

### F-04: Penalty-Logik erfordert nur minimale Anpassung

`penalty.py:47–62` macht einen einfachen `SickWeek`-Lookup per `(user_id, challenge_id, week_start)` und berechnet `deductions = sick_days // 2`. 

Bei Umbau auf `SickPeriod` wird dieser Lookup ersetzt durch eine Overlap-Berechnung:

```python
def _sick_days_in_week(user_id, challenge_id, week_start):
    week_end = week_start + timedelta(days=6)
    periods = query SickPeriod where (
        user_id == user_id,
        challenge_id == challenge_id,
        start_date <= week_end,
        (end_date IS NULL OR end_date >= week_start)
    )
    total = 0
    for p in periods:
        effective_start = max(p.start_date, week_start)
        effective_end = min(p.end_date or week_end, week_end)
        total += (effective_end - effective_start).days + 1
    return min(total, 7)
```

Die restliche Logik (`effective_goal`, `missed`, Strafe) bleibt unverändert.

**Wichtig:** `calculate_total_penalty` überspringt bereits vollständig-zukünftige Wochen (`week_start > today`). Eine `SickPeriod` mit `start_date` in der Zukunft hat deshalb **keinen Einfluss auf die aktuelle Strafe** – korrekt und kein Handlungsbedarf.

### F-05: weekly_summary.py nutzt Pre-Fetch-Index

`weekly_summary.py:60–67` baut einen Index `{(user_id, week_start): sick_days}` aus einem Bulk-Query aller SickWeeks einer Challenge. Dieser Pre-Fetch muss auf `SickPeriod` umgestellt werden: entweder die Overlap-Berechnung in Python, oder eine effizientere SQL-Abfrage mit Datums-Overlap-Filter.

```python
# Neu: alle SickPeriods der Challenge
sick_periods = db.session.scalars(
    db.select(SickPeriod).where(SickPeriod.challenge_id == challenge.id)
).all()

# Dann pro (user_id, week_start) den Overlap berechnen
sick_days_val = _sick_days_in_week_from_periods(sick_periods_for_user, week_start)
```

Potenziell mehr Python-seitige Berechnung, aber SickPeriods sind selten (wenige pro User), sodass kein Performance-Problem erwartet wird.

### F-06: Cascade-Deletes an zwei Stellen manuell

| Datei | Zeile | Operation |
|---|---|---|
| `admin.py` | L193 | `SickWeek.query.filter_by(user_id=user.id).delete()` |
| `challenges.py` | L426 | `SickWeek.query.filter_by(challenge_id=challenge.id).delete()` |

Beide müssen auf `SickPeriod` umgestellt werden. Da keine DB-Cascade auf den FKs konfiguriert ist, sind das die einzigen Stellen – überschaubar.

### F-07: Vorhandene Tests – Umbau-Impact hoch aber strukturiert

**Tests die brechen werden:**

| Test | Datei | Grund |
|---|---|---|
| `test_sick_week_creation` | test_challenge.py:280 | Route + Model ändert sich |
| `test_duplicate_sick_week_rejected` | test_challenge.py:318 | UniqueConstraint-Semantik ändert sich |
| `test_sick_week_submit_partial` | test_challenge.py:367 | Path B entfällt oder ändert sich |
| `test_sick_week_submit_update` | test_challenge.py:396 | Update-Logik ändert sich |
| `test_sick_week_submit_future_rejected` | test_challenge.py:420 | Zukunft wird jetzt erlaubt |
| `test_sick_week_submit_von_bis_single_week` | test_challenge.py:442 | Model ändert sich |
| `test_sick_week_submit_von_bis_two_weeks` | test_challenge.py:480 | Kein Split in Zeilen mehr |
| `test_sick_week_no_penalty` | test_penalty.py:141 | SickWeek-Fixture ersetzt |
| `test_sick_days_deduction_table` | test_penalty.py:247–279 | SickWeek-Fixture ersetzt |
| `test_partial_sick_week_goal_met` | test_penalty.py:282 | SickWeek-Fixture ersetzt |
| `test_admin_deletes_challenge_cascade` | test_challenge_delete.py:60 | Cascade auf SickPeriod |
| `test_delete_sick_week_*` | test_activities_log.py:553 | Route + Model |

Alle ~12 betroffenen Tests sind gut strukturiert und direkt adaptierbar.

**Neue Tests erforderlich:**
- Zukunfts-SickPeriod wird gespeichert
- "Gesund melden" kürzt `end_date` korrekt
- Gesund-Meldung vor Wochenstart → Periode wird gelöscht
- Overlap-Berechnung bei Perioden über Wochengrenzen
- Mehrere überlappende Perioden (sollten nicht möglich sein per UniqueConstraint oder business-logisch verhindert)

### F-08: Migration – SQLite render_as_batch Pflicht

Bestehende Migrations-Notiz in CLAUDE.md: `render_as_batch=True` in `env.py` bereits gezogen (Commit 21c5cfd). Die Migration für `SickPeriod` muss:

1. Neue Tabelle `sick_periods` anlegen
2. Daten aus `sick_weeks` migrieren:
   - `week_start + sick_days` → `start_date = week_start`, `end_date = week_start + timedelta(days=sick_days-1)`
3. `sick_weeks`-Tabelle droppen

Datenmigration ist verlustfrei: jede SickWeek-Zeile wird zu einer SickPeriod.

---

## Depth Ratings

| Area | Rating | Notes |
|---|---|---|
| SickWeek-Model | 4 | Vollständig gelesen, UniqueConstraint, FKs, Felder verstanden |
| penalty.py | 4 | Komplette Logik gelesen, Overlap-Formel ableitbar |
| weekly_summary.py | 3 | Pre-Fetch-Pattern und Ausgabe verstanden |
| challenge_activities.py (sick routes) | 4 | Alle drei Pfade gelesen, Validierungen bekannt |
| challenges.py (legacy sick) | 4 | Legacy-Route komplett analysiert |
| admin.py cascade | 3 | Relevante Zeile bekannt, Kontext gelesen |
| Templates | 3 | Alle sick-relevanten Stellen identifiziert |
| Tests | 4 | Vollständige Inventur, Coverage-Gaps identifiziert |
| Migrationen | 3 | Beide sick-relevanten Migrationen gelesen |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|---|---|---|
| Soll die Legacy-`sick`-Route auf challenges/detail behalten oder entfernt werden? | nice-to-have | Designentscheidung |
| Performance von Python-seitiger Overlap-Berechnung bei vielen Teilnehmern | nice-to-have | Bei >50 Teilnehmern ggf. SQL-Overlap-Query prüfen |

## Design-Entscheidungen (Käpt'n 2026-05-04)

| Thema | Entscheidung |
|---|---|
| Überlappende Perioden | **Nicht erlaubt** – Validierung verhindert überlappende SickPeriods pro User+Challenge |
| `end_date` nullable | **Nein** – `end_date` ist immer Pflichtfeld; User gibt immer Von + Bis an. "Gesund melden früher" = Update des end_date |

---

## Assumptions

| Assumption | Verified? | Evidence |
|---|---|---|
| `sick_days // 2`-Formel bleibt unverändert | Nein | Nur per Konvention; Käpt'n könnte andere Formel wollen |
| Keine FK-Cascade auf DB-Ebene vorhanden | Ja | `sick_week.py` – keine `ondelete` Parameter |
| `render_as_batch=True` aktiv | Ja | CLAUDE.md "Commit 21c5cfd" |
| SickPeriod-Daten sind selten (<10 pro User pro Challenge) | Ja (erwartet) | Typischer Use-Case: 1-3 Krankmeldungen pro Challenge |

---

## Recommendations

### Empfehlung: Modell-Umbau auf SickPeriod

**Begründung:** Das Von/Bis-Input ist bereits da. Was fehlt, ist Zukunftsunterstützung und einfaches Kürzen. Das wochenbasierte Modell macht beides unnötig kompliziert – "Gesund melden" würde bedeuten, 1–N Zeilen zu aktualisieren/löschen, was fehleranfällig ist.

**Implementierungsplan (atomare Issues):**

1. **Model** – `SickPeriod` (start_date, end_date nullable, user_id FK, challenge_id FK, created_at); UniqueConstraint-Frage klären
2. **Migration** – neue Tabelle, Datenmigration aus sick_weeks, Drop sick_weeks
3. **penalty.py** – Lookup-Funktion auf Overlap-Berechnung umstellen
4. **weekly_summary.py** – Pre-Fetch auf SickPeriod umstellen
5. **challenge_activities.py** – `sick_week_submit` auf eine SickPeriod pro Meldung umstellen; Zukunfts-Sperre entfernen; `delete_sick_week` → `delete_sick_period`
6. **Neue Route "Gesund melden"** – setzt `end_date = yesterday` oder löscht Periode wenn noch nicht gestartet
7. **challenges.py** – Legacy-`sick`-Route konsolidieren oder entfernen; Cascade-Delete anpassen
8. **admin.py** – Cascade-Delete anpassen
9. **Templates** – log.html, my_week.html, detail.html, dashboard
10. **Tests** – ~12 bestehende Tests adaptieren, ~6 neue Tests

**Geschätzter Aufwand:** 8–10 atomare Commits.
