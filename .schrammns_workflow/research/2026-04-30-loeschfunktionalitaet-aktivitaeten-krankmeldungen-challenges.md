# Research: Lösch-Funktionalität für Aktivitäten, Krankmeldungen, Challenges und Bonus-Challenges

**Date:** 2026-04-30
**Scope:** app/routes/, app/models/, app/templates/, tests/

## Executive Summary

- **3 Delete-Routen existieren bereits:** `delete_activity` (Owner), `delete_media` (Owner), `delete_user` (Admin mit Guards) – alle vollständig getestet
- **4 Delete-Routen fehlen komplett:** SickWeek (User + Admin), Challenge (Admin), BonusChallenge (Admin)
- **Challenge-Delete ist das risikoreichste Feature:** Kein einziger `ondelete="CASCADE"` auf den abhängigen Tabellen (ChallengeParticipation, Activity, SickWeek, BonusChallenge, PenaltyOverride, BonusChallengeEntry) → manuelle Cascade-Löschung in der richtigen Reihenfolge zwingend
- **SickWeek-Delete ist einfach:** Kein Dateisystem-Cleanup, einfache FK-Abhängigkeit
- **Muster für neue Routen klar definiert:** Owner-Check-Pattern aus `delete_activity`, Admin-Guard-Pattern aus `delete_user` als Vorlage direkt nutzbar

## Key Files

| File | Purpose |
|------|---------|
| `app/routes/challenge_activities.py` | delete_activity (L523–537), delete_media (L645–665) – Vorlage für neue Delete-Routen |
| `app/routes/challenges.py` | Challenge-Routen (kein Delete vorhanden) |
| `app/routes/admin.py` | delete_user (L154–196) – Vorlage für Admin-Delete mit Cascade |
| `app/routes/bonus.py` | Bonus-Routen (kein Delete vorhanden) |
| `app/models/activity.py` | Activity + ActivityMedia Cascades (L29–94) |
| `app/models/challenge.py` | Challenge + ChallengeParticipation – KEINE Cascades |
| `app/models/sick_week.py` | SickWeek – KEINE Cascades |
| `app/models/bonus.py` | BonusChallenge + BonusChallengeEntry – KEINE Cascades |
| `app/models/penalty.py` | PenaltyOverride – KEINE Cascades |
| `app/templates/activities/my_week.html` | Bestehender Delete-Button für Aktivitäten (L154–162) |
| `app/templates/challenges/detail.html` | Kein Challenge-Delete-Button vorhanden |
| `app/templates/bonus/index.html` | Kein Bonus-Delete-Button vorhanden |
| `app/templates/base.html` | Global data-confirm JS Handler |
| `tests/test_activities_log.py` | Tests delete_activity (L86–146), delete_media (L439–485) |
| `tests/test_admin_user_detail.py` | Tests delete_user (L121–195) – Cascade + Guards |

## Technology Stack

| Library/Framework | Version (if known) | Role |
|-------------------|--------------------|------|
| Flask | 3.x | Route-Handling, Blueprint-Architektur |
| SQLAlchemy | 2.x | ORM, Cascade-Definitionen |
| Flask-Login | - | login_required, current_user |
| app/utils/decorators.py | - | admin_required (verkettet login_required) |
| app/utils/uploads.py | - | delete_media_files(), delete_upload() für Dateisystem-Cleanup |

## Findings

### F-01: Bestehende Delete-Route delete_activity (Owner)

**Datei:** `app/routes/challenge_activities.py:523–537`

```
Route: POST /challenge-activities/<int:activity_id>/delete
Auth: @login_required
Guard: activity.user_id == current_user.id (404 wenn nicht Match)
Workflow: delete_media_files(activity) → delete_upload(screenshot_path) → db.session.delete(activity) → commit
Redirect: challenge_activities.my_week
```

Admin-Override fehlt: Admins können keine fremden Aktivitäten löschen.

Template: `activities/my_week.html:154–162` – nur für `source == "manual"` sichtbar.

### F-02: Bestehende Delete-Route delete_media (Owner)

**Datei:** `app/routes/challenge_activities.py:645–665`

```
Route: POST /challenge-activities/<int:activity_id>/media/<int:media_id>/delete
Auth: @login_required
Guard: activity.user_id == current_user.id (404 wenn nicht Match) + media.activity_id == activity_id
Workflow: delete_upload(media.file_path) → db.session.delete(media) → commit
```

Admin-Override fehlt ebenfalls.

### F-03: Bestehende Delete-Route delete_user (Admin)

**Datei:** `app/routes/admin.py:154–196`

```
Route: POST /admin/users/<int:user_id>/delete
Auth: @admin_required
Guards:
  - Self-Delete blockiert (L158–160)
  - Last-Admin-Guard (L162–169)
  - Challenge-Creator-Block (L171–174) ← User muss keine Challenges haben
  - Email-Bestätigung (L176–180)
Cascade-Reihenfolge (L182–190):
  1. BonusChallengeEntry (user_id)
  2. PenaltyOverride (user_id oder set_by_id)
  3. SickWeek (user_id)
  4. Activity (user_id) ← löscht NICHT ActivityMedia-Dateien vom FS!
  5. ChallengeParticipation (user_id)
  6. ConnectorCredential (user_id)
  7. User selbst
```

**Sicherheitslücke:** Bei User-Delete werden Aktivitäten per `.delete()` (bulk) gelöscht – dabei läuft die ORM-Cascade NICHT (kein `session.delete()` pro Objekt). ActivityMedia-Dateien bleiben physisch auf dem Filesystem! Dies ist ein bekannter SQLAlchemy-Gotcha: Bulk `.delete()` triggert keine ORM-Cascades.

### F-04: FEHLT – delete_sick_week (User + Admin)

**Modell:** `app/models/sick_week.py:9–22`

```
Tabelle: sick_weeks
Felder: id, user_id, challenge_id, week_start, created_at
Constraints: UniqueConstraint(user_id, challenge_id, week_start)
ForeignKeys: user_id→users.id, challenge_id→challenges.id (KEIN ondelete)
```

Keine Delete-Route, kein Template-Button, kein Test.

Benötigt: User-Route (eigene Einträge) + Admin-Route (alle Nutzer).

### F-05: FEHLT – delete_challenge (Admin)

**Modell:** `app/models/challenge.py`

```
Tabelle: challenges
Abhängige Tabellen (OHNE ondelete CASCADE):
  - ChallengeParticipation (challenge_id)
  - Activity (challenge_id) ← Activities haben Dateisystem-Medien!
  - SickWeek (challenge_id)
  - PenaltyOverride (challenge_id)
  - BonusChallenge (challenge_id) ← hat wiederum BonusChallengeEntry!
```

Challenge-Delete erfordert tiefste Cascade-Logik:
1. BonusChallengeEntry (via BonusChallenge.challenge_id)
2. BonusChallenge (challenge_id)
3. PenaltyOverride (challenge_id)
4. SickWeek (challenge_id)
5. Activity + ActivityMedia-Dateien (challenge_id) ← Muss über ORM-Objekte iterieren!
6. ChallengeParticipation (challenge_id)
7. Challenge selbst

Kein Template-Button, kein Test.

### F-06: FEHLT – delete_bonus_challenge (Admin)

**Modell:** `app/models/bonus.py`

```
Tabelle: bonus_challenges
Felder: id, challenge_id, scheduled_date, description
Abhängige Tabelle:
  - BonusChallengeEntry (bonus_challenge_id, OHNE ondelete CASCADE)
```

Delete-Reihenfolge: BonusChallengeEntry → BonusChallenge.

Kein Template-Button, kein Test.

### F-07: Admin-Override für Activity/SickWeek Delete

Aktuell können Admins keine fremden Aktivitäten oder Krankmeldungen löschen.
Lösung: Entweder eigene Admin-Route oder Admin-Guard in bestehender Route:

```python
if activity.user_id != current_user.id and not current_user.is_admin:
    abort(403)
```

Analog für SickWeek-Delete.

### F-08: ORM-Cascade vs. Bulk-Delete (SQLAlchemy Gotcha)

**Bestehende Lücke in admin.py:187:**
```python
Activity.query.filter_by(user_id=user.id).delete()  # Bulk!
```
ORM-Cascades (media, likes, comments) werden NICHT ausgelöst. ActivityMedia-Dateien bleiben auf dem Filesystem.

Korrekte Alternative für Aktivitäten mit Medien:
```python
for activity in Activity.query.filter_by(user_id=user.id).all():
    delete_media_files(activity)
    db.session.delete(activity)
```

Oder: `synchronize_session="fetch"` + Bulk, aber dann Datei-Cleanup separat.

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| delete_activity Route | 4 | Vollständig gelesen, Tests bekannt |
| delete_media Route | 4 | Vollständig gelesen, Tests bekannt |
| delete_user (Admin) Route | 4 | Vollständig gelesen inkl. Guards |
| Challenge-Cascade-Abhängigkeiten | 3 | Alle FKs geprüft, kein ondelete |
| SickWeek Model | 3 | Einfaches Model, klar |
| BonusChallenge/Entry Model | 3 | Abhängigkeiten klar |
| bestehende Tests | 3 | Inventar vollständig |
| Template-Patterns | 3 | data-confirm, Modal verstanden |
| Bulk-Delete vs. ORM-Cascade | 3 | Gotcha identifiziert |

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Kann ein Admin Challenge löschen wenn aktive Participations existieren? | must-fill | Produktentscheidung: Guard einbauen oder nicht |
| Soll User SickWeek rückwirkend löschen dürfen? | must-fill | Produktentscheidung: Betrug-Risiko vs. Usability |
| Filesystem-Leak bei delete_user (ActivityMedia) | must-fill | F-08 fixen in delete_user |
| SickWeek: Admin-Route in admin.py oder eigener Blueprint? | nice-to-have | Konvention: Nutzerverwaltungs-Aktionen → admin.py |

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| admin_required verkettet login_required | Yes | `app/utils/decorators.py` (via Agent B) |
| delete_upload() löscht Datei vom FS, nicht DB | Yes | `app/routes/challenge_activities.py:645–665` |
| Bulk .delete() triggert keine ORM-Cascades | Yes | SQLAlchemy-Dokumentation, bekanntes Verhalten |
| data-confirm JS Handler ist global in base.html | Yes | `app/templates/base.html` |
| Challenge.created_by_id hat keinen ondelete | Yes | `app/models/challenge.py` (Agent B) |
| BonusChallenge hat kein Relationship-Cascade | Yes | `app/models/bonus.py` (Agent B) |

## Recommendations

### Neue Routen (Priorität 1 – User-facing)

1. **`POST /challenge-activities/sick-week/<int:sick_week_id>/delete`** (User)
   - Guard: `sick_week.user_id == current_user.id`
   - Template: Lösch-Button in der Krankmeldungs-Übersicht (noch zu bauen oder in `my_week.html` integrieren)
   
2. **Admin-Override für delete_activity** – Admin kann fremde Aktivitäten löschen
   - Anpassung in `delete_activity()`: Guard erweitern auf `or current_user.is_admin`
   - Template: Admin-sichtbarer Button in `user_activities.html`

3. **Admin-Route für SickWeek-Delete** – Admin kann Krankmeldungen aller Nutzer löschen
   - Entweder in `admin.py` oder als Admin-Override in der User-Route

### Neue Routen (Priorität 2 – Admin)

4. **`POST /challenges/<string:public_id>/delete`** (Admin)
   - Tiefste Cascade-Logik (7 Schritte, ActivityMedia-Dateien über ORM iterieren)
   - Guard: `current_user.is_admin`
   - Optional: Schutz wenn aktive Participations/noch laufende Challenge

5. **`POST /bonus/<int:bonus_id>/delete`** (Admin)
   - Cascade: BonusChallengeEntry → BonusChallenge
   - Einfacher als Challenge-Delete

### Bugfix (Priorität 0 – bestehende Lücke)

6. **Filesystem-Leak in `delete_user()`** (F-08)
   - Aktivitäten nicht per Bulk-Delete, sondern per Iteration mit `delete_media_files()`
   - Gilt auch für Challenge-Delete (wenn implementiert)

### Template-Ergänzungen

- `admin/user_detail.html`: Aktivitäten-Tab mit Admin-Delete-Buttons
- `challenges/detail.html`: Admin-sichtbarer "Challenge löschen"-Button
- `bonus/index.html`: Admin-sichtbarer Lösch-Button pro BonusChallenge
- Neues Template oder Integration in `my_week.html`: SickWeek-Einträge mit Lösch-Button
