# Looplink Mini Offer Engine — Tech Notes

Welcome to the technical overview of my submission! I've structured this document to make it as easy as possible to run, test, and understand the core design decisions.

---

## 🚀 Quick Start & Example Commands

All API endpoints are available on `http://localhost:8000`. You can test them directly using `curl`.

### 1. Ingest a Transaction
Submit a purchase and let the offer engine process it.
```bash
curl -X POST http://localhost:8000/api/transactions/ \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "tx-1001",
    "shopper_id": "shopper-123",
    "store_id": "store-001",
    "timestamp": "2026-06-02T10:00:00Z",
    "items": [
      {"sku": "SKU-MILK", "name": "Whole Milk", "quantity": 2, "unit_price": "3.50", "category": "dairy"}
    ]
  }'
```

### 2. Check Shopper Status
View a shopper's transaction history and current sticker balance.
```bash
curl http://localhost:8000/api/shoppers/shopper-123/
```

### 3. Redeem Stickers
Redeem a shopper's stickers for a reward (e.g., `MUG` costs 10 stickers).
```bash
curl -X POST http://localhost:8000/api/shoppers/redeem/ \
  -H "Content-Type: application/json" \
  -d '{
    "shopper_id": "shopper-123",
    "reward_id": "MUG"
  }'
```

### 4. View System Stats ("The Analyst")
See global statistics across all stores, offers, and transactions.
```bash
curl http://localhost:8000/api/stats/
```

### 5. Web Portals
If you prefer a UI over the terminal, open these in your browser:
* **Shopper Portal:** `http://localhost:8000/shoppers/`
* **System Stats:** `http://localhost:8000/stats/`
* **Debug view:** `http://localhost:8000/debug/tx/<transaction_id>/`

---

## 🧪 Running Tests ("The Tester")

The test suite runs entirely in-memory using SQLite, meaning no Docker or Postgres is required to verify the logic.

```bash
# Run all tests using the dedicated test settings
python -m pytest --ds=looplink.project.test_settings
```

---

## 🏗️ Core Design Decisions

### 1. Engine as a Pure Function
The offer engine (`engine.evaluate(transaction, offers) -> EngineOutput`) has **zero side effects**. It does not call the database and performs no file I/O. 
* **Why?** It makes it trivially easy to unit-test and reason about. All database persistence happens strictly at the view layer *after* the engine is finished.

### 2. Offers as Static Config
Promotions usually change on campaign cycles (days/weeks), not per-request. 
* **Implementation:** A JSON file (`offers/fixtures/offers.json`) is loaded once at process startup and cached. This is simpler and much faster than hitting the database for a heavily read evaluation pattern.

### 3. Smart Offer Stacking ("The Offer Engineer")
All applicable offers stack by default, but there are guardrails to prevent >100% discounts and "bleeding":
* **Ledger-Based Pricing:** Product and BOGO offers evaluate against an in-memory ledger. When a discount applies, it proportionately reduces the `unit_price` of the affected items. Subsequent offers evaluate against the *discounted* value.
* **Cart Thresholds:** `CART_FIXED_DISCOUNT` evaluates against the `current_total` (the post-product-discount subtotal), ensuring thresholds are only met *after* earlier discounts.
* **Discount Caps:** `PRODUCT_PERCENT_DISCOUNT` is strictly capped at the item's total cost.

### 4. BOGO Definition
"Buy 1, Get 1 Free" — for quantity `q`, pay for `ceil(q/2)` and get `floor(q/2)` free.
* **How it works:** The engine sorts matching units by `unit_price` and gives the cheapest `floor(q/2)` units for free. The discount is then spread proportionately across the item lines so subsequent offers stack correctly.

### 5. Sticker Logic ("The Mathlete")
* **Earn Basis:** Stickers are calculated against the **pre-discount** basket total. This ensures shopper rewards remain predictable and aren't penalized if they use a discount.
* **Campaign Deduplication:** If multiple sticker campaigns overlap, the base earning is deduplicated so shoppers get exactly one instance of the highest base plus any bonuses.

---

## 🛡️ Database & Concurrency

### Idempotency
Ingestion is completely idempotent. If a duplicate `transaction_id` is submitted:
1. The stored result is returned immediately with `HTTP 200`.
2. An `idempotent: true` flag is added to the response.
3. No reprocessing or double-counting occurs.

### Safe Sticker Balances ("The Loyalty Whisperer")
`ShopperProfile.sticker_balance` is a denormalized counter:
* **Earning:** Updated atomically using Django's `F()` expressions on every transaction ingest to avoid race conditions. Profile creation is wrapped in a nested `transaction.atomic()` savepoint with `IntegrityError` retries for robust concurrent creation.
* **Redeeming:** Uses `select_for_update()` to lock the shopper row during redemption, preventing negative balances from simultaneous requests.

---

## 🕵️ Transaction Tracing

Every transaction creates a fully traceable record:

* **Debug View:** The debug page (`/debug/tx/<transaction_id>/`) compares the transaction's applied offers against the full catalog, showing you exactly which offers fired and which did not.
