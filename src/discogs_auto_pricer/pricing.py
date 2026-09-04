"""Pricing decisions independent from the command-line interface."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Callable

from .api import DiscogsApiError
from .cache import PriceCache
from .models import ApiResponse, CsvInventory, RowOutcome, RunStats

VALID_CONDITIONS = {
    "Mint (M)", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Very Good (VG)",
    "Good Plus (G+)", "Good (G)", "Fair (F)", "Poor (P)",
}
RELEASE_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
CENT = Decimal("0.01")


def money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def format_money(value: Decimal) -> str:
    return format(value.quantize(CENT, rounding=ROUND_HALF_UP), ".2f")


def parse_money(value: str) -> Decimal | None:
    if not value.strip():
        return None
    try:
        return money(value.strip())
    except (InvalidOperation, ValueError):
        return None


def valid_release_id(value: str) -> bool:
    return bool(RELEASE_ID_PATTERN.fullmatch(value.strip()))


class PriceEngine:
    def __init__(
        self,
        inventory: CsvInventory,
        fetcher: Callable[[str], dict],
        cache: PriceCache,
        *,
        max_increase_percent: Decimal | None = None,
        max_decrease_percent: Decimal | None = None,
    ) -> None:
        self.inventory = inventory
        self.fetcher = fetcher
        self.cache = cache
        self.max_increase_percent = max_increase_percent
        self.max_decrease_percent = max_decrease_percent
        self.memory: dict[str, ApiResponse] = {}
        self.memory_errors: dict[str, DiscogsApiError] = {}
        self.stats = RunStats(rows_read=len(inventory.rows))

    def _suggestions(self, release_id: str) -> ApiResponse:
        if release_id in self.memory:
            return self.memory[release_id]
        if release_id in self.memory_errors:
            raise self.memory_errors[release_id]
        cached = self.cache.get(release_id)
        if cached is not None:
            result = ApiResponse(cached, from_cache=True)
            self.stats.cache_hits += 1
        else:
            try:
                suggestions = self.fetcher(release_id)
            except DiscogsApiError as error:
                self.memory_errors[release_id] = error
                self.stats.unique_api_requests += 1
                raise
            if not isinstance(suggestions, dict):
                error = DiscogsApiError("Risposta API inattesa.")
                self.memory_errors[release_id] = error
                self.stats.unique_api_requests += 1
                raise error
            self.cache.set(release_id, suggestions)
            result = ApiResponse(suggestions)
            self.stats.unique_api_requests += 1
        self.memory[release_id] = result
        return result

    def _safe_status(self, row: dict[str, str]) -> bool:
        column = self.inventory.columns.get("status")
        return column is None or row[column].strip().casefold() == "for sale"

    def _exceeds_limits(self, old: Decimal | None, new: Decimal) -> str | None:
        if old is None or old <= 0:
            return None
        change = (new - old) / old * Decimal("100")
        if self.max_increase_percent is not None and change > self.max_increase_percent:
            return f"Aumento {format_money(change)}% oltre il limite configurato."
        if self.max_decrease_percent is not None and -change > self.max_decrease_percent:
            return f"Diminuzione {format_money(-change)}% oltre il limite configurato."
        return None

    def process(self, progress: Callable[[int, RunStats], None] | None = None) -> list[RowOutcome]:
        outcomes: list[RowOutcome] = []
        release_column = self.inventory.columns["release_id"]
        condition_column = self.inventory.columns["media_condition"]
        price_column = self.inventory.columns["price"]
        for number, source in enumerate(self.inventory.rows, start=1):
            row = source.copy()
            old_price = row[price_column]
            old_value = parse_money(old_price)
            if not self._safe_status(row):
                outcome = RowOutcome(row, "SKIPPED_STATUS", "Stato diverso da For Sale.", old_price=old_price, new_price=old_price, old_value=old_value)
                self.stats.skipped_status += 1
            else:
                release_id = row[release_column].strip()
                condition = row[condition_column].strip()
                if not valid_release_id(release_id):
                    outcome = RowOutcome(row, "INVALID_RELEASE_ID", "release_id mancante o non valido.", old_price=old_price, new_price=old_price, old_value=old_value)
                    self.stats.invalid_release_id += 1
                elif condition not in VALID_CONDITIONS:
                    outcome = RowOutcome(row, "INVALID_CONDITION", "media_condition non riconosciuta.", old_price=old_price, new_price=old_price, old_value=old_value)
                    self.stats.invalid_condition += 1
                else:
                    try:
                        suggestions = self._suggestions(release_id).suggestions
                    except DiscogsApiError as error:
                        outcome = RowOutcome(row, "API_ERROR", str(error), old_price=old_price, new_price=old_price, old_value=old_value)
                        self.stats.api_error += 1
                    else:
                        suggested = suggestions.get(condition)
                        if not isinstance(suggested, dict) or "value" not in suggested:
                            outcome = RowOutcome(row, "NO_SUGGESTION", "Nessun suggerimento per questa condizione.", old_price=old_price, new_price=old_price, old_value=old_value)
                            self.stats.no_suggestion += 1
                        else:
                            try:
                                new_value = money(suggested["value"])
                            except (InvalidOperation, ValueError):
                                outcome = RowOutcome(row, "NO_SUGGESTION", "Suggerimento Discogs senza valore valido.", old_price=old_price, new_price=old_price, old_value=old_value)
                                self.stats.no_suggestion += 1
                            else:
                                currency = str(suggested.get("currency", ""))
                                limit_message = self._exceeds_limits(old_value, new_value)
                                if limit_message:
                                    outcome = RowOutcome(row, "UNCHANGED", limit_message, old_price=old_price, new_price=old_price, currency=currency, old_value=old_value, new_value=old_value)
                                    self.stats.unchanged += 1
                                else:
                                    new_price = format_money(new_value)
                                    row[price_column] = new_price
                                    result = "UNCHANGED" if old_value == new_value else "UPDATED"
                                    outcome = RowOutcome(row, result, "", old_price=old_price, new_price=new_price, currency=currency, old_value=old_value, new_value=new_value)
                                    if result == "UPDATED":
                                        self.stats.updated += 1
                                    else:
                                        self.stats.unchanged += 1
                                if currency:
                                    self.stats.currencies.add(currency)
            outcomes.append(outcome)
            if progress:
                progress(number, self.stats)
        return outcomes


def report_row(outcome: RowOutcome, inventory: CsvInventory) -> dict[str, str]:
    row = outcome.row
    get = lambda key: row.get(inventory.columns.get(key, ""), "")
    difference = ""
    percent = ""
    if outcome.old_value is not None and outcome.new_value is not None:
        delta = outcome.new_value - outcome.old_value
        difference = format_money(delta)
        if outcome.old_value != 0:
            percent = format_money(delta / outcome.old_value * Decimal("100"))
    return {
        "listing_id": get("listing_id"), "release_id": get("release_id"), "artist": get("artist"),
        "title": get("title"), "media_condition": get("media_condition"),
        "old_price": outcome.old_price,
        "new_price": outcome.new_price or "", "difference": difference,
        "difference_percent": percent, "currency": outcome.currency, "result": outcome.result,
        "message": outcome.message,
    }
