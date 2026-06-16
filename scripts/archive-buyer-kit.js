#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const version = pkg.version || '0.0.0';
const outRoot = path.join(root, 'dist', 'delivery');
const kitName = `ai-chat-buyer-kit-${version}`;
const kitDir = path.join(outRoot, kitName);
const archivePath = path.join(outRoot, `${kitName}.zip`);
const checksumPath = `${archivePath}.sha256`;

function sha256File(file) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(file));
  return hash.digest('hex');
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

if (!fs.existsSync(kitDir)) {
  fail(`Buyer kit folder is missing: ${path.relative(root, kitDir)}. Run npm run build:buyer-kit first.`);
}

const manifest = path.join(kitDir, 'MANIFEST.json');
const checksums = path.join(kitDir, 'CHECKSUMS.txt');
if (!fs.existsSync(manifest)) fail('Buyer kit MANIFEST.json is missing.');
if (!fs.existsSync(checksums)) fail('Buyer kit CHECKSUMS.txt is missing.');

fs.rmSync(archivePath, { force: true });
fs.rmSync(checksumPath, { force: true });

const zip = spawnSync('zip', ['-qry', path.basename(archivePath), kitName], {
  cwd: outRoot,
  encoding: 'utf8',
  shell: false
});

if (zip.status !== 0) {
  fail(`zip failed: ${(zip.stderr || zip.stdout || '').trim()}`);
}

const digest = sha256File(archivePath);
fs.writeFileSync(checksumPath, `${digest}  ${path.basename(archivePath)}\n`);

console.log(`Buyer kit archive generated: ${path.relative(root, archivePath)}`);
console.log(`SHA256: ${digest}`);
