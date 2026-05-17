/**
 * @typedef {Object} Task
 * @property {string|number} id
 * @property {*} data
 * @property {number} priority
 */

/**
 * @typedef {Object} WorkerOptions
 * @property {number} [concurrency=1]
 * @property {number} [retryCount=0]
 */

/**
 * Pulls tasks from a TaskQueue and executes them concurrently.
 * Tasks are run by handlers registered via `on('task', handler)`.
 * Failed tasks are retried up to `retryCount` times.
 */
class Worker {
  #queue;
  #concurrency;
  #retryCount;
  #running = false;
  #stopping = false;
  #inFlight = new Set();
  #handlers = new Map();
  #retries = new WeakMap();
  #pollTimer = null;
  #stopResolve = null;
  #pollMs = 10;

  /**
   * @param {TaskQueue} taskQueue
   * @param {WorkerOptions} [options]
   */
  constructor(taskQueue, options = {}) {
    this.#queue = taskQueue;
    this.#concurrency = options.concurrency ?? 1;
    this.#retryCount = options.retryCount ?? 0;
  }

  get queue() { return this.#queue; }
  get concurrency() { return this.#concurrency; }
  get retryCount() { return this.#retryCount; }

  /**
   * Subscribe to a worker event.
   * @param {string} event
   * @param {Function} handler
   */
  on(event, handler) {
    if (!this.#handlers.has(event)) {
      this.#handlers.set(event, new Set());
    }
    this.#handlers.get(event).add(handler);
  }

  /** @param {string} event @param {...*} args */
  async #emit(event, ...args) {
    const set = this.#handlers.get(event);
    if (!set) return;
    let last;
    for (const fn of set) {
      last = await fn(...args);
    }
    return last;
  }

  /** Begin polling and processing tasks. */
  start() {
    if (this.#running) return;
    this.#running = true;
    this.#stopping = false;
    this.#emit('started');
    this.#poll();
  }

  /**
   * Stop accepting new tasks. Resolves when in-flight tasks finish.
   * @returns {Promise<void>}
   */
  stop() {
    if (!this.#running || this.#stopping) return Promise.resolve();
    this.#stopping = true;
    this.#clearPollTimer();
    if (this.#inFlight.size === 0) {
      this.#running = false;
      this.#stopping = false;
      this.#emit('stopped');
      return Promise.resolve();
    }
    return new Promise((resolve) => { this.#stopResolve = resolve; });
  }

  #poll() {
    if (!this.#running || this.#stopping) return;
    this.#clearPollTimer();
    while (this.#inFlight.size < this.#concurrency) {
      const task = this.#queue.dequeue();
      if (!task) break;
      this.#processTask(task);
    }
    if (this.#running && !this.#stopping) {
      this.#pollTimer = setTimeout(() => this.#poll(), this.#pollMs);
    }
  }

  #clearPollTimer() {
    if (this.#pollTimer) {
      clearTimeout(this.#pollTimer);
      this.#pollTimer = null;
    }
  }

  /** @param {Task} task */
  async #processTask(task) {
    this.#inFlight.add(task);
    const attempt = (this.#retries.get(task) ?? 0) + 1;
    try {
      this.#emit('task_start', { task, attempt });
      const result = await this.#emit('task', task);
      this.#emit('completed', task);
      this.#emit('task_complete', { task, result, attempt });
      this.#retries.delete(task);
    } catch (error) {
      const current = this.#retries.get(task) ?? 0;
      if (current < this.#retryCount) {
        this.#retries.set(task, current + 1);
        this.#queue.enqueue(task);
      } else {
        this.#emit('failed', task, error);
        this.#emit('task_error', { task, error, attempt });
        this.#retries.delete(task);
      }
    } finally {
      this.#inFlight.delete(task);
      if (this.#running && !this.#stopping) this.#poll();
      this.#checkStopped();
    }
  }

  #checkStopped() {
    if (this.#stopping && this.#inFlight.size === 0) {
      this.#running = false;
      this.#stopping = false;
      this.#emit('stopped');
      if (this.#stopResolve) {
        this.#stopResolve();
        this.#stopResolve = null;
      }
    }
  }
}

export { Worker };
export default Worker;
