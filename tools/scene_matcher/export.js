#!/usr/bin/env node
// 把 data.js 里的 88 条特征向量导出成：
//   1) public/scene_features.json   —— 前端 fetch 加载
//   2) tools/scene_matcher/features_table.md  —— 给人看的 Markdown 表
'use strict';

const fs = require('fs');
const path = require('path');
const { FEATURE_KEYS, FEATURE_LABELS, ENTRIES } = require('./data');

const ROOT = path.resolve(__dirname, '..', '..');
const JSON_OUT = path.join(ROOT, 'public', 'scene_features.json');
const MD_OUT = path.join(__dirname, 'features_table.md');

// 1) JSON 导出（前端 fetch）
const payload = {
  version: 'v2.1.0',
  generated_at: new Date().toISOString(),
  feature_keys: FEATURE_KEYS,
  feature_labels: FEATURE_LABELS,
  total: ENTRIES.length,
  templates: ENTRIES
};
fs.writeFileSync(JSON_OUT, JSON.stringify(payload, null, 2), 'utf8');
console.log(`✓ JSON → ${JSON_OUT} (${ENTRIES.length} 条 · ${(fs.statSync(JSON_OUT).size/1024).toFixed(1)} KB)`);

// 2) Markdown 表
const headers = ['编号', '模板 name', '中文标题', '类别', ...FEATURE_KEYS.map(k => FEATURE_LABELS[k])];
const lines = [
  '# 场景模板特征向量表（v2.1.0）',
  '',
  `共 **${ENTRIES.length}** 条 · 生成于 ${new Date().toISOString()}`,
  '',
  '> 所有维度取值 0~1。数值越大代表该特征越强。color_warm: 0=冰冷 / 0.5=中性 / 1=暖。',
  '',
  '| ' + headers.join(' | ') + ' |',
  '|' + headers.map(() => '---').join('|') + '|'
];
ENTRIES.forEach(e => {
  const row = [e.id, '`' + e.name + '`', e.title_zh, e.category, ...FEATURE_KEYS.map(k => e.features[k].toFixed(2))];
  lines.push('| ' + row.join(' | ') + ' |');
});
lines.push('', `生成命令：\`node tools/scene_matcher/export.js\``);
fs.writeFileSync(MD_OUT, lines.join('\n'), 'utf8');
console.log(`✓ MD   → ${MD_OUT}`);
