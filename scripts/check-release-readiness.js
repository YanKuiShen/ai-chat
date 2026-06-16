#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const strict = process.argv.includes('--strict') || process.env.RELEASE_STRICT === '1';
let failed = false;
let warned = false;

function rel(p) {
  return path.relative(root, p).replace(/\\/g, '/');
}

function log(status, message) {
  const icon = status === 'ok' ? 'OK  ' : status === 'warn' ? 'WARN' : 'FAIL';
  console.log(`${icon} ${message}`);
  if (status === 'warn') warned = true;
  if (status === 'fail') failed = true;
}

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8');
}

function exists(file) {
  return fs.existsSync(path.join(root, file));
}

function run(cmd, args, options = {}) {
  return spawnSync(cmd, args, {
    cwd: root,
    encoding: 'utf8',
    shell: false,
    ...options
  });
}

function requireMatch(file, pattern, message) {
  const text = read(file);
  if (pattern.test(text)) log('ok', message);
  else log('fail', `${message} (${file})`);
}

function requireNoMatch(file, pattern, message) {
  const text = read(file);
  if (!pattern.test(text)) log('ok', message);
  else log('fail', `${message} (${file})`);
}

console.log('Release readiness check\n');

const pkg = JSON.parse(read('package.json'));
const buildFiles = pkg.build && Array.isArray(pkg.build.files) ? pkg.build.files : [];
const fileList = buildFiles.join('\n');

if (pkg.scripts && pkg.scripts['build:mac']) log('ok', 'macOS build script exists');
else log('fail', 'macOS build script exists');

if (pkg.scripts && pkg.scripts['build:addon']) log('ok', 'Blender addon zip build script exists');
else log('fail', 'Blender addon zip build script exists');

[
  'data/configs.json',
  'data/sessions.json',
  '3d/hunyuan3d_service.py',
  '3d/Hunyuan3D-2-main',
  '3d/Hunyuan3D-2mini-weights',
  'ps_addon'
].forEach(item => {
  if (!fileList.includes(item)) log('ok', `electron build.files excludes ${item}`);
  else log('fail', `electron build.files excludes ${item}`);
});

const gitignore = read('.gitignore');
[
  'data/configs.json',
  'data/sessions.json',
  '*.dmg',
  '*.safetensors',
  '3d/hunyuan3d-env/'
].forEach(item => {
  if (gitignore.includes(item)) log('ok', `.gitignore protects ${item}`);
  else log('fail', `.gitignore protects ${item}`);
});

requireMatch('server.js', /const ENABLE_PS_BRIDGE = IS_DEV_EDITION \|\| process\.env\.AI_CHAT_ENABLE_PS_BRIDGE === '1';/, 'PS bridge is disabled by default');
requireMatch('server.js', /if \(ENABLE_PS_BRIDGE\) setTimeout\(startPSBridge, 1000\);/, 'PS bridge does not auto-start in sales mode');
requireMatch('server.js', /const ENABLE_HUNYUAN_AUTOSTART = IS_DEV_EDITION \|\| process\.env\.AI_CHAT_ENABLE_HUNYUAN_AUTOSTART === '1';/, 'Hunyuan autostart is disabled by default');
requireMatch('server.js', /销售版保留混元3D接口，但不内置启动混元服务/, 'Hunyuan remains an external-service interface');

requireMatch('public/index.html', /hideViews: \['psassist'\]/, 'sales UI hides only PS assistant view');
requireNoMatch('public/index.html', /btn-photo-hy3dtest[^>]+sale-hidden|agent-hunyuan3d-card[^>]+sale-hidden/, 'Hunyuan UI is not hidden in sales mode');
requireMatch('public/index.html', /混元3D接口/, 'Hunyuan UI is labeled as an interface');
requireMatch('public/index.html', /用户需自行部署混元3D服务/, 'Hunyuan UI tells users to self-deploy service');

[
  'docs/marketing/site/index.html',
  'docs/marketing/buyer-docs/INSTALL.md',
  'docs/marketing/buyer-docs/FIRST_SCENE_TUTORIAL.md',
  'docs/marketing/buyer-docs/THIRD_PARTY_NOTICES.md',
  'docs/marketing/buyer-docs/REFUND_AND_SUPPORT.md',
  'docs/marketing/screenshots/06-blender-agent-rendering.png',
  'docs/marketing/screenshots/05-one-click-3d-modeling.png'
].forEach(file => {
  if (exists(file)) log('ok', `${file} exists`);
  else log('fail', `${file} exists`);
});

function checkLandingPageRefs() {
  const file = path.join(root, 'docs/marketing/site/index.html');
  const html = fs.readFileSync(file, 'utf8');
  const dir = path.dirname(file);
  const refs = [...html.matchAll(/(?:src|href)="([^"]+)"/g)]
    .map(m => m[1])
    .filter(ref => !ref.startsWith('#') && !/^https?:/.test(ref) && !ref.startsWith('mailto:'));
  const missing = refs.filter(ref => !fs.existsSync(path.resolve(dir, ref)));
  if (missing.length) log('fail', `landing page has missing local refs: ${missing.join(', ')}`);
  else log('ok', 'landing page local refs resolve');
}

checkLandingPageRefs();

const syntax = run(process.execPath, ['--check', 'server.js']);
if (syntax.status === 0) log('ok', 'server.js syntax check passes');
else {
  log('fail', 'server.js syntax check passes');
  if (syntax.stderr) console.error(syntax.stderr.trim());
}

const secretPatterns = [
  /sk-[A-Za-z0-9_-]{20,}/,
  /AIza[0-9A-Za-z_-]{20,}/,
  /AKIA[0-9A-Z]{16}/,
  /ghp_[A-Za-z0-9]{20,}/,
  /github_pat_[A-Za-z0-9_]{20,}/,
  /BEGIN (RSA|OPENSSH|PRIVATE) KEY/
];

const scanFiles = [
  'server.js',
  'package.json',
  'public/index.html',
  'docs/marketing/README.md',
  'docs/marketing/website-copy.md',
  'docs/marketing/pricing-and-offer.md',
  'docs/marketing/site/index.html',
  'docs/marketing/buyer-docs/INSTALL.md',
  'docs/marketing/buyer-docs/THIRD_PARTY_NOTICES.md',
  'docs/marketing/buyer-docs/COMMERCIAL_TERMS_DRAFT.md'
];

const secretHits = [];
for (const file of scanFiles) {
  const text = read(file);
  for (const pattern of secretPatterns) {
    if (pattern.test(text)) secretHits.push(file);
  }
}
if (secretHits.length) log('fail', `possible secret patterns found in ${[...new Set(secretHits)].join(', ')}`);
else log('ok', 'no high-confidence secret patterns in release-facing files');

const status = run('git', ['status', '--porcelain']);
const dirty = status.stdout.trim().split('\n').filter(Boolean);
const nonRuntimeDirty = dirty.filter(line => !line.endsWith('data/asset_index.json'));
if (dirty.length === 0) {
  log('ok', 'git worktree is clean');
} else if (nonRuntimeDirty.length === 0 && !strict) {
  log('warn', 'only data/asset_index.json is dirty; ignored for this non-strict check');
} else if (!strict) {
  log('warn', `worktree has uncommitted changes: ${dirty.join('; ')}`);
} else {
  log('fail', `strict mode requires clean worktree: ${dirty.join('; ')}`);
}

console.log('');
if (failed) {
  console.error('Release readiness check failed.');
  process.exit(1);
}
if (warned) {
  console.log('Release readiness check passed with warnings.');
} else {
  console.log('Release readiness check passed.');
}
