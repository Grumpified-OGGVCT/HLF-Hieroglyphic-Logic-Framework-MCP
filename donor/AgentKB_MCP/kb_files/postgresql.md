# PostgreSQL Knowledge Base

### ID: postgresql-max-connections-default-0001

**Question**: What is the default max_connections in PostgreSQL 16?

**Answer**:
The default value for `max_connections` in PostgreSQL 16 is **100**. This parameter determines the maximum number of concurrent connections to the database server.

You can check the current value by running:

```sql
SHOW max_connections;
```

To modify it, edit the `postgresql.conf` file:

```
max_connections = 200
```

Then restart the PostgreSQL server for the change to take effect.

**Important considerations:**
- Each connection consumes memory (approximately 5-10 MB per connection)
- Increasing this value requires more shared memory
- Consider using a connection pooler (like PgBouncer) for high-connection workloads
- The practical maximum depends on your available memory

**Domain**: postgresql

**Software Version**: 16.0

**Valid Until**: latest

**Confidence**: 1.00

**Tier**: GOLD

**Sources**:
- https://www.postgresql.org/docs/16/runtime-config-connection.html

**Related Questions**:
- How do I increase max_connections in PostgreSQL?
- What happens when max_connections is exceeded in PostgreSQL?
- How does max_connections affect memory usage in PostgreSQL?
- What is the relationship between max_connections and shared_buffers?
- Should I use a connection pooler with PostgreSQL?

---

### ID: postgresql-create-index-basic-0002

**Question**: How do I create an index in PostgreSQL?

**Answer**:
To create an index in PostgreSQL, use the `CREATE INDEX` command. Here are the common patterns:

**Basic B-tree index (default):**
```sql
CREATE INDEX idx_users_email ON users(email);
```

**Unique index:**
```sql
CREATE UNIQUE INDEX idx_users_email_unique ON users(email);
```

**Composite (multi-column) index:**
```sql
CREATE INDEX idx_orders_customer_date ON orders(customer_id, order_date);
```

**Partial index (filtered):**
```sql
CREATE INDEX idx_active_users ON users(email) WHERE active = true;
```

**Expression index:**
```sql
CREATE INDEX idx_lower_email ON users(LOWER(email));
```

**Concurrent index creation (non-blocking):**
```sql
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
```

**Available index types:**
- **B-tree** (default): Best for equality and range queries
- **Hash**: Equality comparisons only
- **GiST**: Geometric data, full-text search, range types
- **GIN**: Arrays, JSONB, full-text search
- **BRIN**: Block range indexes for very large tables with natural ordering

**Domain**: postgresql

**Software Version**: 16.0

**Valid Until**: latest

**Confidence**: 1.00

**Tier**: GOLD

**Sources**:
- https://www.postgresql.org/docs/16/sql-createindex.html
- https://www.postgresql.org/docs/16/indexes.html

**Related Questions**:
- When should I use a partial index in PostgreSQL?
- How do I drop an index in PostgreSQL?
- What is the difference between B-tree and GIN indexes?
- How do I create an index without blocking writes?
- How do I check if an index is being used?

---

### ID: postgresql-jsonb-query-0003

**Question**: How do I query JSONB data in PostgreSQL?

**Answer**:
PostgreSQL provides powerful operators for querying JSONB data:

**Basic operators:**

```sql
-- Get value as JSON (->)
SELECT data->'name' FROM users;

-- Get value as text (->>)
SELECT data->>'name' FROM users;

-- Get nested value
SELECT data->'address'->>'city' FROM users;

-- Get array element by index
SELECT data->'tags'->0 FROM users;
```

**Containment operators:**

```sql
-- Contains (@>)
SELECT * FROM users WHERE data @> '{"role": "admin"}';

-- Is contained by (<@)
SELECT * FROM users WHERE '{"admin": true}' <@ data;

-- Key exists (?)
SELECT * FROM users WHERE data ? 'email';

-- Any key exists (?|)
SELECT * FROM users WHERE data ?| array['email', 'phone'];

-- All keys exist (?&)
SELECT * FROM users WHERE data ?& array['email', 'name'];
```

**Path queries (jsonpath - PostgreSQL 12+):**

```sql
-- Using jsonpath
SELECT * FROM users 
WHERE data @@ '$.age > 21';

-- Extract with jsonpath
SELECT jsonb_path_query(data, '$.tags[*]') FROM users;
```

**Indexing JSONB for performance:**

```sql
-- GIN index for containment queries
CREATE INDEX idx_data_gin ON users USING gin(data);

-- GIN index for specific paths
CREATE INDEX idx_data_email ON users USING gin((data->'email'));
```

**Domain**: postgresql

**Software Version**: 16.0

**Valid Until**: latest

**Confidence**: 1.00

**Tier**: GOLD

**Sources**:
- https://www.postgresql.org/docs/16/functions-json.html
- https://www.postgresql.org/docs/16/datatype-json.html

**Related Questions**:
- What is the difference between JSON and JSONB in PostgreSQL?
- How do I update a value inside a JSONB column?
- How do I index JSONB data for faster queries?
- How do I aggregate JSONB arrays?
- What are the performance characteristics of JSONB operators?

---

