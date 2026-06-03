# Architecture

## Project Structure

```
looplink/
├── django_ext/          # Shared Django utilities
│   ├── htmx/            # HTMX action dispatch layer
│   ├── middleware/       # Custom middleware
│   └── templatetags/    # Custom template tags (webpack/common helpers)
├── offers/              # Promotion evaluation engine (pure logic)
│   ├── engine.py        # Core evaluation functions
│   ├── config.py        # Offer catalogue loader (cached from JSON)
│   └── fixtures/        # Offer definitions as static JSON
├── project/             # Django project configuration
│   ├── settings.py      # Global settings (DB, cache, apps)
│   ├── urls.py          # Root URL routing
│   └── wsgi.py          # WSGI entrypoint
├── shoppers/            # Shopper domain (DRF API)
│   ├── models.py        # ShopperProfile, StickerRedemption
│   ├── serializers.py   # Input validation for redemptions
│   ├── views.py         # API endpoints (detail, redeem)
│   └── urls.py          # API route definitions
├── transactions/        # Transaction domain (DRF API)
│   ├── models.py        # Transaction, AppliedOffer
│   ├── serializers.py   # Input validation for ingestion
│   ├── views.py         # API endpoints (ingest, stats)
│   └── urls.py          # API route definitions
└── ui/                  # Server-rendered template views
    ├── base/            # Landing page, HTMX demo, transaction trace
    ├── shoppers/        # Shopper search and detail portal
    └── stats/           # System-wide statistics dashboard
```

## Layers

```
┌──────────────────────────────────────────────────┐
│                  UI Layer                         │
│  TemplateView (Django templates + HTMX + Alpine)  │
│  looplink/ui/*/views.py                          │
├──────────────────────────────────────────────────┤
│                  API Layer                        │
│  DRF @api_view decorators                        │
│  looplink/{shoppers,transactions}/views.py       │
├──────────────────────────────────────────────────┤
│              Business Logic                       │
│  Pure evaluation engine (no I/O)                 │
│  looplink/offers/engine.py                       │
├──────────────────────────────────────────────────┤
│              Data Layer                           │
│  Django ORM models + PostgreSQL                  │
│  looplink/*/models.py                            │
└──────────────────────────────────────────────────┘
```

## Offer Evaluation Flow

### Ingestion Sequence

```
Client                    API                     Engine                 Database
  │                        │                        │                      │
  │  POST /api/transactions/                       │                      │
  │────────────────────►    │                        │                      │
  │                        │  Idempotency check     │                      │
  │                        │  (transaction_id)      │                      │
  │                        ├───────Exist?──────────►│                      │
  │                        │◄──────Return cached────┤                      │
  │                        │                        │                      │
  │                        │  Load offers           │                      │
  │                        │  (from JSON fixture)   │                      │
  │                        │  cached via            │                      │
  │                        │  @functools.cache      │                      │
  │                        │                        │                      │
  │                        │  evaluate(tx, offers)  │                      │
  │                        ├──────────────────────►│                      │
  │                        │                        │                      │
  │                        │  For each offer type   │                      │
  │                        │  (in evaluation order):│                      │
  │                        │                        │                      │
  │                        │  1. PRODUCT_PERCENT    │                      │
  │                        │     Apply % discount   │                      │
  │                        │     to matching SKUs   │                      │
  │                        │                        │                      │
  │                        │  2. BOGO               │                      │
  │                        │     Free units on      │                      │
  │                        │     matching SKU       │                      │
  │                        │                        │                      │
  │                        │  3. CART_FIXED         │                      │
  │                        │     Fixed $ off if     │                      │
  │                        │     basket above       │                      │
  │                        │     threshold          │                      │
  │                        │                        │                      │
  │                        │  4. STICKER_EARN       │                      │
  │                        │     Base sticker       │                      │
  │                        │     award per $10      │                      │
  │                        │                        │                      │
  │                        │  5. STICKER_CAMPAIGN   │                      │
  │                        │     Bonus stickers     │                      │
  │                        │     per weekday/store  │                      │
  │                        │                        │                      │
  │                        │◄────EngineOutput───────┤                      │
  │                        │                        │                      │
  │                        │  Persist results       │                      │
  │                        ├──────────────────────────────────────────────►│
  │                        │  - Transaction row     │                      │
  │                        │  - AppliedOffer rows   │                      │
  │                        │  - Shopper.sticker_    │                      │
  │                        │    balance += earned   │                      │
  │                        │                        │                      │
  │◄────────────────────────┤                        │                      │
  │  201 Created /          │                        │                      │
  │  applied offers +       │                        │                      │
  │  final totals           │                        │                      │
```

### Offer Evaluation Order

Offers are evaluated in a fixed order to ensure deterministic stacking:

```
PRODUCT_PERCENT_DISCOUNT  →  BOGO  →  CART_FIXED_DISCOUNT  →  STICKER_EARN  →  STICKER_CAMPAIGN
      │                        │              │                    │                   │
      │                        │              │                    │                   │
      ▼                        ▼              ▼                    ▼                   ▼
  Mutates items          Mutates items    Reads running       Reads original      Reads original
  (unit_price ↓)         (unit_price ↓)   total for          basket total         basket total
                                           threshold check
```

- Monetary offers (1-3) stack against the basket, each reducing the running total.
- Product-level offers (1-2) mutate the item's `unit_price` in-place so subsequent offers apply to the already-discounted value.
- `CART_FIXED_DISCOUNT` evaluates against the running total *after* product-level discounts.
- Sticker offers (4-5) always evaluate against the *pre-discount* `basket_total` so rewards are predictable regardless of which monetary offers applied.
- Campaign base earnings (`STICKER_CAMPAIGN`) are deduplicated against the standard `STICKER_EARN` base to avoid double-counting.

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Pure evaluation engine** (`engine.py` has no I/O) | Unit-testable in isolation, reusable from any context (API, batch, simulation) |
| **Offers as static JSON fixture** | No database query on every request; loaded once at startup via `@functools.cache` |
| **Idempotent ingestion** | Duplicate `transaction_id` submissions return the stored result without re-processing |
| **Atomic sticker balance** | `F()` expressions ensure atomic balance updates; redemption additionally uses `select_for_update()` to prevent concurrent double-spend |
| **Campaign base deduplication** | `_deduplicate_campaign_base()` removes redundant base earnings that overlap with standard `STICKER_EARN` |
| **Deep copy of items** | Input transaction is never mutated; items are deep-copied and modifications only affect the working copy |

## URL Routing

```
/                           →  Landing page (ui.base)
/api/transactions/          →  POST: ingest transaction
/api/stats/                 →  GET:  system-wide statistics
/api/shoppers/<id>/         →  GET:  shopper profile + history
/api/shoppers/redeem/       →  POST: redeem stickers
/shoppers/                  →  UI:   shopper search
/shoppers/<id>/             →  UI:   shopper detail
/stats/                     →  UI:   statistics dashboard
/debug/tx/<id>/             →  UI:   transaction trace
```

## Scalability Considerations

### Caching

| Layer | Cache Strategy | Notes |
|---|---|---|
| **Offer catalogue** | `@functools.cache` in `config.py` | Loaded once per process; restart to pick up changes |
| **Django cache** | Redis (via `django-redis`) | Configured in `settings.py`; used for sessions by default |
| **Database query cache** | Not currently used | Could add `cacheops` or manual `cache.set()` for expensive aggregations |

**Recommended improvements:**
- Cache `transaction_stats()` and `StatsView` aggregations with a short TTL (e.g., 60s) to reduce database load on dashboard pages.
- Use Redis for rate-limiting the ingest endpoint to protect against bursts.

### Async Processing with Celery/Redis

The current ingest flow is synchronous — the client waits for offer evaluation and persistence to complete. The diagram below is a proposed future design for higher throughput:

```
Client                     API                    Queue (Redis/Celery)        Worker                   Database
  │                        │                        │                         │                         │
  │  POST /api/transactions/                       │                         │                         │
  │────────────────────►    │                        │                         │                         │
  │                        │  Validate + persist    │                         │                         │
  │                        │  with status="pending" │                         │                         │
  │                        ├──────────────────────────────────────────────────────────────►             │
  │                        │                        │                         │                         │
  │  202 Accepted          │                        │                         │                         │
  │◄────────────────────────┤                        │                         │                         │
  │                        │                        │                         │                         │
  │                        │  Enqueue task          │                         │                         │
  │                        ├──────────────────────►│                         │                         │
  │                        │                        │  Worker picks up task   │                         │
  │                        │                        ├────────────────────────►│                         │
  │                        │                        │                         │                         │
  │                        │                        │  Evaluate offers        │                         │
  │                        │                        │  Update status          │                         │
  │                        │                        │  ="processed"           │                         │
  │                        │                        ├──────────────────────────────────────────────►    │
  │                        │                        │                         │                         │
  │  GET /api/transactions/<id>/                    │                         │                         │
  │────────────────────►    │                        │                         │                         │
  │◄──── status:"processed" │                        │                         │                         │
```

**When to add async processing:**
- Transaction ingest latency exceeds acceptable thresholds (>500ms per request).
- Ingest volume exceeds the web server's worker pool capacity.
- You need to process additional downstream effects (emails, analytics, webhooks) that don't need to block the HTTP response.

**Implementation notes:**
- Add a `status` field on `Transaction` (already exists: `pending` / `processed` / `duplicate`).
- The API persists the transaction as `pending` immediately, enqueues a Celery task, and returns `202 Accepted`.
- The Celery worker calls `evaluate()`, persists results, and flips status to `processed`.
- A polling endpoint such as `GET /api/transactions/<id>/` can be added so clients can retrieve the final result (this endpoint does not exist yet in the current implementation).

### Horizontal Scaling

The web service is stateless (sessions use Redis, static files are collected at build time), so it can scale horizontally behind a load balancer:

```
                       ┌─────────────┐
                       │  Load       │
                       │  Balancer   │
                       └──────┬──────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
         │ Web     │    │ Web     │    │ Web     │
         │  (1)    │    │  (2)    │    │  (N)    │
         └────┬────┘    └────┬────┘    └────┬────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
                    ┌─────────┴─────────┐
                    │     PostgreSQL     │
                    │   (Primary/Replica)│
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │       Redis       │
                    │  (Cache + Session)│
                    └───────────────────┘
```

**Database scaling notes:**
- The `ShopperProfile` table uses `shopper_id` as primary key (no auto-increment), making it suitable for hash-based sharding.
- `Transaction` and `AppliedOffer` are append-only (immutable after creation), which pairs well with read replicas for dashboard queries.
- Add database indexing on `shopper_id` and `store_id` (already present via `db_index=True`) for common query patterns.

### Performance Characteristics of the Engine

The offer evaluation engine operates in `O(N * M)` where `N` = number of line items and `M` = number of active offers. In practice:
- Item list mutation is in-place (no additional allocations per offer).
- SKU matching is a linear scan — acceptable for typical basket sizes (<100 items).
- The entire engine is CPU-bound and typically low-latency for realistic inputs.

For baskets with thousands of line items, consider:
- Pre-indexing items by SKU via `defaultdict(list)`.
- Moving evaluation to a background worker (see Async Processing above).
