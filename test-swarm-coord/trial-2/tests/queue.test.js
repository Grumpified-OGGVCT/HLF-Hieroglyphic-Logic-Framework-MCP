import { describe, it } from 'node:test';
import assert from 'node:assert';
import { TaskQueue } from '../src/index.js';

describe('TaskQueue', () => {
  it('enqueue and dequeue tasks in priority order', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    q.enqueue({ id: 'b', data: 2, priority: 2 });
    assert.strictEqual(q.dequeue().id, 'b');
    assert.strictEqual(q.dequeue().id, 'a');
  });

  it('returns correct size', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.size(), 0);
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    assert.strictEqual(q.size(), 1);
    q.enqueue({ id: 'b', data: 2, priority: 2 });
    assert.strictEqual(q.size(), 2);
    q.dequeue();
    assert.strictEqual(q.size(), 1);
  });

  it('peek returns highest priority without removing', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    assert.strictEqual(q.peek().id, 'a');
    assert.strictEqual(q.size(), 1);
    q.enqueue({ id: 'b', data: 2, priority: 2 });
    assert.strictEqual(q.peek().id, 'b');
    assert.strictEqual(q.size(), 2);
  });

  it('handles empty queue edge cases', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.dequeue(), null);
    assert.strictEqual(q.peek(), null);
    assert.strictEqual(q.size(), 0);
  });

  it('maintains FIFO for equal priorities', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'first', data: 1, priority: 5 });
    q.enqueue({ id: 'second', data: 2, priority: 5 });
    q.enqueue({ id: 'third', data: 3, priority: 5 });
    assert.strictEqual(q.dequeue().id, 'first');
    assert.strictEqual(q.dequeue().id, 'second');
    assert.strictEqual(q.dequeue().id, 'third');
  });

  it('throws for invalid task', () => {
    const q = new TaskQueue();
    assert.throws(() => q.enqueue(null), /numeric priority/);
    assert.throws(() => q.enqueue({ id: 1 }), /numeric priority/);
  });
});
