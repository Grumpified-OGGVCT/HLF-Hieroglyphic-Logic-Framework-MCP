import { describe, it } from 'node:test';
import assert from 'node:assert';
import { TaskQueue } from '../src/queue.js';

describe('TaskQueue', () => {
  it('enqueue returns new size', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.enqueue({ id: 1, priority: 1 }), 1);
    assert.strictEqual(q.enqueue({ id: 2, priority: 2 }), 2);
  });

  it('dequeue returns highest-priority task', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', priority: 1 });
    q.enqueue({ id: 'b', priority: 5 });
    assert.deepStrictEqual(q.dequeue(), { id: 'b', priority: 5 });
    assert.deepStrictEqual(q.dequeue(), { id: 'a', priority: 1 });
  });

  it('dequeue returns undefined when empty', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.dequeue(), undefined);
  });

  it('peek returns highest-priority task without removing', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', priority: 3 });
    assert.deepStrictEqual(q.peek(), { id: 'a', priority: 3 });
    assert.strictEqual(q.size(), 1);
  });

  it('peek returns undefined when empty', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.peek(), undefined);
  });

  it('size reflects enqueue and dequeue', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.size(), 0);
    q.enqueue({ id: 1, priority: 1 });
    assert.strictEqual(q.size(), 1);
    q.dequeue();
    assert.strictEqual(q.size(), 0);
  });

  it('orders by descending priority', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', priority: 2 });
    q.enqueue({ id: 'b', priority: 10 });
    q.enqueue({ id: 'c', priority: 5 });
    assert.deepStrictEqual(q.dequeue(), { id: 'b', priority: 10 });
    assert.deepStrictEqual(q.dequeue(), { id: 'c', priority: 5 });
    assert.deepStrictEqual(q.dequeue(), { id: 'a', priority: 2 });
  });

  it('is stable for equal priorities', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'first',  priority: 5 });
    q.enqueue({ id: 'second', priority: 5 });
    assert.deepStrictEqual(q.dequeue(), { id: 'first', priority: 5 });
    assert.deepStrictEqual(q.dequeue(), { id: 'second', priority: 5 });
  });

  it('throws for missing or non-numeric priority', () => {
    const q = new TaskQueue();
    assert.throws(() => q.enqueue({ id: 1 }), /numeric priority/);
    assert.throws(() => q.enqueue({ id: 1, priority: 'high' }), /numeric priority/);
    assert.throws(() => q.enqueue(null), /numeric priority/);
  });
});
