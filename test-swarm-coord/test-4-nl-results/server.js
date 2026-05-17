const http = require('http');
const { URL } = require('url');

const PORT = process.env.SHIPPING_PORT || 3002;

// In-memory shipments store
const shipments = [];
let nextId = 1;

/**
 * Parse JSON body from request
 */
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => (body += chunk));
    req.on('end', () => {
      try {
        resolve(JSON.parse(body || '{}'));
      } catch (err) {
        reject(err);
      }
    });
    req.on('error', reject);
  });
}

/**
 * Send JSON response
 */
function sendJSON(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

const server = http.createServer(async (req, res) => {
  try {
    const reqUrl = new URL(req.url, `http://${req.headers.host}`);
    const path = reqUrl.pathname.split('/').filter(Boolean);
    const method = req.method;

    // POST /shipments
    if (method === 'POST' && path.length === 1 && path[0] === 'shipments') {
      const body = await parseBody(req);
      const shipment = {
        id: String(nextId++),
        orderId: body.orderId || '',
        address: body.address || '',
        status: 'created',
        createdAt: new Date().toISOString()
      };
      shipments.push(shipment);
      sendJSON(res, 201, shipment);
      return;
    }

    // GET /shipments/:id
    if (method === 'GET' && path.length === 2 && path[0] === 'shipments') {
      const id = path[1];
      const shipment = shipments.find(s => s.id === id);
      if (!shipment) {
        sendJSON(res, 404, { error: 'Shipment not found' });
        return;
      }
      sendJSON(res, 200, shipment);
      return;
    }

    // PUT /shipments/:id/status
    if (method === 'PUT' && path.length === 3 && path[0] === 'shipments' && path[2] === 'status') {
      const id = path[1];
      const shipment = shipments.find(s => s.id === id);
      if (!shipment) {
        sendJSON(res, 404, { error: 'Shipment not found' });
        return;
      }
      const body = await parseBody(req);
      if (!body.status) {
        sendJSON(res, 400, { error: 'Missing status field' });
        return;
      }
      shipment.status = body.status;
      sendJSON(res, 200, shipment);
      return;
    }

    // Fallback – not found
    sendJSON(res, 404, { error: 'Not found' });
  } catch (err) {
    if (err instanceof SyntaxError) {
      sendJSON(res, 400, { error: 'Invalid JSON' });
    } else {
      sendJSON(res, 500, { error: 'Internal server error' });
    }
  }
});

server.listen(PORT, () => {
  console.log(`ShippingService running on port ${PORT}`);
});

module.exports = server;
