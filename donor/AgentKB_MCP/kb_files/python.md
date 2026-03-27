# Python Knowledge Base

### ID: python-asyncio-basics-0001

**Question**: How do I use async/await in Python?

**Answer**:
Python's `async/await` syntax (introduced in Python 3.5) enables asynchronous programming. Here's how to use it:

**Basic async function:**
```python
import asyncio

async def fetch_data():
    print("Fetching...")
    await asyncio.sleep(1)  # Simulates async I/O
    return {"data": "result"}

# Run the async function
result = asyncio.run(fetch_data())
print(result)
```

**Running multiple coroutines concurrently:**
```python
async def main():
    # Run concurrently with gather
    results = await asyncio.gather(
        fetch_data(),
        fetch_data(),
        fetch_data()
    )
    return results

asyncio.run(main())
```

**Creating tasks for better control:**
```python
async def main():
    # Create tasks
    task1 = asyncio.create_task(fetch_data())
    task2 = asyncio.create_task(fetch_data())
    
    # Wait for both
    result1 = await task1
    result2 = await task2
    
    return result1, result2
```

**Error handling:**
```python
async def safe_fetch():
    try:
        result = await fetch_data()
        return result
    except Exception as e:
        print(f"Error: {e}")
        return None
```

**Key concepts:**
- `async def` defines a coroutine function
- `await` suspends execution until the awaited coroutine completes
- `asyncio.run()` runs the main coroutine (Python 3.7+)
- Only use `await` inside `async` functions
- Async is beneficial for I/O-bound operations, not CPU-bound

**Domain**: python

**Software Version**: 3.12

**Valid Until**: latest

**Confidence**: 1.00

**Tier**: GOLD

**Sources**:
- https://docs.python.org/3/library/asyncio-task.html
- https://docs.python.org/3/library/asyncio.html

**Related Questions**:
- What is the difference between asyncio.gather and asyncio.wait?
- How do I handle timeouts in async Python?
- Can I use async with synchronous libraries?
- What is an event loop in asyncio?
- How do I debug async Python code?

---

### ID: python-type-hints-basics-0002

**Question**: How do I add type hints to Python functions?

**Answer**:
Python type hints (PEP 484) provide optional static type annotations. Here's how to use them:

**Basic function annotations:**
```python
def greet(name: str) -> str:
    return f"Hello, {name}"

def add(a: int, b: int) -> int:
    return a + b
```

**Common types:**
```python
from typing import List, Dict, Optional, Union, Tuple, Callable

# List of strings
def process_names(names: List[str]) -> None:
    pass

# Dictionary
def get_config() -> Dict[str, int]:
    return {"timeout": 30}

# Optional (can be None)
def find_user(id: int) -> Optional[str]:
    return None

# Union (multiple types)
def parse_id(id: Union[str, int]) -> int:
    return int(id)

# Tuple with specific types
def get_point() -> Tuple[float, float]:
    return (1.0, 2.0)

# Callable
def apply(func: Callable[[int], int], value: int) -> int:
    return func(value)
```

**Python 3.10+ syntax (simplified):**
```python
# Use | instead of Union
def parse_id(id: str | int) -> int:
    return int(id)

# Use list, dict directly (no import needed)
def process(items: list[str]) -> dict[str, int]:
    return {}
```

**Type hints for classes:**
```python
class User:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age
    
    def greet(self) -> str:
        return f"Hi, I'm {self.name}"
```

**Note:** Type hints are not enforced at runtime. Use tools like `mypy` for static type checking.

**Domain**: python

**Software Version**: 3.12

**Valid Until**: latest

**Confidence**: 1.00

**Tier**: GOLD

**Sources**:
- https://docs.python.org/3/library/typing.html
- https://peps.python.org/pep-0484/

**Related Questions**:
- How do I use mypy for type checking?
- What is the difference between List and list in type hints?
- How do I type hint a decorator?
- What are TypeVar and Generic in Python typing?
- How do I type hint *args and **kwargs?

---

