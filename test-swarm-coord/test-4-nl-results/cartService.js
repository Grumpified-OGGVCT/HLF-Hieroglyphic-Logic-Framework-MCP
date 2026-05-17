const carts = {};

function getCart(userId) {
  if (!carts[userId]) {
    carts[userId] = { items: [] };
  }
  return carts[userId];
}

function addToCart(userId, item) {
  const cart = getCart(userId);
  const existing = cart.items.find(i => i.id === item.id);
  if (existing) {
    existing.quantity += item.quantity || 1;
  } else {
    cart.items.push({
      id: item.id,
      name: item.name,
      price: item.price,
      quantity: item.quantity || 1
    });
  }
  return cart;
}

function removeFromCart(userId, itemId) {
  const cart = getCart(userId);
  cart.items = cart.items.filter(i => i.id !== itemId);
  return cart;
}

function checkout(userId) {
  const cart = getCart(userId);
  const total = cart.items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  // clear cart after checkout
  carts[userId] = { items: [] };
  return { items: cart.items, total };
}

function clearCart(userId) {
  delete carts[userId];
}

module.exports = { getCart, addToCart, removeFromCart, checkout, clearCart };
