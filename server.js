const express = require('express');
const axios = require('axios');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { exec } = require('child_process');
const { randomUUID, createHash } = require('crypto');
let sharp;
try { sharp = require('sharp'); } catch(e) { console.warn('[warn] sharp not installed, generate_texture resize disabled'); }

const app = express();
const IS_DEV_EDITION = process.env.AI_CHAT_EDITION === 'dev';
const ENABLE_PS_BRIDGE = IS_DEV_EDITION || process.env.AI_CHAT_ENABLE_PS_BRIDGE === '1';
const ENABLE_HUNYUAN_AUTOSTART = IS_DEV_EDITION || process.env.AI_CHAT_ENABLE_HUNYUAN_AUTOSTART === '1';

app.use(cors());
app.use((req, res, next) => {
  if (req.path === '/' || req.path.endsWith('.html')) {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
  }
  next();
});
// ==================== PS Bridge 进程管理 ====================
const { spawn } = require('child_process');
let psBridgeProcess = null;
let psBridgePort = 8765;
let _psBridgeShutdown = false;  // v3.8.1：app 退出时置 true，阻止 PS bridge exit handler 自动重启

function startPSBridge() {
  if (!ENABLE_PS_BRIDGE) {
    console.log('[PS Bridge] 销售版默认关闭，如需开发测试请设置 AI_CHAT_ENABLE_PS_BRIDGE=1');
    return;
  }
  if (psBridgeProcess) return;
  const bridgeScript = path.join(__dirname, 'ps_addon', 'aichat_ps_bridge', 'ps_mcp_bridge.py');
  if (!fs.existsSync(bridgeScript)) {
    console.log('[PS Bridge] 脚本未找到: ' + bridgeScript);
    return;
  }
  console.log('[PS Bridge] 正在启动...');
  let psBridgeErrBuf = '';
  psBridgeProcess = spawn('python3', [bridgeScript, '--port', String(psBridgePort)], {
    stdio: 'pipe',
    detached: false
  });
  psBridgeProcess.stdout.on('data', (d) => console.log('[PS Bridge]', d.toString().trim()));
  psBridgeProcess.stderr.on('data', (d) => {
    const s = d.toString();
    psBridgeErrBuf += s;
    if (psBridgeErrBuf.length > 8000) psBridgeErrBuf = psBridgeErrBuf.slice(-8000);
    console.log('[PS Bridge]', s.trim());
  });
  psBridgeProcess.on('exit', (code) => {
    console.log('[PS Bridge] 已退出, code:', code);
    psBridgeProcess = null;
    if (/Address already in use|Errno 48|EADDRINUSE/i.test(psBridgeErrBuf)) {
      console.log(`[PS Bridge] 端口 ${psBridgePort} 已被占用，停止自动重启（通常表示已有 PS Bridge 在运行）`);
      return;
    }
    // Auto-restart after 3 seconds
    setTimeout(() => { if (!_psBridgeShutdown && !psBridgeProcess) startPSBridge(); }, 3000);
  });
  psBridgeProcess.on('error', (err) => {
    console.log('[PS Bridge] 启动失败:', err.message);
    psBridgeProcess = null;
  });
}

function stopPSBridge() {
  if (psBridgeProcess) {
    psBridgeProcess.kill();
    psBridgeProcess = null;
  }
}

// Auto-start PS Bridge on server startup only for dev/test builds.
if (ENABLE_PS_BRIDGE) setTimeout(startPSBridge, 1000);

// PS Bridge 状态端点
app.get('/api/ps-mcp/status', (req, res) => {
  if (!ENABLE_PS_BRIDGE) {
    return res.json({
      running: false,
      disabled: true,
      message: 'PS 辅助未包含在销售版中'
    });
  }
  res.json({
    running: psBridgeProcess !== null,
    port: psBridgePort,
    pid: psBridgeProcess?.pid || null
  });
});

app.post('/api/ps-mcp/restart', (req, res) => {
  if (!ENABLE_PS_BRIDGE) {
    return res.status(403).json({ ok: false, error: 'PS 辅助未包含在销售版中' });
  }
  stopPSBridge();
  setTimeout(() => { startPSBridge(); res.json({ ok: true, status: 'restarted' }); }, 500);
});


app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

const HUNYUAN_MODELS_DIR = path.join(os.homedir(), 'Desktop', 'ai-chat-workspace', '_hunyuan3d_models');
app.use('/workspace-models', (req, res, next) => {
  const decoded = decodeURIComponent(req.path || '');
  if (decoded.includes('..') || path.isAbsolute(decoded)) {
    return res.status(400).json({ ok: false, error: '非法模型路径' });
  }
  const abs = path.resolve(HUNYUAN_MODELS_DIR, '.' + decoded);
  if (!abs.startsWith(path.resolve(HUNYUAN_MODELS_DIR) + path.sep)) {
    return res.status(403).json({ ok: false, error: '路径不在允许目录内' });
  }
  next();
}, express.static(HUNYUAN_MODELS_DIR));

// 数据存储路径
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const SESSIONS_FILE = path.join(DATA_DIR, 'sessions.json');
const CONFIGS_FILE = path.join(DATA_DIR, 'configs.json');
const ASSET_LIBRARY_DIR = process.env.AI_CHAT_ASSET_LIBRARY_DIR || path.join(DATA_DIR, 'asset_library');
const ASSET_INDEX_FILE = path.join(DATA_DIR, 'asset_index.json');

// 初始化数据目录
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}
if (!fs.existsSync(SESSIONS_FILE)) {
  fs.writeFileSync(SESSIONS_FILE, JSON.stringify({ sessions: [], messages: [] }, null, 2));
}
if (!fs.existsSync(CONFIGS_FILE)) {
  fs.writeFileSync(CONFIGS_FILE, JSON.stringify([], null, 2));
}
if (!fs.existsSync(ASSET_LIBRARY_DIR)) {
  fs.mkdirSync(ASSET_LIBRARY_DIR, { recursive: true });
}
if (!fs.existsSync(ASSET_INDEX_FILE)) {
  fs.writeFileSync(ASSET_INDEX_FILE, JSON.stringify({ version: 1, updated_at: '', assets: [] }, null, 2));
}

function readData() {
  try { return JSON.parse(fs.readFileSync(SESSIONS_FILE, 'utf-8')); }
  catch { return { sessions: [], messages: [] }; }
}
function writeData(data) {
  fs.writeFileSync(SESSIONS_FILE, JSON.stringify(data, null, 2));
}

function readConfigs() {
  try { return JSON.parse(fs.readFileSync(CONFIGS_FILE, 'utf-8')); }
  catch { return []; }
}
function writeConfigs(data) {
  fs.writeFileSync(CONFIGS_FILE, JSON.stringify(data, null, 2));
}

// ==================== 素材索引 v1：扫描 + 自动打标签 + 检索调用 ====================
const ASSET_PROFILE_NAMES = new Set(['asset_profile.json', 'profile.json']);
const ASSET_FILE_EXTS = new Set(['.blend', '.glb', '.gltf', '.fbx', '.obj', '.dae', '.stl', '.ply', '.png', '.jpg', '.jpeg', '.webp', '.exr', '.hdr']);
const ASSET_PREVIEW_EXTS = new Set(['.png', '.jpg', '.jpeg', '.webp']);
const ASSET_MODEL_EXTS = new Set(['.blend', '.glb', '.gltf', '.fbx', '.obj', '.dae', '.stl', '.ply']);
const ASSET_TEXTURE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.exr']);
const ASSET_HDRI_EXTS = new Set(['.hdr', '.exr']);
const ASSET_SCAN_SKIP_DIRS = new Set(['node_modules', '.git', 'dist', 'build', '.superpowers']);
const ASSET_DEFAULT_SCAN_ROOTS = [
  ASSET_LIBRARY_DIR,
  path.join(os.homedir(), 'Library', 'Caches', 'aichat_polyhaven'),
];

const ASSET_TAG_RULES = [
  ['apple', ['apple', 'fruit', 'food', 'tabletop prop', 'kitchen prop']],
  ['苹果', ['apple', 'fruit', 'food', 'tabletop prop']],
  ['red', ['red']],
  ['红', ['red']],
  ['wood', ['wood', 'organic material']],
  ['wooden', ['wood', 'organic material']],
  ['brick', ['brick', 'wall material', 'masonry']],
  ['stone', ['stone', 'rock', 'wall material']],
  ['rock', ['stone', 'rock']],
  ['moss', ['moss', 'green', 'nature']],
  ['grass', ['grass', 'nature', 'ground']],
  ['floor', ['floor', 'ground surface']],
  ['wall', ['wall', 'architecture']],
  ['cottage', ['cottage', 'house', 'architecture']],
  ['irish', ['irish', 'countryside']],
  ['chair', ['chair', 'furniture', 'seating']],
  ['table', ['table', 'furniture', 'tabletop']],
  ['sofa', ['sofa', 'furniture', 'seating']],
  ['bed', ['bed', 'furniture']],
  ['lamp', ['lamp', 'lighting prop']],
  ['metal', ['metal', 'hard surface']],
  ['fabric', ['fabric', 'cloth', 'soft material']],
  ['leather', ['leather', 'soft material']],
  ['concrete', ['concrete', 'wall material', 'floor material']],
  ['hdri', ['hdri', 'environment light']],
  ['sunset', ['sunset', 'warm light', 'environment light']],
  ['studio', ['studio light', 'environment light']],
  ['white model', ['white model', 'untextured model', 'base mesh', 'model']],
  ['whitemodel', ['white model', 'untextured model', 'base mesh', 'model']],
  ['白模', ['white model', 'untextured model', 'base mesh', 'model']],
  ['untextured', ['white model', 'untextured model', 'base mesh', 'model']],
  ['base mesh', ['white model', 'untextured model', 'base mesh', 'model']],
  ['basemesh', ['white model', 'untextured model', 'base mesh', 'model']],
  ['clay', ['clay render', 'white model', 'untextured model', 'model']],
];

function _uniqueStrings(items) {
  return [...new Set((items || [])
    .flatMap(v => Array.isArray(v) ? v : [v])
    .filter(v => v !== undefined && v !== null)
    .map(v => String(v).trim())
    .filter(Boolean))];
}

function _safeAssetId(s) {
  return (s || '').toString().trim().toLowerCase()
    .replace(/[^a-z0-9_\-\u4e00-\u9fa5]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 80) || 'asset_' + Date.now();
}

function _assetHashId(absPath) {
  return createHash('sha1').update(absPath).digest('hex').slice(0, 12);
}

function _walkAssetFiles(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const ent of entries) {
    if (ent.name.startsWith('.') || ASSET_SCAN_SKIP_DIRS.has(ent.name)) continue;
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) _walkAssetFiles(p, out);
    else out.push(p);
  }
  return out;
}

function _readAssetIndex() {
  try {
    const data = JSON.parse(fs.readFileSync(ASSET_INDEX_FILE, 'utf8'));
    return { version: 1, updated_at: data.updated_at || '', assets: Array.isArray(data.assets) ? data.assets : [] };
  } catch {
    return { version: 1, updated_at: '', assets: [] };
  }
}

function _writeAssetIndex(assets) {
  const payload = { version: 1, updated_at: new Date().toISOString(), assets: Array.isArray(assets) ? assets : [] };
  fs.writeFileSync(ASSET_INDEX_FILE, JSON.stringify(payload, null, 2));
  return payload;
}

function _isPathInsideAnyAssetRoot(target, roots) {
  if (!target) return false;
  const abs = path.resolve(target);
  return (roots || []).some(root => {
    if (!root) return false;
    const r = path.resolve(root);
    return abs === r || abs.startsWith(r + path.sep);
  });
}

function _assetTypeFromExt(ext, filePath = '') {
  const low = filePath.toLowerCase();
  if (ASSET_MODEL_EXTS.has(ext)) return 'model';
  if (ASSET_HDRI_EXTS.has(ext) && /hdri|hdr|environment|sky|studio|sunset/.test(low)) return 'hdri';
  if (ASSET_TEXTURE_EXTS.has(ext)) return 'texture';
  return 'asset';
}

function _assetCategoryFromTags(tags, type) {
  const text = (tags || []).join(' ').toLowerCase();
  if (type === 'hdri') return 'environment';
  if (type === 'texture') {
    if (/floor|ground|wood|brick|stone|concrete|wall/.test(text)) return 'pbr_material';
    return 'texture_set';
  }
  if (/food|fruit|apple/.test(text)) return 'food_prop';
  if (/furniture|chair|table|sofa|bed/.test(text)) return 'furniture';
  if (/architecture|wall|house|cottage/.test(text)) return 'architecture';
  if (/nature|grass|moss|stone|rock/.test(text)) return 'nature_prop';
  return type || 'asset';
}

function _autoTagAsset({ name = '', rel = '', ext = '', source = 'local', extraTags = [] }) {
  const rawText = [name, rel, ext, source, ...(extraTags || [])].join(' ');
  const normalized = rawText.toLowerCase().replace(/[_\-./]+/g, ' ');
  const tokens = normalized.split(/[\s,，、()【】\[\]]+/).filter(Boolean);
  const tags = [...tokens, ...extraTags];
  const materials = [];
  const colors = [];
  const usage = [];
  const avoid = [];
  for (const [needle, adds] of ASSET_TAG_RULES) {
    if (normalized.includes(needle)) tags.push(...adds);
  }
  for (const c of ['red', 'green', 'blue', 'yellow', 'brown', 'black', 'white', 'orange', 'gray', 'grey']) {
    if (tags.includes(c)) colors.push(c);
  }
  for (const m of ['wood', 'stone', 'metal', 'fabric', 'leather', 'concrete', 'brick', 'moss', 'grass']) {
    if (tags.includes(m)) materials.push(m);
  }
  if (tags.includes('tabletop prop')) usage.push('place on table', 'foreground prop');
  if (tags.includes('furniture')) usage.push('room furnishing');
  if (tags.includes('environment light')) usage.push('world lighting');
  if (tags.includes('wall material')) usage.push('wall surface material');
  if (tags.includes('floor material') || tags.includes('ground surface')) usage.push('floor or ground surface');
  if (tags.includes('white model') || tags.includes('untextured model') || tags.includes('base mesh')) usage.push('base mesh import', 'model kitbash', 'geometry reference');
  if (tags.includes('apple')) avoid.push('tomato', 'orange', 'pumpkin');
  const type = _assetTypeFromExt(ext, rel);
  if (type === 'model') tags.push('model');
  return {
    type,
    category: _assetCategoryFromTags(tags, type),
    tags: _uniqueStrings(tags).slice(0, 40),
    materials: _uniqueStrings(materials),
    colors: _uniqueStrings(colors),
    usage: _uniqueStrings(usage),
    avoid: _uniqueStrings(avoid),
  };
}

function _assetDisplayNameFromPath(file) {
  return path.basename(file, path.extname(file)).replace(/[_-]+/g, ' ').trim();
}

function _scanLocalAssetRecords(roots = ASSET_DEFAULT_SCAN_ROOTS, maxFiles = 5000) {
  const out = [];
  const seen = new Set();
  for (const root of roots) {
    if (!root || !fs.existsSync(root)) continue;
    const absRoot = path.resolve(root);
    const files = _walkAssetFiles(absRoot).slice(0, maxFiles);
    const polyTextureDirs = new Map();
    for (const file of files) {
      const ext = path.extname(file).toLowerCase();
      if (!ASSET_TEXTURE_EXTS.has(ext)) continue;
      const abs = path.resolve(file);
      const low = abs.toLowerCase();
      if (!low.includes(`${path.sep}aichat_polyhaven${path.sep}textures${path.sep}`)) continue;
      const dir = path.dirname(abs);
      if (!polyTextureDirs.has(dir)) polyTextureDirs.set(dir, []);
      polyTextureDirs.get(dir).push(abs);
    }
    for (const [dir, mapFiles] of polyTextureDirs.entries()) {
      if (mapFiles.length < 2) continue;
      const folder = path.basename(dir);
      const name = folder.replace(/_\d+k$/i, '').replace(/[_-]+/g, ' ');
      const rel = path.relative(absRoot, dir);
      const auto = _autoTagAsset({ name, rel, ext: '.png', source: 'polyhaven_cache', extraTags: ['pbr', 'texture set'] });
      const fileMap = {};
      for (const mf of mapFiles) {
        const key = path.basename(mf, path.extname(mf));
        fileMap[key] = mf;
        seen.add(path.resolve(mf));
      }
      out.push({
        id: _safeAssetId(`pbr_${folder}_${_assetHashId(dir)}`),
        source: 'polyhaven_cache',
        origin: 'scan',
        index_status: 'auto',
        confirmed: false,
        type: 'texture',
        category: 'pbr_material',
        display_name: name,
        description: `Auto-indexed PolyHaven PBR texture set from ${rel}. Contains ${mapFiles.length} texture maps.`,
        tags: _uniqueStrings([...auto.tags, 'pbr', 'texture set', 'polyhaven cache']),
        aliases: [folder],
        style: [],
        materials: auto.materials,
        colors: auto.colors,
        visual_features: [],
        semantic_roles: auto.usage,
        usage: auto.usage.length ? auto.usage : ['surface material'],
        avoid: auto.avoid,
        scale_hint: 'PBR texture set; apply to mesh material, not a mesh object.',
        quality: 2,
        ph_query: auto.tags.slice(0, 6).join(' '),
        files: fileMap,
        preview: '',
        preview_url: '',
        notes: 'Auto-grouped from cached PolyHaven texture maps.',
        relative_dir: rel,
        asset_dir: dir,
        asset_path: dir,
        detected_files: mapFiles.map(f => path.basename(f)),
        updated_at: new Date().toISOString(),
      });
    }
    for (const file of files) {
      const ext = path.extname(file).toLowerCase();
      if (!ASSET_FILE_EXTS.has(ext) || ASSET_PROFILE_NAMES.has(path.basename(file))) continue;
      const abs = path.resolve(file);
      if (seen.has(abs)) continue;
      seen.add(abs);
      const rel = path.relative(absRoot, abs);
      const name = _assetDisplayNameFromPath(abs);
      const auto = _autoTagAsset({ name, rel, ext, source: 'local' });
      const isPreview = ASSET_PREVIEW_EXTS.has(ext) && /preview|thumb|thumbnail|cover|render/i.test(path.basename(file));
      out.push({
        id: _safeAssetId(`${name}_${_assetHashId(abs)}`),
        source: absRoot.includes('aichat_polyhaven') ? 'polyhaven_cache' : 'local',
        origin: 'scan',
        index_status: 'auto',
        confirmed: false,
        type: isPreview ? 'reference_image' : auto.type,
        category: isPreview ? 'preview' : auto.category,
        display_name: name,
        description: `Auto-indexed ${auto.type} from ${rel}. Review tags before production use.`,
        tags: auto.tags,
        aliases: [],
        style: [],
        materials: auto.materials,
        colors: auto.colors,
        visual_features: [],
        semantic_roles: auto.usage,
        usage: auto.usage,
        avoid: auto.avoid,
        scale_hint: '',
        quality: 1,
        ph_query: auto.tags.slice(0, 6).join(' '),
        files: { main: abs },
        preview: isPreview ? abs : '',
        preview_url: isPreview ? `/api/assets/raw-file?path=${encodeURIComponent(abs)}` : '',
        notes: 'Auto-generated by asset index scanner.',
        relative_dir: rel,
        asset_dir: path.dirname(abs),
        asset_path: abs,
        detected_files: [path.basename(abs)],
        updated_at: new Date().toISOString(),
      });
    }
  }
  return out;
}

function _readAssetProfiles() {
  const profiles = [];
  const files = _walkAssetFiles(ASSET_LIBRARY_DIR);
  const profileFiles = files.filter(p => ASSET_PROFILE_NAMES.has(path.basename(p)));
  for (const file of profileFiles) {
    try {
      const raw = fs.readFileSync(file, 'utf8');
      const profile = JSON.parse(raw);
      const baseDir = path.dirname(file);
      const relDir = path.relative(ASSET_LIBRARY_DIR, baseDir);
      const id = _safeAssetId(profile.id || path.basename(baseDir));
      const localFiles = _walkAssetFiles(baseDir)
        .filter(p => !ASSET_PROFILE_NAMES.has(path.basename(p)))
        .filter(p => ASSET_FILE_EXTS.has(path.extname(p).toLowerCase()))
        .map(p => path.relative(baseDir, p));
      profiles.push({
        id,
        source: profile.source || 'local',
        origin: 'profile',
        index_status: profile.index_status || 'confirmed',
        confirmed: profile.confirmed !== false,
        type: profile.type || 'model',
        category: profile.category || '',
        display_name: profile.display_name || profile.name || id,
        description: profile.description || '',
        tags: Array.isArray(profile.tags) ? profile.tags : [],
        aliases: Array.isArray(profile.aliases) ? profile.aliases : [],
        style: Array.isArray(profile.style) ? profile.style : [],
        materials: Array.isArray(profile.materials) ? profile.materials : [],
        colors: Array.isArray(profile.colors) ? profile.colors : [],
        visual_features: Array.isArray(profile.visual_features) ? profile.visual_features : [],
        semantic_roles: Array.isArray(profile.semantic_roles) ? profile.semantic_roles : [],
        usage: Array.isArray(profile.usage) ? profile.usage : [],
        avoid: Array.isArray(profile.avoid) ? profile.avoid : [],
        scale_hint: profile.scale_hint || '',
        quality: Number(profile.quality || 0),
        ph_query: profile.ph_query || '',
        files: profile.files && typeof profile.files === 'object' ? profile.files : {},
        preview: profile.preview || '',
        notes: profile.notes || '',
        asset_path: profile.asset_path || '',
        relative_dir: relDir,
        profile_path: file,
        asset_dir: baseDir,
        detected_files: localFiles,
      });
    } catch (e) {
      console.warn('[asset-library] failed to read profile:', file, e.message);
    }
  }
  return profiles;
}

function _discoverLooseAssets() {
  const profileDirs = new Set(_readAssetProfiles().map(p => p.asset_dir));
  const files = _walkAssetFiles(ASSET_LIBRARY_DIR).filter(p => {
    if (ASSET_PROFILE_NAMES.has(path.basename(p))) return false;
    if (!ASSET_FILE_EXTS.has(path.extname(p).toLowerCase())) return false;
    return ![...profileDirs].some(dir => p.startsWith(dir + path.sep));
  });
  return files.map(file => {
    const ext = path.extname(file).toLowerCase();
    const name = path.basename(file, ext);
    const id = _safeAssetId(name + '_' + _assetHashId(file));
    const isPreview = ASSET_PREVIEW_EXTS.has(ext);
    const auto = _autoTagAsset({ name, rel: path.relative(ASSET_LIBRARY_DIR, file), ext, source: 'local' });
    return {
      id,
      source: 'local',
      origin: 'scan',
      index_status: 'auto',
      confirmed: false,
      type: isPreview ? 'reference_image' : auto.type,
      category: isPreview ? 'preview' : auto.category,
      display_name: name.replace(/[_-]+/g, ' '),
      description: 'Auto-discovered local asset. Tags are generated from filename/path; review before production use.',
      tags: auto.tags,
      aliases: [],
      style: [],
      materials: auto.materials,
      colors: auto.colors,
      visual_features: [],
      semantic_roles: auto.usage,
      usage: auto.usage,
      avoid: auto.avoid,
      scale_hint: '',
      quality: 1,
      ph_query: auto.tags.slice(0, 6).join(' '),
      files: { main: path.relative(ASSET_LIBRARY_DIR, file) },
      preview: isPreview ? path.relative(ASSET_LIBRARY_DIR, file) : '',
      notes: 'Auto-discovered. Create asset_profile.json next to this file for better matching.',
      asset_path: file,
      relative_dir: path.dirname(path.relative(ASSET_LIBRARY_DIR, file)),
      profile_path: '',
      asset_dir: path.dirname(file),
      detected_files: [path.basename(file)],
      needs_profile: true,
    };
  });
}

function _allAssetProfiles() {
  const merged = [];
  const seen = new Set();
  for (const p of [..._readAssetProfiles(), ...(_readAssetIndex().assets || []), ..._discoverLooseAssets()]) {
    if (!p || !p.id || seen.has(p.id)) continue;
    seen.add(p.id);
    merged.push(p);
  }
  return merged;
}

function _assetSearchText(profile) {
  const parts = [
    profile.id, profile.display_name, profile.category, profile.description,
    profile.scale_hint, profile.ph_query, profile.notes,
    ...(profile.tags || []), ...(profile.aliases || []), ...(profile.style || []),
    ...(profile.materials || []), ...(profile.colors || []), ...(profile.visual_features || []),
    ...(profile.semantic_roles || []), ...(profile.usage || []), ...(profile.avoid || []),
  ];
  return parts.filter(Boolean).join(' ').toLowerCase();
}

function _scoreAsset(profile, query) {
  const raw = (query || '').toString().trim().toLowerCase();
  const tokens = raw.split(/[\s,，、/_-]+/).filter(Boolean);
  const text = _assetSearchText(profile);
  if (!tokens.length) return { score: (profile.quality || 0) + 1, reasons: ['all'] };
  let score = 0;
  const reasons = [];
  if (raw.length > 2 && text.includes(raw)) {
    score += 30;
    reasons.push('phrase');
  }
  const fieldWeights = [
    ['id', 18], ['display_name', 18], ['aliases', 16], ['tags', 14],
    ['category', 12], ['description', 10], ['visual_features', 9],
    ['semantic_roles', 9], ['materials', 8], ['style', 8], ['usage', 6],
    ['colors', 6], ['ph_query', 10], ['avoid', -8],
  ];
  for (const token of tokens) {
    for (const [field, weight] of fieldWeights) {
      const val = Array.isArray(profile[field]) ? profile[field].join(' ') : (profile[field] || '');
      const low = val.toString().toLowerCase();
      if (!low) continue;
      if (low.split(/[\s,，、/_-]+/).includes(token)) {
        score += weight;
        if (weight > 0) reasons.push(`${field}:${token}`);
      } else if (low.includes(token)) {
        score += weight * 0.45;
      }
    }
  }
  if (score > 0) score += Math.min(Number(profile.quality || 0), 5);
  return { score, reasons: [...new Set(reasons)].slice(0, 6) };
}

function _publicAsset(profile) {
  const previewPath = profile.preview ? `/api/assets/file/${encodeURIComponent(profile.id)}/${encodeURIComponent(profile.preview)}` : '';
  return {
    id: profile.id,
    source: profile.source,
    origin: profile.origin,
    index_status: profile.index_status,
    confirmed: !!profile.confirmed,
    type: profile.type,
    category: profile.category,
    display_name: profile.display_name,
    description: profile.description,
    tags: profile.tags,
    aliases: profile.aliases,
    style: profile.style,
    materials: profile.materials,
    colors: profile.colors,
    visual_features: profile.visual_features,
    semantic_roles: profile.semantic_roles,
    usage: profile.usage,
    avoid: profile.avoid,
    scale_hint: profile.scale_hint,
    quality: profile.quality,
    ph_query: profile.ph_query,
    files: profile.files,
    detected_files: profile.detected_files,
    asset_path: profile.asset_path,
    relative_dir: profile.relative_dir,
    preview: profile.preview,
    preview_url: profile.preview_url || previewPath,
    needs_profile: !!profile.needs_profile,
    notes: profile.notes,
  };
}

app.get('/api/assets/library', (req, res) => {
  const profiles = _allAssetProfiles().map(_publicAsset);
  const index = _readAssetIndex();
  res.json({ ok: true, root: ASSET_LIBRARY_DIR, index_file: ASSET_INDEX_FILE, updated_at: index.updated_at, count: profiles.length, assets: profiles });
});

app.get('/api/assets/index', (req, res) => {
  const profiles = _allAssetProfiles().map(_publicAsset);
  const index = _readAssetIndex();
  res.json({ ok: true, root: ASSET_LIBRARY_DIR, index_file: ASSET_INDEX_FILE, updated_at: index.updated_at, count: profiles.length, assets: profiles });
});

app.post('/api/assets/scan', (req, res) => {
  const body = req.body || {};
  const roots = Array.isArray(body.roots) && body.roots.length ? body.roots.map(String) : ASSET_DEFAULT_SCAN_ROOTS;
  const scanRoots = roots.map(r => path.resolve(r));
  const maxFiles = Math.max(10, Math.min(parseInt(body.max_files || '5000', 10) || 5000, 20000));
  const scanned = _scanLocalAssetRecords(roots, maxFiles);
  const old = (_readAssetIndex().assets || []).filter(a => {
    if (a.confirmed || a.origin !== 'scan') return true;
    const indexedPath = a.asset_path || a.asset_dir || (a.files && a.files.main) || '';
    return !indexedPath || !_isPathInsideAnyAssetRoot(indexedPath, scanRoots);
  });
  const byId = new Map(old.map(a => [a.id, a]));
  for (const rec of scanned) {
    const prev = byId.get(rec.id);
    byId.set(rec.id, prev && prev.confirmed ? { ...rec, ...prev, updated_at: new Date().toISOString() } : { ...prev, ...rec });
  }
  const payload = _writeAssetIndex([...byId.values()]);
  res.json({ ok: true, root: ASSET_LIBRARY_DIR, index_file: ASSET_INDEX_FILE, scanned: scanned.length, count: payload.assets.length, updated_at: payload.updated_at, assets: scanned.map(_publicAsset) });
});

app.get('/api/assets/search', (req, res) => {
  const q = (req.query.q || '').toString();
  const type = (req.query.type || '').toString().trim().toLowerCase();
  const limit = Math.max(1, Math.min(parseInt(req.query.limit || '30', 10) || 30, 100));
  let scored = _allAssetProfiles()
    .filter(p => !type || (p.type || '').toLowerCase() === type)
    .map(p => {
      const s = _scoreAsset(p, q);
      return { profile: p, score: s.score, reasons: s.reasons };
    })
    .filter(x => !q.trim() || x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(x => ({ ..._publicAsset(x.profile), _score: x.score, match_reasons: x.reasons }));
  res.json({ ok: true, query: q, root: ASSET_LIBRARY_DIR, returned: scored.length, results: scored });
});

app.get('/api/assets/profile/:id', (req, res) => {
  const profile = _allAssetProfiles().find(p => p.id === req.params.id);
  if (!profile) return res.status(404).json({ ok: false, error: '素材不存在' });
  res.json({ ok: true, asset: _publicAsset(profile) });
});

app.patch('/api/assets/index/:id', (req, res) => {
  const id = req.params.id;
  const idx = _readAssetIndex();
  const list = idx.assets || [];
  const found = list.find(a => a.id === id);
  if (!found) return res.status(404).json({ ok: false, error: '索引素材不存在或来自只读 profile' });
  const body = req.body || {};
  const arrayFields = ['tags', 'aliases', 'style', 'materials', 'colors', 'visual_features', 'semantic_roles', 'usage', 'avoid', 'detected_files'];
  for (const key of arrayFields) {
    if (Array.isArray(body[key])) found[key] = _uniqueStrings(body[key]);
  }
  for (const key of ['display_name', 'description', 'category', 'type', 'scale_hint', 'ph_query', 'notes', 'preview_url']) {
    if (body[key] !== undefined) found[key] = String(body[key] || '');
  }
  if (body.confirmed !== undefined) {
    found.confirmed = !!body.confirmed;
    found.index_status = found.confirmed ? 'confirmed' : 'auto';
  }
  found.updated_at = new Date().toISOString();
  _writeAssetIndex(list);
  res.json({ ok: true, asset: _publicAsset(found) });
});

app.get('/api/assets/raw-file', (req, res) => {
  const raw = (req.query.path || '').toString();
  if (!raw || raw.includes('\0')) return res.status(400).send('bad path');
  const abs = path.resolve(raw);
  const allowedRoots = ASSET_DEFAULT_SCAN_ROOTS.map(r => path.resolve(r)).filter(r => fs.existsSync(r));
  if (!allowedRoots.some(root => abs === root || abs.startsWith(root + path.sep))) return res.status(403).send('path not allowed');
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) return res.status(404).send('file not found');
  res.sendFile(abs);
});

app.get('/api/assets/file/:id/:file', (req, res) => {
  const profile = _allAssetProfiles().find(p => p.id === req.params.id);
  if (!profile) return res.status(404).send('asset not found');
  const rel = decodeURIComponent(req.params.file || '');
  if (!rel || rel.includes('..') || path.isAbsolute(rel)) return res.status(400).send('bad path');
  const abs = path.join(profile.asset_dir, rel);
  if (!abs.startsWith(profile.asset_dir) || !fs.existsSync(abs)) return res.status(404).send('file not found');
  res.sendFile(abs);
});

app.post('/api/assets/profile', (req, res) => {
  const body = req.body || {};
  const id = _safeAssetId(body.id || body.display_name || body.name);
  const dir = path.join(ASSET_LIBRARY_DIR, id);
  fs.mkdirSync(dir, { recursive: true });
  const profile = {
    id,
    type: body.type || 'model',
    category: body.category || '',
    display_name: body.display_name || body.name || id,
    description: body.description || '',
    tags: Array.isArray(body.tags) ? body.tags : [],
    aliases: Array.isArray(body.aliases) ? body.aliases : [],
    style: Array.isArray(body.style) ? body.style : [],
    materials: Array.isArray(body.materials) ? body.materials : [],
    colors: Array.isArray(body.colors) ? body.colors : [],
    visual_features: Array.isArray(body.visual_features) ? body.visual_features : [],
    semantic_roles: Array.isArray(body.semantic_roles) ? body.semantic_roles : [],
    usage: Array.isArray(body.usage) ? body.usage : [],
    avoid: Array.isArray(body.avoid) ? body.avoid : [],
    scale_hint: body.scale_hint || '',
    quality: Number(body.quality || 0),
    ph_query: body.ph_query || '',
    files: body.files && typeof body.files === 'object' ? body.files : {},
    preview: body.preview || '',
    notes: body.notes || '',
  };
  const file = path.join(dir, 'asset_profile.json');
  fs.writeFileSync(file, JSON.stringify(profile, null, 2));
  res.json({ ok: true, id, profile_path: file, asset: _publicAsset({ ...profile, asset_dir: dir, relative_dir: id, detected_files: [] }) });
});

// ==================== API 配置 ====================
app.get('/api/configs', (req, res) => {
  res.json(readConfigs());
});

app.post('/api/configs', (req, res) => {
  const { name, base_url, api_key, balance_url } = req.body;
  if (!name || !base_url || !api_key) {
    return res.status(400).json({ error: '请提供完整信息' });
  }
  const configs = readConfigs();
  const newConfig = {
    id: randomUUID(),
    name,
    base_url,
    api_key,
    balance_url: balance_url || '',
    enabledModels: null,  // null=全部启用；数组=只启用数组中的模型
    customModels: [],     // 用户手动追加的模型 id，会和 /v1/models 返回结果合并去重
    createdAt: new Date().toISOString()
  };
  configs.push(newConfig);
  writeConfigs(configs);
  res.json(newConfig);
});

app.delete('/api/configs/:id', (req, res) => {
  let configs = readConfigs();
  configs = configs.filter(c => c.id !== req.params.id);
  writeConfigs(configs);
  res.json({ success: true });
});

app.put('/api/configs/:id', (req, res) => {
  const { name, enabledModels, customModels } = req.body;
  let configs = readConfigs();
  const config = configs.find(c => c.id === req.params.id);
  if (!config) return res.status(404).json({ error: '配置不存在' });
  if (name) config.name = name;
  if (enabledModels !== undefined) config.enabledModels = enabledModels; // null=全部；数组=筛选
  if (customModels !== undefined) {
    // 去重 + 去空白
    const set = new Set((Array.isArray(customModels) ? customModels : [])
      .map(s => (s || '').toString().trim()).filter(Boolean));
    config.customModels = Array.from(set);
  }
  writeConfigs(configs);
  res.json(config);
});

app.get('/api/configs/:id/models', async (req, res) => {
  const configs = readConfigs();
  const config = configs.find(c => c.id === req.params.id);
  if (!config) return res.status(404).json({ error: '配置不存在' });

  const showAll = req.query.all === '1';

  try {
    let baseUrl = config.base_url.trim().replace(/\/+$/, '');
    if (!baseUrl.endsWith('/v1')) {
      baseUrl = baseUrl.replace(/\/v1\/.*$/, '');
      if (!baseUrl.includes('/v1')) {
        baseUrl = baseUrl + '/v1';
      }
    }
    const modelsUrl = baseUrl + '/models';
    const response = await axios.get(modelsUrl, {
      headers: { Authorization: `Bearer ${config.api_key}` },
      timeout: 15000
    });
    let models = (response.data.data || response.data.models || []).map(m => ({
      id: m.id || m.name,
      name: m.id || m.name
    }));

    // 合并用户在「API筛选模型」里手动追加的自定义模型 id（标记 custom:true 方便前端区分）
    if (Array.isArray(config.customModels) && config.customModels.length > 0) {
      const existIds = new Set(models.map(m => m.id));
      for (const id of config.customModels) {
        if (id && !existIds.has(id)) {
          models.push({ id, name: id, custom: true });
          existIds.add(id);
        }
      }
    }

    // 如果不要求全部，并且配置了 enabledModels 数组，则只返回启用的
    if (!showAll && Array.isArray(config.enabledModels) && config.enabledModels.length > 0) {
      const enabledSet = new Set(config.enabledModels);
      models = models.filter(m => enabledSet.has(m.id));
    }

    res.json(models);
  } catch (err) {
    res.status(500).json({ error: '获取模型失败: ' + (err.response?.data?.error?.message || err.message) });
  }
});


// ==================== 会话管理 ====================
app.post('/api/sessions', (req, res) => {
  const { name, mode } = req.body;
  const data = readData();
  
  let finalName = name;
  if (!finalName) {
    const modeNameMap = {
      'normal': '普通对话',
      'battle': 'AI对战',
      'workflow': '工作流',
      'mindmap': '大纲笔记',
      'photo': '摄影工具'
    };
    const prefix = modeNameMap[mode || 'normal'] || '新会话';
    
    // 查找当前模式下已有的默认名称数量，生成如 "普通对话 1", "普通对话 2"
    const existingCount = data.sessions.filter(s => s.mode === (mode || 'normal') && s.name.startsWith(prefix)).length;
    finalName = `${prefix} ${existingCount + 1}`;
  }
  
  const session = {
    id: randomUUID(),
    name: finalName,
    mode: mode || 'normal', // normal, battle, workflow, mindmap
    createdAt: new Date().toISOString()
  };
  data.sessions.push(session);
  writeData(data);
  res.json(session);
});

app.get('/api/sessions', (req, res) => {
  const { mode } = req.query;
  const data = readData();
  let sessions = data.sessions;
  
  if (mode) {
    sessions = sessions.filter(s => s.mode === mode);
  }
  
  res.json(sessions.sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    return new Date(b.createdAt) - new Date(a.createdAt);
  }));
});

app.delete('/api/sessions/:id', (req, res) => {
  const data = readData();
  data.sessions = data.sessions.filter(s => s.id !== req.params.id);
  data.messages = data.messages.filter(m => m.sessionId !== req.params.id);
  writeData(data);
  res.json({ success: true });
});

app.put('/api/sessions/:id', (req, res) => {
  const data = readData();
  const session = data.sessions.find(s => s.id === req.params.id);
  if (!session) return res.status(404).json({ error: '会话不存在' });
  if (req.body.name !== undefined) session.name = req.body.name;
  if (req.body.pinned !== undefined) session.pinned = req.body.pinned;
  if (req.body.configId !== undefined) session.configId = req.body.configId;
  if (req.body.model !== undefined) session.model = req.body.model;
  if (req.body.battleConfig !== undefined) session.battleConfig = req.body.battleConfig;
  writeData(data);
  res.json(session);
});

app.get('/api/sessions/:id/messages', (req, res) => {
  const data = readData();
  const messages = data.messages
    .filter(m => m.sessionId === req.params.id)
    .sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt));
  res.json(messages);
});

app.post('/api/sessions/:id/messages', (req, res) => {
  const { role, content, participant, model } = req.body;
  const data = readData();
  const message = {
    id: randomUUID(),
    sessionId: req.params.id,
    role,
    content,
    participant,
    model,
    createdAt: new Date().toISOString()
  };
  data.messages.push(message);
  writeData(data);
  res.json(message);
});

app.delete('/api/sessions/:id/messages', (req, res) => {
  const data = readData();
  const initialLength = data.messages.length;
  data.messages = data.messages.filter(m => m.sessionId !== req.params.id);
  writeData(data);
  res.json({ success: true, deleted: initialLength - data.messages.length });
});

app.delete('/api/sessions/:sessionId/messages/:messageId', (req, res) => {
  const data = readData();
  const initialLength = data.messages.length;
  data.messages = data.messages.filter(m => m.id !== req.params.messageId);
  if (data.messages.length < initialLength) {
    writeData(data);
    res.json({ success: true });
  } else {
    res.status(404).json({ error: '消息不存在' });
  }
});

// ==================== v1.11.0 模型能力检测 ====================
// 一次测一个能力，前端按需调（vision / tools / reasoning）。后端调一次真实 LLM 短请求然后判定。
// 视觉：发一张 1x1 透明 png + 「what color do you see?」 看 200/4xx
// 工具：发一个 hello_world 工具 schema + tool_choice='auto' 看是否返回 tool_calls
// 推理：检查 message.reasoning_content 字段或模型名特征 + 一次极短问 "1+1=" 看 latency
app.post('/api/configs/:id/test-capability', async (req, res) => {
  const { id } = req.params;
  const { model, capability } = req.body;
  if (!model || !capability) return res.status(400).json({ error: '缺少 model / capability' });
  if (!['vision', 'tools', 'reasoning'].includes(capability)) {
    return res.status(400).json({ error: 'capability 必须是 vision / tools / reasoning' });
  }
  const configs = readConfigs();
  const cfg = configs.find(c => c.id === id);
  if (!cfg) return res.status(404).json({ error: 'config 不存在' });

  const TIMEOUT_MS = 30000;
  const url = cfg.base_url.replace(/\/+$/, '') + '/chat/completions';
  const t0 = Date.now();
  try {
    let body;
    if (capability === 'vision') {
      // 1x1 透明 png base64
      const tinyPng = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgYAAAAAMAASsJTYQAAAAASUVORK5CYII=';
      body = {
        model, max_tokens: 50, stream: false,
        messages: [{ role: 'user', content: [
          { type: 'text', text: 'What is in this image? Answer in one short sentence.' },
          { type: 'image_url', image_url: { url: 'data:image/png;base64,' + tinyPng } }
        ]}]
      };
    } else if (capability === 'tools') {
      body = {
        model, max_tokens: 100, stream: false,
        messages: [{ role: 'user', content: 'Please call the hello_world tool with name="test".' }],
        tools: [{ type: 'function', function: {
          name: 'hello_world', description: 'Say hello to a name',
          parameters: { type: 'object', properties: { name: { type: 'string' } }, required: ['name'] }
        }}],
        tool_choice: 'auto'
      };
    } else { // reasoning
      body = {
        model, max_tokens: 200, stream: false,
        messages: [{ role: 'user', content: 'Solve step by step: If a train travels 60km in 30 min, what is its speed in km/h? Show your reasoning.' }]
      };
    }
    const r = await axios.post(url, body, {
      headers: { 'Authorization': 'Bearer ' + cfg.api_key, 'Content-Type': 'application/json' },
      timeout: TIMEOUT_MS, validateStatus: () => true
    });
    const took = Date.now() - t0;
    if (r.status >= 400) {
      const errMsg = (r.data?.error?.message || JSON.stringify(r.data || {}).substring(0, 250));
      // 视觉模型不支持时常见特征：'image_url' / 'unsupported' / 'multimodal' / 400
      let supported = false;
      let hint = `❌ HTTP ${r.status}: ${errMsg.substring(0, 150)}`;
      if (capability === 'vision' && /image_url|multimodal|vision|image|not support/i.test(errMsg)) {
        supported = false; hint = '❌ 模型不支持视觉输入: ' + errMsg.substring(0, 100);
      } else if (capability === 'tools' && /tool|function call|tools.*not/i.test(errMsg)) {
        supported = false; hint = '❌ 模型不支持工具调用: ' + errMsg.substring(0, 100);
      }
      return res.json({ ok: false, supported, capability, model, took_ms: took, http_status: r.status, hint, raw_error: errMsg.substring(0, 400) });
    }
    const choice = r.data?.choices?.[0];
    const msg = choice?.message || {};
    const content = (msg.content || '').toString();
    const toolCalls = msg.tool_calls || [];
    const reasoning = msg.reasoning_content || msg.reasoning || '';
    let supported = false, detail = '';
    if (capability === 'vision') {
      // 模型回了文字（哪怕是 "I see a transparent image" 也算支持），且没报错就视作支持
      supported = content.length > 0;
      detail = `回复: ${content.substring(0, 120)}`;
    } else if (capability === 'tools') {
      supported = toolCalls.length > 0;
      detail = supported
        ? `✓ 调用了 ${toolCalls.length} 个工具：${toolCalls.map(t => t.function?.name).join(',')}`
        : `✗ 模型只返回文字未调用工具：${content.substring(0, 100)}`;
    } else { // reasoning
      // 有 reasoning_content 字段直接判定为推理模型；否则看回复是否包含逐步推理标志
      const hasReasoningField = reasoning.length > 0;
      const hasStepByStep = /step\s*[12]|首先|然后|因此|so the|therefore/i.test(content);
      supported = hasReasoningField;
      detail = hasReasoningField
        ? `✓ 有 reasoning_content 字段（${reasoning.length} 字）`
        : (hasStepByStep ? '⚠️ 没 reasoning 字段但回复含分步推理（部分推理模型特征）' : '✗ 普通对话模型（无 reasoning 字段）');
    }
    return res.json({
      ok: true, supported, capability, model, took_ms: took,
      detail, content_preview: content.substring(0, 200),
      tool_calls_count: toolCalls.length, reasoning_chars: reasoning.length
    });
  } catch (e) {
    return res.json({ ok: false, supported: false, capability, model, took_ms: Date.now() - t0, hint: '❌ 网络/超时: ' + e.message.substring(0, 200) });
  }
});

// 持久化模型能力测试结果到 config（前端展示 badge 用）
// PUT /api/configs/:id/model-capabilities  body: { capabilities: { 'gpt-4o': {vision:true, tools:true, reasoning:false, tested_at: '2026-05-17 ...'} } }
app.put('/api/configs/:id/model-capabilities', (req, res) => {
  const { id } = req.params;
  const { capabilities } = req.body;
  if (!capabilities || typeof capabilities !== 'object') return res.status(400).json({ error: '缺少 capabilities' });
  let configs = readConfigs();
  const idx = configs.findIndex(c => c.id === id);
  if (idx < 0) return res.status(404).json({ error: 'config 不存在' });
  configs[idx].modelCapabilities = { ...(configs[idx].modelCapabilities || {}), ...capabilities };
  writeConfigs(configs);
  res.json({ ok: true });
});

// ==================== 聊天接口 ====================
app.post('/api/chat', async (req, res) => {
  const { config_id, model, messages, timeout, max_tokens, tools, tool_choice } = req.body;
  // 超时时间（秒），前端可传，默认 300 秒（5 分钟），范围 60~1800
  let timeoutSec = 300;
  if (typeof timeout === 'number' && timeout > 0) {
    timeoutSec = Math.max(60, Math.min(1800, timeout));
  }
  const timeoutMs = timeoutSec * 1000;
  // v1.9.4：max_tokens 上限（前端可传，默认不传 = 用中转 API 默认值，一般 4096）
  // 智能 Agent / 一键3D 这种要 AI 输出长 JSON 或大段 bpy 代码的场景必须传一个大值（如 16000）
  // 否则中转 API 会截断输出 → 前端拿到不完整的 JSON 解析失败
  let maxTokensParam = undefined;
  if (typeof max_tokens === 'number' && max_tokens > 0) {
    maxTokensParam = Math.max(256, Math.min(64000, Math.floor(max_tokens)));
  }

  // v1.10.0 / v2.0 Phase 3：OpenAI tool calling 透传
  // tools：function tool schema 数组（{type:'function', function:{name, description, parameters}}）
  // tool_choice：'auto' / 'none' / 'required' / {type:'function', function:{name}}
  // 任一参数缺失就不透传，向后兼容老 caller（一键3D / 普通聊天 等不需要 tools）
  let toolsParam = undefined;
  let toolChoiceParam = undefined;
  if (Array.isArray(tools) && tools.length > 0) {
    // 简单白名单：每个工具必须是 {type:'function', function:{name, parameters}} 结构
    const cleaned = [];
    for (const t of tools) {
      if (!t || typeof t !== 'object') continue;
      if (t.type !== 'function' || !t.function || typeof t.function.name !== 'string') continue;
      // 直接透传，不二次校验 parameters（让上游 LLM 自己报错）
      cleaned.push(t);
    }
    if (cleaned.length > 0) {
      toolsParam = cleaned;
      if (typeof tool_choice === 'string' && ['auto', 'none', 'required'].includes(tool_choice)) {
        toolChoiceParam = tool_choice;
      } else if (tool_choice && typeof tool_choice === 'object' && tool_choice.type === 'function') {
        toolChoiceParam = tool_choice;
      } else {
        toolChoiceParam = 'auto';  // 默认让 LLM 自主决定
      }
    }
  }


  const configs = readConfigs();
  const config = configs.find(c => c.id === config_id);
  if (!config) return res.status(404).json({ error: '配置不存在' });

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  let baseUrl = config.base_url.trim().replace(/\/+$/, '');
  if (!baseUrl.includes('/v1')) {
    baseUrl = baseUrl + '/v1';
  }
  const chatUrl = baseUrl + '/chat/completions';

  const sendEvent = (eventData) => {
    res.write(`data: ${JSON.stringify(eventData)}\n\n`);
  };

  try {
    // v1.9.4：组装请求 body，按需把 max_tokens 加进去
    const reqBody = { model, messages, stream: true };
    if (maxTokensParam !== undefined) reqBody.max_tokens = maxTokensParam;
    // v1.10.0：透传 tools / tool_choice 到上游 LLM
    if (toolsParam !== undefined) {
      reqBody.tools = toolsParam;
      reqBody.tool_choice = toolChoiceParam;
    }
    const response = await axios.post(chatUrl, reqBody, {

      headers: {
        Authorization: `Bearer ${config.api_key}`,
        'Content-Type': 'application/json'
      },
      responseType: 'stream',
      timeout: timeoutMs
    });


    response.data.on('data', chunk => {
      const lines = chunk.toString().split('\n').filter(line => line.trim() !== '');
      for (const line of lines) {
        if (line.includes('[DONE]')) {
          sendEvent({ done: true });
          return;
        }
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            // v1.6.9：转发 reasoning_content（Claude/DeepSeek/GPT-o1 等推理模型的 thinking 内容）
            // 让前端立刻知道 AI 在思考，而不是干等 30~120 秒一片空白
            if (data.choices && data.choices[0]) {
              const choice = data.choices[0];
              const delta = choice.delta || {};
              if (delta.reasoning_content) {
                sendEvent({ reasoning: delta.reasoning_content });
              }
              if (delta.content) {
                sendEvent({ content: delta.content });
              }
              // v1.10.0：OpenAI tool calling 流式 delta.tool_calls 透传
              // 单条 delta 形如 [{index:0, id:'call_xxx', type:'function', function:{name:'foo', arguments:'{"a"'}}]
              // 后续 chunk 只带 index + function.arguments 增量（要前端按 index 累加 arguments 字符串）
              if (Array.isArray(delta.tool_calls) && delta.tool_calls.length > 0) {
                sendEvent({ tool_calls: delta.tool_calls });
              }
              // v1.10.0：finish_reason 转发（'stop' / 'tool_calls' / 'length' / 'content_filter'）
              // 用于前端 Agent 循环判断本轮是否要继续调工具
              if (choice.finish_reason) {
                sendEvent({ finish_reason: choice.finish_reason });
              }
            }

          } catch (e) {}
        }
      }
    });

    response.data.on('end', () => {
      res.end();
    });

  } catch (err) {
    // v1.10.2 修复：axios responseType:'stream' 时 err.response.data 是 Stream 对象不是已解析 JSON，
    // 直接读 .error.message 永远拿不到具体原因（用户看到光秃秃的「Request failed with status code 400」）。
    // 这里把 stream 收齐成 Buffer → 尝试 JSON.parse → 抠出真正的 error.message
    let upstreamMsg = err.message;
    let upstreamStatus = err.response?.status;
    let upstreamRaw = '';
    try {
      const stream = err.response?.data;
      if (stream && typeof stream.on === 'function') {
        upstreamRaw = await new Promise((resolve) => {
          const chunks = [];
          stream.on('data', c => chunks.push(c));
          stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
          stream.on('error', () => resolve(''));
          // 防卡死：500ms 兜底
          setTimeout(() => resolve(Buffer.concat(chunks).toString('utf-8')), 500);
        });
        if (upstreamRaw) {
          try {
            const j = JSON.parse(upstreamRaw);
            upstreamMsg = j?.error?.message || j?.error || j?.message || upstreamRaw.slice(0, 400);
          } catch {
            upstreamMsg = upstreamRaw.slice(0, 400);
          }
        }
      }
    } catch { /* ignore */ }
    // 透传上游 status code 和原始片段，方便前端给用户更针对性的引导
    sendEvent({
      error: upstreamMsg,
      upstream_status: upstreamStatus,
      upstream_raw: upstreamRaw ? upstreamRaw.slice(0, 800) : undefined,
    });
    console.error(`[/api/chat] 上游错误 status=${upstreamStatus || '?'} msg=${String(upstreamMsg).slice(0, 300)}`);
    res.end();
  }
});

// ==================== 一键3D建模 - 图像生成代理 ====================
// 支持三种上游：
//   1. OpenAI 官方 /v1/images/generations（DALL·E 3 / gpt-image-1）
//   2. 兼容 OpenAI 协议的中转站（同上）
//   3. Gemini / SD3 / 其它通过 chat completions 返回图片的模型（fallback 走 /api/chat 即可，无需此路由）
app.post('/api/image/generate', async (req, res) => {
  const { config_id, model, prompt, size, n } = req.body;
  if (!config_id || !model || !prompt) {
    return res.status(400).json({ error: '缺少 config_id / model / prompt' });
  }
  const configs = readConfigs();
  const config = configs.find(c => c.id === config_id);
  if (!config) return res.status(404).json({ error: '配置不存在' });

  let baseUrl = config.base_url.trim().replace(/\/+$/, '');
  if (!baseUrl.includes('/v1')) baseUrl += '/v1';

  // —— 路径 A：先尝试 OpenAI 风格 /images/generations
  try {
    const response = await axios.post(
      baseUrl + '/images/generations',
      {
        model,
        prompt,
        n: n || 1,
        size: size || '1024x1024',
        response_format: 'b64_json'
      },
      {
        headers: {
          Authorization: `Bearer ${config.api_key}`,
          'Content-Type': 'application/json'
        },
        timeout: 180000
      }
    );
    const item = (response.data && response.data.data && response.data.data[0]) || {};
    if (item.b64_json) return res.json({ b64_json: item.b64_json });
    if (item.url)      return res.json({ url: item.url });
    // 上游返回 200 但格式不认识，下沉到 fallback
  } catch (err) {
    // 不是 OpenAI 协议或模型不支持出图，下沉到 fallback
    const status = err.response?.status;
    // 4xx 一律转 fallback；5xx / 网络错才直接抛
    if (status && status >= 500) {
      return res.status(502).json({
        error: '上游图像服务异常: ' + (err.response?.data?.error?.message || err.message)
      });
    }
  }

  // —— 路径 B：fallback 走 chat completions，让模型直接输出图片 URL / base64
  try {
    const response = await axios.post(
      baseUrl + '/chat/completions',
      {
        model,
        messages: [
          { role: 'user', content: prompt + '\n\nPlease directly output the generated image (markdown image syntax or base64 data URL).' }
        ],
        stream: false
      },
      {
        headers: {
          Authorization: `Bearer ${config.api_key}`,
          'Content-Type': 'application/json'
        },
        timeout: 180000
      }
    );
    const text = response.data?.choices?.[0]?.message?.content || '';
    // 兼容字符串 / 数组 content
    const textStr = typeof text === 'string'
      ? text
      : Array.isArray(text)
        ? text.map(p => p?.text || '').join('\n')
        : '';
    // 1) markdown ![](url)
    const md = textStr.match(/!\[.*?\]\((.*?)\)/);
    if (md) return res.json({ url: md[1] });
    // 2) data:image/...;base64,xxx
    const dataUri = textStr.match(/data:image\/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=]+)/);
    if (dataUri) return res.json({ b64_json: dataUri[1] });
    // 3) 裸 https url
    const u = textStr.match(/https?:\/\/[^\s"'<>)\]]+\.(?:png|jpg|jpeg|webp)/i);
    if (u) return res.json({ url: u[0] });
    // 4) 部分供应商把 b64 放在 message.images[]/multi_modal_content 里
    const arr = response.data?.choices?.[0]?.message?.images
             || response.data?.choices?.[0]?.message?.multi_modal_content
             || [];
    for (const part of arr) {
      if (part?.image_url?.url) return res.json({ url: part.image_url.url });
      if (part?.b64_json)       return res.json({ b64_json: part.b64_json });
    }
    return res.status(502).json({ error: '上游既不支持 /images/generations，也未在 chat 返回中找到图片' });
  } catch (err) {
    return res.status(502).json({
      error: '图像生成失败: ' + (err.response?.data?.error?.message || err.message)
    });
  }
});

// ==================== 一键3D建模 - Blender 桥接代理（可选） ====================
// 浏览器直连 http://127.0.0.1:9876 通常没问题，
// 但若部署到远端服务器，前端可改成调本路由由后端转发。
app.post('/api/blender/exec', async (req, res) => {
  const { blender_url, code, scene_name } = req.body;
  if (!blender_url || !code) {
    return res.status(400).json({ error: '缺少 blender_url / code' });
  }
  try {
    const r = await axios.post(
      blender_url.replace(/\/+$/, '') + '/exec',
      { code, scene_name: scene_name || 'AIScene' },
      { timeout: 600000 }
    );
    res.json(r.data);
  } catch (err) {
    res.status(502).json({
      error: 'Blender 桥接失败: ' + (err.response?.data || err.message)
    });
  }
});

app.get('/api/blender/ping', async (req, res) => {
  const url = (req.query.url || '').toString();
  if (!url) return res.status(400).json({ error: '缺少 url' });
  try {
    const r = await axios.get(url.replace(/\/+$/, '') + '/ping', { timeout: 5000 });
    res.json(r.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// v1.6.6：一键导出 Blender 插件 zip 到桌面
// 在 Electron 打包后位于 process.resourcesPath/blender_addon/aichat_bridge.zip
// 在开发环境位于 __dirname/blender_addon/aichat_bridge.zip
app.get('/api/blender/export-addon', (req, res) => {
  const os = require('os');
  const candidates = [
    process.resourcesPath ? path.join(process.resourcesPath, 'blender_addon', 'aichat_bridge.zip') : null,
    path.join(__dirname, 'blender_addon', 'aichat_bridge.zip')
  ].filter(Boolean);

  let srcPath = null;
  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) { srcPath = p; break; }
    } catch (e) {}
  }

  if (!srcPath) {
    return res.status(404).json({
      ok: false,
      error: 'aichat_bridge.zip 未找到。开发环境请先 npm run build:addon；安装包应自动包含。',
      candidates
    });
  }

  const desktopDir = path.join(os.homedir(), 'Desktop');
  if (!fs.existsSync(desktopDir)) {
    try { fs.mkdirSync(desktopDir, { recursive: true }); } catch(e) {}
  }
  const destPath = path.join(desktopDir, 'aichat_bridge.zip');

  try {
    fs.copyFileSync(srcPath, destPath);
    const stat = fs.statSync(destPath);
    res.json({ ok: true, path: destPath, size: stat.size, src: srcPath });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// ============================================================
// v3.7.0: generate_texture API - AI 生图模型生成贴图
// ============================================================
app.post('/api/generate-texture', async (req, res) => {
  const { config_id, model, prompt, size, style } = req.body;
  if (!config_id || !model || !prompt) {
    return res.status(400).json({ ok: false, error: 'missing config_id / model / prompt' });
  }
  const configs = readConfigs();
  const config = configs.find(c => c.id === config_id);
  if (!config) return res.status(404).json({ ok: false, error: 'config not found' });

  let baseUrl = config.base_url.trim().replace(/\/+$/, '');
  if (!baseUrl.includes('/v1')) baseUrl += '/v1';

  const sizeMap = { '1K': 1024, '2K': 2048, '4K': 4096, '1024x1024': 1024, '2048x2048': 2048, '4096x4096': 4096 };
  const targetPx = sizeMap[size] || sizeMap[(size || '').toUpperCase()] || 2048;
  const sizeStr = targetPx + 'x' + targetPx;

  const fullPrompt = (style === 'seamless')
    ? prompt + ', seamless tileable texture, high quality PBR material'
    : (style === 'stylized')
      ? prompt + ', stylized texture, game asset quality'
      : prompt + ', realistic texture, high quality PBR material, 4K';

  let b64 = null;
  let imgUrl = null;

  try {
    const r = await axios.post(baseUrl + '/images/generations', {
      model, prompt: fullPrompt, n: 1, size: sizeStr, response_format: 'b64_json'
    }, {
      headers: { Authorization: 'Bearer ' + config.api_key, 'Content-Type': 'application/json' },
      timeout: 180000
    });
    const item = (r.data && r.data.data && r.data.data[0]) || {};
    if (item.b64_json) b64 = item.b64_json;
    else if (item.url) imgUrl = item.url;
  } catch(e) {
    const status = e.response?.status;
    if (status && status >= 500) {
      return res.json({ ok: false, error: 'upstream error: ' + (e.response?.data?.error?.message || e.message) });
    }
  }

  if (!b64 && !imgUrl) {
    try {
      const r = await axios.post(baseUrl + '/chat/completions', {
        model,
        messages: [{ role: 'user', content: fullPrompt + '\n\nPlease directly output the generated image.' }],
        stream: false
      }, {
        headers: { Authorization: 'Bearer ' + config.api_key, 'Content-Type': 'application/json' },
        timeout: 180000
      });
      const text = r.data?.choices?.[0]?.message?.content || '';
      const textStr = typeof text === 'string' ? text : Array.isArray(text) ? text.map(p => p?.text || '').join('\n') : '';
      const dataUri = textStr.match(/data:image\/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=]+)/);
      if (dataUri) b64 = dataUri[1];
      const md = textStr.match(/!\[.*?\]\((.*?)\)/);
      if (!b64 && md) imgUrl = md[1];
      const u = textStr.match(/https?:\/\/[^\s"'<>)\]]+\.(?:png|jpg|jpeg|webp)/i);
      if (!b64 && !imgUrl && u) imgUrl = u[0];
      const arr = r.data?.choices?.[0]?.message?.images || r.data?.choices?.[0]?.message?.multi_modal_content || [];
      for (const part of arr) {
        if (!b64 && part?.b64_json) b64 = part.b64_json;
        if (!b64 && !imgUrl && part?.image_url?.url) imgUrl = part.image_url.url;
      }
    } catch(e) {
      return res.json({ ok: false, error: 'image gen failed: ' + (e.response?.data?.error?.message || e.message) });
    }
  }

  if (!b64 && imgUrl) {
    try {
      const r = await axios.get(imgUrl, { responseType: 'arraybuffer', timeout: 60000 });
      b64 = Buffer.from(r.data).toString('base64');
    } catch(e) {
      return res.json({ ok: false, error: 'failed to download image from URL: ' + e.message });
    }
  }

  if (!b64) {
    return res.json({
      ok: false,
      error: '所选模型未返回图片。请确认使用的是生图模型（如 gpt-image-2 / dall-e-3 / flux / kolors / seedream），而非文本对话模型。',
      error_type: 'not_image_model'
    });
  }

  try {
    if (sharp) {
      const buf = Buffer.from(b64, 'base64');
      const meta = await sharp(buf).metadata();
      const maxDim = Math.max(meta.width || 0, meta.height || 0);
      if (maxDim > targetPx) {
        const resized = await sharp(buf)
          .resize(targetPx, targetPx, { fit: 'inside', withoutEnlargement: true })
          .png()
          .toBuffer();
        b64 = resized.toString('base64');
      }
    }
  } catch(e) {
    console.warn('[generate-texture] resize failed:', e.message);
  }

  const bytes = Buffer.from(b64, 'base64').length;
  res.json({
    ok: true,
    data: { base64: b64, format: 'png', bytes: bytes,
      bytes_human: bytes > 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : (bytes / 1024).toFixed(0) + ' KB',
      target_size: sizeStr, prompt: fullPrompt }
  });
});

// ============================================================================
// v1.9.1 新增：上传本地 3D 模型到 OS 临时目录，返回绝对路径供 Blender 端 import
// 接收 { filename, b64 }，把 b64 解码写入 $TMP/aichat_local_models/{uuid}_{filename}
// 前端拿到 local_path 后，再用现有的 /api/blender/exec → /exec 让 Blender 调用
//   bpy.ops.import_scene.gltf(filepath=...) / fbx / obj / ... 把模型 append 到当前场景
// 这样【插件零改动】，老用户也能直接用本功能
// ============================================================================
const ALLOWED_MODEL_EXTS = new Set(['glb','gltf','fbx','obj','dae','ply','stl']);
app.post('/api/blender/upload-local-model', (req, res) => {
  try {
    const filename = (req.body.filename || '').toString().trim();
    const b64 = (req.body.b64 || '').toString();
    if (!filename) return res.status(400).json({ ok: false, error: '缺少 filename' });
    if (!b64) return res.status(400).json({ ok: false, error: '缺少 b64（文件内容 base64）' });

    // 提取并校验扩展名
    const lower = filename.toLowerCase();
    const dot = lower.lastIndexOf('.');
    const ext = dot >= 0 ? lower.slice(dot + 1) : '';
    if (!ALLOWED_MODEL_EXTS.has(ext)) {
      return res.status(400).json({ ok: false, error: `不支持的扩展名 .${ext}，仅支持 ${[...ALLOWED_MODEL_EXTS].join(' / ')}` });
    }

    // 去掉 data:...;base64, 前缀（如果有）
    const cleanB64 = b64.replace(/^data:[^;]+;base64,/, '');
    const buf = Buffer.from(cleanB64, 'base64');
    if (!buf.length) return res.status(400).json({ ok: false, error: 'b64 解码后内容为空' });

    const os = require('os');
    const cacheDir = path.join(os.tmpdir(), 'aichat_local_models');
    if (!fs.existsSync(cacheDir)) fs.mkdirSync(cacheDir, { recursive: true });

    // 安全的文件名：UUID 前缀 + 清洗后的原始名（避免 / .. \）
    const safeName = filename.replace(/[\/\\:*?"<>|]/g, '_').slice(0, 120);
    const localPath = path.join(cacheDir, `${randomUUID().slice(0, 8)}_${safeName}`);
    fs.writeFileSync(localPath, buf);

    res.json({ ok: true, local_path: localPath, size: buf.length, ext });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});


// ============================================================================
// v2.0 Phase 2：MCP 工具网关（透传到 Blender 插件 aichat_bridge 2.0.0 的 /mcp/*）
// ----------------------------------------------------------------------------
// 设计要点：
//   1. 浏览器前端 Agent 循环只调本网关，不直连 9876（统一错误格式 + 方便未来切远端）
//   2. Blender 端 /mcp/call 即使工具失败也返回 HTTP 200 + {ok:false, error}，
//      网关层只把"网络/HTTP 异常"归一化成 {ok:false, error, error_type}，
//      工具自身错误原样透传，让前端 Agent 看到结构化错误后换策略
//   3. 默认超时 120s（PolyHaven 4k 下载/blend append 可能慢），可由请求覆盖
//
// 端点：
//   GET  /api/mcp/tools?url=<blender_url>          拉 16 个 tool 的 OpenAI schema
//   POST /api/mcp/call    { blender_url, tool, args, timeout? }   通用调度
//   POST /api/mcp/tool/:tool_name  { blender_url, args, timeout? }  RESTful 直调（备用）
//   GET  /api/mcp/ping?url=<blender_url>           快检：返回插件 /ping 的 mcp 子对象
//
// 错误归一化：
//   网关层错误 → { ok:false, error_type: 'network'|'timeout'|'bad_request'|'upstream',
//                  error: 'xxx', http_status?: number, hint?: '...' }
//   工具自身错误（Blender 端返回的 {ok:false, error}）原样透传
// ============================================================================
const MCP_DEFAULT_TIMEOUT_MS = 120000;          // 2 分钟，覆盖 PolyHaven 下载等慢操作
const MCP_PING_TIMEOUT_MS = 5000;
const MCP_TOOLS_LIST_TIMEOUT_MS = 8000;

function _normalizeBlenderUrl(raw) {
  if (!raw || typeof raw !== 'string') return null;
  const s = raw.trim().replace(/\/+$/, '');
  if (!/^https?:\/\//i.test(s)) return null;
  return s;
}

function _mcpErrorPayload(err, errorType) {
  const status = err?.response?.status;
  const upstreamData = err?.response?.data;
  const isTimeout = err?.code === 'ECONNABORTED' || /timeout/i.test(err?.message || '');
  const isConnRefused = ['ECONNREFUSED', 'ENOTFOUND', 'EAI_AGAIN', 'ECONNRESET'].includes(err?.code);
  const finalType = errorType ||
    (isTimeout ? 'timeout' :
     isConnRefused ? 'network' :
     status ? 'upstream' : 'network');
  const hintMap = {
    network: '无法连接到 Blender 插件，请确认 Blender 已开启并在 N 面板启用了 AI Chat Bridge（默认 http://127.0.0.1:9876）',
    timeout: '调用超时。复杂工具（如 PolyHaven 4k 下载、HDRI 导入）可能需要 60s+，可在请求里加大 timeout 字段',
    upstream: 'Blender 插件返回了非 2xx 状态，可能是请求体格式不对或插件版本过旧（需 2.0.0+）',
    bad_request: '请求参数不合法',
  };
  // 上游 4xx/5xx 时 Blender 端可能返回 {ok:false, error}
  // 透传它，但补上 error_type / hint / http_status，保证前端 Agent 能按结构化字段分支判断
  if (upstreamData && typeof upstreamData === 'object' && upstreamData.ok === false) {
    return {
      ok: false,
      error_type: upstreamData.error_type || finalType,
      error: upstreamData.error || err?.message || 'upstream error',
      http_status: status,
      hint: upstreamData.hint || hintMap[finalType] || '',
      // 保留 Blender 端原样的额外字段（如 available 工具列表、traceback）
      upstream_data: upstreamData,
    };
  }
  return {
    ok: false,
    error_type: finalType,
    error: err?.message || String(err),
    http_status: status,
    hint: hintMap[finalType] || '',
  };
}


// GET /api/mcp/tools?url=http://127.0.0.1:9876
// 透传 Blender 端 GET /mcp/tools，返回 16 个工具的 OpenAI tools 格式 schema
app.get('/api/mcp/tools', async (req, res) => {
  const blenderUrl = _normalizeBlenderUrl(req.query.url);
  if (!blenderUrl) {
    return res.status(400).json({ ok: false, error_type: 'bad_request',
      error: '缺少 url 参数或格式不正确，应形如 http://127.0.0.1:9876' });
  }
  try {
    const r = await axios.get(blenderUrl + '/mcp/tools',
      { timeout: MCP_TOOLS_LIST_TIMEOUT_MS,
        headers: { 'User-Agent': 'aichat-mcp-gateway/2.0.0' } });
    // 期望格式：{ ok, tools: [...], addon_version, count }
    const data = r.data || {};
    if (!data.ok || !Array.isArray(data.tools)) {
      return res.status(502).json({
        ok: false, error_type: 'upstream',
        error: 'Blender 插件 /mcp/tools 返回格式不符合预期（需要 {ok, tools:[]}），可能是插件版本低于 2.0.0',
        upstream_data: data,
      });
    }
    res.json({
      ok: true,
      tools: data.tools,
      count: data.count || data.tools.length,
      addon_version: data.addon_version,
      blender_url: blenderUrl,
    });
  } catch (err) {
    res.status(502).json(_mcpErrorPayload(err));
  }
});

// ============================================================
// v3.0.1 反踩坑硬拦截 —— exec_python 前 preflight 扫描常见错误模式
// AI 反复犯的 5 类错（prompt 加再多也记不住）：
//   1. sky_type='NISHITA' 错填到 phase_function（合法值 SINGLE_SCATTERING / ... / HOSEK_WILKIE）
//   2. ShaderNodeTexSky 的 dust_density 属性不存在（合法名是 air_density）
//   3. obj.modifiers["Solidify"] 方括号取 KeyError（应用 .get() 或保留 new() 引用）
//   4. obj.particle_systems[0].settings.child_nbr（Blender 2.x 老 API，应改 child_count）
//   5. bpy.ops.mesh.bevel(vertex_only=True)（Blender 4.2+ 已移除，改 affect='VERTICES'）
// v3.4.4 新增 4 个检查：
//   6. boolean 工具 target_name/tool_name 为空
//   7. add_subdivision levels 超出 1-5 范围
//   8. add_bevel affect 枚举值错误
//   9. EEVEE 颜色映射枚举值缺少 AgX - 前缀
// 命中 → 直接拒发并把【正确写法】塞回 tool result，AI 下一轮自动看到答案
// ============================================================
function _preflightExecPython(code, toolName, args) {
  // v3.8.1 修复：无 code 时不再直接 return —— 否则 boolean/subdivision/bevel 等工具级参数检查（坑6/7/8）永远跑不到。
  //   下面的代码类正则都是对字符串跑，置空串即可安全跳过（不会误报），只保留工具级参数检查。
  if (typeof code !== 'string') code = '';
  const issues = [];

  // 坑 1：NISHITA 错填到 phase_function（v3.1.0 Hotfix1：无条件拦截 —— 不管同段是否有合法的 sky_type='NISHITA'，
  //         phase_function='NISHITA' 都是错的；之前漏拦同时含 sky_type='NISHITA' 的代码）
  if (/phase_function\s*=\s*['"]NISHITA['"]/i.test(code)) {
    issues.push({
      type: 'enum_misuse',
      bad: "phase_function='NISHITA'",
      good: "phase_function='SINGLE_SCATTERING'  # 合法值: SINGLE_SCATTERING / MULTIPLE_SCATTERING / PREETHAM / HOSEK_WILKIE",
      hint: "NISHITA 是 Sky Texture 的 sky_type 枚举值，不是 Volume Scatter 的 phase_function。"
    });
  }
  // 坑 1b：同段 inputs['phase_function'] 写法（部分代码用字典访问，需要单独抓）
  if (/inputs\[['"]phase_function['"]\][^=]*=\s*['"]NISHITA['"]/i.test(code)) {
    issues.push({
      type: 'enum_misuse',
      bad: "node.inputs['phase_function'].default_value = 'NISHITA'",
      good: "node.inputs['phase_function'].default_value = 'SINGLE_SCATTERING'",
      hint: "NISHITA 只能用于 Sky Texture 的 sky_type，不能用于 Volume Scatter 的 phase_function。"
    });
  }

  // 坑 2：ShaderNodeTexSky.dust_density（Blender 没这个属性）
  if (/\.dust_density\s*=/.test(code) || /['"]dust_density['"]/.test(code)) {
    issues.push({
      type: 'attribute_not_exist',
      bad: "sky.dust_density = ...",
      good: "sky.air_density = 1.0  # Blender 5.x 只有 air_density / dust_density 不存在",
      hint: "ShaderNodeTexSky (sky_type='NISHITA') 合法属性: sun_elevation / sun_rotation / altitude / air_density / ozone_density. 没有 dust_density."
    });
  }

  // 坑 5：bevel(vertex_only=True)（4.2+ 已移除）
  if (/bpy\.ops\.mesh\.bevel\([^)]*vertex_only\s*=/.test(code)) {
    issues.push({
      type: 'removed_keyword',
      bad: "bpy.ops.mesh.bevel(vertex_only=True, ...)",
      good: "推荐改用 modifier API（更稳）:\n    mod = obj.modifiers.new(name='Bevel', type='BEVEL')\n    mod.affect = 'VERTICES'  # 或 'EDGES'（默认）\n    mod.width = 0.03; mod.segments = 3",
      hint: "vertex_only 在 Blender 4.2+ 已被移除，改用 affect 关键字或 modifier API。"
    });
  }

  // 坑 4：粒子系统 child_nbr（2.x 老 API）
  if (/\.child_nbr\s*=/.test(code)) {
    issues.push({
      type: 'deprecated_api',
      bad: "particle_settings.child_nbr = ...",
      good: "particle_settings.child_count = 50  # Blender 2.8+ 改名为 child_count",
      hint: "child_nbr 是 Blender 2.x 老 API，已改名 child_count。"
    });
  }

  // 坑 3：modifiers["xxx"] 方括号取 + 紧跟着 .xxx = 赋值（很容易 KeyError）
  // 只匹配同行链式调用 obj.modifiers["xxx"].yyy =，不误伤 .get() / mod.xxx 引用模式
  const modBracketRe = /\.modifiers\[['"][^'"]+['"]\]\.[a-zA-Z_]+\s*=/g;
  if (modBracketRe.test(code)) {
    issues.push({
      type: 'risky_bracket_access',
      bad: "obj.modifiers['Solidify'].thickness = 0.1  # 名字对不上就 KeyError",
      good: "推荐写法 A: 保留 new 的引用\n    mod = obj.modifiers.new(name='Solidify', type='SOLIDIFY')\n    mod.thickness = 0.1\n\n推荐写法 B: 用 .get() 兜底\n    mod = obj.modifiers.get('Solidify')\n    if mod is None: mod = obj.modifiers.new(name='Solidify', type='SOLIDIFY')\n    mod.thickness = 0.1",
      hint: "modifiers 是按 new(name) 时的 name 索引；没显式设 name 会自动加 .001 后缀导致方括号取报 KeyError。"
    });
  }

  // ============================================================
  // v3.4.4 新增：工具参数预检（布尔运算 / 细分 / 倒角 / 颜色映射）
  // ============================================================

  // 坑 6：boolean 工具 target_name 不存在时 Blender 崩溃
  const BOOLEAN_TOOLS = ['boolean_union', 'boolean_difference', 'boolean_intersect'];
  if (BOOLEAN_TOOLS.includes(toolName)) {
    const targetName = args?.target_name;
    const toolName2 = args?.tool_name;
    if (!targetName || typeof targetName !== 'string' || !targetName.trim()) {
      issues.push({
        type: 'preflight_param',
        bad: "boolean 工具缺少 target_name",
        good: "target_name='Cube'  # 必须是已存在的 Blender 物体名",
        hint: "boolean 工具的 target_name 不能为空"
      });
    }
    if (!toolName2 || typeof toolName2 !== 'string' || !toolName2.trim()) {
      issues.push({
        type: 'preflight_param',
        bad: "boolean 工具缺少 tool_name",
        good: "tool_name='Cylinder'  # 工具物体名（布尔后会删除）",
        hint: "boolean 工具的 tool_name 不能为空"
      });
    }
  }

  // 坑 7：add_subdivision levels 超出范围（1-5）
  if (toolName === 'add_subdivision') {
    const levels = args?.levels;
    if (levels !== undefined && (typeof levels !== 'number' || levels < 1 || levels > 5)) {
      issues.push({
        type: 'preflight_param',
        bad: "levels=%d  # levels 超出 1-5 范围".replace('%d', levels),
        good: "levels=2  # 视口细分建议 2，渲染细分用 render_levels=3",
        hint: "add_subdivision 的 levels 必须在 1-5 范围内（太高会卡死 Blender）"
      });
    }
  }

  // 坑 8：add_bevel affect 枚举值错误
  if (toolName === 'add_bevel') {
    const affect = args?.affect;
    if (affect !== undefined && affect !== 'EDGES' && affect !== 'VERTICES') {
      issues.push({
        type: 'preflight_param',
        bad: "affect='%s'  # 枚举值错误".replace('%s', affect),
        good: "affect='EDGES'  # 只能是 'EDGES' 或 'VERTICES'",
        hint: "Blender 4.2+ 用 affect 替代已移除的 vertex_only=True"
      });
    }
  }

  // 坑 9：EEVEE 颜色映射枚举值缺少 AgX - 前缀
  if (/view_settings\.view_transform\s*=\s*['"]High Contrast['"]/i.test(code) ||
      /film_grain\.preset\s*=\s*['"]High Contrast['"]/i.test(code)) {
    issues.push({
      type: 'enum_misuse',
      bad: "view_transform = 'High Contrast'",
      good: "view_transform = 'AgX - High Contrast'  # 必须加 'AgX - ' 前缀",
      hint: "Blender 4.x EEVEE/AgX 颜色映射枚举值格式是 'AgX - xxx'，不是直接写 xxx"
    });
  }

  if (issues.length === 0) return null;
  return {
    ok: false,
    error_type: 'preflight_block',
    error: `检测到 ${issues.length} 个常见 bpy API 错误（preflight 拒发，避免污染场景）：\n\n` +
      issues.map((it, i) => `❌ 错误 ${i+1} (${it.type}):\n  错的写法: ${it.bad}\n  正确写法: ${it.good}\n  提示: ${it.hint}`).join('\n\n'),
    hint: '请按上方"正确写法"重写 code 后再次调用 exec_python。这些错误已被 server.js preflight 拦下，没有发到 Blender 也没有污染场景。',
    issues,
  };
}

// 内部工具：把请求转发给 Blender 端 POST /mcp/call
async function _proxyMcpCall(blenderUrl, toolName, args, timeoutMs) {
  // v3.0.1 反踩坑硬拦截：exec_python 调用前 preflight 扫常见错误
  // v3.8.1 修复：boolean/subdivision/bevel 等工具的参数检查也要走 preflight，
  //   旧代码只在 exec_python 时调用，导致 _preflightExecPython 里的坑6/7/8（空 target_name → Blender 崩溃等）从未生效
  const _PREFLIGHT_PARAM_TOOLS = ['boolean_union', 'boolean_difference', 'boolean_intersect', 'add_subdivision', 'add_bevel'];
  if ((toolName === 'exec_python' && args && typeof args.code === 'string') ||
      _PREFLIGHT_PARAM_TOOLS.includes(toolName)) {
    const preflightErr = _preflightExecPython(args && args.code, toolName, args);
    if (preflightErr) {
      // 假装是 Blender 端返回的 {ok:false, error},让 AI 在 tool result 里看到正确写法
      return { status: 200, data: preflightErr };
    }
  }

  const body = { tool: toolName, args: args || {} };
  const r = await axios.post(blenderUrl + '/mcp/call', body, {
    timeout: timeoutMs,
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'aichat-mcp-gateway/2.0.0',
    },
    // 让 4xx/5xx 也走 resolve，由我们在外层判断 ok 字段
    validateStatus: () => true,
  });
  return { status: r.status, data: r.data };
}

// POST /api/mcp/call  { blender_url, tool, args, timeout? }
// 通用调度。这是前端 Agent 循环的主入口。
app.post('/api/mcp/call', async (req, res) => {
  const blenderUrl = _normalizeBlenderUrl(req.body?.blender_url);
  const toolName = (req.body?.tool || req.body?.name || '').toString().trim();
  const args = req.body?.args || req.body?.arguments || {};
  let timeoutMs = MCP_DEFAULT_TIMEOUT_MS;
  if (typeof req.body?.timeout === 'number' && req.body.timeout > 0) {
    // 秒为单位（与 /api/chat 一致），范围 5~600s
    timeoutMs = Math.max(5, Math.min(600, req.body.timeout)) * 1000;
  } else if (typeof req.body?.timeout_ms === 'number' && req.body.timeout_ms > 0) {
    timeoutMs = Math.max(5000, Math.min(600000, req.body.timeout_ms));
  }

  if (!blenderUrl) {
    return res.status(400).json({ ok: false, error_type: 'bad_request',
      error: '缺少 blender_url 或格式不正确，应形如 http://127.0.0.1:9876' });
  }
  if (!toolName) {
    return res.status(400).json({ ok: false, error_type: 'bad_request',
      error: '缺少 tool 字段（要调用的 MCP 工具名）' });
  }
  if (args && typeof args !== 'object') {
    return res.status(400).json({ ok: false, error_type: 'bad_request',
      error: 'args 必须是对象（即使为空也要传 {}）' });
  }

  try {
    const { status, data } = await _proxyMcpCall(blenderUrl, toolName, args, timeoutMs);
    // 上游返回结构化错误（工具自身错误 / unknown tool）→ 仍然 HTTP 200 透传
    // 上游 HTTP 异常 → 502 + 错误归一化
    if (status >= 500) {
      return res.status(502).json({
        ok: false, error_type: 'upstream',
        error: `Blender 端返回 HTTP ${status}`,
        http_status: status, upstream_data: data,
      });
    }
    if (status >= 400 && (!data || data.ok !== false)) {
      // 4xx 但不是 {ok:false} 结构 → 包装一下
      return res.status(status).json({
        ok: false, error_type: 'upstream',
        error: `Blender 端返回 HTTP ${status}`,
        http_status: status, upstream_data: data,
      });
    }
    // 正常透传（包括 {ok:true, ...} 和 {ok:false, error: '...'}）
    res.json(data);
  } catch (err) {
    res.status(502).json(_mcpErrorPayload(err));
  }
});

// POST /api/mcp/tool/:tool_name  { blender_url, args, timeout? }
// RESTful 直调（便于 curl 调试）。:tool_name 受 URL 限制只能匹配安全字符
app.post('/api/mcp/tool/:tool_name', async (req, res) => {
  const toolName = (req.params.tool_name || '').trim();
  if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(toolName)) {
    return res.status(400).json({ ok: false, error_type: 'bad_request',
      error: 'tool_name 仅允许字母/数字/下划线' });
  }
  const blenderUrl = _normalizeBlenderUrl(req.body?.blender_url);
  if (!blenderUrl) {
    return res.status(400).json({ ok: false, error_type: 'bad_request',
      error: '缺少 blender_url' });
  }
  const args = req.body?.args || {};
  let timeoutMs = MCP_DEFAULT_TIMEOUT_MS;
  if (typeof req.body?.timeout === 'number' && req.body.timeout > 0) {
    timeoutMs = Math.max(5, Math.min(600, req.body.timeout)) * 1000;
  }
  try {
    const { status, data } = await _proxyMcpCall(blenderUrl, toolName, args, timeoutMs);
    if (status >= 500) {
      return res.status(502).json({ ok: false, error_type: 'upstream',
        error: `Blender 端返回 HTTP ${status}`, http_status: status, upstream_data: data });
    }
    if (status >= 400 && (!data || data.ok !== false)) {
      return res.status(status).json({ ok: false, error_type: 'upstream',
        error: `Blender 端返回 HTTP ${status}`, http_status: status, upstream_data: data });
    }
    res.json(data);
  } catch (err) {
    res.status(502).json(_mcpErrorPayload(err));
  }
});

// GET /api/mcp/ping?url=http://127.0.0.1:9876
// 轻量探活：调 Blender /ping 然后只挑跟 MCP 相关的字段返回，前端 Agent 模式启动前先做这步
app.get('/api/mcp/ping', async (req, res) => {
  const blenderUrl = _normalizeBlenderUrl(req.query.url);
  if (!blenderUrl) {
    return res.status(400).json({ ok: false, error_type: 'bad_request',
      error: '缺少 url 参数' });
  }
  try {
    const r = await axios.get(blenderUrl + '/ping',
      { timeout: MCP_PING_TIMEOUT_MS,
        headers: { 'User-Agent': 'aichat-mcp-gateway/2.0.0' } });
    const data = r.data || {};
    const mcp = data.mcp || {};
    const hasMcp = mcp.enabled === true && Array.isArray(mcp.tools) && mcp.tools.length > 0;
    res.json({
      ok: true,
      mcp_ready: hasMcp,
      addon_version: data.addon_version || null,
      blender_version: data.blender_version || null,
      tool_count: mcp.tool_count || 0,
      tools: mcp.tools || [],
      // 当插件版本 < 2.0.0 时（v1.x 的 /ping 不带 mcp 字段），明确给前端提示
      upgrade_hint: hasMcp ? null
        : '检测到 Blender 插件未启用 MCP 工具协议，请升级到 aichat_bridge 2.0.0+',
      raw: data,
    });
  } catch (err) {
    res.status(502).json(_mcpErrorPayload(err));
  }
});


// ============================================================================
// v3.0.1 PolyHaven 贴图 + HDRI 轻量回归（只下贴图/HDRI/深度图、不下 .blend 模型 ⭐）
// ----------------------------------------------------------------------------
// 设计要点：
//   1. v2.1.1 删 PolyHaven 后用户反馈"AI 自己写 procedural shader 不真实"，本版重新启用
//      但只下载贴图类资产 —— 模型继续走脚本化粗模（不回归 .blend 模型下载）
//   2. 三类可下载：
//      a) textures —— PBR 贴图集（diffuse / nor_gl 法向 / rough / metal / disp 深度 / ao 等）
//      b) hdris    —— HDR 环境贴图（.hdr / .exr）+ 缩略图
//      c) （材质参数 = 贴图本身就是参数）
//   3. 全量资产列表 5 分钟内存缓存（PolyHaven API rate-limit 友好）
//   4. 贴图文件本地磁盘缓存到 ~/Library/Caches/aichat_polyhaven/<type>/<slug>_<resolution>/
//
// 端点（贴图类）：
//   GET  /api/polyhaven/textures/search?q=wood&limit=20      搜贴图
//   GET  /api/polyhaven/textures/:slug/files?resolution=2k   拿 map 下载 URL
//   POST /api/polyhaven/textures/download  {slug, resolution, maps}  代下载 → 本地路径
//
// 端点（HDRI 类）：
//   GET  /api/polyhaven/hdris/search?q=sunset&limit=20       搜 HDRI
//   POST /api/polyhaven/hdris/download  {slug, resolution}   代下载 .hdr → 本地路径
//
// ⚠️ 不提供模型下载端点（policy：复杂模型走 AI 脚本化粗模 + 这里下来的贴图来"以假乱真"）
// ============================================================================
const POLYHAVEN_CACHE_DIR = path.join(os.homedir(), 'Library', 'Caches', 'aichat_polyhaven');
const POLYHAVEN_TEX_CACHE_DIR = path.join(POLYHAVEN_CACHE_DIR, 'textures');
const POLYHAVEN_HDRI_CACHE_DIR = path.join(POLYHAVEN_CACHE_DIR, 'hdris');
const POLYHAVEN_LIST_CACHE_TTL_MS = 5 * 60 * 1000;  // 全量资产列表 5 分钟内存缓存
// PolyHaven 贴图 map 名约定（合集 8 类）：
//   Diffuse    —— 颜色（接 BSDF Base Color）
//   nor_gl     —— OpenGL 法向贴图（接 Normal Map → BSDF Normal）
//   nor_dx     —— DirectX 法向贴图（备选）
//   Rough      —— 粗糙度（接 BSDF Roughness）
//   Metal      —— 金属度（接 BSDF Metallic，部分贴图才有）
//   Displacement —— 位移/深度图（接 Material Output Displacement，需 Adaptive Subdivision）
//   AO         —— 环境光遮蔽（叠到 Diffuse 上变暗）
//   Translucency —— 透射（如树叶贴图才有）
const POLYHAVEN_DEFAULT_TEX_MAPS = ['Diffuse', 'nor_gl', 'Rough', 'Displacement', 'AO'];
const POLYHAVEN_ALL_TEX_MAPS = ['Diffuse', 'nor_gl', 'nor_dx', 'Rough', 'Metal', 'Displacement', 'AO', 'Translucency', 'Bump'];
const POLYHAVEN_VALID_RESOLUTIONS = new Set(['1k', '2k', '4k', '8k']);
// 内存缓存：分 textures / hdris 两份
const _polyhavenListCache = { textures: null, hdris: null };  // { fetchedAt, assets }

for (const d of [POLYHAVEN_CACHE_DIR, POLYHAVEN_TEX_CACHE_DIR, POLYHAVEN_HDRI_CACHE_DIR]) {
  if (!fs.existsSync(d)) { try { fs.mkdirSync(d, { recursive: true }); } catch {} }
}

async function _polyhavenFetchAssetList(type /* 'textures' | 'hdris' */) {
  if (!['textures', 'hdris'].includes(type)) throw new Error('type 必须是 textures 或 hdris');
  const now = Date.now();
  const cache = _polyhavenListCache[type];
  if (cache && (now - cache.fetchedAt < POLYHAVEN_LIST_CACHE_TTL_MS)) {
    return cache.assets;
  }
  const r = await axios.get('https://api.polyhaven.com/assets', {
    params: { type },
    timeout: 15000,
    headers: { 'User-Agent': 'aichat-polyhaven/3.0.1' }
  });
  if (!r.data || typeof r.data !== 'object') throw new Error(`PolyHaven /assets?type=${type} 返回格式异常`);
  _polyhavenListCache[type] = { assets: r.data, fetchedAt: now };
  return r.data;
}

const POLYHAVEN_SEARCH_SYNONYMS = {
  floor: ['ground', 'planks', 'paving', 'tiles', 'boards'],
  ground: ['floor', 'soil', 'dirt', 'forest', 'moss', 'grass'],
  path: ['road', 'trail', 'paving', 'cobblestone', 'gravel'],
  road: ['asphalt', 'street', 'pavement'],
  wall: ['plaster', 'brick', 'concrete', 'stone'],
  wood: ['oak', 'walnut', 'plank', 'timber', 'bark'],
  wooden: ['wood', 'oak', 'walnut', 'plank', 'timber'],
  stone: ['rock', 'granite', 'limestone', 'paving'],
  rock: ['stone', 'cliff', 'boulder'],
  metal: ['steel', 'iron', 'rust', 'brushed'],
  rusty: ['rust', 'corroded', 'metal'],
  fabric: ['cloth', 'linen', 'wool', 'cotton'],
  cloth: ['fabric', 'linen', 'wool', 'cotton'],
  leather: ['hide', 'worn', 'brown'],
  grass: ['lawn', 'field', 'meadow', 'moss'],
  moss: ['forest', 'green', 'ground', 'rock'],
  mud: ['dirt', 'soil', 'wet', 'ground'],
  sand: ['beach', 'desert', 'gravel'],
  tile: ['tiles', 'ceramic', 'roof', 'floor'],
  brick: ['bricks', 'masonry', 'wall'],
  concrete: ['cement', 'plaster', 'wall', 'floor'],
  plaster: ['stucco', 'wall', 'ceiling'],
  glass: ['window', 'frosted', 'pane'],
  rubber: ['tire', 'black'],
  bark: ['tree', 'trunk', 'wood'],
  irish: ['cottage', 'moss', 'stone', 'grass', 'pasture'],
  countryside: ['rural', 'field', 'grass', 'stone', 'path'],
};

function _polyhavenBuildSearchNeedles(query) {
  const raw = (query || '').toString().toLowerCase().trim();
  const baseTokens = raw.split(/[\s,，、/_-]+/).filter(Boolean);
  const tokens = new Set(baseTokens);
  for (const token of baseTokens) {
    const syns = POLYHAVEN_SEARCH_SYNONYMS[token];
    if (syns) syns.forEach(s => tokens.add(s));
  }
  return { raw, baseTokens, tokens: [...tokens] };
}

function _polyhavenScoreAndPick(assets, query, limit) {
  const { raw, baseTokens, tokens } = _polyhavenBuildSearchNeedles(query);
  const scored = [];
  for (const [slug, a] of Object.entries(assets || {})) {
    if (!a || typeof a !== 'object') continue;
    let score = 0;
    const reasons = [];
    const name = (a.name || '').toLowerCase();
    const cats = (a.categories || []).map(c => String(c).toLowerCase());
    const tags = (a.tags || []).map(t => String(t).toLowerCase());
    const slugLow = slug.toLowerCase();
    const haystack = [slugLow, name, ...cats, ...tags].filter(Boolean).join(' ');
    if (baseTokens.length === 0) {
      score = (a.download_count || 0) / 1000 + 1;
    } else {
      if (raw.length > 2 && haystack.includes(raw)) {
        score += 35;
        reasons.push(`phrase:${raw}`);
      }
      for (const t of tokens) {
        const isOriginal = baseTokens.includes(t);
        const mul = isOriginal ? 1 : 0.45;
        if (slugLow === t) { score += 40 * mul; reasons.push(`slug:${t}`); }
        else if (slugLow.includes(t)) { score += 20 * mul; if (isOriginal) reasons.push(`slug~${t}`); }
        if (name === t) { score += 30 * mul; reasons.push(`name:${t}`); }
        else if (name.includes(t)) { score += 15 * mul; if (isOriginal) reasons.push(`name~${t}`); }
        for (const c of cats) {
          if (c === t) { score += 12 * mul; if (isOriginal) reasons.push(`cat:${t}`); }
          else if (c.includes(t)) score += 5 * mul;
        }
        for (const tg of tags) {
          if (tg === t) { score += 6 * mul; if (isOriginal) reasons.push(`tag:${t}`); }
          else if (tg.includes(t)) score += 2 * mul;
        }
      }
      score += Math.min((a.download_count || 0) / 10000, 4);
    }
    if (score > 0) scored.push({ score, slug, asset: a, reasons: [...new Set(reasons)].slice(0, 5) });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, Math.max(1, Math.min(limit || 20, 50)));
}

function _polyhavenIndexRecord(type, slug, asset, score = 0, reasons = []) {
  const name = asset?.name || slug;
  const tags = _uniqueStrings([...(asset?.categories || []), ...(asset?.tags || []), ...slug.split(/[_-]+/), type]);
  const auto = _autoTagAsset({ name, rel: slug, ext: type === 'hdris' ? '.hdr' : '.png', source: 'polyhaven', extraTags: tags });
  const isHdri = type === 'hdris';
  return {
    id: _safeAssetId(`polyhaven_${type}_${slug}`),
    source: 'polyhaven',
    origin: 'network_index',
    index_status: 'auto',
    confirmed: false,
    type: isHdri ? 'hdri' : 'texture',
    category: isHdri ? 'environment' : auto.category,
    display_name: name,
    description: `PolyHaven CC0 ${isHdri ? 'HDRI environment' : 'PBR texture'} indexed from network metadata. Download when selected for use.`,
    tags: _uniqueStrings([...auto.tags, ...tags, 'cc0', 'polyhaven']),
    aliases: [slug],
    style: [],
    materials: auto.materials,
    colors: auto.colors,
    visual_features: [],
    semantic_roles: auto.usage,
    usage: isHdri ? ['world lighting', 'environment background'] : auto.usage,
    avoid: auto.avoid,
    scale_hint: isHdri ? 'World/environment asset, not a mesh object.' : 'Surface material; apply to mesh faces or objects.',
    quality: Math.min(5, Math.max(1, Math.round((asset?.download_count || 0) / 25000) + 1)),
    ph_query: tags.slice(0, 8).join(' '),
    files: { polyhaven_slug: slug, polyhaven_type: type },
    detected_files: [],
    preview: '',
    preview_url: `https://cdn.polyhaven.com/asset_img/thumbs/${slug}.png?width=256`,
    relative_dir: `polyhaven/${type}/${slug}`,
    asset_dir: '',
    asset_path: '',
    notes: `Indexed from PolyHaven search. match=${(reasons || []).join(', ')} score=${Number(score || 0).toFixed(1)}`,
    updated_at: new Date().toISOString(),
  };
}

app.post('/api/assets/index/polyhaven', async (req, res) => {
  const type = (req.body?.type || req.query.type || 'textures').toString();
  const q = (req.body?.q || req.query.q || '').toString();
  const limit = Math.max(1, Math.min(parseInt(req.body?.limit || req.query.limit || '30', 10) || 30, 80));
  if (!['textures', 'hdris'].includes(type)) return res.status(400).json({ ok: false, error: 'type 必须是 textures 或 hdris' });
  try {
    const assets = await _polyhavenFetchAssetList(type);
    const top = _polyhavenScoreAndPick(assets, q, limit);
    const records = top.map(s => _polyhavenIndexRecord(type, s.slug, s.asset, s.score, s.reasons));
    const old = _readAssetIndex().assets || [];
    const byId = new Map(old.map(a => [a.id, a]));
    for (const rec of records) {
      const prev = byId.get(rec.id);
      byId.set(rec.id, prev && prev.confirmed ? { ...rec, ...prev, updated_at: new Date().toISOString() } : { ...prev, ...rec });
    }
    const payload = _writeAssetIndex([...byId.values()]);
    res.json({ ok: true, source: 'polyhaven', type, query: q, indexed: records.length, count: payload.assets.length, assets: records.map(_publicAsset) });
  } catch (e) {
    res.status(502).json({ ok: false, error: 'PolyHaven 索引失败: ' + e.message });
  }
});

// ============================ Textures ============================

// GET /api/polyhaven/textures/search?q=wood&limit=20
app.get('/api/polyhaven/textures/search', async (req, res) => {
  const q = (req.query.q || '').toString();
  const limit = parseInt(req.query.limit || '20', 10);
  try {
    const assets = await _polyhavenFetchAssetList('textures');
    const top = _polyhavenScoreAndPick(assets, q, limit);
    const results = top.map(s => ({
      slug: s.slug,
      name: s.asset.name || s.slug,
      categories: s.asset.categories || [],
      tags: s.asset.tags || [],
      thumbnail_url: `https://cdn.polyhaven.com/asset_img/thumbs/${s.slug}.png?width=256`,
      preview_url: `https://cdn.polyhaven.com/asset_img/primary/${s.slug}.png?width=512`,
      download_count: s.asset.download_count,
      _score: s.score,
      match_reasons: s.reasons || [],
    }));
    res.json({ ok: true, type: 'textures', query: q, returned: results.length, results });
  } catch (e) {
    res.status(502).json({ ok: false, error: 'PolyHaven textures 搜索失败: ' + e.message });
  }
});

// GET /api/polyhaven/textures/:slug/files?resolution=2k
app.get('/api/polyhaven/textures/:slug/files', async (req, res) => {
  const slug = (req.params.slug || '').replace(/[^a-zA-Z0-9_-]/g, '');
  const resolution = (req.query.resolution || '2k').toString().toLowerCase();
  if (!slug) return res.status(400).json({ ok: false, error: '缺少 slug' });
  if (!POLYHAVEN_VALID_RESOLUTIONS.has(resolution)) {
    return res.status(400).json({ ok: false, error: `resolution 必须是 ${[...POLYHAVEN_VALID_RESOLUTIONS].join('/')}` });
  }
  try {
    const r = await axios.get(`https://api.polyhaven.com/files/${slug}`, {
      timeout: 15000, headers: { 'User-Agent': 'aichat-polyhaven/3.0.1' }
    });
    const files = r.data || {};
    const maps = {};
    for (const [mapName, byRes] of Object.entries(files)) {
      if (!byRes || typeof byRes !== 'object') continue;
      const r1 = byRes[resolution];
      if (!r1 || typeof r1 !== 'object') continue;
      let chosen = null, chosenExt = null;
      for (const ext of ['jpg', 'png', 'exr', 'hdr']) {
        if (r1[ext] && r1[ext].url) { chosen = r1[ext]; chosenExt = ext; break; }
      }
      if (chosen) maps[mapName] = { url: chosen.url, ext: chosenExt, size: chosen.size || null, md5: chosen.md5 || null };
    }
    res.json({ ok: true, slug, resolution, maps_count: Object.keys(maps).length, available_maps: Object.keys(maps), maps });
  } catch (e) {
    const status = e.response?.status || 502;
    res.status(status).json({ ok: false, error: `PolyHaven /files/${slug} 失败: ` + e.message });
  }
});

// POST /api/polyhaven/textures/download  body { slug, resolution, maps:[] }
app.post('/api/polyhaven/textures/download', async (req, res) => {
  const slug = (req.body?.slug || '').replace(/[^a-zA-Z0-9_-]/g, '');
  const resolution = (req.body?.resolution || '2k').toString().toLowerCase();
  let mapNames = req.body?.maps;
  if (!Array.isArray(mapNames) || mapNames.length === 0) mapNames = POLYHAVEN_DEFAULT_TEX_MAPS;
  // 白名单过滤，防 SSRF
  mapNames = mapNames.filter(m => POLYHAVEN_ALL_TEX_MAPS.includes(m));
  if (!slug) return res.status(400).json({ ok: false, error: '缺少 slug' });
  if (!POLYHAVEN_VALID_RESOLUTIONS.has(resolution)) {
    return res.status(400).json({ ok: false, error: `resolution 必须是 ${[...POLYHAVEN_VALID_RESOLUTIONS].join('/')}` });
  }
  if (mapNames.length === 0) {
    return res.status(400).json({ ok: false, error: `maps 必须从白名单选: ${POLYHAVEN_ALL_TEX_MAPS.join(' / ')}` });
  }
  try {
    const fr = await axios.get(`https://api.polyhaven.com/files/${slug}`, {
      timeout: 15000, headers: { 'User-Agent': 'aichat-polyhaven/3.0.1' }
    });
    const files = fr.data || {};
    const cacheSubdir = path.join(POLYHAVEN_TEX_CACHE_DIR, `${slug}_${resolution}`);
    if (!fs.existsSync(cacheSubdir)) fs.mkdirSync(cacheSubdir, { recursive: true });

    const downloaded = {};
    const failed = {};
    for (const mapName of mapNames) {
      const byRes = files[mapName];
      if (!byRes || !byRes[resolution]) {
        failed[mapName] = `slug 不提供 ${mapName}@${resolution}`; continue;
      }
      let chosen = null, chosenExt = null;
      for (const ext of ['jpg', 'png', 'exr', 'hdr']) {
        if (byRes[resolution][ext] && byRes[resolution][ext].url) {
          chosen = byRes[resolution][ext]; chosenExt = ext; break;
        }
      }
      if (!chosen) { failed[mapName] = '没有可下载的扩展名'; continue; }
      const fname = `${mapName}.${chosenExt}`;
      const localPath = path.join(cacheSubdir, fname);
      if (fs.existsSync(localPath) && fs.statSync(localPath).size > 0) {
        downloaded[mapName] = { local_path: localPath, cached: true, size: fs.statSync(localPath).size, ext: chosenExt };
        continue;
      }
      try {
        const dl = await axios.get(chosen.url, {
          responseType: 'arraybuffer', timeout: 120000,
          headers: { 'User-Agent': 'aichat-polyhaven/3.0.1' }
        });
        fs.writeFileSync(localPath, Buffer.from(dl.data));
        downloaded[mapName] = { local_path: localPath, cached: false, size: dl.data.byteLength, ext: chosenExt };
      } catch (e) {
        failed[mapName] = '下载失败: ' + e.message.substring(0, 100);
      }
    }

    const okCount = Object.keys(downloaded).length;
    const failCount = Object.keys(failed).length;
    res.json({
      ok: okCount > 0, slug, resolution, cache_dir: cacheSubdir,
      downloaded, failed,
      summary: `${okCount} 张下载成功${failCount ? `，${failCount} 张失败` : ''}`,
    });
  } catch (e) {
    res.status(502).json({ ok: false, error: 'PolyHaven 贴图下载失败: ' + e.message });
  }
});

// ============================ HDRIs ============================

// GET /api/polyhaven/hdris/search?q=sunset&limit=20
app.get('/api/polyhaven/hdris/search', async (req, res) => {
  const q = (req.query.q || '').toString();
  const limit = parseInt(req.query.limit || '20', 10);
  try {
    const assets = await _polyhavenFetchAssetList('hdris');
    const top = _polyhavenScoreAndPick(assets, q, limit);
    const results = top.map(s => ({
      slug: s.slug,
      name: s.asset.name || s.slug,
      categories: s.asset.categories || [],
      tags: s.asset.tags || [],
      thumbnail_url: `https://cdn.polyhaven.com/asset_img/thumbs/${s.slug}.png?width=256`,
      preview_url: `https://cdn.polyhaven.com/asset_img/primary/${s.slug}.png?width=1024`,
      download_count: s.asset.download_count,
      _score: s.score,
    }));
    res.json({ ok: true, type: 'hdris', query: q, returned: results.length, results });
  } catch (e) {
    res.status(502).json({ ok: false, error: 'PolyHaven HDRIs 搜索失败: ' + e.message });
  }
});

// POST /api/polyhaven/hdris/download  body { slug, resolution }
app.post('/api/polyhaven/hdris/download', async (req, res) => {
  const slug = (req.body?.slug || '').replace(/[^a-zA-Z0-9_-]/g, '');
  const resolution = (req.body?.resolution || '2k').toString().toLowerCase();
  if (!slug) return res.status(400).json({ ok: false, error: '缺少 slug' });
  if (!POLYHAVEN_VALID_RESOLUTIONS.has(resolution)) {
    return res.status(400).json({ ok: false, error: `resolution 必须是 ${[...POLYHAVEN_VALID_RESOLUTIONS].join('/')}` });
  }
  try {
    const fr = await axios.get(`https://api.polyhaven.com/files/${slug}`, {
      timeout: 15000, headers: { 'User-Agent': 'aichat-polyhaven/3.0.1' }
    });
    const files = fr.data || {};
    const hdri = files.hdri;
    if (!hdri || !hdri[resolution]) {
      return res.status(404).json({ ok: false, error: `slug 不是 HDRI 或没有 ${resolution} 分辨率` });
    }
    let chosen = null, chosenExt = null;
    for (const ext of ['hdr', 'exr']) {
      if (hdri[resolution][ext] && hdri[resolution][ext].url) { chosen = hdri[resolution][ext]; chosenExt = ext; break; }
    }
    if (!chosen) return res.status(404).json({ ok: false, error: 'HDRI 文件没有 hdr/exr 扩展' });

    const cacheSubdir = path.join(POLYHAVEN_HDRI_CACHE_DIR, slug);
    if (!fs.existsSync(cacheSubdir)) fs.mkdirSync(cacheSubdir, { recursive: true });
    const localPath = path.join(cacheSubdir, `${resolution}.${chosenExt}`);
    if (fs.existsSync(localPath) && fs.statSync(localPath).size > 0) {
      return res.json({
        ok: true, slug, resolution, cached: true,
        local_path: localPath, size: fs.statSync(localPath).size, ext: chosenExt
      });
    }
    const dl = await axios.get(chosen.url, {
      responseType: 'arraybuffer', timeout: 180000,
      headers: { 'User-Agent': 'aichat-polyhaven/3.0.1' }
    });
    fs.writeFileSync(localPath, Buffer.from(dl.data));
    res.json({
      ok: true, slug, resolution, cached: false,
      local_path: localPath, size: dl.data.byteLength, ext: chosenExt
    });
  } catch (e) {
    res.status(502).json({ ok: false, error: 'PolyHaven HDRI 下载失败: ' + e.message });
  }
});



// ============================================================================
// v1.8.4 Tripo3D 文生 3D 透传 API（用户自带 key，不内置任何 trial）
// 参考文档：https://platform.tripo3d.ai/docs/generation
// 端点：
//   POST /api/tripo3d/create          创建任务（透传 POST https://api.tripo3d.com/v2/openapi/task）
//   GET  /api/tripo3d/task/:task_id   查询任务状态（透传 GET）
//   POST /api/tripo3d/download-glb    把 Tripo3D 输出的 GLB（5 分钟过期）下载到本地缓存，返回本地路径供 Blender 用
// ============================================================================
const TRIPO3D_BASE_URL = 'https://api.tripo3d.com/v2/openapi';

// 创建任务（type=text_to_model / image_to_model 等）
app.post('/api/tripo3d/create', async (req, res) => {
  const apiKey = (req.body.api_key || '').trim();
  const payload = req.body.payload || {};
  if (!apiKey) return res.status(400).json({ ok: false, error: '缺少 api_key（请到 platform.tripo3d.ai 自助申请）' });
  if (!payload.type) return res.status(400).json({ ok: false, error: '缺少 payload.type（如 text_to_model）' });
  try {
    const r = await axios.post(`${TRIPO3D_BASE_URL}/task`, payload, {
      headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      timeout: 30000
    });
    res.json({ ok: true, data: r.data });
  } catch (e) {
    const status = e.response?.status || 500;
    const data = e.response?.data;
    // v1.8.5：把 Tripo3D 返回的 message + suggestion 抠出来作为友好错误（之前只显示 "Request failed with status code 403" 看不出根因）
    let friendly = e.message;
    if (data && typeof data === 'object') {
      const parts = [];
      if (data.code) parts.push(`code=${data.code}`);
      if (data.message) parts.push(data.message);
      if (data.suggestion) parts.push(`💡 ${data.suggestion}`);
      if (parts.length > 0) friendly = parts.join(' · ');
    }
    // 常见 HTTP 状态额外提示
    if (status === 401) friendly = `🔑 API key 无效或已被禁用 · ${friendly}`;
    else if (status === 403) friendly = `🚫 HTTP 403 · ${friendly} · 常见原因：(1) 免费版同时只能跑 1 个任务，请等待上一个完成；(2) prompt 含中文/敏感词（Tripo3D 要求纯英文）；(3) 账号余额不足`;
    else if (status === 429) friendly = `⏱ HTTP 429 限流 · ${friendly}`;
    res.status(status).json({ ok: false, error: friendly, http_status: status, tripo_response: data });
  }
});

// 查询任务（轮询用）
app.get('/api/tripo3d/task/:task_id', async (req, res) => {
  const apiKey = (req.query.api_key || req.headers['x-tripo-key'] || '').trim();
  const taskId = req.params.task_id;
  if (!apiKey) return res.status(400).json({ ok: false, error: '缺少 api_key' });
  if (!taskId) return res.status(400).json({ ok: false, error: '缺少 task_id' });
  try {
    const r = await axios.get(`${TRIPO3D_BASE_URL}/task/${encodeURIComponent(taskId)}`, {
      headers: { 'Authorization': `Bearer ${apiKey}` },
      timeout: 20000
    });
    res.json({ ok: true, data: r.data });
  } catch (e) {
    const status = e.response?.status || 500;
    res.status(status).json({ ok: false, error: e.message, tripo_response: e.response?.data });
  }
});

// 把 Tripo3D 临时 URL 的 GLB 下载到本地缓存（避免 5 分钟过期 + 让 Blender 端 file:// 导入）
app.post('/api/tripo3d/download-glb', async (req, res) => {
  const url = (req.body.url || '').trim();
  const taskId = (req.body.task_id || 'unknown').replace(/[^a-zA-Z0-9_-]/g, '_');
  if (!url || !/^https?:\/\//i.test(url)) return res.status(400).json({ ok: false, error: '缺少有效 url' });
  try {
    const os = require('os');
    const cacheDir = path.join(os.tmpdir(), 'aichat_tripo3d_cache');
    if (!fs.existsSync(cacheDir)) fs.mkdirSync(cacheDir, { recursive: true });
    const localPath = path.join(cacheDir, `${taskId}.glb`);
    // 已存在且大小 > 0 → 直接复用
    if (fs.existsSync(localPath) && fs.statSync(localPath).size > 0) {
      return res.json({ ok: true, local_path: localPath, cached: true, size: fs.statSync(localPath).size });
    }
    const r = await axios.get(url, { responseType: 'arraybuffer', timeout: 120000 });
    fs.writeFileSync(localPath, Buffer.from(r.data));
    res.json({ ok: true, local_path: localPath, cached: false, size: r.data.byteLength });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// ============================================================================
// v2.1.0 Phase B：暴露真·文件系统（ai-chat-workspace/）
// ----------------------------------------------------------------------------
// 设计要点：
//   1. 工作目录固定在 ~/Desktop/ai-chat-workspace/（用户最易找）
//   2. 每个建模 session 一个子目录：{session_name}_{YYYY-MM-DD_HHmmss}/
//   3. 所有 /api/workspace/file/* 端点强制把请求 path 限制在该 session 子目录内，
//      防止路径穿越（'..' 跳出、绝对路径越权）
//   4. 不限制具体文件后缀，但有大小硬性上限（单文件 10 MB，整 session 200 MB）
//
// 端点：
//   GET   /api/workspace/list-sessions       列出所有 session 子目录
//   POST  /api/workspace/create-session      新建一个 session 子目录
//   POST  /api/workspace/file/read           { session, path } 读文件文本
//   POST  /api/workspace/file/write          { session, path, content } 写文件
//   POST  /api/workspace/file/list           { session, sub_path?, recursive? } 列目录
//   POST  /api/workspace/file/delete         { session, path } 删除文件
//   POST  /api/workspace/open-folder         { session? } 在 Finder/Explorer 打开
// ============================================================================
const AICHAT_WORKSPACE_ROOT = path.join(os.homedir(), 'Desktop', 'ai-chat-workspace');
const WORKSPACE_MAX_FILE_BYTES = 10 * 1024 * 1024;       // 单文件 10 MB
const WORKSPACE_MAX_SESSION_BYTES = 200 * 1024 * 1024;   // 整 session 200 MB
const WORKSPACE_LIST_MAX_ENTRIES = 2000;                 // 列目录最多返回 2000 项（防爆）
const LOCAL_CODEX_JOBS = new Map();

function ensureWorkspaceRoot() {
  if (!fs.existsSync(AICHAT_WORKSPACE_ROOT)) {
    try { fs.mkdirSync(AICHAT_WORKSPACE_ROOT, { recursive: true }); }
    catch (e) { console.error('[workspace] 创建根目录失败:', e.message); }
  }
  // 写一个 README.txt 让用户一打开就知道这是什么
  const readmePath = path.join(AICHAT_WORKSPACE_ROOT, 'README.txt');
  if (!fs.existsSync(readmePath)) {
    try {
      fs.writeFileSync(readmePath,
        [
          '# AI Chat 工作目录（v2.1.0 Phase B 引入）',
          '',
          '这里是「白歌的AI讨论组」MCP Agent 的真·文件系统：',
          '每次开始一个新建模任务，会在这里建一个 session 子目录，',
          'AI 会把 plan.md / scratch.py / critic_notes.md 等中间产物写到对应子目录里，',
          '用户可以随时打开任何一个子目录里的文件查看、编辑、复用。',
          '',
          '## 子目录命名规则',
          '  {session_name}_{YYYY-MM-DD_HHmmss}/',
          '',
          '## AI 写入的典型文件',
          '  plan.md           Planner 写的任务清单（Markdown）',
          '  scratch.py        Modeler 写的草稿 Python 脚本（exec_python 前的版本）',
          '  critic_notes.md   Critic 审图后的反思清单',
          '  scene_snapshot.json  场景快照 / 物体列表',
          '  history.jsonl     工具调用历史（每行一条 JSON）',
          '',
          '## 注意',
          '- 单文件 ≤ 10 MB',
          '- 单 session 总大小 ≤ 200 MB',
          '- 删除一个 session 子目录就完全清理那次任务的中间产物',
        ].join('\n'),
        'utf-8'
      );
    } catch (e) { /* 忽略 */ }
  }
}
ensureWorkspaceRoot();

// 校验 session 名称：只允许字母/数字/下划线/中划线/中文/空格，限长 80
function _safeSessionName(name) {
  if (!name || typeof name !== 'string') return null;
  // 去掉路径分隔符 / 冒号等危险字符
  let s = name.trim().replace(/[\/\\:*?"<>|\.]+/g, '_').slice(0, 80);
  if (!s) return null;
  return s;
}

// 把请求中的相对 path 解析成绝对路径，必须落在 session 子目录内
function _resolveWorkspacePath(sessionName, relPath) {
  const safe = _safeSessionName(sessionName);
  if (!safe) return { error: 'session 名称非法（只允许字母/数字/下划线/中划线/中文/空格，≤80 字）' };
  const sessionDir = path.join(AICHAT_WORKSPACE_ROOT, safe);
  if (!fs.existsSync(sessionDir)) {
    return { error: `session 目录不存在：${safe}（请先调 /api/workspace/create-session）`, sessionDir, safe };
  }
  // 清洗相对路径：禁止以 / 开头、禁止含 .. 跳跃
  let rel = (relPath || '').toString().trim();
  if (rel.startsWith('/') || rel.startsWith('\\')) rel = rel.slice(1);
  if (rel.includes('..')) return { error: 'path 不允许包含 ..（防路径穿越）' };
  const absPath = path.resolve(sessionDir, rel);
  // 二次校验：解析后的绝对路径必须仍在 sessionDir 内
  const rel2 = path.relative(sessionDir, absPath);
  if (rel2.startsWith('..') || path.isAbsolute(rel2)) {
    return { error: 'path 越权（解析后不在 session 目录内）' };
  }
  return { sessionDir, absPath, safe };
}

// 递归计算 session 目录总大小（用于写入前校验）
function _sessionDirSize(sessionDir) {
  let total = 0;
  function walk(dir) {
    let entries;
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const e of entries) {
      const p = path.join(dir, e.name);
      try {
        if (e.isDirectory()) walk(p);
        else if (e.isFile()) total += fs.statSync(p).size;
      } catch {}
    }
  }
  walk(sessionDir);
  return total;
}

// GET /api/workspace/list-sessions  列出所有 session 子目录
app.get('/api/workspace/list-sessions', (req, res) => {
  ensureWorkspaceRoot();
  try {
    const entries = fs.readdirSync(AICHAT_WORKSPACE_ROOT, { withFileTypes: true });
    const sessions = entries
      .filter(e => e.isDirectory())
      .map(e => {
        const dir = path.join(AICHAT_WORKSPACE_ROOT, e.name);
        let stat;
        try { stat = fs.statSync(dir); } catch { return null; }
        let fileCount = 0;
        try { fileCount = fs.readdirSync(dir).length; } catch {}
        return {
          name: e.name,
          path: dir,
          createdAt: stat?.birthtime || stat?.ctime || null,
          modifiedAt: stat?.mtime || null,
          file_count: fileCount,
        };
      })
      .filter(Boolean)
      .sort((a, b) => new Date(b.modifiedAt || 0) - new Date(a.modifiedAt || 0));
    res.json({ ok: true, root: AICHAT_WORKSPACE_ROOT, sessions, total: sessions.length });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /api/workspace/create-session  { name } 新建一个 session 子目录
// 自动加时间戳后缀：{name}_{YYYY-MM-DD_HHmmss}/
app.post('/api/workspace/create-session', (req, res) => {
  ensureWorkspaceRoot();
  const rawName = (req.body?.name || '').toString().trim() || 'session';
  const safe = _safeSessionName(rawName);
  if (!safe) return res.status(400).json({ ok: false, error: 'name 非法' });
  // 生成时间戳：2026-05-18_124530
  const d = new Date();
  const pad = n => String(n).padStart(2, '0');
  const ts = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  const finalName = `${safe}_${ts}`;
  const sessionDir = path.join(AICHAT_WORKSPACE_ROOT, finalName);
  try {
    fs.mkdirSync(sessionDir, { recursive: true });
    // 写一个空 plan.md 占位
    fs.writeFileSync(
      path.join(sessionDir, 'README.md'),
      `# ${finalName}\n\n创建于 ${d.toISOString()}\n\n这是 AI Chat MCP Agent 的 session 工作目录。\n`,
      'utf-8'
    );
    res.json({ ok: true, session: finalName, path: sessionDir });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /api/workspace/file/read  { session, path } 读取文件文本
app.post('/api/workspace/file/read', (req, res) => {
  const { session, path: relPath } = req.body || {};
  const r = _resolveWorkspacePath(session, relPath);
  if (r.error) return res.status(400).json({ ok: false, error: r.error });
  const { absPath } = r;
  try {
    if (!fs.existsSync(absPath)) return res.status(404).json({ ok: false, error: '文件不存在' });
    const stat = fs.statSync(absPath);
    if (stat.isDirectory()) return res.status(400).json({ ok: false, error: '目标是目录而非文件' });
    if (stat.size > WORKSPACE_MAX_FILE_BYTES) {
      return res.status(413).json({ ok: false, error: `文件过大（${stat.size} > ${WORKSPACE_MAX_FILE_BYTES} bytes）` });
    }
    const content = fs.readFileSync(absPath, 'utf-8');
    res.json({ ok: true, session: r.safe, path: relPath, size: stat.size, modifiedAt: stat.mtime, content });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /api/workspace/file/write  { session, path, content, append? }
app.post('/api/workspace/file/write', (req, res) => {
  const { session, path: relPath, content, append } = req.body || {};
  if (typeof content !== 'string') {
    return res.status(400).json({ ok: false, error: 'content 必须是字符串' });
  }
  const r = _resolveWorkspacePath(session, relPath);
  if (r.error) return res.status(400).json({ ok: false, error: r.error });
  const { sessionDir, absPath } = r;
  // 单文件大小校验
  const newSize = Buffer.byteLength(content, 'utf-8');
  if (newSize > WORKSPACE_MAX_FILE_BYTES) {
    return res.status(413).json({ ok: false, error: `content 过大（${newSize} > ${WORKSPACE_MAX_FILE_BYTES} bytes）` });
  }
  // session 总大小校验（粗算：当前总大小 - 该文件旧大小 + 新大小）
  let oldSize = 0;
  try { if (fs.existsSync(absPath)) oldSize = fs.statSync(absPath).size; } catch {}
  const currentTotal = _sessionDirSize(sessionDir);
  const projectedTotal = currentTotal - oldSize + newSize;
  if (projectedTotal > WORKSPACE_MAX_SESSION_BYTES) {
    return res.status(413).json({ ok: false,
      error: `session 总大小超限（写入后 ${projectedTotal} > ${WORKSPACE_MAX_SESSION_BYTES} bytes，请先删旧文件）` });
  }
  try {
    // 确保父目录存在
    fs.mkdirSync(path.dirname(absPath), { recursive: true });
    if (append === true && fs.existsSync(absPath)) {
      fs.appendFileSync(absPath, content, 'utf-8');
    } else {
      fs.writeFileSync(absPath, content, 'utf-8');
    }
    const stat = fs.statSync(absPath);
    res.json({ ok: true, session: r.safe, path: relPath, size: stat.size, modifiedAt: stat.mtime, append: !!append });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /api/workspace/file/list  { session, sub_path?, recursive? }
app.post('/api/workspace/file/list', (req, res) => {
  const { session, sub_path, recursive } = req.body || {};
  const r = _resolveWorkspacePath(session, sub_path || '.');
  if (r.error) return res.status(400).json({ ok: false, error: r.error });
  const { absPath, sessionDir } = r;
  try {
    if (!fs.existsSync(absPath)) return res.status(404).json({ ok: false, error: '目录不存在' });
    const stat = fs.statSync(absPath);
    if (!stat.isDirectory()) return res.status(400).json({ ok: false, error: '目标不是目录' });
    const out = [];
    function walk(dir) {
      if (out.length >= WORKSPACE_LIST_MAX_ENTRIES) return;
      let entries;
      try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
      for (const e of entries) {
        if (out.length >= WORKSPACE_LIST_MAX_ENTRIES) return;
        const p = path.join(dir, e.name);
        let st;
        try { st = fs.statSync(p); } catch { continue; }
        out.push({
          name: e.name,
          path: path.relative(sessionDir, p),
          type: e.isDirectory() ? 'dir' : (e.isFile() ? 'file' : 'other'),
          size: e.isFile() ? st.size : 0,
          modifiedAt: st.mtime
        });
        if (recursive === true && e.isDirectory()) walk(p);
      }
    }
    walk(absPath);
    res.json({ ok: true, session: r.safe, sub_path: sub_path || '.', total: out.length, items: out,
      truncated: out.length >= WORKSPACE_LIST_MAX_ENTRIES });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /api/workspace/file/delete  { session, path }
app.post('/api/workspace/file/delete', (req, res) => {
  const { session, path: relPath } = req.body || {};
  if (!relPath || relPath === '.' || relPath === '/') {
    return res.status(400).json({ ok: false, error: '禁止删除 session 根目录' });
  }
  const r = _resolveWorkspacePath(session, relPath);
  if (r.error) return res.status(400).json({ ok: false, error: r.error });
  const { absPath } = r;
  try {
    if (!fs.existsSync(absPath)) return res.status(404).json({ ok: false, error: '目标不存在' });
    const stat = fs.statSync(absPath);
    if (stat.isDirectory()) {
      fs.rmSync(absPath, { recursive: true, force: true });
    } else {
      fs.unlinkSync(absPath);
    }
    res.json({ ok: true, session: r.safe, path: relPath, deleted: true });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /api/workspace/open-folder  { session? }
// 用系统命令打开 Finder/Explorer（不依赖 Electron shell.openPath，方便浏览器模式也能用）
app.post('/api/workspace/open-folder', (req, res) => {
  ensureWorkspaceRoot();
  const sessionName = (req.body?.session || '').toString().trim();
  let target = AICHAT_WORKSPACE_ROOT;
  if (sessionName) {
    const safe = _safeSessionName(sessionName);
    if (!safe) return res.status(400).json({ ok: false, error: 'session 非法' });
    const dir = path.join(AICHAT_WORKSPACE_ROOT, safe);
    if (fs.existsSync(dir)) target = dir;
  }
  let cmd;
  if (process.platform === 'darwin') cmd = `open "${target}"`;
  else if (process.platform === 'win32') cmd = `explorer "${target.replace(/\//g, '\\')}"`;
  else cmd = `xdg-open "${target}"`;
  exec(cmd, (err) => {
    if (err) return res.status(500).json({ ok: false, error: err.message, target });
    res.json({ ok: true, target });
  });
});

// ==================== 本地 Codex 后备模式 ====================
// 无 API key / API 不可用时，调用本机 Codex CLI 在 workspace session 内生成 Blender 脚本。
function _findCodexBin() {
  const candidates = [
    process.env.CODEX_BIN,
    '/Applications/Codex.app/Contents/Resources/codex',
    '/opt/homebrew/bin/codex',
    '/usr/local/bin/codex',
    'codex'
  ].filter(Boolean);
  for (const c of candidates) {
    if (c === 'codex' || fs.existsSync(c)) return c;
  }
  return 'codex';
}

function _readLocalCodexOutputs(sessionDir) {
  const outputPath = path.join(sessionDir, 'codex_result.md');
  const stdoutPath = path.join(sessionDir, 'codex_stdout.log');
  const stderrPath = path.join(sessionDir, 'codex_stderr.log');
  const scriptPath = path.join(sessionDir, 'scene_script.py');
  const planPath = path.join(sessionDir, 'plan.md');
  let result = '', stdout = '', stderr = '', script = '', plan = '';
  try { if (fs.existsSync(outputPath)) result = fs.readFileSync(outputPath, 'utf-8'); } catch {}
  try { if (fs.existsSync(stdoutPath)) stdout = fs.readFileSync(stdoutPath, 'utf-8'); } catch {}
  try { if (fs.existsSync(stderrPath)) stderr = fs.readFileSync(stderrPath, 'utf-8'); } catch {}
  try { if (fs.existsSync(scriptPath)) script = fs.readFileSync(scriptPath, 'utf-8'); } catch {}
  try { if (fs.existsSync(planPath)) plan = fs.readFileSync(planPath, 'utf-8'); } catch {}
  return { outputPath, stdoutPath, stderrPath, scriptPath, planPath, result, stdout, stderr, script, plan };
}

function _buildLocalCodexArgs(sessionDir, outputPath) {
  return [
    '--ask-for-approval', 'never',
    'exec',
    '--cd', sessionDir,
    '--skip-git-repo-check',
    '--sandbox', 'workspace-write',
    '--ignore-rules',
    '--output-last-message', outputPath,
    '-'
  ];
}

function _startLocalCodexJob({ session, prompt, timeoutSec }) {
  const r = _resolveWorkspacePath(session, '.');
  if (r.error) throw new Error(r.error);
  const sessionDir = r.absPath;
  const codexBin = _findCodexBin();
  const taskPath = path.join(sessionDir, 'codex_task.md');
  const outputPath = path.join(sessionDir, 'codex_result.md');
  const stdoutPath = path.join(sessionDir, 'codex_stdout.log');
  const stderrPath = path.join(sessionDir, 'codex_stderr.log');
  const timeoutMs = Math.max(60, Math.min(1800, Number(timeoutSec) || 900)) * 1000;
  fs.writeFileSync(taskPath, prompt, 'utf-8');

  const jobId = randomUUID();
  const job = {
    id: jobId,
    ok: null,
    status: 'running',
    session: r.safe,
    session_path: sessionDir,
    codexBin,
    startedAt: new Date().toISOString(),
    finishedAt: null,
    code: null,
    timed_out: false,
    error: null,
    files: {
      task: taskPath,
      result: outputPath,
      stdout: stdoutPath,
      stderr: stderrPath,
      script: path.join(sessionDir, 'scene_script.py'),
      plan: path.join(sessionDir, 'plan.md')
    },
    stdout_tail: '',
    stderr_tail: ''
  };
  LOCAL_CODEX_JOBS.set(jobId, job);

  const args = _buildLocalCodexArgs(sessionDir, outputPath);
  let stdout = '', stderr = '';
  const child = spawn(codexBin, args, {
    cwd: sessionDir,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, FORCE_COLOR: '0', NO_COLOR: '1' }
  });
  job.pid = child.pid || null;

  const timer = setTimeout(() => {
    job.timed_out = true;
    try { child.kill('SIGTERM'); } catch {}
    setTimeout(() => { try { child.kill('SIGKILL'); } catch {} }, 3000);
  }, timeoutMs);

  child.stdout.on('data', d => {
    stdout += d.toString();
    if (stdout.length > 200000) stdout = stdout.slice(-200000);
    job.stdout_tail = stdout.slice(-12000);
  });
  child.stderr.on('data', d => {
    stderr += d.toString();
    if (stderr.length > 200000) stderr = stderr.slice(-200000);
    job.stderr_tail = stderr.slice(-12000);
  });
  child.on('error', e => {
    clearTimeout(timer);
    job.status = 'failed';
    job.ok = false;
    job.finishedAt = new Date().toISOString();
    job.error = '启动 Codex 失败: ' + e.message;
  });
  child.on('close', code => {
    clearTimeout(timer);
    try { fs.writeFileSync(stdoutPath, stdout, 'utf-8'); } catch {}
    try { fs.writeFileSync(stderrPath, stderr, 'utf-8'); } catch {}
    const out = _readLocalCodexOutputs(sessionDir);
    const ok = code === 0 && !!out.script.trim();
    job.status = ok ? 'done' : 'failed';
    job.ok = ok;
    job.code = code;
    job.finishedAt = new Date().toISOString();
    job.script = out.script;
    job.plan = out.plan;
    job.result = out.result;
    job.stdout_tail = out.stdout.slice(-12000);
    job.stderr_tail = out.stderr.slice(-12000);
    job.error = ok ? null : (job.timed_out ? 'Codex 执行超时' : (!out.script.trim() ? 'Codex 未生成 scene_script.py' : `Codex 退出码 ${code}`));
  });

  child.stdin.write(prompt);
  child.stdin.end();
  return job;
}

app.get('/api/local-codex/status', (req, res) => {
  const codexBin = _findCodexBin();
  const child = spawn(codexBin, ['--version'], { stdio: ['ignore', 'pipe', 'pipe'] });
  let out = '', err = '';
  child.stdout.on('data', d => { out += d.toString(); });
  child.stderr.on('data', d => { err += d.toString(); });
  child.on('error', e => res.json({ ok: false, available: false, codexBin, error: e.message }));
  child.on('close', code => {
    res.json({ ok: code === 0, available: code === 0, codexBin, version: out.trim(), error: err.trim() });
  });
});

app.post('/api/local-codex/run', async (req, res) => {
  const { session, prompt, timeout_sec } = req.body || {};
  console.log(`[Local Codex] run requested: session=${session || '(missing)'} prompt=${typeof prompt === 'string' ? prompt.length : 0} chars`);
  if (!prompt || typeof prompt !== 'string') {
    return res.status(400).json({ ok: false, error: 'prompt 必须是字符串' });
  }
  const r = _resolveWorkspacePath(session, '.');
  if (r.error) return res.status(400).json({ ok: false, error: r.error });
  const sessionDir = r.absPath;
  const codexBin = _findCodexBin();
  const taskPath = path.join(sessionDir, 'codex_task.md');
  const outputPath = path.join(sessionDir, 'codex_result.md');
  const stdoutPath = path.join(sessionDir, 'codex_stdout.log');
  const stderrPath = path.join(sessionDir, 'codex_stderr.log');
  const timeoutMs = Math.max(60, Math.min(1800, Number(timeout_sec) || 900)) * 1000;

  try {
    fs.writeFileSync(taskPath, prompt, 'utf-8');
  } catch (e) {
    return res.status(500).json({ ok: false, error: '写入 codex_task.md 失败: ' + e.message });
  }

  const args = [
    '--ask-for-approval', 'never',
    'exec',
    '--cd', sessionDir,
    '--skip-git-repo-check',
    '--sandbox', 'workspace-write',
    '--ignore-rules',
    '--output-last-message', outputPath,
    '-'
  ];

  let stdout = '', stderr = '';
  let timedOut = false;
  let responded = false;
  const child = spawn(codexBin, args, {
    cwd: sessionDir,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, FORCE_COLOR: '0', NO_COLOR: '1' }
  });

  const timer = setTimeout(() => {
    timedOut = true;
    try { child.kill('SIGTERM'); } catch {}
    setTimeout(() => { try { child.kill('SIGKILL'); } catch {} }, 3000);
  }, timeoutMs);

  child.stdout.on('data', d => {
    stdout += d.toString();
    if (stdout.length > 200000) stdout = stdout.slice(-200000);
  });
  child.stderr.on('data', d => {
    stderr += d.toString();
    if (stderr.length > 200000) stderr = stderr.slice(-200000);
  });

  child.on('error', e => {
    clearTimeout(timer);
    if (responded) return;
    responded = true;
    res.status(500).json({ ok: false, error: '启动 Codex 失败: ' + e.message, codexBin });
  });

  child.on('close', code => {
    clearTimeout(timer);
    if (responded) return;
    responded = true;
    try { fs.writeFileSync(stdoutPath, stdout, 'utf-8'); } catch {}
    try { fs.writeFileSync(stderrPath, stderr, 'utf-8'); } catch {}

    const scriptPath = path.join(sessionDir, 'scene_script.py');
    const planPath = path.join(sessionDir, 'plan.md');
    let result = '';
    try { if (fs.existsSync(outputPath)) result = fs.readFileSync(outputPath, 'utf-8'); } catch {}
    let script = '';
    try { if (fs.existsSync(scriptPath)) script = fs.readFileSync(scriptPath, 'utf-8'); } catch {}
    let plan = '';
    try { if (fs.existsSync(planPath)) plan = fs.readFileSync(planPath, 'utf-8'); } catch {}

    const ok = code === 0 && !!script.trim();
    res.status(ok ? 200 : 500).json({
      ok,
      code,
      timed_out: timedOut,
      codexBin,
      session: r.safe,
      session_path: sessionDir,
      files: {
        task: taskPath,
        result: outputPath,
        stdout: stdoutPath,
        stderr: stderrPath,
        script: scriptPath,
        plan: planPath
      },
      script,
      plan,
      result,
      stdout_tail: stdout.slice(-12000),
      stderr_tail: stderr.slice(-12000),
      error: ok ? undefined : (timedOut ? 'Codex 执行超时' : (!script.trim() ? 'Codex 未生成 scene_script.py' : `Codex 退出码 ${code}`))
    });
  });

  child.stdin.write(prompt);
  child.stdin.end();
});

app.post('/api/local-codex/start', (req, res) => {
  const { session, prompt, timeout_sec } = req.body || {};
  console.log(`[Local Codex] start requested: session=${session || '(missing)'} prompt=${typeof prompt === 'string' ? prompt.length : 0} chars`);
  if (!prompt || typeof prompt !== 'string') {
    return res.status(400).json({ ok: false, error: 'prompt 必须是字符串' });
  }
  try {
    const job = _startLocalCodexJob({ session, prompt, timeoutSec: timeout_sec });
    res.json({ ok: true, job_id: job.id, status: job.status, session: job.session, session_path: job.session_path, files: job.files });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

app.get('/api/local-codex/job/:id', (req, res) => {
  const job = LOCAL_CODEX_JOBS.get(req.params.id);
  if (!job) return res.status(404).json({ ok: false, error: '任务不存在或已过期' });
  const payload = { ...job };
  if (payload.status === 'running') {
    const out = _readLocalCodexOutputs(job.session_path);
    payload.stdout_tail = out.stdout.slice(-12000) || payload.stdout_tail;
    payload.stderr_tail = out.stderr.slice(-12000) || payload.stderr_tail;
  }
  res.json(payload);
});


// ============================================================================
// v2.1.0 Phase C：bpy API 实时检索（cheatsheet）
// v2.1.0 Phase E：bmesh / Geometry Nodes 模板库
// ----------------------------------------------------------------------------
// 设计要点：
//   1. server.js 启动时一次性把 scripts/bpy-cheatsheet.json + bmesh-templates.json 加载到内存
//   2. 提供 3 个端点：
//      GET  /api/bpy/search?q=keyword&limit=N     bpy API 模糊搜（关键词命中度排序）
//      GET  /api/bpy/templates                     列出全部模板（schema 概要，给 AI 选择用）
//      POST /api/bpy/templates/render              { name, params } → 渲染参数到模板代码
//   3. 模板渲染器：Mustache 风格 `{{var}}` 占位符 + `{{var|json}}` 修饰（json 串化）
//      未提供的参数取 default；类型用 params 数组里的 type 校验；
//      所有结果直接返回 Python 字符串，AI 拿到后通过 exec_python 推到 Blender
// ============================================================================
const BPY_CHEATSHEET_PATH = path.join(__dirname, 'scripts', 'bpy-cheatsheet.json');
const BMESH_TEMPLATES_PATH = path.join(__dirname, 'scripts', 'bmesh-templates.json');
let _BPY_CHEATSHEET = { version: '0.0.0', entries: [] };
let _BMESH_TEMPLATES = { version: '0.0.0', templates: [] };

function _loadBpyCheatsheet() {
  try {
    if (fs.existsSync(BPY_CHEATSHEET_PATH)) {
      _BPY_CHEATSHEET = JSON.parse(fs.readFileSync(BPY_CHEATSHEET_PATH, 'utf-8'));
      console.log(`[bpy] cheatsheet 已加载：${_BPY_CHEATSHEET.entries.length} 条`);
    } else {
      console.warn(`[bpy] 找不到 ${BPY_CHEATSHEET_PATH}（search_bpy_docs 工具不可用）`);
    }
  } catch (e) {
    console.error('[bpy] cheatsheet 加载失败:', e.message);
  }
}
function _loadBmeshTemplates() {
  try {
    if (fs.existsSync(BMESH_TEMPLATES_PATH)) {
      _BMESH_TEMPLATES = JSON.parse(fs.readFileSync(BMESH_TEMPLATES_PATH, 'utf-8'));
      console.log(`[bpy] templates 已加载：${_BMESH_TEMPLATES.templates.length} 个`);
    } else {
      console.warn(`[bpy] 找不到 ${BMESH_TEMPLATES_PATH}（apply_template 工具不可用）`);
    }
  } catch (e) {
    console.error('[bpy] templates 加载失败:', e.message);
  }
}
_loadBpyCheatsheet();
_loadBmeshTemplates();

// v3.3.0 脚本生成大师 · 8 个高精度场景 prompt 模板
const SCENE_PROMPTS_PATH = path.join(__dirname, 'scripts', 'scene-prompts.json');
let _SCENE_PROMPTS = { version: '0.0.0', templates: [], shared_master_rules: '' };
function _loadScenePrompts() {
  try {
    if (fs.existsSync(SCENE_PROMPTS_PATH)) {
      _SCENE_PROMPTS = JSON.parse(fs.readFileSync(SCENE_PROMPTS_PATH, 'utf-8'));
      console.log(`[script-master] scene-prompts 已加载：${_SCENE_PROMPTS.templates.length} 个模板`);
    } else {
      console.warn(`[script-master] 找不到 ${SCENE_PROMPTS_PATH}`);
    }
  } catch (e) {
    console.error('[script-master] scene-prompts 加载失败:', e.message);
  }
}
_loadScenePrompts();

// GET /api/scene-prompts/list — 返回所有模板的元数据（id/name/keywords，不含 system_prompt 长内容，省 token）
app.get('/api/scene-prompts/list', (req, res) => {
  try {
    const items = (_SCENE_PROMPTS.templates || []).map(t => ({
      id: t.id, name: t.name, keywords: t.keywords || [],
      prompt_chars: (t.system_prompt || '').length
    }));
    res.json({ ok: true, version: _SCENE_PROMPTS.version, total: items.length, templates: items });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /api/scene-prompts/match — 按用户描述模糊匹配最佳模板，返回 top-3
// body: { description: '...', limit?: 3 }
app.post('/api/scene-prompts/match', (req, res) => {
  try {
    const { description = '', limit = 3 } = req.body || {};
    const desc = description.toString().toLowerCase();
    if (!desc.trim()) return res.status(400).json({ ok: false, error: 'description 不能为空' });
    const scored = [];
    for (const t of _SCENE_PROMPTS.templates || []) {
      let score = 0;
      for (const kw of (t.keywords || [])) {
        if (desc.includes(kw.toLowerCase())) score += 10;
      }
      // name 命中也加分（中文名）
      if (t.name) {
        for (const word of t.name.split(/[·\s/]+/).filter(Boolean)) {
          if (desc.includes(word.toLowerCase())) score += 5;
        }
      }
      if (score > 0) scored.push({ id: t.id, name: t.name, score, keywords: t.keywords });
    }
    scored.sort((a, b) => b.score - a.score);
    // v3.3.2 兜底：0 命中时回退到所有模板按 id 顺序，分数标 1，加 fallback 标志
    let fallback = false;
    if (scored.length === 0) {
      fallback = true;
      for (const t of _SCENE_PROMPTS.templates || []) {
        scored.push({ id: t.id, name: t.name, score: 1, keywords: t.keywords });
      }
    }
    res.json({ ok: true, total: scored.length, fallback, matches: scored.slice(0, limit) });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// GET /api/scene-prompts/:id — 拿单个模板的完整 system_prompt（含 shared_master_rules 拼接好的）
app.get('/api/scene-prompts/:id', (req, res) => {
  try {
    const tpl = (_SCENE_PROMPTS.templates || []).find(t => t.id === req.params.id);
    if (!tpl) return res.status(404).json({ ok: false, error: '模板不存在' });
    const fullPrompt = (_SCENE_PROMPTS.shared_master_rules || '') + '\n\n---\n\n' + (tpl.system_prompt || '');
    res.json({
      ok: true, id: tpl.id, name: tpl.name, keywords: tpl.keywords,
      system_prompt: tpl.system_prompt, full_prompt: fullPrompt,
      shared_master_rules: _SCENE_PROMPTS.shared_master_rules || ''
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});


// bpy 速查表模糊搜：按 keywords / title / category 多字段加权打分排序
function _searchBpyEntries(query, limit) {
  const q = (query || '').toString().toLowerCase().trim();
  if (!q) return [];
  const tokens = q.split(/[\s,，、]+/).filter(Boolean);
  const scored = [];
  for (const e of _BPY_CHEATSHEET.entries || []) {
    let score = 0;
    const id = (e.id || '').toLowerCase();
    const title = (e.title || '').toLowerCase();
    const cat = (e.category || '').toLowerCase();
    const kws = (e.keywords || []).map(k => String(k).toLowerCase());
    const code = (e.code || '').toLowerCase();
    for (const t of tokens) {
      // keywords 完全匹配 +30；包含 +18
      for (const k of kws) {
        if (k === t) score += 30;
        else if (k.includes(t) || t.includes(k)) score += 18;
      }
      // id / title / category 命中
      if (id === t) score += 25;
      else if (id.includes(t)) score += 12;
      if (title.includes(t)) score += 8;
      if (cat === t) score += 14;
      else if (cat.includes(t)) score += 6;
      // code 命中（最弱）
      if (code.includes(t)) score += 2;
    }
    if (score > 0) scored.push({ score, entry: e });
  }
  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, Math.max(1, Math.min(limit || 5, 20)));
  return top.map(s => ({
    id: s.entry.id,
    title: s.entry.title,
    category: s.entry.category,
    keywords: s.entry.keywords,
    code: s.entry.code,
    deprecated: s.entry.deprecated || '',
    see_also: s.entry.see_also || [],
    _score: s.score
  }));
}

// 模板参数渲染器：Mustache 风格 {{var}} / {{var|json}}
function _renderTemplateCode(tpl, params) {
  const paramMap = {};
  // 1) 用 params schema 里的 default 兜底
  for (const p of (tpl.params || [])) {
    paramMap[p.name] = (params && params[p.name] !== undefined) ? params[p.name] : p.default;
  }
  // 2) 替换占位符
  let code = String(tpl.code || '');
  // 优先处理带修饰的 {{name|json}}
  code = code.replace(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*json\s*\}\}/g, (m, key) => {
    if (paramMap[key] === undefined) return 'None';
    return JSON.stringify(paramMap[key]);
  });
  // 再处理无修饰的 {{name}}
  code = code.replace(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g, (m, key) => {
    const v = paramMap[key];
    if (v === undefined || v === null) return '0';
    if (typeof v === 'number') return String(v);
    if (typeof v === 'boolean') return v ? 'True' : 'False';
    if (typeof v === 'string') return JSON.stringify(v);   // 字符串自动加双引号
    return JSON.stringify(v);
  });
  return { code, paramMap };
}

// GET /api/bpy/search?q=...&limit=5  bpy API 速查表模糊搜
app.get('/api/bpy/search', (req, res) => {
  try {
    const q = (req.query.q || '').toString();
    const limit = parseInt(req.query.limit || '5', 10);
    if (!q.trim()) return res.status(400).json({ ok: false, error: '缺少查询参数 q' });
    if (!_BPY_CHEATSHEET.entries || !_BPY_CHEATSHEET.entries.length) {
      return res.json({
        ok: true, query: q, total: 0, results: [],
        warning: 'bpy-cheatsheet.json 未加载或为空'
      });
    }
    const results = _searchBpyEntries(q, limit);
    res.json({
      ok: true,
      query: q,
      cheatsheet_version: _BPY_CHEATSHEET.version,
      cheatsheet_total: _BPY_CHEATSHEET.entries.length,
      total: results.length,
      results
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// GET /api/bpy/templates  列出全部 bmesh / GN 模板（schema 概要）
app.get('/api/bpy/templates', (req, res) => {
  try {
    const summary = (_BMESH_TEMPLATES.templates || []).map(t => ({
      name: t.name,
      title: t.title,
      category: t.category,
      description: t.description,
      params: (t.params || []).map(p => ({
        name: p.name,
        type: p.type,
        default: p.default,
        description: p.description
      }))
    }));
    res.json({
      ok: true,
      templates_version: _BMESH_TEMPLATES.version,
      total: summary.length,
      templates: summary
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /api/bpy/templates/render  { name, params }
//   返回 { ok, name, code, paramMap }  → 调用方可以拿 code 直接走 /api/blender/exec 或 exec_python
app.post('/api/bpy/templates/render', (req, res) => {
  try {
    const { name, params } = req.body || {};
    if (!name) return res.status(400).json({ ok: false, error: '缺少 name 字段' });
    const tpl = (_BMESH_TEMPLATES.templates || []).find(t => t.name === name);
    if (!tpl) {
      const known = (_BMESH_TEMPLATES.templates || []).map(t => t.name);
      return res.status(404).json({
        ok: false,
        error: `未知模板 name="${name}"。可用模板：${known.join(' / ')}`
      });
    }
    const { code, paramMap } = _renderTemplateCode(tpl, params || {});
    res.json({
      ok: true,
      name: tpl.name,
      title: tpl.title,
      category: tpl.category,
      paramMap,
      code,
      code_size: code.length
    });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});



// ==================== PS 辅助 MCP 代理 ====================

// PS MCP ping 检测连接
app.get('/api/ps-mcp/ping', async (req, res) => {
  const url = req.query.url || `http://127.0.0.1:${psBridgePort}`;
  // Auto-start bridge if not running
  if (!psBridgeProcess) startPSBridge();
  try {
    const response = await axios.get(url, { timeout: 3000 });
    res.json({ ok: true, status: response.status, bridgeRunning: psBridgeProcess !== null });
  } catch (err) {
    res.json({ ok: false, error: err.message, bridgeRunning: false });
  }
});

// PS MCP 执行指令
app.post('/api/ps-mcp/execute', async (req, res) => {
  const { mcpUrl, commands } = req.body;
  if (!mcpUrl || !commands) {
    return res.status(400).json({ error: 'mcpUrl and commands required' });
  }
  try {
    let results = [];
    for (const cmd of (Array.isArray(commands) ? commands : [commands])) {
      const response = await axios.post(mcpUrl, cmd, { timeout: 30000 });
      results.push(response.data);
    }
    res.json({ ok: true, result: results });
  } catch (err) {
    res.json({ ok: false, error: err.message });
  }
});

// PS 辅助聊天端点 - 代理 AI 请求 + 生成 MCP 指令
app.post('/api/ps-assist/chat', async (req, res) => {
  const { configId, modelId, prompt, mcpUrl, messages, autoFilter } = req.body;
  
  if (!configId || !modelId || !prompt) {
    return res.status(400).json({ error: '缺少必要参数' });
  }

  const configs = readConfigs();
  const config = configs.find(c => c.id === configId);
  if (!config) return res.status(404).json({ error: '供应商配置不存在' });

  let baseUrl = config.base_url.trim().replace(/\/+$/, '');
  if (!baseUrl.endsWith('/v1')) baseUrl += '/v1';

  const chatMessages = [];
  
  const psSystemPrompt = `You are a Photoshop automation assistant. You communicate via MCP (Model Context Protocol) to control Adobe Photoshop.

When the user asks you to perform operations in Photoshop:
1. First, explain what you plan to do in the user's language (Chinese)
2. Then provide the MCP commands in a structured JSON block using \`\`\`mcp code blocks
3. The MCP commands will be automatically executed on the user's Photoshop

Available MCP tools:
- create_document(width, height, name, resolution)
- add_text_layer(text, font, size, color, position)
- add_adjustment_layer(type, params)
- apply_filter(filter_name, params)
- resize_canvas(width, height)
- export(format, path, quality)
- select_layer(name_or_index)
- delete_layer(name_or_index)
- move_layer(x, y)
- change_blend_mode(layer, mode)
- duplicate_layer(name)
- merge_visible()
- crop(x, y, width, height)

Format commands exactly as:
\`\`\`mcp
{"tool": "tool_name", "params": {}}
\`\`\`

ALWAYS respond in Chinese, and provide practical, actionable responses.`;

  chatMessages.push({ role: 'system', content: psSystemPrompt });
  
  if (Array.isArray(messages)) {
    chatMessages.push(...messages);
  }
  
  chatMessages.push({ role: 'user', content: prompt });

  try {
    const response = await axios.post(`${baseUrl}/chat/completions`, {
      model: modelId,
      messages: chatMessages,
      max_tokens: 4096,
      temperature: 0.7
    }, {
      headers: { 
        'Authorization': `Bearer ${config.api_key}`,
        'Content-Type': 'application/json'
      },
      timeout: 120000
    });

    const reply = response.data.choices?.[0]?.message?.content || '';
    
    const mcpCommands = [];
    const mcpRegex = /```mcp\s*\n([\s\S]*?)\n```/g;
    let match;
    while ((match = mcpRegex.exec(reply)) !== null) {
      try {
        const cmd = JSON.parse(match[1].trim());
        mcpCommands.push(cmd);
      } catch(e) {}
    }

    if (mcpCommands.length === 0) {
      try {
        const parsed = JSON.parse(reply.trim());
        if (parsed.tool && parsed.params) {
          mcpCommands.push(parsed);
        }
      } catch(e) {}
    }

    res.json({ 
      reply,
      mcpCommands: mcpCommands.length > 0 ? mcpCommands : undefined
    });
  } catch (err) {
    const errMsg = err.response?.data?.error?.message || err.message;
    res.status(500).json({ error: 'AI 请求失败: ' + errMsg });
  }
});


// ============================================================================
// v3.4.4: 混元3D (Hunyuan3D) 本地生成 API
// ----------------------------------------------------------------------------
// 使用方式：
//   1. 确保已安装 Python 依赖并下载模型权重
//   2. 在独立终端运行: python3 hunyuan3d_service.py
//   3. 本端点将请求转发到 hunyuan3d_service.py (默认端口 8767)
// 
// 支持两种模式：
//   - from-image: 从图像生成3D模型
//   - from-text:  从文本生成3D模型（需要先生成图像）
// ============================================================================
const HUNYUAN_BASE_URL = process.env.HUNYUAN_BASE_URL || 'http://127.0.0.1:8767';
function getHunyuanPort() {
  try { return Number(new URL(HUNYUAN_BASE_URL).port || 80) || 8767; }
  catch (e) { return 8767; }
}
function execShell(cmd) {
  return new Promise((resolve) => {
    exec(cmd, { timeout: 5000 }, (error, stdout, stderr) => resolve({ error, stdout: stdout || '', stderr: stderr || '' }));
  });
}
async function findListeningPids(port) {
  const found = new Set();
  const lsof = await execShell(`lsof -nP -tiTCP:${port} -sTCP:LISTEN`);
  String(lsof.stdout || '').split(/\s+/).filter(Boolean).forEach(pid => found.add(pid));
  return [...found];
}
async function killListeningPids(port) {
  const pids = await findListeningPids(port);
  for (const pid of pids) {
    if (String(pid) === String(process.pid)) continue;
    try { process.kill(Number(pid), 'SIGKILL'); } catch (e) {}
  }
  if (pids.length > 0) await new Promise(r => setTimeout(r, 500));
  return pids;
}

app.post('/api/hunyuan/generate', async (req, res) => {
  // v3.8.1 修复：mode 在 from-text 分支会被重写为 'from-image'（见下方），
  //   原来用 const 声明导致 "Assignment to constant variable" 崩溃 → from-text 必失败
  let { mode, image, prompt, texture } = req.body;
  
  if (!mode || !['from-image', 'from-text'].includes(mode)) {
    return res.status(400).json({ 
      ok: false, 
      error: 'mode 必须是 "from-image" 或 "from-text"' 
    });
  }
  
  if (mode === 'from-image' && !image) {
    return res.status(400).json({ 
      ok: false, 
      error: 'from-image 模式需要提供 image 字段（base64编码的PNG图像）' 
    });
  }
  
  if (mode === 'from-text' && !prompt) {
    return res.status(400).json({ 
      ok: false, 
      error: 'from-text 模式需要提供 prompt 字段（文本描述）' 
    });
  }
  
  try {
    let actualImage = image;
    
    // v3.8.0: from-text 模式 → 先用生图模型生成参考图，再转 from-image
    // Hunyuan3D-2mini 只支持 image-to-3D，不支持纯文本
    if (mode === 'from-text') {
      const { config_id, image_model } = req.body;
      if (!config_id || !image_model) {
        return res.json({
          ok: false,
          error: 'from-text 模式需要启用生图模型。请在 Agent 设置中配置生图模型（config_id + image_model）。',
          hint: '混元3D-2mini 不支持纯文本生成3D，需要先用生图模型生成参考图。'
        });
      }
      
      console.log(`[hunyuan3d] from-text: 先用生图模型生成参考图 → prompt: ${prompt}`);
      // 调用已有的 /api/generate-texture 生成参考图
      const configs = readConfigs();
      const imgConfig = configs.find(c => c.id === config_id);
      if (!imgConfig) {
        return res.json({ ok: false, error: '生图模型配置不存在: ' + config_id });
      }
      
      let imgBaseUrl = imgConfig.base_url.trim().replace(/\/+$/, '');
      if (!imgBaseUrl.includes('/v1')) imgBaseUrl += '/v1';
      
      // 生成参考图（正面视角，白色背景，适合3D重建）
      const enhancedPrompt = prompt + ', front view, centered, white background, product photography, high quality, 3D model reference';
      let refImageB64 = null;
      
      try {
        const imgR = await axios.post(imgBaseUrl + '/images/generations', {
          model: image_model,
          prompt: enhancedPrompt,
          n: 1,
          size: '1024x1024',
          response_format: 'b64_json'
        }, {
          headers: { Authorization: 'Bearer ' + imgConfig.api_key, 'Content-Type': 'application/json' },
          timeout: 180000
        });
        const item = (imgR.data && imgR.data.data && imgR.data.data[0]) || {};
        if (item.b64_json) refImageB64 = item.b64_json;
        else if (item.url) {
          // 下载 URL 转 base64
          const dlR = await axios.get(item.url, { responseType: 'arraybuffer', timeout: 60000 });
          refImageB64 = Buffer.from(dlR.data).toString('base64');
        }
      } catch (imgErr) {
        // fallback: 走 chat completions
        try {
          const chatR = await axios.post(imgBaseUrl + '/chat/completions', {
            model: image_model,
            messages: [{ role: 'user', content: enhancedPrompt + '\n\nPlease generate this image.' }],
            stream: false
          }, {
            headers: { Authorization: 'Bearer ' + imgConfig.api_key, 'Content-Type': 'application/json' },
            timeout: 180000
          });
          const text = chatR.data?.choices?.[0]?.message?.content || '';
          const textStr = typeof text === 'string' ? text : '';
          const dataUri = textStr.match(/data:image\/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=]+)/);
          if (dataUri) refImageB64 = dataUri[1];
        } catch (e2) {
          return res.json({ ok: false, error: '生图模型调用失败: ' + (imgErr.message || '') + ' / ' + (e2.message || '') });
        }
      }
      
      if (!refImageB64) {
        return res.json({
          ok: false,
          error: '生图模型未返回图片，无法进行3D生成。请确认使用的是生图模型（如 gpt-image-1 / dall-e-3 / flux）。',
        });
      }
      
      console.log(`[hunyuan3d] from-text: 参考图生成成功（${(refImageB64.length / 1024).toFixed(0)} KB），转 from-image 模式`);
      
      // 保存预览图供前端显示
      const previewDir = path.join(os.homedir(), 'Desktop', 'ai-chat-workspace', '_hunyuan3d_previews');
      if (!fs.existsSync(previewDir)) fs.mkdirSync(previewDir, { recursive: true });
      const previewPath = path.join(previewDir, `preview_${Date.now()}.png`);
      fs.writeFileSync(previewPath, Buffer.from(refImageB64, 'base64'));
      
      actualImage = refImageB64;
      mode = 'from-image';  // 转换模式
    }
    
    // 统一走 from-image
    const response = await axios.post(
      HUNYUAN_BASE_URL + '/generate/from-image',
      { image: actualImage, texture: texture !== false },
      { timeout: 600000 }  // 10分钟超时
    );
    
    if (response.data?.ok && response.data.glb_base64) {
      // v3.8.0: 直接落盘到 workspace，不返回 base64 给前端/LLM（防止上下文窗口爆炸）
      const glbBuf = Buffer.from(response.data.glb_base64, 'base64');
      const glbSize = glbBuf.length;
      const fname = `hunyuan3d_${Date.now()}.glb`;
      
      // 落盘到 ai-chat-workspace 临时目录
      const wsRoot = path.join(os.homedir(), 'Desktop', 'ai-chat-workspace');
      const modelsDir = path.join(wsRoot, '_hunyuan3d_models');
      if (!fs.existsSync(modelsDir)) fs.mkdirSync(modelsDir, { recursive: true });
      const localPath = path.join(modelsDir, fname);
      fs.writeFileSync(localPath, glbBuf);
      
      res.json({
        ok: true,
        local_path: localPath,
        filename: fname,
        size: glbSize,
        size_human: glbSize > 1048576 ? (glbSize / 1048576).toFixed(1) + ' MB' : (glbSize / 1024).toFixed(0) + ' KB',
        has_texture: response.data.has_texture,
        message: `✅ 3D模型已生成并保存到 ${localPath}（${glbSize > 1048576 ? (glbSize / 1048576).toFixed(1) + ' MB' : (glbSize / 1024).toFixed(0) + ' KB'}）。请用 exec_python 调 bpy.ops.import_scene.gltf(filepath="${localPath}") 导入 Blender。`
      });
    } else {
      res.json({
        ok: false,
        error: response.data?.error || '生成失败',
        hint: '请确保 hunyuan3d_service.py 正在运行且已安装所有依赖'
      });
    }
  } catch (err) {
    console.error('[/api/hunyuan/generate] 错误:', err.message);
    
    // 根据错误类型提供友好的提示
    if (err.code === 'ECONNREFUSED' || err.code === 'ENOTFOUND') {
      res.json({
        ok: false,
        error_type: 'service_not_running',
        error: '混元3D服务未启动',
        hint: '请在独立终端运行: python3 ai-chat/3d/hunyuan3d_service.py'
      });
    } else if (err.code === 'ETIMEDOUT' || err.message.includes('timeout')) {
      res.json({
        ok: false,
        error_type: 'timeout',
        error: '生成超时（超过10分钟）',
        hint: '3D模型生成可能需要较长时间，请重试或减少图像复杂度'
      });
    } else {
      res.json({
        ok: false,
        error_type: 'unknown',
        error: err.message
      });
    }
  }
});

// 混元3D服务健康检查
app.get('/api/hunyuan/status', async (req, res) => {
  try {
    const response = await axios.get(HUNYUAN_BASE_URL + '/health', { timeout: 5000 });
    res.json({
      ok: true,
      running: response.data?.model_loaded || false,
      model_loaded: response.data?.model_loaded || false,
      ...response.data
    });
  } catch (err) {
    res.json({
      ok: false,
      running: false,
      model_loaded: false,
      error: '服务未运行或无法连接'
    });
  }
});

// 预热混元3D模型
app.post('/api/hunyuan/warmup', async (req, res) => {
  try {
    const response = await axios.post(
      HUNYUAN_BASE_URL + '/load-models',
      {},
      { timeout: 600000 }
    );
    res.json(response.data);
  } catch (err) {
    res.json({
      ok: false,
      error: err.message
    });
  }
});

// v3.4.4: 自动启动混元3D服务（勾选启用时自动 spawn python3 进程）
let _hunyuan3dProcess = null;
app.post('/api/hunyuan/start', async (req, res) => {
  // 1) 先检查是否已经在运行
  try {
    const check = await axios.get(HUNYUAN_BASE_URL + '/health', { timeout: 3000 });
    if (check.data) {
      return res.json({
        ok: true,
        already_running: true,
        model_loaded: check.data.model_loaded || false,
        message: '混元3D服务已在运行中' + (check.data.model_loaded ? '（模型已加载）' : '（模型未加载，首次调用时会自动加载）')
      });
    }
  } catch (e) { /* 未运行，继续启动 */ }

  if (!ENABLE_HUNYUAN_AUTOSTART) {
    return res.status(403).json({
      ok: false,
      disabled: true,
      error: '销售版保留混元3D接口，但不内置启动混元服务',
      hint: `请用户自行部署混元3D服务，并通过 HUNYUAN_BASE_URL 指向服务地址。当前地址: ${HUNYUAN_BASE_URL}`
    });
  }

  const hunyuanPort = getHunyuanPort();
  try {
    const occupiedPids = await findListeningPids(hunyuanPort);
    if (occupiedPids.length > 0) {
      console.warn(`[hunyuan3d/start] /health 不可用，但端口 ${hunyuanPort} 被占用，准备清理僵尸进程: ${occupiedPids.join(', ')}`);
      const killedPids = await killListeningPids(hunyuanPort);
      console.warn(`[hunyuan3d/start] 已清理端口 ${hunyuanPort}: ${killedPids.join(', ') || '无'}`);
    }
  } catch (portErr) {
    console.warn(`[hunyuan3d/start] 端口 ${hunyuanPort} 自检失败: ${portErr.message}`);
  }

  // 2) 找到 hunyuan3d_service.py 的路径
  // 优先从 app 资源目录找（打包后），其次从项目目录找（开发时）
  let scriptPath = '';
  const candidates = [
    path.join(process.resourcesPath || '', '3d', 'hunyuan3d_service.py'),
    path.join(__dirname, '3d', 'hunyuan3d_service.py'),
    path.join(__dirname, '..', '3d', 'hunyuan3d_service.py'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) { scriptPath = c; break; }
  }
  if (!scriptPath) {
    return res.json({
      ok: false,
      error: '找不到 hunyuan3d_service.py',
      hint: '请确认 3d/hunyuan3d_service.py 文件存在',
      searched: candidates
    });
  }

  // 关键修复：如果 scriptPath 在 app.asar 内（Electron 虚拟文件系统），
  // Python 无法直接执行 asar 内的文件，必须先复制到临时目录
  if (scriptPath.includes('app.asar')) {
    const tmpScript = path.join(os.tmpdir(), 'aichat_hunyuan3d_service.py');
    try {
      const content = fs.readFileSync(scriptPath, 'utf-8');
      fs.writeFileSync(tmpScript, content, 'utf-8');
      console.log(`[hunyuan3d/start] 脚本在 app.asar 内，已复制到: ${tmpScript}`);
      scriptPath = tmpScript;
    } catch (cpErr) {
      return res.json({
        ok: false,
        error: '无法从 app.asar 复制脚本到临时目录: ' + cpErr.message,
        hint: '请尝试手动运行: python3 /path/to/hunyuan3d_service.py'
      });
    }
  }

  // 3) 找到 Python 虚拟环境（如果有）或系统 python3
  // 硬编码优先查找 ai-chat/3d/hunyuan3d-env/bin/python3（用户已创建的虚拟环境）
  let pythonCmd = 'python3';
  const venvCandidates = [
    path.join(os.homedir(), 'Desktop', 'ai-chat', '3d', 'hunyuan3d-env', 'bin', 'python3'),
    path.join(__dirname, '..', '3d', 'hunyuan3d-env', 'bin', 'python3'),
    path.join(__dirname, '3d', 'hunyuan3d-env', 'bin', 'python3'),
  ];
  for (const v of venvCandidates) {
    if (fs.existsSync(v)) { pythonCmd = v; break; }
  }

  // 4) spawn 子进程
  console.log(`[hunyuan3d/start] 启动: ${pythonCmd} ${scriptPath}`);
  try {
    if (_hunyuan3dProcess && !_hunyuan3dProcess.killed) {
      try { _hunyuan3dProcess.kill(); } catch (e) {}
    }

    // cwd 必须是真实磁盘目录（不能是 app.asar 内部路径 / .py 文件路径）
    // 优先用 ai-chat/3d/ 目录，其次 os.tmpdir()
    let spawnCwd = path.join(os.homedir(), 'Desktop', 'ai-chat', '3d');
    if (!fs.existsSync(spawnCwd)) {
      spawnCwd = path.dirname(scriptPath);
      try { if (!fs.statSync(spawnCwd).isDirectory()) spawnCwd = os.tmpdir(); } catch(e) { spawnCwd = os.tmpdir(); }
    }
    const child = spawn(pythonCmd, [scriptPath], {
      cwd: spawnCwd,
      env: { ...process.env },
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false
    });

    _hunyuan3dProcess = child;
    let startupLog = '';
    let childExitInfo = null;
    let resolveChildExit;
    const childExitPromise = new Promise(resolve => { resolveChildExit = resolve; });

    child.stdout.on('data', (data) => {
      const s = data.toString();
      startupLog += s;
      console.log('[hunyuan3d] ' + s.trim());
    });
    child.stderr.on('data', (data) => {
      const s = data.toString();
      startupLog += s;
      // Flask 输出到 stderr 是正常的
      if (s.includes('Running on') || s.includes('WARNING')) {
        console.log('[hunyuan3d] ' + s.trim());
      } else {
        console.error('[hunyuan3d-err] ' + s.trim());
      }
    });
    child.on('error', (err) => {
      console.error('[hunyuan3d] 进程启动失败:', err.message);
      _hunyuan3dProcess = null;
    });
    child.on('exit', (code, signal) => {
      console.log('[hunyuan3d] 进程退出, code=' + code);
      _hunyuan3dProcess = null;
      childExitInfo = { code, signal: signal || null };
      if (resolveChildExit) resolveChildExit(childExitInfo);
    });

    // 5) 等待服务可用（最多 15 秒轮询 /health）
    let ready = false;
    for (let i = 0; i < 30; i++) {
      await Promise.race([
        new Promise(r => setTimeout(r, 500)),
        childExitPromise
      ]);
      if (childExitInfo) break;
      try {
        const h = await axios.get(HUNYUAN_BASE_URL + '/health', { timeout: 2000 });
        if (h.data) { ready = true; break; }
      } catch (e) { /* 还没起来 */ }
    }

    if (ready) {
      res.json({
        ok: true,
        already_running: false,
        started: true,
        python: pythonCmd,
        script: scriptPath,
        pid: child.pid,
        message: '✅ 混元3D服务已成功启动（端口 8767）。首次调用 generate_3d_model 时会自动加载模型（约需 1-2 分钟）。'
      });
    } else {
      res.json({
        ok: false,
        started: true,
        pid: child.pid,
        exit_code: childExitInfo ? childExitInfo.code : null,
        exit_signal: childExitInfo ? childExitInfo.signal : null,
        startup_log: startupLog.substring(0, 5000),
        error: childExitInfo
          ? `服务进程已退出（code=${childExitInfo.code}${childExitInfo.signal ? ', signal=' + childExitInfo.signal : ''}）`
          : '服务进程已启动但 15 秒内未就绪',
        hint: startupLog.trim()
          ? ''
          : '启动日志为空。请手动运行 python3 3d/hunyuan3d_service.py 查看终端输出，或检查端口 8767 是否仍被占用。'
      });
    }
  } catch (err) {
    res.json({
      ok: false,
      error: '启动进程失败: ' + err.message,
      hint: pythonCmd === 'python3'
        ? '未找到虚拟环境，使用系统 python3。如果报错请先安装依赖。'
        : '使用虚拟环境: ' + pythonCmd
    });
  }
});

// v3.4.4: 停止混元3D服务
// v3.8.1：统一的混元3D子进程清理（/api/hunyuan/stop 与 app 退出/信号共用，根治孤儿残留）
function stopHunyuan3d() {
  if (_hunyuan3dProcess) {
    try { _hunyuan3dProcess.kill('SIGKILL'); } catch (e) {}
  }
  _hunyuan3dProcess = null;
}

app.post('/api/hunyuan/stop', (req, res) => {
  const wasRunning = !!(_hunyuan3dProcess && !_hunyuan3dProcess.killed);
  stopHunyuan3d();
  res.json({ ok: true, message: wasRunning ? '混元3D服务已停止' : '服务未在运行' });
});

// v3.8.1：统一退出清理（混元3D + PS bridge），根治 app 退出 / Ctrl+C 后子进程孤儿残留
function cleanupOnExit() {
  _psBridgeShutdown = true;  // 阻止 PS bridge exit handler 的 3 秒自动重启
  try { if (psBridgeProcess) { psBridgeProcess.kill('SIGKILL'); psBridgeProcess = null; } } catch (e) {}
  stopHunyuan3d();
}

// 命令行运行（node server.js）时，Ctrl+C / kill 也清理子进程
process.on('SIGINT', () => { try { cleanupOnExit(); } catch (e) {} process.exit(0); });
process.on('SIGTERM', () => { try { cleanupOnExit(); } catch (e) {} process.exit(0); });


// 自动选择可用端口启动（端口被占用时顺延，最多尝试 20 个）
function startServer(preferredPort = 3456, maxTries = 20) {


  return new Promise((resolve, reject) => {
    let port = preferredPort;
    let tries = 0;

    const tryListen = () => {
      const server = app.listen(port, () => {
        console.log(`\n✅ AI多轮对话系统已启动！`);
        console.log(`📌 请在浏览器打开: http://localhost:${port}`);
        console.log(`按 Ctrl+C 停止服务\n`);
        resolve({ port, server });
      });

      server.on('error', (err) => {
        if (err.code === 'EADDRINUSE' && tries < maxTries) {
          tries++;
          port++;
          console.warn(`⚠️ 端口被占用，尝试新端口 ${port} ...`);
          setTimeout(tryListen, 50);
        } else {
          reject(err);
        }
      });
    };

    tryListen();
  });
}

// 直接 node server.js 启动时立刻监听
if (require.main === module) {
  startServer().catch((err) => {
    console.error('❌ 服务器启动失败:', err);
    process.exit(1);
  });
}

module.exports = { app, startServer, stopHunyuan3d, cleanupOnExit };
