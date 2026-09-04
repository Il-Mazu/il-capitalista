"""CSV reading and writing without altering the input schema."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import CsvInventory

REQUIRED_COLUMNS = ("release_id", "price", "media_condition")
OPTIONAL_COLUMNS = ("status", "listing_id", "artist", "title")


class CsvValidationError(ValueError):
    """Raised when an input is not a usable Discogs inventory CSV."""


def _normalized(name: str) -> str:
    return "".join(character for character in name.casefold() if character.isalnum())


def detect_columns(fieldnames: list[str]) -> dict[str, str]:
    """Find known Discogs columns while preserving their original spelling."""
    by_normalized = {_normalized(name): name for name in fieldnames}
    aliases = {
        "release_id": ("releaseid",),
        "price": ("price",),
        "media_condition": ("mediacondition",),
        "status": ("status",),
        "listing_id": ("listingid",),
        "artist": ("artist",),
        "title": ("title",),
    }
    found: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        for candidate in candidates:
            if candidate in by_normalized:
                found[canonical] = by_normalized[candidate]
                break
    return found


def read_inventory(path: Path) -> CsvInventory:
    """Read UTF-8 CSV including quoted commas and multiline fields."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            sample = source.read(8192)
            source.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(source, dialect=dialect)
            fieldnames = reader.fieldnames
            if not fieldnames:
                raise CsvValidationError("Il CSV non contiene una riga di intestazione.")
            rows = []
            for row in reader:
                if None in row:
                    raise CsvValidationError("Una riga CSV contiene più campi dell'intestazione.")
                rows.append({name: value if value is not None else "" for name, value in row.items()})
    except UnicodeDecodeError as error:
        raise CsvValidationError("Il file deve essere codificato in UTF-8.") from error
    except OSError as error:
        raise CsvValidationError(f"Impossibile leggere il CSV: {error}") from error

    columns = detect_columns(fieldnames)
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        raise CsvValidationError(
            "Colonne obbligatorie mancanti: " + ", ".join(missing) + ". "
            "Intestazioni trovate: " + ", ".join(fieldnames)
        )
    return CsvInventory(fieldnames=fieldnames, rows=rows, columns=columns, dialect=dialect)


def write_inventory(path: Path, inventory: CsvInventory, rows: list[dict[str, str]]) -> None:
    """Write rows with precisely the original columns and order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=inventory.fieldnames,
            dialect=inventory.dialect,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


REPORT_FIELDS = [
    "listing_id", "release_id", "artist", "title", "media_condition", "old_price",
    "new_price", "difference", "difference_percent", "currency", "result", "message",
]


def write_report(path: Path, report_rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(report_rows)
