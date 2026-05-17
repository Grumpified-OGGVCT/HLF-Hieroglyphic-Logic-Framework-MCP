# Agent 1 — TaskQueue Design Notes

## Data Structure
A **binary max-heap** is used internally so that both `enqueue` and `dequeue` are **O(log n)**.  A naive sorted array would make enqueue O(n); a simple unsorted array would make dequeue O(n).  The heap gives the best overall throughput for a mixed workload.

## Stability
When two tasks share the same `priority`, a monotonic sequence counter preserves **FIFO ordering** among them.  This prevents starvation and makes the queue predictable.

## API Surface

| Method | Args | Returns | Behaviour |
|--------|------|---------|-----------|
| `enqueue(task)` | `Task` object | `void` | Validates `id` and `priority`, then inserts. |
| `dequeue()` | — | `Task \| undefined` | Removes and returns highest-priority task, or `undefined` if empty. |
| `peek()` | — | `Task \| undefined` | Returns highest-priority task without removing it. |
| `size()` | — | `number` | Current number of queued tasks. |

### `Task` shape
```js
{
  id: string | number,   // required — used for logging / correlation
  data: any,             // opaque payload — Agent 2 should treat it as a black box
  priority: number       // required — higher == more urgent
}
```

## What Agent 2 (Worker) Should Expect
- `dequeue()` will hand over the highest-priority task whenever the worker asks for work.
- `data` is completely opaque — the worker decides how to execute it.
- The queue does **not** mutate tasks; the worker may attach results or error info to the same object if desired.

## What Agent 3 (Tests) Should Know
- `enqueue` throws `TypeError` for missing `id` or non-numeric `priority`.
- The queue is empty when constructed; `size()` starts at `0`.
- `dequeue` on an empty queue returns `undefined` (does not throw).
- Equal-priority tasks come out in insertion order.
- Private fields (`#heap`, `#seq`) are not part of the public contract.

---

## Agent 2 — Worker Design Notes

### Concurrency Model
The worker maintains an **in-flight set** of currently executing tasks. A lightweight
**polling loop** (default 10 ms) continuously fills available concurrency slots by calling
`queue.dequeue()`. When a task completes, the worker immediately attempts to refill the
slot, ensuring high throughput without busy-waiting.

### Retry Strategy
Failed tasks are **re-enqueued** at their original priority. A `WeakMap` tracks
per-task retry attempts. The retry logic is:
- `retryCount = 0` → task is attempted once; on failure it emits `failed`/`task_error`.
- `retryCount = N` → task is attempted `1 + N` times total.

### Event System
The worker exposes an `on(event, handler)` registry. Emitted events:

| Event | When | Args |
|-------|------|------|
| `started` | `start()` transitions worker to running | none |
| `stopped` | `stop()` completes and all in-flight tasks finish | none |
| `task` / `task_start` | A task is dequeued and about to be processed | `task` object / `{task, attempt}` |
| `completed` / `task_complete` | All `task` handlers finish without throwing | `task` object / `{task, result, attempt}` |
| `failed` / `task_error` | Task fails after exhausting retries | `task, error` / `{task, error, attempt}` |

### Execution Model
Tasks are **executed by event handlers** registered via `worker.on('task', handler)`.
The worker itself does not call `task.execute()`; it dequeues the task, emits the `task`
event, and treats any thrown error (sync or async) as a task failure. This keeps the
worker generic and decoupled from domain logic.

### Public API
- `new Worker(taskQueue, { concurrency, retryCount })`
- `worker.start()` — begins polling and processing
- `worker.stop()` — stops accepting new tasks, returns a `Promise` that resolves when
  in-flight tasks finish
- `worker.on(event, handler)` — subscribe to events
- Getters: `worker.queue`, `worker.concurrency`, `worker.retryCount`

### What Agent 3 Should Expect
- `dequeue()` returning `undefined` when empty is handled gracefully.
- `stop()` emits `stopped` synchronously if no tasks are in-flight.
- Retried tasks are re-inserted into the queue via `enqueue()`, preserving the
  queue's priority ordering.

---

## Agent 2 — Worker Implementation Notes

### File
`src/worker.js` exports the `Worker` class.

### Private State
- `#handlers` — `Map<string, Set<Function>>` for event subscriptions.
- `#running` — boolean polling flag.
- `#intervalId` — `setInterval` handle for the 10 ms poll loop.
- `#inFlight` — `Set<Task>` tracking currently executing tasks.
- `#retries` — `WeakMap<Task, number>` for per-task retry counters.
- `#stopPromise / #stopResolve` — lazily created when `stop()` is called while tasks are in-flight.

### Concurrency & Polling
`#poll()` is called both on the interval **and** immediately after any task completes or fails. The `while` loop fills slots synchronously up to `concurrency`, so throughput stays high without busy-waiting.

### Retry Strategy (revised)
- `retryCount = 0` → 1 total attempt; failure emits `task_error`.
- `retryCount = N` → `1 + N` total attempts.
- Retried tasks are re-enqueued via `queue.enqueue(task)` at their original priority.
- Attempt numbering starts at `1` and increments on each dequeue.

### Event Shape (revised)
The worker emits both the canonical names from the spec and the PLAN aliases for backward compatibility:

| Event | Args |
|-------|------|
| `task_start` / `task` | `{ task, attempt }` / `task` |
| `task_complete` / `completed` | `{ task, result, attempt }` / `task` |
| `task_error` / `failed` | `{ task, error, attempt }` / `(task, error)` |
| `started` | none |
| `stopped` | none |

### Error Handling
- Handler exceptions are caught and treated as task failures.
- Errors inside event listeners (for non-`task` events) are swallowed so the worker remains stable.
- If no `task` handler is registered, the task throws immediately.

### Getters
`worker.queue`, `worker.concurrency`, `worker.retryCount`.
