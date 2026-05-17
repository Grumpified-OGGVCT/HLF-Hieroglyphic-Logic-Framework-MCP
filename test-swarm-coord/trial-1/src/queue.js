/**
 * @typedef {Object} Task
 * @property {string} id
 * @property {*} data
 * @property {number} priority
 */

/** Priority queue for tasks. Higher priority values are dequeued first. */
class TaskQueue {
  /** @type {Task[]} */
  #heap = [];

  /** @returns {number} */
  size() {
    return this.#heap.length;
  }

  /** @param {Task} task */
  enqueue(task) {
    this.#heap.push(task);
    this.#bubbleUp(this.#heap.length - 1);
  }

  /** @returns {Task | undefined} */
  dequeue() {
    if (this.#heap.length === 0) return undefined;
    const top = this.#heap[0];
    const last = this.#heap.pop();
    if (this.#heap.length > 0 && last !== undefined) {
      this.#heap[0] = last;
      this.#sinkDown(0);
    }
    return top;
  }

  /** @returns {Task | undefined} */
  peek() {
    return this.#heap[0];
  }

  /** @param {number} i */
  #bubbleUp(i) {
    const task = this.#heap[i];
    while (i > 0) {
      const p = (i - 1) >>> 1;
      if (this.#heap[p].priority >= task.priority) break;
      this.#heap[i] = this.#heap[p];
      i = p;
    }
    this.#heap[i] = task;
  }

  /** @param {number} i */
  #sinkDown(i) {
    const task = this.#heap[i];
    const n = this.#heap.length;
    while (true) {
      const l = (i << 1) + 1;
      if (l >= n) break;
      const r = l + 1;
      const child =
        r < n && this.#heap[r].priority > this.#heap[l].priority ? r : l;
      if (this.#heap[child].priority <= task.priority) break;
      this.#heap[i] = this.#heap[child];
      i = child;
    }
    this.#heap[i] = task;
  }
}

module.exports = { TaskQueue };
