/**
 * @typedef {Object} Task
 * @property {string|number} id   - Unique task identifier
 * @property {*}               data - Arbitrary payload
 * @property {number}          priority - Higher values are processed first
 */

/**
 * Priority-based task queue.
 * Tasks are ordered by descending priority (highest first).
 * Stable for equal priorities (FIFO among ties).
 */
export class TaskQueue {
  /** @type {Task[]} */
  #tasks = [];

  /**
   * Add a task to the queue.
   * @param {Task} task
   * @returns {number} New queue size
   */
  enqueue(task) {
    if (!task || typeof task.priority !== 'number') {
      throw new TypeError('Task must have a numeric priority');
    }

    const idx = this.#tasks.findIndex(t => t.priority < task.priority);
    const insertAt = idx === -1 ? this.#tasks.length : idx;
    this.#tasks.splice(insertAt, 0, task);
    return this.#tasks.length;
  }

  /**
   * Remove and return the highest-priority task.
   * @returns {Task|undefined}
   */
  dequeue() {
    return this.#tasks.shift();
  }

  /**
   * Inspect the highest-priority task without removing it.
   * @returns {Task|undefined}
   */
  peek() {
    return this.#tasks[0];
  }

  /**
   * Current number of tasks.
   * @returns {number}
   */
  size() {
    return this.#tasks.length;
  }
}
