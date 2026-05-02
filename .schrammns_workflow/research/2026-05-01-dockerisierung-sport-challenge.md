# Research: Dockerisierung sport-challenge + Docker Hub Deployment

**Date:** 2026-05-01
**Scope:** Vollständige Containerisierung der Flask-App, CI/CD via GitHub Actions → Docker Hub, Migration der Produktion von bare-metal (cloudflared + Python direkt) auf Docker-Deploy.

---

## Executive Summary

- **Kein Docker-Setup vorhanden** – Dockerfile, docker-compose.yml, .dockerignore, CI/CD müssen komplett neu erstellt werden.
- **Drei kritische Blocker** müssen vor dem ersten Build behoben werden: (1) `UPLOAD_FOLDER` ist hardcodiert und nicht per ENV überschreibbar, (2) `LOG_DIR` ist hardcodiert, (3) `Flask-Limiter` nutzt In-Memory-Backend – bei mehreren Gunicorn-Workern versagen Rate-Limits.
- **`SECRET_KEY` ist Fernet-Schlüssel-Basis** – ein Wechsel macht alle gespeicherten Connector-Credentials unbrauchbar. Muss als persistentes Docker Secret verwaltet werden, niemals ins Image gebaut.
- **Entrypoint-Script** (`entrypoint.sh`) muss `flask db upgrade` vor `gunicorn` ausführen (16 Migrationen vorhanden, SQLite-Volume muss zur Migration-Zeit gemountet sein).
- **`ffmpeg`/`ffprobe`** muss als System-Paket ins Image (wird von `uploads.py` via `subprocess.run` aufgerufen).

---

## Key Files

| File | Purpose |
|------|---------|
| `config.py` | Flask Config – SECRET_KEY Guard, UPLOAD_FOLDER hardcodiert (Z. 15), DATABASE_URL via ENV |
| `run.py` | App-Entry-Point – lädt .env via python-dotenv, `app = create_app()` |
| `app/__init__.py` | App-Factory – ProxyFix, RotatingFileHandler (LOG_DIR hardcodiert Z. 29), Talisman force_https=False |
| `app/extensions.py` | Flask-Limiter ohne `storage_uri` (Z. 20) – In-Memory, multi-worker-unsafe |
| `app/utils/uploads.py` | Upload-Logik – ffprobe via subprocess (Z. 60), liest `current_app.config["UPLOAD_FOLDER"]` |
| `app/utils/crypto.py` | HKDF-Key-Derivation aus SECRET_KEY → Fernet-Verschlüsselung |
| `requirements.txt` | Dependencies: gunicorn>=22.0, cryptography==46.0.7, pytest+pytest-flask (in prod-deps!) |
| `migrations/` | 16 Alembic-Migrationen, render_as_batch=True (SQLite-kompatibel) |
| `instance/sport-challenge.db` | SQLite-Produktionsdatenbank – muss Volume werden |
| `app/static/uploads/` | Foto/Video-Uploads – muss Volume werden |
| `logs/access.log` | RotatingFileHandler 10 MB × 5 – muss Volume werden |

---

## Technology Stack

| Library/Framework | Version | Role |
|---|---|---|
| Flask | >=3.0 | Web Framework |
| gunicorn | >=22.0 | WSGI Production Server |
| Flask-Migrate / Alembic | 4.1.0 | DB Migrationen |
| Flask-SQLAlchemy | 3.1.1 | ORM |
| Flask-Limiter | 4.1.1 | Rate Limiting (aktuell In-Memory!) |
| Flask-Talisman | >=1.0 | Security Headers, CSP |
| cryptography | 46.0.7 | Fernet-Verschlüsselung Connector-Credentials |
| python-dotenv | >=1.0 | .env Laden in run.py |
| Python | 3.14 (lokal via uv) | Laufzeitumgebung |
| ffmpeg/ffprobe | System-Paket | Video-Metadaten in uploads.py |

---

## Findings

### F-01: Projektstruktur – kein Docker vorhanden

Weder `Dockerfile`, `docker-compose.yml`, `.dockerignore`, noch CI-Konfiguration (kein `.github/`-Verzeichnis) existieren. Das ist eine Greenfield-Containerisierung. Quelle: Agent C Exploration.

### F-02: Persistenz-Pfade (Volume-Kandidaten)

| Host-Pfad (prod) | Container-Pfad | Quelle |
|---|---|---|
| `./data/instance/` | `/app/instance/` | `config.py:9` (SQLite default: `instance/sport-challenge.db`) |
| `./data/uploads/` | `/app/app/static/uploads/` | `config.py:15` (hardcodiert!) |
| `./data/logs/` | `/app/logs/` | `app/__init__.py:29` (hardcodiert!) |

**Kritisch:** `UPLOAD_FOLDER` (`config.py:15`) ist ein absoluter Pfad, der aus `os.path.dirname(os.path.abspath(__file__))` berechnet wird und **nicht per ENV überschreibbar** ist. Für Docker muss entweder (a) ein Bind-Mount exakt auf `/app/app/static/uploads/` zeigen **oder** (b) `config.py` gepatcht werden: `UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(...))`.

Empfehlung: **(b) Code-Patch** – ENV-Überschreibung ist sauberer und macht den Container portabler. Eine Zeile Änderung.

**Analog:** Log-Verzeichnis (`app/__init__.py:29`) ist hardcodiert auf `Path(app.root_path).parent / "logs"`. Für Container ist ein Bind-Mount auf `/app/logs/` ausreichend (Verzeichnis wird mit `mkdir(parents=True, exist_ok=True)` erstellt).

### F-03: Flask-Limiter – In-Memory-Backend ist multi-worker-unsafe

`app/extensions.py:20`: `Limiter(key_func=get_remote_address)` – kein `storage_uri`. Im In-Memory-Modus verwaltet jeder Gunicorn-Worker einen eigenen Counter. Bei 3 Workern (`gunicorn -w 3`) kann ein Angreifer 3× die erlaubten Requests machen. Flask-Limiter gibt beim Start eine Warning aus.

**Empfehlung:** Entweder (a) **Gunicorn auf 1 Worker beschränken** (einfachste Lösung für single-node-prod mit wenig Traffic) oder (b) Redis-Sidecar + `RATELIMIT_STORAGE_URI=redis://redis:6379` in Extensions/Config einbauen. Option (a) ist für den Anfang ausreichend; Option (b) wird in der Docker-Memory als geplante Migration gespeichert.

### F-04: SECRET_KEY – Fernet-Basis, niemals wechseln/rotieren ohne Plan

`app/utils/crypto.py` leitet via HKDF einen Fernet-Key aus `SECRET_KEY` ab. Alle Garmin/Strava-Tokens in `connector_credentials.credentials` sind damit verschlüsselt. **Ein SECRET_KEY-Wechsel = alle Connector-Credentials unbrauchbar, User müssen sich neu verbinden.**

Für Docker: `SECRET_KEY` als Datei in `./secrets/secret_key.txt` ablegen, per `env_file: .env.prod` oder Docker Secrets einlesen. **Niemals ins Image baken (ENV im Dockerfile).**

### F-05: System-Abhängigkeit ffmpeg

`app/utils/uploads.py` ruft `subprocess.run(["ffprobe", ...])` auf (Z. 60) um Video-`creation_time` zu lesen. Ohne ffprobe im Image wird der Aufruf mit try/except abgefangen (gibt `None` zurück), das Feature ist aber stumm defekt.

**Erforderlich im Dockerfile:** `RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*`

### F-06: Python-Version und Dependency-Management

Lokal wird Python 3.14 via `uv` verwendet (CLAUDE.md). `requirements.txt` listet keine Python-Version, kein `.python-version`, kein `pyproject.toml`. Für Docker:
- `python:3.12-slim` oder `python:3.13-slim` als sicheres Base-Image (3.14 ist sehr neu, Docker Hub availability prüfen)
- `uv` kann als Build-Tool im Dockerfile genutzt werden: `pip install uv && uv pip install -r requirements.txt` (schneller als pip, schon lokal in Verwendung)
- `pytest` und `pytest-flask` sind in `requirements.txt` gemischt – für prod-Image werden sie mit installiert. Overhead ~20 MB; für v1 akzeptabel, später als `requirements-dev.txt` auslagern.

### F-07: Gunicorn-Konfiguration

Kein `gunicorn.conf.py` vorhanden. Empfohlener CMD:
```bash
gunicorn --bind 0.0.0.0:5000 --workers ${GUNICORN_WORKERS:-1} --timeout 120 run:app
```
Workers als ENV-Variable (`GUNICORN_WORKERS`) konfigurierbar machen. Default 1 (wegen In-Memory-Limiter, F-03).

### F-08: Migrationen im Container-Lifecycle

16 Alembic-Migrationen vorhanden. `render_as_batch=True` in `migrations/env.py` – SQLite ALTER TABLE über Copy-Ansatz (korrekt).

Empfohlenes Entrypoint-Pattern:
```bash
#!/bin/sh
set -e
flask db upgrade
exec gunicorn --bind 0.0.0.0:5000 --workers ${GUNICORN_WORKERS:-1} run:app
```
`exec` übergibt PID 1 an gunicorn → korrekte Signal-Weiterleitung für Docker-Shutdown.

**Wichtig:** Flask-Migrate benötigt `FLASK_APP=run.py` als ENV für den `flask`-CLI-Aufruf.

### F-09: ProxyFix + Talisman – cloudflared-kompatibel

`app/__init__.py:20`: `ProxyFix(x_for=1, x_proto=1, x_host=1)` ist bereits gesetzt – funktioniert hinter cloudflared-Tunnel und Standard-Reverse-Proxies. `force_https=False` in Talisman ist korrekt, da TLS am cloudflared-Endpunkt terminiert wird.

### F-10: GitHub Actions CI/CD – Greenfield

Kein `.github/`-Verzeichnis vorhanden. Empfohlener Workflow:
1. `push` auf `main` → Build + Test + Push zu Docker Hub
2. `pull_request` → Build + Test only (kein Push)
3. Docker Hub Credentials als GitHub Secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`)
4. Image-Tag: `<username>/sport-challenge:latest` + `:<version>` (aus `app/version.py`)
5. `docker/build-push-action` + `docker/metadata-action` für Tags

### F-11: .dockerignore – kritisch (viele große Dateien im Repo)

Der Repo-Root enthält viele PNG-Screenshots (via `.gitignore` ignoriert aber physisch vorhanden), `.playwright-mcp/`-Verzeichnis, `.beads/`, `.serena/`, `.schrammns_workflow/`, `.venv/`, `instance/`, `logs/`. Ohne `.dockerignore` landen diese im Build-Context → massiv verlangsamter Build.

---

## Geplante Datei-Struktur (neu zu erstellen)

```
sport-challenge/
├── Dockerfile
├── docker-compose.yml          # Prod-Compose (lokaler Test + Prod-Template)
├── .dockerignore
├── entrypoint.sh               # flask db upgrade + exec gunicorn
├── .env.example                # aktualisieren um neue Docker-Vars
├── .github/
│   └── workflows/
│       └── docker-publish.yml  # CI/CD: test + build + push Docker Hub
└── data/                       # .gitignore – nur local/prod
    ├── instance/               # SQLite-DB Volume
    ├── uploads/                # Media-Uploads Volume
    └── logs/                   # Access-Log Volume
```

---

## Depth Ratings

| Area | Rating | Notes |
|------|--------|-------|
| Projektstruktur & Dependencies | 4 | Vollständig gelesen, alle Dateien bekannt |
| Persistenz-Pfade | 4 | UPLOAD_FOLDER Hardcoding und Log-Dir verifiziert |
| SECRET_KEY / Fernet | 4 | Crypto-Chain vollständig verstanden |
| Flask-Limiter In-Memory | 4 | Explizit in extensions.py verifiziert |
| ffmpeg-Dependency | 3 | subprocess-Aufruf gefunden, genaues Verhalten bei Fehlen nur aus Code |
| Gunicorn Config | 3 | requirements.txt verifiziert, kein gunicorn.conf.py gefunden |
| Migration Lifecycle | 3 | 16 Migrationen + render_as_batch bestätigt |
| GitHub Actions / Docker Hub | 2 | Web-Research, kein bestehendes Setup |
| Migrations-entrypoint Patterns | 2 | Web-Research, bewährte Patterns gefunden |
| cloudflared → Docker Transition | 2 | ProxyFix/Talisman-Config bekannt, Transition-Prozess nicht tief untersucht |

---

## Knowledge Gaps

| Gap | Priority | How to Fill |
|-----|----------|-------------|
| Python 3.14 auf Docker Hub: `python:3.14-slim` verfügbar? | must-fill | `docker pull python:3.14-slim` testen, ggf. 3.13 nehmen |
| cloudflared-Konfiguration auf Prod-Server | must-fill | SSH auf Server, cloudflared config lesen – muss auf neuen Docker-Port zeigen |
| Redis für Flask-Limiter: jetzt oder später? | nice-to-have | Entscheidung Käpt'n (1 Worker = kein Problem) |
| Multi-Platform Build (linux/amd64 + linux/arm64)? | nice-to-have | Relevant wenn Server ARM (z.B. Raspberry Pi, AWS Graviton) |
| Docker Hub Username / Org | must-fill | Käpt'n muss DOCKERHUB_USERNAME festlegen |
| Strava OAuth Callback-URL ändert sich nicht | nice-to-have | Nur wenn Port sich ändert – prüfen |

---

## Assumptions

| Assumption | Verified? | Evidence |
|------------|-----------|----------|
| Prod läuft auf einem einzelnen Host | Ja | Memory: `project_production_environment.md` |
| cloudflared terminiert TLS | Ja | Memory + `app/__init__.py:60` (force_https=False) |
| gunicorn ist der WSGI-Server | Ja | `requirements.txt:15` |
| SQLite bleibt (kein Postgres-Upgrade) | Angenommen | Kein DATABASE_URL in .env, Käpt'n hat nichts anderes erwähnt |
| Image wird auf Docker Hub öffentlich | Angenommen | Käpt'n sagte "über Docker Hub zur Verfügung stellen" |
| Prod-Server hat Docker installiert | Nicht verifiziert | SSH-Prüfung nötig |

---

## Recommendations

### Priorisierte Umsetzungs-Wellen

**Wave 1 – Blocker-Fixes (Code-Änderungen vor Docker-Build)**
1. `config.py:15` – `UPLOAD_FOLDER` per ENV überschreibbar machen (1 Zeile)
2. `requirements.txt` splitten in `requirements.txt` (prod) + `requirements-dev.txt` (pytest) — optional, aber sauber

**Wave 2 – Docker-Artefakte**
1. `Dockerfile` – `python:3.13-slim`, ffmpeg, non-root user, uv für pip install
2. `entrypoint.sh` – `flask db upgrade && exec gunicorn`
3. `.dockerignore` – alle unnötigen Dateien ausschließen
4. `docker-compose.yml` – 3 Volumes (instance, uploads, logs), env_file, healthcheck

**Wave 3 – CI/CD**
1. `.github/workflows/docker-publish.yml` – pytest on PR, build+push on main
2. GitHub Secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`

**Wave 4 – Prod-Migration (Zero-Downtime)**
1. Docker auf Prod-Server installieren (falls nicht vorhanden)
2. `data/instance/` mit bestehendem SQLite-Backup befüllen
3. `data/uploads/` mit bestehenden Uploads befüllen
4. `.env.prod` mit `SECRET_KEY` befüllen (identisch zum laufenden System!)
5. `docker compose up -d` → testen
6. cloudflared Tunnel-Config anpassen (Port auf Docker-Container)
7. Alten Python-Prozess stoppen

**Wave 5 – Optional (nach stabilem Betrieb)**
- Redis-Sidecar + `RATELIMIT_STORAGE_URI` für Flask-Limiter
- Multi-stage Dockerfile (Builder + Runtime) für kleineres Image
- `requirements-dev.txt` Trennung

---

## Konkrete Datei-Skizzen

### Dockerfile (empfohlen)
```dockerfile
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
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
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
```

### entrypoint.sh
```bash
#!/bin/sh
set -e
flask db upgrade
exec gunicorn --bind 0.0.0.0:5000 --workers ${GUNICORN_WORKERS:-1} --timeout 120 run:app
```

### docker-compose.yml (Prod-Template)
```yaml
services:
  web:
    image: <dockerhub-user>/sport-challenge:latest
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
```

### .env.prod (Vorlage, niemals ins Repo)
```
SECRET_KEY=<langer-zufaelliger-wert>
DATABASE_URL=sqlite:///sport-challenge.db
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
```

### GitHub Actions Workflow (Skizze)
```yaml
name: Docker Publish
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install -r requirements.txt
      - run: pytest
        env:
          SECRET_KEY: ci-test-key

  publish:
    needs: test
    if: github.event_name != 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ${{ secrets.DOCKERHUB_USERNAME }}/sport-challenge:latest
```

---

## Quellen

- [Dockerizing Flask with Postgres, Gunicorn, and Traefik | TestDriven.io](https://testdriven.io/blog/flask-docker-traefik/)
- [Docker Build GitHub Actions | Docker Docs](https://docs.docker.com/build/ci/github-actions/)
- [Publishing Docker images – GitHub Docs](https://docs.github.com/en/actions/publishing-packages/publishing-docker-images)
- [Decoupling database migrations from server startup](https://pythonspeed.com/articles/schema-migrations-server-startup/)
- [Flask SQLAlchemy Microservices: Alembic Migrations Docker Compose Orchestration 2025](https://www.johal.in/flask-sqlalchemy-microservices-alembic-migrations-docker-compose-orchestration-2025/)
- [Containerization Best Practices: Python Dockerfile Multi-Stage Builds](https://johal.in/containerization-best-practices-python-dockerfile-multi-stage-builds-for-slim-images/)
