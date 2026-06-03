# Looplink Mini-Offer-Engine

A promotion evaluation engine with a REST API, server-rendered dashboards, and Docker-based deployment. Designed for deterministic offer stacking, idempotent transaction ingestion, and a full sticker economy (earn → burn → redeem).

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for:
- Project structure and layer diagram
- Offer evaluation flow (sequence diagram, evaluation order)
- Key design decisions and trade-offs (idempotency, extensibility, sticker economy)
- Scalability considerations (caching, Celery/Redis async, horizontal scaling)

---

## Quick Start with Docker

```sh
docker compose -p looplink up --build -d && \
docker compose -p looplink exec web python manage.py migrate && \
docker compose -p looplink --profile dev up -d webpack
```

Visit [http://localhost:8000](http://localhost:8000).

```sh
docker compose -p looplink down
```

### Development Mode

Source code is mounted for hot-reload by default. For automatic frontend rebuilding:

```sh
docker compose -p looplink --profile dev up -d webpack
```

Rebuild the image after adding Python or npm dependencies:

```sh
docker compose -p looplink build --no-cache web
```

---

## Quick Tour

| Endpoint | Description |
|---|---|
| `POST /api/transactions/` | Ingest a purchase; returns applied offers and totals |
| `GET /api/stats/` | System-wide statistics (discounts, stickers, redemptions) |
| `GET /api/shoppers/<id>/` | Shopper profile, balance, transaction history, redemptions |
| `POST /api/shoppers/redeem/` | Redeem stickers for a reward |
| `/shoppers/` | Shopper search portal (HTMX) |
| `/stats/` | Operations dashboard |
| `/debug/tx/<id>/` | Transaction trace (applied + non-applied offers) |

---

## API Example

```sh
curl -X POST http://localhost:8000/api/transactions/ \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "TX001",
    "shopper_id": "SHOPPER1",
    "store_id": "STORE1",
    "timestamp": "2026-06-03T10:00:00Z",
    "items": [
      {"sku": "SKU-MILK", "name": "Milk", "quantity": 2, "unit_price": 3.50, "category": "dairy"},
      {"sku": "SKU-CHEESE", "name": "Cheese", "quantity": 1, "unit_price": 5.00, "category": "dairy"},
      {"sku": "SKU-ORGANIC", "name": "Organic Apple", "quantity": 3, "unit_price": 1.50, "category": "produce"}
    ]
  }'
```

---

## Running Tests

```sh
pytest -v
```

---

## Offer Types

| Type | Description |
|---|---|
| `PRODUCT_PERCENT_DISCOUNT` | Percentage off matching SKUs |
| `BOGO` | Buy One Get One (cheapest units free) |
| `CART_FIXED_DISCOUNT` | Fixed $ off when basket meets threshold |
| `STICKER_BURN` | Convert shopper's sticker balance to $ discount |
| `STICKER_EARN` | Award stickers per $10 spent |
| `STICKER_CAMPAIGN` | Time/store-limited sticker bonuses |

Offers are evaluated in the order above. See [ARCHITECTURE.md](ARCHITECTURE.md#offer-evaluation-order) for stacking details.

---

## Local Development (without Docker)

See [Dev Environment Setup](#dev-environment-setup) below for `uv`-based setup.

---

## Dev Environment Setup

### Prerequisites

- Python 3.13+
- Node.js 22+
- [uv](https://docs.astral.sh/uv/)
- Docker (for PostgreSQL and Redis)

### Setup

```sh
uv venv && source .venv/bin/activate
uv sync --compile-bytecode
inv setup-dev-env
./manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000).

---

## Linting & Formatting

```sh
ruff check .          # Python linting
ruff format --check . # Python formatting
eslint .              # JavaScript linting
```
