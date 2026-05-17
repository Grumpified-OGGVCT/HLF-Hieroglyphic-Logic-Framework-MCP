import { describe, it } from 'node:test';
import assert from 'node:assert';
import { TaskQueue } from '../src/queue.js';
import { Worker } from '../src/worker.js';

describe('Worker', () => {
  it('constructor stores options', () => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 2, retryCount: 3 });
    assert.ok(w);
  });

  it('throws on invalid concurrency', () => {
    const q = new TaskQueue();
    assert.throws(() => new Worker(q, { concurrency: 0, retryCount: 0 }), RangeError);
  });

  it('throws on negative retryCount', () => {
    const q = new TaskQueue();
    assert.throws(() => new Worker(q, { concurrency: 1, retryCount: -1 }), RangeError);
  });

  it('does not auto-start', async () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: async () => 'done', priority: 1 });
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    await new Promise(r => setTimeout(r, 80));
    assert.strictEqual(q.size(), 1);
    await w.stop();
  });

  it('start processes tasks and emits events', async () => {
    const q = new TaskQueue();
    let started = false;
    let completed = false;
    q.enqueue({ id: 'a', data: async () => 'result', priority: 1 });
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    w.on('task_start', () => { started = true; });
    w.on('task_complete', (ev) => { completed = ev.result === 'result'; });
    w.start();
    await new Promise(r => setTimeout(r, 80));
    assert.ok(started);
    assert.ok(completed);
    assert.strictEqual(q.size(), 0);
    await w.stop();
  });

  it('stop waits for in-flight tasks', async () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: async () => new Promise(r => setTimeout(r, 60)), priority: 1 });
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    w.start();
    await new Promise(r => setTimeout(r, 20));
    await w.stop();
    assert.strictEqual(q.size(), 0);
  });

  it('concurrency runs multiple tasks concurrently', async () => {
    const q = new TaskQueue();
    let running = 0;
    let maxRunning = 0;
    const makeTask = (id) => ({
      id,
      data: async () => {
        running++;
        if (running > maxRunning) maxRunning = running;
        await new Promise(r => setTimeout(r, 40));
        running--;
      },
      priority: 1,
    });
    q.enqueue(makeTask('a'));
    q.enqueue(makeTask('b'));
    const w = new Worker(q, { concurrency: 2, retryCount: 0 });
    w.start();
    await new Promise(r => setTimeout(r, 120));
    assert.strictEqual(maxRunning, 2);
    await w.stop();
  });

  it('retry re-enqueues failed tasks', async () => {
    const q = new TaskQueue();
    let attempts = 0;
    q.enqueue({ id: 'a', data: async () => { attempts++; throw new Error('fail'); }, priority: 1 });
    const w = new Worker(q, { concurrency: 1, retryCount: 2 });
    w.start();
    await new Promise(r => setTimeout(r, 250));
    assert.strictEqual(attempts, 3);
    await w.stop();
  });

  it('emits task_error after retries exhausted', async () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: async () => { throw new Error('fail'); }, priority: 1 });
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    let errorEvent = null;
    w.on('task_error', (ev) => { errorEvent = ev; });
    w.start();
    await new Promise(r => setTimeout(r, 100));
    assert.ok(errorEvent);
    assert.strictEqual(errorEvent.task.id, 'a');
    await w.stop();
  });
});
