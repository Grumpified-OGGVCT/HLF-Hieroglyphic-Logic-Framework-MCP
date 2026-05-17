const http = require('http');

const PORT = process.env.REVIEW_SERVICE_PORT || 3002;

let reviews = [];
let nextId = 1;

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
      if (body.length > 1e6) {
        req.destroy();
        reject(new Error('Request body too large'));
      }
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(new Error('Invalid JSON'));
      }
    });
  });
}

function send(res, statusCode, data) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

const server = http.createServer(async (req, res) => {
  const { method, url } = req;
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // Route: /reviews
  if (url === '/reviews' || url === '/reviews/') {
    if (method === 'GET') {
      send(res, 200, reviews);
      return;
    }
    if (method === 'POST') {
      try {
        const body = await parseBody(req);
        if (!body.productId || !body.rating || !body.comment) {
          send(res, 400, { error: 'Missing required fields: productId, rating, comment' });
          return;
        }
        const review = {
          id: nextId++,
          productId: body.productId,
          userId: body.userId || 'anonymous',
          rating: body.rating,
          comment: body.comment,
          createdAt: new Date().toISOString()
        };
        reviews.push(review);
        send(res, 201, review);
      } catch (err) {
        send(res, 400, { error: err.message });
      }
      return;
    }
  }

  // Route: /reviews/:id
  const reviewMatch = url.match(/^\/reviews\/(\d+)$/);
  if (reviewMatch) {
    const id = parseInt(reviewMatch[1], 10);
    const review = reviews.find(r => r.id === id);

    if (method === 'GET') {
      if (!review) {
        send(res, 404, { error: 'Review not found' });
        return;
      }
      send(res, 200, review);
      return;
    }

    if (method === 'PUT') {
      if (!review) {
        send(res, 404, { error: 'Review not found' });
        return;
      }
      try {
        const body = await parseBody(req);
        if (body.rating) review.rating = body.rating;
        if (body.comment) review.comment = body.comment;
        review.updatedAt = new Date().toISOString();
        send(res, 200, review);
      } catch (err) {
        send(res, 400, { error: err.message });
      }
      return;
    }

    if (method === 'DELETE') {
      if (!review) {
        send(res, 404, { error: 'Review not found' });
        return;
      }
      reviews = reviews.filter(r => r.id !== id);
      send(res, 200, { message: 'Review deleted' });
      return;
    }
  }

  // Fallback
  send(res, 404, { error: 'Not found' });
});

server.listen(PORT, () => {
  console.log(`ReviewService running on port ${PORT}`);
});

module.exports = server;
