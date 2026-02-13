// HTTPS wrapper for Next.js standalone server
// This creates HTTPS/HTTP servers that proxy to the standalone server
const { createServer: createHttpsServer } = require('https');
const { createServer: createHttpServer } = require('http');
const http = require('http');
const fs = require('fs');
const path = require('path');

const hostname = process.env.HOSTNAME || '0.0.0.0';
const httpsPort = parseInt(process.env.HTTPS_PORT || '3000', 10);
const httpPort = parseInt(process.env.HTTP_PORT || '3001', 10);
const internalPort = parseInt(process.env.PORT || '3002', 10);

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
    console.log('SSL certificates loaded successfully');
  } catch (err) {
    console.warn('Failed to load SSL certificates, HTTPS will be disabled:', err.message);
  }
} else {
  console.warn('SSL certificates not found, HTTPS will be disabled');
}

// Start the standalone server on internal port
// The standalone server.js will start its own HTTP server
process.env.PORT = internalPort.toString();

// Import the standalone server (this starts the Next.js server)
// The standalone build creates server.js which we copied to the root
// The standalone server.js starts its own HTTP server, so we need to
// set PORT before requiring it
console.log('Starting standalone Next.js server on internal port', internalPort);
console.log('Working directory:', __dirname);
console.log('Files in directory:', require('fs').readdirSync(__dirname).slice(0, 10).join(', '));

// Import the standalone server (this will start the Next.js HTTP server)
// The standalone server.js is a complete server that listens on process.env.PORT
try {
  // The standalone server.js should be in the current directory
  // It's copied from .next/standalone/server.js during Docker build
  require('./server.js');
  console.log('Standalone server module loaded, waiting for it to start...');
} catch (err) {
  console.error('Failed to load standalone server:', err.message);
  console.error('Error stack:', err.stack);
  console.error('Make sure Next.js standalone build completed successfully');
  console.error('Expected server.js to be in:', __dirname);
  
  // List files to help debug
  try {
    const files = require('fs').readdirSync(__dirname);
    console.error('Files in directory:', files.join(', '));
  } catch (e) {
    console.error('Could not list directory:', e.message);
  }
  
  process.exit(1);
}

// Wait for standalone server to be ready, then start proxy servers
function waitForServer(port, maxAttempts = 30) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      attempts++;
      const req = http.get(`http://localhost:${port}`, (res) => {
        resolve();
      });
      req.on('error', (err) => {
        if (attempts >= maxAttempts) {
          reject(new Error(`Server on port ${port} did not start within ${maxAttempts} seconds: ${err.message}`));
        } else {
          setTimeout(check, 1000);
        }
      });
      req.end();
    };
    check();
  });
}

waitForServer(internalPort)
  .then(() => {
    console.log('Standalone server is ready, starting proxy servers...');

    // Proxy function to forward requests to standalone server
    function proxyRequest(req, res) {
      const options = {
        hostname: 'localhost',
        port: internalPort,
        path: req.url,
        method: req.method,
        headers: {
          ...req.headers,
          'x-forwarded-for': req.socket.remoteAddress,
          'x-forwarded-proto': req.connection.encrypted ? 'https' : 'http',
        },
      };

      const proxyReq = http.request(options, (proxyRes) => {
        // Copy response headers
        Object.keys(proxyRes.headers).forEach(key => {
          res.setHeader(key, proxyRes.headers[key]);
        });
        res.statusCode = proxyRes.statusCode;
        // Pipe response
        proxyRes.pipe(res);
      });

      proxyReq.on('error', (err) => {
        console.error('Proxy error:', err);
        if (!res.headersSent) {
          res.statusCode = 502;
          res.end('Bad Gateway');
        }
      });

      // Pipe request body
      req.pipe(proxyReq);
    }

    // Create HTTPS server if certificates are available
    if (httpsOptions) {
      const httpsServer = createHttpsServer(httpsOptions, proxyRequest);
      httpsServer.listen(httpsPort, hostname, (err) => {
        if (err) {
          console.error('Failed to start HTTPS server:', err);
          process.exit(1);
        }
        console.log(`> HTTPS server ready on https://${hostname}:${httpsPort}`);
      });
    } else {
      console.log(`> HTTPS server skipped (no certificates)`);
    }

    // Create HTTP server (always available as fallback)
    const httpServer = createHttpServer(proxyRequest);
    httpServer.listen(httpPort, hostname, (err) => {
      if (err) {
        console.error('Failed to start HTTP server:', err);
        process.exit(1);
      }
      console.log(`> HTTP server ready on http://${hostname}:${httpPort}`);
    });
  })
  .catch((err) => {
    console.error('Failed to start proxy servers:', err);
    process.exit(1);
  });
