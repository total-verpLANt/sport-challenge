# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/).

## [0.18.2] – 2026-06-15

### Behoben
- **Multi-Challenge-Anzeige: getrennte Sicht je Challenge** (Epic `0bv.2`): Die Anzeige-Routen `my_week` und `user_activities` hingen an `_active_participation().first()` und zeigten bei zwei parallel aktiven Challenges nur **eine** davon – Aktivitäten und Abwesenheiten der anderen „verschwanden" optisch. Beide Routen bestimmen die anzuzeigende Challenge jetzt über einen Selektor (`?challenge_id`, Default = erste, deterministisch); manipulierte/fremde Werte fallen sauber auf den Default zurück. `user_activities` berücksichtigt **alle** gemeinsamen Challenges von Betrachter und Ziel-Person (Sichtbarkeit bleibt auf gemeinsame Challenges beschränkt). Die Abwesenheits-Formulare in `my_week` binden nun an die gewählte Challenge (schließt `kkz`/M-1)

### Hinzugefügt
- **Challenge-Selektor (Dropdown) in der Anzeige**: `my_week.html` und `user_activities.html` zeigen bei mehreren (gemeinsamen) Challenges ein Auswahl-Dropdown; bei genau einer Teilnahme bleibt es ausgeblendet (kein UX-Regress). Die Eingabe-Formulare `log.html`/`import.html` belegen ihr Challenge-Select aus `?challenge_id` vor, sodass der Wechsel-Kontext aus „Meine Woche" erhalten bleibt

## [0.18.1] – 2026-06-15

### Behoben
- **Multi-Challenge-Eingabe: stiller Daten-Bug + IDOR** (Epic `0bv.1`): Bei zwei parallel aktiven Challenges zog die Eingabe (`log_submit`, `sick_period_submit`, `import_submit`) die Ziel-Challenge aus `_active_participation().first()` (ohne `ORDER BY`) — Aktivitäten, Importe und Abwesenheiten konnten so in der **falschen** Challenge landen. Außerdem wurde die Datums-Validierung gegen die zufällig gewählte statt die tatsächliche Challenge geprüft. Die Schreibpfade leiten die `challenge_id` jetzt ausschließlich aus einer per `_resolve_participation()` gegen `(current_user, challenge_id, status=accepted)` **verifizierten** Teilnahme ab. Damit ist zugleich ein IDOR/BOLA-Pfad geschlossen: Schreibzugriffe auf fremde oder nur „invited“/„bailed_out“ Challenges werden abgewiesen, und bei mehreren Teilnahmen ohne gültige Auswahl erfolgt **kein** stiller Schreibzugriff. Rückwärtskompatibel: bei genau einer akzeptierten Teilnahme greift weiterhin der Default

### Hinzugefügt
- **Challenge-Auswahl in den Eingabe-Formularen**: `log.html` (beide Tabs), `import.html` und die Abwesenheits-Form zeigen bei mehreren akzeptierten Teilnahmen ein Challenge-Select; bei genau einer Teilnahme bleibt das Feld implizit (kein UI-Regress)

## [0.18.0] – 2026-06-13

### Hinzugefügt
- **Teilnehmer-Übersicht mit Durchschnittswerten** auf der Challenge-Statistik-Seite: Neue Tabelle „Durchschnittswerte je Teilnehmer" unter den Top-3-Karten listet **alle** akzeptierten Teilnehmer (auch ohne Aktivität) mit ihrer **Ø Start-Uhrzeit**, **Ø Trainingsdauer** und der Anzahl Aktivitäten. Fehlende Werte erscheinen als „–". Rein additiv aus den bereits geladenen Aggregaten abgeleitet – keine zusätzliche DB-Query

## [0.17.1] – 2026-06-13

### Geändert
- **Frühaufsteher/Nachteule auf früheste/späteste Startzeit umgestellt** (Option B): Beide Ranglisten basierten auf der **durchschnittlichen** Startzeit pro Teilnehmer. Bei gemischten Trainingszeiten (z. B. früh + spät) landete der Schnitt irreführend in der Tagesmitte – ein Sportler mit echten 06:00-Einheiten erschien als „Frühaufsteher" erst gegen 10:00. „Frühaufsteher" wertet jetzt die **früheste** je erreichte Startzeit (`min`), „Nachteule" die **späteste** (`max`). Keine DB-/Query-Änderung, rein additive In-Memory-Ableitung aus den bereits geladenen Startzeiten

## [0.17.0] – 2026-06-13

### Hinzugefügt
- **Statistiken pro Challenge** (Issue `dqn`): Neuer Service `app/services/statistics.py` berechnet neun Top-3-Ranglisten je Challenge – meiste Zeit aktiv, meiste Aktivitäten, längste Wochen-Streak (eine Krankheit/Abwesenheit **bricht** die Serie), längste Tages-Streak, vielseitigster Sportler, beliebteste Aktivität (Likes), Frühaufsteher, Nachteule, längste Einzel-Session. Strikt Bulk-Load (kein N+1, per Query-Count-Wächter abgesichert). Anzeige als Karten-Grid unter dem Leaderboard (`dashboard/_statistics.html`)
- **Leaderboard pro Challenge** (`/dashboard/leaderboard/<public_id>`): Jedes Leaderboard ist über ein neues **Navbar-Dropdown** (Context-Processor `inject_nav_challenges`) erreichbar, das alle Challenges listet
- **Globaler News-Feed**: Der Dashboard-Feed zeigt jetzt Aktivitäten und Abwesenheiten **aller** Challenges (auch fremder), jeweils mit verlinktem Challenge-Badge
- **Mehrere Top-5-Blöcke**: Bei mehreren gleichzeitig aktiven Challenges erhält jede einen eigenen Top-5-Block und Spendentopf; beendete Challenges erscheinen als kompakte Abschluss-Karte (finale Spendensumme + Leaderboard-Link)

### Geändert
- **Offenes Lesemodell „alle sehen alles"**: Jeder eingeloggte Nutzer kann jedes Leaderboard, jede Aktivität und jeden Feed-Eintrag sehen – auch ohne Teilnahme an der Challenge. Das Like-Gate (vormals nur Teilnehmer) wurde entfernt; `login_required` und `is_approved` bleiben überall Pflicht (kein anonymer Zugriff)

## [0.16.7] – 2026-06-08

### Geändert
- **Dashboard-Leaderboard entlastet** (Issue `5gh`): `get_challenge_summary` löste die Strafberechnung bisher über pro-Zelle-Queries (~`Teilnehmer × Wochen × 7` SQL-Abfragen je Dashboard-Aufruf). Die benötigten Daten werden jetzt über drei Bulk-Queries (erfüllte Tage via `GROUP BY`, Krankheitszeiträume, Strafüberschreibungen) vorgeladen und rein im Speicher verrechnet; die Teilnehmer-User werden via `joinedload` eager geladen. Der Query-Aufwand ist dadurch **konstant** (≈3–4 Abfragen, unabhängig von Teilnehmer- und Wochenzahl) statt quadratisch zu wachsen. **Verhalten unverändert** – die berechneten Zellen- und Gesamtstrafen sind byte-genau identisch (durch Regressionstest gegen die kanonischen `penalty.py`-Funktionen abgesichert)

### Hinzugefügt
- Regressionstests `tests/test_weekly_summary.py`: Bulk-Pfad == `penalty.py`-Pfad über ein gemischtes Szenario (Aktivitäten, Krankheit, Override, Bailout) sowie ein Query-Count-Wächter gegen erneute N+1-Regressionen

## [0.16.6] – 2026-06-08

### Sicherheit
- **Upload-Inhalte serverseitig validieren** (Issue `43k`): Hochgeladene Medien werden nicht mehr allein anhand der Dateiendung akzeptiert, sondern ihr **Inhalt** wird geprüft. **Bilder** müssen via Pillow als gültiges JPEG/PNG/WEBP dekodierbar sein (inkl. Schutz vor Decompression-Bombs über `MAX_IMAGE_PIXELS`); **Videos** müssen via ffprobe einen echten Video-Stream in einem erlaubten Container (mp4/mov/webm) enthalten. Eine Datei mit erlaubter Endung aber gefälschtem Inhalt (z. B. HTML als `.jpg`, Text als `.mp4`, oder ein Bild mit `.mp4`-Endung) wird abgelehnt und hinterlässt **keine Orphan-Datei**. Der vom Client gelieferte Content-Type wird nicht als Wahrheit verwendet. Validierung zentral in `save_upload()` – alle Aufrufstellen (Activity-Medien, Bonus-Beweisvideo) profitieren ohne Routenänderung

### Hinzugefügt
- Neue Laufzeit-Abhängigkeit **Pillow** (`requirements.txt`) für die Bild-Inhaltsvalidierung. ffmpeg/ffprobe ist im Docker-Image bereits vorhanden

## [0.16.5] – 2026-06-08

### Sicherheit
- **Secure-Cookies env-gesteuert erzwingen** (Issue `26x`): Session- **und** Remember-Me-Cookie werden über die neue Variable `SECURE_COOKIES=1` als `Secure` markiert, sodass Browser sie nur über HTTPS senden (Cloudflare/HTTPS-Setup). Bislang sicherte Flask-Talisman nur das Session-Cookie (request-zeit-abhängig, an `app.debug` gekoppelt) – das **Remember-Me-Cookie war ungeschützt**. Zusätzlich werden `HttpOnly` (XSS-Härtung) und `SameSite=Lax` (CSRF-Härtung) für beide Cookies explizit gesetzt. Default `0` lässt lokale HTTP-Dev funktionsfähig; keine hardcoded Domain. Neue Var in `.env.example` dokumentiert

## [0.16.4] – 2026-06-08

### Sicherheit
- **Login-Lockout-DoS entschärft** (Issue `znn`): Ein Angreifer konnte ein fremdes Konto durch wenige absichtlich falsche Passwörter temporär aussperren (Account-DoS gegen Verfügbarkeit). Ein **korrektes Passwort durchbricht jetzt immer** eine eventuelle Lockout-Markierung – legitime Nutzer können sich nicht mehr aussperren lassen. Der Brute-Force-Schutz wandert auf ein **IP-Rate-Limit** (`10/min; 60/h`) am Login-POST (Client-IP via `CF-Connecting-IP` unter Cloudflare). `failed_login_attempts`/`locked_until` bleiben als Monitoring-Signal erhalten und werden beim Erreichen der Schwelle geloggt (inkl. IP). Fehlermeldungen unverändert generisch – keine zusätzliche User-Enumeration

## [0.16.3] – 2026-06-08

### Behoben
- **Medien-Lightbox** zeigte nach der Zugriffsschutz-Umstellung (v0.16.2) statt des Bildes ein leeres Scroll-Fenster mit Dateiname: Die geschützten Medien-URLs (`/media/activity/<id>`) haben keine Datei-Endung mehr, an der GLightbox den Typ erkennt. Behoben durch explizites `data-type="image"` an den Bild-Anchors (Dashboard-Feed + Activity-Details)
- **Bild-Vorschau in den Activity-Details** wurde durch `object-fit:cover` in der breiten Box mittig zugeschnitten (Großteil unsichtbar); jetzt `object-fit:contain` – das ganze Bild ist sichtbar, konsistent zur Video-Vorschau

## [0.16.2] – 2026-06-08

### Sicherheit
- **Medien-Uploads gegen anonymen Direktzugriff geschützt** (Issue `1ye`): Hochgeladene Bilder/Videos liegen nicht mehr unter `app/static/uploads` und sind damit nicht länger über geratene Direkt-URLs ohne Login abrufbar. Die Auslieferung erfolgt jetzt ausschließlich über eine login-geschützte Route (`/media/activity/<id>`, `/media/screenshot/<id>`) mit `X-Content-Type-Options: nosniff` und `Cache-Control: private`. Anonyme Requests erhalten 302 zum Login; HTML/JSON enthalten keine `static/uploads`-Direktlinks mehr

### Geändert
- Default-`UPLOAD_FOLDER` zeigt jetzt auf `<root>/data/uploads` (außerhalb von `static`); leeres `UPLOAD_FOLDER=` fällt sicher auf den Default zurück statt ins Arbeitsverzeichnis zu schreiben. Docker-Volume entsprechend auf `./data/uploads:/app/data/uploads` umgestellt (Host-Pfad unverändert – keine Datei-Migration nötig). DB-Spalten (`file_path`, `screenshot_path`) bleiben unverändert

## [0.16.1] – 2026-06-08

### Sicherheit
- **Host-Header-Poisoning gehärtet** (Issue `haf`): Externe Links in Passwort-Reset-, Admin-/Approval-Mails und der Strava-OAuth-`redirect_uri` werden nicht mehr aus dem (fälschbaren) Request-Host abgeleitet, sondern aus einer kontrolliert konfigurierten `PUBLIC_BASE_URL`. Damit kann ein Angreifer keinen Reset-Link mehr auf eine Fremddomain umlenken
- Neue, konfigurierbare Host-Policy (keine hartkodierte Domain): `PUBLIC_BASE_URL` (kanonische Basis externer Links), `TRUSTED_HOSTS` (Allowlist — Flask weist fremde Host-Header mit HTTP 400 ab) und `PROXY_X_HOST` (ProxyFix vertraut `X-Forwarded-Host` nur noch, wenn explizit aktiviert; Default `0`)

## [0.16.0] – 2026-06-08

### Geändert
- Die bisherige **Krankmeldung** ist jetzt eine allgemeine **Abwesenheit**: Wording und Emojis (🤒 → 🚫) im gesamten UI neutralisiert, da es auch andere Gründe gibt, zeitweise nicht teilzunehmen (Urlaub, Dienstreise …). Die Strafberechnung bleibt unverändert (pro 2 Abwesenheitstage wird eine benötigte Aktivität abgezogen)

### Neu
- Beim Eintragen einer Abwesenheit kann ein **optionaler Grund** angegeben werden (Textfeld, max. 500 Zeichen)
- Eingetragene Abwesenheiten erscheinen jetzt im **Dashboard-Feed** (Zeitraum + Grund, ohne Motivationsspruch) und können wie Aktivitäten **gelikt** werden

### Behoben
- `/dashboard/feed`: fehlender `url_for`-Import behoben, der den Endpunkt bei Aktivitäten mit hochgeladenen Medien zum Absturz gebracht hätte

## [0.15.2] – 2026-06-05

### Geändert
- Admin-Benachrichtigung bei Neuregistrierung wird jetzt als **ein einziger BCC-Request** an alle Admins versendet (statt N Einzel-Requests): spart Mailgun-Requests/Rate-Limit und verbirgt die Admin-Adressen voreinander (kein PII-Leak im To-Feld). `MailgunService.send()` unterstützt dafür einen neuen `bcc`-Parameter

## [0.15.1] – 2026-06-05

### Behoben
- Admin-Benachrichtigung bei Neuregistrierung: Schlägt der Mailversand an einen Admin fehl (z.B. Rate-Limit), werden die übrigen Admins jetzt trotzdem benachrichtigt (Teilausfall-Härtung — Versand pro Admin isoliert)

## [0.15.0] – 2026-05-27

### Neu
- Dashboard zeigt neben dem Like-Herz die Spitznamen der Liker an (z.B. „Tick, Trick und Track gefällt das"); ab 6 Likern wird abgekürzt

## [0.14.0] – 2026-05-19

### Neu
- "Meine Woche" zeigt jetzt **mehrere Krankmeldungen** derselben Woche gleichzeitig: jede Periode hat eine eigene Edit-Form und einen eigenen Löschen-Button; ein separates Eingabefeld erlaubt das Anlegen einer weiteren Krankmeldung
- Karten-Header zeigt bei mehreren Perioden eine Kompakt-Übersicht aller Zeiträume

## [0.13.2] – 2026-05-19

### Behoben
- "Meine Woche": Krankgemeldete Tage werden jetzt pro Tag mit Badge (🤒 Krank) und farbiger Karten-Markierung sichtbar gemacht — Aktivitäten an Krank-Tagen werden weiterhin korrekt angezeigt
- "Meine Woche" stürzt nicht mehr ab, wenn mehrere Krankmeldungen in dieselbe Woche fallen (`scalar_one_or_none` → Liste)

## [0.13.1] – 2026-05-11

### Sicherheit
- Passwort-Reset-Token sind jetzt **One-Time-Use**: Nach erfolgreichem Passwort-Wechsel wird der Link automatisch ungültig (stateless via Hash-Suffix im Token-Payload, keine Migration nötig)

## [0.13.0] – 2026-05-06

### Neu
- Krankmeldungen nutzen jetzt ein Von/Bis-Datumsmodell (`SickPeriod`) statt dem wochenbasierten `SickWeek`-Modell
- Zukunftsdaten erlaubt: Krankmeldungen für bevorstehende Zeiträume können vorab eingetragen werden
- Krankmeldung kürzen: Enddatum nachträglich anpassbar (Frühgenesungs-Flow)
- Krankmeldungen werden auf Challenge-Grenzen geclampt
- Overlap-Prüfung: Überschneidende Perioden pro Teilnehmer werden abgelehnt

### Geändert
- Datenbankschema: `sick_weeks`-Tabelle durch `sick_periods` ersetzt (Migration `a3f7e2b9c1d5`)
- Route `/challenge-activities/sick-period` (POST) ersetzt `/challenge-activities/sick-week`
- Penalty-Berechnung nutzt Tage-Überschneidung statt Wochenstartdatum

## [0.12.1] – 2026-05-02

### Neu
- Trainingsnotiz nachträglich bearbeitbar: Die "Medien hinzufügen"-Seite enthält jetzt eine Textarea, über die Notizen auch nach dem initialen Erfassen gesetzt, geändert oder gelöscht werden können
- Trainingsnotiz direkt auf der Aktivitäts-Detailseite bearbeitbar (kein Umweg über "Medien hinzufügen")

### Behoben
- Passwort-vergessen: Rate-Limit greift jetzt nur auf POST-Anfragen, nicht mehr auf die GET-Seite
- Rate-Limiter liest echte Client-IP aus dem `CF-Connecting-IP`-Header (korrekte Sperrung hinter Cloudflare-Tunnel)

## [0.12.0] – 2026-05-02

### Neu
- E-Mail-Integration via Mailgun REST API (`app/services/mailer.py`)
- Passwort-vergessen-Flow: Link im Login, Route `/auth/forgot-password`, Reset-Link per E-Mail mit signiertem Token (itsdangerous, 1h TTL, timing-sicher)
- Admin-Benachrichtigung per E-Mail bei jeder Neuregistrierung
- Bestätigungsmail an User bei Admin-Freischaltung
- 24 neue Tests (Mailer-Unit-Tests + Password-Reset-Integrationstests)

### Konfiguration
- Neue Env-Variablen: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_SENDER`, `MAILGUN_BASE_URL` (EU-Region: `https://api.eu.mailgun.net/v3`)
- App startet ohne Mailgun-Config, Mailversand schlägt dann erst beim Senden fehl (kein Crash beim Start)

## [0.11.0] – 2026-05-02

### Neu
- Containerisierung: Docker-Image mit Gunicorn, Docker Compose für Prod-Deployment
- CI/CD: GitHub Actions-Pipeline baut und pusht Docker-Image automatisch zu Docker Hub (`stoertebeker2k/sport-challenge`)
- Access-Log: HTTP-Zugriffe werden in `logs/access.log` geschrieben (RotatingFileHandler, 10 MB, 5 Backups)
- ProxyFix-Middleware für echte Client-IP hinter cloudflared-Tunnel (Rate-Limiting + Logging korrekt)

### Behoben
- Docker Hub Username in CI-Pipeline von `changeme` auf `stoertebeker2k` korrigiert
- CI: Version wird direkt aus `app/version.py` per `grep` ausgelesen statt per App-Import (verhindert Import-Fehler ohne DB)

## [0.10.0] – 2026-05-01

### Neu
- Bonus-Challenge: Video-Beweis-Upload (MP4, MOV, WebM, max. 50 MB) beim Zeiteintragen verpflichtend
- Bonus-Challenge: Aufnahmedatum wird automatisch aus Video-Metadaten (ffprobe `creation_time`) ausgelesen und in der Rangliste angezeigt
- Bonus-Challenge: Wanderpokal-Gesamtwertung – beste Einzelzeit pro Nutzer über alle Datums-Runden
- Bonus-Challenge: Admin kann beim Erstellen mehrere Termine auf einmal eingeben (dynamische Datumsfelder)
- Bonus-Challenge: Einsendungen jederzeit möglich (kein Datum-Limit), Vertrauen auf Ehrlichkeit

### Behoben
- `delete_upload()` verwendete `static_folder` statt `UPLOAD_FOLDER` – Video-Orphans blieben in Tests und potenziell auch in Produktionsumgebungen mit abweichendem Upload-Pfad zurück

## [0.9.0] – 2026-04-30

### Neu
- Benutzer können eigene Krankmeldungen löschen (mit Bestätigungs-Dialog)
- Admin kann Krankmeldungen aller Nutzer löschen
- Admin kann Aktivitäten aller Nutzer löschen
- Admin kann Bonus-Challenges inkl. aller Einträge löschen
- Admin kann Challenges inkl. aller Aktivitäten, Krankmeldungen und Bonus-Challenges löschen (vollständige 7-stufige Cascade)

### Behoben
- Filesystem-Leak beim Löschen eines Nutzers: ActivityMedia-Dateien blieben physisch auf dem Server, weil Bulk-Delete keine ORM-Cascades auslöst

## [0.8.2] – 2026-04-29

### Neu
- Partielle Krankmeldung: 1–7 einzelne Krankentage pro Woche meldbar (statt nur ganze Woche)
- Rückwirkende Krankmeldung über Wochen-Navigation in „Meine Woche" (beliebige Vorwochen)
- Krankmeldung auch direkt über „Eintragen" (Tab „Krankmeldung") mit freier Datumswahl erreichbar
- Formel: je 2 Krankentage = 1 Aktivitäts-Abzug vom Wochenziel (`deductions = sick_days // 2`); ab 6 Tagen keine Strafe
- Effektives Wochenziel wird in der Fortschrittsanzeige ausgewiesen
- Bestehende Krankmeldung kann über dasselbe Formular korrigiert werden

## [0.8.1] – 2026-04-29

### Sicherheit
- fix(security): Stored XSS via `original_filename` im AJAX-Feed-Card-Builder behoben: Media-Elemente werden jetzt per DOM-API (`createElement`/Property-Set) erzeugt statt via innerHTML-String-Konkatenation (kein Attribut-Breakout mehr möglich)
- Defense-in-Depth: `werkzeug.utils.secure_filename()` wird auf Dateinamen vor der Persistierung angewendet, eliminiert `"`, `<`, `>` und Pfad-Separatoren aus `original_filename`

## [0.8.0] – 2026-04-29

### Neu
- Social-Media-Timeline im Dashboard: Activity-Feed mit den 10 neuesten Aktivitäten aller Challenge-Teilnehmer (AJAX-Nachladen, je 10 weitere)
- Jede Feed-Karte zeigt Sport-Typ, Dauer, Datum/Uhrzeit, zufälligen Motivationsspruch (100 deutsche Quotes), Medien (Fotos/Videos) und Trainingsnotiz
- Like/Heart-Button pro Aktivität (AJAX-Toggle, CSRF-geschützt, Rate-Limit 30/min, Teilnahme-Guard)
- Top-5-Leaderboard auf der Dashboard-Startseite; vollständiges Leaderboard unter `/dashboard/leaderboard` erreichbar
- „Leaderboard"-Link in der Navbar
- ActivityComment-Model als Code-Stub für spätere Implementierung (kein UI)
- GLightbox-Instanz bleibt nach AJAX-Nachladen funktionsfähig (`lightbox.reload()`)

## [0.7.7] – 2026-04-29

### Neu
- Optionales Freitextfeld „Trainingsnotiz" (max. 2000 Zeichen) beim Aktivitäten-Eintragen; Notiz wird in der Detail-Ansicht und als Kurzvorschau in der Wochenansicht angezeigt

## [0.7.6] – 2026-04-29

### Neu
- Benutzer können ihr Passwort im Profil (`/settings/`) selbst ändern (altes Passwort als Bestätigung, Sichtbarkeits-Toggle, Rate-Limit 5/min)

## [0.7.5] – 2026-04-29

### Geändert
- `migrations/env.py`: veralteten `db.get_engine()`-Aufruf durch `db.engine` ersetzt (Flask-SQLAlchemy >= 3)

## [0.7.4] – 2026-04-29

### Geändert
- Produktions-Webserver von Flask Dev-Server auf Gunicorn umgestellt (3 Worker, graceful reload via SIGHUP)

## [0.7.3] – 2026-04-29

### Neu
- Admin: User-Detailseite (`/admin/users/<id>`) mit E-Mail, Nickname, Rolle, Approval-Status und eingerichteten Integrationen (nur `provider_type`)
- Admin: Konto sperren/entsperren (setzt `is_approved` – gesperrte User können sich nicht einloggen)
- Admin: Passwort eines Users direkt zurücksetzen (serverseitige Mindestlängen-Validierung)
- Admin: User löschen mit zweistufiger Bestätigung (Bootstrap-Modal + E-Mail-Eingabe) und manuellem Cascade-Delete

### Sicherheit
- Löschen blockiert wenn User Challenges erstellt hat (Datenverlust-Schutz)
- E-Mail-Bestätigung serverseitig geprüft (Defense in depth, kein Verlass auf JS)
- Self-Delete und Self-Suspend blockiert

## [0.7.2] – 2026-04-29

### Neu
- Toggle-Admin-Funktion in Benutzerverwaltung (Admin ↔ User)

### Sicherheit
- Last-Admin-Guard verhindert Null-Admin-Zustand (Defense-in-depth)

## [0.7.1] – 2026-04-29

### Neu
- SVG-Favicon (Läufer-Icon, Darkmode-responsiv via `prefers-color-scheme`)

## [0.7.0] – 2026-04-29

### Neu
- Darkmode-Toggle in der Navbar (🌙/☀️), Persistenz via localStorage
- FOUC-Prevention: Theme wird vor Bootstrap-CSS-Load gesetzt
- Bootstrap 5.3 `data-bs-theme` auf `<html>` für natives Dark-Mode-Switching

## [0.6.0] – 2026-04-28

### Neu
- Versionsnummer in der Navbar (klickbar → Changelog)
- Changelog-Seite unter `/changelog`

## [0.5.0] – 2026-04-27

### Neu
- Lightbox-Medienansicht via GLightbox 3.3.1
- Einzelnes Medium aus Aktivität löschen (Owner-Guard)

## [0.4.0] – 2026-04-27

### Neu
- Multi-File-Upload für Fotos und Videos (bis 50 MB) pro Aktivität
- Drag-and-Drop-Interface für Medien-Upload
- Retroaktiver Upload via Route `/challenge-activities/<id>/media/add`
- Medien-Galerie in Aktivitätsdetail-Ansicht (Video + Bild)
- Thumbnails in Wochen- und Benutzeransichten

### Sicherheit
- Path-Traversal-Guard (`is_relative_to`) in Upload-Lösch-Route
- `media-src 'self'` explizit in CSP gesetzt

## [0.3.0] – 2026-04-27

### Neu
- Öffentliche Challenge-URLs via UUID (`public_id`)
- Challenge auf öffentlich/privat stellbar (`is_public`)

## [0.2.0] – 2026-04-26

### Neu
- Challenge-System mit Leaderboard und Strafpunkten
- Wochenziele (2 oder 3 Tage), Krankheitswochen, Penalty-Override
- Bonus-Challenges mit Zeitwertung und Ranking
- Aktivitäten-Eintragung (manuell, Garmin-Import, Strava-Import)
- Screenshot-Upload pro Aktivität

## [0.1.0] – 2026-04-24

### Neu
- Multi-User-Unterstützung mit Flask-Login (scrypt-Passwort-Hashing)
- Connector-Architektur: Garmin Connect + Strava OAuth
- Fernet-verschlüsselte Token-Speicherung in der Datenbank
- Admin-Bereich für Benutzerverwaltung

## [0.0.1] – 2026-04-01

### Neu
- Single-User Flask-App mit Garmin-Aktivitätsübersicht
- Wochenansicht mit 30-Minuten-Filter
