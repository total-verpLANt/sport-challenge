import logging
from collections.abc import Iterable

import requests
from flask import current_app

logger = logging.getLogger(__name__)


class MailgunError(Exception):
    """Wird geworfen wenn die Mailgun-API einen Fehler zurückgibt."""


class MailgunService:
    """Thin wrapper um den Mailgun v3 messages-Endpunkt."""

    def __init__(
        self,
        api_key: str,
        domain: str,
        sender: str,
        base_url: str = "https://api.mailgun.net/v3",
        timeout: float = 10.0,
    ):
        if not api_key or not domain or not sender:
            raise MailgunError(
                "Mailgun nicht konfiguriert – MAILGUN_API_KEY, "
                "MAILGUN_DOMAIN und MAILGUN_SENDER müssen gesetzt sein."
            )
        self._api_key = api_key
        self._domain = domain
        self._sender = sender
        self._endpoint = f"{base_url}/{domain}/messages"
        self._timeout = timeout
        self._session = requests.Session()

    def send(
        self,
        to: str | Iterable[str],
        subject: str,
        text: str | None = None,
        html: str | None = None,
        reply_to: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Sendet eine E-Mail. Gibt die Mailgun-Message-ID zurück."""
        if not text and not html:
            raise ValueError("text oder html muss angegeben werden")

        recipients = [to] if isinstance(to, str) else list(to)

        data: dict = {
            "from": self._sender,
            "to": recipients,
            "subject": subject,
        }
        if text:
            data["text"] = text
        if html:
            data["html"] = html
        if reply_to:
            data["h:Reply-To"] = reply_to
        if tags:
            data["o:tag"] = tags

        try:
            resp = self._session.post(
                self._endpoint,
                auth=("api", self._api_key),
                data=data,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.error("Mailgun-Verbindung fehlgeschlagen: %s", exc)
            raise MailgunError("Mailgun-Verbindung fehlgeschlagen") from exc

        if resp.status_code == 429:
            logger.warning("Mailgun Rate-Limit (429) erreicht")
            raise MailgunError("Mailgun Rate-Limit erreicht")

        if not resp.ok:
            # Nur die ersten 200 Zeichen loggen – Empfänger sind PII
            logger.error("Mailgun %s: %s", resp.status_code, resp.text[:200])
            raise MailgunError(f"Mailgun antwortete mit Status {resp.status_code}")

        return resp.json().get("id", "")


def get_mailer() -> MailgunService:
    """Gibt eine konfigurierte MailgunService-Instanz zurück (lazy, pro Request)."""
    cfg = current_app.config
    return MailgunService(
        api_key=cfg.get("MAILGUN_API_KEY") or "",
        domain=cfg.get("MAILGUN_DOMAIN") or "",
        sender=cfg.get("MAILGUN_SENDER") or "",
        base_url=cfg.get("MAILGUN_BASE_URL", "https://api.mailgun.net/v3"),
    )
