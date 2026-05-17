const InventoryService = class InventoryService {
  constructor() {
    this.stock = new Map();
  }

  /**
   * Get current stock level for an item.
   * @param {string} itemId
   * @returns {number}
   */
  getStock(itemId) {
    return this.stock.get(itemId) || 0;
  }

  /**
   * Add stock for an item.
   * @param {string} itemId
   * @param {number} quantity
   * @returns {number} new stock level
   */
  addStock(itemId, quantity) {
    if (quantity < 0) throw new Error('Quantity must be non-negative');
    const current = this.getStock(itemId);
    this.stock.set(itemId, current + quantity);
    return this.stock.get(itemId);
  }

  /**
   * Remove stock for an item.
   * @param {string} itemId
   * @param {number} quantity
   * @returns {number} new stock level
   * @throws {Error} if insufficient stock
   */
  removeStock(itemId, quantity) {
    if (quantity < 0) throw new Error('Quantity must be non-negative');
    const current = this.getStock(itemId);
    if (current < quantity) throw new Error('Insufficient stock');
    this.stock.set(itemId, current - quantity);
    return this.stock.get(itemId);
  }

  /**
   * Check if an item is in stock (above zero).
   * @param {string} itemId
   * @returns {boolean}
   */
  isInStock(itemId) {
    return this.getStock(itemId) > 0;
  }

  /**
   * Get all items and their stock levels.
   * @returns {Object} map of itemId -> quantity
   */
  getAllStock() {
    const result = {};
    for (const [itemId, quantity] of this.stock.entries()) {
      result[itemId] = quantity;
    }
    return result;
  }
};

module.exports = InventoryService;
