# Natural Language Swarm: 20-Agent E-Commerce Marketplace

## Task: Build a Complete Multi-Vendor E-Commerce Marketplace API

**Tech Stack:** Node.js + Express + PostgreSQL + Knex.js + JWT  
**Goal:** Working marketplace API with vendor management, product catalog, shopping cart, orders, payments, shipping, reviews, search, inventory tracking, coupons, notifications, and an admin dashboard.

---

## Critical Rules
1. Every agent MUST read `schema.sql` (and any other files they depend on) before writing.
2. Every agent MUST write to their assigned files only.
3. If you find a bug in another agent's code, document it in `BUGS.md` and work around it.
4. Use CommonJS (`require` / `module.exports`) for compatibility.
5. Do NOT run `npm install` — just write the code.
6. All services MUST export a factory function: `(knex, helpers) => { ... }`.
7. All routes MUST export a factory function: `(services, auth, middleware) => Express.Router`.

---

## Agent Instructions

### Agent 1: SchemaDesigner
Design the PostgreSQL schema for a multi-vendor e-commerce marketplace.

**Tables:**
- `users` (id PK, email UNIQUE, password_hash, role ENUM('customer','vendor','admin'), created_at, updated_at)
- `vendors` (id PK, user_id FK→users.id, name, slug UNIQUE, description, logo_url, status ENUM('pending','approved','suspended'), rating DECIMAL(2,1), created_at, updated_at)
- `customers` (id PK, user_id FK→users.id, first_name, last_name, phone, created_at, updated_at)
- `addresses` (id PK, customer_id FK→customers.id, type ENUM('shipping','billing'), street, city, state, zip, country, is_default BOOLEAN, created_at)
- `categories` (id PK, name, slug UNIQUE, parent_id FK→categories.id NULL, description, created_at)
- `products` (id PK, vendor_id FK→vendors.id, category_id FK→categories.id, name, slug UNIQUE, description, price DECIMAL(10,2), compare_at_price DECIMAL(10,2), status ENUM('draft','active','archived'), created_at, updated_at)
- `product_variants` (id PK, product_id FK→products.id, sku UNIQUE, variant_name, price_adjustment DECIMAL(10,2), stock_quantity INT, created_at)
- `inventory` (id PK, product_id FK→products.id, variant_id FK→product_variants.id NULL, quantity INT, reserved_quantity INT DEFAULT 0, low_stock_threshold INT DEFAULT 10, updated_at)
- `carts` (id PK, customer_id FK→customers.id NULL, session_id VARCHAR(255), created_at, updated_at)
- `cart_items` (id PK, cart_id FK→carts.id, product_id FK→products.id, variant_id FK→product_variants.id NULL, quantity INT, created_at, updated_at)
- `coupons` (id PK, code VARCHAR(50) UNIQUE, type ENUM('percentage','fixed','free_shipping'), value DECIMAL(10,2), min_order_amount DECIMAL(10,2) DEFAULT 0, max_uses INT, used_count INT DEFAULT 0, expires_at TIMESTAMP, created_at)
- `coupon_products` (coupon_id FK→coupons.id, product_id FK→products.id, PRIMARY KEY(coupon_id, product_id))
- `orders` (id PK, customer_id FK→customers.id, status ENUM('pending','confirmed','shipped','delivered','cancelled','refunded'), subtotal DECIMAL(10,2), tax DECIMAL(10,2), shipping_cost DECIMAL(10,2), coupon_id FK→coupons.id NULL, coupon_discount DECIMAL(10,2) DEFAULT 0, shipping_address_id FK→addresses.id, total_amount DECIMAL(10,2), created_at, updated_at)
- `order_items` (id PK, order_id FK→orders.id, product_id FK→products.id, variant_id FK→product_variants.id NULL, quantity INT, unit_price DECIMAL(10,2), total_price DECIMAL(10,2), created_at)
- `payments` (id PK, order_id FK→orders.id, amount DECIMAL(10,2), method ENUM('card','paypal','stripe'), status ENUM('pending','completed','failed','refunded'), transaction_id VARCHAR(255), created_at)
- `shipments` (id PK, order_id FK→orders.id, carrier VARCHAR(50), tracking_number VARCHAR(100), status ENUM('pending','label_created','in_transit','delivered'), cost DECIMAL(10,2), estimated_delivery DATE, shipped_at TIMESTAMP, delivered_at TIMESTAMP, created_at)
- `reviews` (id PK, product_id FK→products.id, customer_id FK→customers.id, order_id FK→orders.id, rating INT CHECK(1-5), title VARCHAR(255), content TEXT, status ENUM('pending','approved','rejected'), helpful_count INT DEFAULT 0, created_at, updated_at)
- `notifications` (id PK, user_id FK→users.id, type ENUM('order_update','promotion','system'), title VARCHAR(255), body TEXT, data JSONB, read BOOLEAN DEFAULT false, created_at)

**Write:** `migrations/001_initial_schema.js` (Knex migration), `schema.sql` (plain SQL reference)

---

### Agent 2: ConfigEngineer
Create project configuration files.

**Write:**
- `package.json` — dependencies: express, knex, pg, bcryptjs, jsonwebtoken, express-validator, dotenv, helmet, cors, compression, morgan, supertest, jest
- `knexfile.js` — development config using pg
- `.env.example` — all required env vars (DB_URL, JWT_SECRET, PORT, etc.)
- `.gitignore` — standard Node.js ignores

---

### Agent 3: MiddlewareEngineer
Build the base middleware stack.

**Write:**
- `middleware/error.js` — centralized error handler returning JSON `{ error, status, timestamp }`; handles 400, 401, 403, 404, 500
- `middleware/logger.js` — request logging middleware using morgan format
- `middleware/validate.js` — request validation helper using express-validator patterns
- `middleware/rateLimit.js` — simple in-memory rate limiter (requests per window per IP)

---

### Agent 4: MigrationWriter
Write additional migrations for indexes and constraints.

**Input:** `schema.sql`, `migrations/001_initial_schema.js`
**Write:**
- `migrations/002_indexes.js` — indexes on products(vendor_id, status), products(category_id), orders(customer_id, status), reviews(product_id, status), inventory(product_id, variant_id), cart_items(cart_id), order_items(order_id), notifications(user_id, read)
- `migrations/003_constraints.js` — check constraints (e.g., rating 1-5, prices >= 0)

---

### Agent 5: AuthService
Build JWT authentication and authorization.

**Input:** `schema.sql` (users table)
**Write:**
- `services/authService.js` — register, login, refresh, logout, verify; bcrypt password hashing; role-aware JWT payload
- `middleware/auth.js` — `authenticate` middleware (verify JWT from Authorization header), `optionalAuth` middleware, `requireRole(roles)` middleware
- `routes/auth.js` — POST /auth/register, POST /auth/login, POST /auth/refresh, POST /auth/logout

---

### Agent 6: VendorService
Build vendor management.

**Input:** `schema.sql`
**Write:**
- `services/vendorService.js` — create (pending status), update (own profile only), list (approved only), get by slug, approve/suspend (admin), calculate average rating
- `routes/vendors.js` — GET /vendors, GET /vendors/:slug, POST /vendors (auth), PUT /vendors/:id (auth, own), GET /vendors/:id/products

---

### Agent 7: CustomerService
Build customer profiles and address book.

**Input:** `schema.sql`
**Write:**
- `services/customerService.js` — create profile, update profile, get by user_id, manage addresses (add, update, delete, set default), list addresses
- `routes/customers.js` — GET /customers/me (auth), PUT /customers/me (auth), GET /customers/me/addresses (auth), POST /customers/me/addresses (auth), PUT /customers/me/addresses/:id (auth), DELETE /customers/me/addresses/:id (auth)

---

### Agent 8: ProductService
Build product catalog with categories and variants.

**Input:** `schema.sql`
**Write:**
- `services/productService.js` — create (vendor only), update (vendor/admin), list with filters (category, vendor, price range, status), get by slug with variants, archive, search within vendor catalog
- `routes/products.js` — GET /products, GET /products/:slug, POST /products (auth, vendor), PUT /products/:id (auth, vendor/admin), DELETE /products/:id (auth, vendor/admin)
- `routes/categories.js` — GET /categories, GET /categories/:slug/products

---

### Agent 9: CartService
Build shopping cart logic.

**Input:** `schema.sql`
**Write:**
- `services/cartService.js` — get or create cart (by customer_id or session_id), add item (check product availability), update quantity, remove item, clear cart, calculate totals
- `routes/carts.js` — GET /cart, POST /cart/items, PUT /cart/items/:id, DELETE /cart/items/:id, DELETE /cart

---

### Agent 10: InventoryService
Build stock tracking and reservations.

**Input:** `schema.sql`
**Write:**
- `services/inventoryService.js` — track stock for products and variants, reserve stock (for carts/orders), release reservation, adjust stock, check availability, low-stock alert query
- `routes/inventory.js` — GET /inventory/products/:id (stock level), PUT /inventory/products/:id (admin stock adjust), GET /inventory/low-stock (admin)

---

### Agent 11: CouponService
Build discount codes.

**Input:** `schema.sql`
**Write:**
- `services/couponService.js` — create coupon (admin), validate coupon (check code, expiry, usage limits, applicability to products), apply discount calculation, increment used_count
- `routes/coupons.js` — POST /coupons (admin), GET /coupons/:code/validate, GET /coupons (admin list)

---

### Agent 12: SearchService
Build full-text product search.

**Input:** `schema.sql`
**Write:**
- `services/searchService.js` — full-text search on products (name, description), filters (category, vendor, price min/max, rating), facets (category counts, price ranges), sorting (relevance, price, rating), pagination
- `routes/search.js` — GET /search/products?q=&category=&vendor=&minPrice=&maxPrice=&sort=&page=&limit=

---

### Agent 13: OrderService
Build order lifecycle management.

**Input:** `schema.sql`
**Write:**
- `services/orderService.js` — create order from cart (calculate subtotal, tax, shipping, apply coupon), get order by id, list customer orders, update status (confirmed, shipped, delivered, cancelled, refunded), validate status transitions
- `routes/orders.js` — GET /orders (auth), GET /orders/:id (auth), POST /orders (auth), PUT /orders/:id/cancel (auth)

---

### Agent 14: PaymentService
Build payment processing.

**Input:** `schema.sql`
**Write:**
- `services/paymentService.js` — process payment (mock/stub integration), record payment, get payment status, process refund, validate payment amount matches order
- `routes/payments.js` — POST /payments/:orderId/process (auth), POST /payments/:orderId/refund (auth, admin), GET /payments/:id (auth)

---

### Agent 15: ShippingService
Build shipping and tracking.

**Input:** `schema.sql`
**Write:**
- `services/shippingService.js` — calculate shipping rates (mock carriers), create shipment, update tracking status, get tracking info, estimate delivery
- `routes/shipping.js` — POST /shipping/rates (auth), GET /orders/:id/tracking (auth), PUT /shipments/:id/status (auth, admin)

---

### Agent 16: ReviewService
Build ratings and reviews.

**Input:** `schema.sql`
**Write:**
- `services/reviewService.js` — create review (must have purchased product), update review, list approved reviews for product, moderate review (approve/reject admin), mark helpful, calculate average rating
- `routes/reviews.js` — GET /products/:id/reviews, POST /products/:id/reviews (auth), PUT /reviews/:id/helpful, PUT /reviews/:id/moderate (auth, admin)

---

### Agent 17: NotificationService
Build notification system.

**Input:** `schema.sql`
**Write:**
- `services/notificationService.js` — create notification, get user notifications, mark as read, mark all read, get unread count, delete old notifications
- `routes/notifications.js` — GET /notifications (auth), PUT /notifications/:id/read (auth), PUT /notifications/read-all (auth)

---

### Agent 18: AdminDashboardService
Build admin routes and analytics.

**Input:** ALL previous services' routes and `schema.sql`
**Write:**
- `services/adminService.js` — sales analytics (total revenue, orders by status, top products), vendor management (pending approvals), review moderation queue, low-stock summary
- `routes/admin.js` — GET /admin/analytics (admin), GET /admin/vendors/pending (admin), PUT /admin/vendors/:id/approve (admin), GET /admin/reviews/pending (admin), GET /admin/inventory/low-stock (admin)
- `middleware/permissions.js` — `requireAdmin`, `requireVendor` middleware

---

### Agent 19: DevOpsAssembler
Create the server entry point and wire everything together.

**Input:** ALL routes, services, middleware files
**Write:**
- `server.js` — Express app, register all routes at correct paths, apply middleware in order (CORS, helmet, compression, logger, rate limit, body parsing, auth optional, routes, error handler last)
- Ensure routes are mounted: /auth, /vendors, /customers, /products, /categories, /cart, /inventory, /coupons, /search, /orders, /payments, /shipping, /reviews, /notifications, /admin

---

### Agent 20: IntegrationTester
Write end-to-end integration tests.

**Input:** ALL files produced by other agents
**Write:**
- `tests/marketplace.test.js` — comprehensive tests using supertest + jest
- **Must test:**
  - Auth: register, login, access protected route
  - Products: CRUD, listing with filters
  - Cart: add item, update quantity, remove, clear
  - Orders: create from cart, cancel
  - Payments: process payment, check status
  - Reviews: create review, list reviews, helpful vote
  - Admin: analytics endpoint (admin-only), vendor approval
  - Search: full-text search with filters
  - Coupons: validate coupon
- **Use:** supertest + jest, mock Knex or use in-memory SQLite adapter if possible

---

## Execution Order

1. **Layer 1 (parallel):** Agent 1 (SchemaDesigner), Agent 2 (ConfigEngineer), Agent 3 (MiddlewareEngineer)
2. **Layer 2 (parallel):** Agent 4 (MigrationWriter), Agent 5 (AuthService), Agent 6 (VendorService), Agent 7 (CustomerService)
3. **Layer 3 (parallel):** Agent 8 (ProductService), Agent 9 (CartService), Agent 10 (InventoryService), Agent 11 (CouponService), Agent 12 (SearchService)
4. **Layer 4 (parallel):** Agent 13 (OrderService), Agent 14 (PaymentService), Agent 15 (ShippingService), Agent 16 (ReviewService), Agent 17 (NotificationService)
5. **Layer 5:** Agent 18 (AdminDashboardService)
6. **Layer 6:** Agent 19 (DevOpsAssembler)
7. **Layer 7:** Agent 20 (IntegrationTester)

**Note:** Agents within Layers 3 and 4 are primarily schema-aware (they read `schema.sql`). They do not strictly need files from each other. This allows 5-agent parallel waves even within a single layer.
