const { v4: uuidv4 } = require('uuid'); // Not available without npm, so using custom ID generator

// Simple ID generator (since we can't rely on uuid)
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
}

const payments = [];

function addPayment(orderId, amount, paymentMethod) {
  const payment = {
    id: generateId(),
    orderId,
    amount,
    paymentMethod,
    status: 'pending',
    createdAt: new Date().toISOString(),
    updatedAt: null
  };
  payments.push(payment);
  return payment;
}

function getPayment(id) {
  return payments.find(p => p.id === id) || null;
}

function updatePaymentStatus(id, status) {
  const payment = payments.find(p => p.id === id);
  if (!payment) return null;
  payment.status = status;
  payment.updatedAt = new Date().toISOString();
  return payment;
}

module.exports = { addPayment, getPayment, updatePaymentStatus };
