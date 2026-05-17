/**
 * A priority-based task queue for managing asynchronous work.
 *
 * Higher numeric priority values are dequeued first.
 * Tasks with equal priority are handled in FIFO order.
 */
export class TaskQueue {
  #heap = [];

  /**
   * Add a task to the queue.
   *
   * @param {Object} task
   * @param {string|number} task.id
   * @param {*} task.data
   * @param {number} task.priority
   * @returns {void}
   */
  enqueue(task) {
    if (!task || typeof task.priority !== 'number') {
      throw new TypeError('Task must have a numeric priority');
    }
    this.#heap.push({ ...task, _seq: this.#heap.length });
    this.#siftUp(this.#heap.length - 1);
  }

  /**
   * Remove and return the highest-priority task.
   *
   * @returns {Object|null} The task object or null if empty.
   */
  dequeue() {
    if (this.#heap.length === 0) return null;
    const root = this.#heap[0];
    const last = this.#heap.pop();
    if (this.#heap.length > 0) {
      this.#heap[0] = last;
      this.#siftDown(0);
    }
    return root ?? null;
  }

  /**
   * View the highest-priority task without removing it.
   *
   * @returns {Object|null}
   */
  peek() {
    return this.#heap[0] ?? null;
  }

  /**
   * Number of tasks in the queue.
   *
   * @returns {number}
   */
  size() {
    return this.#heap.length;
  }

  // --- internal heap helpers ---

  #siftUp(i) {
    const node = this.#heap[i];
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (this.#compare(node, this.#heap[parent]) > 0) {
        this.#heap[i] = this.#heap[parent];
        i = parent;
      } else {
        break;
      }
    }
    this.#heap[i] = node;
  }

  #siftDown(i) {
    const node = this.#heap[i];
    const len = this.#heap.length;
    const half = len >> 1;
    while (i < half) {
      let child = (i << 1) + 1;
      const right = child + 1;
      if (right < len && this.#compare(this.#heap[right], this.#heap[child]) > 0) {
        child = right;
      }
      if (this.#compare(this.#heap[child], node) > 0) {
        this.#heap[i] = this.#heap[child];
        i = child;
      } else {
        break;
      }
    }
    this.#heap[i] = node;
  }

  #compare(a, b) {
    if (a.priority !== b.priority) return a.priority - b.priority;
    return b._seq - a._seq;
  }
}
