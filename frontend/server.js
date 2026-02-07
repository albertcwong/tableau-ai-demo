const { createServer: createHttpsServer } = require('https');
const { createServer: createHttpServer } = require('http');
const { parse } = require('url');
const next = require('next');
const fs = require('fs');
const path = require('path');

const dev = process.env.NODE_ENV !== 'production';
const hostname = 'localhost';
const httpsPort = parseInt(process.env.HTTPS_PORT || '3000', 10);
const httpPort = parseInt(process.env.HTTP_PORT || '3001', 10);

// SSL certificate paths
const httpsOptions = {
  key: fs.readFileSync(path.join(__dirname, 'localhost-key.pem')),
  cert: fs.readFileSync(path.join(__dirname, 'localhost.pem')),
};

const app = next({ dev, hostname });
const handle = app.getRequestHandler();

// Request handler function shared by both servers
async function requestHandler(req, res) {
  try {
    const parsedUrl = parse(req.url, true);
    await handle(req, res, parsedUrl);
  } catch (err) {
    console.error('Error occurred handling', req.url, err);
    res.statusCode = 500;
    res.end('internal server error');
  }
}

app.prepare().then(() => {
  // Create HTTPS server
  createHttpsServer(httpsOptions, requestHandler).listen(httpsPort, (err) => {
    if (err) throw err;
    console.log(`> HTTPS server ready on https://${hostname}:${httpsPort}`);
  });

  // Create HTTP server
  createHttpServer(requestHandler).listen(httpPort, (err) => {
    if (err) throw err;
    console.log(`> HTTP server ready on http://${hostname}:${httpPort}`);
  });
});
