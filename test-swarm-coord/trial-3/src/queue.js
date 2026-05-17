/** @module TaskQueue */

/**
 * @typedef {object} Task
 * @property {string} id   - Unique task identifier.
 * @property {*}      data - Arbitrary payload.
 * @property {number} [priority=0] - Higher number = processed first.
 */

/**
 * Priority queue for tasks. Higher priority values are dequeued first.
 * FIFO order is preserved among tasks with equal priority.
 */
class TaskQueue {
  /** @type {Task[]} */
  #tasks = [];

  /**
   * Add a task to the queue.
   * @param {Task} task
   * @returns {TaskQueue} this (chainable)
   */
  enqueue(task) {
    const t = { priority: 0, ...task };
    const idx = this.#tasks.findIndex(x => x.priority < t.priority);
    this.#tasks.splice(idx === -1 ? this.#tasks.length : idx, 0, t);
    return this;
  }

  /** Remove and return the highest-priority task.
   * @returns {Task | undefined}
   */
  dequeue() {
    return this.#tasks.shift();
  }

  /** View the highest-priority task without removing it.
   * @returns {Task | undefined}
   */
  peek() {
    return this.#tasks[0];
  }

  /** @returns {number} Number of tasks in the queue. */
  get size() {
    return this.#tasks.length;
  }
}

module.exports = { TaskQueue };
