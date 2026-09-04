from __future__ import annotations

import csv

from discogs_auto_pricer.csv_handler import read_inventory, write_inventory


def test_preserves_order_and_quoted_comma_comment(inventory_file, tmp_path):
    fields = ["title", "release_id", "price", "media_condition", "comments"]
    path = inventory_file([{"title": "Álbum", "release_id": "12", "price": "1.00", "media_condition": "Very Good (VG)", "comments": "pulito, suona bene"}], fields)
    inventory = read_inventory(path)
    inventory.rows[0]["price"] = "2.50"
    target = tmp_path / "result.csv"
    write_inventory(target, inventory, inventory.rows)
    with target.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == fields
        assert next(reader) == {"title": "Álbum", "release_id": "12", "price": "2.50", "media_condition": "Very Good (VG)", "comments": "pulito, suona bene"}


def test_multiline_comment_and_utf8_are_read(inventory_file):
    path = inventory_file([{"listing_id": "1", "release_id": "8", "artist": "Björk", "title": "Début", "media_condition": "Mint (M)", "sleeve_condition": "M", "price": "", "comments": "prima riga\nseconda, riga", "status": "For Sale"}])
    inventory = read_inventory(path)
    assert inventory.rows[0]["comments"] == "prima riga\nseconda, riga"
    assert inventory.rows[0]["artist"] == "Björk"


def test_detects_human_friendly_headers(inventory_file):
    fields = ["Release ID", "Price", "Media Condition"]
    inventory = read_inventory(inventory_file([{"Release ID": "1", "Price": "2", "Media Condition": "Mint (M)"}], fields))
    assert inventory.columns == {"release_id": "Release ID", "price": "Price", "media_condition": "Media Condition"}
