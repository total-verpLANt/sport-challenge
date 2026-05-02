# Plan: Dockerisierung sport-challenge + Docker Hub Deployment

**Erstellt:** 2026-05-01
**Ziel:** Flask-App containerisieren, über Docker Hub deployen, Produktion von bare-metal (cloudflared + Python direkt) auf Docker migrieren.
**Research:** `.schrammns_workflow/research/2026-05-01-dockerisierung-sport-challenge.md`
**Status:** draft

---

## Zusammenfassung

Keine Docker-Infrastruktur vorhanden – Greenfield-Containerisierung in 4 Wellen.
Drei Code-Blocker müssen vor dem ersten Build behoben werden:
1. `config.py:15` – `UPLOAD_FOLDER` nicht per ENV überschreibbar
2. `requirements.txt` – pytest/pytest-flask in prod-deps gemischt
3. Flask-Limiter In-Memory: Entscheidung → 1 Gunicorn-Worker (kein Redis)

**Entscheidungen (vorab getroffen):**
- Flask-Limiter: 1 Worker, kein Redis
- Docker Hub Image: öffentlich
- WSGI-Server: Gunicorn (bereits in requirements.txt)
- Base-Image: `python:3.13-slim` + apt ffmpeg
- Python: 3.14 lokal, 3.13 im Image (3.14-slim Verfügbarkeit ungewiss)

---

## Files to Modify

| File | Change | Wave |
|------|--------|------|
| `config.py` | `UPLOAD_FOLDER` via `os.environ.get()` konfigurierbar | W1 |
| `requirements.txt` | pytest/pytest-flask entfernen | W1 |
| `requirements-dev.txt` | **NEW** – pytest, pytest-flask, (playwright) | W1 |
| `Dockerfile` | **NEW** – python:3.13-slim, ffmpeg, non-root, uv | W2 |
| `entrypoint.sh` | **NEW** – `flask db upgrade && exec gunicorn` | W2 |
| `.dockerignore` | **NEW** – alle nicht-prod-Dateien ausschließen | W2 |
| `docker-compose.yml` | **NEW** – 3 Volumes, env_file, healthcheck, Port 5000 | W2 |
| `.env.example` | `UPLOAD_FOLDER`, `GUNICORN_WORKERS`, `FLASK_APP` ergänzen | W2 |
| `.github/workflows/docker-publish.yml` | **NEW** – pytest on PR, build+push on main | W3 |
| `docs/prod-migration-guide.md` | **NEW** – bare-metal → Docker Schritt-für-Schritt | W4 |

**Baseline-Audit (verifiziert):**
- `config.py`: 16 LOC (`wc -l config.py`)
- `requirements.txt`: 15 LOC, pytest auf Zeile 11-12 (`grep -n "pytest" requirements.txt`)
- `UPLOAD_FOLDER` in `config.py:15` (1 Vorkommen), gelesen in `uploads.py:31,41,54` via config (korrekt)
- Tests: 158 gesammelt (`pytest --collect-only -q`)
- Docker-Dateien: alle 4 fehlen (`find . -name "Dockerfile*" ...`)
- `.github/`: nicht vorhanden

---

## Implementation Detail

### I-01: UPLOAD_FOLDER per ENV konfigurierbar (config.py:15)

**Datei:** `config.py`

Aktuelle Zeile 15:
```python
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "uploads")
```

Änderung:
```python
_default_upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "uploads")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", _default_upload_folder)
```

Kein Breaking Change: Default bleibt identisch. `uploads.py:31,41,54` liest über `current_app.config["UPLOAD_FOLDER"]` – kein Anpassungsbedarf.

**Tests:** Kein neuer Test nötig – bestehende Upload-Tests decken das ab (UPLOAD_FOLDER via `tempfile.gettempdir()` in `conftest.py`).

---

### I-02: requirements.txt splitten

**Datei:** `requirements.txt` (modifizieren), `requirements-dev.txt` (neu)

`requirements.txt` (prod – pytest-Zeilen entfernen):
```
garminconnect==0.3.3
stravalib
flask>=3.0
python-dotenv>=1.0
Flask-SQLAlchemy==3.1.1
Flask-Migrate==4.1.0
Flask-Login==0.6.3
Flask-WTF==1.3.0
Flask-Limiter==4.1.1
cryptography==46.0.7
email-validator>=2.0
flask-talisman>=1.0
gunicorn>=22.0
```

`requirements-dev.txt` (neu):
```
-r requirements.txt
pytest>=8.0
pytest-flask>=1.3
```

`CLAUDE.md` Build-Befehl muss angepasst werden: `uv pip install -r requirements-dev.txt` für lokale Entwicklung.

---

### I-03: Dockerfile

**Datei:** `Dockerfile` (neu)

```dockerfile
FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install uv

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY . .

RUN useradd -m -u 1001 appuser \
    && mkdir -p /app/instance /app/logs /app/app/static/uploads \
    && chown -R appuser:appuser /app/instance /app/logs /app/app/static/uploads

USER appuser

COPY entrypoint.sh /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
```

Hinweise:
- `curl` wird für den Healthcheck-CMD in compose benötigt
- Layer-Reihenfolge: requirements.txt vor Code-Copy (Cache-Effizienz)
- `uv pip install --system`: installiert in System-Python (kein venv im Container nötig)
- `entrypoint.sh` wird separat via I-04 geliefert

---

### I-04: entrypoint.sh

**Datei:** `entrypoint.sh` (neu)

```bash
#!/bin/sh
set -e

echo "Running database migrations..."
flask db upgrade

echo "Starting Gunicorn..."
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers "${GUNICORN_WORKERS:-1}" \
  --timeout 120 \
  --access-logfile - \
  run:app
```

- `set -e` – bricht bei Migrationsfehler ab (kein defekter Start)
- `exec` – übergibt PID 1 an gunicorn (korrekte SIGTERM-Weiterleitung)
- `--access-logfile -` – Gunicorn-Zugriffslog auf stdout (Docker-konform)
- `FLASK_APP=run.py` muss als ENV in docker-compose.yml stehen

---

### I-05: .dockerignore

**Datei:** `.dockerignore` (neu)

```
# Venv und Caches
.venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# Secrets und lokale Daten
.env
instance/
logs/
*.db
app.db

# Uploads (Volume)
app/static/uploads/

# Dev-Tools und CI
.git/
.github/
.beads/
.dolt/
.serena/
.playwright-mcp/
.schrammns_workflow/
.claude/
.beads-credential-key

# Testdaten und Screenshots
tests/
*.png
*.jpeg
*.webm
dashboard-*.md
playwright-report/
test-results/

# Dokumentation (nicht fürs Image)
docs/
CHANGELOG.md
```

---

### I-06: docker-compose.yml

**Datei:** `docker-compose.yml` (neu)

```yaml
services:
  web:
    image: ${DOCKERHUB_USERNAME:-changeme}/sport-challenge:${IMAGE_TAG:-latest}
    build: .
    restart: unless-stopped
    env_file: .env.prod
    environment:
      FLASK_APP: run.py
      GUNICORN_WORKERS: "1"
    volumes:
      - ./data/instance:/app/instance
      - ./data/uploads:/app/app/static/uploads
      - ./data/logs:/app/logs
    ports:
      - "127.0.0.1:5000:5000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
```

Hinweise:
- `build: .` ermöglicht lokalen Build (`docker compose up --build`)
- Port nur auf `127.0.0.1` gebunden (cloudflared/Reverse-Proxy vorgelagert)
- `./data/` als Volume-Basis → Verzeichnis muss auf Prod-Server erstellt werden
- `.env.prod` enthält SECRET_KEY, DATABASE_URL etc. (niemals ins Repo)

---

### I-07: .env.example aktualisieren

**Datei:** `.env.example`

Neue Vars ergänzen:
```
# REQUIRED: App startet nicht ohne diesen Key (mind. 32 zufällige Zeichen in Produktion)
SECRET_KEY=aendere-mich-in-produktion

# Strava OAuth (optional – ohne diese Var verschwindet Strava aus der UI)
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=

# Docker / Deployment
# Upload-Verzeichnis (Standard: app/static/uploads relativ zum Projektroot)
# In Docker via Volume: UPLOAD_FOLDER=/app/app/static/uploads
UPLOAD_FOLDER=

# WSGI-Server: Anzahl Gunicorn-Worker (Standard: 1 – wegen In-Memory Rate-Limiter)
GUNICORN_WORKERS=1

# Flask CLI (für flask db upgrade im Entrypoint)
FLASK_APP=run.py
```

---

### I-08: GitHub Actions Workflow

**Datei:** `.github/workflows/docker-publish.yml` (neu)

```yaml
name: Docker Publish

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  IMAGE_NAME: ${{ secrets.DOCKERHUB_USERNAME }}/sport-challenge

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install dev dependencies
        run: pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest -v
        env:
          SECRET_KEY: ci-test-key-not-for-production

  publish:
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Read version
        id: version
        run: echo "version=$(python -c 'from app.version import __version__; print(__version__)')" >> "$GITHUB_OUTPUT"

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ${{ env.IMAGE_NAME }}:latest
            ${{ env.IMAGE_NAME }}:${{ steps.version.outputs.version }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

GitHub Secrets (einmalig im Repo unter Settings → Secrets → Actions):
- `DOCKERHUB_USERNAME`: Docker Hub Benutzername
- `DOCKERHUB_TOKEN`: Docker Hub Access Token (nicht Passwort!)

---

### I-09: Prod-Migration Guide

**Datei:** `docs/prod-migration-guide.md` (neu)

Inhalt (Kapitel):
1. Voraussetzungen (Docker installieren, Compose-Plugin)
2. Daten sichern (SQLite-Backup, Uploads-Backup)
3. `.env.prod` erstellen (SECRET_KEY identisch zum laufenden System!)
4. `data/`-Verzeichnisse anlegen und Daten kopieren
5. Docker Image pullen: `docker compose pull`
6. Container starten: `docker compose up -d`
7. Smoke-Test: `curl http://localhost:5000/` → 302
8. cloudflared Tunnel-Config anpassen (Port → Container-Port)
9. Alten Python-Prozess stoppen (systemd/screen/nohup)
10. Rollback-Strategie (docker compose down → alten Prozess neu starten)

**KRITISCH in Schritt 3:** SECRET_KEY muss EXAKT identisch zum laufenden System sein. Sonst werden alle gespeicherten Garmin/Strava-Tokens unbrauchbar (Fernet-Key-Derivation via HKDF).

---

## Wave-Struktur

```
Wave 1 (parallel): I-01, I-02
         ↓
Wave 2 (parallel): I-03, I-04, I-05, I-06, I-07
         ↓
Wave 3: I-08                 Wave 4: I-09
```

### Dependency-Validierung

| Abhängigkeit | Typ | Begründung |
|---|---|---|
| I-03 nach I-02 | File-Dependency | Dockerfile kopiert `requirements.txt` – muss bereits gesplittet sein |
| I-07 nach I-01 | File-Dependency | `.env.example` dokumentiert neue `UPLOAD_FOLDER`-Var |
| I-08 nach I-03 | File-Dependency | GitHub Actions baut Dockerfile, muss existieren |
| I-08 nach I-02 | File-Dependency | CI installiert `requirements-dev.txt`, muss existieren |
| I-09 nach I-06 | File-Dependency | Guide referenziert `docker-compose.yml`-Syntax |
| I-04,I-05,I-06 nach I-01 | Logisch | UPLOAD_FOLDER-Var muss vor compose/entrypoint bekannt sein |

Alle Wave-2-Issues sind untereinander unabhängig (können parallel laufen).

---

## Issues

### Wave 1

#### I-01: UPLOAD_FOLDER per ENV konfigurierbar machen
**Typ:** task | **Priorität:** P1 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Dateien:** `config.py`

**Was:** `config.py:15` – hardcodierten Pfad durch `os.environ.get("UPLOAD_FOLDER", <default>)` ersetzen.

**Acceptance Criteria:**
- [ ] `config.py:15`: `UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", _default_upload_folder)`
- [ ] Default-Wert identisch zum bisherigen Hardcode
- [ ] `pytest -v` → alle 158 Tests grün
- [ ] `python -c "from config import Config"` ohne ERROR (SECRET_KEY setzen)

---

#### I-02: requirements.txt splitten (prod/dev)
**Typ:** task | **Priorität:** P1 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Dateien:** `requirements.txt`, `requirements-dev.txt` (NEW)

**Was:** `pytest>=8.0` und `pytest-flask>=1.3` aus `requirements.txt` entfernen, `requirements-dev.txt` mit `-r requirements.txt` + test-deps erstellen.

**Acceptance Criteria:**
- [ ] `requirements.txt`: kein `pytest` oder `pytest-flask` mehr (verifiziert: `grep pytest requirements.txt` → leer)
- [ ] `requirements-dev.txt` existiert mit `-r requirements.txt`, `pytest>=8.0`, `pytest-flask>=1.3`
- [ ] `pip install -r requirements-dev.txt && pytest -v` → 158 Tests grün
- [ ] CLAUDE.md Build-Befehl aktualisiert auf `uv pip install -r requirements-dev.txt`

---

### Wave 2

#### I-03: Dockerfile erstellen
**Typ:** task | **Priorität:** P1 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Abhängig von:** I-02 (requirements.txt split)
**Dateien:** `Dockerfile` (NEW)

**Was:** Dockerfile nach Spec in Implementation Detail Sektion I-03 erstellen.

**Acceptance Criteria:**
- [ ] `Dockerfile` existiert im Projektroot
- [ ] `docker build -t sport-challenge:test .` läuft ohne Error
- [ ] Image enthält ffprobe: `docker run --rm sport-challenge:test ffprobe -version`
- [ ] Image startet nicht ohne SECRET_KEY (RuntimeError erwartet): `docker run --rm sport-challenge:test` → Exit-Code ≠ 0

---

#### I-04: entrypoint.sh erstellen
**Typ:** task | **Priorität:** P1 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Dateien:** `entrypoint.sh` (NEW)

**Was:** `entrypoint.sh` nach Spec in I-04 Sektion erstellen, ausführbar machen.

**Acceptance Criteria:**
- [ ] `entrypoint.sh` existiert
- [ ] `chmod +x entrypoint.sh` ausgeführt (oder im Dockerfile: `RUN chmod +x /entrypoint.sh`)
- [ ] `#!/bin/sh` + `set -e` + `flask db upgrade` + `exec gunicorn ...`
- [ ] `shellcheck entrypoint.sh` (falls installiert) → keine Fehler

---

#### I-05: .dockerignore erstellen
**Typ:** task | **Priorität:** P1 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Dateien:** `.dockerignore` (NEW)

**Was:** `.dockerignore` nach Spec in I-05 Sektion erstellen.

**Acceptance Criteria:**
- [ ] `.dockerignore` existiert
- [ ] `.env` ist enthalten (kein Secret ins Image)
- [ ] `instance/` ist enthalten (kein DB-File ins Image)
- [ ] `app/static/uploads/` ist enthalten
- [ ] `.venv/`, `__pycache__/`, `*.png` sind enthalten
- [ ] `tests/` ist enthalten (prod-Image ohne Test-Code)
- [ ] `docker build --no-cache -t sport-challenge:test . 2>&1 | grep -i "sending"` – Build-Context deutlich kleiner als ohne ignore

---

#### I-06: docker-compose.yml erstellen
**Typ:** task | **Priorität:** P1 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Abhängig von:** I-01, I-03, I-04
**Dateien:** `docker-compose.yml` (NEW)

**Was:** `docker-compose.yml` nach Spec in I-06 Sektion erstellen.

**Acceptance Criteria:**
- [ ] `docker-compose.yml` existiert
- [ ] Port nur auf `127.0.0.1:5000` gebunden (nicht `0.0.0.0`)
- [ ] 3 Volumes: `./data/instance`, `./data/uploads`, `./data/logs`
- [ ] `env_file: .env.prod` referenziert
- [ ] `FLASK_APP: run.py` als environment
- [ ] Healthcheck konfiguriert
- [ ] `docker compose config` → keine Syntax-Fehler

---

#### I-07: .env.example aktualisieren
**Typ:** task | **Priorität:** P2 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Abhängig von:** I-01
**Dateien:** `.env.example`

**Was:** `.env.example` um neue Docker-Vars ergänzen (UPLOAD_FOLDER, GUNICORN_WORKERS, FLASK_APP) nach Spec in I-07 Sektion.

**Acceptance Criteria:**
- [ ] `UPLOAD_FOLDER` mit Kommentar (Docker-Hinweis) vorhanden
- [ ] `GUNICORN_WORKERS=1` mit Kommentar (Rate-Limiter-Warnung) vorhanden
- [ ] `FLASK_APP=run.py` vorhanden
- [ ] Existierende Vars unverändert

---

### Wave 3

#### I-08: GitHub Actions Workflow erstellen
**Typ:** task | **Priorität:** P1 | **Größe:** M
**Risiko:** reversible / system / autonomous-ok
**Abhängig von:** I-02, I-03
**Dateien:** `.github/workflows/docker-publish.yml` (NEW)

**Was:** GitHub Actions Workflow nach Spec in I-08 Sektion erstellen. `.github/workflows/`-Verzeichnis muss neu angelegt werden.

**Acceptance Criteria:**
- [ ] `.github/workflows/docker-publish.yml` existiert
- [ ] `test` Job: Python 3.13, `pip install -r requirements-dev.txt`, `pytest -v` mit `SECRET_KEY=ci-test-key-not-for-production`
- [ ] `publish` Job: nur auf `push` zu `main` (nicht auf PR)
- [ ] Tags: `latest` + Versionsstring aus `app.version.__version__`
- [ ] Docker Layer Cache via `cache-from: type=gha`
- [ ] Workflow YAML-Syntax valide: `python -c "import yaml; yaml.safe_load(open('.github/workflows/docker-publish.yml'))"` → kein Error

---

### Wave 4

#### I-09: Prod-Migration Guide erstellen
**Typ:** task | **Priorität:** P2 | **Größe:** S
**Risiko:** reversible / local / autonomous-ok
**Abhängig von:** I-06
**Dateien:** `docs/prod-migration-guide.md` (NEW)

**Was:** Schritt-für-Schritt-Anleitung für die bare-metal → Docker Migration nach Spec in I-09 Sektion erstellen.

**Acceptance Criteria:**
- [ ] `docs/prod-migration-guide.md` existiert
- [ ] Enthält Warnung zu SECRET_KEY (identisch halten, Fernet-Impact)
- [ ] Enthält Rollback-Strategie
- [ ] Enthält Daten-Backup-Schritt (SQLite + Uploads) vor Migration
- [ ] Enthält cloudflared Tunnel-Anpassungs-Schritt
- [ ] Enthält `docker compose up -d` + Smoke-Test-Befehl

---

## Boundaries

**Always:**
- `SECRET_KEY` niemals im Dockerfile oder docker-compose.yml hartkodieren (immer via `env_file`)
- `--workers 1` in Gunicorn (Flask-Limiter In-Memory, Entscheidung Käpt'n)
- Port nur auf `127.0.0.1` binden (cloudflared/Reverse-Proxy vorgelagert)
- `set -e` in entrypoint.sh (Migrationsfehler = kein Start)
- Python 3.13-slim als Base-Image (3.14-slim Verfügbarkeit ungewiss)
- `exec gunicorn` (nicht `gunicorn`) für PID-1-Signal-Weiterleitung

**Never:**
- `.env` oder `instance/` ins Docker-Image kopieren
- `FLASK_DEBUG=1` in docker-compose.yml setzen
- `--no-verify` oder `--force` bei git-Befehlen

**Ask First:** –

---

## Design Decisions

| Entscheidung | Gewählt | Abgelehnt | Begründung |
|---|---|---|---|
| Flask-Limiter Backend | In-Memory (1 Worker) | Redis-Sidecar | Weniger Komplexität; bei single-node + wenig Traffic ausreichend; jederzeit nachrüstbar |
| Docker Hub Visibility | Öffentlich | Privat | Kein Secret-Code im Image; einfacherer Pull auf Prod ohne Auth |
| Base-Image | python:3.13-slim | python:3.14-slim, alpine | 3.14-slim Verfügbarkeit unsicher; alpine inkompatibel mit cryptography Build |
| Dependency-Install | uv pip install --system | pip direkt | uv bereits lokal in Verwendung; deutlich schneller |
| Gunicorn Workers | ENV-Variable (Default: 1) | Hardcode | Konfigurierbar ohne Image-Rebuild; Rate-Limiter-safe |

---

## Rollback-Strategie

| Ebene | Rollback |
|---|---|
| Wave 1 | `git checkout config.py requirements.txt` – keine DB-Änderungen |
| Wave 2 | `rm Dockerfile entrypoint.sh .dockerignore docker-compose.yml` – alle neuen Dateien |
| Wave 3 | `rm -rf .github/` oder Workflow-Datei deaktivieren (Zeile `on: ...` auskommentieren) |
| Wave 4 | `rm docs/prod-migration-guide.md` – reine Dokumentation |
| Prod-Migration | `docker compose down` → alten Python-Prozess (`python run.py` / gunicorn direkt) neu starten, cloudflared zurückstellen |

**Git-Checkpoint vor Prod-Migration:** `git tag pre-docker-migration` setzen.

---

## Invalidation Risks

| Annahme | Risiko | Betroffen |
|---|---|---|
| `python:3.13-slim` verfügbar auf Docker Hub | Gering – aktuelles LTS | I-03 |
| `python:3.14-slim` NICHT verfügbar | Medium – sehr neue Version | I-03 (Fallback: 3.13 gewählt) |
| Prod-Server hat Docker + Compose-Plugin | Unverrifiziert – SSH-Check nötig | I-09 |
| SECRET_KEY auf Prod-Server bekannt | Muss vor Migration beschafft werden | I-09 (kritisch) |
| cloudflared Tunnel-Config lokalisierbar | Unverrifiziert | I-09 |
| `ghcr.io` vs Docker Hub irrelevant | Gewählt: Docker Hub (öffentlich) | I-08 |
