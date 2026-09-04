#!/usr/bin/env python3
"""Command-line entry point for Discogs Auto Pricer."""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

# Running `python discogs_pricer.py` from a source checkout needs no installation.
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from discogs_auto_pricer.api import DiscogsApiError, DiscogsClient  # noqa: E402
from discogs_auto_pricer.cache import PriceCache  # noqa: E402
from discogs_auto_pricer.csv_handler import CsvValidationError, read_inventory, write_inventory, write_report  # noqa: E402
from discogs_auto_pricer.pricing import PriceEngine, canonical_condition, report_row, valid_release_id  # noqa: E402


def percent(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("Inserire un numero percentuale valido.") from error
    if not result.is_finite() or result < 0:
        raise argparse.ArgumentTypeError("La percentuale non può essere negativa.")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ricalcola i prezzi di un CSV Marketplace Discogs tramite l'API ufficiale."
    )
    parser.add_argument("inventory", type=Path, help="CSV esportato dall'inventario Marketplace Discogs")
    parser.add_argument("--output", type=Path, default=Path("output/inventory_repriced.csv"), help="CSV sicuro per l'importazione (default: output/inventory_repriced.csv)")
    parser.add_argument("--dry-run", action="store_true", help="Valida e prova una richiesta, senza produrre CSV")
    parser.add_argument("--no-cache", action="store_true", help="Ignora e non salva la cache persistente")
    parser.add_argument("--refresh-cache", action="store_true", help="Ignora la cache esistente e la aggiorna")
    parser.add_argument("--max-increase-percent", type=percent, help="Non applica aumenti oltre questa percentuale")
    parser.add_argument("--max-decrease-percent", type=percent, help="Non applica diminuzioni oltre questa percentuale")
    return parser.parse_args()


def token_or_error() -> str | None:
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("DISCOGS_TOKEN", "").strip()
    if token:
        return token
    print("DISCOGS_TOKEN non configurato.\n\nCrea un file .env nella directory del progetto:\n\nDISCOGS_TOKEN=xxxxxxxxxxxxxxxx\n\nIl token può essere generato dal proprio account Discogs.", file=sys.stderr)
    return None


def show_preview(path: Path, rows: int, unique: int) -> None:
    print(f"File: {path}\nRighe trovate: {rows}\nRelease uniche: {unique}\nValuta prezzi: determinata dalle API Discogs\n")


def main() -> int:
    args = parse_args()
    try:
        inventory = read_inventory(args.inventory)
    except CsvValidationError as error:
        print(f"Errore CSV: {error}", file=sys.stderr)
        return 2

    release_column = inventory.columns["release_id"]
    condition_column = inventory.columns["media_condition"]
    unique = {row[release_column].strip() for row in inventory.rows if valid_release_id(row[release_column])}
    show_preview(args.inventory, len(inventory.rows), len(unique))
    token = token_or_error()
    if token is None:
        return 2

    client = DiscogsClient(token)
    if args.dry_run:
        candidate = next(
            (row[release_column].strip() for row in inventory.rows
             if valid_release_id(row[release_column]) and canonical_condition(row[condition_column]) is not None),
            None,
        )
        if candidate:
            try:
                suggestions = client.get_price_suggestions(candidate)
            except DiscogsApiError as error:
                print(f"Dry-run: richiesta di prova fallita: {error}", file=sys.stderr)
                return 1
            print(f"Dry-run completato: richiesta API di prova riuscita per release {candidate} ({len(suggestions)} condizioni).")
        else:
            print("Dry-run completato: nessuna riga valida disponibile per una richiesta API di prova.")
        print("Nessun CSV è stato generato.")
        return 0

    cache = PriceCache(PROJECT_ROOT / ".cache/price_suggestions.json", enabled=not args.no_cache, refresh=args.refresh_cache)
    engine = PriceEngine(
        inventory, client.get_price_suggestions, cache,
        max_increase_percent=args.max_increase_percent,
        max_decrease_percent=args.max_decrease_percent,
    )
    last_printed = 0

    def progress(current: int, stats: object) -> None:
        nonlocal last_printed
        if current == len(inventory.rows) or current - last_printed >= 25:
            last_printed = current
            print(f"Analisi inventario: {current} / {len(inventory.rows)} | Release API uniche: {engine.stats.unique_api_requests} | Cache hits: {engine.stats.cache_hits}", end="\r", flush=True)

    outcomes = engine.process(progress)
    print()
    output = args.output
    full_output = output.parent / "inventory_repriced_full.csv"
    report_output = output.parent / "report.csv"
    full_rows = [outcome.row for outcome in outcomes]
    status_column = inventory.columns.get("status")
    safe_rows = [
        outcome.row for outcome in outcomes
        if status_column is None or outcome.row[status_column].strip().casefold() == "for sale"
    ]
    write_inventory(output, inventory, safe_rows)
    write_inventory(full_output, inventory, full_rows)
    write_report(report_output, [report_row(outcome, inventory) for outcome in outcomes])

    stats = engine.stats
    currency = ", ".join(sorted(stats.currencies)) or "non determinata"
    print("=" * 30)
    print("Discogs Auto Pricer\n" + "=" * 30)
    print(f"\nRighe lette:              {stats.rows_read}")
    print(f"Righe aggiornate:          {stats.updated}")
    print(f"Prezzo già corretto:       {stats.unchanged}")
    print(f"Senza suggerimento:        {stats.no_suggestion}")
    print(f"Errori API:                {stats.api_error}")
    print(f"Condizioni non valide:     {stats.invalid_condition}")
    print(f"Release ID non validi:     {stats.invalid_release_id}")
    print(f"Saltate per stato:         {stats.skipped_status}")
    print(f"\nRelease uniche richieste: {stats.unique_api_requests}")
    print(f"Risposte dalla cache:       {stats.cache_hits}")
    print(f"Valuta suggerimenti: {currency}")
    print(f"\nCSV generato:\n{output}\n\nCSV completo:\n{full_output}\n\nReport:\n{report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
