# TaskQueue Design

## Decisions
- **Array + linear search**: Chosen for clarity and small-to-medium queues. `findIndex` locates the insertion point by descending priority; `splice` maintains FIFO for equal priorities.
- **ES2020+ features**: Private field `#tasks` encapsulates internal state. Object spread provides default priority.
- **Chainable `enqueue`**: Returns `this` so callers can queue multiple tasks fluently.

## Interface Contract
- `new TaskQueue()`
- `enqueue(task)` → `TaskQueue`
- `dequeue()` → `Task | undefined`
- `peek()` → `Task | undefined`
- `size` → `number` (getter)

Task shape expected by all consumers: `{ id: string, data: any, priority?: number }`

# Worker Design

## Decisions
- **Event-driven execution**: `Worker` is a pure consumer of `TaskQueue`. It emits `'task_start'`, `'task_complete'`, and `'task_error'` so upstream orchestrators can observe progress without tight coupling.
- **Concurrency via active counter**: A private `#active` counter tracks in-flight tasks. `#poll()` greedily dequeues while `#active < concurrency`.
- **Retry via re-enqueue**: Failed tasks are re-enqueued with `_retries` incremented so priority order is preserved. When `_retries` exceeds `retryCount`, `'task_error'` is emitted instead.
- **`task.data` as callable**: If `task.data` is a function it is invoked and awaited; otherwise the raw value is treated as the result.
- **Graceful stop**: `stop()` sets `#running = false` and returns a promise that resolves once `#active` reaches zero. No new tasks are picked up after stop.
- **Chainable API**: `start()` and `on()` return `this` for fluent configuration.

## Interface Contract
- `new Worker(taskQueue, { concurrency, retryCount })`
- `start()` → `Worker`
- `stop()` → `Promise<void>`
- `on(event, handler)` → `Worker`
- Events: `task_start`, `task_complete`, `task_error`
