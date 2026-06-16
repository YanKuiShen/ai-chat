#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const version = pkg.version || '0.0.0';
const productName = (pkg.build && pkg.build.productName) || '白歌的AI讨论组';
const distDir = path.join(root, 'dist');
const kitDir = path.join(distDir, 'delivery', `ai-chat-buyer-kit-${version}`);
const reportPath = path.join(kitDir, 'RELEASE_REPORT.md');

let failed = false;
let warned = false;
const lines = [];

function rel(abs) {
  return path.relative(root, abs).replace(/\\/g, '/');
}

function run(cmd, args, options = {}) {
  return spawnSync(cmd, args, {
    cwd: root,
    encoding: 'utf8',
    shell: false,
    ...options
  });
}

function sha256File(file) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(file));
  return hash.digest('hex');
}

function check(status, label, detail = '') {
  if (status === 'fail') failed = true;
  if (status === 'warn') warned = true;
  const mark = status === 'ok' ? 'OK' : status === 'warn' ? 'WARN' : 'FAIL';
  lines.push(`- ${mark}: ${label}${detail ? ` — ${detail}` : ''}`);
}

function commandDetail(result) {
  return (result.stdout || result.stderr || '').trim().split('\n').slice(-3).join(' / ');
}

function listFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  const out = [];
  const walk = current => {
    for (const name of fs.readdirSync(current)) {
      const file = path.join(current, name);
      const stat = fs.statSync(file);
      if (stat.isDirectory()) walk(file);
      else out.push(file);
    }
  };
  walk(dir);
  return out;
}

function scanTextFiles(files, patterns) {
  const hits = [];
  for (const file of files) {
    const stat = fs.statSync(file);
    if (stat.size > 5 * 1024 * 1024) continue;
    const buf = fs.readFileSync(file);
    if (buf.includes(0)) continue;
    const text = buf.toString('utf8');
    for (const pattern of patterns) {
      if (pattern.test(text)) hits.push(rel(file));
    }
  }
  return [...new Set(hits)];
}

function asarHasForbidden(appAsar) {
  if (!fs.existsSync(appAsar)) return [`missing ${rel(appAsar)}`];
  const result = run('npx', ['asar', 'list', appAsar]);
  if (result.status !== 0) return [`asar list failed for ${rel(appAsar)}`];
  const forbidden = /data\/configs|data\/sessions|asset_index|hunyuan3d_service|Hunyuan3D-2|ps_addon|configs\.json|sessions\.json/;
  return result.stdout.split('\n').filter(line => forbidden.test(line));
}

lines.push(`# ${productName} ${version} Release Report`);
lines.push('');
lines.push(`Generated: ${new Date().toISOString()}`);
lines.push(`Git: ${commandDetail(run('git', ['rev-parse', '--short', 'HEAD'])) || 'unknown'}`);
lines.push('');

lines.push('## Installers');
const dmgs = fs.existsSync(distDir)
  ? fs.readdirSync(distDir)
      .filter(name => name.endsWith('.dmg') && name.includes(productName))
      .sort()
      .map(name => path.join(distDir, name))
  : [];

if (dmgs.length) check('ok', 'DMG installers found', dmgs.map(file => path.basename(file)).join(', '));
else check('fail', 'DMG installers found');

for (const dmg of dmgs) {
  const stat = fs.statSync(dmg);
  check('ok', `${path.basename(dmg)} SHA256`, sha256File(dmg));
  check('ok', `${path.basename(dmg)} size`, `${(stat.size / 1024 / 1024).toFixed(1)} MB`);
  const verify = run('hdiutil', ['verify', dmg]);
  if (verify.status === 0) check('ok', `${path.basename(dmg)} hdiutil verify`);
  else check('fail', `${path.basename(dmg)} hdiutil verify`, commandDetail(verify));
}
lines.push('');

lines.push('## Buyer Kit');
if (fs.existsSync(kitDir)) check('ok', 'buyer kit exists', rel(kitDir));
else check('fail', 'buyer kit exists', rel(kitDir));

const manifestPath = path.join(kitDir, 'MANIFEST.json');
if (fs.existsSync(manifestPath)) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  if (Array.isArray(manifest.warnings) && manifest.warnings.length === 0) check('ok', 'buyer kit manifest has no warnings');
  else check('fail', 'buyer kit manifest has warnings', (manifest.warnings || []).join('; '));
  if (Array.isArray(manifest.checksums) && manifest.checksums.length === dmgs.length) check('ok', 'manifest records installer checksums');
  else check('fail', 'manifest records installer checksums');
} else {
  check('fail', 'MANIFEST.json exists');
}

const checksumsPath = path.join(kitDir, 'CHECKSUMS.txt');
if (fs.existsSync(checksumsPath)) check('ok', 'CHECKSUMS.txt exists');
else check('fail', 'CHECKSUMS.txt exists');

const buyerFiles = listFiles(kitDir);
check('ok', 'buyer kit file count', String(buyerFiles.length));

const secretPatterns = [
  /sk-[A-Za-z0-9_-]{20,}/,
  /AIza[0-9A-Za-z_-]{20,}/,
  /AKIA[0-9A-Z]{16}/,
  /ghp_[A-Za-z0-9]{20,}/,
  /github_pat_[A-Za-z0-9_]{20,}/,
  /BEGIN (RSA|OPENSSH|PRIVATE) KEY/
];
const secretHits = scanTextFiles(buyerFiles, secretPatterns);
if (secretHits.length) check('fail', 'buyer kit has no high-confidence secret patterns', secretHits.join(', '));
else check('ok', 'buyer kit has no high-confidence secret patterns');

const forbiddenNames = /(configs\.json|sessions\.json|asset_index\.json|hunyuan3d_service|ps_addon)/;
const forbiddenFiles = buyerFiles.map(rel).filter(file => forbiddenNames.test(file));
if (forbiddenFiles.length) check('fail', 'buyer kit excludes runtime/private service files', forbiddenFiles.join(', '));
else check('ok', 'buyer kit excludes runtime/private service files');
lines.push('');

lines.push('## Packaged App');
const asars = [
  path.join(distDir, 'mac-arm64', `${productName}.app`, 'Contents', 'Resources', 'app.asar'),
  path.join(distDir, 'mac', `${productName}.app`, 'Contents', 'Resources', 'app.asar')
];
for (const appAsar of asars) {
  const hits = asarHasForbidden(appAsar);
  if (hits.length) check('fail', `${rel(appAsar)} excludes runtime/private service files`, hits.join(', '));
  else check('ok', `${rel(appAsar)} excludes runtime/private service files`);
}
lines.push('');

lines.push('## Dependency Audit');
const audit = run('npm', ['audit', '--omit=dev', '--json']);
if (audit.status === 0) {
  const parsed = JSON.parse(audit.stdout);
  const total = parsed.metadata && parsed.metadata.vulnerabilities ? parsed.metadata.vulnerabilities.total : 'unknown';
  if (total === 0) check('ok', 'production dependency audit has 0 vulnerabilities');
  else check('fail', 'production dependency audit has vulnerabilities', String(total));
} else {
  check('fail', 'production dependency audit runs', commandDetail(audit));
}
lines.push('');

lines.push('## macOS Signing Gate');
const apps = [
  path.join(distDir, 'mac-arm64', `${productName}.app`),
  path.join(distDir, 'mac', `${productName}.app`)
];
for (const app of apps) {
  if (!fs.existsSync(app)) {
    check('fail', `${rel(app)} exists`);
    continue;
  }
  const code = run('codesign', ['--verify', '--deep', '--strict', '--verbose=2', app]);
  if (code.status === 0) check('ok', `${rel(app)} codesign verification`);
  else check('warn', `${rel(app)} codesign verification`, commandDetail(code));

  const assess = run('spctl', ['--assess', '--type', 'execute', '--verbose', app]);
  if (assess.status === 0) check('ok', `${rel(app)} Gatekeeper assessment`);
  else check('warn', `${rel(app)} Gatekeeper assessment`, commandDetail(assess));
}
check('warn', 'public launch signing status', 'Apple Developer ID signing and notarization are still required for broad public paid distribution.');
lines.push('');

lines.push('## Result');
if (failed) lines.push('FAIL: Do not deliver this build until failed checks are fixed.');
else if (warned) lines.push('PASS WITH WARNINGS: usable for controlled/manual delivery; resolve warnings before broad public launch.');
else lines.push('PASS: release artifacts passed all configured checks.');
lines.push('');

if (!fs.existsSync(kitDir)) fs.mkdirSync(kitDir, { recursive: true });
fs.writeFileSync(reportPath, lines.join('\n'));
console.log(lines.join('\n'));
console.log(`\nReport written to ${rel(reportPath)}`);

if (failed) process.exit(1);
