# TaskQueue Design Plan

## Overview
A lightweight, in-memory priority queue for Node.js built as an ES module.

## Decisions
- **Max-heap via array** — gives `O(log n)` enqueue/dequeue with `O(1)` peek/size.
- **Stable ordering** — tie-breaker (`_seq`) preserves FIFO for equal priorities.
- **Private field `#heap`** — encapsulates internal state; no external mutation.
- **JSDoc** — typed API surface without a build step or TS dependency.
- **ES2020+** — uses private class fields and native `export`.

## Public Interface (other agents can rely on this)
```js
import { TaskQueue } from './src/queue.js';

const q = new TaskQueue();
q.enqueue({ id: 1, data: '...', priority: 10 });
const task = q.dequeue(); // highest priority task, or null
const next = q.peek();    // highest priority task without removal, or null
const n    = q.size();    // current count
```

## Task Shape Contract
```ts
interface Task {
  id: string | number;
  data: any;
  priority: number;   // higher number = higher priority
}
```

## Out of Scope
- Persistence / durability.
- Concurrency / worker scheduling (see `Worker` agent).
- Test suite (see testing agent).

## Worker Design Notes

- **Concurrency control** — tracks in-flight count; polls queue only when under limit.
- **Fire-and-forget processing** — `#process()` runs independently so the polling loop stays responsive.
- **Retry with re-enqueue** — failed tasks are pushed back into the queue with a `_retries` counter; preserves priority ordering.
- **Event emitter pattern** — `on()` registers handlers; `#emit()` calls them with try/catch isolation.
- **Graceful stop** — `stop()` sets a flag; polling loop exits; in-flight tasks finish naturally.
- **JSDoc** — full type coverage for public API and event payloads.
- **ES2020+** — private fields (`#handlers`, `#running`, `#loopActive`, etc.).
