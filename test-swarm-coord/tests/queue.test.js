const assert = require('assert');
const { TaskQueue } = require('../src/queue');

console.log('--- TaskQueue Tests ---');

// Test: enqueue adds tasks and dequeue returns them in FIFO order
(function testEnqueueAndDequeue() {
    const q = new TaskQueue();
    q.enqueue({ id: 't1', data: 'a', priority: 1 });
    q.enqueue({ id: 't2', data: 'b', priority: 1 });
    const t1 = q.dequeue();
    const t2 = q.dequeue();
    assert.strictEqual(t1.id, 't1', 'first dequeued should be t1');
    assert.strictEqual(t2.id, 't2', 'second dequeued should be t2');
    console.log('✓ enqueue and dequeue');
})();

// Test: size reflects the number of tasks
(function testSize() {
    const q = new TaskQueue();
    assert.strictEqual(q.size(), 0, 'initial size should be 0');
    q.enqueue({ id: 't1', data: 'a', priority: 1 });
    assert.strictEqual(q.size(), 1, 'size should be 1 after one enqueue');
    q.enqueue({ id: 't2', data: 'b', priority: 2 });
    assert.strictEqual(q.size(), 2, 'size should be 2 after two enqueues');
    q.dequeue();
    assert.strictEqual(q.size(), 1, 'size should be 1 after one dequeue');
    console.log('✓ size');
})();

// Test: peek returns the next task without removing it
(function testPeek() {
    const q = new TaskQueue();
    q.enqueue({ id: 't1', data: 'a', priority: 1 });
    q.enqueue({ id: 't2', data: 'b', priority: 1 });
    const peeked = q.peek();
    assert.strictEqual(peeked.id, 't1', 'peek should return t1');
    assert.strictEqual(q.size(), 2, 'peek should not remove the task');
    console.log('✓ peek');
})();

// Test: dequeue on an empty queue returns undefined
(function testDequeueEmpty() {
    const q = new TaskQueue();
    assert.strictEqual(q.dequeue(), undefined, 'dequeue on empty queue should return undefined');
    console.log('✓ dequeue empty queue');
})();

// Test: peek on an empty queue returns undefined
(function testPeekEmpty() {
    const q = new TaskQueue();
    assert.strictEqual(q.peek(), undefined, 'peek on empty queue should return undefined');
    console.log('✓ peek empty queue');
})();

// Test: priority ordering (higher priority first)
(function testPriority() {
    const q = new TaskQueue();
    q.enqueue({ id: 'low', data: 'low', priority: 1 });
    q.enqueue({ id: 'high', data: 'high', priority: 10 });
    q.enqueue({ id: 'mid', data: 'mid', priority: 5 });
    assert.strictEqual(q.dequeue().id, 'high', 'highest priority should be dequeued first');
    assert.strictEqual(q.dequeue().id, 'mid', 'mid priority should be next');
    assert.strictEqual(q.dequeue().id, 'low', 'lowest priority should be last');
    console.log('✓ priority ordering');
})();

// Test: tasks with the same priority maintain FIFO order
(function testPriorityTieBreaksWithFIFO() {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 'a', priority: 5 });
    q.enqueue({ id: 'b', data: 'b', priority: 5 });
    q.enqueue({ id: 'c', data: 'c', priority: 5 });
    assert.strictEqual(q.dequeue().id, 'a');
    assert.strictEqual(q.dequeue().id, 'b');
    assert.strictEqual(q.dequeue().id, 'c');
    console.log('✓ priority tie breaks with FIFO');
})();

console.log('--- TaskQueue Tests Passed ---');
