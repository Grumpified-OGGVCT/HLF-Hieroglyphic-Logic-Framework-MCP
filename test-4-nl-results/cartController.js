const { getCart, addItem, updateItem, removeItem, clearCart } = require('./cartModel');

const parseBody = (req) => {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(new Error('Invalid JSON'));
      }
    });
    req.on('error', reject);
  });
};

const sendResponse = (res, statusCode, data) => {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
};

const getUserIdFromUrl = (url) => {
  // URL pattern: /cart/:userId or /cart/:userId/items/:productId
  const parts = url.split('/').filter(p => p);
  if (parts.length >= 2 && parts[0] === 'cart') {
    return parts[1];
  }
  return null;
};

const getProductIdFromUrl = (url) => {
  const parts = url.split('/').filter(p => p);
  if (parts.length === 4 && parts[0] === 'cart' && parts[2] === 'items') {
    return parts[3];
  }
  return null;
};

const handleRequest = async (req, res) => {
  const { method, url } = req;

  try {
    if (method === 'GET' && url.startsWith('/cart/')) {
      const userId = getUserIdFromUrl(url);
      if (!userId) {
        sendResponse(res, 400, { error: 'userId is required' });
        return;
      }
      const cart = getCart(userId);
      sendResponse(res, 200, cart);
    } else if (method === 'POST' && url.startsWith('/cart/') && !url.includes('/items/')) {
      const userId = getUserIdFromUrl(url);
      if (!userId) {
        sendResponse(res, 400, { error: 'userId is required' });
        return;
      }
      const body = await parseBody(req);
      const { productId, quantity } = body;
      if (!productId || quantity == null) {
        sendResponse(res, 400, { error: 'productId and quantity are required' });
        return;
      }
      const cart = addItem(userId, productId, quantity);
      sendResponse(res, 201, cart);
    } else if (method === 'PUT' && url.includes('/items/')) {
      const userId = getUserIdFromUrl(url);
      const productId = getProductIdFromUrl(url);
      if (!userId || !productId) {
        sendResponse(res, 400, { error: 'userId and productId are required' });
        return;
      }
      const body = await parseBody(req);
      const { quantity } = body;
      if (quantity == null) {
        sendResponse(res, 400, { error: 'quantity is required' });
        return;
      }
      const cart = updateItem(userId, productId, quantity);
      sendResponse(res, 200, cart);
    } else if (method === 'DELETE' && url.includes('/items/')) {
      const userId = getUserIdFromUrl(url);
      const productId = getProductIdFromUrl(url);
      if (!userId || !productId) {
        sendResponse(res, 400, { error: 'userId and productId are required' });
        return;
      }
      const cart = removeItem(userId, productId);
      sendResponse(res, 200, cart);
    } else if (method === 'DELETE' && url.startsWith('/cart/') && !url.includes('/items/')) {
      const userId = getUserIdFromUrl(url);
      if (!userId) {
        sendResponse(res, 400, { error: 'userId is required' });
        return;
      }
      clearCart(userId);
      sendResponse(res, 200, { message: 'Cart cleared' });
    } else {
      sendResponse(res, 404, { error: 'Not found' });
    }
  } catch (error) {
    sendResponse(res, 500, { error: error.message });
  }
};

module.exports = { handleRequest };
