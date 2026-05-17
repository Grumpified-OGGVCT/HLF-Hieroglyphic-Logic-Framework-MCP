const assert = require('assert');
const { TaskQueue } = require('../src/queue');
const { Worker } = require('../src/worker');

function test(name, fn) {
  try { fn(); console.log(`  ✔ ${name}`); }
  catch (e) { console.error(`  ✘ ${name}: ${e.message}`); process.exitCode = 1; }
}

console.log('worker.test.js');

test('constructor stores options', () => {
  const q = new TaskQueue();
  const w = new Worker(q, { concurrency: 3, retryCount: 2 });
  assert.ok(w);
});

test('start returns this (chainable)', () => {
  const q = new TaskQueue();
  const w = new Worker(q, { concurrency: 1, retryCount: 0 });
  assert.strictEqual(w.start(), w);
});

test('no auto-start', () => {
  const q = new TaskQueue();
  q.enqueue({ id: 'a', data: () => 'done' });
  new Worker(q, { concurrency: 1, retryCount: 0 });
  assert.strictEqual(q.size, 1);
});

async function runWorkerTests() {
  await (async () => {
    const q = new TaskQueue();
    const events = [];
    q.enqueue({ id: 'a', data: () => 'result' });
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    w.on('task_start', (t) => events.push({ type: 'start', id: t.id }));
    w.on('task_complete', (p) => events.push({ type: 'complete', id: p.task.id, result: p.result }));
    w.start();
    await w.stop();
    assert.strictEqual(events.length, 2);
    assert.strictEqual(events[0].type, 'start');
    assert.strictEqual(events[1].type, 'complete');
    assert.strictEqual(events[1].result, 'result');
    console.log('  ✔ events: task_start and task_complete');
  })();

  await (async () => {
    const q = new TaskQueue();
    const errors = [];
    q.enqueue({ id: 'fail', data: () => { throw new Error('boom'); } });
    const w = new Worker(q, { concurrency: 1, retryCount: 0 });
    w.on('task_error', (p) => errors.push({ id: p.task.id, error: p.error.message }));
    w.start();
    await w.stop();
    assert.strictEqual(errors.length, 1);
    assert.strictEqual(errors[0].id, 'fail');
    assert.strictEqual(errors[0].error, 'boom');
    console.log('  ✔ events: task_error');
  })();

  await (async () => {
    const q = new TaskQueue();
    let running = 0;
    let maxRunning = 0;
    for (let i = 0; i < 5; i++) {
      q.enqueue({ id: String(i), data: async () => {
        running++;
        maxRunning = Math.max(maxRunning, running);
        await new Promise(r => setTimeout(r, 20));
        running--;
      } });
    }
    const w = new Worker(q, { concurrency: 2, retryCount: 0 });
    w.start();
    await w.stop();
    assert.strictEqual(maxRunning, 2);
    console.log('  ✔ concurrency limit respected');
  })();

  await (async () => {
    const q = new TaskQueue();
    let attempts = 0;
    q.enqueue({ id: 'retry', data: () => { attempts++; throw new Error('nope'); } });
    const w = new Worker(q, { concurrency: 1, retryCount: 2 });
    w.start();
    await w.stop();
    assert.strictEqual(attempts, 3);
    console.log('  ✔ retry logic: 1 attempt + 2 retries');
  })();

  await (async () => {
    const q = new TaskQueue();
    let attempts = 0;
    q.enqueue({ id: 'retry', data: () => { attempts++; if (attempts < 2) throw new Error('nope'); return 'ok'; } });
    const completions = [];
    const w = new Worker(q, { concurrency: 1, retryCount: 2 });
    w.on('task_complete', (p) => completions.push(p.result));
    w.start();
    await w.stop();
    assert.strictEqual(attempts, 2);
    assert.deepStrictEqual(completions, ['ok']);
    console.log('  ✔ retry then success');
  })();
}

runWorkerTests().catch(e => { console.error(e); process.exitCode = 1; });
