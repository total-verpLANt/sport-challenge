# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/).

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
