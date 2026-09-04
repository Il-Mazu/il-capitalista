from __future__ import annotations

import requests

import pytest

from discogs_auto_pricer.api import DiscogsApiError, DiscogsClient


class FakeResponse:
    def __init__(self, status, payload=None, headers=None, text="error"):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.headers = {}
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        reply = next(self.replies)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def test_retries_429_using_retry_after():
    waits = []
    session = FakeSession([FakeResponse(429, headers={"Retry-After": "3"}), FakeResponse(200, {"Mint (M)": {"value": 2}})])
    client = DiscogsClient("secret", session=session, sleeper=waits.append)
    assert client.get_price_suggestions("1")["Mint (M)"]["value"] == 2
    assert waits == [3.0]
    assert session.headers["Authorization"] == "Discogs token=secret"


def test_retries_500_then_fails_with_bounded_attempts():
    waits = []
    client = DiscogsClient("secret", session=FakeSession([FakeResponse(500), FakeResponse(500), FakeResponse(500)]), max_attempts=3, sleeper=waits.append)
    with pytest.raises(DiscogsApiError, match="HTTP 500"):
        client.get_price_suggestions("1")
    assert waits == [1.0, 2.0]


def test_retries_timeout():
    waits = []
    session = FakeSession([requests.Timeout(), FakeResponse(200, {})])
    client = DiscogsClient("secret", session=session, sleeper=waits.append)
    assert client.get_price_suggestions("1") == {}
    assert waits == [1.0]


def test_does_not_retry_client_error():
    client = DiscogsClient("secret", session=FakeSession([FakeResponse(401)]), sleeper=lambda _: None)
    with pytest.raises(DiscogsApiError, match="HTTP 401"):
        client.get_price_suggestions("1")
