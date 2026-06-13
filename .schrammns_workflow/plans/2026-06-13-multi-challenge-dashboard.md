# Plan: Challenge-Statistiken, globales Dashboard & Leaderboard pro Challenge

## Context

In Prod startet demnächst die **zweite Challenge**. Das Dashboard/Leaderboard ist bisher
auf *eine* Challenge fixiert. Der Kapitän will:
1. **Alle sehen alles** — jeder eingeloggte Nutzer sieht jedes Leaderboard und jede Aktivität,
   auch ohne Teilnahme. (→ IDOR-Sorge entfällt, kein Sichtbarkeits-Gate nötig.)
2. **Globaler Feed** — alle Aktivitäten/Abwesenheiten aller Challenges, dauerhaft (auch beim
   Zurückscrollen), jeder Post mit **Challenge-Label**.
3. **Mehrere aktive Challenges** — je ein **Top-5-Block** + eigener **Spendentopf** pro aktiver
   Challenge. Nach Ende: **Abschluss-Karte** (finale Spendensumme + Link zum vollständigen
   Leaderboard inkl. Stats).
4. **Leaderboard pro Challenge** über ein Navbar-**Dropdown**; dort die **Top-3-Statistiken**
   (nur dort, nicht auf dem Dashboard).
5. KI-Ideen als **bd-Tickets** (✅ erledigt: `18t`, `4t4`).

**Oberstes Prinzip:** rein additiv/non-destruktiv. **Kein** `.env`-/Migrations-/Dependency-
Eingriff (alle Daten existieren). Deploy = reiner Code-Pull.

**Status:** Schritt 0 (KI-Tickets) ✅, Schritt 1 (Statistik-Service `statistics.py` + Tests) ✅
committet (`449932e`). Restliche Schritte unten.

---

## Statistiken (✅ Service fertig)
9 Top-3-Ranglisten in [statistics.py](app/services/statistics.py): meiste Zeit, meiste
Aktivitäten, Wochen-Streak (Krankheit **bricht** die Serie), Tages-Streak (strenge Variante),
Vielseitigkeit, beliebteste Aktivität, Frühaufsteher/Nachteule, längste Einzel-Session.
Bulk-Load, kein N+1. Werden in Schritt 6 nur auf der Leaderboard-Seite gerendert.

---

## Umsetzung (atomar, ein Schritt = ein Commit)

### Schritt 2 — Leaderboard-Route pro Challenge
[dashboard.py](app/routes/dashboard.py):
- Helfer `_get_challenge_by_public_id(public_id)` (UUID→Challenge, sonst `404`) — analog
  [challenges._get_challenge_by_public_id](app/routes/challenges.py#L20). **Kein** Sichtbarkeits-
  Gate (alle sehen alles), nur `@login_required`.
- Neue Route `leaderboard_challenge` → `/leaderboard/<public_id>`. Ruft `get_challenge_summary()`
  **und** `get_challenge_statistics()` auf, gibt `summary` + `stats` ans `leaderboard.html`.
- Bestehende `/leaderboard` (aktive/neueste) bleibt als Fallback — ruft jetzt ebenfalls `stats` ab.
- Tests: Route erreichbar für Nicht-Teilnehmer (200, kein 403/404); ungültige UUID → 404.

### Schritt 3 — Like-Gate entfernen (Security-relevant, klein & isoliert)
[dashboard.py](app/routes/dashboard.py) `like_activity` + `like_sick_period`: den
`_is_challenge_participant`-Check entfernen (alle dürfen liken). Rate-Limit `30/min` bleibt,
`@login_required` bleibt, Existenz-Check (404) bleibt. `_is_challenge_participant` löschen, wenn
nirgends sonst genutzt (vorher grep).
- Tests: angemeldeter Nicht-Teilnehmer kann liken (200, count steigt).

### Schritt 4 — Globaler Feed mit Challenge-Label
[dashboard.py](app/routes/dashboard.py):
- `_build_feed_items(page)` umbauen: **keine** `challenge_id`/`participant_ids`-Filter mehr —
  alle Aktivitäten + Abwesenheiten aller Challenges. Challenge-Namen per Bulk-Load
  (`Challenge.id.in_(...)`) auflösen, in die Dicts schreiben (`challenge_name`,
  `challenge_public_id`).
- `_activity_to_dict` / `_absence_to_dict`: Feld `challenge_name` (+ `_public_id` für Link) ergänzen.
- `/dashboard/feed`-Endpunkt: nur noch `page`-Param, **kein** `challenge_id`, **kein**
  Participation-Gate. Liefert globalen Feed.
- [index.html](app/templates/dashboard/index.html): Feed-Karten zeigen ein dezentes
  Challenge-Badge (`<span class="badge">{{ item.challenge_name }}</span>`), verlinkt aufs
  jeweilige Leaderboard. JS `buildCard()` analog erweitern; "Mehr laden" ohne `challenge_id`.
- Tests: Feed enthält Aktivitäten aus mehreren Challenges; Dict trägt `challenge_name`.

### Schritt 5 — Dashboard-Oberbereich: mehrere Top-5-Blöcke + Abschluss-Karten
[dashboard.py](app/routes/dashboard.py) `index()` umbauen — statt einer Challenge eine **Liste
von "Boards"** bauen:
- **Aktiv** (`start_date <= today <= end_date`): Board mit `summary` (Top-5 = `participants[:5]`)
  + Spendentopf + Link zum vollen Leaderboard.
- **Kürzlich beendet** (`end_date < today` und `end_date >= today - RECENT_DAYS`, `RECENT_DAYS=14`):
  Abschluss-Karte mit finaler Spendensumme + Link zu Leaderboard inkl. Stats.
- **Fallback** wenn nichts qualifiziert: neueste Challenge als Abschluss-Karte (Dashboard nie leer).
- Alle Summaries per `get_challenge_summary()` (Bulk). Anzahl Boards in der Praxis 1–3 → unkritisch.
- [index.html](app/templates/dashboard/index.html): Top-5-Tabelle in eine Schleife über `boards`
  heben; Abschluss-Karten-Variante ergänzen. Globaler Feed bleibt darunter.
- Tests: zwei aktive Challenges → zwei Top-5-Blöcke + zwei Spendentöpfe; beendete → Abschluss-Karte;
  keine aktive → Fallback.

### Schritt 6 — Navbar-Dropdown + Stats auf Leaderboard-Seite
- Context-Processor in [app/__init__.py](app/__init__.py#L136) `inject_nav_challenges`: alle
  Challenges (newest first) als `[{public_id, name}]` — schlanke Single-Query (alle sehen alles,
  kein User-Filter). Nur wenn `current_user.is_authenticated`.
- [base.html](app/templates/base.html#L34-L36): statischen Leaderboard-`nav-link` durch
  `nav-item dropdown` ersetzen (Muster: Settings-Dropdown Z. 53–76). Items →
  `url_for('dashboard.leaderboard_challenge', public_id=...)`. Leer → Link auf `dashboard.leaderboard`.
- **NEU** `app/templates/dashboard/_statistics.html`: responsive Karten-Grid
  (`row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3`), pro Statistik eine Card mit Icon+Titel+
  Top-3 (🥇🥈🥉). Leere Statistik → dezenter "noch keine Daten"-Hinweis.
- [leaderboard.html](app/templates/dashboard/leaderboard.html): Partial unter dem Spendentopf
  per `{% include %}` einbinden (nur hier, nicht im Dashboard).

### Schritt 7 — CHANGELOG + Version
[CHANGELOG.md](CHANGELOG.md) + [app/version.py](app/version.py): SemVer **minor** (Feature),
keepachangelog-Format.

---

## Betroffene Dateien
- **NEU** [app/services/statistics.py](app/services/statistics.py) ✅, tests/test_statistics.py ✅
- **NEU** [app/templates/dashboard/_statistics.html](app/templates/dashboard/_statistics.html)
- [app/routes/dashboard.py](app/routes/dashboard.py) — Route, Feed-Globalisierung, Like-Gate, Boards
- [app/__init__.py](app/__init__.py) — Context-Processor
- [app/templates/base.html](app/templates/base.html) — Navbar-Dropdown
- [app/templates/dashboard/index.html](app/templates/dashboard/index.html) — Boards + Feed-Label + JS
- [app/templates/dashboard/leaderboard.html](app/templates/dashboard/leaderboard.html) — Stats-Include
- tests: test_dashboard / test_statistics erweitern
- CHANGELOG.md + app/version.py

## Verifikation
1. `set -a && source .env && set +a && .venv/bin/pytest -v` — alle grün (vorbestehender flaky
   `test_sick_period_update` = Ticket `3oe`, nicht Teil dieses Features).
2. Dev-Server + Playwright-Sub-Agent (Haiku):
   - Navbar-Dropdown listet alle Challenges; Klick → jeweiliges Leaderboard + Stats.
   - Nicht-Teilnehmer sieht fremdes Leaderboard (kein 403/404) und kann dort liken.
   - Feed zeigt Aktivitäten mehrerer Challenges mit Challenge-Badge.
   - Zwei aktive Challenges → zwei Top-5-Blöcke + zwei Spendentöpfe; beendete → Abschluss-Karte.
   - Stats nur auf Leaderboard-Seite, nicht auf Dashboard.
   - Screenshots → `.playwright/`, Server beenden.

## Risiken & Sicherheit
- **Zugriffsmodell bewusst offen:** "alle sehen alles" ist gewünscht. Folge: kein IDOR-Gate, aber
  weiterhin `@login_required` + `is_approved` überall — **kein** anonymer Zugriff.
- **Like-Gate-Entfernung:** unkritisch (rate-limited, login-pflichtig, low-risk Aktion).
- **Performance:** Statistik- & Summary-Service strikt Bulk (kein N+1, per Tests abgesichert);
  globaler Feed lädt mit Limit + Bulk-User/Challenge-Auflösung.
- **Non-destruktiv:** keine Migration, keine Dependency, kein `.env` → Prod-Deploy = `git pull
  && docker compose up -d`.
