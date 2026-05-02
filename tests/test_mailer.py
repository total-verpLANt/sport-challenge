"""Tests für app/services/mailer.py"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.mailer import MailgunError, MailgunService


class TestMailgunServiceInit:
    def test_raises_without_api_key(self):
        with pytest.raises(MailgunError, match="nicht konfiguriert"):
            MailgunService(api_key="", domain="mg.example.com", sender="noreply@mg.example.com")

    def test_raises_without_domain(self):
        with pytest.raises(MailgunError, match="nicht konfiguriert"):
            MailgunService(api_key="key-123", domain="", sender="noreply@mg.example.com")

    def test_raises_without_sender(self):
        with pytest.raises(MailgunError, match="nicht konfiguriert"):
            MailgunService(api_key="key-123", domain="mg.example.com", sender="")

    def test_valid_config_creates_instance(self):
        svc = MailgunService(api_key="key", domain="mg.example.com", sender="no@mg.example.com")
        assert svc is not None


class TestMailgunServiceSend:
    @pytest.fixture()
    def svc(self):
        return MailgunService(
            api_key="key-abc",
            domain="mg.example.com",
            sender="Sport Challenge <noreply@mg.example.com>",
        )

    def _mock_response(self, status_code=200, json_body=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.ok = status_code < 400
        resp.json.return_value = json_body or {"id": "<msg-id@mailgun.org>", "message": "Queued"}
        resp.text = str(json_body)
        return resp

    def test_raises_without_body(self, svc):
        with pytest.raises(ValueError, match="text oder html"):
            svc.send(to="user@example.com", subject="Test")

    def test_successful_send_returns_message_id(self, svc):
        with patch.object(svc._session, "post", return_value=self._mock_response()) as mock_post:
            msg_id = svc.send(to="user@example.com", subject="Hallo", text="Welt")

        assert msg_id == "<msg-id@mailgun.org>"
        call_kwargs = mock_post.call_args
        data = call_kwargs.kwargs.get("data") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["data"]
        assert data["to"] == ["user@example.com"]
        assert data["subject"] == "Hallo"
        assert data["text"] == "Welt"

    def test_send_uses_correct_endpoint(self, svc):
        with patch.object(svc._session, "post", return_value=self._mock_response()) as mock_post:
            svc.send(to="x@y.com", subject="s", text="t")

        url = mock_post.call_args.args[0]
        assert "mg.example.com" in url
        assert "/messages" in url

    def test_send_uses_basic_auth(self, svc):
        with patch.object(svc._session, "post", return_value=self._mock_response()) as mock_post:
            svc.send(to="x@y.com", subject="s", text="t")

        auth = mock_post.call_args.kwargs["auth"]
        assert auth == ("api", "key-abc")

    def test_429_raises_mailgun_error(self, svc):
        with patch.object(svc._session, "post", return_value=self._mock_response(status_code=429)):
            with pytest.raises(MailgunError, match="Rate-Limit"):
                svc.send(to="x@y.com", subject="s", text="t")

    def test_500_raises_mailgun_error(self, svc):
        with patch.object(svc._session, "post", return_value=self._mock_response(status_code=500)):
            with pytest.raises(MailgunError, match="Status 500"):
                svc.send(to="x@y.com", subject="s", text="t")

    def test_connection_error_raises_mailgun_error(self, svc):
        import requests as _requests
        with patch.object(svc._session, "post", side_effect=_requests.ConnectionError("timeout")):
            with pytest.raises(MailgunError, match="Verbindung"):
                svc.send(to="x@y.com", subject="s", text="t")

    def test_list_recipients_sent_as_list(self, svc):
        with patch.object(svc._session, "post", return_value=self._mock_response()) as mock_post:
            svc.send(to=["a@b.com", "c@d.com"], subject="s", text="t")

        data = mock_post.call_args.kwargs["data"]
        assert data["to"] == ["a@b.com", "c@d.com"]

    def test_html_only_accepted(self, svc):
        with patch.object(svc._session, "post", return_value=self._mock_response()):
            svc.send(to="x@y.com", subject="s", html="<b>Hallo</b>")

    def test_tags_sent_as_o_tag(self, svc):
        with patch.object(svc._session, "post", return_value=self._mock_response()) as mock_post:
            svc.send(to="x@y.com", subject="s", text="t", tags=["test-tag"])

        data = mock_post.call_args.kwargs["data"]
        assert data["o:tag"] == ["test-tag"]
