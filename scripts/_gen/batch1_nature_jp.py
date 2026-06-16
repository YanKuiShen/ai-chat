#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.1 H-Hotfix5 批 1：自然 14 + 日式 10 = 24 个模板
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import append_templates

TEMPLATES = []

# ============================================================
# 自然场景（14 个）
# ============================================================

# 1. terrain_displace ⭐ 崎岖地面
TEMPLATES.append({
    "name": "terrain_displace",
    "title": "崎岖地面（Plane subdivide + Displace Voronoi）",
    "category": "nature",
    "description": "大面积 plane subdivide 100×100 + Displace Voronoi 噪波位移 + Subsurf 平滑 + 岩石/草地 PBR 材质。AI 反复造不出复杂地面的根本药。",
    "params": [
        {"name": "name",      "type": "string", "default": "Terrain",   "description": "对象名"},
        {"name": "location",  "type": "vec3",   "default": [0, 0, 0],   "description": "中心位置"},
        {"name": "size",      "type": "float",  "default": 30.0,        "description": "地面边长（米）"},
        {"name": "subdiv",    "type": "int",    "default": 100,         "description": "细分次数"},
        {"name": "strength",  "type": "float",  "default": 1.5,         "description": "位移强度（米）"},
        {"name": "tex_scale", "type": "float",  "default": 4.0,         "description": "Voronoi 缩放（越大越细碎）"},
        {"name": "color",     "type": "rgb",    "default": [0.45, 0.40, 0.32], "description": "基础色（土黄）"},
        {"name": "kind",      "type": "string", "default": "rocky",     "description": "类型：rocky / grass / sand / snow"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _SIZE = float({{size}})\n    _SUB = int({{subdiv}})\n    _STR = float({{strength}})\n    _TS = float({{tex_scale}})\n    _COL = {{color|json}}\n    _KIND = {{kind|json}}\n\n    bpy.ops.mesh.primitive_plane_add(size=_SIZE, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    # subdivide\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    cuts = max(1, min(_SUB, 200))\n    # 分批 subdivide（一次太多会卡）\n    while cuts > 50:\n        bpy.ops.mesh.subdivide(number_cuts=50)\n        cuts -= 50\n    if cuts > 0:\n        bpy.ops.mesh.subdivide(number_cuts=cuts)\n    bpy.ops.object.mode_set(mode='OBJECT')\n\n    # Voronoi 噪波纹理 + Displace\n    tex = bpy.data.textures.new(_NAME + '_disp_tex', 'VORONOI')\n    tex.noise_scale = max(0.05, _SIZE / max(1.0, _TS) / 10.0)\n    tex.distance_metric = 'DISTANCE_SQUARED'\n    dm = obj.modifiers.new('Displace', 'DISPLACE')\n    dm.texture = tex\n    dm.strength = _STR\n    dm.mid_level = 0.5\n    # 第二层 Noise 让细节更碎\n    tex2 = bpy.data.textures.new(_NAME + '_disp2', 'CLOUDS')\n    tex2.noise_scale = 0.5\n    dm2 = obj.modifiers.new('Displace2', 'DISPLACE')\n    dm2.texture = tex2\n    dm2.strength = _STR * 0.3\n\n    sub = obj.modifiers.new('Sub', 'SUBSURF')\n    sub.levels = 1; sub.render_levels = 2\n    bpy.ops.object.shade_smooth()\n\n    # 材质（按 kind 选色）\n    color_map = {'grass': (0.18, 0.45, 0.15), 'sand': (0.85, 0.75, 0.55), 'snow': (0.92, 0.94, 0.97), 'rocky': tuple(_COL)}\n    base_c = color_map.get(_KIND, tuple(_COL))\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    nt = mat.node_tree\n    bsdf = nt.nodes.get('Principled BSDF') or nt.nodes.new('ShaderNodeBsdfPrincipled')\n    if 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (base_c[0], base_c[1], base_c[2], 1.0)\n    if 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.85 if _KIND != 'snow' else 0.5\n    # 噪波着色（土地有色差）\n    noise = nt.nodes.new('ShaderNodeTexNoise')\n    noise.inputs['Scale'].default_value = 8.0\n    cr = nt.nodes.new('ShaderNodeValToRGB')\n    cr.color_ramp.elements[0].color = (base_c[0]*0.7, base_c[1]*0.7, base_c[2]*0.7, 1)\n    cr.color_ramp.elements[1].color = (base_c[0]*1.15, base_c[1]*1.15, base_c[2]*1.15, 1)\n    nt.links.new(noise.outputs['Fac'], cr.inputs['Fac'])\n    nt.links.new(cr.outputs['Color'], bsdf.inputs['Base Color'])\n    obj.data.materials.append(mat)\n    print('[apply_template] terrain_displace 完成: ' + _NAME + ' size=' + str(_SIZE) + 'm subdiv=' + str(_SUB) + ' kind=' + _KIND)\nexcept Exception as _e:\n    import traceback; print('[apply_template] terrain_displace 失败:', _e); traceback.print_exc()\n"
})

# 2. mountain_layered 远景分层山脉
TEMPLATES.append({
    "name": "mountain_layered",
    "title": "远景分层山脉（多层 Plane + Displace + 透视错位）",
    "category": "nature",
    "description": "用 3 层渐变颜色的 Plane（subdivide + Displace Noise）按 Y 方向远近排列，做背景远山。靠雾色叠色营造层次感。",
    "params": [
        {"name": "name",     "type": "string", "default": "Mountains", "description": "对象名前缀"},
        {"name": "location", "type": "vec3",   "default": [0, 30, 0],  "description": "山脉中心"},
        {"name": "layers",   "type": "int",    "default": 3,           "description": "山脉层数（2~4）"},
        {"name": "width",    "type": "float",  "default": 80.0,        "description": "山脉宽度（米）"},
        {"name": "max_height", "type": "float", "default": 8.0,        "description": "最近山脉高度（米）"},
        {"name": "base_color", "type": "rgb",  "default": [0.30, 0.40, 0.50], "description": "最近山脉色（远山会渐变成天空色）"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _N = max(2, min(int({{layers}}), 4))\n    _W = float({{width}})\n    _MH = float({{max_height}})\n    _BC = {{base_color|json}}\n\n    parts = []\n    for i in range(_N):\n        t = i / max(1, _N - 1)\n        y_off = i * (_W * 0.15)\n        h = _MH * (1.0 - t * 0.5)\n        bpy.ops.mesh.primitive_plane_add(size=_W, location=(_LOC[0], _LOC[1] + y_off, _LOC[2]))\n        m = bpy.context.object; m.name = _NAME + '_layer' + str(i + 1)\n        m.rotation_euler = (math.radians(90), 0, 0)\n        m.scale = (1.0, h / _W, 1.0)\n        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)\n        # subdivide\n        bpy.ops.object.mode_set(mode='EDIT')\n        bpy.ops.mesh.select_all(action='SELECT')\n        bpy.ops.mesh.subdivide(number_cuts=30)\n        bpy.ops.object.mode_set(mode='OBJECT')\n        tex = bpy.data.textures.new(_NAME + '_t' + str(i), 'CLOUDS')\n        tex.noise_scale = 1.5\n        dm = m.modifiers.new('Displace', 'DISPLACE')\n        dm.texture = tex\n        dm.strength = h * 1.5\n        dm.direction = 'Y'\n        # 颜色：越远越偏蓝灰（雾色）\n        c = (_BC[0] * (1 - t) + 0.65 * t, _BC[1] * (1 - t) + 0.72 * t, _BC[2] * (1 - t) + 0.80 * t)\n        mat = bpy.data.materials.new(_NAME + '_m' + str(i))\n        mat.use_nodes = True\n        bsdf = mat.node_tree.nodes.get('Principled BSDF')\n        if bsdf and 'Base Color' in bsdf.inputs:\n            bsdf.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1.0)\n        if bsdf and 'Roughness' in bsdf.inputs:\n            bsdf.inputs['Roughness'].default_value = 0.95\n        m.data.materials.append(mat)\n        parts.append(m)\n    print('[apply_template] mountain_layered 完成: ' + str(len(parts)) + ' 层远山')\nexcept Exception as _e:\n    import traceback; print('[apply_template] mountain_layered 失败:', _e); traceback.print_exc()\n"
})

# 3. volumetric_clouds ⭐ 体积云朵
TEMPLATES.append({
    "name": "volumetric_clouds",
    "title": "体积云朵（Cube domain + Principled Volume + Noise）",
    "category": "nature",
    "description": "用一个大 Cube domain + Principled Volume + Noise + ColorRamp 形成蓬松云朵效果。Cycles 必备，EEVEE Next 也支持体积。",
    "params": [
        {"name": "name",     "type": "string", "default": "Clouds",     "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 15.0], "description": "云层中心高度"},
        {"name": "size",     "type": "float",  "default": 40.0,         "description": "云层 domain 边长 X/Y"},
        {"name": "thickness","type": "float",  "default": 5.0,          "description": "云层厚度 Z"},
        {"name": "density",  "type": "float",  "default": 0.5,          "description": "云密度（0.1~2.0）"},
        {"name": "tex_scale","type": "float",  "default": 1.5,          "description": "Noise 缩放（越大云越细碎）"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _T = float({{thickness}})\n    _D = float({{density}})\n    _TS = float({{tex_scale}})\n\n    bpy.ops.mesh.primitive_cube_add(size=1, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    obj.scale = (_S, _S, _T)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    obj.display_type = 'WIRE'   # 视口里 domain 显示成线框\n    obj.hide_render = False\n\n    mat = bpy.data.materials.new(_NAME + '_vol_mat')\n    mat.use_nodes = True\n    nt = mat.node_tree\n    # 清空默认节点\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (600, 0)\n    pv = nt.nodes.new('ShaderNodeVolumePrincipled'); pv.location = (300, 0)\n    if 'Density' in pv.inputs:\n        pv.inputs['Density'].default_value = _D\n    if 'Anisotropy' in pv.inputs:\n        pv.inputs['Anisotropy'].default_value = 0.3\n    if 'Color' in pv.inputs:\n        pv.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)\n    # Noise → ColorRamp → Density 接入\n    coord = nt.nodes.new('ShaderNodeTexCoord'); coord.location = (-700, 0)\n    map_n = nt.nodes.new('ShaderNodeMapping'); map_n.location = (-500, 0)\n    map_n.inputs['Scale'].default_value = (_TS, _TS, _TS)\n    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.location = (-300, 0)\n    noise.inputs['Scale'].default_value = 2.0\n    noise.inputs['Detail'].default_value = 4.0\n    noise.inputs['Roughness'].default_value = 0.7\n    cr = nt.nodes.new('ShaderNodeValToRGB'); cr.location = (0, 0)\n    cr.color_ramp.elements[0].position = 0.4\n    cr.color_ramp.elements[0].color = (0, 0, 0, 1)\n    cr.color_ramp.elements[1].position = 0.7\n    cr.color_ramp.elements[1].color = (1, 1, 1, 1)\n    nt.links.new(coord.outputs['Generated'], map_n.inputs['Vector'])\n    nt.links.new(map_n.outputs['Vector'], noise.inputs['Vector'])\n    nt.links.new(noise.outputs['Fac'], cr.inputs['Fac'])\n    nt.links.new(cr.outputs['Color'], pv.inputs['Density'])\n    nt.links.new(pv.outputs['Volume'], out.inputs['Volume'])\n    obj.data.materials.append(mat)\n    print('[apply_template] volumetric_clouds 完成: domain ' + str(_S) + 'x' + str(_S) + 'x' + str(_T))\nexcept Exception as _e:\n    import traceback; print('[apply_template] volumetric_clouds 失败:', _e); traceback.print_exc()\n"
})

# 4. sky_nishita ⭐ NISHITA 大气天空 + 5 个时段
TEMPLATES.append({
    "name": "sky_nishita",
    "title": "真实大气天空（World Sky NISHITA + 5 个时段预设）",
    "category": "nature",
    "description": "替换 World 的环境为 ShaderNodeTexSky（sky_type='NISHITA' 真实瑞利散射），time_preset 可选 noon/sunset/dawn/dusk/night。是『二次元蓝天』的标准答案。",
    "params": [
        {"name": "time_preset", "type": "string", "default": "noon", "description": "时段：noon（正午）/ sunset（黄昏）/ dawn（黎明）/ dusk（傍晚）/ night（夜空，月光）"},
        {"name": "strength",    "type": "float",  "default": 1.0,    "description": "天空强度倍数"},
        {"name": "sun_rotation","type": "float",  "default": 135.0,  "description": "太阳方位角（度）"}
    ],
    "code": "import bpy, math\ntry:\n    _PRESET = {{time_preset|json}}\n    _STR = float({{strength}})\n    _ROT = float({{sun_rotation}})\n\n    # NISHITA 是 ShaderNodeTexSky 的 sky_type 枚举，合法值仅限 NISHITA / PREETHAM / HOSEK_WILKIE\n    # 不要把 NISHITA 塞到 phase_function（那是其它东西的）\n    presets = {\n        'noon':   {'elev': 60.0,  'intensity': 1.0, 'air': 1.0, 'dust': 1.0,  'ozone': 1.0, 'strength_mul': 1.0},\n        'sunset': {'elev': 5.0,   'intensity': 0.7, 'air': 1.0, 'dust': 4.0,  'ozone': 1.0, 'strength_mul': 0.8},\n        'dawn':   {'elev': 3.0,   'intensity': 0.5, 'air': 1.0, 'dust': 3.0,  'ozone': 1.0, 'strength_mul': 0.6},\n        'dusk':   {'elev': -2.0,  'intensity': 0.3, 'air': 1.0, 'dust': 2.0,  'ozone': 1.0, 'strength_mul': 0.4},\n        'night':  {'elev': -25.0, 'intensity': 0.0, 'air': 1.0, 'dust': 1.0,  'ozone': 1.0, 'strength_mul': 0.05}\n    }\n    p = presets.get(_PRESET, presets['noon'])\n\n    world = bpy.context.scene.world\n    if not world:\n        world = bpy.data.worlds.new('World')\n        bpy.context.scene.world = world\n    world.use_nodes = True\n    nt = world.node_tree\n    # 清空老节点\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputWorld'); out.location = (400, 0)\n    bg = nt.nodes.new('ShaderNodeBackground'); bg.location = (200, 0)\n    bg.inputs['Strength'].default_value = _STR * p['strength_mul']\n    sky = nt.nodes.new('ShaderNodeTexSky'); sky.location = (-100, 0)\n    sky.sky_type = 'NISHITA'   # ★ 正确枚举值\n    try:\n        sky.sun_elevation = math.radians(p['elev'])\n        sky.sun_rotation = math.radians(_ROT)\n        sky.sun_intensity = p['intensity']\n        sky.air_density = p['air']\n        sky.dust_density = p['dust']\n        sky.ozone_density = p['ozone']\n    except AttributeError as _ae:\n        print('[sky_nishita] 部分属性不存在（可能 Blender 版本旧）:', _ae)\n    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])\n    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])\n\n    # 夜空兜底：叠一个深蓝色\n    if _PRESET == 'night':\n        bg.inputs['Color'].default_value = (0.02, 0.04, 0.10, 1.0)\n        # 把 sky 节点的输出断开（避免还是亮的）\n        for ln in list(nt.links):\n            if ln.from_node == sky:\n                nt.links.remove(ln)\n    print('[apply_template] sky_nishita 完成: preset=' + _PRESET + ' elev=' + str(p['elev']) + '°')\nexcept Exception as _e:\n    import traceback; print('[apply_template] sky_nishita 失败:', _e); traceback.print_exc()\n"
})

# 5. fog_volume 体积雾
TEMPLATES.append({
    "name": "fog_volume",
    "title": "体积雾（地面层 Cube domain + Volume Scatter）",
    "category": "nature",
    "description": "在地面 0~3m 范围内放一个大 Cube domain，里面填 Volume Scatter（白色低密度），制造神社夜景/晨雾的丁达尔效果。",
    "params": [
        {"name": "name",     "type": "string", "default": "Fog",       "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 1.5], "description": "雾层中心高度"},
        {"name": "size",     "type": "float",  "default": 40.0,        "description": "雾层 X/Y 边长（米）"},
        {"name": "thickness","type": "float",  "default": 3.0,         "description": "雾层 Z 厚度（米）"},
        {"name": "density",  "type": "float",  "default": 0.05,        "description": "雾密度（0.01~0.2）"},
        {"name": "color",    "type": "rgb",    "default": [1.0, 1.0, 1.0], "description": "雾颜色"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _T = float({{thickness}})\n    _D = float({{density}})\n    _C = {{color|json}}\n\n    bpy.ops.mesh.primitive_cube_add(size=1, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    obj.scale = (_S, _S, _T)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    obj.display_type = 'WIRE'\n\n    mat = bpy.data.materials.new(_NAME + '_fog_mat')\n    mat.use_nodes = True\n    nt = mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    out.location = (400, 0)\n    vs = nt.nodes.new('ShaderNodeVolumeScatter')\n    vs.location = (200, 0)\n    if 'Color' in vs.inputs:\n        vs.inputs['Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Density' in vs.inputs:\n        vs.inputs['Density'].default_value = _D\n    if 'Anisotropy' in vs.inputs:\n        vs.inputs['Anisotropy'].default_value = 0.0\n    nt.links.new(vs.outputs['Volume'], out.inputs['Volume'])\n    obj.data.materials.append(mat)\n    print('[apply_template] fog_volume 完成: density=' + str(_D))\nexcept Exception as _e:\n    import traceback; print('[apply_template] fog_volume 失败:', _e); traceback.print_exc()\n"
})

# 6. water_plane 水面
TEMPLATES.append({
    "name": "water_plane",
    "title": "水面（Plane + Subsurf + Wave 法线扰动 + Transmission）",
    "category": "nature",
    "description": "Plane 高细分 + Wave Texture 接 Normal，BSDF Transmission=1 / IOR=1.33 / Roughness=0.05。湖面/海面/水池都靠它。",
    "params": [
        {"name": "name",     "type": "string", "default": "Water",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "水面中心"},
        {"name": "size",     "type": "float",  "default": 10.0,      "description": "水面边长"},
        {"name": "color",    "type": "rgb",    "default": [0.05, 0.15, 0.20], "description": "水底色（深蓝绿）"},
        {"name": "wave_scale","type": "float", "default": 6.0,       "description": "波纹密度"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _C = {{color|json}}\n    _WS = float({{wave_scale}})\n\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    bpy.ops.mesh.subdivide(number_cuts=20)\n    bpy.ops.object.mode_set(mode='OBJECT')\n\n    mat = bpy.data.materials.new(_NAME + '_water_mat')\n    mat.use_nodes = True\n    nt = mat.node_tree\n    bsdf = nt.nodes.get('Principled BSDF') or nt.nodes.new('ShaderNodeBsdfPrincipled')\n    if 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.05\n    # 4.x: 'Transmission Weight' / 老版本: 'Transmission'\n    for key in ['Transmission Weight', 'Transmission']:\n        if key in bsdf.inputs:\n            bsdf.inputs[key].default_value = 1.0\n            break\n    if 'IOR' in bsdf.inputs:\n        bsdf.inputs['IOR'].default_value = 1.33\n    # Wave → Bump → BSDF Normal\n    wave = nt.nodes.new('ShaderNodeTexWave')\n    wave.wave_type = 'BANDS'\n    wave.inputs['Scale'].default_value = _WS\n    wave.inputs['Distortion'].default_value = 3.0\n    bump = nt.nodes.new('ShaderNodeBump')\n    bump.inputs['Strength'].default_value = 0.1\n    nt.links.new(wave.outputs['Fac'], bump.inputs['Height'])\n    if 'Normal' in bsdf.inputs:\n        nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])\n    obj.data.materials.append(mat)\n    print('[apply_template] water_plane 完成: ' + str(_S) + 'm × ' + str(_S) + 'm')\nexcept Exception as _e:\n    import traceback; print('[apply_template] water_plane 失败:', _e); traceback.print_exc()\n"
})

# 7. river_curve 蜿蜒河流
TEMPLATES.append({
    "name": "river_curve",
    "title": "蜿蜒河流（Bezier Curve + Mesh river + Solidify）",
    "category": "nature",
    "description": "用 Bezier 曲线手画一条 S 形河道，转 Mesh + Solidify 加厚成水体（再套水面材质）。",
    "params": [
        {"name": "name",     "type": "string", "default": "River",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0.02], "description": "河面中心 Z（略高于地面避免穿模）"},
        {"name": "length",   "type": "float",  "default": 20.0,      "description": "河流长度"},
        {"name": "width",    "type": "float",  "default": 2.0,       "description": "河流宽度"},
        {"name": "color",    "type": "rgb",    "default": [0.10, 0.30, 0.40], "description": "水色"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _L = float({{length}})\n    _W = float({{width}})\n    _C = {{color|json}}\n\n    # 用 Bezier 画一条 S 形\n    bpy.ops.curve.primitive_bezier_curve_add(location=_LOC)\n    cv = bpy.context.object; cv.name = _NAME + '_curve'\n    cv.data.dimensions = '2D'\n    cv.data.bevel_depth = _W * 0.5\n    cv.data.bevel_resolution = 4\n    cv.data.fill_mode = 'BOTH'\n    bp = cv.data.splines[0].bezier_points\n    bp[0].co = (-_L * 0.5, -_L * 0.2, 0)\n    bp[1].co = ( _L * 0.5,  _L * 0.2, 0)\n    bp[0].handle_left = (-_L * 0.7, -_L * 0.4, 0)\n    bp[0].handle_right = (-_L * 0.2, _L * 0.3, 0)\n    bp[1].handle_left = ( _L * 0.2, -_L * 0.3, 0)\n    bp[1].handle_right = ( _L * 0.7,  _L * 0.4, 0)\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    bsdf = mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf:\n        if 'Base Color' in bsdf.inputs:\n            bsdf.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n        if 'Roughness' in bsdf.inputs:\n            bsdf.inputs['Roughness'].default_value = 0.1\n        for key in ['Transmission Weight', 'Transmission']:\n            if key in bsdf.inputs:\n                bsdf.inputs[key].default_value = 0.8\n                break\n        if 'IOR' in bsdf.inputs:\n            bsdf.inputs['IOR'].default_value = 1.33\n    cv.data.materials.append(mat)\n    print('[apply_template] river_curve 完成: 长 ' + str(_L) + 'm 宽 ' + str(_W) + 'm')\nexcept Exception as _e:\n    import traceback; print('[apply_template] river_curve 失败:', _e); traceback.print_exc()\n"
})

# 8. waterfall 瀑布
TEMPLATES.append({
    "name": "waterfall",
    "title": "瀑布（Plane + 半透明水材质 + 粒子细线）",
    "category": "nature",
    "description": "竖直 Plane（带 Wave Distortion）+ 半透白水材质，下方加一个雾团 Cube 模拟水花。",
    "params": [
        {"name": "name",     "type": "string", "default": "Waterfall", "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0],   "description": "瀑布底中心"},
        {"name": "width",    "type": "float",  "default": 2.0,         "description": "瀑布宽"},
        {"name": "height",   "type": "float",  "default": 5.0,         "description": "瀑布高"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _W = float({{width}})\n    _H = float({{height}})\n\n    bpy.ops.mesh.primitive_plane_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] + _H * 0.5))\n    fall = bpy.context.object; fall.name = _NAME\n    fall.rotation_euler = (math.radians(90), 0, 0)\n    fall.scale = (_W, _H, 1.0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    bpy.ops.mesh.subdivide(number_cuts=8)\n    bpy.ops.object.mode_set(mode='OBJECT')\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    bsdf = mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf:\n        if 'Base Color' in bsdf.inputs:\n            bsdf.inputs['Base Color'].default_value = (0.85, 0.92, 1.0, 1.0)\n        if 'Roughness' in bsdf.inputs:\n            bsdf.inputs['Roughness'].default_value = 0.15\n        for key in ['Transmission Weight', 'Transmission']:\n            if key in bsdf.inputs:\n                bsdf.inputs[key].default_value = 0.7\n                break\n    mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else 'BLEND'\n    fall.data.materials.append(mat)\n\n    # 底部水花团\n    bpy.ops.mesh.primitive_uv_sphere_add(radius=_W * 0.6, location=(_LOC[0], _LOC[1], _LOC[2] + 0.1))\n    mist = bpy.context.object; mist.name = _NAME + '_mist'\n    mist.scale = (1.5, 1.5, 0.4)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bpy.ops.object.shade_smooth()\n    mat2 = bpy.data.materials.new(_NAME + '_mist_mat')\n    mat2.use_nodes = True\n    b2 = mat2.node_tree.nodes.get('Principled BSDF')\n    if b2:\n        if 'Base Color' in b2.inputs:\n            b2.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)\n        if 'Alpha' in b2.inputs:\n            b2.inputs['Alpha'].default_value = 0.3\n    mat2.blend_method = 'BLEND'\n    mist.data.materials.append(mat2)\n    print('[apply_template] waterfall 完成: ' + str(_W) + 'm × ' + str(_H) + 'm + 水花')\nexcept Exception as _e:\n    import traceback; print('[apply_template] waterfall 失败:', _e); traceback.print_exc()\n"
})

# 9. rock_voronoi 不规则岩石
TEMPLATES.append({
    "name": "rock_voronoi",
    "title": "不规则岩石（IcoSphere + Displace Voronoi + Decimate）",
    "category": "nature",
    "description": "ico_sphere(subdiv=3) + Displace（Voronoi 噪波） + Decimate 减面，得到棱角分明的天然岩石。可放 1~N 块。",
    "params": [
        {"name": "name",     "type": "string", "default": "Rock",    "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "岩石位置"},
        {"name": "size",     "type": "float",  "default": 0.5,       "description": "岩石半径（米）"},
        {"name": "color",    "type": "rgb",    "default": [0.35, 0.32, 0.28], "description": "岩石色"},
        {"name": "strength", "type": "float",  "default": 0.4,       "description": "Displace 强度（相对半径）"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _C = {{color|json}}\n    _STR = float({{strength}})\n\n    bpy.ops.mesh.primitive_ico_sphere_add(radius=_S, subdivisions=3, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    tex = bpy.data.textures.new(_NAME + '_tex', 'VORONOI')\n    tex.noise_scale = 0.5\n    dm = obj.modifiers.new('Displace', 'DISPLACE')\n    dm.texture = tex\n    dm.strength = _STR * _S\n    dec = obj.modifiers.new('Dec', 'DECIMATE')\n    dec.ratio = 0.5\n    bpy.ops.object.shade_smooth()\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    bsdf = mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf:\n        if 'Base Color' in bsdf.inputs:\n            bsdf.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n        if 'Roughness' in bsdf.inputs:\n            bsdf.inputs['Roughness'].default_value = 0.9\n    obj.data.materials.append(mat)\n    print('[apply_template] rock_voronoi 完成: r=' + str(_S) + ' strength=' + str(_STR))\nexcept Exception as _e:\n    import traceback; print('[apply_template] rock_voronoi 失败:', _e); traceback.print_exc()\n"
})

# 10. grass_field 草地
TEMPLATES.append({
    "name": "grass_field",
    "title": "草地（Plane + GN Distribute Points + Instance grass blade）",
    "category": "nature",
    "description": "底部 Plane + Geometry Nodes 散布草叶实例（小 plane 加 Cone scaled）。AI 反复造不出草地的根本药。",
    "params": [
        {"name": "name",     "type": "string", "default": "Grass",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "草地中心"},
        {"name": "size",     "type": "float",  "default": 10.0,      "description": "草地边长"},
        {"name": "density",  "type": "float",  "default": 200.0,     "description": "每平米草叶数"},
        {"name": "color",    "type": "rgb",    "default": [0.20, 0.55, 0.18], "description": "草地基色"},
        {"name": "blade_height", "type": "float", "default": 0.15,   "description": "草叶高度（米）"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _D = float({{density}})\n    _C = {{color|json}}\n    _BH = float({{blade_height}})\n\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=_LOC)\n    ground = bpy.context.object; ground.name = _NAME + '_ground'\n    g_mat = bpy.data.materials.new(_NAME + '_ground_mat')\n    g_mat.use_nodes = True\n    bsdf = g_mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (_C[0] * 0.7, _C[1] * 0.7, _C[2] * 0.7, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.95\n    ground.data.materials.append(g_mat)\n\n    # 草叶 proto（cone 倒立）\n    bpy.ops.mesh.primitive_cone_add(radius1=0.01, radius2=0.0, depth=_BH, vertices=4, location=(_LOC[0] + 100, 0, 0))\n    blade = bpy.context.object; blade.name = _NAME + '_blade'\n    blade.hide_render = True\n    blade.hide_viewport = True\n    b_mat = bpy.data.materials.new(_NAME + '_blade_mat')\n    b_mat.use_nodes = True\n    bsdf2 = b_mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf2 and 'Base Color' in bsdf2.inputs:\n        bsdf2.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if bsdf2 and 'Roughness' in bsdf2.inputs:\n        bsdf2.inputs['Roughness'].default_value = 0.85\n    blade.data.materials.append(b_mat)\n\n    mod = ground.modifiers.new('GN_Grass', 'NODES')\n    nt = bpy.data.node_groups.new(_NAME + '_GN', 'GeometryNodeTree')\n    mod.node_group = nt\n    try:\n        nt.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')\n        nt.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')\n    except Exception:\n        pass\n    g_in = nt.nodes.new('NodeGroupInput'); g_in.location = (-800, 0)\n    g_out = nt.nodes.new('NodeGroupOutput'); g_out.location = (800, 0)\n    dp = nt.nodes.new('GeometryNodeDistributePointsOnFaces'); dp.location = (-500, 0)\n    if 'Density' in dp.inputs:\n        dp.inputs['Density'].default_value = _D\n    ip = nt.nodes.new('GeometryNodeInstanceOnPoints'); ip.location = (-200, 0)\n    oi = nt.nodes.new('GeometryNodeObjectInfo'); oi.location = (-500, 200)\n    oi.inputs['Object'].default_value = blade\n    rand_rot = nt.nodes.new('FunctionNodeRandomValue'); rand_rot.location = (-500, -200)\n    rand_rot.data_type = 'FLOAT_VECTOR'\n    rand_rot.inputs['Min'].default_value = (0, 0, -math.pi)\n    rand_rot.inputs['Max'].default_value = (0, 0, math.pi)\n    rand_sc = nt.nodes.new('FunctionNodeRandomValue'); rand_sc.location = (-500, -400)\n    rand_sc.data_type = 'FLOAT'\n    rand_sc.inputs['Min'].default_value = 0.6\n    rand_sc.inputs['Max'].default_value = 1.3\n    ri = nt.nodes.new('GeometryNodeRealizeInstances'); ri.location = (100, 0)\n    jn = nt.nodes.new('GeometryNodeJoinGeometry'); jn.location = (400, 0)\n    nt.links.new(g_in.outputs[0], dp.inputs['Mesh'])\n    nt.links.new(dp.outputs['Points'], ip.inputs['Points'])\n    nt.links.new(oi.outputs['Geometry'], ip.inputs['Instance'])\n    nt.links.new(rand_rot.outputs['Value'], ip.inputs['Rotation'])\n    nt.links.new(rand_sc.outputs['Value'], ip.inputs['Scale'])\n    nt.links.new(ip.outputs['Instances'], ri.inputs['Geometry'])\n    nt.links.new(g_in.outputs[0], jn.inputs['Geometry'])\n    nt.links.new(ri.outputs['Geometry'], jn.inputs['Geometry'])\n    nt.links.new(jn.outputs['Geometry'], g_out.inputs[0])\n    print('[apply_template] grass_field 完成: ' + str(_S) + 'm² density=' + str(_D))\nexcept Exception as _e:\n    import traceback; print('[apply_template] grass_field 失败:', _e); traceback.print_exc()\n"
})

# 11. cherry_blossom_tree ⭐ 樱花树
TEMPLATES.append({
    "name": "cherry_blossom_tree",
    "title": "樱花树（Skin 树干 + IcoSphere 花球 + 粉色材质）",
    "category": "nature",
    "description": "用顶点骨架 + Skin modifier 生成树干树枝，顶端挂 3~5 个 IcoSphere 当樱花球（粉白 SSS 材质）。",
    "params": [
        {"name": "name",     "type": "string", "default": "Sakura",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "树底中心"},
        {"name": "height",   "type": "float",  "default": 4.0,       "description": "树整体高度"},
        {"name": "blossom_color", "type": "rgb", "default": [1.0, 0.78, 0.85], "description": "樱花色（粉白）"},
        {"name": "trunk_color",   "type": "rgb", "default": [0.30, 0.20, 0.15], "description": "树干色"}
    ],
    "code": "import bpy, math, random\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _H = float({{height}})\n    _BC = {{blossom_color|json}}\n    _TC = {{trunk_color|json}}\n\n    # 1. 树干（Skin）\n    me = bpy.data.meshes.new(_NAME + '_trunk_mesh')\n    obj = bpy.data.objects.new(_NAME + '_trunk', me)\n    bpy.context.collection.objects.link(obj)\n    obj.location = _LOC\n    import bmesh\n    bm = bmesh.new()\n    v0 = bm.verts.new((0, 0, 0))\n    v1 = bm.verts.new((0, 0, _H * 0.5))\n    bm.edges.new((v0, v1))\n    # 分支\n    branches = []\n    for i in range(5):\n        ang = i * math.pi * 2 / 5\n        bx = math.cos(ang) * _H * 0.25\n        by = math.sin(ang) * _H * 0.25\n        bz = _H * (0.7 + random.random() * 0.25)\n        vb = bm.verts.new((bx, by, bz))\n        bm.edges.new((v1, vb))\n        branches.append((bx, by, bz))\n    bm.to_mesh(me); bm.free()\n\n    sk = obj.modifiers.new('Skin', 'SKIN')\n    sk.use_smooth_shade = True\n    # 调粗细：root 粗，顶端细\n    for sv in obj.data.skin_vertices[0].data:\n        sv.radius = (0.12, 0.12)\n    # 最后几个分支顶点细一些\n    n_verts = len(obj.data.skin_vertices[0].data)\n    for idx in range(max(0, n_verts - 5), n_verts):\n        obj.data.skin_vertices[0].data[idx].radius = (0.04, 0.04)\n    sub = obj.modifiers.new('Sub', 'SUBSURF')\n    sub.levels = 2\n\n    trunk_mat = bpy.data.materials.new(_NAME + '_trunk_mat')\n    trunk_mat.use_nodes = True\n    bsdf = trunk_mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (_TC[0], _TC[1], _TC[2], 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.85\n    obj.data.materials.append(trunk_mat)\n\n    # 2. 樱花球（每个分支顶端）\n    blossom_mat = bpy.data.materials.new(_NAME + '_blossom_mat')\n    blossom_mat.use_nodes = True\n    bsdf2 = blossom_mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf2 and 'Base Color' in bsdf2.inputs:\n        bsdf2.inputs['Base Color'].default_value = (_BC[0], _BC[1], _BC[2], 1.0)\n    if bsdf2 and 'Roughness' in bsdf2.inputs:\n        bsdf2.inputs['Roughness'].default_value = 0.6\n\n    for (bx, by, bz) in branches:\n        bpy.ops.mesh.primitive_ico_sphere_add(radius=_H * 0.18, subdivisions=2, location=(_LOC[0] + bx, _LOC[1] + by, _LOC[2] + bz))\n        ball = bpy.context.object; ball.name = _NAME + '_blossom'\n        # 凹凸感\n        bt = bpy.data.textures.new(ball.name + '_tex', 'CLOUDS')\n        bt.noise_scale = 0.2\n        dm = ball.modifiers.new('Bump', 'DISPLACE')\n        dm.texture = bt\n        dm.strength = _H * 0.04\n        bpy.ops.object.shade_smooth()\n        ball.data.materials.append(blossom_mat)\n        ball.parent = obj\n        ball.matrix_parent_inverse = obj.matrix_world.inverted()\n    print('[apply_template] cherry_blossom_tree 完成: 树高 ' + str(_H) + 'm + ' + str(len(branches)) + ' 个花球')\nexcept Exception as _e:\n    import traceback; print('[apply_template] cherry_blossom_tree 失败:', _e); traceback.print_exc()\n"
})

# 12. bamboo_forest 竹林
TEMPLATES.append({
    "name": "bamboo_forest",
    "title": "竹林（Array 多根 cylinder + 关节段 + 随机高低）",
    "category": "nature",
    "description": "用 cylinder 做竹竿（带 Array 节段感）+ Empty 分布，做出一片简易竹林。",
    "params": [
        {"name": "name",     "type": "string", "default": "Bamboo",  "description": "对象名前缀"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "竹林中心"},
        {"name": "count",    "type": "int",    "default": 12,        "description": "竹竿数量"},
        {"name": "area",     "type": "float",  "default": 4.0,       "description": "分布半径"},
        {"name": "height",   "type": "float",  "default": 4.0,       "description": "平均竹竿高度"}
    ],
    "code": "import bpy, math, random\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _N = max(1, int({{count}}))\n    _A = float({{area}})\n    _H = float({{height}})\n\n    bamboo_mat = bpy.data.materials.new(_NAME + '_mat')\n    bamboo_mat.use_nodes = True\n    bsdf = bamboo_mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (0.45, 0.60, 0.30, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.6\n\n    parts = []\n    for i in range(_N):\n        ang = random.random() * math.pi * 2\n        r = random.random() * _A\n        x = _LOC[0] + math.cos(ang) * r\n        y = _LOC[1] + math.sin(ang) * r\n        h = _H * (0.7 + random.random() * 0.6)\n        bpy.ops.mesh.primitive_cylinder_add(radius=0.04 + random.random() * 0.02, depth=h, vertices=10, location=(x, y, _LOC[2] + h * 0.5))\n        c = bpy.context.object; c.name = _NAME + '_' + str(i + 1)\n        bpy.ops.object.shade_smooth()\n        # 用 Array 加几个节段（缩放微变）让有竹节感\n        bv = c.modifiers.new('Bevel', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.003; bv.segments = 2\n        c.data.materials.append(bamboo_mat)\n        parts.append(c)\n\n    bpy.ops.object.empty_add(type='PLAIN_AXES', location=_LOC)\n    root = bpy.context.object; root.name = _NAME + '_root'\n    for p in parts:\n        p.parent = root\n        p.matrix_parent_inverse = root.matrix_world.inverted()\n    print('[apply_template] bamboo_forest 完成: ' + str(len(parts)) + ' 根竹竿')\nexcept Exception as _e:\n    import traceback; print('[apply_template] bamboo_forest 失败:', _e); traceback.print_exc()\n"
})

# 13. forest_geonode 树林散布
TEMPLATES.append({
    "name": "forest_geonode",
    "title": "树林散布（Plane GN Distribute + 简易树 Instance）",
    "category": "nature",
    "description": "在 Plane 上用 GN 散布树原型（圆锥+圆柱组合的低模树），数量参数化。",
    "params": [
        {"name": "name",     "type": "string", "default": "Forest",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "森林中心"},
        {"name": "size",     "type": "float",  "default": 20.0,      "description": "Plane 边长"},
        {"name": "count",    "type": "int",    "default": 30,        "description": "树的数量"}
    ],
    "code": "import bpy, math, random\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _N = max(1, int({{count}}))\n\n    # 树原型（圆柱 + 圆锥）\n    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.8, location=(_LOC[0] + 100, 0, 0.4))\n    trunk = bpy.context.object; trunk.name = _NAME + '_tree_trunk'\n    bpy.ops.mesh.primitive_cone_add(radius1=0.6, radius2=0, depth=2.0, vertices=8, location=(_LOC[0] + 100, 0, 1.8))\n    leaves = bpy.context.object; leaves.name = _NAME + '_tree_leaves'\n    bpy.ops.object.select_all(action='DESELECT')\n    trunk.select_set(True); leaves.select_set(True)\n    bpy.context.view_layer.objects.active = leaves\n    bpy.ops.object.join()\n    tree = bpy.context.object; tree.name = _NAME + '_tree_proto'\n    tree.hide_render = True; tree.hide_viewport = True\n\n    # 材质\n    m1 = bpy.data.materials.new(_NAME + '_tree_mat')\n    m1.use_nodes = True\n    bsdf = m1.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (0.20, 0.45, 0.18, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.85\n    tree.data.materials.append(m1)\n\n    # 地面 plane + GN 散布\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=_LOC)\n    ground = bpy.context.object; ground.name = _NAME + '_ground'\n    mod = ground.modifiers.new('GN_Forest', 'NODES')\n    nt = bpy.data.node_groups.new(_NAME + '_GN', 'GeometryNodeTree')\n    mod.node_group = nt\n    try:\n        nt.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')\n        nt.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')\n    except Exception:\n        pass\n    g_in = nt.nodes.new('NodeGroupInput'); g_in.location = (-800, 0)\n    g_out = nt.nodes.new('NodeGroupOutput'); g_out.location = (800, 0)\n    dp = nt.nodes.new('GeometryNodeDistributePointsOnFaces'); dp.location = (-500, 0)\n    dens = max(0.05, float(_N) / max(1.0, _S * _S))\n    if 'Density' in dp.inputs:\n        dp.inputs['Density'].default_value = dens\n    ip = nt.nodes.new('GeometryNodeInstanceOnPoints'); ip.location = (-200, 0)\n    oi = nt.nodes.new('GeometryNodeObjectInfo'); oi.location = (-500, 200)\n    oi.inputs['Object'].default_value = tree\n    rs = nt.nodes.new('FunctionNodeRandomValue'); rs.location = (-500, -200)\n    rs.data_type = 'FLOAT'\n    rs.inputs['Min'].default_value = 0.7\n    rs.inputs['Max'].default_value = 1.5\n    ri = nt.nodes.new('GeometryNodeRealizeInstances'); ri.location = (100, 0)\n    jn = nt.nodes.new('GeometryNodeJoinGeometry'); jn.location = (400, 0)\n    nt.links.new(g_in.outputs[0], dp.inputs['Mesh'])\n    nt.links.new(dp.outputs['Points'], ip.inputs['Points'])\n    nt.links.new(oi.outputs['Geometry'], ip.inputs['Instance'])\n    nt.links.new(rs.outputs['Value'], ip.inputs['Scale'])\n    nt.links.new(ip.outputs['Instances'], ri.inputs['Geometry'])\n    nt.links.new(g_in.outputs[0], jn.inputs['Geometry'])\n    nt.links.new(ri.outputs['Geometry'], jn.inputs['Geometry'])\n    nt.links.new(jn.outputs['Geometry'], g_out.inputs[0])\n    print('[apply_template] forest_geonode 完成: ' + str(_S) + 'm² target=' + str(_N) + '棵 density=' + str(round(dens, 3)))\nexcept Exception as _e:\n    import traceback; print('[apply_template] forest_geonode 失败:', _e); traceback.print_exc()\n"
})

# 14. snowy_terrain 雪地
TEMPLATES.append({
    "name": "snowy_terrain",
    "title": "雪地（Plane + Displace 起伏 + 白色高 Subsurface 材质）",
    "category": "nature",
    "description": "雪地版的 terrain：起伏柔和 + 白色基底 + Subsurface 微泛蓝。",
    "params": [
        {"name": "name",     "type": "string", "default": "SnowField","description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0],  "description": "中心位置"},
        {"name": "size",     "type": "float",  "default": 20.0,       "description": "边长"},
        {"name": "strength", "type": "float",  "default": 0.6,        "description": "起伏强度（米）"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _STR = float({{strength}})\n\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    bpy.ops.mesh.subdivide(number_cuts=40)\n    bpy.ops.object.mode_set(mode='OBJECT')\n\n    tex = bpy.data.textures.new(_NAME + '_tex', 'CLOUDS')\n    tex.noise_scale = 1.5\n    dm = obj.modifiers.new('Displace', 'DISPLACE')\n    dm.texture = tex\n    dm.strength = _STR\n    sub = obj.modifiers.new('Sub', 'SUBSURF')\n    sub.levels = 1\n    bpy.ops.object.shade_smooth()\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    bsdf = mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (0.93, 0.95, 0.98, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.4\n    # SSS 让雪有半透感\n    for key in ['Subsurface Weight', 'Subsurface']:\n        if key in bsdf.inputs:\n            bsdf.inputs[key].default_value = 0.3\n            break\n    if 'Subsurface Radius' in bsdf.inputs:\n        bsdf.inputs['Subsurface Radius'].default_value = (0.3, 0.4, 0.6)\n    obj.data.materials.append(mat)\n    print('[apply_template] snowy_terrain 完成: ' + str(_S) + 'm')\nexcept Exception as _e:\n    import traceback; print('[apply_template] snowy_terrain 失败:', _e); traceback.print_exc()\n"
})


# ============================================================
# 日式二次元（10 个）
# ============================================================

# 15. torii_gate ⭐ 鸟居
TEMPLATES.append({
    "name": "torii_gate",
    "title": "鸟居（2 立柱 + 笠木 + 岛木，朱红漆色）",
    "category": "japanese",
    "description": "标准明神鸟居：2 根 cylinder 立柱（朱红） + 顶部笠木（横向贯通带翘角） + 岛木（短横） + 额束。",
    "params": [
        {"name": "name",     "type": "string", "default": "Torii",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "鸟居底中心"},
        {"name": "height",   "type": "float",  "default": 4.0,       "description": "鸟居整体高"},
        {"name": "width",    "type": "float",  "default": 3.5,       "description": "立柱间距"},
        {"name": "color",    "type": "rgb",    "default": [0.78, 0.10, 0.08], "description": "朱红色"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _H = float({{height}})\n    _W = float({{width}})\n    _C = {{color|json}}\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    bsdf = mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.4\n\n    parts = []\n    # 立柱 ×2\n    pillar_r = _H * 0.05\n    for sx in [-1, 1]:\n        bpy.ops.mesh.primitive_cylinder_add(radius=pillar_r, depth=_H, vertices=24, location=(_LOC[0] + sx * _W * 0.5, _LOC[1], _LOC[2] + _H * 0.5))\n        c = bpy.context.object; c.name = _NAME + '_pillar_' + ('R' if sx > 0 else 'L')\n        bpy.ops.object.shade_smooth()\n        parts.append(c)\n\n    # 笠木（顶部横梁，比立柱间距长一些，两端翘起用 cube 简化）\n    kasagi_y = pillar_r * 1.2\n    kasagi_z = _H * 0.05\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] + _H + kasagi_z))\n    kasagi = bpy.context.object; kasagi.name = _NAME + '_kasagi'\n    kasagi.scale = (_W + _H * 0.4, kasagi_y * 2, kasagi_z * 2)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bv = kasagi.modifiers.new('Bev', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.02; bv.segments = 2\n    parts.append(kasagi)\n\n    # 岛木（笠木下方的短横）\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] + _H - kasagi_z * 0.8))\n    shimaki = bpy.context.object; shimaki.name = _NAME + '_shimaki'\n    shimaki.scale = (_W + _H * 0.05, kasagi_y * 2.5, kasagi_z * 1.5)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bv = shimaki.modifiers.new('Bev', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.015; bv.segments = 2\n    parts.append(shimaki)\n\n    # 额束（中柱）\n    nuki_h = _H * 0.12\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] + _H * 0.75))\n    nuki = bpy.context.object; nuki.name = _NAME + '_nuki'\n    nuki.scale = (_W * 1.05, kasagi_y * 1.5, nuki_h)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    parts.append(nuki)\n\n    for p in parts:\n        if not p.data.materials:\n            p.data.materials.append(mat)\n        else:\n            p.data.materials[0] = mat\n\n    bpy.ops.object.empty_add(type='PLAIN_AXES', location=_LOC)\n    root = bpy.context.object; root.name = _NAME + '_root'\n    for p in parts:\n        p.parent = root\n        p.matrix_parent_inverse = root.matrix_world.inverted()\n    print('[apply_template] torii_gate 完成: ' + str(_H) + 'm 高 ' + str(_W) + 'm 宽')\nexcept Exception as _e:\n    import traceback; print('[apply_template] torii_gate 失败:', _e); traceback.print_exc()\n"
})

# 16. stone_lantern 石灯笼
TEMPLATES.append({
    "name": "stone_lantern",
    "title": "石灯笼（基座+柱+灯台+灯室+顶盖，5 段组合）",
    "category": "japanese",
    "description": "日式石灯笼春日燈籠：方形基台 + 圆柱身 + 六角灯室（带镂空） + 六角顶盖 + 顶珠。",
    "params": [
        {"name": "name",     "type": "string", "default": "Lantern", "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "height",   "type": "float",  "default": 1.5,       "description": "整体高度"},
        {"name": "lit",      "type": "boolean","default": True,      "description": "灯室是否发光（True=夜晚暖光）"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _H = float({{height}})\n    _LIT = bool({{lit}})\n\n    mat = bpy.data.materials.new(_NAME + '_stone_mat')\n    mat.use_nodes = True\n    bsdf = mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (0.55, 0.52, 0.48, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.9\n\n    parts = []\n    cz = _LOC[2]\n    # 基台\n    base_h = _H * 0.12\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], cz + base_h * 0.5))\n    b = bpy.context.object; b.name = _NAME + '_base'\n    b.scale = (_H * 0.4, _H * 0.4, base_h)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    parts.append(b); cz += base_h\n    # 柱身\n    pole_h = _H * 0.35\n    bpy.ops.mesh.primitive_cylinder_add(radius=_H * 0.08, depth=pole_h, vertices=12, location=(_LOC[0], _LOC[1], cz + pole_h * 0.5))\n    p = bpy.context.object; p.name = _NAME + '_pole'\n    bpy.ops.object.shade_smooth()\n    parts.append(p); cz += pole_h\n    # 灯台（小平台）\n    plat_h = _H * 0.06\n    bpy.ops.mesh.primitive_cylinder_add(radius=_H * 0.18, depth=plat_h, vertices=6, location=(_LOC[0], _LOC[1], cz + plat_h * 0.5))\n    pl = bpy.context.object; pl.name = _NAME + '_platform'\n    parts.append(pl); cz += plat_h\n    # 灯室（六角柱）\n    room_h = _H * 0.25\n    bpy.ops.mesh.primitive_cylinder_add(radius=_H * 0.15, depth=room_h, vertices=6, location=(_LOC[0], _LOC[1], cz + room_h * 0.5))\n    room = bpy.context.object; room.name = _NAME + '_room'\n    parts.append(room); cz += room_h\n    # 顶盖（六角锥）\n    cap_h = _H * 0.15\n    bpy.ops.mesh.primitive_cone_add(radius1=_H * 0.22, radius2=_H * 0.05, depth=cap_h, vertices=6, location=(_LOC[0], _LOC[1], cz + cap_h * 0.5))\n    cap = bpy.context.object; cap.name = _NAME + '_cap'\n    parts.append(cap); cz += cap_h\n    # 顶珠\n    bpy.ops.mesh.primitive_uv_sphere_add(radius=_H * 0.04, location=(_LOC[0], _LOC[1], cz + _H * 0.03))\n    top = bpy.context.object; top.name = _NAME + '_top'\n    bpy.ops.object.shade_smooth()\n    parts.append(top)\n\n    for pt in parts:\n        if not pt.data.materials:\n            pt.data.materials.append(mat)\n        else:\n            pt.data.materials[0] = mat\n\n    # 灯室如果点亮：换发光材质 + 内部 Point Light\n    if _LIT:\n        em_mat = bpy.data.materials.new(_NAME + '_lit_mat')\n        em_mat.use_nodes = True\n        nt = em_mat.node_tree\n        for n in list(nt.nodes):\n            nt.nodes.remove(n)\n        out = nt.nodes.new('ShaderNodeOutputMaterial')\n        em = nt.nodes.new('ShaderNodeEmission')\n        if 'Color' in em.inputs:\n            em.inputs['Color'].default_value = (1.0, 0.75, 0.40, 1.0)\n        if 'Strength' in em.inputs:\n            em.inputs['Strength'].default_value = 6.0\n        nt.links.new(em.outputs['Emission'], out.inputs['Surface'])\n        room.data.materials.clear()\n        room.data.materials.append(em_mat)\n        # 内部 Point Light\n        bpy.ops.object.light_add(type='POINT', location=(_LOC[0], _LOC[1], _LOC[2] + _H * 0.7))\n        lt = bpy.context.object; lt.name = _NAME + '_light'\n        lt.data.energy = 200\n        lt.data.color = (1.0, 0.75, 0.40)\n    print('[apply_template] stone_lantern 完成: 5 段堆叠 lit=' + str(_LIT))\nexcept Exception as _e:\n    import traceback; print('[apply_template] stone_lantern 失败:', _e); traceback.print_exc()\n"
})

# 17. stone_steps 石阶
TEMPLATES.append({
    "name": "stone_steps",
    "title": "石阶（Cube + Array 沿 +Z + 灰石材质）",
    "category": "japanese",
    "description": "1 块石阶 cube + Array 沿 X+Z 等距复制 N 阶，灰色粗糙石材。",
    "params": [
        {"name": "name",     "type": "string", "default": "Steps",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "最低一阶底前中心"},
        {"name": "count",    "type": "int",    "default": 8,         "description": "阶数"},
        {"name": "step_w",   "type": "float",  "default": 2.5,       "description": "每阶宽（米）"},
        {"name": "step_d",   "type": "float",  "default": 0.35,      "description": "每阶进深（米）"},
        {"name": "step_h",   "type": "float",  "default": 0.18,      "description": "每阶高（米）"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _N = max(1, int({{count}}))\n    _W = float({{step_w}})\n    _D = float({{step_d}})\n    _H = float({{step_h}})\n\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1] + _D * 0.5, _LOC[2] + _H * 0.5))\n    s = bpy.context.object; s.name = _NAME\n    s.scale = (_W, _D, _H)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bv = s.modifiers.new('Bev', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.01; bv.segments = 2\n    arr = s.modifiers.new('Array', 'ARRAY')\n    arr.use_relative_offset = False\n    arr.use_constant_offset = True\n    arr.constant_offset_displace = (0, _D, _H)\n    arr.count = _N\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    bsdf = mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (0.55, 0.52, 0.48, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.9\n    s.data.materials.append(mat)\n    print('[apply_template] stone_steps 完成: ' + str(_N) + ' 阶')\nexcept Exception as _e:\n    import traceback; print('[apply_template] stone_steps 失败:', _e); traceback.print_exc()\n"
})

# 18. wooden_bridge 木桥
TEMPLATES.append({
    "name": "wooden_bridge",
    "title": "木桥（桥板 Array + 2 侧栏杆 + 4 桥墩）",
    "category": "japanese",
    "description": "n 块木板（Array）+ 2 根栏杆扶手 + 4 立柱桥墩，朱红或木色可切换。",
    "params": [
        {"name": "name",     "type": "string", "default": "Bridge",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0.4], "description": "桥面中心高度"},
        {"name": "length",   "type": "float",  "default": 4.0,       "description": "桥长"},
        {"name": "width",    "type": "float",  "default": 1.6,       "description": "桥宽"},
        {"name": "color",    "type": "rgb",    "default": [0.78, 0.10, 0.08], "description": "桥色（朱红/木色）"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _L = float({{length}})\n    _W = float({{width}})\n    _C = {{color|json}}\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    bsdf = mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.65\n\n    parts = []\n    # 桥板（Array）\n    plank_l = _W\n    plank_d = 0.12\n    n_planks = max(2, int(_L / 0.15))\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0] - _L * 0.5 + plank_d * 0.5, _LOC[1], _LOC[2]))\n    plank = bpy.context.object; plank.name = _NAME + '_plank'\n    plank.scale = (plank_d * 0.85, plank_l, 0.04)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    arr = plank.modifiers.new('Arr', 'ARRAY')\n    arr.use_relative_offset = False\n    arr.use_constant_offset = True\n    arr.constant_offset_displace = (plank_d, 0, 0)\n    arr.count = n_planks\n    parts.append(plank)\n\n    # 2 根扶手\n    for sy in [-1, 1]:\n        bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1] + sy * _W * 0.5, _LOC[2] + 0.5))\n        rail = bpy.context.object; rail.name = _NAME + '_rail_' + ('R' if sy > 0 else 'L')\n        rail.scale = (_L, 0.05, 0.08)\n        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n        parts.append(rail)\n\n    # 4 立柱桥墩\n    for sx in [-1, 1]:\n        for sy in [-1, 1]:\n            bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0] + sx * _L * 0.45, _LOC[1] + sy * _W * 0.5, _LOC[2] + 0.25))\n            pl = bpy.context.object; pl.name = _NAME + '_post'\n            pl.scale = (0.08, 0.08, 0.55)\n            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n            parts.append(pl)\n\n    for p in parts:\n        p.data.materials.append(mat)\n    print('[apply_template] wooden_bridge 完成: ' + str(_L) + 'm 长 ' + str(n_planks) + ' 块板')\nexcept Exception as _e:\n    import traceback; print('[apply_template] wooden_bridge 失败:', _e); traceback.print_exc()\n"
})

# 19. tatami_floor 榻榻米
TEMPLATES.append({
    "name": "tatami_floor",
    "title": "榻榻米地板（Plane + Array 拼块 + 黄绿色编织材质）",
    "category": "japanese",
    "description": "标准日式榻榻米（半畳/一畳），用 cube 单元 + Array X×Y 拼出整面。黄绿色 + Noise 编织感。",
    "params": [
        {"name": "name",     "type": "string", "default": "Tatami",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "中心位置"},
        {"name": "rows",     "type": "int",    "default": 3,         "description": "畳数（X 方向）"},
        {"name": "cols",     "type": "int",    "default": 3,         "description": "畳数（Y 方向）"},
        {"name": "tatami_x", "type": "float",  "default": 1.80,      "description": "一畳长边"},
        {"name": "tatami_y", "type": "float",  "default": 0.90,      "description": "一畳短边"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _R = max(1, int({{rows}}))\n    _CO = max(1, int({{cols}}))\n    _X = float({{tatami_x}})\n    _Y = float({{tatami_y}})\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    nt = mat.node_tree\n    bsdf = nt.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (0.76, 0.72, 0.45, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.85\n    # 编织感：Noise + ColorRamp\n    noise = nt.nodes.new('ShaderNodeTexNoise')\n    noise.inputs['Scale'].default_value = 40.0\n    cr = nt.nodes.new('ShaderNodeValToRGB')\n    cr.color_ramp.elements[0].color = (0.65, 0.62, 0.35, 1)\n    cr.color_ramp.elements[1].color = (0.85, 0.80, 0.50, 1)\n    nt.links.new(noise.outputs['Fac'], cr.inputs['Fac'])\n    if bsdf:\n        nt.links.new(cr.outputs['Color'], bsdf.inputs['Base Color'])\n\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0] - (_R - 1) * 0.5 * _X, _LOC[1] - (_CO - 1) * 0.5 * _Y, _LOC[2] + 0.025))\n    base = bpy.context.object; base.name = _NAME + '_unit'\n    base.scale = (_X * 0.98, _Y * 0.98, 0.05)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bv = base.modifiers.new('Bev', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.005; bv.segments = 2\n    base.data.materials.append(mat)\n\n    arr1 = base.modifiers.new('ArrX', 'ARRAY')\n    arr1.use_relative_offset = False\n    arr1.use_constant_offset = True\n    arr1.constant_offset_displace = (_X, 0, 0)\n    arr1.count = _R\n    arr2 = base.modifiers.new('ArrY', 'ARRAY')\n    arr2.use_relative_offset = False\n    arr2.use_constant_offset = True\n    arr2.constant_offset_displace = (0, _Y, 0)\n    arr2.count = _CO\n    print('[apply_template] tatami_floor 完成: ' + str(_R) + '×' + str(_CO) + ' = ' + str(_R * _CO) + ' 畳')\nexcept Exception as _e:\n    import traceback; print('[apply_template] tatami_floor 失败:', _e); traceback.print_exc()\n"
})

# 20. shoji_door 障子门
TEMPLATES.append({
    "name": "shoji_door",
    "title": "障子门（木格栅 + 半透白纸 plane）",
    "category": "japanese",
    "description": "外框 4 边 + 内部横竖木格栅（cube Array）+ 后侧一块半透白色 plane 当和纸。",
    "params": [
        {"name": "name",     "type": "string", "default": "Shoji",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 1.0], "description": "门中心（贴墙挂高）"},
        {"name": "width",    "type": "float",  "default": 0.9,       "description": "门宽"},
        {"name": "height",   "type": "float",  "default": 2.0,       "description": "门高"},
        {"name": "grid_x",   "type": "int",    "default": 4,         "description": "横格数"},
        {"name": "grid_y",   "type": "int",    "default": 6,         "description": "竖格数"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _W = float({{width}})\n    _H = float({{height}})\n    _GX = max(1, int({{grid_x}}))\n    _GY = max(1, int({{grid_y}}))\n\n    wood_mat = bpy.data.materials.new(_NAME + '_wood_mat')\n    wood_mat.use_nodes = True\n    bsdf = wood_mat.node_tree.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (0.35, 0.25, 0.18, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.6\n\n    paper_mat = bpy.data.materials.new(_NAME + '_paper_mat')\n    paper_mat.use_nodes = True\n    pb = paper_mat.node_tree.nodes.get('Principled BSDF')\n    if pb and 'Base Color' in pb.inputs:\n        pb.inputs['Base Color'].default_value = (0.95, 0.93, 0.85, 1.0)\n    if pb and 'Roughness' in pb.inputs:\n        pb.inputs['Roughness'].default_value = 0.8\n    if pb and 'Alpha' in pb.inputs:\n        pb.inputs['Alpha'].default_value = 0.85\n    paper_mat.blend_method = 'BLEND'\n\n    parts = []\n    frame_w = 0.04\n    # 4 边框\n    for sy in [-1, 1]:\n        bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] + sy * (_H * 0.5 - frame_w * 0.5)))\n        h = bpy.context.object; h.name = _NAME + '_hframe'\n        h.scale = (_W, frame_w, frame_w)\n        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n        parts.append(h)\n    for sx in [-1, 1]:\n        bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0] + sx * (_W * 0.5 - frame_w * 0.5), _LOC[1], _LOC[2]))\n        v = bpy.context.object; v.name = _NAME + '_vframe'\n        v.scale = (frame_w, frame_w, _H - frame_w * 2)\n        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n        parts.append(v)\n\n    # 横格（Array）\n    inner_h = _H - 2 * frame_w\n    sx_step = inner_h / (_GY + 1)\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] - _H * 0.5 + frame_w + sx_step))\n    h_grid = bpy.context.object; h_grid.name = _NAME + '_hgrid'\n    h_grid.scale = (_W - 2 * frame_w, 0.015, 0.015)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    arr = h_grid.modifiers.new('ArrZ', 'ARRAY')\n    arr.use_relative_offset = False\n    arr.use_constant_offset = True\n    arr.constant_offset_displace = (0, 0, sx_step)\n    arr.count = _GY\n    parts.append(h_grid)\n\n    # 竖格\n    inner_w = _W - 2 * frame_w\n    sy_step = inner_w / (_GX + 1)\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0] - _W * 0.5 + frame_w + sy_step, _LOC[1], _LOC[2]))\n    v_grid = bpy.context.object; v_grid.name = _NAME + '_vgrid'\n    v_grid.scale = (0.015, 0.015, _H - 2 * frame_w)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    arr2 = v_grid.modifiers.new('ArrX', 'ARRAY')\n    arr2.use_relative_offset = False\n    arr2.use_constant_offset = True\n    arr2.constant_offset_displace = (sy_step, 0, 0)\n    arr2.count = _GX\n    parts.append(v_grid)\n\n    # 和纸（薄 plane）\n    bpy.ops.mesh.primitive_plane_add(size=1, location=(_LOC[0], _LOC[1] - 0.005, _LOC[2]))\n    paper = bpy.context.object; paper.name = _NAME + '_paper'\n    paper.rotation_euler = (math.radians(90), 0, 0)\n    paper.scale = (_W - 2 * frame_w, _H - 2 * frame_w, 1)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)\n    paper.data.materials.append(paper_mat)\n\n    for p in parts:\n        p.data.materials.append(wood_mat)\n    print('[apply_template] shoji_door 完成: ' + str(_W) + 'x' + str(_H) + ' 木格 ' + str(_GX) + 'x' + str(_GY))\nexcept Exception as _e:\n    import traceback; print('[apply_template] shoji_door 失败:', _e); traceback.print_exc()\n"
})

# 21. paper_lantern_string 纸灯笼挂串
TEMPLATES.append({
    "name": "paper_lantern_string",
    "title": "纸灯笼挂串（多个 UV Sphere + 自发光 + 连线）",
    "category": "japanese",
    "description": "一条横向悬挂的纸灯笼串，球形（UV Sphere scaled）+ 内置点光 + 顶部红色绳子（cylinder 横线）。",
    "params": [
        {"name": "name",     "type": "string", "default": "Lanterns","description": "对象名前缀"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 3.0], "description": "挂线两端中点"},
        {"name": "length",   "type": "float",  "default": 6.0,       "description": "挂线长度"},
        {"name": "count",    "type": "int",    "default": 6,         "description": "灯笼数量"},
        {"name": "color",    "type": "rgb",    "default": [1.0, 0.40, 0.15], "description": "灯笼色（暖橙）"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _L = float({{length}})\n    _N = max(1, int({{count}}))\n    _C = {{color|json}}\n\n    # 绳子\n    bpy.ops.mesh.primitive_cylinder_add(radius=0.01, depth=_L, vertices=8, location=_LOC)\n    rope = bpy.context.object; rope.name = _NAME + '_rope'\n    rope.rotation_euler = (0, math.radians(90), 0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    rope_mat = bpy.data.materials.new(_NAME + '_rope_mat')\n    rope_mat.use_nodes = True\n    b1 = rope_mat.node_tree.nodes.get('Principled BSDF')\n    if b1 and 'Base Color' in b1.inputs:\n        b1.inputs['Base Color'].default_value = (0.2, 0.15, 0.10, 1.0)\n    rope.data.materials.append(rope_mat)\n\n    # 发光灯笼材质\n    em_mat = bpy.data.materials.new(_NAME + '_em_mat')\n    em_mat.use_nodes = True\n    nt = em_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    em = nt.nodes.new('ShaderNodeEmission')\n    if 'Color' in em.inputs:\n        em.inputs['Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Strength' in em.inputs:\n        em.inputs['Strength'].default_value = 3.0\n    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])\n\n    # 灯笼们\n    step = _L / max(1, _N - 1) if _N > 1 else 0\n    x0 = _LOC[0] - _L * 0.5\n    for i in range(_N):\n        x = x0 + i * step\n        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(x, _LOC[1], _LOC[2] - 0.20))\n        lan = bpy.context.object; lan.name = _NAME + '_' + str(i + 1)\n        lan.scale = (1.0, 1.0, 1.2)\n        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n        bpy.ops.object.shade_smooth()\n        lan.data.materials.append(em_mat)\n        # 短挂绳\n        bpy.ops.mesh.primitive_cylinder_add(radius=0.005, depth=0.10, vertices=6, location=(x, _LOC[1], _LOC[2] - 0.05))\n        sh = bpy.context.object; sh.name = _NAME + '_hang_' + str(i + 1)\n        sh.data.materials.append(rope_mat)\n    print('[apply_template] paper_lantern_string 完成: ' + str(_N) + ' 个灯笼 长 ' + str(_L) + 'm')\nexcept Exception as _e:\n    import traceback; print('[apply_template] paper_lantern_string 失败:', _e); traceback.print_exc()\n"
})

# 22. sakura_petals_particle 樱花瓣飘落
TEMPLATES.append({
    "name": "sakura_petals_particle",
    "title": "樱花瓣飘落（发射器 Plane + Particle Hair 静态散布）",
    "category": "japanese",
    "description": "上方一个大 Plane 当 emitter，用 Particle Hair 系统散布微小粉色花瓣 plane 实例，让画面里看起来在飘。",
    "params": [
        {"name": "name",     "type": "string", "default": "Sakura_petals", "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 5.0],    "description": "发射器中心位置"},
        {"name": "area",     "type": "float",  "default": 8.0,            "description": "发射器边长"},
        {"name": "count",    "type": "int",    "default": 200,            "description": "花瓣总数"},
        {"name": "color",    "type": "rgb",    "default": [1.0, 0.78, 0.85], "description": "花瓣色"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _A = float({{area}})\n    _N = max(1, int({{count}}))\n    _C = {{color|json}}\n\n    # 花瓣 proto\n    bpy.ops.mesh.primitive_plane_add(size=0.04, location=(_LOC[0] + 100, 0, 0))\n    pet = bpy.context.object; pet.name = _NAME + '_proto'\n    pet.scale = (1.5, 0.7, 1.0)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    pet.hide_render = True; pet.hide_viewport = True\n    pmat = bpy.data.materials.new(_NAME + '_mat')\n    pmat.use_nodes = True\n    b = pmat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    pet.data.materials.append(pmat)\n\n    # 发射器（大 plane，hide_render）\n    bpy.ops.mesh.primitive_plane_add(size=_A, location=_LOC)\n    emit = bpy.context.object; emit.name = _NAME + '_emitter'\n    emit.hide_render = True\n\n    # Particle Hair：在发射 plane 上散布\n    psys_mod = emit.modifiers.new('Hair', 'PARTICLE_SYSTEM')\n    psys = emit.particle_systems[-1]\n    s = psys.settings\n    s.type = 'HAIR'\n    s.count = _N\n    s.hair_length = 0.01\n    s.render_type = 'OBJECT'\n    s.instance_object = pet\n    s.particle_size = 1.0\n    s.use_rotations = True\n    s.rotation_mode = 'GLOB_Z'\n    s.rotation_factor_random = 1.0\n    print('[apply_template] sakura_petals_particle 完成: ' + str(_N) + ' 片花瓣 area=' + str(_A) + 'm')\nexcept Exception as _e:\n    import traceback; print('[apply_template] sakura_petals_particle 失败:', _e); traceback.print_exc()\n"
})

# 23. shrine_offering_box 神社赛钱箱
TEMPLATES.append({
    "name": "shrine_offering_box",
    "title": "神社赛钱箱（木箱 + 投币顶部格栅）",
    "category": "japanese",
    "description": "深色木箱 + 顶部一排木条投币格栅 + 正面金属包边。",
    "params": [
        {"name": "name",     "type": "string", "default": "OfferBox","description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "size",     "type": "float",  "default": 1.0,       "description": "尺寸基准（米）"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n\n    wood = bpy.data.materials.new(_NAME + '_wood')\n    wood.use_nodes = True\n    bw = wood.node_tree.nodes.get('Principled BSDF')\n    if bw and 'Base Color' in bw.inputs:\n        bw.inputs['Base Color'].default_value = (0.20, 0.13, 0.08, 1.0)\n    if bw and 'Roughness' in bw.inputs:\n        bw.inputs['Roughness'].default_value = 0.7\n\n    metal = bpy.data.materials.new(_NAME + '_metal')\n    metal.use_nodes = True\n    bm = metal.node_tree.nodes.get('Principled BSDF')\n    if bm and 'Base Color' in bm.inputs:\n        bm.inputs['Base Color'].default_value = (0.6, 0.55, 0.40, 1.0)\n    if bm and 'Metallic' in bm.inputs:\n        bm.inputs['Metallic'].default_value = 0.8\n    if bm and 'Roughness' in bm.inputs:\n        bm.inputs['Roughness'].default_value = 0.4\n\n    parts = []\n    # 主体\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] + _S * 0.4))\n    box = bpy.context.object; box.name = _NAME + '_box'\n    box.scale = (_S * 1.5, _S * 0.6, _S * 0.8)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bv = box.modifiers.new('Bev', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.015; bv.segments = 2\n    box.data.materials.append(wood)\n    parts.append(box)\n\n    # 顶部投币格栅（一排薄 cube）\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0] - _S * 0.7, _LOC[1], _LOC[2] + _S * 0.82))\n    bar = bpy.context.object; bar.name = _NAME + '_bar'\n    bar.scale = (_S * 0.03, _S * 0.55, _S * 0.03)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    arr = bar.modifiers.new('Arr', 'ARRAY')\n    arr.use_relative_offset = False\n    arr.use_constant_offset = True\n    arr.constant_offset_displace = (_S * 0.10, 0, 0)\n    arr.count = 14\n    bar.data.materials.append(metal)\n    parts.append(bar)\n\n    # 正面金属包边\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1] - _S * 0.3 - 0.015, _LOC[2] + _S * 0.4))\n    front = bpy.context.object; front.name = _NAME + '_front_strip'\n    front.scale = (_S * 1.55, 0.02, _S * 0.05)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    front.data.materials.append(metal)\n    parts.append(front)\n\n    bpy.ops.object.empty_add(type='PLAIN_AXES', location=_LOC)\n    root = bpy.context.object; root.name = _NAME + '_root'\n    for p in parts:\n        p.parent = root\n        p.matrix_parent_inverse = root.matrix_world.inverted()\n    print('[apply_template] shrine_offering_box 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] shrine_offering_box 失败:', _e); traceback.print_exc()\n"
})

# 24. zen_garden_stones 枯山水
TEMPLATES.append({
    "name": "zen_garden_stones",
    "title": "枯山水（细沙 Plane + 弧形 wave 线条 + 5 块石头）",
    "category": "japanese",
    "description": "白沙 plane（细 Noise 起伏）+ 3~5 块大小不一的石头（rock_voronoi 类似）+ 同心环波纹（Wave 修饰）。",
    "params": [
        {"name": "name",     "type": "string", "default": "Zen",     "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "中心"},
        {"name": "size",     "type": "float",  "default": 4.0,       "description": "沙地边长"},
        {"name": "stone_count","type": "int",  "default": 5,         "description": "石头数量"}
    ],
    "code": "import bpy, math, random\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _N = max(1, int({{stone_count}}))\n\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=_LOC)\n    sand = bpy.context.object; sand.name = _NAME + '_sand'\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    bpy.ops.mesh.subdivide(number_cuts=30)\n    bpy.ops.object.mode_set(mode='OBJECT')\n    wave = sand.modifiers.new('Wave', 'WAVE')\n    wave.height = 0.015\n    wave.width = 0.5\n    wave.speed = 0\n    wave.use_x = True\n    wave.use_y = True\n    s_mat = bpy.data.materials.new(_NAME + '_sand_mat')\n    s_mat.use_nodes = True\n    bs = s_mat.node_tree.nodes.get('Principled BSDF')\n    if bs and 'Base Color' in bs.inputs:\n        bs.inputs['Base Color'].default_value = (0.93, 0.90, 0.82, 1.0)\n    if bs and 'Roughness' in bs.inputs:\n        bs.inputs['Roughness'].default_value = 0.95\n    sand.data.materials.append(s_mat)\n\n    stone_mat = bpy.data.materials.new(_NAME + '_stone_mat')\n    stone_mat.use_nodes = True\n    bst = stone_mat.node_tree.nodes.get('Principled BSDF')\n    if bst and 'Base Color' in bst.inputs:\n        bst.inputs['Base Color'].default_value = (0.35, 0.32, 0.28, 1.0)\n    if bst and 'Roughness' in bst.inputs:\n        bst.inputs['Roughness'].default_value = 0.9\n\n    for i in range(_N):\n        sx = (random.random() - 0.5) * _S * 0.7\n        sy = (random.random() - 0.5) * _S * 0.7\n        sz = 0.10 + random.random() * 0.20\n        bpy.ops.mesh.primitive_ico_sphere_add(radius=sz, subdivisions=2, location=(_LOC[0] + sx, _LOC[1] + sy, _LOC[2] + sz * 0.5))\n        st = bpy.context.object; st.name = _NAME + '_stone_' + str(i + 1)\n        st.scale = (1.2, 0.8, 0.6)\n        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n        tex = bpy.data.textures.new(st.name + '_tex', 'VORONOI')\n        tex.noise_scale = 0.3\n        dm = st.modifiers.new('Disp', 'DISPLACE')\n        dm.texture = tex\n        dm.strength = sz * 0.2\n        bpy.ops.object.shade_smooth()\n        st.data.materials.append(stone_mat)\n    print('[apply_template] zen_garden_stones 完成: ' + str(_S) + 'm 沙地 + ' + str(_N) + ' 块石')\nexcept Exception as _e:\n    import traceback; print('[apply_template] zen_garden_stones 失败:', _e); traceback.print_exc()\n"
})


# ============================================================
# 写入
# ============================================================
if __name__ == '__main__':
    append_templates(TEMPLATES, batch_label='batch1_nature_jp')
