const { v4: uuidv4 } = require('uuid'); // Only if needed, but Dependencies: {} means no external packages. Let's implement a simple ID generator internally.

// Inline simple UUID generator
function generateId() {
  return 'order-' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
}

const VALID_TRANSITIONS = {
  PENDING: ['CONFIRMED', 'CANCELLED'],
  CONFIRMED: ['SHIPPED', 'CANCELLED'],
  SHIPPED: ['DELIVERED', 'CANCELLED'],
  DELIVERED: [],
  CANCELLED: []
};

class OrderManager {
  constructor() {
    this.orders = new Map();
  }

  createOrder(customerId, items) {
    if (!customerId || typeof customerId !== 'string') {
      throw new Error('customerId is required and must be a string');
    }
    if (!Array.isArray(items) || items.length === 0) {
      throw new Error('items must be a non-empty array');
    }
    // Validate each item has productId and quantity
    items.forEach((item, i) => {
      if (!item.productId || typeof item.productId !== 'string') {
        throw new Error(`Item ${i}: productId is required (string)`);
      }
      if (!Number.isInteger(item.quantity) || item.quantity < 1) {
        throw new Error(`Item ${i}: quantity must be a positive integer`);
      }
    });

    const order = {
      id: generateId(),
      customerId,
      items: items.map(item => ({
        productId: item.productId,
        quantity: item.quantity,
        price: item.price || 0  // optional
      })),
      status: 'PENDING',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      history: [
        { status: 'PENDING', timestamp: new Date().toISOString() }
      ]
    };
    this.orders.set(order.id, order);
    return order;
  }

  getOrder(orderId) {
    return this.orders.get(orderId) || null;
  }

  listOrders(statusFilter) {
    const orders = Array.from(this.orders.values());
    if (statusFilter) {
      return orders.filter(o => o.status === statusFilter.toUpperCase());
    }
    return orders;
  }

  updateOrder(orderId, updates) {
    const order = this.orders.get(orderId);
    if (!order) throw new Error('Order not found');

    // If status update is provided
    if (updates.status) {
      const newStatus = updates.status.toUpperCase();
      const allowed = VALID_TRANSITIONS[order.status];
      if (!allowed || !allowed.includes(newStatus)) {
        throw new Error(`Cannot change status from ${order.status} to ${newStatus}. Allowed: ${allowed ? allowed.join(', ') : 'none'}`);
      }
      order.status = newStatus;
      order.updatedAt = new Date().toISOString();
      order.history.push({ status: newStatus, timestamp: new Date().toISOString() });
    }

    // Update other fields? We could allow updating customerId or items, but for simplicity only status via updateOrder.
    // If you want to allow full update, add checks here.
    return order;
  }

  cancelOrder(orderId) {
    const order = this.orders.get(orderId);
    if (!order) throw new Error('Order not found');
    const allowed = VALID_TRANSITIONS[order.status];
    if (!allowed || !allowed.includes('CANCELLED')) {
      throw new Error(`Order cannot be cancelled from ${order.status}`);
    }
    order.status = 'CANCELLED';
    order.updatedAt = new Date().toISOString();
    order.history.push({ status: 'CANCELLED', timestamp: new Date().toISOString() });
    return order;
  }
}

module.exports = OrderManager;