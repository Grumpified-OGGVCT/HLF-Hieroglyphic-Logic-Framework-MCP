const url = require('url');
const {
  createReview,
  getAllReviews,
  getReviewById,
  updateReview,
  deleteReview,
  moderateReview,
} = require('./reviewModel');

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
      if (body.length > 1e6) {
        req.connection.destroy();
        reject(new Error('Request body too large'));
      }
    });
    req.on('end', () => {
      if (!body) return resolve({});
      try {
        resolve(JSON.parse(body));
      } catch (err) {
        reject(new Error('Invalid JSON'));
      }
    });
  });
}

function sendJSON(res, statusCode, data) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function sendError(res, statusCode, message) {
  sendJSON(res, statusCode, { error: message });
}

async function handleRequest(req, res) {
  const parsedUrl = url.parse(req.url, true);
  const path = parsedUrl.pathname.replace(/\/+$/, ''); // remove trailing slash
  const method = req.method;

  // Route: /reviews
  const reviewsRoute = /^\/reviews(?:\/(\d+)(?:\/moderate)?)?$/;
  const match = path.match(reviewsRoute);

  if (!match) {
    sendError(res, 404, 'Not found');
    return;
  }

  const id = match[1] ? parseInt(match[1], 10) : null;
  const isModerate = path.endsWith('/moderate');

  try {
    if (path === '/reviews' && method === 'GET') {
      // GET /reviews?productId=...&userId=...&status=...
      const filters = {
        productId: parsedUrl.query.productId,
        userId: parsedUrl.query.userId,
        status: parsedUrl.query.status,
      };
      const reviews = getAllReviews(filters);
      sendJSON(res, 200, reviews);
    } else if (path === '/reviews' && method === 'POST') {
      const body = await parseBody(req);
      if (!body.userId || !body.productId || body.rating === undefined) {
        sendError(res, 400, 'userId, productId, and rating are required');
        return;
      }
      const rating = parseFloat(body.rating);
      if (isNaN(rating) || rating < 1 || rating > 5) {
        sendError(res, 400, 'Rating must be a number between 1 and 5');
        return;
      }
      const review = createReview({ userId: body.userId, productId: body.productId, rating, text: body.text });
      sendJSON(res, 201, review);
    } else if (id && !isModerate && method === 'GET') {
      // GET /reviews/:id
      const review = getReviewById(id);
      if (!review) {
        sendError(res, 404, 'Review not found');
        return;
      }
      sendJSON(res, 200, review);
    } else if (id && !isModerate && method === 'PUT') {
      // PUT /reviews/:id
      const body = await parseBody(req);
      const updated = updateReview(id, body);
      if (!updated) {
        sendError(res, 404, 'Review not found');
        return;
      }
      if (body.rating !== undefined) {
        const rating = parseFloat(body.rating);
        if (isNaN(rating) || rating < 1 || rating > 5) {
          sendError(res, 400, 'Rating must be a number between 1 and 5');
          return;
        }
      }
      sendJSON(res, 200, updated);
    } else if (id && !isModerate && method === 'DELETE') {
      // DELETE /reviews/:id
      const deleted = deleteReview(id);
      if (!deleted) {
        sendError(res, 404, 'Review not found');
        return;
      }
      sendJSON(res, 200, { message: 'Review deleted' });
    } else if (id && isModerate && method === 'PUT') {
      // PUT /reviews/:id/moderate
      const body = await parseBody(req);
      const { status } = body;
      if (!status || !['approved', 'rejected'].includes(status)) {
        sendError(res, 400, 'Status must be "approved" or "rejected"');
        return;
      }
      const moderated = moderateReview(id, status);
      if (!moderated) {
        sendError(res, 404, 'Review not found');
        return;
      }
      sendJSON(res, 200, moderated);
    } else {
      sendError(res, 405, 'Method not allowed');
    }
  } catch (err) {
    sendError(res, 500, err.message || 'Internal server error');
  }
}

module.exports = { handleRequest };