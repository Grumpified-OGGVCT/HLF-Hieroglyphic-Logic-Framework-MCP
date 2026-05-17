// cartService.js - In-memory shopping cart logic

class CartService {
  constructor() {
    // Store carts keyed by userId
    this.carts = new Map();
  }

  /**
   * Get or create a cart for a user
   */
  _getCart(userId) {
    if (!this.carts.has(userId)) {
      this.carts.set(userId, { items: [], total: 0 });
    }
    return this.carts.get(userId);
  }

  /**
   * Add an item to the cart
   * @param {string} userId
   * @param {Object} item - { id, name, price, quantity }
   */
  addItem(userId, item) {
    const cart = this._getCart(userId);
    const existingIndex = cart.items.findIndex(i => i.id === item.id);
    if (existingIndex >= 0) {
      // Item exists: increase quantity
      cart.items[existingIndex].quantity += item.quantity || 1;
    } else {
      // New item: set quantity default to 1
      const newItem = { ...item, quantity: item.quantity || 1 };
      cart.items.push(newItem);
    }
    this._recalcTotal(cart);
    return cart;
  }

  /**
   * Remove an item from the cart
   * @param {string} userId
   * @param {string} itemId
   */
  removeItem(userId, itemId) {
    const cart = this._getCart(userId);
    const index = cart.items.findIndex(i => i.id === itemId);
    if (index >= 0) {
      cart.items.splice(index, 1);
      this._recalcTotal(cart);
    }
    return cart;
  }

  /**
   * Update the quantity of an item
   * @param {string} userId
   * @param {string} itemId
   * @param {number} quantity
   */
  updateItemQuantity(userId, itemId, quantity) {
    const cart = this._getCart(userId);
    const item = cart.items.find(i => i.id === itemId);
    if (item) {
      const qty = Math.max(0, parseInt(quantity, 10) || 0);
      if (qty === 0) {
        // Remove item if quantity set to zero
        return this.removeItem(userId, itemId);
      }
      item.quantity = qty;
      this._recalcTotal(cart);
    }
    return cart;
  }

  /**
   * Get the full cart for a user
   * @param {string} userId
   */
  getCart(userId) {
    return this._getCart(userId);
  }

  /**
   * Clear all items from the cart
   * @param {string} userId
   */
  clearCart(userId) {
    const cart = this._getCart(userId);
    cart.items = [];
    cart.total = 0;
    return cart;
  }

  /**
   * Calculate total price
   * @param {string} userId
   */
  getTotal(userId) {
    const cart = this._getCart(userId);
    return cart.total;
  }

  /**
   * Recalculate and update cart.total
   */
  _recalcTotal(cart) {
    cart.total = cart.items.reduce((sum, item) => {
      return sum + item.price * item.quantity;
    }, 0);
  }
}

module.exports = CartService;
