"""Discogs official API client with bounded, polite retries."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import requests

BASE_URL = "https://api.discogs.com/marketplace/price_suggestions"
LOGGER = logging.getLogger(__name__)


class DiscogsApiError(RuntimeError):
    """A request failed after its retry budget was exhausted."""


class DiscogsClient:
    def __init__(
        self,
        token: str,
        *,
        session: requests.Session | None = None,
        timeout: float = 20.0,
        max_attempts: int = 5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.sleeper = sleeper
        self.session.headers.update({
            "Authorization": f"Discogs token={token}",
            "User-Agent": "discogs-auto-pricer/1.0",
            "Accept": "application/json",
        })

    @staticmethod
    def _retry_delay(response: requests.Response | None, attempt: int) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return max(0.0, float(retry_after))
                except ValueError:
                    pass
        return min(30.0, 1.0 * (2 ** (attempt - 1)))

    def get_price_suggestions(self, release_id: str) -> dict[str, dict[str, Any]]:
        """Get condition-keyed suggestions for a numeric release identifier."""
        url = f"{BASE_URL}/{release_id}"
        last_error = "richiesta non completata"
        for attempt in range(1, self.max_attempts + 1):
            response: requests.Response | None = None
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise DiscogsApiError("Risposta API inattesa (non è un oggetto JSON).")
                    remaining = response.headers.get("X-Discogs-Ratelimit-Remaining")
                    if remaining is not None:
                        try:
                            if int(remaining) <= 0:
                                LOGGER.info("Rate limit Discogs esaurito: pausa di 60 secondi.")
                                self.sleeper(60.0)
                        except ValueError:
                            pass
                    return payload
                if response.status_code not in (429,) and not 500 <= response.status_code < 600:
                    raise DiscogsApiError(f"HTTP {response.status_code}: {response.text[:200]}")
                last_error = f"HTTP {response.status_code}"
            except requests.Timeout:
                last_error = "timeout HTTP"
            except requests.RequestException as error:
                last_error = f"errore di rete: {error}"
            except ValueError as error:
                raise DiscogsApiError("Risposta API non contiene JSON valido.") from error

            if attempt < self.max_attempts:
                delay = self._retry_delay(response, attempt)
                LOGGER.warning("Discogs %s; nuovo tentativo tra %.1f s (%s/%s).", last_error, delay, attempt, self.max_attempts)
                self.sleeper(delay)
        raise DiscogsApiError(f"Discogs non disponibile dopo {self.max_attempts} tentativi: {last_error}")
