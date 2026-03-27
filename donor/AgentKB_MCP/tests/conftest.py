"""
Pytest configuration and fixtures.
"""

import pytest
import asyncio
from pathlib import Path
from typing import AsyncGenerator
import tempfile
import shutil

from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def temp_kb_dir():
    """Create a temporary KB directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="kb_test_")
    kb_files = Path(temp_dir) / "kb_files"
    kb_staging = Path(temp_dir) / "kb_staging"
    
    kb_files.mkdir()
    kb_staging.mkdir()
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_kb_content():
    """Sample KB content for testing."""
    return '''### ID: postgresql-max-connections-0001

**Question**: What is the default max_connections in PostgreSQL 16?

**Answer**:
The default value for `max_connections` in PostgreSQL 16 is 100. This parameter determines the maximum number of concurrent connections to the database server.

You can check the current value with:
```sql
SHOW max_connections;
```

To modify it, update `postgresql.conf`:
```
max_connections = 200
```

Note that increasing this value requires more shared memory.

**Domain**: postgresql

**Software Version**: 16.0

**Valid Until**: latest

**Confidence**: 1.00

**Tier**: GOLD

**Sources**:
- https://www.postgresql.org/docs/16/runtime-config-connection.html

**Related Questions**:
- How do I increase max_connections in PostgreSQL?
- What happens when max_connections is exceeded?
- How does max_connections affect memory usage?

---

### ID: postgresql-create-index-0002

**Question**: How do I create an index in PostgreSQL?

**Answer**:
To create an index in PostgreSQL, use the `CREATE INDEX` command:

```sql
-- Basic B-tree index
CREATE INDEX idx_users_email ON users(email);

-- Unique index
CREATE UNIQUE INDEX idx_users_email_unique ON users(email);

-- Composite index
CREATE INDEX idx_orders_customer_date ON orders(customer_id, order_date);

-- Partial index
CREATE INDEX idx_active_users ON users(email) WHERE active = true;

-- Expression index
CREATE INDEX idx_lower_email ON users(LOWER(email));
```

Common index types:
- B-tree (default): equality and range queries
- Hash: equality comparisons only
- GiST: geometric data, full-text search
- GIN: arrays, JSONB, full-text search

**Domain**: postgresql

**Software Version**: 16.0

**Valid Until**: latest

**Confidence**: 1.00

**Tier**: GOLD

**Sources**:
- https://www.postgresql.org/docs/16/sql-createindex.html
- https://www.postgresql.org/docs/16/indexes.html

**Related Questions**:
- When should I use a partial index?
- How do I drop an index in PostgreSQL?
- What is the difference between B-tree and GIN indexes?

---
'''


@pytest.fixture
def sample_kb_file(temp_kb_dir, sample_kb_content):
    """Create a sample KB file."""
    kb_path = Path(temp_kb_dir) / "kb_files" / "postgresql.md"
    kb_path.write_text(sample_kb_content, encoding="utf-8")
    return kb_path


@pytest.fixture
async def app():
    """Create a test application."""
    import os
    
    # Set test environment
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    
    from app.main import create_app
    return create_app()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sync_client(app):
    """Create a sync test client."""
    return TestClient(app)

