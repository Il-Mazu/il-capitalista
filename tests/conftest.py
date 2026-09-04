from __future__ import annotations

import csv
from pathlib import Path

import pytest

from discogs_auto_pricer.csv_handler import read_inventory


@pytest.fixture
def inventory_file(tmp_path: Path):
    def make(rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> Path:
        path = tmp_path / "inventory.csv"
        names = fieldnames or ["listing_id", "release_id", "artist", "title", "media_condition", "sleeve_condition", "price", "comments", "status"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=names)
            writer.writeheader()
            writer.writerows(rows)
        return path
    return make


@pytest.fixture
def read(inventory_file):
    return lambda rows, fieldnames=None: read_inventory(inventory_file(rows, fieldnames))
