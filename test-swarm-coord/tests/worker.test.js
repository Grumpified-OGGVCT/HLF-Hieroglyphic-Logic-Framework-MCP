const assert = require('assert');
const { Worker } = require('../src/worker');
const { TaskQueue } = require('../src/queue');

console.log('--- Worker Tests ---');

// Test: Worker constructor stores queue and options
(function testConstructor() {
    const q = new TaskQueue();
    const worker = new Worker(q, { concurrency: 3, retryCount: 2 });
    assert.strictEqual(worker.queue, q, 'worker should hold reference to queue');
    assert.strictEqual(worker.concurrency, 3, 'concurrency should be 3');
    assert.strictEqual(worker.retryCount, 2, 'retryCount should be 2');
    console.log('✓ constructor');
})();

// Test: Worker starts and emits a 'started' event
(function testStartEvent() {
    const q = new TaskQueue();
    const worker = new Worker(q, { concurrency: 1 });
    let called = false;
    worker.on('started', () => { called = true; });
    worker.start();
    assert.strictEqual(called, true, 'started event should fire');
    worker.stop();
    console.log('✓ start event');
})();

// Test: Worker stops and emits a 'stopped' event
(function testStopEvent() {
    const q = new TaskQueue();
    const worker = new Worker(q, { concurrency: 1 });
    let called = false;
    worker.on('stopped', () => { called = true; });
    worker.start();
    worker.stop();
    assert.strictEqual(called, true, 'stopped event should fire');
    console.log('✓ stop event');
})();

// Test: Worker processes a task from the queue
const testProcessTask = () => new Promise((resolve) => {
    const q = new TaskQueue();
    const worker = new Worker(q, { concurrency: 1 });
    const processed = [];
    worker.on('task', (task) => { processed.push(task.id); });
    worker.start();
    q.enqueue({ id: 't1', data: 'hello', priority: 1 });
    setTimeout(() => {
        assert.deepStrictEqual(processed, ['t1'], 'task t1 should be processed');
        worker.stop();
        resolve();
    }, 100);
});

// Test: Worker processes multiple tasks respecting concurrency
const testConcurrency = () => new Promise((resolve) => {
    const q = new TaskQueue();
    const worker = new Worker(q, { concurrency: 1 });
    const order = [];
    worker.on('task', (task) => { order.push(task.id); });
    worker.start();
    q.enqueue({ id: 't1', data: 'a', priority: 1 });
    q.enqueue({ id: 't2', data: 'b', priority: 1 });
    setTimeout(() => {
        assert.deepStrictEqual(order, ['t1', 't2'], 'tasks should be processed in order');
        worker.stop();
        resolve();
    }, 200);
});

// Test: Worker retries failed tasks up to retryCount
const testRetry = () => new Promise((resolve) => {
    const q = new TaskQueue();
    const worker = new Worker(q, { concurrency: 1, retryCount: 2 });
    let attempts = 0;
    worker.on('task', () => {
        attempts++;
        throw new Error('fail');
    });
    worker.on('failed', () => {
        assert.strictEqual(attempts, 3, 'should attempt initial + 2 retries = 3');
        worker.stop();
        resolve();
    });
    worker.start();
    q.enqueue({ id: 'retry-task', data: 'x', priority: 1 });
});

// Test: Worker emits 'completed' after a successful task
const testCompletedEvent = () => new Promise((resolve) => {
    const q = new TaskQueue();
    const worker = new Worker(q, { concurrency: 1 });
    let completedTask = null;
    worker.on('completed', (task) => { completedTask = task; });
    worker.start();
    q.enqueue({ id: 'done', data: 'ok', priority: 1 });
    setTimeout(() => {
        assert.ok(completedTask, 'completed event should fire');
        assert.strictEqual(completedTask.id, 'done');
        worker.stop();
        resolve();
    }, 100);
});

// Test: Worker does not process tasks before start is called
(function testNoAutoStart() {
    const q = new TaskQueue();
    const worker = new Worker(q, { concurrency: 1 });
    let processed = false;
    worker.on('task', () => { processed = true; });
    q.enqueue({ id: 't1', data: 'a', priority: 1 });
    assert.strictEqual(processed, false, 'task should not process before start');
    console.log('✓ no auto-start');
})();

// Run async tests sequentially
(async function runAsyncTests() {
    await testProcessTask();
    await testConcurrency();
    await testRetry();
    await testCompletedEvent();
    console.log('--- Worker Tests Passed ---');
})().catch((err) => {
    console.error('--- Worker Test Failed ---');
    console.error(err);
    process.exit(1);
});
