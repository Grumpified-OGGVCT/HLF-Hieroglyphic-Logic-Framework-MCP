/**
 * @typedef {object} Task
 * @property {string} id - Unique task identifier
 * @property {unknown} data - Payload for the task
 * @property {number} priority - Higher value means higher priority (dequeued first)
 */

/**
 * Priority-based task queue.
 * Backed by a binary max-heap for O(log n) enqueue/dequeue.
 */
export class TaskQueue {
  /** @type {Task[]} */
  #heap = [];

  /**
   * Add a task to the queue.
   * @param {Task} task
   * @returns {void}
   */
  enqueue(task) {
    this.#heap.push(task);
    this.#siftUp(this.#heap.length - 1);
  }

  /**
   * Remove and return the highest-priority task.
   * @returns {Task | undefined}
   */
  dequeue() {
    if (this.#heap.length === 0) return undefined;
    const max = this.#heap[0];
    const end = this.#heap.pop();
    if (this.#heap.length > 0 && end !== undefined) {
      this.#heap[0] = end;
      this.#siftDown(0);
    }
    return max;
  }

  /**
   * View the highest-priority task without removing it.
   * @returns {Task | undefined}
   */
  peek() {
    return this.#heap[0];
  }

  /**
   * Number of tasks in the queue.
   * @returns {number}
   */
  size() {
    return this.#heap.length;
  }

  /** @param {number} idx */
  #siftUp(idx) {
    const task = this.#heap[idx];
    while (idx > 0) {
      const parent = (idx - 1) >>> 1;
      if (this.#heap[parent].priority >= task.priority) break;
      this.#heap[idx] = this.#heap[parent];
      idx = parent;
    }
    this.#heap[idx] = task;
  }

  /** @param {number} idx */
  #siftDown(idx) {
    const task = this.#heap[idx];
    const len = this.#heap.length;
    const half = len >>> 1;
    while (idx < half) {
      let child = (idx << 1) + 1;
      const right = child + 1;
      if (right < len && this.#heap[right].priority > this.#heap[child].priority) {
        child = right;
      }
      if (this.#heap[child].priority <= task.priority) break;
      this.#heap[idx] = this.#heap[child];
      idx = child;
    }
    this.#heap[idx] = task;
  }
}
