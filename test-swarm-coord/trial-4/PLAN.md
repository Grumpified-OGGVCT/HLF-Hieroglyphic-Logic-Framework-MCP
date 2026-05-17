# TaskQueue Design

## Data Structure
Binary max-heap stored in an array. Gives O(log n) enqueue/dequeue and O(1) peek/size.

## Task Shape
```js
{ id: string, data: unknown, priority: number }
```
`priority` is numeric; larger values dequeue first. Ties are resolved by insertion order (stable-ish via heap shape).

## Public API
- `enqueue(task)` – inserts a task
- `dequeue()` – removes and returns highest-priority task, or `undefined` if empty
- `peek()` – returns highest-priority task without removing it
- `size()` – current count

## Worker Design

### Execution Model
- Spawns `concurrency` independent async loops on `start()`.
- Each loop polls the queue; if empty, sleeps 50 ms and retries.
- `stop()` sets the active flag to false and blocks until `#running` reaches 0.

### Retry Logic
- Retries are tracked per `task.id` in a private `Map`.
- Failed tasks are re-enqueued with their original priority if attempts ≤ `retryCount`.
- When retries are exhausted, `'task_error'` is emitted and the task is dropped.

### Task Execution
- If `task.data` is a function, it is invoked (`await task.data()`).
- Otherwise `task.data` is returned as-is.

### Events
| Event          | Payload                              |
|----------------|---------------------------------------|
| `task_start`   | `Task`                                |
| `task_complete`| `{ task: Task, result: unknown }`     |
| `task_error`   | `{ task: Task, error: unknown }`      |

## Conventions for Other Agents
- The queue is **not** thread-safe; synchronize externally if used across workers.
- Do not mutate a task after enqueueing; the queue does not clone.
- Use `id` for deduplication or logging; the queue does not enforce uniqueness.
