const assert = require('assert');
const { TaskQueue } = require('../src/queue');
const { Worker } = require('../src/worker');

console.log('--- Worker Tests ---');

(function testConstructor() {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 3, retryCount: 2 });
    assert.strictEqual(w.queue, q);
    assert.strictEqual(w.concurrency, 3);
    assert.strictEqual(w.retryCount, 2);
    console.log('✓ constructor');
})();

(function testNoAutoStart() {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    let processed = false;
    w.on('task', () => { processed = true; });
    q.enqueue({ id: 't1', data: 'a', priority: 1 });
    assert.strictEqual(processed, false);
    console.log('✓ no auto-start');
})();

const testStartStopEvents = () => new Promise((resolve) => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    let started = false;
    let stopped = false;
    w.on('started', () => { started = true; });
    w.on('stopped', () => { stopped = true; });
    w.start();
    assert.strictEqual(started, true);
    setTimeout(() => {
        w.stop().then(() => {
            assert.strictEqual(stopped, true);
            console.log('✓ start/stop events');
            resolve();
        });
    }, 50);
});

const testProcessTask = () => new Promise((resolve) => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    const completed = [];
    w.on('task', () => {});
    w.on('completed', (task) => { completed.push(task.id); });
    w.start();
    q.enqueue({ id: 't1', data: 'hello', priority: 1 });
    setTimeout(() => {
        assert.deepStrictEqual(completed, ['t1']);
        w.stop();
        console.log('✓ process task');
        resolve();
    }, 100);
});

const testConcurrency = () => new Promise((resolve) => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 2, retryCount: 0 });
    const completed = new Set();
    w.on('task', () => {});
    w.on('completed', (task) => { completed.add(task.id); });
    w.start();
    q.enqueue({ id: 'a', data: 1, priority: 1 });
    q.enqueue({ id: 'b', data: 2, priority: 1 });
    setTimeout(() => {
        assert.strictEqual(completed.has('a'), true);
        assert.strictEqual(completed.has('b'), true);
        w.stop();
        console.log('✓ concurrency');
        resolve();
    }, 150);
});

const testRetry = () => new Promise((resolve) => {
    const q = new TaskQueue();
    const w = new Worker(q, { concurrency: 1, retryCount: 2 });
    w.on('task', () => { throw new Error('fail'); });
    w.on('failed', () => {
        w.stop();
        console.log('✓ retry');
        resolve();
    });
    w.start();
    q.enqueue({ id: 'r1', data: 'x', priority: 1 });
});

(async function run() {
    await testStartStopEvents();
    await testProcessTask();
    await testConcurrency();
    await testRetry();
    console.log('--- Worker Tests Passed ---');
})().catch((err) => {
    console.error('--- Worker Test Failed ---');
    console.error(err);
    process.exit(1);
});
