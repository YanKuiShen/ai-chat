#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const version = pkg.version || '0.0.0';
const productName = (pkg.build && pkg.build.productName) || '白歌的AI讨论组';
const outRoot = path.join(root, 'dist', 'delivery');
const kitDir = path.join(outRoot, `ai-chat-buyer-kit-${version}`);

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function copyFile(relSrc, relDest = relSrc) {
  const src = path.join(root, relSrc);
  const dest = path.join(kitDir, relDest);
  if (!fs.existsSync(src)) return { ok: false, src: relSrc, dest: relDest, reason: 'missing source' };
  ensureDir(path.dirname(dest));
  fs.copyFileSync(src, dest);
  return { ok: true, src: relSrc, dest: relDest, bytes: fs.statSync(dest).size };
}

function copyDirFiles(srcRel, destRel, filter) {
  const srcDir = path.join(root, srcRel);
  const copied = [];
  if (!fs.existsSync(srcDir)) return copied;
  for (const name of fs.readdirSync(srcDir).sort()) {
    const src = path.join(srcDir, name);
    if (!fs.statSync(src).isFile()) continue;
    if (filter && !filter(name)) continue;
    copied.push(copyFile(path.join(srcRel, name), path.join(destRel, name)));
  }
  return copied;
}

function findBuiltDmgs() {
  const distDir = path.join(root, 'dist');
  if (!fs.existsSync(distDir)) return [];
  return fs.readdirSync(distDir)
    .filter(name => name.endsWith('.dmg') && name.includes(productName))
    .sort()
    .map(name => path.join('dist', name));
}

function newestMtime(files) {
  return files
    .map(file => path.join(root, file))
    .filter(file => fs.existsSync(file))
    .map(file => fs.statSync(file).mtimeMs)
    .reduce((max, mtime) => Math.max(max, mtime), 0);
}

function writeText(relDest, content) {
  const dest = path.join(kitDir, relDest);
  ensureDir(path.dirname(dest));
  fs.writeFileSync(dest, content);
  return { ok: true, src: '(generated)', dest: relDest, bytes: Buffer.byteLength(content) };
}

if (fs.existsSync(kitDir)) fs.rmSync(kitDir, { recursive: true, force: true });
ensureDir(kitDir);

const copied = [];

const buyerDocs = [
  'INSTALL.md',
  'FIRST_SCENE_TUTORIAL.md',
  'THIRD_PARTY_NOTICES.md',
  'REFUND_AND_SUPPORT.md',
  'DELIVERY_MESSAGE.md',
  'COMMERCIAL_TERMS_DRAFT.md'
];

for (const name of buyerDocs) {
  copied.push(copyFile(path.join('docs/marketing/buyer-docs', name), path.join('buyer-docs', name)));
}

[
  'docs/marketing/site/index.html',
  'docs/marketing/pricing-and-offer.md',
  'docs/marketing/sales-delivery-flow.md',
  'docs/marketing/release-packaging.md'
].forEach(file => copied.push(copyFile(file, file.replace(/^docs\/marketing\//, 'marketing/'))));

copied.push(...copyDirFiles(
  'docs/marketing/screenshots',
  'marketing/screenshots',
  name => [
    '01-home-overview.png',
    '02-workflow-builder-clean.png',
    '03-mindmap-notes-clean.png',
    '04-photography-tools-clean.png',
    '05-one-click-3d-modeling.png',
    '06-blender-agent-rendering.png'
  ].includes(name)
));

const dmgs = findBuiltDmgs();
for (const dmg of dmgs) {
  copied.push(copyFile(dmg, path.join('installers', path.basename(dmg))));
}

const freshnessInputs = [
  'package.json',
  'main.js',
  'server.js',
  'public/index.html',
  'blender_addon/aichat_bridge/__init__.py'
];
const newestSourceMtime = newestMtime(freshnessInputs);
const staleDmgs = dmgs.filter(dmg => {
  const abs = path.join(root, dmg);
  return fs.existsSync(abs) && fs.statSync(abs).mtimeMs < newestSourceMtime;
});

const missing = copied.filter(item => !item.ok);
const generatedAt = new Date().toISOString();
const manifest = {
  product: productName,
  version,
  generated_at: generatedAt,
  kit_dir: path.relative(root, kitDir),
  installers_found: dmgs.map(name => path.basename(name)),
  warnings: [
    ...(dmgs.length ? [] : ['No DMG installers were found in dist/. Run npm run build:mac before making a final buyer delivery bundle.']),
    ...staleDmgs.map(dmg => `${path.basename(dmg)} is older than current source files. Run npm run build:mac before final delivery.`),
    ...missing.map(item => `Missing ${item.src}: ${item.reason}`)
  ],
  files: copied.filter(item => item.ok).map(item => ({
    path: item.dest,
    source: item.src,
    bytes: item.bytes
  }))
};

copied.push(writeText('MANIFEST.json', JSON.stringify(manifest, null, 2) + '\n'));
copied.push(writeText('README.md', `# ${productName} Buyer Kit ${version}

Generated: ${generatedAt}

## Contents

- \`buyer-docs/\`: installation guide, first-scene tutorial, third-party notices, refund/support policy, delivery message, and commercial terms draft.
- \`marketing/site/index.html\`: static landing page prototype.
- \`marketing/screenshots/\`: selected product screenshots for sales pages.
- \`installers/\`: DMG installers, if \`npm run build:mac\` has already produced them.
- \`MANIFEST.json\`: generated file list and warnings.

## Final Delivery Steps

1. Run \`npm run check:release:strict\` from a clean worktree.
2. Run \`npm run build:addon\`.
3. Run \`npm run build:mac\`.
4. Run \`npm run build:buyer-kit\`.
5. Upload this buyer kit folder or selected files to your delivery channel.

## Important Notes

- API keys are not included.
- PS assistant is not included in the sales edition.
- Hunyuan3D is an external-service interface only. Users self-deploy compatible services and follow the original license.
- Generated output quality depends on models, prompts, Blender, plugins, and third-party services.
`));

if (missing.length) {
  console.error('Buyer kit generated with missing required files:');
  missing.forEach(item => console.error(`- ${item.src}: ${item.reason}`));
  process.exitCode = 1;
} else {
  console.log(`Buyer kit generated: ${path.relative(root, kitDir)}`);
  if (!dmgs.length) {
    console.log('WARN No DMG installers found. Build macOS installers before final delivery.');
  }
  if (staleDmgs.length) {
    staleDmgs.forEach(dmg => console.log(`WARN ${path.basename(dmg)} is older than current source files.`));
  }
  console.log(`Files: ${manifest.files.length + 2}`);
}
