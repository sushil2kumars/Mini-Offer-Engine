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
  │                        │  Load shopper balance  │                      │
  │                        │  (for sticker burn)    │                      │
  │                        ├──────────────────────────────────────────────►│
  │                        │◄──── shopper_balance ──┤                      │
  │                        │                        │                      │
  │                        │  Load offers           │                      │
  │                        │  (from JSON fixture)   │                      │
  │                        │  cached via            │                      │
  │                        │  @functools.cache      │                      │
  │                        │                        │                      │
  │                        │  evaluate(tx, offers,  │                      │
  │                        │    shopper_balance)    │                      │
  │                        ├──────────────────────►│                      │
  │                        │                        │                      │
  │                        │  For each offer type   │                      │
  │                        │  (in evaluation order):│                      │
  │                        │                        │                      │
  │                        │  1. PRODUCT_PERCENT    │                      │
  │                        │     Apply % discount   │                      │
  │                        │                        │                      │
  │                        │  2. BOGO               │                      │
  │                        │     Free units on      │                      │
  │                        │                        │                      │
  │                        │  3. CART_FIXED         │                      │
  │                        │     Fixed $ off if     │                      │
  │                        │     basket above       │                      │
  │                        │     threshold          │                      │
  │                        │                        │                      │
  │                        │  4. STICKER_BURN       │                      │
  │                        │     Convert stickers   │                      │
  │                        │     → $ discount       │                      │
  │                        │                        │                      │
  │                        │  5. STICKER_EARN       │                      │
  │                        │     Base sticker       │                      │
  │                        │     award per $10      │                      │
  │                        │                        │                      │
  │                        │  6. STICKER_CAMPAIGN   │                      │
  │                        │     Bonus stickers     │                      │
  │                        │     per weekday/store  │                      │
  │                        │                        │                      │
  │                        │◄────EngineOutput───────┤                      │
  │                        │                        │                      │
  │                        │  Persist results       │                      │
  │                        ├──────────────────────────────────────────────►│
  │                        │  - Transaction row     │                      │
  │                        │  - AppliedOffer rows   │                      │
  │                        │  - Shopper.balance     │                      │
  │                        │    += earned - burned  │                      │
  │                        │                        │                      │
  │◄────────────────────────┤                        │                      │
  │  201 Created /          │                        │                      │
  │  applied offers +       │                        │                      │
  │  final totals           │                        │                      │
```

### Offer Evaluation Order

Offers are evaluated in a fixed order to ensure deterministic stacking:

```
PRODUCT_PERCENT_DISCOUNT  →  BOGO  →  CART_FIXED_DISCOUNT  →  STICKER_BURN  →  STICKER_EARN  →  STICKER_CAMPAIGN
      │                        │              │                    │               │                   │
      │                        │              │                    │               │                   │
      ▼                        ▼              ▼                    ▼               ▼                   ▼
  Mutates items          Mutates items    Reads running       Reads running  Reads original      Reads original
  (unit_price ↓)         (unit_price ↓)   total for          total +        basket total         basket total
                                            threshold check   shopper
                                                              balance
```

- Monetary offers (1-4) stack against the basket, each reducing the running total.
- Product-level offers (1-2) mutate the item's `unit_price` in-place so subsequent offers apply to the already-discounted value.
- `CART_FIXED_DISCOUNT` evaluates against the running total *after* product-level discounts.
- `STICKER_BURN` converts the shopper's pre-existing sticker balance into a monetary discount, evaluated against the running total after cart-level discounts.
- Sticker offers (5-6) always evaluate against the *pre-discount* `basket_total` so rewards are predictable regardless of which monetary offers applied.
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

## Trade-offs

### Idempotency Strategy

| Approach | Trade-off |
|---|---|
| **Current: application-level dedup** on `transaction_id` via `Transaction.objects.filter(...).first()` before processing | No DB uniqueness constraint enforcement at the API layer — two concurrent requests for the same `transaction_id` could both pass the check. The `unique` constraint on `transaction_id` catches the second writer via `IntegrityError`, which triggers a retry path. |
| **Alternative: DB-unique + early return** | Slightly slower happy path (always attempts INSERT), but eliminates the race window entirely. |

The current split-check approach is chosen for latency: the read is cheap and avoids a write attempt for the common case (first submission). The `IntegrityError` fallback in `_persist_transaction` ensures correctness under contention.

### Pure Engine vs. I/O-coupled Logic

| Decision | Benefit | Cost |
|---|---|---|
| **Engine is pure** (`engine.py` has no DB or network calls) | Trivially testable; reusable from Celery tasks, management commands, REPL | Cannot access shopper balance or historical data without the caller passing it in |
| **Offer catalogue as JSON fixture** | Zero database load on evaluation; startup-time cache via `@functools.cache` | Cannot update offers without a deployment/restart; no per-offer targeting rules |
| **Items mutated in-place** for stacking | Simple, predictable evaluation order; no need for a complex rule engine | Offer interactions are implicit (order-dependent); adding new offer types requires careful placement in `EVALUATION_ORDER` |

### Extensibility

Adding a new offer type requires:
1. Add a constant to `OfferType`
2. Add it to `EVALUATION_ORDER`
3. Write an `apply_*` function
4. Add a dispatch branch in `_evaluate_offer`
5. (Optional) Add a fixture entry and integration tests

No interfaces or abstract base classes are used — the engine relies on duck-typing and a flat dispatch chain. For ~10 offer types this is pragmatic; beyond that, consider a plugin registry or strategy pattern.

### Sticker Economy: Earn vs. Burn

The `STICKER_BURN` offer type closes the sticker economy loop — shoppers earn stickers on purchases and can burn them at checkout for a monetary discount. Key trade-offs:

| Decision | Rationale |
|---|---|
| **Burn evaluated against pre-earn balance** | Shoppers cannot spend stickers they earn in the same transaction, preventing circular dependency |
| **Burn discount capped by `current_total`** | Basket never goes negative, consistent with other monetary offers |
| **Sticker earn always based on pre-discount `basket_total`** | Rewards are predictable regardless of sticker-burn discount amount |
| **Balance deduction happens in the same DB transaction** | Atomicity: if the discount is applied, the stickers are burned; partial failure cannot leave the system inconsistent |

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
