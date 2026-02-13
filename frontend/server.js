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
const useHttpOnly = process.env.USE_HTTP_ONLY === '1';

// SSL certificate paths - skip HTTPS when USE_HTTP_ONLY=1 (fixes HMR WebSocket with custom server)
let httpsOptions = null;
const keyPath = path.join(__dirname, 'localhost-key.pem');
const certPath = path.join(__dirname, 'localhost.pem');

if (!useHttpOnly && fs.existsSync(keyPath) && fs.existsSync(certPath)) {
  try {
    httpsOptions = {
      key: fs.readFileSync(keyPath),
      cert: fs.readFileSync(certPath),
    };
  } catch (err) {
    console.warn('Failed to load SSL certificates, HTTPS will be disabled:', err.message);
  }
} else if (!useHttpOnly) {
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
  const upgradeHandler = app.getUpgradeHandler?.() || (() => {});

  function attachUpgrade(server) {
    if (server && upgradeHandler) {
      server.on('upgrade', (req, socket, head) => {
        upgradeHandler(req, socket, head).catch((err) => {
          console.error('Upgrade error:', err);
          socket.destroy();
        });
      });
    }
  }

  if (httpsOptions) {
    const httpsServer = createHttpsServer(httpsOptions, requestHandler);
    attachUpgrade(httpsServer);
    httpsServer.listen(httpsPort, hostname, (err) => {
      if (err) throw err;
      console.log(`> HTTPS server ready on https://${hostname}:${httpsPort}`);
    });
  } else {
    console.log(`> HTTPS server skipped (no certificates)`);
  }

  const httpServer = createHttpServer(requestHandler);
  attachUpgrade(httpServer);
  httpServer.listen(httpPort, hostname, (err) => {
    if (err) throw err;
    console.log(`> HTTP server ready on http://${hostname}:${httpPort}`);
  });
});
