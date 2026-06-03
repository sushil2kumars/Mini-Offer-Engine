# Technical Notes

## Trade-offs

### Offer Storage: JSON Fixture vs. Database Table

**Chosen: Static JSON fixture loaded via `functools.cache`.**

| Concern | Trade-off |
|---|---|
| **Latency** | Zero database queries on every ingest; one disk read at process start. |
| **Mutability** | Changing offers requires a deployment/restart. No hot-reload without process restart. |
| **Targeting** | No per-shopper or per-cohort offer targeting — all offers apply to all transactions. |
| **Audit trail** | Offer definitions live in version control (git), providing a natural change log. |
| **Scaling** | Multiple web workers each hold their own in-memory copy (one per process). Acceptable for <100 offers. |

A database-backed offer table would enable admin CRUD, hot-reload, per-shopper targeting, and dynamic activation schedules — at the cost of a DB round-trip on every ingest (mitigable via Redis caching). The JSON fixture was chosen because the brief specified static offers and the latency benefit is meaningful at this scale.

### Evaluation Dispatch: Flat Chain vs. Strategy Pattern

**Chosen: `if/elif` dispatch in `_evaluate_offer` with `EVALUATION_ORDER` tuple.**

For six offer types this is pragmatic and readable. A strategy pattern (registry of `OfferProcessor` classes each implementing an `apply()` method) would be warranted when:
- The number of types exceeds ~12-15.
- Third-party plugins need to register types dynamically.
- Each type needs its own configuration schema validation.

The flat chain keeps all evaluation logic in one file (487 lines total for `engine.py`) and makes the evaluation order explicit.

### Sticker Balance: Denormalized Field vs. Event-Sourced Ledger

**Chosen: Single `IntegerField` on `ShopperProfile`, updated atomically via `F()` expressions.**

| Approach | Benefit | Cost |
|---|---|---|
| **Denormalized field** (chosen) | Simple reads; no sum queries; atomic `F()` updates avoid races | No history of balance changes; hard to debug drift |
| **Event-sourced ledger** | Every earn/burn/redeem is an immutable row; replayable to reconstruct balance | Complex; slower reads; requires periodic compaction |

The denormalized approach is correct for concurrent access because `F()` expressions are atomic at the database level (`UPDATE ... SET balance = balance + N`). A ledger would be useful for auditing and debugging but was out of scope.

### API Layer: `@api_view` Decorators vs. ViewSets

**Chosen: Functional `@api_view` decorators, not DRF ViewSets.**

ViewSets provide automatic route generation, browsable API, and serializer integration — but add indirection. The ingest endpoint has enough custom logic (idempotency check, engine dispatch, error handling, serialization) that a ViewSet would require overriding most defaults anyway. The decorator style keeps the request-response cycle explicit and readable.

### Synchronous Ingest vs. Async (Celery)

**Chosen: Synchronous blocking ingest.**

See the Async Processing proposal in ARCHITECTURE.md for the full analysis. The synchronous path keeps deployment simple (no worker pool, no queue) and is the right choice until ingest latency or throughput becomes a bottleneck.

### Monetary Precision: Python `Decimal` Throughout

Money is represented as Python `Decimal` with two-place quantization at every output boundary. The `_to_decimal` helper converts raw input (float, int, string) before any arithmetic. This avoids float drift in discounts, totals, and percentages. The cost is verbosity — every value must be explicitly converted — but correctness with money justifies it.

### Docker Bind Mount for Development

The Docker Compose `web` service mounts the host project directory at `/app` with anonymous volumes overlaying `.venv`, `node_modules`, `staticfiles`, and `bundled_assets`. This means:
- Source code changes are reflected immediately (Django's dev server auto-reloads).
- Virtual environment and installed packages are **not** overwritten by the mount — the build-time `uv sync` results survive.
- Static file artifacts from `collectstatic` and webpack builds survive.

The overlay approach was chosen over copying files into the image for development speed, at the cost of slightly more complex Docker Compose configuration.

---

## Assumptions

These are the implicit design decisions made during development. If any of these assumptions is wrong, the corresponding architecture area needs re-evaluation.

### Domain

| Assumption | Implication |
|---|---|
| **Offer types are known at compile time** | No plugin system; adding a type requires code changes in 5 locations (see ARCHITECTURE.md Extensibility). |
| **SKU matching is exact string equality** | No glob, regex, or category-tree matching. An offer for "dairy" applies to "SKU-MILK" only if explicitly listed. |
| **Basket sizes are small (<100 items)** | SKU matching is a linear scan; acceptable for typical retail transactions. |
| **Single currency** | All monetary values are dimensionless. Adding multi-currency requires plumbing a currency field through the entire stack. |
| **No negative prices or free items** | The engine does not handle negative `unit_price` or 100%-off scenarios beyond what BOGO produces. |
| **`shopper_id` is a string with no FK constraint on Transaction** | Orphan transactions are possible. Shoppers are created lazily on first transaction. |
| **`store_id` and `timestamp` are optional** | Campaign offers that gate on these silently skip when absent. |
| **No PII in transaction data** | Transaction `items` contain SKU, name, price, category — no customer personal data. No encryption or masking needed at rest. |

### Scale

| Assumption | Implication |
|---|---|
| **TPS is low (<50 req/s)** | Synchronous blocking ingest is fine. Single gunicorn worker handles the load. |
| **Active offer count is small (<100)** | `functools.cache` per-process memory overhead is negligible. |
| **Sticker balance fits in a 32-bit signed int** | `IntegerField` max is ~2.1B. At 1 sticker per $10, a shopper would need $21B in spending to overflow. Safe for any real deployment. |
| **All web workers run in the same timezone (UTC)** | Campaign weekday checks use the server timezone. Multi-region deployments need timezone-aware campaign scheduling. |
| **Idempotency keys (`transaction_id`) are never recycled** | No TTL or expiry on stored transactions. The `Transaction` table grows monotonically. Archival/partitioning would be needed for multi-billion-row tables. |

### Infrastructure

| Assumption | Implication |
|---|---|
| **PostgreSQL is the only database** | Raw SQL expressions (`F()`, `select_for_update()`) are portable, but any migration to MySQL or SQLite would need testing. |
| **Docker on Linux (WSL) or Docker Desktop** | Dockerfile is Linux-only; no Windows container support. |
| **Single-region, single-AZ deployment** | No read replicas, no cross-region replication. Database is a single point of failure. |
| **No authentication required for API** | `AllowAny` permission class on all endpoints. Adding auth means changing one setting and adding a decorator or middleware, but all current clients will break. |
| **HTMX + server-rendered HTML suffices for dashboards** | No SPA framework. The dashboard is driven by Django templates, HTMX partial swaps, and Alpine.js. Interactive BI-style dashboards would need a heavier frontend. |

---

## How I Would Scale and Enhance with Additional Time

### Phase 1: Operational Readiness (Days 1-2)

1. **Structured logging** — Replace ad-hoc `logger.info` calls in `views.py` with structured logging (JSON output via `python-json-logger`). Include `transaction_id`, `shopper_id`, latency, and evaluation result as structured fields for log aggregation (ELK, Datadog, etc.).

2. **Health check endpoint** — Add `GET /health/` returning DB connectivity, Redis ping, and last-offer-load timestamp. Essential for load balancer probes and container orchestrators.

3. **Prometheus metrics** — Export counters for: transactions ingested, offers applied (by type), sticker burns, sticker earnings, idempotency hits, and latency histograms (p50/p95/p99 for `evaluate()` and full ingest). Use `django-prometheus` or manual `prometheus_client` instrumentation.

4. **Rate limiting** — Apply `django-ratelimit` or DRF throttling on the ingest endpoint to protect against bursts and abuse. Allowlist internal health checks.

### Phase 2: Offer Management (Days 3-5)

1. **Database-backed offers** — Migrate from `offers.json` to an `Offer` model with an admin CRUD interface. Add an `is_active` flag, `starts_at`/`ends_at` datetime fields, and a `priority` integer for evaluation ordering.

2. **Offer validation** — Add a JSON Schema validator for each offer type's `details` field so invalid configurations are rejected at save time, not at evaluation time.

3. **Offer history / audit log** — Use `django-simple-history` or a custom `OfferVersion` model to track every change to an offer definition (who changed what, when).

4. **Hot-reload cache invalidation** — When an offer is saved via admin, publish a Redis pub/sub message. Workers subscribe and clear their `functools.cache`. This avoids process restarts for offer changes.

5. **Simulation/sandbox endpoint** — `POST /api/offers/simulate/` that runs the evaluation engine against arbitrary offer configurations without persisting results. Useful for merchants testing "what if" scenarios.

### Phase 3: Async Processing & Throughput (Days 6-10)

1. **Celery integration** — Add Celery with Redis as broker. The ingest endpoint persists the transaction as `status="pending"`, enqueues a task, and returns `202 Accepted`. A polling endpoint (`GET /api/transactions/<id>/`) lets clients retrieve results. See ARCHITECTURE.md for the sequence diagram.

2. **Background worker pool** — Run 2-4 Celery workers, each sharing the same `functools.cache` limitation (or migrate to Redis cache for offers — see Phase 2).

3. **Database connection pooling** — Use `pgbouncer` or Django's built-in `CONN_MAX_AGE` to reduce connection churn from async workers.

4. **Batch ingest endpoint** — `POST /api/transactions/batch/` accepting up to 100 transactions. Validates all, persists all, enqueues a single Celery task chain. Returns 202 with batch ID.

### Phase 4: Observability & Testing (Days 11-14)

1. **Distributed tracing** — Instrument the ingest path with OpenTelemetry spans: serializer validation, idempotency check, offer loading, engine evaluation, persistence. Trace context propagates to Celery tasks and database queries.

2. **Load testing** — Write a `locustfile.py` simulating realistic traffic patterns (mix of SKUs, varying basket sizes, concurrent duplicate submissions). Establish baseline and regression benchmarks.

3. **Fuzz testing** — Use `hypothesis` to generate random transaction payloads and offer configurations, verifying that the engine never throws an unhandled exception and monetary invariants hold (no negative totals, discounts don't exceed basket, etc.).

4. **Integration test suite** — Spin up the full Docker stack (web + db + redis), run a series of curl commands against the live API, and assert responses. This catches issues that unit tests miss (serialization drift, database migration problems, etc.).

5. **Chaos testing** — Inject failures (database connection drops, Redis unavailability, slow disk) and verify the system degrades gracefully (returns 503, retries, doesn't corrupt data).

### Phase 5: Advanced Features (Weeks 3-4)

1. **Multi-currency support** — Add a `currency` field to Transaction and Offer. The engine converts all monetary values to a canonical currency for evaluation, then converts back. Requires an exchange rate provider (static or API-based).

2. **Stackable offer groups** — Replace linear `EVALUATION_ORDER` with a directed acyclic graph (DAG) of offer groups. Each group can be "best of N" (e.g., apply the single best product discount) while still stacking with cart-level offers. This allows "20% off milk" and "$1 off milk" to be mutually exclusive (shopper gets whichever is better) while still stacking with "$5 off $50".

3. **Offer targeting rules** — Add a JSON-based rule DSL for per-shopper targeting:
   ```json
   {
     "type": "STICKER_CAMPAIGN",
     "targeting": {
       "shopper_segments": ["vip", "new"],
       "max_redemptions_per_shopper": 3,
       "exclude_skus": ["SKU-TOBACCO"]
     }
   }
   ```

4. **Sticker campaign scheduler** — A Django management command (`./manage.py apply_campaigns`) or Celery beat task that evaluates time-based campaigns (flash sales, happy hour) and pre-computes eligibility.

5. **Webhook notifications** — On transaction completion, fire webhooks to registered URLs with the evaluation result. Useful for downstream analytics, loyalty systems, and real-time dashboards.

6. **API versioning** — Prefix all endpoints with `/v1/` (e.g., `/v1/transactions/`). Use DRF's versioning classes or URL namespace versioning. The unversioned routes redirect or return a deprecation header.

7. **OpenAPI schema** — Generate OpenAPI 3.0 docs using `drf-spectacular`. Add schema annotations to every endpoint and serializer. Serve via Swagger UI at `/docs/`.

### Phase 6: Platform Hardening (Weeks 5-6)

1. **Multi-tenant isolation** — Add a `tenant_id` column to every domain model. All queries are scoped by tenant. Offer configurations become per-tenant. The engine accepts a `tenant_id` parameter.

2. **Read replicas** — Configure Django's database router to send dashboard queries (stats, shopper history) to PostgreSQL read replicas. The ingest endpoint always writes to the primary.

3. **Database partitioning** — Partition the `Transaction` and `AppliedOffer` tables by month (range partitioning on `timestamp`). Old partitions can be detached and archived without impacting active data.

4. **Idempotency key rotation** — Add a configurable TTL (e.g., 24 hours) on idempotency. After TTL, a duplicate `transaction_id` is treated as a new transaction. Requires a background job to purge or archive old keys.

5. **Secret management** — Move secrets (database password, Redis password, SECRET_KEY) from `.env` to a vault (HashiCorp Vault, AWS Secrets Manager, or Docker Secrets). The `.env` file stores only non-sensitive configuration.

### Phase 7: Performance Optimization (Ongoing)

1. **Offer pre-filtering** — Before entering the evaluation loop, filter the offer list to only those whose conditions could possibly match the current transaction (e.g., `STICKER_CAMPAIGN` offers for different stores are skipped).

2. **SKU pre-indexing** — For large baskets, build a `defaultdict(list)` index of items by SKU so product-level offers (`PRODUCT_PERCENT_DISCOUNT`, `BOGO`) find matching items in O(1) instead of O(N).

3. **Cached aggregation for stats** — Cache `transaction_stats()` result in Redis with a 30-second TTL. Invalidate on every successful ingest (or accept staleness for dashboard pages).

4. **Connection pooling for parallelism** — If the engine is parallelized (e.g., offer groups evaluated concurrently via `concurrent.futures`), reuse database connections across threads to avoid connection storms.

---

## Design Verification Checklist

Before considering any Phase complete, verify:

- [ ] All existing unit tests pass (currently 92/92).
- [ ] No new warnings from `ruff check .` and `ruff format --check .`.
- [ ] Docker compose build succeeds cleanly.
- [ ] Smoke test: ingest a transaction, verify applied offers match expectation.
- [ ] Idempotency test: re-submit the same `transaction_id`, verify `200 OK` with `idempotent: true`.
- [ ] Sticker economy test: earn stickers via purchase, verify balance, burn via STICKER_BURN, verify deduction, redeem remainder via `/api/shoppers/redeem/`.
- [ ] Campaign test: submit transaction on a Wednesday from STORE1, verify campaign stickers applied.
- [ ] Error case: submit invalid payload, verify 400 response with serializer errors.
