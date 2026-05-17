const http = require('http');

// Simple route table
const routes = {
  'GET:/': (req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('Hello, world!');
  },
};

const server = http.createServer((req, res) => {
  const method = req.method.toUpperCase();
  const path = req.url;
  const routeKey = `${method}:${path}`;
  const handler = routes[routeKey];

  if (handler) {
    handler(req, res);
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
  }
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`);
});

module.exports = server;
