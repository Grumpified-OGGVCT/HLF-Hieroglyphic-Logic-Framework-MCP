/**
 * @typedef {Object} Task
 * @property {string|number} id
 * @property {*} data
 * @property {number} priority
 */

/**
 * @typedef {Object} WorkerOptions
 * @property {number} [concurrency=1] - Max concurrent tasks.
 * @property {number} [retryCount=0] - Additional retries after initial failure.
 */

/**
 * A concurrent task worker that pulls from a {@link TaskQueue}.
 *
 * Tasks are executed by event handlers registered via `on('task', handler)`.
 * Any thrown error (sync or async) is treated as a task failure. Failed tasks
 * are transparently re-enqueued up to `retryCount` times.
 *
 * @example
 * const worker = new Worker(queue, { concurrency: 4, retryCount: 2 });
 * worker.on('task', (task) => console.log(task.id));
 * worker.start();
 */
class Worker {
  #taskQueue;
  #concurrency;
  #retryCount;
  #running = false;
  #stopping = false;
  #inFlight = new Set();
  #handlers = new Map();
  #retryMap = new WeakMap();
  #pollTimer = null;
  #stopResolve = null;
  #pollInterval = 10;

  /**
   * @param {TaskQueue} taskQueue
   * @param {WorkerOptions} [options]
   */
  constructor(taskQueue, options = {}) {
    this.#taskQueue = taskQueue;
    this.#concurrency = options.concurrency ?? 1;
    this.#retryCount = options.retryCount ?? 0;
  }

  /** @returns {TaskQueue} */
  get queue() {
    return this.#taskQueue;
  }

  /** @returns {number} */
  get concurrency() {
    return this.#concurrency;
  }

  /** @returns {number} */
  get retryCount() {
    return this.#retryCount;
  }

  /**
   * Subscribe to a worker event.
   *
   * @param {string} event
   * @param {Function} handler
   */
  on(event, handler) {
    if (!this.#handlers.has(event)) {
      this.#handlers.set(event, new Set());
    }
    this.#handlers.get(event).add(handler);
  }

  /**
   * @param {string} event
   * @param {...*} args
   * @returns {Promise<*>} Last handler's return value.
   */
  async #emit(event, ...args) {
    const handlers = this.#handlers.get(event);
    if (!handlers) return;
    let last;
    for (const handler of handlers) {
      last = await handler(...args);
    }
    return last;
  }

  /** Begin polling for and processing tasks. */
  start() {
    if (this.#running) return;
    this.#running = true;
    this.#stopping = false;
    this.#emit('started');
    this.#poll();
  }

  /**
   * Stop accepting new tasks and wait for in-flight work to finish.
   *
   * @returns {Promise<void>}
   */
  stop() {
    if (!this.#running || this.#stopping) {
      return Promise.resolve();
    }

    this.#stopping = true;
    this.#clearPollTimer();

    if (this.#inFlight.size === 0) {
      this.#running = false;
      this.#stopping = false;
      this.#emit('stopped');
      return Promise.resolve();
    }

    return new Promise((resolve) => {
      this.#stopResolve = resolve;
    });
  }

  /** @private */
  #poll() {
    if (!this.#running || this.#stopping) return;
    this.#clearPollTimer();

    while (this.#inFlight.size < this.#concurrency) {
      const task = this.#taskQueue.dequeue();
      if (!task) break;
      this.#processTask(task);
    }

    if (this.#running && !this.#stopping) {
      this.#pollTimer = setTimeout(() => this.#poll(), this.#pollInterval);
    }
  }

  /** @private */
  #clearPollTimer() {
    if (this.#pollTimer) {
      clearTimeout(this.#pollTimer);
      this.#pollTimer = null;
    }
  }

  /**
   * @param {Task} task
   * @private
   */
  async #processTask(task) {
    this.#inFlight.add(task);
    const attempt = (this.#retryMap.get(task) ?? 0) + 1;

    try {
      this.#emit('task_start', { task, attempt });
      const result = await this.#emit('task', task);
      this.#emit('completed', task);
      this.#emit('task_complete', { task, result, attempt });
      this.#retryMap.delete(task);
    } catch (error) {
      const currentRetries = this.#retryMap.get(task) ?? 0;
      if (currentRetries < this.#retryCount) {
        this.#retryMap.set(task, currentRetries + 1);
        this.#taskQueue.enqueue(task);
      } else {
        this.#emit('failed', task, error);
        this.#emit('task_error', { task, error, attempt });
        this.#retryMap.delete(task);
      }
    } finally {
      this.#inFlight.delete(task);
      if (this.#running && !this.#stopping) {
        this.#poll();
      }
      this.#checkStopped();
    }
  }

  /** @private */
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

module.exports = Worker;
module.exports.Worker = Worker;
