/**
 * @typedef {Object} Task
 * @property {string|number} id
 * @property {*} data
 * @property {number} priority
 */

/**
 * @typedef {Object} TaskStartEvent
 * @property {Task} task
 */

/**
 * @typedef {Object} TaskCompleteEvent
 * @property {Task} task
 * @property {*} result
 */

/**
 * @typedef {Object} TaskErrorEvent
 * @property {Task} task
 * @property {Error} error
 */

/**
 * A concurrent worker that consumes tasks from a {@link TaskQueue}.
 *
 * Emits lifecycle events for each task and supports configurable
 * concurrency and retry behaviour.
 */
export class Worker {
  #taskQueue;
  #concurrency;
  #retryCount;
  #running = 0;
  #stopped = true;
  #loopActive = false;
  #handlers = new Map();

  /**
   * @param {Object} taskQueue - Queue instance with `dequeue()` and `enqueue()`.
   * @param {Object} options
   * @param {number} [options.concurrency=1] - Max simultaneous tasks.
   * @param {number} [options.retryCount=0] - Max retries per failed task.
   */
  constructor(taskQueue, { concurrency = 1, retryCount = 0 } = {}) {
    if (!taskQueue || typeof taskQueue.dequeue !== 'function') {
      throw new TypeError('taskQueue must have a dequeue() method');
    }
    this.#taskQueue = taskQueue;
    this.#concurrency = Math.max(1, concurrency);
    this.#retryCount = Math.max(0, retryCount);
  }

  /**
   * Register an event handler.
   *
   * @param {'task_start'|'task_complete'|'task_error'} event
   * @param {Function} handler
   * @returns {this}
   */
  on(event, handler) {
    if (!['task_start', 'task_complete', 'task_error'].includes(event)) {
      throw new TypeError(`Unknown event: ${event}`);
    }
    if (typeof handler !== 'function') {
      throw new TypeError('handler must be a function');
    }
    if (!this.#handlers.has(event)) {
      this.#handlers.set(event, []);
    }
    this.#handlers.get(event).push(handler);
    return this;
  }

  /**
   * Start consuming tasks from the queue.
   *
   * @returns {this}
   */
  start() {
    if (this.#loopActive) return this;
    this.#stopped = false;
    this.#loopActive = true;
    this.#loop().catch(() => {}).finally(() => {
      this.#loopActive = false;
    });
    return this;
  }

  /**
   * Stop accepting new tasks. In-flight tasks are allowed to finish.
   *
   * @returns {this}
   */
  stop() {
    this.#stopped = true;
    return this;
  }

  #emit(event, payload) {
    const list = this.#handlers.get(event);
    if (!list) return;
    for (const fn of list) {
      try {
        fn(payload);
      } catch {
        /* handler errors are ignored */
      }
    }
  }

  async #loop() {
    while (!this.#stopped) {
      if (this.#running >= this.#concurrency) {
        await new Promise(r => setTimeout(r, 10));
        continue;
      }

      const task = this.#taskQueue.dequeue();
      if (!task) {
        await new Promise(r => setTimeout(r, 50));
        continue;
      }

      this.#running++;
      this.#process(task);
    }
  }

  async #process(task) {
    this.#emit('task_start', { task });

    try {
      const result = await this.#execute(task);
      this.#emit('task_complete', { task, result });
    } catch (error) {
      const retries = task._retries ?? 0;
      if (retries < this.#retryCount) {
        task._retries = retries + 1;
        this.#taskQueue.enqueue(task);
      } else {
        this.#emit('task_error', { task, error });
      }
    } finally {
      this.#running--;
    }
  }

  async #execute(task) {
    if (typeof task.data === 'function') {
      return await task.data();
    }
    return task.data;
  }
}
