const { createServer: createHttpsServer } = require('https');
const { createServer: createHttpServer } = require('http');
const { parse } = require('url');
const next = require('next');
const fs = require('fs');
const path = require('path');

const dev = process.env.NODE_ENV !== 'production';
const hostname = process.env.HOSTNAME || '0.0.0.0';
const httpsPort = parseInt(process.env.HTTPS_PORT || '3000', 10);
const httpPort = parseInt(process.env.HTTP_PORT || '3001', 10);

// SSL certificate paths - check if files exist, fallback to HTTP if not
let httpsOptions = null;
const keyPath = path.join(__dirname, 'localhost-key.pem');
const certPath = path.join(__dirname, 'localhost.pem');

if (fs.existsSync(keyPath) && fs.existsSync(certPath)) {
  try {
    httpsOptions = {
      key: fs.readFileSync(keyPath),
      cert: fs.readFileSync(certPath),
    };
  } catch (err) {
    console.warn('Failed to load SSL certificates, HTTPS will be disabled:', err.message);
  }
} else {
  console.warn('SSL certificates not found, HTTPS will be disabled');
}

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
  // Create HTTPS server if certificates are available
  if (httpsOptions) {
    createHttpsServer(httpsOptions, requestHandler).listen(httpsPort, hostname, (err) => {
      if (err) throw err;
      console.log(`> HTTPS server ready on https://${hostname}:${httpsPort}`);
    });
  } else {
    console.log(`> HTTPS server skipped (no certificates)`);
  }

  // Create HTTP server (always available as fallback)
  createHttpServer(requestHandler).listen(httpPort, hostname, (err) => {
    if (err) throw err;
    console.log(`> HTTP server ready on http://${hostname}:${httpPort}`);
  });
});
