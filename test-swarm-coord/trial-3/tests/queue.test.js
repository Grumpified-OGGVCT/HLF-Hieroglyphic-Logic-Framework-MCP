const assert = require('assert');
const { TaskQueue } = require('../src/queue');

function test(name, fn) {
  try { fn(); console.log(`  ✔ ${name}`); }
  catch (e) { console.error(`  ✘ ${name}: ${e.message}`); process.exitCode = 1; }
}

console.log('queue.test.js');

test('enqueue returns this (chainable)', () => {
  const q = new TaskQueue();
  assert.strictEqual(q.enqueue({ id: 'a', data: 1 }), q);
});

test('dequeue returns tasks in priority order', () => {
  const q = new TaskQueue();
  q.enqueue({ id: 'a', data: 1, priority: 1 });
  q.enqueue({ id: 'b', data: 2, priority: 3 });
  q.enqueue({ id: 'c', data: 3, priority: 2 });
  assert.deepStrictEqual(q.dequeue(), { id: 'b', data: 2, priority: 3 });
  assert.deepStrictEqual(q.dequeue(), { id: 'c', data: 3, priority: 2 });
  assert.deepStrictEqual(q.dequeue(), { id: 'a', data: 1, priority: 1 });
});

test('FIFO for equal priority', () => {
  const q = new TaskQueue();
  q.enqueue({ id: 'a', data: 1, priority: 5 });
  q.enqueue({ id: 'b', data: 2, priority: 5 });
  assert.strictEqual(q.dequeue().id, 'a');
  assert.strictEqual(q.dequeue().id, 'b');
});

test('peek returns highest-priority task without removing', () => {
  const q = new TaskQueue();
  q.enqueue({ id: 'a', data: 1, priority: 2 });
  assert.deepStrictEqual(q.peek(), { id: 'a', data: 1, priority: 2 });
  assert.strictEqual(q.size, 1);
});

test('size reflects number of tasks', () => {
  const q = new TaskQueue();
  assert.strictEqual(q.size, 0);
  q.enqueue({ id: 'a', data: 1 });
  assert.strictEqual(q.size, 1);
  q.enqueue({ id: 'b', data: 2 });
  assert.strictEqual(q.size, 2);
  q.dequeue();
  assert.strictEqual(q.size, 1);
});

test('dequeue on empty queue returns undefined', () => {
  const q = new TaskQueue();
  assert.strictEqual(q.dequeue(), undefined);
});

test('peek on empty queue returns undefined', () => {
  const q = new TaskQueue();
  assert.strictEqual(q.peek(), undefined);
});

test('default priority is 0', () => {
  const q = new TaskQueue();
  q.enqueue({ id: 'a', data: 1 });
  assert.strictEqual(q.peek().priority, 0);
});
