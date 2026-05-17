/**
 * @typedef {import('./queue.js').Task} Task
 */

/**
 * @typedef {(payload: unknown) => void} EventHandler
 */

/**
 * Worker that pulls tasks from a {@link TaskQueue} and executes them
 * concurrently with retry support.
 */
export class Worker {
  /** @type {import('./queue.js').TaskQueue} */
  #taskQueue;
  /** @type {number} */
  #concurrency;
  /** @type {number} */
  #retryCount;
  /** @type {Map<string, EventHandler[]>} */
  #handlers = new Map();
  /** @type {number} */
  #running = 0;
  /** @type {boolean} */
  #active = false;
  /** @type {Map<string, number>} */
  #retries = new Map();

  /**
   * @param {import('./queue.js').TaskQueue} taskQueue
   * @param {object} options
   * @param {number} options.concurrency
   * @param {number} options.retryCount
   */
  constructor(taskQueue, { concurrency, retryCount }) {
    if (concurrency < 1) throw new RangeError('concurrency must be >= 1');
    if (retryCount < 0) throw new RangeError('retryCount must be >= 0');
    this.#taskQueue = taskQueue;
    this.#concurrency = concurrency;
    this.#retryCount = retryCount;
  }

  /**
   * Register an event handler.
   * @param {'task_start' | 'task_complete' | 'task_error'} event
   * @param {EventHandler} handler
   * @returns {void}
   */
  on(event, handler) {
    const list = this.#handlers.get(event) ?? [];
    list.push(handler);
    this.#handlers.set(event, list);
  }

  /** @param {string} event @param {unknown} payload */
  #emit(event, payload) {
    for (const h of this.#handlers.get(event) ?? []) {
      h(payload);
    }
  }

  /** @param {Task} task */
  async #execute(task) {
    if (typeof task.data === 'function') {
      return task.data();
    }
    return task.data;
  }

  /** @returns {Promise<void>} */
  async #loop() {
    while (this.#active) {
      if (this.#taskQueue.size() === 0) {
        await new Promise(r => setTimeout(r, 50));
        continue;
      }

      const task = this.#taskQueue.dequeue();
      if (!task) continue;

      this.#running++;
      this.#emit('task_start', task);

      try {
        const result = await this.#execute(task);
        this.#emit('task_complete', { task, result });
        this.#retries.delete(task.id);
      } catch (error) {
        const attempts = (this.#retries.get(task.id) ?? 0) + 1;
        if (attempts <= this.#retryCount) {
          this.#retries.set(task.id, attempts);
          this.#taskQueue.enqueue(task);
        } else {
          this.#retries.delete(task.id);
          this.#emit('task_error', { task, error });
        }
      } finally {
        this.#running--;
      }
    }
  }

  /** Start consuming and processing tasks. */
  start() {
    if (this.#active) return;
    this.#active = true;
    for (let i = 0; i < this.#concurrency; i++) {
      this.#loop();
    }
  }

  /**
   * Stop accepting new tasks and wait for in-flight tasks to finish.
   * @returns {Promise<void>}
   */
  async stop() {
    this.#active = false;
    while (this.#running > 0) {
      await new Promise(r => setTimeout(r, 50));
    }
  }
}
