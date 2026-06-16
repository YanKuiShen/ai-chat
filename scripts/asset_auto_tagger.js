#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'data');
const LOG_FILE = path.join(DATA_DIR, 'asset_auto_tagger.jsonl');
const PID_FILE = path.join(DATA_DIR, 'asset_auto_tagger.pid');
const API_BASE = process.env.ASSET_TAGGER_API || 'http://localhost:3456';
const INTERVAL_MS = Math.max(30000, Number(process.env.ASSET_TAGGER_INTERVAL_MS || 90000));

const JOBS = [
  { type: 'textures', q: 'wood floor stone wall concrete fabric metal', limit: 10 },
  { type: 'textures', q: 'brick marble plaster tiles asphalt roof', limit: 10 },
  { type: 'textures', q: 'leather cloth carpet fabric woven pattern', limit: 10 },
  { type: 'textures', q: 'grass moss bark leaves soil gravel sand', limit: 10 },
  { type: 'textures', q: 'rust metal painted steel gold copper', limit: 10 },
  { type: 'textures', q: 'water mud snow ice terrain path', limit: 10 },
  { type: 'hdris', q: 'sunset studio overcast indoor forest', limit: 6 },
  { type: 'hdris', q: 'night city morning cloudy sky warehouse', limit: 6 },
  { type: 'hdris', q: 'dawn beach mountains room workshop', limit: 6 },
];

let cursor = Number(process.env.ASSET_TAGGER_CURSOR || 0) || 0;
let stopped = false;

function uniq(items) {
  return [...new Set((items || [])
    .flatMap(v => Array.isArray(v) ? v : [v])
    .filter(v => v !== undefined && v !== null)
    .map(v => String(v).trim())
    .filter(Boolean))];
}

function has(text, words) {
  return words.some(w => text.includes(w));
}

function enrichAsset(asset) {
  const derivedTagBlocklist = new Set([
    'floor material',
    'ground surface',
    'wall material',
    'roof material',
    'terrain material',
    'hard surface material',
    'soft material',
    'ai tagged',
    'metadata only',
  ]);
  const tags = uniq(asset.tags || []).filter(t => !derivedTagBlocklist.has(String(t).toLowerCase()));
  const primaryText = [
    asset.id,
    asset.display_name,
    ...(asset.aliases || []),
  ].join(' ').toLowerCase().replace(/[_-]+/g, ' ');
  const text = [
    asset.id,
    asset.display_name,
    asset.category,
    asset.description,
    ...(asset.aliases || []),
    ...tags,
  ].join(' ').toLowerCase().replace(/[_-]+/g, ' ');
  const addTags = [];
  const materials = [];
  const colors = [];
  const visual = [];
  const usage = [];
  const avoid = [];
  let category = asset.category || '';

  const materialRules = [
    ['wood', ['wood', 'plank', 'timber', 'bark', 'floorboard']],
    ['stone', ['stone', 'rock', 'granite', 'slate', 'marble', 'limestone', 'pebble']],
    ['concrete', ['concrete', 'cement', 'plaster']],
    ['brick', ['brick', 'masonry']],
    ['metal', ['metal', 'steel', 'iron', 'copper', 'gold', 'aluminium', 'aluminum', 'rust']],
    ['fabric', ['fabric', 'cloth', 'woven', 'carpet', 'rug', 'canvas']],
    ['leather', ['leather']],
    ['glass', ['glass']],
    ['ceramic', ['ceramic', 'tile', 'tiles']],
    ['soil', ['soil', 'mud', 'dirt', 'earth']],
    ['sand', ['sand', 'beach']],
    ['snow', ['snow', 'ice']],
    ['grass', ['grass', 'moss', 'leaf', 'leaves', 'foliage']],
    ['asphalt', ['asphalt', 'road']],
  ];
  for (const [material, words] of materialRules) {
    if (has(text, words)) {
      materials.push(material);
      addTags.push(material);
    }
  }

  const colorRules = [
    ['white', ['white', 'snow', 'chalk']],
    ['black', ['black', 'charcoal']],
    ['gray', ['gray', 'grey', 'concrete', 'slate', 'asphalt']],
    ['brown', ['brown', 'wood', 'bark', 'soil', 'mud', 'rust']],
    ['green', ['green', 'grass', 'moss', 'leaf', 'forest']],
    ['red', ['red', 'brick', 'rust', 'copper']],
    ['yellow', ['yellow', 'sand', 'gold']],
    ['blue', ['blue', 'sky', 'night']],
  ];
  for (const [color, words] of colorRules) {
    if (has(text, words)) colors.push(color);
  }

  const visualRules = [
    ['rough surface', ['rough', 'gravel', 'rock', 'bark', 'weathered']],
    ['worn aged', ['worn', 'aged', 'old', 'weathered', 'scratched', 'damaged']],
    ['clean surface', ['clean', 'smooth', 'polished']],
    ['patterned', ['pattern', 'woven', 'tile', 'brick', 'plank']],
    ['natural variation', ['natural', 'grass', 'stone', 'wood', 'soil', 'leaf']],
    ['industrial', ['metal', 'concrete', 'asphalt', 'warehouse']],
    ['rustic', ['rustic', 'aged wood', 'cottage']],
  ];
  for (const [feature, words] of visualRules) {
    if (has(text, words)) visual.push(feature);
  }

  if (asset.type === 'hdri') {
    category = 'environment';
    usage.push('world lighting', 'environment background', 'reflection source');
    avoid.push('surface material', 'mesh geometry', 'object prop');
    if (has(text, ['studio', 'indoor', 'room', 'workshop', 'warehouse'])) usage.push('indoor lighting');
    if (has(text, ['forest', 'beach', 'mountain', 'city', 'sky', 'sunset', 'dawn', 'overcast'])) usage.push('outdoor lighting');
    if (has(text, ['sunset', 'dawn', 'morning'])) visual.push('warm directional light');
    if (has(text, ['overcast', 'cloudy'])) visual.push('soft diffuse light');
  } else if (asset.type === 'texture') {
    avoid.push('standalone mesh', 'object model', 'environment hdri');
    if (has(primaryText, ['wall', 'brick wall', 'stone wall', 'concrete wall', 'plaster'])) {
      category = 'wall_material';
      usage.push('wall surface material', 'architecture material');
      addTags.push('wall material');
    } else if (has(primaryText, ['floor', 'ground', 'road', 'asphalt', 'carpet', 'rug'])) {
      category = 'floor_material';
      usage.push('floor surface material', 'ground plane material');
      addTags.push('floor material', 'ground surface');
    } else if (has(primaryText, ['roof', 'shingle'])) {
      category = 'roof_material';
      usage.push('roof surface material', 'architecture material');
    } else if (has(primaryText, ['grass', 'moss', 'soil', 'sand', 'snow', 'mud', 'gravel'])) {
      category = 'terrain_material';
      usage.push('terrain material', 'outdoor ground surface');
    } else if (has(primaryText, ['fabric', 'leather', 'cloth', 'woven'])) {
      category = 'soft_material';
      usage.push('furniture upholstery', 'cloth surface material');
    } else if (has(primaryText, ['metal', 'steel', 'copper', 'rust', 'gold'])) {
      category = 'hard_surface_material';
      usage.push('hard surface material', 'prop or architecture material');
    } else if (has(text, ['wall', 'brick', 'plaster', 'masonry'])) {
      category = 'wall_material';
      usage.push('wall surface material', 'architecture material');
      addTags.push('wall material');
    } else if (has(text, ['roof', 'shingle'])) {
      category = 'roof_material';
      usage.push('roof surface material', 'architecture material');
    } else if (has(text, ['fabric', 'leather', 'cloth', 'woven'])) {
      category = 'soft_material';
      usage.push('furniture upholstery', 'cloth surface material');
    } else if (has(text, ['grass', 'moss', 'soil', 'sand', 'snow', 'mud', 'gravel'])) {
      category = 'terrain_material';
      usage.push('terrain material', 'outdoor ground surface');
    } else if (has(text, ['metal', 'steel', 'copper', 'rust', 'gold'])) {
      category = 'hard_surface_material';
      usage.push('hard surface material', 'prop or architecture material');
    } else {
      category = category || 'pbr_material';
      usage.push('surface material');
    }
  }

  const notes = uniq([
    asset.notes || '',
    `AI semantic retag ${new Date().toISOString()}: material/use/avoid labels refined from metadata only; no download.`,
  ]).join('\n');

  return {
    tags: uniq([...tags, ...addTags, 'ai tagged', 'metadata only']).slice(0, 80),
    materials: uniq(materials).slice(0, 20),
    colors: uniq(colors).slice(0, 16),
    visual_features: uniq(visual).slice(0, 24),
    semantic_roles: uniq(usage).slice(0, 24),
    usage: uniq(usage).slice(0, 24),
    avoid: uniq(avoid).slice(0, 16),
    category,
    notes,
  };
}

async function patchAsset(asset, enrichment) {
  const res = await fetch(`${API_BASE}/api/assets/index/${encodeURIComponent(asset.id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(enrichment),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || `PATCH ${asset.id} HTTP ${res.status}`);
}

async function semanticRetag(limit = 500) {
  const res = await fetch(`${API_BASE}/api/assets/index`);
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || `index HTTP ${res.status}`);
  const assets = (data.assets || [])
    .filter(a => a.origin === 'network_index' && a.source === 'polyhaven')
    .slice(-limit);
  let patched = 0;
  for (const asset of assets) {
    await patchAsset(asset, enrichAsset(asset));
    patched += 1;
  }
  log('ai_retagged', { patched, download: false });
  return patched;
}

function log(event, extra = {}) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.appendFileSync(LOG_FILE, JSON.stringify({
    ts: new Date().toISOString(),
    event,
    pid: process.pid,
    ...extra,
  }) + '\n');
}

async function runOne() {
  const job = JOBS[cursor % JOBS.length];
  cursor = (cursor + 1) % JOBS.length;
  const startedAt = Date.now();
  const res = await fetch(`${API_BASE}/api/assets/index/polyhaven`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(job),
  });
  const text = await res.text();
  let data = {};
  try {
    data = JSON.parse(text);
  } catch {
    data = { ok: false, error: text.slice(0, 300) };
  }
  if (!res.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  log('indexed', {
    job,
    indexed: data.indexed || 0,
    count: data.count || 0,
    duration_ms: Date.now() - startedAt,
    download: false,
  });
  await semanticRetag();
}

async function loop() {
  while (!stopped) {
    try {
      await runOne();
      await new Promise(resolve => setTimeout(resolve, INTERVAL_MS));
    } catch (err) {
      log('error', { error: err.message || String(err), retry_ms: Math.max(INTERVAL_MS, 180000) });
      await new Promise(resolve => setTimeout(resolve, Math.max(INTERVAL_MS, 180000)));
    }
  }
}

process.on('SIGINT', () => {
  stopped = true;
  log('stop', { signal: 'SIGINT' });
  process.exit(0);
});

process.on('SIGTERM', () => {
  stopped = true;
  log('stop', { signal: 'SIGTERM' });
  process.exit(0);
});

log('start', { api: API_BASE, interval_ms: INTERVAL_MS, download: false });
fs.writeFileSync(PID_FILE, String(process.pid) + '\n');
loop();
