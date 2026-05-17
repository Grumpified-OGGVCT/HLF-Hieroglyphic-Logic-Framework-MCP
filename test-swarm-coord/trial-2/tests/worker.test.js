import { describe, it } from 'node:test';
import assert from 'node:assert';
import { TaskQueue, Worker } from '../src/index.js';

const delay = (ms) => new Promise(r => setTimeout(r, ms));

describe('Worker', () => {
  it('constructor accepts queue and options', () => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 3, retryCount: 2 });
    assert.ok(w);
    assert.strictEqual(w.start(), w);
    w.stop();
  });

  it('constructor throws for invalid queue', () => {
    assert.throws(() => new Worker(null), /dequeue/);
    assert.throws(() => new Worker({}), /dequeue/);
  });

  it('uses defaults when options omitted', () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    assert.ok(w);
  });

  it('does not auto-start', () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    let started = false;
    w.on('task_start', () => { started = true; });
    q.enqueue({ id: 't1', data: 'a', priority: 1 });
    assert.strictEqual(started, false);
  });

  it('starts processing tasks', async () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    const completed = [];
    w.on('task_complete', ({ task }) => { completed.push(task.id); });
    w.start();
    q.enqueue({ id: 't1', data: 'hello', priority: 1 });
    await delay(100);
    assert.deepStrictEqual(completed, ['t1']);
    w.stop();
  });

  it('emits task_start and task_complete events', async () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    const events = [];
    w.on('task_start', ({ task }) => { events.push(`start:${task.id}`); });
    w.on('task_complete', ({ task }) => { events.push(`complete:${task.id}`); });
    w.start();
    q.enqueue({ id: 't1', data: 42, priority: 1 });
    await delay(100);
    assert.deepStrictEqual(events, ['start:t1', 'complete:t1']);
    w.stop();
  });

  it('respects concurrency limit', async () => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 2 });
    let maxRunning = 0;
    let current = 0;
    q.enqueue({ id: 'a', data: async () => { current++; maxRunning = Math.max(maxRunning, current); await delay(50); current--; return 'a'; }, priority: 1 });
    q.enqueue({ id: 'b', data: async () => { current++; maxRunning = Math.max(maxRunning, current); await delay(50); current--; return 'b'; }, priority: 1 });
    q.enqueue({ id: 'c', data: async () => { current++; maxRunning = Math.max(maxRunning, current); await delay(50); current--; return 'c'; }, priority: 1 });
    w.start();
    await delay(200);
    assert.strictEqual(maxRunning, 2);
    w.stop();
  });

  it('retries failed tasks up to retryCount', async () => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 1, retryCount: 2 });
    let attempts = 0;
    const errors = [];
    w.on('task_error', ({ task, error }) => { errors.push({ id: task.id, msg: error.message }); });
    q.enqueue({ id: 'r1', data: () => { attempts++; throw new Error('fail'); }, priority: 1 });
    w.start();
    await delay(300);
    assert.strictEqual(attempts, 3);
    assert.strictEqual(errors.length, 1);
    assert.strictEqual(errors[0].msg, 'fail');
    w.stop();
  });

  it('stop prevents new tasks from starting', async () => {
    const q = new TaskQueue();
    const w = new Worker(q);
    const completed = [];
    w.on('task_complete', ({ task }) => { completed.push(task.id); });
    q.enqueue({ id: 't1', data: async () => { await delay(30); return 'done'; }, priority: 1 });
    w.start();
    await delay(20);
    w.stop();
    await delay(100);
    assert.deepStrictEqual(completed, ['t1']);
    q.enqueue({ id: 't2', data: 'x', priority: 1 });
    await delay(100);
    assert.strictEqual(completed.length, 1);
  });
});
