# il-capitalista

A Python script for repricing a Discogs inventory CSV. It looks up price suggestions for each record's media condition and writes a new CSV plus a report. It does not change your live listings.

[Guida in italiano](docs/README.it.md)

## Setup

Requires Python 3.11+ and a Discogs personal access token with access to price suggestions.

```sh
git clone https://github.com/Il-Mazu/il-capitalista.git
cd il-capitalista
python -m venv .venv
```

Activate the environment with `source .venv/bin/activate` on Linux/macOS or `.venv\Scripts\activate` on Windows, then:

```sh
pip install -r requirements.txt
cp .env.example .env
```

Set `DISCOGS_TOKEN` in `.env`. On Windows, you can copy `.env.example` through File Explorer. The token file is ignored by Git.

## Use

First check the CSV and make one test API request:

```sh
python discogs_pricer.py inventory.csv --dry-run
```

Then generate the output:

```sh
python discogs_pricer.py inventory.csv
```

| File | Contents |
| --- | --- |
| `output/inventory_repriced.csv` | Rows ready to review for import; only `For Sale` rows when the input has a status column |
| `output/inventory_repriced_full.csv` | All rows, including drafts |
| `output/report.csv` | Old prices, suggestions, changes, and errors; do not import this file |

Keep the original export and review the report before importing. In Discogs, choose the option to **update existing listings**, not add new listings.

## Options

```sh
python discogs_pricer.py inventory.csv --max-increase-percent 50 --max-decrease-percent 50
python discogs_pricer.py inventory.csv --output output/repriced.csv
python discogs_pricer.py inventory.csv --refresh-cache
```

Percentage limits skip changes above your threshold. `--no-cache` bypasses the persistent cache. `--include-drafts` prices draft rows without prompting, but they remain excluded from the importable CSV.

Missing suggestions, invalid rows, and API errors keep the original price. Prices use media condition, not sleeve condition. Requests are sequential, cached by release, and retried with backoff for transient errors and rate limits.

See the [Italian guide](docs/README.it.md) for CSV handling, import instructions, cache behavior, and API limits.

## Tests

```sh
pytest
```
