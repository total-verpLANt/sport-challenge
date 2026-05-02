# Plan: Garmin Connect Flask – Wochenansicht Aktivitäten

**Date:** 2026-04-23  
**Goal:** Modulare Python/Flask-App mit Garmin-Connect-Anbindung, wochenweise Aktivitätsanzeige  
**Research:** `.schrammns_workflow/research/2026-04-23-garmin-connect-python-flask-weekly-activities.md`

---

## Baseline Audit

| Metrik | Wert | Befehl |
|--------|------|--------|
| Bestehende Dateien | 0 | `ls sport-challenge/` |
| Python-Version | 3.14.4 | `python3 --version` |
| pip | 26.0.1 | `pip3 --version` |
| Git-Repo | Nein | `git status` |
| garminconnect installiert | Nein | Neu zu installieren |

---

## Files to Modify

| Datei | Änderung |
|-------|---------|
| `requirements.txt` | **NEU** – Abhängigkeiten |
| `.gitignore` | **NEU** – .env, __pycache__, Tokens ausschließen |
| `.env.example` | **NEU** – Vorlage für Credentials |
| `config.py` | **NEU** – Flask-Config-Klasse |
| `run.py` | **NEU** – Dev-Server-Einstiegspunkt |
| `app/__init__.py` | **NEU** – create_app() Factory |
| `app/garmin/__init__.py` | **NEU** – Modul-Init |
| `app/garmin/client.py` | **NEU** – GarminClient-Wrapper |
| `app/routes/__init__.py` | **NEU** – Modul-Init |
| `app/routes/activities.py` | **NEU** – Activities Blueprint + /week Route |
| `app/templates/base.html` | **NEU** – Bootstrap 5 Basis-Template |
| `app/templates/activities/week.html` | **NEU** – Wochenansicht-Template |

---

## Boundaries

**Always:**
- Credentials (GARMIN_EMAIL, GARMIN_PASSWORD) nur aus `.env` / Umgebungsvariablen – niemals hardcoden
- `garth`-Library nicht verwenden (deprecated, Issue #222)
- Token-Reuse vor Fresh-Login versuchen (Rate-Limit-Schutz)
- `.env` in `.gitignore` aufnehmen
- Flask `SECRET_KEY` aus Umgebungsvariable
- Fehler von `GarminConnectAuthenticationError` explizit abfangen und dem User anzeigen

**Never:**
- `garth` importieren
- Credentials in Source-Code oder Logs schreiben
- `garmin.login()` bei jedem Request aufrufen (nur beim Start / Token-Ablauf)

**Ask First:**
- Soll der Login über eine Web-UI erfolgen (Formular) oder via `.env` vorkonfiguriert? → Käpt'n hat bestätigt: `.env` für Phase 1

---

## Design Decisions

| Entscheidung | Gewählt | Abgelehnt | Begründung |
|-------------|---------|-----------|------------|
| Auth-Methode | `.env` + Token-Reuse | Web-Login-Formular | Einfacher für Phase 1, kein MFA |
| Web-Framework | Flask + Blueprints | FastAPI | Jinja2-Templates, geringere Komplexität |
| Garmin-Lib | garminconnect 0.3.2 | garth (deprecated), direkte API | Aktiv gepflegt, Python-nativ |
| UI | Bootstrap 5 CDN | Tailwind, custom CSS | Schnell, keine Build-Pipeline nötig |
| Token-Storage | `~/.garminconnect/` (Standard) | DB, Redis | Einfach, Lib-Standard |

---

## Issues

### Issue 1 – Projekt-Scaffolding [Wave 1]

**Titel:** Projektstruktur und Abhängigkeiten einrichten  
**Größe:** S | **Risiko:** reversible / local / autonomous-ok  
**Abhängigkeiten:** keine

**Beschreibung:** Alle Basis-Dateien für das Projekt anlegen.

**Dateien:**

`requirements.txt`:
```
garminconnect==0.3.2
flask>=3.0
python-dotenv>=1.0
```

`config.py`:
```python
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-prod")
    GARMIN_EMAIL = os.environ.get("GARMIN_EMAIL")
    GARMIN_PASSWORD = os.environ.get("GARMIN_PASSWORD")
    GARMIN_TOKEN_DIR = os.environ.get("GARMINTOKENS", os.path.expanduser("~/.garminconnect"))
```

`run.py`:
```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
```

`.env.example`:
```
GARMIN_EMAIL=deine@email.de
GARMIN_PASSWORD=deinPasswort
SECRET_KEY=aendere-mich-in-produktion
```

`.gitignore`: `.env`, `__pycache__/`, `*.pyc`, `*.pyo`, `*.egg-info/`, `.venv/`, `garmin_tokens.json`

**Akzeptanzkriterien:**
- [ ] `pip install -r requirements.txt` läuft ohne Fehler
- [ ] `config.py` importierbar: `python3 -c "from config import Config; print(Config.GARMIN_TOKEN_DIR)"`
- [ ] `.env` ist in `.gitignore` aufgeführt
- [ ] `.env.example` enthält alle drei Variablen

**Verification:**
```bash
pip install -r requirements.txt
python3 -c "from config import Config; print('Config OK:', Config.GARMIN_TOKEN_DIR)"
grep -q "^.env$" .gitignore && echo ".env korrekt ignoriert"
```

---

### Issue 2 – GarminClient-Modul [Wave 1]

**Titel:** GarminClient-Modul mit Token-Reuse implementieren  
**Größe:** S | **Risiko:** reversible / local / autonomous-ok  
**Abhängigkeiten:** keine (parallel zu Issue 1)

**Beschreibung:** Wrapper um `garminconnect.Garmin` mit Token-Reuse, Fehlerbehandlung und Wochenabfrage.

**Dateien:**

`app/__init__.py` (leerer Stub – wird in Issue 3 befüllt):
```python
# wird in Issue 3 implementiert
```

`app/garmin/__init__.py`: leer

`app/garmin/client.py`:
```python
from __future__ import annotations
import os
from datetime import date
from garminconnect import Garmin, GarminConnectAuthenticationError

class GarminClient:
    def __init__(self, email: str, password: str, token_dir: str) -> None:
        self._email = email
        self._password = password
        self._token_dir = token_dir
        self._api: Garmin | None = None

    def connect(self) -> None:
        """Token-Reuse versuchen; bei Fehler Fresh-Login."""
        self._api = Garmin(email=self._email, password=self._password)
        try:
            self._api.login(self._token_dir)
        except Exception:
            self._api.login()  # Fresh login, speichert Tokens

    def get_week_activities(
        self,
        start: date,
        end: date,
    ) -> list[dict]:
        if self._api is None:
            self.connect()
        return self._api.get_activities_by_date(
            start.isoformat(),
            end.isoformat(),
        )

    @staticmethod
    def format_duration(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def format_distance(meters: float) -> str:
        return f"{meters / 1000:.2f} km"
```

**Akzeptanzkriterien:**
- [ ] `from app.garmin.client import GarminClient` ohne Fehler
- [ ] `GarminClient.format_duration(3723)` → `"01:02:03"`
- [ ] `GarminClient.format_distance(5000)` → `"5.00 km"`
- [ ] `connect()` versucht Token-Reuse, fällt auf Fresh-Login zurück

**Verification:**
```bash
python3 -c "
from app.garmin.client import GarminClient
print(GarminClient.format_duration(3723))
print(GarminClient.format_distance(5000))
print('GarminClient OK')
"
```

---

### Issue 3 – Flask App Factory + Activities Blueprint [Wave 2]

**Titel:** Flask App Factory und Activities Blueprint implementieren  
**Größe:** M | **Risiko:** reversible / local / autonomous-ok  
**Abhängigkeiten:** Issue 1 (config.py), Issue 2 (GarminClient)

**Beschreibung:** `create_app()` Factory und Blueprint mit `/activities/week`-Route.

**Dateien:**

`app/__init__.py`:
```python
from flask import Flask
from config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.routes.activities import activities_bp
    app.register_blueprint(activities_bp, url_prefix="/activities")

    return app
```

`app/routes/__init__.py`: leer

`app/routes/activities.py`:
```python
from __future__ import annotations
from datetime import date, timedelta
from flask import Blueprint, render_template, request, current_app
from app.garmin.client import GarminClient

activities_bp = Blueprint("activities", __name__, template_folder="../templates")

def _get_week_bounds(ref: date) -> tuple[date, date]:
    """Montag und Sonntag der Woche, in der ref liegt."""
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday

def _get_garmin_client() -> GarminClient:
    return GarminClient(
        email=current_app.config["GARMIN_EMAIL"],
        password=current_app.config["GARMIN_PASSWORD"],
        token_dir=current_app.config["GARMIN_TOKEN_DIR"],
    )

@activities_bp.route("/week")
def week_view():
    offset = request.args.get("offset", 0, type=int)  # Wochen-Offset (0=aktuell, -1=letzte Woche)
    ref = date.today() + timedelta(weeks=offset)
    monday, sunday = _get_week_bounds(ref)

    error = None
    activities = []
    try:
        client = _get_garmin_client()
        raw = client.get_week_activities(monday, sunday)
        activities = [
            {
                "date": a.get("startTimeLocal", "")[:10],
                "name": a.get("activityName", "–"),
                "type": a.get("activityType", {}).get("typeKey", "–"),
                "duration": GarminClient.format_duration(a.get("duration", 0)),
                "distance": GarminClient.format_distance(a.get("distance", 0)) if a.get("distance") else "–",
                "avg_hr": a.get("averageHR", "–"),
                "calories": a.get("calories", "–"),
            }
            for a in raw
        ]
    except Exception as exc:
        error = str(exc)

    return render_template(
        "activities/week.html",
        activities=activities,
        monday=monday,
        sunday=sunday,
        offset=offset,
        error=error,
    )
```

**Akzeptanzkriterien:**
- [ ] `python3 -c "from app import create_app; app = create_app(); print('App OK')"` ohne Fehler
- [ ] Route `/activities/week` ist registriert: `flask routes | grep week`
- [ ] `_get_week_bounds(date(2026,4,23))` → `(date(2026,4,20), date(2026,4,26))`

**Verification:**
```bash
python3 -c "
from app import create_app
app = create_app()
print('App OK')
with app.test_client() as c:
    # Ohne echte Garmin-Creds → error-State expected
    r = c.get('/activities/week')
    print('Status:', r.status_code)
"
```

---

### Issue 4 – HTML-Templates [Wave 2]

**Titel:** Bootstrap 5 Basis- und Wochenansicht-Template anlegen  
**Größe:** S | **Risiko:** reversible / local / autonomous-ok  
**Abhängigkeiten:** Issue 3 (Template-Variablen: activities, monday, sunday, offset, error)

**Beschreibung:** Responsives Template mit Wochennavigation und Aktivitätstabelle.

**Template-Variablen (aus Issue 3):**
- `activities`: `list[dict]` mit keys: date, name, type, duration, distance, avg_hr, calories
- `monday`, `sunday`: `date`-Objekte für Wochentitel
- `offset`: `int` für Wochennavigation
- `error`: `str | None` für Fehleranzeige

**Dateien:**

`app/templates/base.html`:
- Bootstrap 5 CDN (CSS + JS Bundle)
- `<title>Sport Challenge</title>`
- Navbar mit App-Name
- `{% block content %}{% endblock %}`

`app/templates/activities/week.html`:
- extends `base.html`
- Wochentitel: „Woche vom {monday.strftime('%d.%m.%Y')} – {sunday.strftime('%d.%m.%Y')}"
- Navigation: „← Vorherige Woche" (`?offset=offset-1`) | „Aktuelle Woche" | „Nächste Woche →"
- Fehlermeldung: Bootstrap `alert-danger` falls `error` gesetzt
- Tabelle: Datum | Aktivität | Typ | Dauer | Distanz | ⌀ Puls | Kalorien
- Leerer Zustand: „Keine Aktivitäten in dieser Woche" wenn `activities` leer

**Akzeptanzkriterien:**
- [ ] Template rendert ohne Jinja2-Fehler mit leerer `activities`-Liste
- [ ] Wochennavigation-Links erzeugen korrekte `?offset=`-Parameter
- [ ] Fehlermeldung erscheint wenn `error` gesetzt ist
- [ ] Tabelle zeigt alle 7 Spalten

**Verification:**
```bash
python3 -c "
from app import create_app
from datetime import date
app = create_app()
with app.test_client() as c:
    r = c.get('/activities/week')
    html = r.data.decode()
    assert 'Woche vom' in html, 'Wochentitel fehlt'
    assert 'Vorherige Woche' in html, 'Navigation fehlt'
    print('Templates OK, Status:', r.status_code)
"
```

---

## Wave-Struktur

```
Wave 1 (parallel):
  Issue 1 – Scaffolding
  Issue 2 – GarminClient

Wave 2 (parallel, nach Wave 1):
  Issue 3 – App Factory + Blueprint   [depends: 1, 2]
  Issue 4 – Templates                 [depends: 3]
```

> Issue 4 hängt von Issue 3 ab (Template-Variablen-Interface). Da Issue 3 klein ist, bleibt Wave 2 straff.

---

## Invalidation Risks

| Annahme | Risiko | Betroffene Issues |
|---------|--------|-------------------|
| garminconnect 0.3.2 auth funktioniert | Issue #332 – Fresh-Login könnte fehlschlagen | Issue 2, 3 |
| Token-Reuse hält ~1 Jahr | Ggf. kürzer nach Garmin-Änderung | Issue 2 |
| Activity-Felder stabil | Schema kann sich ändern | Issue 3, 4 |

**Mitigierung:** Bei Auth-Fehler zeigt die App eine klare Fehlermeldung (error-State in Template).

---

## Rollback-Strategie

- Wave 1: Dateien löschen → keine Auswirkung auf externes System
- Wave 2: Route/Template löschen → kein persistenter State
- Kein DB-Schema, keine Migration → vollständig reversibel
- Empfehlung: `git init` nach Issue 1, dann Commits pro Issue

---

## Nächste Schritte nach Phase 1

- Phase 2: Auth-Formular im Browser (falls benötigt)
- Phase 3: Charts (z.B. Chart.js für Wochen-Trends)
- Phase 4: Weitere Aktivitätstypen-Filter, Statistiken
