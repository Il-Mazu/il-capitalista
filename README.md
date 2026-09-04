# Discogs Auto Pricer

Strumento locale che aggiorna il campo `price` di un CSV Marketplace Discogs usando esclusivamente i suggerimenti dell'API ufficiale Discogs, scelti in base a `media_condition` (mai `sleeve_condition`). Non modifica il CSV originale né invia modifiche dirette a Discogs.

> **Prima di ogni importazione massiva, controlla attentamente `output/report.csv` e conserva il backup del CSV originale.** I suggerimenti Discogs possono non essere appropriati per ogni copia o mercato.

## Installazione

```bash
git clone <URL-del-repository>
cd discogs-auto-pricer
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Poi:

```bash
pip install -r requirements.txt
```

## Configurazione

```bash
cp .env.example .env
```

Inserisci il Personal Access Token Discogs nel file `.env`:

```text
DISCOGS_TOKEN=...
```

Il token non viene mai stampato, e `.env` è escluso da Git. L'endpoint dei suggerimenti richiede un account con impostazioni venditore configurate; i prezzi ricevuti sono nella valuta di vendita dell'account Discogs. Il riferimento ufficiale è la [documentazione Marketplace Price Suggestions](https://www.discogs.com/developers/#page:marketplace,header:marketplace-price-suggestions).

## Utilizzo

```bash
python discogs_pricer.py inventory.csv
```

Oppure scegli il file importabile:

```bash
python discogs_pricer.py inventory.csv --output output/mio_inventory.csv
```

Verifica CSV, token e una singola richiesta API senza scrivere output:

```bash
python discogs_pricer.py inventory.csv --dry-run
```

Opzioni di sicurezza facoltative (non attive per default):

```bash
python discogs_pricer.py inventory.csv --max-increase-percent 50 --max-decrease-percent 50
```

La cache persistente è `.cache/price_suggestions.json`; evita richieste duplicate anche fra esecuzioni. Per ignorarla una volta, usa `--no-cache`; per rifarla usa `--refresh-cache`.

## Output

Il programma conserva tutte le colonne, l'ordine delle colonne, i commenti quotati/multilinea e i valori non legati al prezzo. Riconosce sia le etichette leggibili delle condizioni sia gli enum che l'export Marketplace usa attualmente (per esempio `VERY_GOOD_PLUS`), traducendoli solo per cercare la chiave corrispondente nella risposta API.

- `output/inventory_repriced.csv`: file **consigliato per l'importazione**. Se l'input ha `status`, contiene solo righe `For Sale`; le altre sono escluse e segnalate nel report.
- `output/inventory_repriced_full.csv`: copia completa con tutte le righe. Le righe con stato diverso da `For Sale` non vengono rivalutate.
- `output/report.csv`: diagnostica separata, non importare su Discogs. Include prezzi vecchi/nuovi, differenze, valuta e risultato.

Una riga senza suggerimento, con `media_condition` non valida, `release_id` non valido o errore API mantiene il suo prezzo originale. Ogni riga valida viene rivalutata anche se `price` era già compilato. I valori API sono formattati con due decimali e arrotondamento monetario `ROUND_HALF_UP`.

## Importazione Discogs

1. Fai sempre il backup del CSV originale.
2. Apri l'Inventario Marketplace in Discogs.
3. Scegli **Importa CSV / Bulk Upload**.
4. Scegli la funzione per **AGGIORNARE/MODIFICARE annunci esistenti**.
5. **Non scegliere “Aggiungi”**: potrebbe creare annunci nuovi.
6. Carica `output/inventory_repriced.csv`.
7. Controlla il risultato dell'importazione mostrato da Discogs.

## API e limiti

Le richieste sono sequenziali. Il client usa il token personale, un `User-Agent`, timeout, massimo cinque tentativi con exponential backoff per timeout/rete, HTTP 429 e 5xx, e rispetta `Retry-After` e `X-Discogs-Ratelimit-Remaining` quando presenti. Una release duplicata comporta una sola richiesta e la risposta viene riusata.

L'API può restituire un oggetto vuoto o non avere un valore per una condizione; in questi casi controlla il report e il prezzo non cambia. Discogs può anche cambiare rate limit, disponibilità o suggerimenti: riesegui con `--refresh-cache` solo quando desideri dati nuovi.

## Sviluppo

```bash
pytest
```
