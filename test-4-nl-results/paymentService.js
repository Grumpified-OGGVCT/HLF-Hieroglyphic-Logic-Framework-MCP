const http = require('http');
const { addPayment, getPayment, updatePaymentStatus } = require('./paymentStore');

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {
  const { method, url } = req;
  const pathname = new URL(url, `http://${req.headers.host}`).pathname;

  // Set CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Health check
  if (method === 'GET' && pathname === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok' }));
    return;
  }

  // POST /payments
  if (method === 'POST' && pathname === '/payments') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        if (!data.orderId || !data.amount || !data.paymentMethod) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Missing required fields: orderId, amount, paymentMethod' }));
          return;
        }
        if (isNaN(data.amount) || data.amount <= 0) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Invalid amount' }));
          return;
        }
        const payment = addPayment(data.orderId, data.amount, data.paymentMethod);
        res.writeHead(201, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(payment));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }

  // GET /payments/:id
  const getMatch = pathname.match(/^\/payments\/([^\/]+)$/);
  if (method === 'GET' && getMatch) {
    const id = getMatch[1];
    const payment = getPayment(id);
    if (!payment) {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Payment not found' }));
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(payment));
    return;
  }

  // PUT /payments/:id/status
  const putStatusMatch = pathname.match(/^\/payments\/([^\/]+)\/status$/);
  if (method === 'PUT' && putStatusMatch) {
    const id = putStatusMatch[1];
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const { status } = JSON.parse(body);
        if (!status || !['pending', 'confirmed', 'failed', 'refunded'].includes(status)) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Invalid status' }));
          return;
        }
        const payment = updatePaymentStatus(id, status);
        if (!payment) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Payment not found' }));
          return;
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(payment));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid JSON' }));
      }
    });
    return;
  }

  // Fallback 404
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'Not found' }));
});

server.listen(PORT, () => {
  console.log(`PaymentService running on port ${PORT}`);
});
