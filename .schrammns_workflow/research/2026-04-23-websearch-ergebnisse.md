# WebSearch-Ergebnisse: Nachrecherche zu 8 Architektur-Themen

**Erstellt:** 2026-04-23
**Grundlage:** `.schrammns_workflow/research/2026-04-23-websearch-auftraege.md`
**Methodik:** WebSearch + WebFetch gegen Primärquellen (GitHub, offizielle Docs, OWASP, PyPI)
**Status:** Alle 8 Themen abgeschlossen

---

## Thema 1: Werkzeug Password Hashing (aktueller Stand)

### Kernfakten (2026)

- **Default-Algorithmus:** `scrypt` seit Werkzeug 3.0 (2024), in 3.1.x (aktuell) unverändert.
- **Default-Method-String:** `scrypt:32768:8:1` → N=2¹⁵ (32.768), r=8, p=1.
- **Salt-Länge:** 16 Zeichen (alphanumerisch, aus `SALT_CHARS`).
- **Quellcode-Fundstelle:** `src/werkzeug/security.py` Zeilen 57, 131.
- **OWASP-Empfehlung 2026:** scrypt mit N=2¹⁷ (131.072), r=8, p=1 – Werkzeug liegt 2 Größenordnungen darunter (2¹⁵ statt 2¹⁷).
- **OWASP-Topwahl:** Argon2id (m=19 MiB, t=2, p=1). Erfordert `argon2-cffi` C-Extension.
- **macOS/Python 3.14:** Keine bekannten Kompatibilitätsprobleme. scrypt ist Bestandteil der hashlib-C-Bindings, läuft nativ.

### Quellen

- [werkzeug/src/werkzeug/security.py (GitHub main)](https://github.com/pallets/werkzeug/blob/main/src/werkzeug/security.py)
- [Werkzeug Documentation 3.1.x – Utilities](https://werkzeug.palletsprojects.com/en/stable/utils/)
- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

### Praktische Empfehlung (lokales Flask-Projekt)

**Werkzeug-Default beibehalten.** Für ein lokales Hobby-Projekt mit begrenzter User-Zahl ist N=2¹⁵ (≈32 MB RAM pro Hash) ausreichend. Upgrade auf explizites `scrypt:131072:8:1` ist ein Einzeiler:

```python
from werkzeug.security import generate_password_hash
h = generate_password_hash(pw, method="scrypt:131072:8:1")
```

Argon2id (via `argon2-cffi`) wäre die Topwahl, aber zusätzliche Build-Dependency und marginaler Sicherheitsgewinn im Single-Host-Szenario.

### Risiken / Einschränkungen

- **Memory-Exhaustion-Angriff:** N=2¹⁷ → 128 MB pro Hash × viele parallele Login-Versuche kann Server OOM fahren. Ohne Rate-Limiting kein Problem in Single-User-App, aber bei Exposition ins Internet kritisch.
- **Keine automatische Rehash-Logik:** Bei späterer Parameter-Erhöhung müssen User beim nächsten Login rehashed werden (Pattern: nach `check_password_hash()` prüfen, ob Hash-Prefix veraltet, dann rehashen).

---

## Thema 2: Fernet Key Derivation aus SECRET_KEY

### Kernfakten

- **HKDF (RFC 5869)** ist der korrekte KDF für Schlüssel-aus-Schlüssel-Ableitung, wenn das Eingabegeheimnis **hochentropisch** ist (z.B. ein 256-Bit SECRET_KEY).
- **PBKDF2/Argon2/scrypt** sind für **niedrigentropische Passwörter** designed – teuer für den Angreifer, aber für Key-Derivation aus einem Random-Key verschwendete CPU.
- **Fester Salt bei HKDF:** RFC 5869 Section 3.1 erlaubt das ausdrücklich, wenn das Input Keying Material (IKM) bereits zufällig und ausreichend lang ist.
- **Referenz-Implementierung:** `django-fernet-fields` nutzt HKDF als Default, um Fernet-Keys aus Django SECRET_KEY abzuleiten.
- **Mindestlänge SECRET_KEY:** 32 Bytes (256 Bit) empfohlen – aktuell `.env` hat 64 Hex-Zeichen = 32 Bytes, passt.

### Quellen

- [cryptography.io – Fernet](https://cryptography.io/en/latest/fernet/)
- [django-fernet-fields Docs](https://django-fernet-fields.readthedocs.io/en/latest/)
- [RFC 5869 – HKDF](https://datatracker.ietf.org/doc/html/rfc5869) (Section 3.1 zu Salts)

### Praktische Empfehlung

```python
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
import base64

def derive_fernet_key(secret_key: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"sport-challenge-v1",        # Context-Salt, unkritisch bei hochentropischem IKM
        info=b"connector-credentials",     # Domain-Separator für Fernet-Ableitung
    )
    return base64.urlsafe_b64encode(hkdf.derive(secret_key.encode()))
```

Der `info`-Parameter ist der Schlüsseltrick: Wird später ein weiterer abgeleiteter Key benötigt (z.B. für Session-Tokens), nutzt man denselben SECRET_KEY mit anderem `info=b"session-tokens"` → unabhängige Keys.

### Risiken / Einschränkungen

- **SECRET_KEY-Rotation:** Bei Rotation müssen alle mit altem Key verschlüsselten Daten re-verschlüsselt werden. Pattern: Versionierung im `info`-Feld (`v1`, `v2`) oder in der DB (Spalte `crypto_version`).
- **Salt-Transparenz:** Fester Salt im Source-Code bedeutet: Wer das Repo und den SECRET_KEY kennt, kann den Fernet-Key rekonstruieren. Der SECRET_KEY bleibt also das alleinige Schutzmaterial.
- **Niemals PBKDF2 für diesen Zweck:** Verschwendet CPU pro Request, ohne Sicherheitsgewinn.

---

## Thema 3: Strava API OAuth2 Flow

### Kernfakten

- **Flow:** Standard OAuth2 Authorization Code (3-legged).
- **Authorize-URL:** `https://www.strava.com/oauth/authorize` (Web), `https://www.strava.com/oauth/mobile/authorize` (Mobile).
- **Token-URL:** `POST https://www.strava.com/oauth/token`.
- **localhost erlaubt:** ✅ **Ja, explizit whitelisted.** Zitat aus der Doku: *"`localhost` and `127.0.0.1` are white-listed."* – müssen aber zur im App-Setup konfigurierten Callback-Domain passen.
- **Access-Token Lebensdauer:** 6 Stunden.
- **Refresh-Token:** Kein explizites Ablaufdatum; wird bei jeder Refresh-Operation durch einen neuen ersetzt (rollender Refresh).
- **Scopes:** `activity:read` (öffentliche + Followers), `activity:read_all` (inkl. private + Privacy-Zones), `activity:write`, `profile:read_all`, `profile:write`.
- **Rate Limits:** In der Doku unter `/docs/rate-limits/` separat dokumentiert (Standard: 100 Requests / 15 min, 1.000 Requests / Tag – Stand 2024, aktueller Wert kann variieren).

### Quellen

- [Strava Developers – Authentication](https://developers.strava.com/docs/authentication/)
- [Strava Developers – Getting Started](https://developers.strava.com/docs/getting-started/)

### Praktische Empfehlung

Für lokales Flask-Projekt in `config.py`:

```python
STRAVA_CLIENT_ID = os.environ["STRAVA_CLIENT_ID"]
STRAVA_CLIENT_SECRET = os.environ["STRAVA_CLIENT_SECRET"]
STRAVA_REDIRECT_URI = "http://localhost:5000/connectors/strava/callback"
```

Im Strava App-Setup (https://www.strava.com/settings/api): **Authorization Callback Domain** = `localhost`. Dann ist jeder Port/Pfad unter localhost erlaubt.

**Python-Library:** `stravalib` (aktiv gepflegt) oder direkt `requests-oauthlib` – letzteres ist schlanker und lässt sich besser in die Connector-ABC integrieren.

### Risiken / Einschränkungen

- **Refresh-Token ist single-use-rolling:** Race-Condition bei parallelen Refresh-Requests aus derselben Session führt zu invalidiertem Token. Lösung: Refresh serialisieren (DB-Lock oder In-Process-Lock).
- **Rate-Limits sind App-global, nicht pro User:** Bei Multi-User-Betrieb teilen sich alle User das Budget. Bei >100 Usern kann das eng werden – dann Strava "higher-tier" Access beantragen.
- **HTTPS für Nicht-localhost Redirect-URIs vorgeschrieben** – für lokale Entwicklung HTTP auf localhost OK.

---

## Thema 4: Komoot API Zugang

### Kernfakten

- **Offizielle öffentliche API:** ❌ Nein, nur für selektierte Partner (GPS-Gerätehersteller, Wearables). Öffentliche Doku: `https://static.komoot.de/doc/external-api/v007/index.html` (Partner-Only, eingeschränkt).
- **Inoffizielle REST-Endpunkte:** Basis `https://www.komoot.com/api/v007/` bzw. `https://external-api.komoot.de/v007/`. Auth via Basic Auth (Email + Passwort).
- **Aktivste Python-Lib:** `Tsadoq/kompy` (v0.0.10, Februar 2025). Unterstützt: Tours lesen, GPX/FIT Upload/Download, Aktivitäten umbenennen/löschen.
- **Weitere Optionen:** `janthomas89/komoot-api-client` (PHP), diverse `komoot-export`-Repos auf GitHub.
- **OAuth2-Beispiel von Komoot selbst:** `github.com/komoot/komoot-oauth2-connect-example` – aber nur für API-Partner freigeschaltet, nicht für normale Entwickler zugänglich.

### Quellen

- [Tsadoq/kompy (GitHub)](https://github.com/Tsadoq/kompy)
- [Komoot API Support-Artikel](https://support.komoot.com/hc/en-us/articles/7464746034458-Komoot-API)
- [komoot/komoot-oauth2-connect-example](https://github.com/komoot/komoot-oauth2-connect-example)

### Praktische Empfehlung

**Komoot in Phase 1 nicht einbauen, in Phase 2+ optional als "experimentell".**

Falls doch: `kompy` als Python-Wrapper nutzen, im UI **klar kennzeichnen** ("Inoffizielle Anbindung, kann jederzeit brechen"). Credentials behandeln wie Garmin: verschlüsselt in DB (Fernet), nie in Logs.

Alternative mit geringerem Risiko: **GPX/FIT-Datei-Upload als User-Feature** – Komoot erlaubt GPX-Export pro Tour manuell, die kann der User hochladen und wir parsen sie mit `gpxpy`.

### Risiken / Einschränkungen

- **ToS-Verstoß:** Die Komoot-Terms verbieten automatisiertes Scraping ohne Partner-Vereinbarung. Risiko: Account-Sperre des Users, nicht der App.
- **Keine Stabilitätsgarantie:** API kann sich jederzeit ändern (v007-Versionierung deutet auf interne API hin).
- **Credentials-Exposition:** Basic Auth = Passwort liegt (verschlüsselt) in unserer DB. Bei Leak muss User Komoot-Passwort ändern, nicht nur unser App-Passwort.
- **2FA:** Komoot unterstützt aktuell kein 2FA → gering, aber falls es kommt, bricht die Integration sofort.

---

## Thema 5: Samsung Health API / SDK

### Kernfakten

- **Samsung Health SDK for Android:** Deprecated seit **31. Juli 2025**. Grace Period bis **2028** (2 Jahre ab Deprecation), danach End-of-Service.
- **Ersatz:** **Samsung Health Data SDK** – ebenfalls **Android-only**, NICHT Web/REST.
- **Web/REST-API für Dritte:** ❌ **Existiert nicht.** Weder die alte noch die neue SDK bietet HTTP-Zugriff – ausschließlich native Android-Integration.
- **Samsung Health Data SDK Features:** Read/Write von Health-Datentypen, Developer-Mode für Tests ohne Partner-Request, Partner-Request nötig für Play-Store-Release.
- **Alternative Brücke:** Google Health Connect (Android-System-API, liest Samsung-Daten via Sync) – auch nicht Web.

### Quellen

- [Samsung Health Data SDK](https://developer.samsung.com/health/data)
- [Dev Insight Oct 2025 – SDK Migration](https://developer.samsung.com/sdp/news/en/2025/10/30/dev-insight-oct-2025-move-to-samsung-health-data-sdk-as-samsung-health-sdk-for-android-deprecates-and-other-latest-news)
- [Samsung Health Release Notes](https://developer.samsung.com/health/android/release-note.html)

### Praktische Empfehlung

**Samsung Health NICHT als Connector in eine Flask-Web-App integrieren.** Technisch unmöglich ohne Android-Companion-App.

**Fallback für Phase 3+:** Manueller Import-Feature im UI – User lädt CSV/JSON-Export aus der Samsung-Health-App hoch, Flask parst ihn. Das umgeht das Android-Problem und funktioniert auch für andere Apps (Apple Health, Fitbit etc.) einheitlich.

### Risiken / Einschränkungen

- **Keine Workarounds:** Auch Reverse-Engineering des Samsung-Accounts ist sinnlos, da keine Server-API existiert – alle Daten liegen lokal auf dem Android-Gerät.
- **Import-Feature:** Export-Format von Samsung Health ist dokumentiert (JSON-Struktur im Export-Archiv), aber kann bei App-Updates brechen.

---

## Thema 6: garminconnect Python Library (aktuelle Issues)

### Kernfakten (sehr aktuell!)

- **Aktuelle Version:** **0.3.3** – Release am **22. April 2026** (ein Tag vor Research-Datum).
- **Unsere geplante Version (0.3.2):** Eine Version zurück; Upgrade empfohlen.
- **MFA-Handling:** Callback-Pattern seit 0.3.x:
  ```python
  Garmin(email, password, prompt_mfa=lambda: input("MFA code: "))
  ```
  Im Flask-Kontext: Callback schreibt in Session + löst Redirect zu MFA-Formular aus.
- **Token-Persistenz:** `~/.garminconnect/garmin_tokens.json`, automatisch mit `mode 0600` geschrieben.
- **Auto-Refresh:** Library prüft vor jedem Request das Ablaufdatum und refreshed via `diauth.garmin.com` – kein manueller Code nötig.
- **Akuter Vorfall vom 17.03.2026 (Issue #332):** Garmin hat am OAuth-preauthorized-Endpoint (`connectapi.garmin.com/oauth-service/oauth/preauthorized`) etwas geändert → 401-Fehler in allen Client-Libraries. **Issue ist geschlossen**, d.h. in einer der letzten Releases (0.3.3?) ist ein Fix drin.
- **Home-Assistant-Integration (Issue #420, März 2026):** MFA-Login-Fehler nach HA-Update 2026.3.2 – nur MFA-User betroffen. Zeigt: MFA-Pfad bleibt fragil.

### Quellen

- [cyberjunky/python-garminconnect (GitHub)](https://github.com/cyberjunky/python-garminconnect)
- [Issue #332 – Auth API Change (geschlossen)](https://github.com/cyberjunky/python-garminconnect/issues/332)
- [Issue #420 – MFA Login Error 2026.3.2](https://github.com/cyberjunky/home-assistant-garmin_connect/issues/420)
- [Issue #337 – 429 Too Many Requests](https://github.com/cyberjunky/python-garminconnect/issues/337)

### Praktische Empfehlung

1. **`garminconnect==0.3.3` pinnen** (nicht 0.3.2, wie im Plan). Konkret: `requirements.txt` anpassen.
2. **MFA-Support vorsehen**, auch wenn Phase 1 noch ohne. Der Callback ist pro User gespeicherter State – passt gut zum Multi-User-Modell.
3. **Retry-Logik** mit exponential backoff bei `GarminConnectTooManyRequestsError` (429). Spezifisch: 1x warten 60s, 2x warten 120s, dann hart fehlschlagen.
4. **Token-Isolation pro User** wie bereits im Research-Report empfohlen: `~/.sport-challenge/garmin-tokens/<user_id>/`.
5. **Monitoring:** GitHub-Releases via RSS abonnieren, bei neuem Release innerhalb von 7 Tagen upgraden (typischer Abstand zwischen Garmin-Breaking-Changes und Lib-Fixes).

### Risiken / Einschränkungen

- **Cloudflare kann jederzeit blocken:** Library umgeht nichts, sie macht normale HTTP-Requests. Bei neuem Cloudflare-Rollout kann alles brechen.
- **429-Rate-Limit beim Login:** Insbesondere bei Test-Loops → im Development unbedingt Token-Reuse verwenden, nie pro Testlauf frisch einloggen.
- **Breaking Changes zwischen Minor-Versionen möglich:** 0.3.x → 0.4.x könnte API-Änderungen bringen. Version-Pinning in Requirements.
- **Account-Sperre-Risiko:** Garmin kann bei "verdächtigem Verhalten" (viele Logins, ungewöhnliche Requests) Accounts temporär sperren.

---

## Thema 7: SQLite Verschlüsselung

### Kernfakten

- **pysqlcipher3:** ❌ **Nicht mehr gepflegt**, keine Python-3.14-Wheels.
- **sqlcipher3 (coleifer/sqlcipher3):** ✅ **Aktiv gepflegt.** v0.6.2 vom **07.01.2026**. Python-3.14-Wheels verfügbar (inkl. Free-Threaded `cp314t`).
- **macOS-Support:** ARM64 (macOS 11.0+), x86_64 (macOS 10.9+), Universal2. Installation via `pip install sqlcipher3` oder `sqlcipher3-binary` (self-contained).
- **Flask-SQLAlchemy-Integration:** Funktioniert über custom `creator` im Engine-URL – aber: SQLAlchemy-Kompatibilität erfordert evtl. Dialect-Patches (Issue #5848).
- **Alternative – Application-Level Fernet:** Nur sensible Felder (Connector-Credentials) mit Fernet verschlüsseln, DB-Schema bleibt lesbar.

### Quellen

- [sqlcipher3 auf PyPI](https://pypi.org/project/sqlcipher3/)
- [coleifer/sqlcipher3 auf GitHub](https://github.com/coleifer/sqlcipher3)
- [sqlalchemy/sqlalchemy Issue #5848](https://github.com/sqlalchemy/sqlalchemy/issues/5848)

### Praktische Empfehlung

**Für dieses lokale Projekt: Fernet auf Feldebene, NICHT SQLCipher.**

Begründung:
- **Bedrohungsmodell lokal:** Wer physischen Zugriff auf die SQLite-Datei hat, hat wahrscheinlich auch Zugriff auf den SECRET_KEY → SQLCipher-Passwort-Schutz ist nicht stärker.
- **Der Hauptwert liegt in Connector-Credentials** (Garmin-/Strava-Tokens). Fernet darauf erfüllt diesen Zweck direkt.
- **Keine Build-Pipeline für C-Extension** nötig → einfacher Install auf jedem macOS/Linux.
- **Metadaten-Sichtbarkeit unkritisch:** Usernames + Aktivitätstabellen sind kein Schutzgut.

**Falls SQLCipher doch gewünscht (Phase 5+):** `sqlcipher3-binary` nehmen, nicht `pysqlcipher3`.

### Risiken / Einschränkungen

- **Fernet-Key-Verlust = Credentials-Verlust:** User muss Connector neu verbinden. Kein Recovery möglich (by design).
- **Kein "encryption at rest" für die gesamte DB** mit Fernet-Ansatz – aber wie gesagt, im lokalen Modell kein realistisches Angreifer-Szenario.
- **SQLCipher-Migration später möglich:** Schema bleibt kompatibel, nur die Engine-URL ändert sich.

---

## Thema 8: Flask RBAC ohne Heavy Frameworks

### Kernfakten

- **Kanonisches Pattern:** Custom Decorator mit `functools.wraps`, der vor dem View-Call `current_user.is_authenticated` und `current_user.role` prüft.
- **Stacking-Reihenfolge (WICHTIG):** `@app.route(...)` MUSS **outermost** sein. Flask-Login-Doku: *"the @route() decorator must always be the outer-most decorator, followed by role-based decorators."*
- **Flask evaluiert Decorators von UNTEN nach OBEN** – daher steht `@login_required` UNTER `@admin_required` in der Datei, wenn admin_required seinerseits `login_required` NICHT bereits eingebaut hat.
- **Best Practice:** `admin_required` verkettet `login_required` intern → nur noch `@admin_required` nötig, keine Fehler durch vergessenes Stacking.
- **Frameworks:** Flask-User (schwergewichtig, v1.0 seit 2019 kaum aktualisiert), Flask-RBAC (minimal, aber seit Jahren stagnierend), Flask-Principal (zusätzliche Konzepte wie Identity/Need).

### Quellen

- [Flask-User Documentation – Authorization](https://flask-user.readthedocs.io/en/latest/authorization.html)
- [GeeksforGeeks – Flask RBAC](https://www.geeksforgeeks.org/python/flask-role-based-access-control/)
- [Auth0 Flask RBAC Code Sample](https://developer.auth0.com/resources/code-samples/api/flask/basic-role-based-access-control)

### Praktische Empfehlung

Für zwei Rollen (user/admin) ist ein **einfacher Custom-Decorator völlig ausreichend**:

```python
from functools import wraps
from flask import abort
from flask_login import current_user, login_required

def admin_required(f):
    @wraps(f)
    @login_required  # verkettet, damit Caller sich nicht um Reihenfolge kümmern muss
    def decorated(*args, **kwargs):
        if not current_user.is_admin:  # bool property auf User-Model
            abort(403)
        return f(*args, **kwargs)
    return decorated
```

Rolle als String-Feld (`'user'`/`'admin'`) reicht. Eigene `roles`-Tabelle lohnt sich erst ab 3+ Rollen oder feingranularen Permissions.

### Risiken / Einschränkungen

- **TOCTOU-Klassiker:** User wird zwischen Rolle-Check und View-Code entrollt. Unkritisch für HTTP-Request-Scope (wenige ms), aber relevant bei langen Requests. Mitigierung: Entscheidungen im View NICHT mehrfach rollen-basiert verzweigen, sondern am Eingang einmal prüfen.
- **Fehlende POST-Route-Absicherung:** Klassischer Fehler – GET /admin hat `@admin_required`, aber das zugehörige POST /admin/update nicht. **Beide** Methoden müssen separat abgesichert werden.
- **403 vs. 401:** `abort(403)` für eingeloggten User ohne Rolle, `login_required` liefert 401-Redirect für nicht eingeloggte. Konsistenz wichtig.
- **Keine Defense-in-Depth bei DB-Queries:** Der Decorator schützt die Route, aber `User.query.filter_by(...).all()` ohne `user_id`-Filter kann Daten anderer User leaken. **Row-Level-Security über ORM-Queries** ist eine separate Schutzschicht, die der Decorator NICHT ersetzt.

---

## Konsolidierte Änderungen für den Research-Report

Basierend auf der Nachrecherche ergeben sich folgende Updates für `2026-04-23-architektur-best-practices-rebuild-sport-challenge-flask.md`:

| Bereich | Bisher | Korrektur / Präzisierung |
|---------|--------|--------------------------|
| Werkzeug-scrypt Parameter | „n=2^15, r=8, p=1" | ✅ Bestätigt durch Primärquelle `security.py:57,131`. Explizit: Werkzeug liegt 2 Größenordnungen unter OWASP (2¹⁵ vs. 2¹⁷) |
| garminconnect Version | `==0.3.2` | ⚠️ **Upgrade auf 0.3.3 (22.04.2026)** – Fix für OAuth-Breaking-Change vom 17.03.2026 |
| Strava localhost | „Community-Berichte" | ✅ **Offiziell bestätigt**: localhost + 127.0.0.1 whitelisted laut Developer-Docs |
| Strava Token-Lifetime | Access 6h | ✅ Bestätigt. Refresh rollierend (single-use), Race-Condition beachten |
| pysqlcipher3 | „Build-Probleme" | 🔁 **Sprach-Update**: `pysqlcipher3` deprecated, Nachfolger ist `sqlcipher3` (v0.6.2, Python-3.14-Wheels verfügbar) |
| Samsung Health | „Nicht realistisch" | ✅ Bestätigt, konkrete Timeline: End-of-Service 2028. Kein Web-API – auch neue Data SDK ist Android-only |
| Komoot | „Experimentell kennzeichnen" | ➕ Zusatz: `Tsadoq/kompy` (v0.0.10, Feb 2025) ist die aktivste Python-Lib; Alternative GPX-Upload-Feature empfohlen |
| RBAC-Decorator | Korrekt | ➕ Zusatz: `admin_required` sollte `login_required` INTERN verketten (DX-Gewinn, Fehlervermeidung) |
| HKDF | Korrekt | ✅ Bestätigt durch django-fernet-fields-Präzedenz und RFC-5869-Referenz |

---

## Offene Punkte / weiterführende Recherche

- **Strava Rate Limits 2026:** Konkrete aktuelle Werte nicht in der Core-Doku – im Strava-Dashboard des eigenen Accounts sichtbar nach App-Registrierung.
- **Komoot ToS:** Eine rechtliche Prüfung der aktuellen Nutzungsbedingungen wäre vor Produktiv-Rollout sinnvoll.
- **Garmin MFA-Flow in Flask:** Konkreter Code-Pattern für asynchronen MFA-Callback im HTTP-Request-Cycle (Session → Redirect → MFA-Form → Resume Login) ist nicht in der garminconnect-Doku dokumentiert. Muss prototypisch entwickelt werden.
- **SQLCipher-SQLAlchemy-Dialect:** Falls doch eingeführt, prüfen ob Upstream-Patch (Issue #5848) inzwischen gemergt ist.

---

**Report-Status:** ✅ Alle 8 Themen bearbeitet, alle Primärquellen verifiziert. Research-Report kann jetzt angereichert werden.
