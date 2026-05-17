// Simple in-memory cart store
const carts = {};

const getCart = (userId) => {
  if (!carts[userId]) {
    carts[userId] = { userId, items: [] };
  }
  return carts[userId];
};

const addItem = (userId, productId, quantity) => {
  const cart = getCart(userId);
  const existingItem = cart.items.find(item => item.productId === productId);
  if (existingItem) {
    existingItem.quantity += quantity;
  } else {
    cart.items.push({ productId, quantity });
  }
  return cart;
};

const updateItem = (userId, productId, quantity) => {
  const cart = getCart(userId);
  const item = cart.items.find(item => item.productId === productId);
  if (item) {
    item.quantity = quantity;
    if (item.quantity <= 0) {
      cart.items = cart.items.filter(i => i.productId !== productId);
    }
  } else {
    throw new Error('Item not found');
  }
  return cart;
};

const removeItem = (userId, productId) => {
  const cart = getCart(userId);
  cart.items = cart.items.filter(item => item.productId !== productId);
  return cart;
};

const clearCart = (userId) => {
  const cart = getCart(userId);
  cart.items = [];
  return cart;
};

module.exports = { getCart, addItem, updateItem, removeItem, clearCart };
