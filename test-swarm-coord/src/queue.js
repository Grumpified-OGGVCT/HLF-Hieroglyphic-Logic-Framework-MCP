/**
 * @typedef {Object} Task
 * @property {string|number} id - Unique identifier for the task.
 * @property {*} data - The payload or data associated with the task.
 * @property {number} priority - Priority value; higher numbers are dequeued first.
 */

/**
 * A priority-based task queue.
 *
 * Implements a binary max-heap internally so that `enqueue` and `dequeue`
 * both run in O(log n) time. Tasks with a higher `priority` value are
 * returned first. When priorities are equal, FIFO ordering is preserved
 * via an internal monotonic counter.
 *
 * @example
 * const queue = new TaskQueue();
 * queue.enqueue({ id: 'a', data: { x: 1 }, priority: 5 });
 * queue.enqueue({ id: 'b', data: { x: 2 }, priority: 10 });
 * queue.dequeue(); // => task 'b'
 */
class TaskQueue {
  /** @type {Array<{ task: Task, seq: number }>} */
  #heap = [];

  /** @type {number} */
  #seq = 0;

  /**
   * Adds a task to the queue.
   *
   * @param {Task} task - The task to enqueue.
   * @throws {TypeError} If `task` is missing `id` or `priority`.
   */
  enqueue(task) {
    if (task == null || typeof task.id === 'undefined') {
      throw new TypeError('Task must have an "id" property');
    }
    if (typeof task.priority !== 'number' || Number.isNaN(task.priority)) {
      throw new TypeError('Task must have a numeric "priority" property');
    }

    const node = { task, seq: this.#seq++ };
    this.#heap.push(node);
    this.#siftUp(this.#heap.length - 1);
  }

  /**
   * Removes and returns the highest-priority task.
   *
   * @returns {Task|undefined} The next task, or `undefined` if the queue is empty.
   */
  dequeue() {
    if (this.#heap.length === 0) return undefined;

    const max = this.#heap[0].task;
    const end = this.#heap.pop();

    if (this.#heap.length > 0) {
      this.#heap[0] = end;
      this.#siftDown(0);
    }

    return max;
  }

  /**
   * Returns the highest-priority task without removing it.
   *
   * @returns {Task|undefined} The next task, or `undefined` if the queue is empty.
   */
  peek() {
    return this.#heap.length > 0 ? this.#heap[0].task : undefined;
  }

  /**
   * Returns the number of tasks currently in the queue.
   *
   * @returns {number}
   */
  size() {
    return this.#heap.length;
  }

  /* ---------- private heap helpers ---------- */

  /**
   * @param {number} i
   * @param {number} j
   */
  #swap(i, j) {
    [this.#heap[i], this.#heap[j]] = [this.#heap[j], this.#heap[i]];
  }

  /**
   * @param {number} idx
   * @returns {number}
   */
  #parent(idx) {
    return Math.floor((idx - 1) / 2);
  }

  /**
   * @param {number} idx
   * @returns {number}
   */
  #leftChild(idx) {
    return 2 * idx + 1;
  }

  /**
   * @param {number} idx
   * @returns {number}
   */
  #rightChild(idx) {
    return 2 * idx + 2;
  }

  /**
   * @param {number} a
   * @param {number} b
   * @returns {boolean}
   */
  #hasHigherPriority(a, b) {
    if (this.#heap[a].task.priority !== this.#heap[b].task.priority) {
      return this.#heap[a].task.priority > this.#heap[b].task.priority;
    }
    return this.#heap[a].seq < this.#heap[b].seq;
  }

  /**
   * @param {number} idx
   */
  #siftUp(idx) {
    while (idx > 0) {
      const p = this.#parent(idx);
      if (this.#hasHigherPriority(p, idx)) break;
      this.#swap(idx, p);
      idx = p;
    }
  }

  /**
   * @param {number} idx
   */
  #siftDown(idx) {
    const len = this.#heap.length;
    while (true) {
      const l = this.#leftChild(idx);
      const r = this.#rightChild(idx);
      let largest = idx;

      if (l < len && this.#hasHigherPriority(l, largest)) largest = l;
      if (r < len && this.#hasHigherPriority(r, largest)) largest = r;

      if (largest === idx) break;
      this.#swap(idx, largest);
      idx = largest;
    }
  }
}

module.exports = { TaskQueue };
