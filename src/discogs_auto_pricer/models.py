"""Small, explicit data models used by the application."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class CsvInventory:
    fieldnames: list[str]
    rows: list[dict[str, str]]
    columns: dict[str, str]
    dialect: type


@dataclass(frozen=True)
class ApiResponse:
    suggestions: dict[str, dict[str, Any]]
    from_cache: bool = False


@dataclass
class RowOutcome:
    row: dict[str, str]
    result: str
    message: str = ""
    old_price: str = ""
    new_price: str | None = None
    currency: str = ""
    old_value: Decimal | None = None
    new_value: Decimal | None = None


@dataclass
class RunStats:
    rows_read: int = 0
    updated: int = 0
    unchanged: int = 0
    no_suggestion: int = 0
    invalid_condition: int = 0
    invalid_release_id: int = 0
    api_error: int = 0
    skipped_status: int = 0
    unique_api_requests: int = 0
    cache_hits: int = 0
    currencies: set[str] = field(default_factory=set)
