from __future__ import annotations

from decimal import Decimal

from discogs_auto_pricer.cache import PriceCache
from discogs_auto_pricer.api import DiscogsApiError
from discogs_auto_pricer.csv_handler import write_inventory
from discogs_auto_pricer.pricing import PriceEngine, format_money, money, report_row


def suggestions(**conditions):
    return {condition: {"value": value, "currency": "EUR"} for condition, value in conditions.items()}


def engine(read, tmp_path, rows, fetcher, **kwargs):
    return PriceEngine(read(rows), fetcher, PriceCache(tmp_path / "cache.json"), **kwargs)


def row(release="123", condition="Very Good Plus (VG+)", price="40.00", status="For Sale"):
    return {"listing_id": "7", "release_id": release, "artist": "Pink Floyd", "title": "The Wall", "media_condition": condition, "sleeve_condition": "Good (G)", "price": price, "comments": "", "status": status}


def test_updates_present_price_and_matches_vg_plus(read, tmp_path):
    subject = engine(read, tmp_path, [row()], lambda _: suggestions(**{"Very Good Plus (VG+)": "35.75"}))
    outcome = subject.process()[0]
    assert outcome.row["price"] == "35.75"
    assert outcome.result == "UPDATED"
    assert report_row(outcome, subject.inventory)["difference"] == "-4.25"


def test_updates_empty_price_and_matches_near_mint(read, tmp_path):
    subject = engine(read, tmp_path, [row(condition="Near Mint (NM or M-)", price="")], lambda _: suggestions(**{"Near Mint (NM or M-)": 15.5}))
    result = subject.process()[0]
    assert result.row["price"] == "15.50"
    assert result.result == "UPDATED"


def test_no_suggestion_leaves_price(read, tmp_path):
    subject = engine(read, tmp_path, [row()], lambda _: {})
    result = subject.process()[0]
    assert (result.result, result.row["price"]) == ("NO_SUGGESTION", "40.00")


def test_duplicate_release_makes_one_fetch(read, tmp_path):
    calls: list[str] = []
    subject = engine(read, tmp_path, [row(), row(price="10.00")], lambda release: calls.append(release) or suggestions(**{"Very Good Plus (VG+)": 12}))
    outcomes = subject.process()
    assert calls == ["123"]
    assert [item.row["price"] for item in outcomes] == ["12.00", "12.00"]
    assert subject.stats.unique_api_requests == 1


def test_invalid_condition_and_release_id_are_not_fetched(read, tmp_path):
    calls: list[str] = []
    subject = engine(read, tmp_path, [row(condition="Excellent"), row(release="abc")], lambda release: calls.append(release) or {})
    outcomes = subject.process()
    assert [item.result for item in outcomes] == ["INVALID_CONDITION", "INVALID_RELEASE_ID"]
    assert calls == []


def test_status_not_for_sale_is_skipped(read, tmp_path):
    subject = engine(read, tmp_path, [row(status="Sold")], lambda _: (_ for _ in ()).throw(AssertionError("must not fetch")))
    result = subject.process()[0]
    assert result.result == "SKIPPED_STATUS"
    assert result.row["price"] == "40.00"


def test_money_rounding_and_limits(read, tmp_path):
    assert format_money(money("15.678")) == "15.68"
    subject = engine(read, tmp_path, [row(price="10.00")], lambda _: suggestions(**{"Very Good Plus (VG+)": "17.00"}), max_increase_percent=Decimal("50"))
    result = subject.process()[0]
    assert result.result == "UNCHANGED"
    assert result.row["price"] == "10.00"


def test_persistent_cache_avoids_fetch_on_second_engine(read, tmp_path):
    cache_path = tmp_path / "suggestions.json"
    first = PriceEngine(read([row()]), lambda _: suggestions(**{"Very Good Plus (VG+)": 9}), PriceCache(cache_path))
    first.process()
    second = PriceEngine(read([row()]), lambda _: (_ for _ in ()).throw(AssertionError("cache not used")), PriceCache(cache_path))
    assert second.process()[0].row["price"] == "9.00"
    assert second.stats.cache_hits == 1


def test_failed_duplicate_release_is_requested_only_once(read, tmp_path):
    calls = []
    subject = engine(read, tmp_path, [row(), row()], lambda release: calls.append(release) or (_ for _ in ()).throw(DiscogsApiError("offline")))
    assert [item.result for item in subject.process()] == ["API_ERROR", "API_ERROR"]
    assert calls == ["123"]


def test_inventory_output_keeps_only_for_sale_and_original_schema(read, tmp_path):
    inventory = read([row(), row(release="124", status="Draft")])
    subject = PriceEngine(inventory, lambda _: suggestions(**{"Very Good Plus (VG+)": "20"}), PriceCache(tmp_path / "cache.json"))
    outcomes = subject.process()
    target = tmp_path / "safe.csv"
    write_inventory(target, inventory, [item.row for item in outcomes if item.result != "SKIPPED_STATUS"])
    content = target.read_text(encoding="utf-8")
    assert content.splitlines()[0].split(",") == inventory.fieldnames
    assert content.count("\n") == 2
    assert outcomes[1].row["price"] == "40.00"


def test_refresh_cache_forces_fetch(read, tmp_path):
    path = tmp_path / "cache.json"
    PriceEngine(read([row()]), lambda _: suggestions(**{"Very Good Plus (VG+)": 9}), PriceCache(path)).process()
    calls = []
    refreshed = PriceEngine(read([row()]), lambda release: calls.append(release) or suggestions(**{"Very Good Plus (VG+)": 11}), PriceCache(path, refresh=True))
    assert refreshed.process()[0].row["price"] == "11.00"
    assert calls == ["123"]
