from __future__ import annotations

import csv
import sys

import discogs_pricer


def test_cli_generates_safe_full_and_report_with_mocked_api(monkeypatch, inventory_file, tmp_path):
    rows = [
        {"listing_id": "1", "release_id": "123", "artist": "Test", "title": "Uno", "media_condition": "Very Good Plus (VG+)", "sleeve_condition": "Good (G)", "price": "10.00", "comments": "nota, con virgola", "status": "For Sale"},
        {"listing_id": "2", "release_id": "124", "artist": "Test", "title": "Due", "media_condition": "Mint (M)", "sleeve_condition": "Mint (M)", "price": "20.00", "comments": "non toccare", "status": "Draft"},
    ]
    source = inventory_file(rows)

    class MockClient:
        def __init__(self, token):
            assert token == "test-token"

        def get_price_suggestions(self, release_id):
            assert release_id == "123"
            return {"Very Good Plus (VG+)": {"value": "12.34", "currency": "EUR"}}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DISCOGS_TOKEN", "test-token")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    monkeypatch.setattr(discogs_pricer, "DiscogsClient", MockClient)
    monkeypatch.setattr(sys, "argv", ["discogs_pricer.py", str(source)])
    assert discogs_pricer.main() == 0

    safe = tmp_path / "output/inventory_repriced.csv"
    full = tmp_path / "output/inventory_repriced_full.csv"
    report = tmp_path / "output/report.csv"
    assert safe.exists() and full.exists() and report.exists()
    with safe.open(encoding="utf-8", newline="") as handle:
        safe_rows = list(csv.DictReader(handle))
    with full.open(encoding="utf-8", newline="") as handle:
        full_rows = list(csv.DictReader(handle))
    assert safe_rows == [{**rows[0], "price": "12.34"}]
    assert full_rows == [{**rows[0], "price": "12.34"}, rows[1]]
