const express = require('express');
const crypto = require('crypto');
const app = express();
const PORT = process.env.ORDER_SERVICE_PORT || 3002;

app.use(express.json());

let orders = [];

// Get all orders
app.get('/orders', (req, res) => {
  res.json(orders);
});

// Get order by id
app.get('/order/:id', (req, res) => {
  const order = orders.find(o => o.id === req.params.id);
  if (!order) return res.status(404).json({ error: 'Order not found' });
  res.json(order);
});

// Create new order
app.post('/order', (req, res) => {
  const { item, quantity } = req.body;
  if (!item || !quantity) {
    return res.status(400).json({ error: 'Missing item or quantity' });
  }
  const newOrder = {
    id: crypto.randomUUID(),
    item,
    quantity,
    status: 'pending',
    createdAt: new Date().toISOString()
  };
  orders.push(newOrder);
  res.status(201).json(newOrder);
});

// Update order status
app.put('/order/:id', (req, res) => {
  const order = orders.find(o => o.id === req.params.id);
  if (!order) return res.status(404).json({ error: 'Order not found' });
  const { status } = req.body;
  if (status && ['pending', 'processing', 'completed', 'cancelled'].includes(status)) {
    order.status = status;
  }
  res.json(order);
});

app.listen(PORT, () => {
  console.log(`OrderService running on port ${PORT}`);
});

module.exports = app;