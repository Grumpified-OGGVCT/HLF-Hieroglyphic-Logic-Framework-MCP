# TaskQueue Design

## Implementation
- **Binary max-heap** backed by an array for O(log n) enqueue/dequeue.
- Private `#heap` field keeps the internal state encapsulated.
- Higher `priority` number = dequeued first.

## Public API
| Method | Returns | Notes |
|--------|---------|-------|
| `enqueue(task)` | `void` | `task` shape: `{ id: string, data: any, priority: number }` |
| `dequeue()` | `Task \| undefined` | Highest-priority task, or `undefined` if empty |
| `peek()` | `Task \| undefined` | Same as dequeue but non-mutating |
| `size()` | `number` | Current queue length |

## Expectations for Other Agents
- Import: `const { TaskQueue } = require('./src/queue');`
- Tasks must have unique `id` values if callers need deduplication (the queue does not enforce uniqueness).
- No async behavior or persistence—pure in-memory queue.
