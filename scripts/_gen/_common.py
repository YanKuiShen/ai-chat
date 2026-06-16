#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.1 H-Hotfix5：批次模板生成器公共工具
- 把一批 templates（list of dict）append 到 scripts/bmesh-templates.json 的 templates 数组
- 自动按 name 去重（同名 → 用新版覆盖）
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BMESH_PATH = os.path.join(ROOT, 'bmesh-templates.json')
CHEAT_PATH = os.path.join(ROOT, 'bpy-cheatsheet.json')


def load_templates():
    with open(BMESH_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_templates(data):
    with open(BMESH_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_templates(new_list, batch_label=''):
    data = load_templates()
    existing = {t['name']: i for i, t in enumerate(data['templates'])}
    added, replaced = 0, 0
    for tpl in new_list:
        nm = tpl['name']
        if nm in existing:
            data['templates'][existing[nm]] = tpl
            replaced += 1
        else:
            data['templates'].append(tpl)
            added += 1
    save_templates(data)
    total = len(data['templates'])
    print(f"[{batch_label}] +{added} new / ~{replaced} replaced  →  total = {total}")
    return total


def load_cheat():
    with open(CHEAT_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_cheat(data):
    with open(CHEAT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_cheat(entries, batch_label=''):
    data = load_cheat()
    existing_ids = {e['id']: i for i, e in enumerate(data['entries'])}
    added, replaced = 0, 0
    for e in entries:
        if e['id'] in existing_ids:
            data['entries'][existing_ids[e['id']]] = e
            replaced += 1
        else:
            data['entries'].append(e)
            added += 1
    save_cheat(data)
    total = len(data['entries'])
    print(f"[{batch_label}] +{added} new / ~{replaced} replaced  →  cheat total = {total}")
    return total


# ============ 模板代码片段公用 helper ============

# 给所有模板注入的 try/except 头/尾（单点失败不阻断），加上 Blender 3.x/4.x 自发光双兼容
HEADER = '''import bpy, math
try:
'''

FOOTER = '''
except Exception as _e:
    import traceback
    print("[apply_template] 失败：" + str(_e))
    traceback.print_exc()
'''


def wrap(body_code):
    """把 body 缩进 4 空格塞进 try/except 块。注意：body 必须用 4 空格起始缩进，因为它会被再缩 4 空格。
    简化：body 已经写好不带 try 的版本，自动 indent 4 空格。
    """
    indented = '\n'.join(('    ' + ln if ln.strip() else '') for ln in body_code.split('\n'))
    return HEADER + indented + FOOTER
