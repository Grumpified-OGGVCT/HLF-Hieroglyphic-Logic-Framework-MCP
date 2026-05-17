const http = require('http');

let orders = [];
let nextId = 1;

const server = http.createServer((req, res) => {
  const { method, url } = req;
  res.setHeader('Content-Type', 'application/json');

  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // GET /orders
  if (method === 'GET' && url === '/orders') {
    res.writeHead(200);
    res.end(JSON.stringify(orders));
    return;
  }

  // GET /orders/:id
  const getOrderMatch = url.match(/^\/orders\/(\d+)$/);
  if (method === 'GET' && getOrderMatch) {
    const id = parseInt(getOrderMatch[1], 10);
    const order = orders.find(o => o.id === id);
    if (order) {
      res.writeHead(200);
      res.end(JSON.stringify(order));
    } else {
      res.writeHead(404);
      res.end(JSON.stringify({ error: 'Order not found' }));
    }
    return;
  }

  // POST /orders
  if (method === 'POST' && url === '/orders') {
    let body = '';
    req.on('data', chunk => body += chunk.toString());
    req.on('end', () => {
      try {
        const orderData = JSON.parse(body);
        const newOrder = { id: nextId++, ...orderData, status: 'created', createdAt: new Date().toISOString() };
        orders.push(newOrder);
        res.writeHead(201);
        res.end(JSON.stringify(newOrder));
      } catch (e) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }

  // PUT /orders/:id
  const putOrderMatch = url.match(/^\/orders\/(\d+)$/);
  if (method === 'PUT' && putOrderMatch) {
    const id = parseInt(putOrderMatch[1], 10);
    const index = orders.findIndex(o => o.id === id);
    if (index === -1) {
      res.writeHead(404);
      res.end(JSON.stringify({ error: 'Order not found' }));
      return;
    }
    let body = '';
    req.on('data', chunk => body += chunk.toString());
    req.on('end', () => {
      try {
        const updates = JSON.parse(body);
        orders[index] = { ...orders[index], ...updates, id: orders[index].id, updatedAt: new Date().toISOString() };
        res.writeHead(200);
        res.end(JSON.stringify(orders[index]));
      } catch (e) {
        res.writeHead(400);
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }

  // DELETE /orders/:id
  const deleteOrderMatch = url.match(/^\/orders\/(\d+)$/);
  if (method === 'DELETE' && deleteOrderMatch) {
    const id = parseInt(deleteOrderMatch[1], 10);
    const index = orders.findIndex(o => o.id === id);
    if (index === -1) {
      res.writeHead(404);
      res.end(JSON.stringify({ error: 'Order not found' }));
      return;
    }
    orders.splice(index, 1);
    res.writeHead(204);
    res.end();
    return;
  }

  // Not found
  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found' }));
});

const PORT = process.env.ORDER_SERVICE_PORT || 3002;
server.listen(PORT, () => {
  console.log(`OrderService running on port ${PORT}`);
});

module.exports = server;
