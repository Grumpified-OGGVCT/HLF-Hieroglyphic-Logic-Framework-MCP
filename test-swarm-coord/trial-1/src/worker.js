/**
 * @typedef {object} Task
 * @property {string|number} id
 * @property {*} data
 * @property {number} priority
 */

/**
 * @typedef {object} WorkerOptions
 * @property {number} concurrency
 * @property {number} retryCount
 */

/**
 * Generic worker that processes tasks from a priority queue with
 * configurable concurrency and retry behaviour.
 */
export class Worker {
  #queue;
  #concurrency;
  #retryCount;
  #handlers = new Map();
  #running = false;
  #intervalId = null;
  #inFlight = new Set();
  #retries = new WeakMap();
  #stopPromise = null;
  #stopResolve = null;

  /**
   * @param {object} taskQueue
   * @param {WorkerOptions} options
   */
  constructor(taskQueue, { concurrency, retryCount }) {
    if (!taskQueue || typeof taskQueue.dequeue !== 'function' || typeof taskQueue.enqueue !== 'function') {
      throw new TypeError('taskQueue must expose dequeue() and enqueue()');
    }
    if (!Number.isInteger(concurrency) || concurrency < 1) {
      throw new TypeError('concurrency must be a positive integer');
    }
    if (!Number.isInteger(retryCount) || retryCount < 0) {
      throw new TypeError('retryCount must be a non-negative integer');
    }
    this.#queue = taskQueue;
    this.#concurrency = concurrency;
    this.#retryCount = retryCount;
  }

  get queue() { return this.#queue; }
  get concurrency() { return this.#concurrency; }
  get retryCount() { return this.#retryCount; }

  /**
   * Subscribe to an event.
   * @param {string} event
   * @param {Function} handler
   */
  on(event, handler) {
    if (typeof handler !== 'function') {
      throw new TypeError('handler must be a function');
    }
    if (!this.#handlers.has(event)) {
      this.#handlers.set(event, new Set());
    }
    this.#handlers.get(event).add(handler);
  }

  /**
   * Emit an event to all registered handlers.
   * @private
   */
  #emit(event, ...args) {
    const handlers = this.#handlers.get(event);
    if (!handlers) return;
    for (const h of handlers) {
      try {
        h(...args);
      } catch {
        // ignore errors in handlers to avoid destabilizing the worker
      }
    }
  }

  /**
   * Start polling for tasks.
   */
  start() {
    if (this.#running) return;
    this.#running = true;
    this.#emit('started');
    this.#poll();
    this.#intervalId = setInterval(() => this.#poll(), 10);
  }

  /**
   * Stop accepting new tasks and return a Promise that resolves
   * when all in-flight tasks finish.
   * @returns {Promise<void>}
   */
  stop() {
    if (!this.#running) {
      this.#emit('stopped');
      return Promise.resolve();
    }
    this.#running = false;
    if (this.#intervalId) {
      clearInterval(this.#intervalId);
      this.#intervalId = null;
    }
    if (this.#inFlight.size === 0) {
      this.#emit('stopped');
      return Promise.resolve();
    }
    if (!this.#stopPromise) {
      this.#stopPromise = new Promise((resolve) => {
        this.#stopResolve = resolve;
      });
    }
    return this.#stopPromise;
  }

  /**
   * Attempt to fill available concurrency slots.
   * @private
   */
  #poll() {
    while (this.#running && this.#inFlight.size < this.#concurrency) {
      const task = this.#queue.dequeue();
      if (!task) break;
      this.#process(task);
    }
  }

  /**
   * Process a single task with retry tracking.
   * @private
   * @param {Task} task
   */
  async #process(task) {
    const attempt = (this.#retries.get(task) || 0) + 1;
    this.#inFlight.add(task);
    this.#emit('task_start', { task, attempt });
    this.#emit('task', task);

    try {
      const results = await this.#executeHandlers(task);
      this.#inFlight.delete(task);
      this.#emit('task_complete', { task, result: results.length === 1 ? results[0] : results, attempt });
      this.#emit('completed', task);
      this.#checkStopped();
      this.#poll();
    } catch (error) {
      this.#inFlight.delete(task);
      const retries = this.#retries.get(task) || 0;
      if (retries < this.#retryCount) {
        this.#retries.set(task, retries + 1);
        this.#queue.enqueue(task);
      } else {
        this.#emit('task_error', { task, error, attempt });
        this.#emit('failed', task, error);
      }
      this.#checkStopped();
      this.#poll();
    }
  }

  /**
   * Run all handlers for the 'task' event and propagate errors.
   * @private
   * @param {Task} task
   * @returns {Promise<Array<*>>}
   */
  async #executeHandlers(task) {
    const handlers = this.#handlers.get('task');
    if (!handlers || handlers.size === 0) {
      throw new Error('No task handler registered');
    }
    const promises = [];
    for (const h of handlers) {
      promises.push(Promise.resolve().then(() => h(task)));
    }
    return Promise.all(promises);
  }

  /**
   * Resolve the stop Promise if no tasks remain.
   * @private
   */
  #checkStopped() {
    if (!this.#running && this.#inFlight.size === 0 && this.#stopResolve) {
      this.#stopResolve();
      this.#stopResolve = null;
      this.#stopPromise = null;
      this.#emit('stopped');
    }
  }
}
