# WebSearch-Aufträge für externen Kontext

**Erstellt:** 2026-04-23
**Hintergrund:** Bei der Research-Phase für den sport-challenge Rebuild waren WebSearch-Aufrufe auf Opus blockiert (Vertex AI Policy). Ein Sonnet-Sub-Agent hat Teilantworten geliefert, aber eine unabhängige, quellengestützte Nachrecherche ist sinnvoll.

**Anweisung ans LLM:** Führe die folgenden Suchanfragen durch und erstelle pro Thema einen kurzen Abschnitt (5-10 Sätze) mit:
1. **Kernfakten** – Was ist der aktuelle Stand (2025/2026)?
2. **Quellen-URLs** – Mindestens 2 zitierfähige Links pro Thema
3. **Praktische Empfehlung** – Konkreter Rat für ein lokales Flask-Projekt (Python 3.14, SQLite, Bootstrap 5)
4. **Risiken/Einschränkungen** – Was sollte man beachten?

Formatiere die Ergebnisse als Markdown-Report.

---

## Thema 1: Werkzeug Password Hashing (aktueller Stand)

**Suchbegriffe:**
- `werkzeug security generate_password_hash default algorithm 2025 2026`
- `werkzeug scrypt vs argon2 password hashing Python`
- `OWASP password storage cheat sheet scrypt parameters 2025`

**Was das LLM herausfinden soll:**
- Welcher Algorithmus ist der Default in werkzeug 3.x? (Vermutung: scrypt seit 3.0)
- Welche Parameter nutzt werkzeug (n, r, p, salt_length)?
- Erfüllt der Default die aktuellen OWASP-Empfehlungen?
- Lohnt sich argon2-cffi als Alternative für ein lokales Projekt?
- Gibt es bekannte Probleme mit scrypt auf macOS/Python 3.14?

---

## Thema 2: Fernet Key Derivation aus SECRET_KEY

**Suchbegriffe:**
- `python cryptography Fernet derive key HKDF PBKDF2 best practice`
- `HKDF vs PBKDF2 when to use which key derivation`
- `Fernet encryption credentials at rest Flask application`

**Was das LLM herausfinden soll:**
- HKDF vs. PBKDF2 – wann welches? (HKDF fuer hochentropische Secrets, PBKDF2 fuer Passwoerter)
- Ist ein fester Salt bei HKDF akzeptabel? (RFC 5869 Section 3.1)
- Konkretes Code-Beispiel fuer Fernet-Key-Ableitung mit HKDF aus Flask SECRET_KEY
- Muss der SECRET_KEY eine Mindestlaenge haben? (Empfehlung: 32+ Bytes)

---

## Thema 3: Strava API OAuth2 Flow

**Suchbegriffe:**
- `Strava API v3 OAuth2 authentication developer documentation 2025`
- `Strava API activity read scope token refresh`
- `stravalib python library OAuth2 2025`

**Was das LLM herausfinden soll:**
- Wie funktioniert der OAuth2 Authorization Code Flow bei Strava?
- Welche Scopes gibt es fuer Aktivitaeten? (`activity:read`, `activity:read_all`)
- Wie lange sind Access/Refresh Tokens gueltig? (Access: 6h, Refresh: langlebig)
- Gibt es eine Python-Bibliothek (stravalib)? Aktueller Maintenance-Status?
- Redirect-URI fuer lokale Apps: `http://localhost:PORT/callback` erlaubt?
- Rate Limits?

---

## Thema 4: Komoot API Zugang

**Suchbegriffe:**
- `Komoot API developer access third party 2025 2026`
- `Komoot unofficial API REST endpoints tours activities`
- `komoot-api python github`

**Was das LLM herausfinden soll:**
- Hat Komoot eine offizielle oeffentliche API? (Vermutung: Nein)
- Gibt es eine inoffizielle API? Basis-URL, Auth-Methode, typische Endpunkte?
- GitHub-Projekte die die inoffizielle API nutzen?
- Risiken: ToS-Verstoss? Stabilitaet? Rate Limits?
- Alternative: GPX-Export aus Komoot – wie automatisierbar?

---

## Thema 5: Samsung Health API / SDK

**Suchbegriffe:**
- `Samsung Health SDK API third party developer access 2025 2026`
- `Samsung Health data export web API REST`
- `Samsung Health Android SDK deprecated 2025`

**Was das LLM herausfinden soll:**
- Gibt es eine Web-API/REST-API fuer Samsung Health? (Vermutung: Nein)
- Status des Samsung Health Android SDK (deprecated seit 2025?)
- Samsung Health Data SDK – was kann es, welche Plattformen?
- Ist eine Integration in eine Flask-Web-App realistisch?
- Alternativen: Manueller CSV/JSON-Export? Health Connect (Google) als Bruecke?

---

## Thema 6: garminconnect Python Library (aktuelle Issues)

**Suchbegriffe:**
- `garminconnect python library github issues 2025 2026`
- `cyberjunky python-garminconnect cloudflare authentication problems`
- `garminconnect MFA multi factor authentication handling`
- `garminconnect token persistence refresh`

**Was das LLM herausfinden soll:**
- Aktuelle Versionsnummer und letztes Release-Datum?
- Bekannte Issues mit Cloudflare-Blocking beim Login?
- MFA-Handling: Wird es unterstuetzt? Callback-Funktion?
- Token-Persistenz: Wie werden Tokens gespeichert? Automatischer Refresh?
- 429 Rate Limiting: Wie oft tritt es auf? Workarounds?
- Gibt es Breaking Changes seit 0.3.2?

---

## Thema 7: SQLite Verschluesselung

**Suchbegriffe:**
- `SQLite encryption at rest SQLCipher vs application level 2025`
- `pysqlcipher3 Python compatibility issues`
- `SQLCipher Python Flask SQLAlchemy integration`

**Was das LLM herausfinden soll:**
- SQLCipher: Aktueller Maintenance-Status? Python-Bindings funktional?
- pysqlcipher3: Kompatibilitaet mit Python 3.14? Build-Probleme auf macOS?
- Vergleich: SQLCipher (ganze DB) vs. Fernet (einzelne Felder) – Vor-/Nachteile
- Fuer ein lokales Hobby-Projekt: Was ist angemessen?

---

## Thema 8: Flask RBAC ohne Heavy Frameworks

**Suchbegriffe:**
- `Flask role based access control simple decorator admin_required 2025`
- `Flask RBAC without flask-principal flask-security`
- `Flask custom decorator roles_required best practice`

**Was das LLM herausfinden soll:**
- Kanonisches Decorator-Pattern fuer `admin_required` / `roles_required`?
- Stacking mit `@login_required` – richtige Reihenfolge?
- Rollen als String-Feld vs. separate Tabelle – wann lohnt sich was?
- Reicht ein einfaches Decorator-Pattern fuer Admin/User oder braucht man Flask-Principal?
- Sicherheitsfallen: TOCTOU, fehlende POST-Route-Absicherung?
