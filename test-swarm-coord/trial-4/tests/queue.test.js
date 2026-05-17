import { describe, it } from 'node:test';
import assert from 'node:assert';
import { TaskQueue } from '../src/queue.js';

describe('TaskQueue', () => {
  it('enqueue increases size', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    assert.strictEqual(q.size(), 1);
  });

  it('dequeue returns highest priority task', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    q.enqueue({ id: 'b', data: 2, priority: 3 });
    q.enqueue({ id: 'c', data: 3, priority: 2 });
    assert.strictEqual(q.dequeue()?.id, 'b');
    assert.strictEqual(q.dequeue()?.id, 'c');
    assert.strictEqual(q.dequeue()?.id, 'a');
  });

  it('peek returns highest priority without removing', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 1, priority: 5 });
    assert.strictEqual(q.peek()?.id, 'a');
    assert.strictEqual(q.size(), 1);
  });

  it('dequeue from empty queue returns undefined', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.dequeue(), undefined);
  });

  it('peek on empty queue returns undefined', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.peek(), undefined);
  });

  it('size is zero for empty queue', () => {
    const q = new TaskQueue();
    assert.strictEqual(q.size(), 0);
  });

  it('priority ties resolved by heap shape', () => {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 1, priority: 2 });
    q.enqueue({ id: 'b', data: 2, priority: 2 });
    q.enqueue({ id: 'c', data: 3, priority: 2 });
    const out = [q.dequeue(), q.dequeue(), q.dequeue()].map(t => t?.id);
    assert.strictEqual(new Set(out).size, 3);
    assert.deepStrictEqual(out.slice().sort(), ['a', 'b', 'c']);
  });
});
