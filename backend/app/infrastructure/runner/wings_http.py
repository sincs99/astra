"""Gekapselter HTTP-Client fuer Wings-Kommunikation.

Zentrale Stelle fuer alle ausgehenden HTTP-Requests an Wings-Runner.
- Konfigurierbarer Timeout
- Saubere Fehlerbehandlung
- Query-Parameter-Unterstuetzung
- Text- und JSON-Responses
- Logging ohne Secrets
"""

import logging
from dataclasses import dataclass

import requests as http_lib

from app.domain.agents.models import Agent

logger = logging.getLogger(__name__)


@dataclass
class WingsResponse:
    """Antwort eines Wings-HTTP-Aufrufs."""
    success: bool
    status_code: int | None
    data: dict | None
    error: str | None = None
    text: str | None = None


class WingsHttpClient:
    """HTTP-Client fuer Wings-API-Kommunikation."""

    def __init__(self, timeout: tuple[int, int] = (5, 30), debug: bool = False):
        self.timeout = timeout
        self.debug = debug

    def _build_url(self, agent: Agent, path: str, params: dict | None = None) -> str:
        """Baut die vollstaendige URL zusammen, optional mit Query-Parametern."""
        base = agent.get_connection_url()
        url = f"{base}{path}"

        if params:
            from urllib.parse import urlencode
            query = urlencode(params)
            url = f"{url}?{query}"

        return url

    def _build_headers(self, agent: Agent, content_type: str = "application/json") -> dict:
        """Erstellt die HTTP-Header inkl. Bearer-Auth."""
        headers = {
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "Astra-Panel/1.0",
        }

        # Wings erwartet Bearer-Token-Authentifizierung
        if agent.daemon_token:
            headers["Authorization"] = f"Bearer {agent.daemon_token}"

        return headers

    def _log_request(self, method: str, url: str, agent: Agent) -> None:
        """Loggt den Request ohne Secrets."""
        # Token aus URL entfernen falls versehentlich drin
        safe_url = url
        if agent.daemon_token:
            safe_url = url.replace(agent.daemon_token, "***")
        logger.info("[Wings] %s %s (Agent: %s)", method, safe_url, agent.name)

    def _log_response(self, response: WingsResponse, agent: Agent) -> None:
        """Loggt die Response."""
        if response.success:
            logger.info(
                "[Wings] Response: HTTP %s (Agent: %s)",
                response.status_code, agent.name
            )
        else:
            logger.warning(
                "[Wings] Response: HTTP %s - %s (Agent: %s)",
                response.status_code, response.error, agent.name
            )

    def get(self, agent: Agent, path: str, params: dict | None = None) -> WingsResponse:
        """Sendet einen GET-Request an Wings."""
        return self._request("GET", agent, path, params=params)

    def post(self, agent: Agent, path: str, json_data: dict | None = None, params: dict | None = None) -> WingsResponse:
        """Sendet einen POST-Request an Wings."""
        return self._request("POST", agent, path, json_data, params=params)

    def post_raw(self, agent: Agent, path: str, raw_body: str, params: dict | None = None) -> WingsResponse:
        """Sendet einen POST-Request mit Raw-Text-Body an Wings."""
        return self._request_raw("POST", agent, path, raw_body, params=params)

    def put(self, agent: Agent, path: str, json_data: dict | None = None) -> WingsResponse:
        """Sendet einen PUT-Request an Wings."""
        return self._request("PUT", agent, path, json_data)

    def patch(self, agent: Agent, path: str, json_data: dict | None = None) -> WingsResponse:
        """Sendet einen PATCH-Request an Wings."""
        return self._request("PATCH", agent, path, json_data)

    def delete(self, agent: Agent, path: str) -> WingsResponse:
        """Sendet einen DELETE-Request an Wings."""
        return self._request("DELETE", agent, path)

    def _request(
        self,
        method: str,
        agent: Agent,
        path: str,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> WingsResponse:
        """Fuehrt den eigentlichen HTTP-Request durch."""
        url = self._build_url(agent, path, params)
        headers = self._build_headers(agent)

        self._log_request(method, url, agent)

        if self.debug and json_data:
            logger.debug("[Wings] Payload: %s", json_data)

        try:
            response = http_lib.request(
                method=method,
                url=url,
                json=json_data,
                headers=headers,
                timeout=self.timeout,
            )

            return self._parse_response(response, agent)

        except http_lib.Timeout:
            logger.error("[Wings] Timeout: %s %s (Agent: %s)", method, url, agent.name)
            return WingsResponse(
                success=False, status_code=None, data=None,
                error="Timeout bei Wings-Verbindung"
            )

        except http_lib.ConnectionError:
            logger.error("[Wings] Verbindungsfehler: %s %s (Agent: %s)", method, url, agent.name)
            return WingsResponse(
                success=False, status_code=None, data=None,
                error="Wings nicht erreichbar"
            )

        except Exception as e:
            logger.error("[Wings] Unerwarteter Fehler: %s (Agent: %s)", str(e), agent.name)
            return WingsResponse(
                success=False, status_code=None, data=None,
                error=f"Unerwarteter Fehler: {str(e)}"
            )

    def _request_raw(
        self,
        method: str,
        agent: Agent,
        path: str,
        raw_body: str,
        params: dict | None = None,
    ) -> WingsResponse:
        """Fuehrt einen HTTP-Request mit Raw-Text-Body durch (fuer Datei-Schreiben)."""
        url = self._build_url(agent, path, params)
        headers = self._build_headers(agent, content_type="text/plain")

        self._log_request(method, url, agent)

        try:
            response = http_lib.request(
                method=method,
                url=url,
                data=raw_body.encode("utf-8"),
                headers=headers,
                timeout=self.timeout,
            )

            return self._parse_response(response, agent)

        except http_lib.Timeout:
            logger.error("[Wings] Timeout: %s %s (Agent: %s)", method, url, agent.name)
            return WingsResponse(
                success=False, status_code=None, data=None,
                error="Timeout bei Wings-Verbindung"
            )

        except http_lib.ConnectionError:
            logger.error("[Wings] Verbindungsfehler: %s %s (Agent: %s)", method, url, agent.name)
            return WingsResponse(
                success=False, status_code=None, data=None,
                error="Wings nicht erreichbar"
            )

        except Exception as e:
            logger.error("[Wings] Unerwarteter Fehler: %s (Agent: %s)", str(e), agent.name)
            return WingsResponse(
                success=False, status_code=None, data=None,
                error=f"Unerwarteter Fehler: {str(e)}"
            )

    def _parse_response(self, response, agent: Agent) -> WingsResponse:
        """Parst die HTTP-Response und gibt ein WingsResponse-Objekt zurueck."""
        is_success = 200 <= response.status_code < 300

        # Versuche JSON zu parsen
        data = None
        text = None
        content_type = response.headers.get("Content-Type", "")

        if response.content:
            if "application/json" in content_type:
                try:
                    data = response.json()
                except ValueError:
                    text = response.text
            else:
                text = response.text

        result = WingsResponse(
            success=is_success,
            status_code=response.status_code,
            data=data,
            text=text,
            error=None if is_success else f"HTTP {response.status_code}",
        )

        self._log_response(result, agent)
        return result
