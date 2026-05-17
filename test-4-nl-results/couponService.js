const http = require('http');

// In-memory storage for coupons
const coupons = {};

// Helper to send JSON responses
function sendJSON(res, statusCode, data) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

// Helper to parse request body as JSON
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (e) {
        reject(e);
      }
    });
  });
}

const requestListener = async (req, res) => {
  const { method, url } = req;
  // Parse path: /coupons[/:code]
  const pathParts = url.split('/').filter(Boolean);
  
  // All coupon routes start with /coupons
  if (pathParts[0] !== 'coupons') {
    sendJSON(res, 404, { error: 'Not Found' });
    return;
  }

  const code = pathParts[1]; // optional

  try {
    if (method === 'GET' && !code) {
      // GET /coupons - list all coupons
      const list = Object.values(coupons);
      sendJSON(res, 200, list);
    } else if (method === 'GET' && code) {
      // GET /coupons/:code - get a single coupon
      const coupon = coupons[code];
      if (!coupon) {
        sendJSON(res, 404, { error: 'Coupon not found' });
      } else {
        sendJSON(res, 200, coupon);
      }
    } else if (method === 'POST' && !code) {
      // POST /coupons - create a new coupon
      const body = await parseBody(req);
      if (!body.code || typeof body.code !== 'string' || body.code.trim() === '') {
        sendJSON(res, 400, { error: 'Coupon code is required and must be a non-empty string' });
        return;
      }
      if (coupons[body.code]) {
        sendJSON(res, 409, { error: 'Coupon code already exists' });
        return;
      }
      const coupon = {
        code: body.code,
        discount: typeof body.discount === 'number' ? body.discount : null,
        expiry: body.expiry || null,
        active: body.active !== false, // default active
      };
      coupons[body.code] = coupon;
      sendJSON(res, 201, coupon);
    } else if (method === 'PUT' && code) {
      // PUT /coupons/:code - update an existing coupon
      const existing = coupons[code];
      if (!existing) {
        sendJSON(res, 404, { error: 'Coupon not found' });
        return;
      }
      const body = await parseBody(req);
      if (body.code && body.code !== code) {
        sendJSON(res, 400, { error: 'Coupon code cannot be changed' });
        return;
      }
      // Update allowed fields
      if (typeof body.discount === 'number') existing.discount = body.discount;
      if (body.expiry !== undefined) existing.expiry = body.expiry;
      if (typeof body.active === 'boolean') existing.active = body.active;
      sendJSON(res, 200, existing);
    } else if (method === 'DELETE' && code) {
      // DELETE /coupons/:code - delete a coupon
      if (!coupons[code]) {
        sendJSON(res, 404, { error: 'Coupon not found' });
        return;
      }
      delete coupons[code];
      sendJSON(res, 200, { message: 'Coupon deleted' });
    } else {
      sendJSON(res, 405, { error: 'Method Not Allowed' });
    }
  } catch (e) {
    sendJSON(res, 400, { error: 'Invalid JSON body' });
  }
};

const server = http.createServer(requestListener);

module.exports = server;

// Auto-start if this file is run directly
if (require.main === module) {
  const port = process.env.PORT || 3003;
  server.listen(port, () => {
    console.log(`CouponService listening on port ${port}`);
  });
}
