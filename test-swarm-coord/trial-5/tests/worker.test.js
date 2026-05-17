import { describe, it } from 'node:test';
import assert from 'node:assert';
import { TaskQueue } from '../src/queue.js';
import { Worker } from '../src/worker.js';

describe('Worker', () => {
  it('constructor stores queue and defaults', () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    assert.strictEqual(w.queue, q);
    assert.strictEqual(w.concurrency, 1);
    assert.strictEqual(w.retryCount, 0);
  });

  it('constructor accepts options', () => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 3, retryCount: 2 });
    assert.strictEqual(w.concurrency, 3);
    assert.strictEqual(w.retryCount, 2);
  });

  it('does not auto-start', () => {
    const q = new TaskQueue();
    let started = false;
    const w = new Worker(q);
    w.on('started', () => { started = true; });
    assert.strictEqual(started, false);
  });

  it('emits started on start()', () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    let started = false;
    w.on('started', () => { started = true; });
    w.start();
    assert.strictEqual(started, true);
    return w.stop();
  });

  it('emits stopped on stop()', async () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    let stopped = false;
    w.on('stopped', () => { stopped = true; });
    w.start();
    await w.stop();
    assert.strictEqual(stopped, true);
  });

  it('processes tasks and emits events', async () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    const events = [];

    w.on('task', (task) => {
      events.push({ event: 'task', id: task.id });
      return task.data;
    });
    w.on('completed', (task) => events.push({ event: 'completed', id: task.id }));
    w.on('task_complete', ({ task, result }) => {
      events.push({ event: 'task_complete', id: task.id, result });
    });

    q.enqueue({ id: 'a', data: 42, priority: 1 });
    w.start();
    await w.stop();

    assert.strictEqual(events.length, 3);
    assert.strictEqual(events[0].event, 'task');
    assert.strictEqual(events[0].id, 'a');
    assert.strictEqual(events[1].event, 'completed');
    assert.strictEqual(events[2].event, 'task_complete');
    assert.strictEqual(events[2].result, 42);
  });

  it('retries failed tasks up to retryCount', async () => {
    const q = new TaskQueue();
    const w = new Worker(q, { retryCount: 2 });
    let attempts = 0;

    w.on('task', () => {
      attempts++;
      throw new Error('fail');
    });

    q.enqueue({ id: 'r', data: 0, priority: 1 });
    w.start();

    await new Promise((resolve) => w.on('task_error', resolve));
    await w.stop();

    assert.strictEqual(attempts, 3);
  });

  it('respects concurrency limit', async () => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 2 });
    let running = 0;
    let maxRunning = 0;

    w.on('task', async () => {
      running++;
      if (running > maxRunning) maxRunning = running;
      await new Promise(r => setTimeout(r, 30));
      running--;
    });

    q.enqueue({ id: 1, priority: 1 });
    q.enqueue({ id: 2, priority: 1 });
    q.enqueue({ id: 3, priority: 1 });
    w.start();
    await w.stop();

    assert.strictEqual(maxRunning, 2);
  });
});
