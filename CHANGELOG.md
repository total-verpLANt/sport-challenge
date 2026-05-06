# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/).

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
