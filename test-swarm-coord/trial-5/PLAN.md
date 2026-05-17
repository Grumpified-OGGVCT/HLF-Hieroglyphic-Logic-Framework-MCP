# TaskQueue Design

## Decisions
- **Sorted array**: Kept simple with insertion-sort on `enqueue` (O(n)). dequeue/peek/size are O(1). If throughput becomes a bottleneck, swap in a binary max-heap.
- **Stable ordering**: Equal-priority tasks preserve FIFO order because new tasks are inserted after existing tasks of the same priority.
- **ES module**: `export class TaskQueue` — consumed via `import { TaskQueue } from './src/queue.js'`.
- **Validation**: `enqueue` throws if `priority` is missing or not a number.

## Interface for Other Agents
- **Constructor**: `new TaskQueue()`
- **Methods**:
  - `enqueue(task)` → `number` (new size)
  - `dequeue()` → `Task | undefined`
  - `peek()` → `Task | undefined`
  - `size()` → `number`
- **Task shape**: `{ id: string|number, data: any, priority: number }` where higher numbers = sooner execution.
- **No side effects**: Pure in-memory queue; no Worker or I/O here.

---

# Worker Design

## Concurrency Model
A lightweight **polling loop** (10 ms `setTimeout`) fills available concurrency slots by calling `queue.dequeue()`. After any task finishes, `#poll()` is invoked immediately to refill the slot, keeping throughput high without busy-waiting.

## Retry Strategy
`WeakMap` tracks per-task retry attempts.
- `retryCount = 0` → 1 total attempt; failure emits `task_error`.
- `retryCount = N` → `1 + N` total attempts.
- Exhausted tasks emit `task_error`; retried tasks are re-enqueued at original priority.

## Event System
`on(event, handler)` registers subscribers. Emitted events:

| Event | When | Args |
|-------|------|------|
| `started` | `start()` transitions to running | none |
| `stopped` | `stop()` completes, in-flight empty | none |
| `task_start` | Task dequeued, about to run | `{ task, attempt }` |
| `task_complete` | Task handler succeeds | `{ task, result, attempt }` |
| `task_error` | Task fails after exhausting retries | `{ task, error, attempt }` |
| `task` | Alias for handler execution | `task` |
| `completed` | Alias for `task_complete` | `task` |
| `failed` | Alias for `task_error` | `task, error` |

## Public API
- `new Worker(taskQueue, { concurrency, retryCount })`
- `worker.start()` — begins polling
- `worker.stop()` — stops accepting new tasks; returns `Promise` resolved when in-flight finish
- `worker.on(event, handler)` — subscribe
- Getters: `worker.queue`, `worker.concurrency`, `worker.retryCount`
