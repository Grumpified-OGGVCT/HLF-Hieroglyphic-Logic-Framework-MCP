/** @module Worker */

/**
 * @typedef {import('./queue').Task} Task
 */

/**
 * Event-driven concurrent task processor backed by a {@link TaskQueue}.
 *
 * @example
 * const worker = new Worker(queue, { concurrency: 4, retryCount: 2 });
 * worker.on('task_complete', ({ id }) => console.log('done', id));
 * worker.start();
 */
class Worker {
  /** @type {import('./queue').TaskQueue} */
  #queue;

  /** @type {number} */
  #concurrency;

  /** @type {number} */
  #retryCount;

  /** @type {boolean} */
  #running = false;

  /** @type {number} */
  #active = 0;

  /** @type {Map<string, Set<Function>>} */
  #events = new Map();

  /**
   * @param {import('./queue').TaskQueue} taskQueue
   * @param {object} options
   * @param {number} options.concurrency - Max tasks processed at once.
   * @param {number} options.retryCount - Retries before permanent failure.
   */
  constructor(taskQueue, { concurrency, retryCount }) {
    this.#queue = taskQueue;
    this.#concurrency = concurrency;
    this.#retryCount = retryCount;
  }

  /**
   * Begin consuming tasks from the queue.
   * @returns {Worker} this (chainable)
   */
  start() {
    if (this.#running) return this;
    this.#running = true;
    this.#poll();
    return this;
  }

  /**
   * Stop accepting new tasks; wait for in-flight tasks to finish.
   * @returns {Promise<void>}
   */
  stop() {
    this.#running = false;
    return this.#drain();
  }

  /**
   * Subscribe to worker events.
   * @param {'task_start'|'task_complete'|'task_error'} event
   * @param {Function} handler
   * @returns {Worker} this (chainable)
   */
  on(event, handler) {
    if (!this.#events.has(event)) this.#events.set(event, new Set());
    this.#events.get(event).add(handler);
    return this;
  }

  /** @param {string} event @param {*} payload */
  #emit(event, payload) {
    this.#events.get(event)?.forEach((fn) => {
      try { fn(payload); } catch { /* ignore handler errors */ }
    });
  }

  /** Continuously poll while running and under concurrency limit. */
  #poll() {
    while (this.#running && this.#active < this.#concurrency && this.#queue.size > 0) {
      const task = this.#queue.dequeue();
      if (!task) break;
      this.#active++;
      this.#run(task);
    }
  }

  /**
   * Execute a single task with retry logic.
   * @param {Task & { _retries?: number }} task
   */
  async #run(task) {
    this.#emit('task_start', task);

    try {
      const result =
        typeof task.data === 'function'
          ? await task.data()
          : task.data;

      this.#emit('task_complete', { task, result });
    } catch (error) {
      const retries = task._retries ?? 0;
      if (retries < this.#retryCount) {
        this.#queue.enqueue({ ...task, _retries: retries + 1 });
      } else {
        this.#emit('task_error', { task, error });
      }
    } finally {
      this.#active--;
      this.#poll();
    }
  }

  /** @returns {Promise<void>} */
  #drain() {
    return new Promise((resolve) => {
      const check = () => {
        if (this.#active === 0) return resolve();
        setImmediate(check);
      };
      check();
    });
  }
}

module.exports = { Worker };
