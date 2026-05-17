const assert = require('assert');
const { TaskQueue } = require('../src/queue');

console.log('--- TaskQueue Tests ---');

(function testEnqueueAndDequeue() {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    q.enqueue({ id: 'b', data: 2, priority: 2 });
    assert.strictEqual(q.dequeue().id, 'b');
    assert.strictEqual(q.dequeue().id, 'a');
    console.log('✓ enqueue and dequeue');
})();

(function testSize() {
    const q = new TaskQueue();
    assert.strictEqual(q.size(), 0);
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    assert.strictEqual(q.size(), 1);
    q.enqueue({ id: 'b', data: 2, priority: 2 });
    assert.strictEqual(q.size(), 2);
    q.dequeue();
    assert.strictEqual(q.size(), 1);
    console.log('✓ size');
})();

(function testPeek() {
    const q = new TaskQueue();
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    assert.strictEqual(q.peek().id, 'a');
    assert.strictEqual(q.size(), 1);
    console.log('✓ peek');
})();

(function testEmptyEdgeCases() {
    const q = new TaskQueue();
    assert.strictEqual(q.dequeue(), undefined);
    assert.strictEqual(q.peek(), undefined);
    assert.strictEqual(q.size(), 0);
    console.log('✓ empty edge cases');
})();

(function testPriorityOrdering() {
    const q = new TaskQueue();
    q.enqueue({ id: 'low', data: 1, priority: 1 });
    q.enqueue({ id: 'high', data: 3, priority: 3 });
    q.enqueue({ id: 'mid', data: 2, priority: 2 });
    assert.strictEqual(q.dequeue().id, 'high');
    assert.strictEqual(q.dequeue().id, 'mid');
    assert.strictEqual(q.dequeue().id, 'low');
    console.log('✓ priority ordering');
})();

console.log('--- TaskQueue Tests Passed ---');
