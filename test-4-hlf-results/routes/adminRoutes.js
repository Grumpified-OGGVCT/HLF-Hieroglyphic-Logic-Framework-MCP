const url = require('url');
const analyticsService = require('../services/analyticsService');
const moderationService = require('../services/moderationService');

const sendJSON = (res, statusCode, data) => {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
};

const parseBody = (req) => {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
      if (body.length > 1e6) {
        req.connection.destroy();
        reject(new Error('Payload too large'));
      }
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(err);
      }
    });
  });
};

const handleRequest = async (req, res, parsedUrl) => {
  const { pathname } = parsedUrl;
  const method = req.method;

  // Analytics endpoints
  if (pathname === '/api/admin/analytics' && method === 'GET') {
    const data = analyticsService.getAnalytics();
    sendJSON(res, 200, data);
  } 
  else if (pathname === '/api/admin/analytics/user-growth' && method === 'GET') {
    const data = analyticsService.getUserGrowth();
    sendJSON(res, 200, data);
  }
  else if (pathname === '/api/admin/analytics/track' && method === 'POST') {
    analyticsService.trackPageView();
    sendJSON(res, 200, { message: 'Tracked' });
  }
  // Moderation endpoints
  else if (pathname === '/api/admin/reports' && method === 'GET') {
    const reports = moderationService.getAllReports();
    sendJSON(res, 200, reports);
  }
  else if (pathname === '/api/admin/reports' && method === 'POST') {
    try {
      const body = await parseBody(req);
      const { contentId, reporterId, reason } = body;
      if (!contentId || !reporterId || !reason) {
        return sendJSON(res, 400, { error: 'Missing required fields: contentId, reporterId, reason' });
      }
      const report = moderationService.createReport(contentId, reporterId, reason);
      sendJSON(res, 201, report);
    } catch (err) {
      sendJSON(res, 400, { error: 'Invalid request body' });
    }
  }
  else if (pathname.startsWith('/api/admin/reports/') && method === 'PUT') {
    const reportId = parseInt(pathname.split('/')[4], 10);
    try {
      const body = await parseBody(req);
      const { status } = body;
      if (status === 'resolved') {
        const updated = moderationService.resolveReport(reportId);
        if (!updated) return sendJSON(res, 404, { error: 'Report not found' });
        sendJSON(res, 200, updated);
      } else {
        sendJSON(res, 400, { error: 'Invalid status' });
      }
    } catch (err) {
      sendJSON(res, 400, { error: 'Invalid request' });
    }
  }
  else if (pathname.startsWith('/api/admin/users/') && pathname.endsWith('/ban') && method === 'POST') {
    const userId = parseInt(pathname.split('/')[4], 10);
    const user = moderationService.banUser(userId);
    if (!user) return sendJSON(res, 404, { error: 'User not found' });
    sendJSON(res, 200, user);
  }
  else if (pathname.startsWith('/api/admin/users/') && pathname.endsWith('/unban') && method === 'POST') {
    const userId = parseInt(pathname.split('/')[4], 10);
    const user = moderationService.unbanUser(userId);
    if (!user) return sendJSON(res, 404, { error: 'User not found' });
    sendJSON(res, 200, user);
  }
  else {
    sendJSON(res, 404, { error: 'Not found' });
  }
};

module.exports = { handleRequest };
