#!/usr/bin/env node
// Fallback dev server: use custom server.js if present, else next dev
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const serverPath = path.join(__dirname, 'server.js');
if (fs.existsSync(serverPath)) {
  require(serverPath);
} else {
  const r = spawnSync('npx', ['next', 'dev', '-H', '0.0.0.0'], { stdio: 'inherit', cwd: __dirname });
  process.exit(r.status || 0);
}
