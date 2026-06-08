"""Erzeugung externer URLs unabhängig vom (potenziell gespooften) Request-Host.

Siehe Issue ``haf``: Passwort-Reset-, Admin-/Approval-Mail- und OAuth-URLs dürfen
nicht aus dem eingehenden Host-Header abgeleitet werden, sondern aus einer
kontrolliert konfigurierten Basis-URL (``PUBLIC_BASE_URL``).
"""

from urllib.parse import urljoin

from flask import current_app, url_for


def external_url_for(endpoint: str, **values: object) -> str:
    """Wie ``url_for(..., _external=True)``, aber Host-unabhängig.

    Ist ``PUBLIC_BASE_URL`` konfiguriert, wird die externe URL aus dieser
    kanonischen Basis plus dem relativen Pfad gebildet – der eingehende
    Host-Header wird dabei ignoriert. Ohne Konfiguration (lokale Entwicklung)
    fällt die Funktion auf das normale ``_external=True``-Verhalten zurück.
    """
    base_url = current_app.config.get("PUBLIC_BASE_URL")
    if base_url:
        relative_path = url_for(endpoint, **values)
        return urljoin(base_url.rstrip("/") + "/", relative_path.lstrip("/"))
    return url_for(endpoint, _external=True, **values)
