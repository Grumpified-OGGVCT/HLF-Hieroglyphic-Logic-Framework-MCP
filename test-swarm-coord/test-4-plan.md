# Test 4: Large-Scale Multi-Agent E-Commerce Marketplace (20 Agents)

## Goal: Validate HLF amortization at 20-agent scale; test Ollama queue saturation (~25 concurrent max)

---

## System Overview

Build a **multi-vendor e-commerce marketplace** API — a system where independent vendors list products, customers browse/search/purchase, and the platform handles cart, orders, payments, shipping, reviews, inventory, and admin analytics.

**Tech Stack:** Node.js + Express + PostgreSQL + Knex.js + JWT Auth  
**Agents:** 20 specialized agents  
**Output:** Working marketplace API with tests, migrations, services, routes, middleware, and config

This is the largest swarm attempted so far. It tests whether HLF’s coordination savings compound (Test 3 showed 58% savings at 15 agents; this test targets the ~67% estimate at 20 agents) and whether Ollama’s 10-parallel + 15-queued capacity becomes a bottleneck.

---

## Agent Roster (20 Agents)

### Layer 1: Foundation (3 agents — parallel, no dependencies)

| # | Agent | Role | Output Files | Downstream Consumers |
|---|-------|------|-------------|---------------------|
| 1 | **SchemaDesigner** | Design PostgreSQL schema for marketplace | `migrations/001_initial_schema.js`, `schema.sql` | Agent 2, 4, 5, 6, 7, and all downstream |
| 2 | **ConfigEngineer** | Project config and package manifest | `package.json`, `knexfile.js`, `.env.example`, `.gitignore` | Agent 20 |
| 3 | **MiddlewareEngineer** | Base middleware stack | `middleware/error.js`, `middleware/logger.js`, `middleware/validate.js`, `middleware/rateLimit.js` | Agents 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20 |

### Layer 2: Core Infrastructure (4 agents — parallel, depends on Layer 1)

| # | Agent | Role | Output Files | Inputs Required |
|---|-------|------|-------------|----------------|
| 4 | **MigrationWriter** | Complete Knex migrations with indexes & FKs | `migrations/002_indexes.js`, `migrations/003_constraints.js` | `schema.sql`, `migrations/001_initial_schema.js` |
| 5 | **AuthService** | JWT authentication & authorization | `services/authService.js`, `middleware/auth.js`, `routes/auth.js` | `schema.sql` (users table) |
| 6 | **VendorService** | Vendor CRUD, onboarding, approval workflow | `services/vendorService.js`, `routes/vendors.js` | `schema.sql` |
| 7 | **CustomerService** | Customer profiles, address book | `services/customerService.js`, `routes/customers.js` | `schema.sql` |

### Layer 3: Product & Discovery (5 agents — parallel, schema-aware)

| # | Agent | Role | Output Files | Key Dependencies |
|---|-------|------|-------------|-----------------|
| 8 | **ProductService** | Products, categories, variants, images | `services/productService.js`, `routes/products.js`, `routes/categories.js` | `schema.sql` (products, categories, variants) |
| 9 | **CartService** | Shopping cart, add/remove, calculations | `services/cartService.js`, `routes/carts.js` | `schema.sql` (carts, cart_items) |
| 10 | **InventoryService** | Stock tracking, reservations, low-stock alerts | `services/inventoryService.js`, `routes/inventory.js` | `schema.sql` (inventory, products) |
| 11 | **CouponService** | Discount codes, rules, validation | `services/couponService.js`, `routes/coupons.js` | `schema.sql` (coupons, coupon_products) |
| 12 | **SearchService** | Full-text product search, filters, facets | `services/searchService.js`, `routes/search.js` | `schema.sql` (products, categories, reviews) |

### Layer 4: Transaction & Fulfillment (5 agents — parallel)

| # | Agent | Role | Output Files | Key Dependencies |
|---|-------|------|-------------|-----------------|
| 13 | **OrderService** | Order lifecycle, status transitions | `services/orderService.js`, `routes/orders.js` | `schema.sql` (orders, order_items), CartService concept |
| 14 | **PaymentService** | Payment processing, refunds, methods | `services/paymentService.js`, `routes/payments.js` | `schema.sql` (payments, orders) |
| 15 | **ShippingService** | Shipping rates, carriers, tracking | `services/shippingService.js`, `routes/shipping.js` | `schema.sql` (shipments, orders, addresses) |
| 16 | **ReviewService** | Ratings, reviews, moderation, helpful votes | `services/reviewService.js`, `routes/reviews.js` | `schema.sql` (reviews, products) |
| 17 | **NotificationService** | Email templates, order notifications, webhooks | `services/notificationService.js`, `routes/notifications.js` | `schema.sql` (notifications, users) |

### Layer 5: Operations (1 agent)

| # | Agent | Role | Output Files | Key Dependencies |
|---|-------|------|-------------|-----------------|
| 18 | **AdminDashboardService** | Admin routes, analytics, moderation tools | `services/adminService.js`, `routes/admin.js`, `middleware/permissions.js` | ALL previous services (reads schema + service shapes) |

### Layer 6: Assembly & Validation (2 agents)

| # | Agent | Role | Output Files | Key Dependencies |
|---|-------|------|-------------|-----------------|
| 19 | **DevOpsAssembler** | Server entry point, route mounting, wiring | `server.js` | ALL routes, services, middleware |
| 20 | **IntegrationTester** | End-to-end integration tests | `tests/marketplace.test.js` | ALL files |

---

## Dependency Graph (Execution DAG)

```
Layer 1:  [SchemaDesigner] [ConfigEngineer] [MiddlewareEngineer]
              ↓                ↓                ↓
Layer 2:  [MigrationWriter] [AuthService] [VendorService] [CustomerService]
              ↓                ↓                ↓                ↓
Layer 3:  [ProductService] [CartService] [InventoryService] [CouponService] [SearchService]
              ↓                ↓                ↓                ↓                ↓
Layer 4:  [OrderService] [PaymentService] [ShippingService] [ReviewService] [NotificationService]
              ↓                ↓                ↓                ↓                ↓
Layer 5:  [AdminDashboardService]
              ↓
Layer 6:  [DevOpsAssembler]
              ↓
Layer 7:  [IntegrationTester]
```

**Note on cross-layer parallelism:** Agents in Layers 3–4 do not strictly need files from each other within the same layer. They read `schema.sql` (produced by Layer 1) to know table shapes, FK relationships, and constraints. This allows high parallelism even with 20 agents.

### Dependency Matrix

| Agent | Blocked By | Blocks |
|-------|-----------|--------|
| SchemaDesigner | — | MigrationWriter, AuthService, VendorService, CustomerService, and all downstream |
| ConfigEngineer | — | DevOpsAssembler |
| MiddlewareEngineer | — | DevOpsAssembler, IntegrationTester |
| MigrationWriter | SchemaDesigner | — |
| AuthService | SchemaDesigner | DevOpsAssembler, IntegrationTester |
| VendorService | SchemaDesigner | DevOpsAssembler, IntegrationTester |
| CustomerService | SchemaDesigner | CartService, OrderService, ShippingService, ReviewService, NotificationService (conceptual) |
| ProductService | SchemaDesigner | CartService, InventoryService, CouponService, SearchService, OrderService, ReviewService (conceptual) |
| CartService | SchemaDesigner | OrderService (conceptual) |
| InventoryService | SchemaDesigner | — |
| CouponService | SchemaDesigner | OrderService (conceptual) |
| SearchService | SchemaDesigner | — |
| OrderService | SchemaDesigner | PaymentService, ShippingService, NotificationService (conceptual) |
| PaymentService | SchemaDesigner | — |
| ShippingService | SchemaDesigner | — |
| ReviewService | SchemaDesigner | — |
| NotificationService | SchemaDesigner | — |
| AdminDashboardService | ALL above | DevOpsAssembler |
| DevOpsAssembler | ALL above | IntegrationTester |
| IntegrationTester | DevOpsAssembler | — |

---

## Database Schema Overview

### Core Tables

```sql
-- Users (shared login for customers, vendors, admins)
users (id PK, email UNIQUE, password_hash, role ENUM('customer','vendor','admin'), created_at, updated_at)

-- Vendors (marketplace sellers)
vendors (id PK, user_id FK→users.id, name, slug UNIQUE, description, logo_url, status ENUM('pending','approved','suspended'), rating DECIMAL(2,1), created_at, updated_at)

-- Customers
customers (id PK, user_id FK→users.id, first_name, last_name, phone, created_at, updated_at)

-- Addresses (shipping/billing)
addresses (id PK, customer_id FK→customers.id, type ENUM('shipping','billing'), street, city, state, zip, country, is_default BOOLEAN, created_at)

-- Categories (hierarchical)
categories (id PK, name, slug UNIQUE, parent_id FK→categories.id NULL, description, created_at)

-- Products
products (id PK, vendor_id FK→vendors.id, category_id FK→categories.id, name, slug UNIQUE, description, price DECIMAL(10,2), compare_at_price DECIMAL(10,2), status ENUM('draft','active','archived'), created_at, updated_at)

-- Product Variants
product_variants (id PK, product_id FK→products.id, sku UNIQUE, variant_name, price_adjustment DECIMAL(10,2), stock_quantity INT, created_at)

-- Inventory (stock tracking with reservations)
inventory (id PK, product_id FK→products.id, variant_id FK→product_variants.id NULL, quantity INT, reserved_quantity INT DEFAULT 0, low_stock_threshold INT DEFAULT 10, updated_at)

-- Carts
carts (id PK, customer_id FK→customers.id NULL, session_id VARCHAR(255), created_at, updated_at)

-- Cart Items
cart_items (id PK, cart_id FK→carts.id, product_id FK→products.id, variant_id FK→product_variants.id NULL, quantity INT, created_at, updated_at)

-- Coupons
coupons (id PK, code VARCHAR(50) UNIQUE, type ENUM('percentage','fixed','free_shipping'), value DECIMAL(10,2), min_order_amount DECIMAL(10,2) DEFAULT 0, max_uses INT, used_count INT DEFAULT 0, expires_at TIMESTAMP, created_at)

-- Coupon-Product Junction
coupon_products (coupon_id FK→coupons.id, product_id FK→products.id, PRIMARY KEY(coupon_id, product_id))

-- Orders
orders (id PK, customer_id FK→customers.id, status ENUM('pending','confirmed','shipped','delivered','cancelled','refunded'), subtotal DECIMAL(10,2), tax DECIMAL(10,2), shipping_cost DECIMAL(10,2), coupon_id FK→coupons.id NULL, coupon_discount DECIMAL(10,2) DEFAULT 0, shipping_address_id FK→addresses.id, total_amount DECIMAL(10,2), created_at, updated_at)

-- Order Items
order_items (id PK, order_id FK→orders.id, product_id FK→products.id, variant_id FK→product_variants.id NULL, quantity INT, unit_price DECIMAL(10,2), total_price DECIMAL(10,2), created_at)

-- Payments
payments (id PK, order_id FK→orders.id, amount DECIMAL(10,2), method ENUM('card','paypal','stripe'), status ENUM('pending','completed','failed','refunded'), transaction_id VARCHAR(255), created_at)

-- Shipments
shipments (id PK, order_id FK→orders.id, carrier VARCHAR(50), tracking_number VARCHAR(100), status ENUM('pending','label_created','in_transit','delivered'), cost DECIMAL(10,2), estimated_delivery DATE, shipped_at TIMESTAMP, delivered_at TIMESTAMP, created_at)

-- Reviews
reviews (id PK, product_id FK→products.id, customer_id FK→customers.id, order_id FK→orders.id, rating INT CHECK(1-5), title VARCHAR(255), content TEXT, status ENUM('pending','approved','rejected'), helpful_count INT DEFAULT 0, created_at, updated_at)

-- Notifications
notifications (id PK, user_id FK→users.id, type ENUM('order_update','promotion','system'), title VARCHAR(255), body TEXT, data JSONB, read BOOLEAN DEFAULT false, created_at)
```

### Indexes
- `products(vendor_id, status)`, `products(category_id)`, `products(search_vector)` (for full-text)
- `orders(customer_id, status)`, `orders(created_at)`
- `reviews(product_id, status, created_at)`
- `inventory(product_id, variant_id)`
- `cart_items(cart_id)`, `order_items(order_id)`
- `notifications(user_id, read, created_at)`

---

## API Contract Summary

### Authentication (`/auth`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /auth/register | No | Register customer or vendor |
| POST | /auth/login | No | Login, return JWT |
| POST | /auth/refresh | No | Refresh access token |
| POST | /auth/logout | Yes | Invalidate token |

### Vendors (`/vendors`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /vendors | No | List approved vendors |
| GET | /vendors/:slug | No | Get vendor profile |
| POST | /vendors | Yes | Register as vendor (pending) |
| PUT | /vendors/:id | Yes | Update vendor profile (own only) |
| GET | /vendors/:id/products | No | List vendor's products |

### Products (`/products`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /products | No | List products (filters: category, vendor, price range, status) |
| GET | /products/:slug | No | Get product with variants |
| POST | /products | Yes | Create product (vendor/admin) |
| PUT | /products/:id | Yes | Update product (vendor/admin) |
| DELETE | /products/:id | Yes | Archive product |
| GET | /categories | No | List categories |
| GET | /categories/:slug/products | No | Products by category |

### Cart (`/cart`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /cart | Yes/Session | Get current cart |
| POST | /cart/items | Yes/Session | Add item to cart |
| PUT | /cart/items/:id | Yes/Session | Update quantity |
| DELETE | /cart/items/:id | Yes/Session | Remove item |
| DELETE | /cart | Yes/Session | Clear cart |

### Orders (`/orders`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /orders | Yes | List customer orders |
| GET | /orders/:id | Yes | Get order details |
| POST | /orders | Yes | Create order from cart |
| PUT | /orders/:id/cancel | Yes | Cancel order (if pending) |

### Payments (`/payments`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /payments/:orderId/process | Yes | Process payment |
| POST | /payments/:orderId/refund | Yes | Request refund (admin) |
| GET | /payments/:id | Yes | Get payment status |

### Shipping (`/shipping`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /shipping/rates | Yes | Calculate shipping rates |
| GET | /orders/:id/tracking | Yes | Get tracking info |
| PUT | /shipments/:id/status | Yes | Update shipment status (admin) |

### Reviews (`/reviews`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /products/:id/reviews | No | List approved reviews |
| POST | /products/:id/reviews | Yes | Write review (after purchase) |
| PUT | /reviews/:id/helpful | No | Mark review helpful |
| PUT | /reviews/:id/moderate | Yes | Approve/reject review (admin) |

### Search (`/search`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /search/products | No | Full-text search with filters & facets |

### Coupons (`/coupons`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /coupons/:code/validate | No | Validate coupon |
| POST | /coupons | Yes | Create coupon (admin) |

### Notifications (`/notifications`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /notifications | Yes | Get user notifications |
| PUT | /notifications/:id/read | Yes | Mark as read |

### Admin (`/admin`)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /admin/analytics | Yes (admin) | Sales, orders, vendors stats |
| GET | /admin/vendors/pending | Yes (admin) | Pending vendor approvals |
| PUT | /admin/vendors/:id/approve | Yes (admin) | Approve vendor |
| GET | /admin/reviews/pending | Yes (admin) | Pending review moderation |
| GET | /admin/inventory/low-stock | Yes (admin) | Low stock alerts |

---

## Success Criteria

1. **Completeness:** All 20 agents produce output files assigned to them.
2. **Structural correctness:** `npm start` can boot the Express server without syntax errors.
3. **API coverage:** All route modules mount correctly and handle expected HTTP methods.
4. **No cross-agent type mismatches (HLF):** Interfaces declare shapes; no agent produces incompatible exports.
5. **Traceability:** Every file can be traced to the agent that wrote it.
6. **Tests:** IntegrationTester produces tests covering auth, products, cart, orders, payments, reviews, and admin endpoints.
7. **Schema integrity:** Migrations define all tables with proper FKs, indexes, and constraints.
8. **Ollama queue behavior documented:** Record whether queuing delays occurred at 20-agent scale.

---

## Why This Tests HLF's Value at 20 Agents

1. **Interface count:** 20 agents × avg 3 consumers = ~60 interface boundaries
2. **NL coordination cost:** Each agent needs 2–5 paragraphs describing dependencies in prose; scales linearly with agent count
3. **HLF coordination cost:** Fixed interface declarations (~4,000 tokens for swarm.hlf); per-agent marginal cost near-zero
4. **Amortization hypothesis:** At 20 agents, HLF should show ~60–70% token savings vs NL (extrapolated from 58% at 15 agents)
5. **Execution stress test:** 20 agents approach Ollama's ~25 concurrent ceiling; tests whether queue saturation impacts completion time

---

## Risk Mitigation

- **If an agent fails:** Document in BUGS.md, retry once, and if still failing, assign its work to a sibling agent or the DevOpsAssembler.
- **If Ollama queue saturates:** Reduce Layer 3–4 parallelism by splitting into sub-batches (e.g., run 3 agents, then 2 agents).
- **If dependencies are circular:** The DAG above has no cycles; all commerce services are schema-aware, not file-dependent, within layers.
- **If tests fail:** Attribute failures to specific agent outputs and trace via effect annotations in HLF version.
- **If schema changes mid-build:** SchemaDesigner is Layer 1; all downstream agents read schema.sql. If schema must change, restart from Layer 1.

---

## Project Structure

```
test-4-marketplace/
├── package.json
├── .env.example
├── .gitignore
├── knexfile.js
├── server.js
├── schema.sql
├── migrations/
│   ├── 001_initial_schema.js
│   ├── 002_indexes.js
│   └── 003_constraints.js
├── services/
│   ├── authService.js
│   ├── vendorService.js
│   ├── customerService.js
│   ├── productService.js
│   ├── cartService.js
│   ├── inventoryService.js
│   ├── couponService.js
│   ├── searchService.js
│   ├── orderService.js
│   ├── paymentService.js
│   ├── shippingService.js
│   ├── reviewService.js
│   ├── notificationService.js
│   └── adminService.js
├── routes/
│   ├── auth.js
│   ├── vendors.js
│   ├── customers.js
│   ├── products.js
│   ├── categories.js
│   ├── carts.js
│   ├── inventory.js
│   ├── coupons.js
│   ├── search.js
│   ├── orders.js
│   ├── payments.js
│   ├── shipping.js
│   ├── reviews.js
│   ├── notifications.js
│   └── admin.js
├── middleware/
│   ├── auth.js
│   ├── error.js
│   ├── logger.js
│   ├── permissions.js
│   ├── rateLimit.js
│   └── validate.js
└── tests/
    └── marketplace.test.js
```

---

## Execution Strategy Summary

| Layer | Agents | Max Parallel | Est. Time |
|-------|--------|-------------|-----------|
| 1 | SchemaDesigner, ConfigEngineer, MiddlewareEngineer | 3 | ~2 min |
| 2 | MigrationWriter, AuthService, VendorService, CustomerService | 4 | ~3 min |
| 3 | ProductService, CartService, InventoryService, CouponService, SearchService | 5 | ~4 min |
| 4 | OrderService, PaymentService, ShippingService, ReviewService, NotificationService | 5 | ~4 min |
| 5 | AdminDashboardService | 1 | ~2 min |
| 6 | DevOpsAssembler | 1 | ~2 min |
| 7 | IntegrationTester | 1 | ~3 min |
| **Total** | **20** | **peak 5** | **~20 min (HLF)** |

**Ollama queue management:** With peak 5 concurrent agents, well under the 10-parallel limit. Even if agents occasionally overlap between layers, total concurrent stays well under 10. The 15-queue buffer is not expected to saturate. If needed, Layers 3 and 4 can be merged into a single 10-agent wave (still under limit).

**Parallelism optimization:** Because Layers 3 and 4 agents are primarily schema-aware (reading `schema.sql` rather than each other's files), they can theoretically be launched together as a 10-agent wave. This would reduce total layers from 7 to 5 and cut execution time by ~30%.
