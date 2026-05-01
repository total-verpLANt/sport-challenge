# Prod-Migration Guide: bare-metal → Docker

Schritt-für-Schritt-Anleitung zur Migration der produktiven sport-challenge-Instanz von bare-metal (cloudflared + Python/Gunicorn direkt) auf Docker-Deployment.

---

## Kapitel 1: Voraussetzungen

Docker und Docker Compose Plugin müssen auf dem Zielsystem installiert sein.

**Installation (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER   # Logout/Login danach erforderlich
```

**Prüfbefehle:**
```bash
docker --version
docker compose version
```

Erwartete Ausgabe: mindestens Docker 24.x und Compose 2.x.

---

## Kapitel 2: Sicherung (KRITISCH – vor allem anderen)

**Vor jedem weiteren Schritt MÜSSEN Backups erstellt werden.**

```bash
# SQLite-Datenbank sichern
cp instance/sport-challenge.db instance/sport-challenge.db.backup-$(date +%Y%m%d)

# Uploads (Fotos, Videos) sichern
tar -czf uploads-backup-$(date +%Y%m%d).tar.gz app/static/uploads/

# Git-Tag als Rollback-Punkt setzen
git tag pre-docker-migration && git push origin pre-docker-migration
```

Backups vor dem Fortfahren verifizieren:
```bash
ls -lh instance/sport-challenge.db.backup-*
ls -lh uploads-backup-*.tar.gz
git tag | grep pre-docker
```

---

## Kapitel 3: .env.prod erstellen

> ⚠️ **KRITISCH: `SECRET_KEY` MUSS identisch zum aktuell laufenden System sein!**
>
> Ein geänderter `SECRET_KEY` macht **alle gespeicherten Garmin- und Strava-Tokens unbrauchbar**,
> da die Connector-Credentials mit Fernet (HKDF-abgeleitet vom SECRET_KEY) verschlüsselt sind.
> Alle Nutzer müssten ihre Garmin/Strava-Verbindung neu einrichten.

**Aktuellen Key aus der laufenden .env auslesen:**
```bash
grep SECRET_KEY .env
```

**`.env.prod` Vorlage:**
```
SECRET_KEY=<identisch zum laufenden System!>
DATABASE_URL=sqlite:///sport-challenge.db
STRAVA_CLIENT_ID=<falls konfiguriert>
STRAVA_CLIENT_SECRET=<falls konfiguriert>
FLASK_APP=run.py
GUNICORN_WORKERS=1
```

`.env.prod` darf **nicht** ins Git-Repository eingecheckt werden (ist bereits in `.gitignore`).

---

## Kapitel 4: Daten-Verzeichnisse anlegen

Docker-Volumes erwarten die Daten unter `data/`:

```bash
mkdir -p data/instance data/uploads data/logs

# Datenbank übertragen
cp instance/sport-challenge.db data/instance/

# Uploads übertragen
cp -r app/static/uploads/. data/uploads/
```

Übertragung verifizieren:
```bash
ls -lh data/instance/sport-challenge.db
ls data/uploads/ | head -5
```

---

## Kapitel 5: Docker Image holen + Container starten

```bash
# Image aus Docker Hub holen (Produktiv-Empfehlung)
docker compose pull

# Alternativ: lokaler Build
docker compose build

# Container im Hintergrund starten
docker compose up -d

# Migrations-Output und Start-Logs beobachten
docker compose logs -f
```

Warten bis die Zeile `Application startup complete` erscheint, dann mit Strg+C den Log-Follow beenden.

---

## Kapitel 6: Smoke-Test

```bash
# HTTP-Statuscode prüfen – erwartet: 302 (Redirect zu /auth/login)
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/

# Container-Status prüfen – "healthy" abwarten
docker compose ps
```

Erwartetes Ergebnis:
- `curl` liefert `302`
- `docker compose ps` zeigt Status `healthy` (nicht `starting` oder `unhealthy`)

Bei `unhealthy` oder Fehler: `docker compose logs` für Details prüfen.

---

## Kapitel 7: cloudflared Tunnel anpassen

Falls cloudflared als systemd-Service läuft und der Tunnel bereits auf `localhost:5000` zeigt, ist keine Änderung nötig.

**Falls die Tunnel-Config angepasst werden muss:**
```bash
# Config-Datei öffnen
nano ~/.cloudflared/config.yml
```

Relevante Zeile:
```yaml
url: http://localhost:5000
```

**Nach einer Änderung cloudflared neu starten:**
```bash
sudo systemctl restart cloudflared
sudo systemctl status cloudflared
```

Abschließend die öffentliche URL im Browser aufrufen und prüfen, ob die Login-Seite erscheint.

---

## Kapitel 8: Alten Prozess stoppen

Erst stoppen, wenn Docker-Container (Kapitel 5–6) und cloudflared-Tunnel (Kapitel 7) erfolgreich laufen.

```bash
# Gunicorn/Python-Prozess identifizieren
ps aux | grep gunicorn

# Stoppen via systemd (falls als Service konfiguriert)
sudo systemctl stop sport-challenge
sudo systemctl disable sport-challenge   # Verhindert Neustart nach Reboot

# Alternativ: direkt per PID beenden
kill <PID>
```

Sicherstellen, dass kein alter Prozess mehr auf Port 5000 lauscht:
```bash
ss -tlnp | grep 5000
# Nur noch der Docker-Container sollte erscheinen
```

---

## Kapitel 9: Rollback (falls nötig)

Falls nach der Migration Probleme auftreten, kann innerhalb von Minuten zum alten Zustand zurückgekehrt werden.

```bash
# Docker-Container stoppen und entfernen
docker compose down

# Alten Prozess neu starten (systemd)
sudo systemctl start sport-challenge

# Oder manuell (Beispiel)
# SECRET_KEY=<key> .venv/bin/gunicorn -w 1 -b 0.0.0.0:5000 "run:app"

# cloudflared Tunnel ggf. zurückstellen auf alten Prozess
sudo systemctl restart cloudflared
```

**Daten-Rollback (falls DB korrumpiert):**
```bash
cp instance/sport-challenge.db.backup-<YYYYMMDD> instance/sport-challenge.db
```

**Git-Rollback auf den gesetzten Tag:**
```bash
git checkout pre-docker-migration
```
