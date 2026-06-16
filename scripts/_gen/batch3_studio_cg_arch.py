#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.1 H-Hotfix5 批 3：摄影棚 10 + CG 特效 10 + 建筑废墟 6 = 26 个模板
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import append_templates

TEMPLATES = []

# ============================================================
# 摄影棚（10 个）⭐
# ============================================================

# 45. studio_seamless_bg ⭐ 无缝背景纸
TEMPLATES.append({
    "name": "studio_seamless_bg",
    "title": "无缝背景纸（白/灰/黑大 cyclorama 弧形过渡）",
    "category": "studio",
    "description": "摄影棚标准 cyclorama：地面 plane + 后立面 plane + 中间一段圆弧过渡（无缝），shade=neutral 单色 + 极低反射。",
    "params": [
        {"name": "name",     "type": "string", "default": "Cyc",     "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "前下方中心"},
        {"name": "width",    "type": "float",  "default": 6.0,       "description": "背景宽度（X）"},
        {"name": "depth",    "type": "float",  "default": 4.0,       "description": "地面深度（Y）"},
        {"name": "height",   "type": "float",  "default": 4.0,       "description": "立面高度（Z）"},
        {"name": "kind",     "type": "string", "default": "white",   "description": "white / gray / black"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _W = float({{width}})\n    _D = float({{depth}})\n    _H = float({{height}})\n    _K = {{kind|json}}\n\n    color_map = {'white': (0.95, 0.95, 0.95), 'gray': (0.45, 0.45, 0.45), 'black': (0.04, 0.04, 0.04)}\n    c = color_map.get(_K, (0.95, 0.95, 0.95))\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.85\n\n    parts = []\n    # 地面\n    bpy.ops.mesh.primitive_plane_add(size=1, location=(_LOC[0], _LOC[1] + _D * 0.5, _LOC[2]))\n    floor = bpy.context.object; floor.name = _NAME + '_floor'\n    floor.scale = (_W, _D, 1.0)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    parts.append(floor)\n    # 立面\n    bpy.ops.mesh.primitive_plane_add(size=1, location=(_LOC[0], _LOC[1] + _D, _LOC[2] + _H * 0.5))\n    back = bpy.context.object; back.name = _NAME + '_back'\n    back.rotation_euler = (math.radians(90), 0, 0)\n    back.scale = (_W, _H, 1.0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)\n    parts.append(back)\n    # 圆弧过渡（cylinder 分段四分之一）\n    bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=_W, vertices=24, location=(_LOC[0], _LOC[1] + _D - 0.6, _LOC[2] + 0.6))\n    arc = bpy.context.object; arc.name = _NAME + '_arc'\n    arc.rotation_euler = (0, math.radians(90), 0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    parts.append(arc)\n\n    for p in parts:\n        p.data.materials.append(mat)\n    print('[apply_template] studio_seamless_bg 完成: ' + _K + ' ' + str(_W) + 'x' + str(_D) + 'x' + str(_H))\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_seamless_bg 失败:', _e); traceback.print_exc()\n"
})

# 46. studio_softbox ⭐ 柔光箱
TEMPLATES.append({
    "name": "studio_softbox",
    "title": "柔光箱（金字塔形 cube + 前发光 plane + 灯架）",
    "category": "studio",
    "description": "金字塔形外壳（cone scaled）+ 前面发光 plane（高强度 Emission）+ 真实 Area Light，最常用的主光形态。",
    "params": [
        {"name": "name",     "type": "string", "default": "Softbox", "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [2, -2, 2], "description": "柔光箱中心"},
        {"name": "size",     "type": "float",  "default": 0.6,       "description": "前发光面边长（米）"},
        {"name": "strength", "type": "float",  "default": 800.0,     "description": "Area Light 强度（W）"},
        {"name": "aim_at",   "type": "vec3",   "default": [0, 0, 1.5], "description": "对准的目标点"}
    ],
    "code": "import bpy, math\nfrom mathutils import Vector\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _STR = float({{strength}})\n    _AIM = {{aim_at|json}}\n\n    body_mat = bpy.data.materials.new(_NAME + '_body_mat')\n    body_mat.use_nodes = True\n    b = body_mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.6\n\n    em_mat = bpy.data.materials.new(_NAME + '_em_mat')\n    em_mat.use_nodes = True\n    nt = em_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    em = nt.nodes.new('ShaderNodeEmission')\n    if 'Color' in em.inputs:\n        em.inputs['Color'].default_value = (1.0, 0.98, 0.95, 1.0)\n    if 'Strength' in em.inputs:\n        em.inputs['Strength'].default_value = 5.0\n    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])\n\n    # 金字塔形外壳（cone radius1=大，radius2=小，倒置）\n    bpy.ops.mesh.primitive_cone_add(radius1=_S * 0.7, radius2=_S * 0.55, depth=_S * 0.7, vertices=4, location=_LOC)\n    body = bpy.context.object; body.name = _NAME + '_body'\n    body.data.materials.append(body_mat)\n\n    # 前发光面\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=(_LOC[0], _LOC[1], _LOC[2] + _S * 0.36))\n    face = bpy.context.object; face.name = _NAME + '_face'\n    face.data.materials.append(em_mat)\n\n    # Area Light\n    bpy.ops.object.light_add(type='AREA', location=(_LOC[0], _LOC[1], _LOC[2] + _S * 0.36))\n    lt = bpy.context.object; lt.name = _NAME + '_light'\n    lt.data.shape = 'SQUARE'\n    lt.data.size = _S\n    lt.data.energy = _STR\n    lt.data.color = (1.0, 0.98, 0.95)\n\n    # Track To 对准 aim 目标\n    bpy.ops.object.empty_add(type='PLAIN_AXES', location=tuple(_AIM))\n    target = bpy.context.object; target.name = _NAME + '_aim'\n    for o in [body, face, lt]:\n        con = o.constraints.new('TRACK_TO')\n        con.target = target\n        con.track_axis = 'TRACK_NEGATIVE_Z'\n        con.up_axis = 'UP_Y'\n    print('[apply_template] studio_softbox 完成: size=' + str(_S) + ' energy=' + str(_STR))\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_softbox 失败:', _e); traceback.print_exc()\n"
})

# 47. studio_umbrella 反光伞
TEMPLATES.append({
    "name": "studio_umbrella",
    "title": "反光伞（cone 球面 + 内 silver/white + Area Light）",
    "category": "studio",
    "description": "圆锥形外壳（cone）+ 内表面银/白色 + 顶部 Spot Light 或 Area Light 朝伞内打光。",
    "params": [
        {"name": "name",     "type": "string", "default": "Umbrella","description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [-2, -2, 2.2], "description": "中心"},
        {"name": "size",     "type": "float",  "default": 0.9,       "description": "伞口直径"},
        {"name": "color",    "type": "rgb",    "default": [0.95, 0.95, 0.95], "description": "内里色（白/银）"},
        {"name": "strength", "type": "float",  "default": 600.0,     "description": "Area Light 强度"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _C = {{color|json}}\n    _STR = float({{strength}})\n\n    inside_mat = bpy.data.materials.new(_NAME + '_inside_mat')\n    inside_mat.use_nodes = True\n    b = inside_mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if b and 'Metallic' in b.inputs:\n        b.inputs['Metallic'].default_value = 0.85 if max(_C) > 0.7 and abs(_C[0] - _C[1]) < 0.1 else 0.2\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.4\n\n    # 伞（cone）\n    bpy.ops.mesh.primitive_cone_add(radius1=_S * 0.5, radius2=0, depth=_S * 0.7, vertices=24, location=_LOC)\n    umb = bpy.context.object; umb.name = _NAME + '_umb'\n    bpy.ops.object.shade_smooth()\n    # 反转法线让内表面朝外\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    bpy.ops.mesh.flip_normals()\n    bpy.ops.object.mode_set(mode='OBJECT')\n    umb.data.materials.append(inside_mat)\n\n    # Area Light（朝伞内）\n    bpy.ops.object.light_add(type='AREA', location=(_LOC[0], _LOC[1], _LOC[2] - _S * 0.2))\n    lt = bpy.context.object; lt.name = _NAME + '_light'\n    lt.data.size = _S * 0.7\n    lt.data.energy = _STR\n    print('[apply_template] studio_umbrella 完成: size=' + str(_S))\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_umbrella 失败:', _e); traceback.print_exc()\n"
})

# 48. studio_beauty_dish 美人碟
TEMPLATES.append({
    "name": "studio_beauty_dish",
    "title": "美人碟（圆盘 + 中央反光板 + 强 Area Light）",
    "category": "studio",
    "description": "时尚摄影专用：浅圆盘碟（cylinder 大半径浅深度） + 中央小反光圆盘 + Area Light，光效硬中带柔。",
    "params": [
        {"name": "name",     "type": "string", "default": "Beauty",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, -2.0, 2.2], "description": "中心"},
        {"name": "radius",   "type": "float",  "default": 0.40,      "description": "碟半径"},
        {"name": "strength", "type": "float",  "default": 700.0,     "description": "Area Light 强度"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _R = float({{radius}})\n    _STR = float({{strength}})\n\n    metal = bpy.data.materials.new(_NAME + '_metal')\n    metal.use_nodes = True\n    b = metal.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.92, 0.92, 0.94, 1.0)\n    if b and 'Metallic' in b.inputs:\n        b.inputs['Metallic'].default_value = 0.9\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.25\n\n    # 圆盘碟\n    bpy.ops.mesh.primitive_cylinder_add(radius=_R, depth=0.10, vertices=32, location=_LOC)\n    dish = bpy.context.object; dish.name = _NAME + '_dish'\n    bpy.ops.object.shade_smooth()\n    dish.data.materials.append(metal)\n    # 中央反光小圆盘（挡光板）\n    bpy.ops.mesh.primitive_cylinder_add(radius=_R * 0.25, depth=0.02, vertices=20, location=(_LOC[0], _LOC[1], _LOC[2] - 0.04))\n    rfl = bpy.context.object; rfl.name = _NAME + '_reflector'\n    rfl.data.materials.append(metal)\n\n    bpy.ops.object.light_add(type='AREA', location=(_LOC[0], _LOC[1], _LOC[2] - 0.03))\n    lt = bpy.context.object; lt.name = _NAME + '_light'\n    lt.data.shape = 'DISK'\n    lt.data.size = _R * 1.8\n    lt.data.energy = _STR\n    print('[apply_template] studio_beauty_dish 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_beauty_dish 失败:', _e); traceback.print_exc()\n"
})

# 49. studio_reflector 反光板
TEMPLATES.append({
    "name": "studio_reflector",
    "title": "反光板（白/银/金 3 色，scaled plane + Metallic）",
    "category": "studio",
    "description": "圆形或矩形反光板（plane scaled），按 kind 切换白/银/金材质。",
    "params": [
        {"name": "name",     "type": "string", "default": "Reflector","description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [-2, -1, 1.5], "description": "中心"},
        {"name": "size",     "type": "float",  "default": 0.8,       "description": "板边长"},
        {"name": "kind",     "type": "string", "default": "white",   "description": "white / silver / gold"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _K = {{kind|json}}\n\n    color_map = {'white': (0.95, 0.95, 0.95, 0.0, 0.85), 'silver': (0.92, 0.92, 0.94, 0.95, 0.25), 'gold': (1.0, 0.78, 0.30, 0.92, 0.30)}\n    c = color_map.get(_K, color_map['white'])\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (c[0], c[1], c[2], 1.0)\n    if b and 'Metallic' in b.inputs:\n        b.inputs['Metallic'].default_value = c[3]\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = c[4]\n\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME + '_' + _K\n    # 圆形（用 Bevel + Subsurf 让边角圆）\n    obj.rotation_euler = (math.radians(90), 0, math.radians(45))\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    obj.data.materials.append(mat)\n    print('[apply_template] studio_reflector 完成: ' + _K + ' size=' + str(_S))\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_reflector 失败:', _e); traceback.print_exc()\n"
})

# 50. studio_light_stand C-stand 灯架
TEMPLATES.append({
    "name": "studio_light_stand",
    "title": "C-stand 灯架（三脚底 + 升降柱 + 横臂）",
    "category": "studio",
    "description": "三脚底（3 根斜柱） + 中央立柱（cylinder 多段） + 顶部水平横臂 + 横臂末端球形夹具。",
    "params": [
        {"name": "name",     "type": "string", "default": "Stand",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "height",   "type": "float",  "default": 2.2,       "description": "立柱高度"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _H = float({{height}})\n\n    metal = bpy.data.materials.new(_NAME + '_mat')\n    metal.use_nodes = True\n    b = metal.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1.0)\n    if b and 'Metallic' in b.inputs:\n        b.inputs['Metallic'].default_value = 0.6\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.4\n\n    # 三脚\n    for i in range(3):\n        ang = i * 2 * math.pi / 3\n        ex = math.cos(ang) * 0.45\n        ey = math.sin(ang) * 0.45\n        bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.55, vertices=10, location=(_LOC[0] + ex * 0.5, _LOC[1] + ey * 0.5, _LOC[2] + 0.20))\n        leg = bpy.context.object; leg.name = _NAME + '_leg_' + str(i + 1)\n        # 朝外+略下倾\n        leg.rotation_euler = (math.radians(20) * math.cos(ang), math.radians(20) * math.sin(ang), 0)\n        leg.data.materials.append(metal)\n\n    # 立柱\n    bpy.ops.mesh.primitive_cylinder_add(radius=0.022, depth=_H, vertices=12, location=(_LOC[0], _LOC[1], _LOC[2] + _H * 0.5))\n    pole = bpy.context.object; pole.name = _NAME + '_pole'\n    bpy.ops.object.shade_smooth()\n    pole.data.materials.append(metal)\n\n    # 横臂\n    bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.8, vertices=10, location=(_LOC[0] + 0.4, _LOC[1], _LOC[2] + _H - 0.05))\n    arm = bpy.context.object; arm.name = _NAME + '_arm'\n    arm.rotation_euler = (0, math.radians(90), 0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    arm.data.materials.append(metal)\n\n    # 末端夹具\n    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, location=(_LOC[0] + 0.8, _LOC[1], _LOC[2] + _H - 0.05))\n    knob = bpy.context.object; knob.name = _NAME + '_knob'\n    bpy.ops.object.shade_smooth()\n    knob.data.materials.append(metal)\n    print('[apply_template] studio_light_stand 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_light_stand 失败:', _e); traceback.print_exc()\n"
})

# 51. studio_tripod_camera 三脚架 + 相机
TEMPLATES.append({
    "name": "studio_tripod_camera",
    "title": "三脚架 + 相机（3 腿 + 云台 + 相机机身镜头）",
    "category": "studio",
    "description": "3 腿三脚架 + 中央云台 + 一台 DSLR/无反相机（机身 cube + 镜头 cylinder + 闪光灯小 cube），自动添加 Blender Camera 对象。",
    "params": [
        {"name": "name",     "type": "string", "default": "Tripod",  "description": "对象名前缀"},
        {"name": "location", "type": "vec3",   "default": [0, -3, 0], "description": "三脚架底中心"},
        {"name": "height",   "type": "float",  "default": 1.5,       "description": "三脚架高"},
        {"name": "aim_at",   "type": "vec3",   "default": [0, 0, 1.5], "description": "相机对准点"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _H = float({{height}})\n    _AIM = {{aim_at|json}}\n\n    metal = bpy.data.materials.new(_NAME + '_metal')\n    metal.use_nodes = True\n    b = metal.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.10, 0.10, 0.10, 1.0)\n    if b and 'Metallic' in b.inputs:\n        b.inputs['Metallic'].default_value = 0.5\n\n    # 3 脚\n    for i in range(3):\n        ang = i * 2 * math.pi / 3\n        ex = math.cos(ang) * 0.5\n        ey = math.sin(ang) * 0.5\n        bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=_H, vertices=8, location=(_LOC[0] + ex * 0.5, _LOC[1] + ey * 0.5, _LOC[2] + _H * 0.5))\n        lg = bpy.context.object; lg.name = _NAME + '_leg_' + str(i + 1)\n        lg.rotation_euler = (math.radians(15) * math.sin(ang), -math.radians(15) * math.cos(ang), 0)\n        lg.data.materials.append(metal)\n\n    # 云台\n    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, segments=16, ring_count=8, location=(_LOC[0], _LOC[1], _LOC[2] + _H + 0.04))\n    head = bpy.context.object; head.name = _NAME + '_head'\n    bpy.ops.object.shade_smooth()\n    head.data.materials.append(metal)\n\n    # 相机机身\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] + _H + 0.13))\n    body = bpy.context.object; body.name = _NAME + '_camera_body'\n    body.scale = (0.14, 0.10, 0.10)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bv = body.modifiers.new('Bev', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.005; bv.segments = 2\n    body.data.materials.append(metal)\n\n    # 镜头\n    bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=0.10, vertices=20, location=(_LOC[0], _LOC[1] + 0.10, _LOC[2] + _H + 0.13))\n    lens = bpy.context.object; lens.name = _NAME + '_lens'\n    lens.rotation_euler = (math.radians(90), 0, 0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    bpy.ops.object.shade_smooth()\n    lens.data.materials.append(metal)\n\n    # 真实 Blender Camera\n    bpy.ops.object.camera_add(location=(_LOC[0], _LOC[1] + 0.08, _LOC[2] + _H + 0.13))\n    cam = bpy.context.object; cam.name = _NAME + '_render_cam'\n    cam.data.lens = 50\n    # Track To AIM\n    bpy.ops.object.empty_add(type='PLAIN_AXES', location=tuple(_AIM))\n    target = bpy.context.object; target.name = _NAME + '_aim'\n    con = cam.constraints.new('TRACK_TO')\n    con.target = target\n    con.track_axis = 'TRACK_NEGATIVE_Z'\n    con.up_axis = 'UP_Y'\n    bpy.context.scene.camera = cam\n    print('[apply_template] studio_tripod_camera 完成（已 set as scene camera）')\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_tripod_camera 失败:', _e); traceback.print_exc()\n"
})

# 52. studio_product_acrylic 亚克力产品托台
TEMPLATES.append({
    "name": "studio_product_acrylic",
    "title": "亚克力产品托台（透明拱形 + 顶面磨砂）",
    "category": "studio",
    "description": "U 形拱（plane + bend modifier） + 顶面磨砂亚克力 + 高 IOR 透射，常用于产品摄影站位。",
    "params": [
        {"name": "name",     "type": "string", "default": "Acrylic", "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "size",     "type": "float",  "default": 0.5,       "description": "边长"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b:\n        if 'Base Color' in b.inputs:\n            b.inputs['Base Color'].default_value = (0.95, 0.97, 1.0, 1.0)\n        if 'Roughness' in b.inputs:\n            b.inputs['Roughness'].default_value = 0.05\n        for k in ['Transmission Weight', 'Transmission']:\n            if k in b.inputs:\n                b.inputs[k].default_value = 0.95\n                break\n        if 'IOR' in b.inputs:\n            b.inputs['IOR'].default_value = 1.49\n\n    # 顶部 plane（产品台面）\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=(_LOC[0], _LOC[1], _LOC[2] + _S * 0.6))\n    top = bpy.context.object; top.name = _NAME + '_top'\n    top.data.materials.append(mat)\n    # 前后侧面（U 形支撑）\n    for sy in [-1, 1]:\n        bpy.ops.mesh.primitive_plane_add(size=1, location=(_LOC[0], _LOC[1] + sy * _S * 0.5, _LOC[2] + _S * 0.3))\n        side = bpy.context.object; side.name = _NAME + '_side'\n        side.rotation_euler = (math.radians(90), 0, 0)\n        side.scale = (_S, _S * 0.6, 1.0)\n        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)\n        side.data.materials.append(mat)\n    print('[apply_template] studio_product_acrylic 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_product_acrylic 失败:', _e); traceback.print_exc()\n"
})

# 53. studio_grid_ceiling 天花格栅
TEMPLATES.append({
    "name": "studio_grid_ceiling",
    "title": "天花格栅（横竖 cube Array 组成网格）",
    "category": "studio",
    "description": "棚顶悬挂式格栅（用于挂柔光灯具），Array 横竖各 N 根 + 上方支架。",
    "params": [
        {"name": "name",     "type": "string", "default": "Grid",    "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 4.0], "description": "格栅中心高度"},
        {"name": "size",     "type": "float",  "default": 6.0,       "description": "格栅总边长"},
        {"name": "spacing",  "type": "float",  "default": 0.5,       "description": "网格间距（米）"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _SP = float({{spacing}})\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.10, 0.10, 0.10, 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.5\n\n    n = max(2, int(_S / _SP))\n    # 横向条\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1] - _S * 0.5 + _SP * 0.5, _LOC[2]))\n    h = bpy.context.object; h.name = _NAME + '_h'\n    h.scale = (_S, 0.04, 0.04)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    arr = h.modifiers.new('Arr', 'ARRAY')\n    arr.use_relative_offset = False\n    arr.use_constant_offset = True\n    arr.constant_offset_displace = (0, _SP, 0)\n    arr.count = n\n    h.data.materials.append(mat)\n    # 纵向条\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0] - _S * 0.5 + _SP * 0.5, _LOC[1], _LOC[2] + 0.05))\n    v = bpy.context.object; v.name = _NAME + '_v'\n    v.scale = (0.04, _S, 0.04)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    arr2 = v.modifiers.new('Arr', 'ARRAY')\n    arr2.use_relative_offset = False\n    arr2.use_constant_offset = True\n    arr2.constant_offset_displace = (_SP, 0, 0)\n    arr2.count = n\n    v.data.materials.append(mat)\n    print('[apply_template] studio_grid_ceiling 完成: ' + str(n) + 'x' + str(n))\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_grid_ceiling 失败:', _e); traceback.print_exc()\n"
})

# 54. studio_smoke_machine 雾机
TEMPLATES.append({
    "name": "studio_smoke_machine",
    "title": "雾机（设备 cube + 体积雾域）",
    "category": "studio",
    "description": "黑色 cube 设备机器（开关按钮 + 出风口） + 旁边一个低密度 Volume domain，模拟舞台烟雾效果。",
    "params": [
        {"name": "name",     "type": "string", "default": "Smoke",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [-2, -2, 0.3], "description": "雾机中心"},
        {"name": "fog_size", "type": "float",  "default": 4.0,       "description": "出雾团边长"},
        {"name": "density",  "type": "float",  "default": 0.10,      "description": "雾密度"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _FS = float({{fog_size}})\n    _D = float({{density}})\n\n    # 机器\n    bpy.ops.mesh.primitive_cube_add(size=1, location=_LOC)\n    box = bpy.context.object; box.name = _NAME + '_box'\n    box.scale = (0.40, 0.30, 0.20)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bv = box.modifiers.new('Bev', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.01; bv.segments = 2\n    box_mat = bpy.data.materials.new(_NAME + '_box_mat')\n    box_mat.use_nodes = True\n    b = box_mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1.0)\n    box.data.materials.append(box_mat)\n\n    # 出风口（小 cylinder 朝前）\n    import math\n    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.05, vertices=12, location=(_LOC[0], _LOC[1] - 0.18, _LOC[2]))\n    out = bpy.context.object; out.name = _NAME + '_outlet'\n    out.rotation_euler = (math.radians(90), 0, 0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    out.data.materials.append(box_mat)\n\n    # 雾域\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1] - _FS * 0.5 - 0.5, _LOC[2] + _FS * 0.3))\n    vol = bpy.context.object; vol.name = _NAME + '_volume'\n    vol.scale = (_FS, _FS, _FS * 0.6)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    vol.display_type = 'WIRE'\n    v_mat = bpy.data.materials.new(_NAME + '_vol_mat')\n    v_mat.use_nodes = True\n    nt = v_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out_n = nt.nodes.new('ShaderNodeOutputMaterial')\n    vs = nt.nodes.new('ShaderNodeVolumeScatter')\n    if 'Density' in vs.inputs:\n        vs.inputs['Density'].default_value = _D\n    if 'Color' in vs.inputs:\n        vs.inputs['Color'].default_value = (1, 1, 1, 1)\n    nt.links.new(vs.outputs['Volume'], out_n.inputs['Volume'])\n    vol.data.materials.append(v_mat)\n    print('[apply_template] studio_smoke_machine 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] studio_smoke_machine 失败:', _e); traceback.print_exc()\n"
})


# ============================================================
# CG 后期特效（10 个）
# ============================================================

# 55. magic_circle ⭐ 地面魔法阵
TEMPLATES.append({
    "name": "magic_circle",
    "title": "地面魔法阵（圆形 plane + 自发光 + alpha 描边）",
    "category": "fx",
    "description": "扁圆 cylinder + 自发光彩色（青/紫/蓝） + 多层缩放叠加营造光环 + 上方点光。",
    "params": [
        {"name": "name",     "type": "string", "default": "Magic",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0.01], "description": "中心"},
        {"name": "radius",   "type": "float",  "default": 1.5,       "description": "魔法阵半径"},
        {"name": "color",    "type": "rgb",    "default": [0.30, 0.85, 1.0], "description": "光色（青蓝）"},
        {"name": "strength", "type": "float",  "default": 12.0,      "description": "自发光强度"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _R = float({{radius}})\n    _C = {{color|json}}\n    _S = float({{strength}})\n\n    em_mat = bpy.data.materials.new(_NAME + '_em_mat')\n    em_mat.use_nodes = True\n    nt = em_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    em = nt.nodes.new('ShaderNodeEmission')\n    if 'Color' in em.inputs:\n        em.inputs['Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Strength' in em.inputs:\n        em.inputs['Strength'].default_value = _S\n    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])\n\n    # 3 层圆环（外、中、内）\n    for i, scale in enumerate([1.0, 0.7, 0.4]):\n        bpy.ops.mesh.primitive_cylinder_add(radius=_R * scale, depth=0.005, vertices=64, location=(_LOC[0], _LOC[1], _LOC[2] + i * 0.001))\n        ring = bpy.context.object; ring.name = _NAME + '_ring_' + str(i + 1)\n        bpy.ops.object.shade_smooth()\n        ring.data.materials.append(em_mat)\n\n    # 顶部点光\n    bpy.ops.object.light_add(type='POINT', location=(_LOC[0], _LOC[1], _LOC[2] + 0.5))\n    lt = bpy.context.object; lt.name = _NAME + '_light'\n    lt.data.energy = 100\n    lt.data.color = (_C[0], _C[1], _C[2])\n    print('[apply_template] magic_circle 完成: r=' + str(_R) + ' strength=' + str(_S))\nexcept Exception as _e:\n    import traceback; print('[apply_template] magic_circle 失败:', _e); traceback.print_exc()\n"
})

# 56. energy_beam 能量光柱
TEMPLATES.append({
    "name": "energy_beam",
    "title": "能量光柱（垂直 cylinder + Emission + 半透）",
    "category": "fx",
    "description": "瘦长 cylinder + 强自发光 + 半透 alpha + 顶部底部 ico_sphere 圆球散点。",
    "params": [
        {"name": "name",     "type": "string", "default": "Beam",    "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "height",   "type": "float",  "default": 6.0,       "description": "光柱高"},
        {"name": "radius",   "type": "float",  "default": 0.20,      "description": "光柱半径"},
        {"name": "color",    "type": "rgb",    "default": [0.80, 0.30, 1.0], "description": "光色（紫粉）"},
        {"name": "strength", "type": "float",  "default": 20.0,      "description": "自发光强度"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _H = float({{height}})\n    _R = float({{radius}})\n    _C = {{color|json}}\n    _S = float({{strength}})\n\n    em_mat = bpy.data.materials.new(_NAME + '_em_mat')\n    em_mat.use_nodes = True\n    nt = em_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    em = nt.nodes.new('ShaderNodeEmission')\n    if 'Color' in em.inputs:\n        em.inputs['Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Strength' in em.inputs:\n        em.inputs['Strength'].default_value = _S\n    tr = nt.nodes.new('ShaderNodeBsdfTransparent')\n    mix = nt.nodes.new('ShaderNodeMixShader')\n    mix.inputs[0].default_value = 0.4\n    nt.links.new(tr.outputs['BSDF'], mix.inputs[1])\n    nt.links.new(em.outputs['Emission'], mix.inputs[2])\n    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])\n    em_mat.blend_method = 'BLEND'\n\n    bpy.ops.mesh.primitive_cylinder_add(radius=_R, depth=_H, vertices=20, location=(_LOC[0], _LOC[1], _LOC[2] + _H * 0.5))\n    obj = bpy.context.object; obj.name = _NAME\n    bpy.ops.object.shade_smooth()\n    obj.data.materials.append(em_mat)\n\n    # 底部+顶部小球（端点能量团）\n    for sz in [0, _H]:\n        bpy.ops.mesh.primitive_uv_sphere_add(radius=_R * 1.5, segments=16, ring_count=8, location=(_LOC[0], _LOC[1], _LOC[2] + sz))\n        bp = bpy.context.object; bp.name = _NAME + '_orb'\n        bpy.ops.object.shade_smooth()\n        bp.data.materials.append(em_mat)\n    print('[apply_template] energy_beam 完成: h=' + str(_H) + ' r=' + str(_R))\nexcept Exception as _e:\n    import traceback; print('[apply_template] energy_beam 失败:', _e); traceback.print_exc()\n"
})

# 57. floating_island ⭐ 浮岛
TEMPLATES.append({
    "name": "floating_island",
    "title": "浮岛（IcoSphere 上扁下尖 + Displace + 草地顶面）",
    "category": "fx",
    "description": "ico_sphere subdivide + Displace Voronoi（顶部 flat，底部尖锥状）+ 顶面草地材质 + 侧面岩石材质。RPG/魔幻必用。",
    "params": [
        {"name": "name",     "type": "string", "default": "Island",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 5.0], "description": "浮岛中心高度"},
        {"name": "size",     "type": "float",  "default": 4.0,       "description": "岛尺寸（顶面直径）"}
    ],
    "code": "import bpy, bmesh\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n\n    # 主体：ico_sphere → 拉伸 Z 上下做出锥状\n    bpy.ops.mesh.primitive_ico_sphere_add(radius=_S * 0.5, subdivisions=4, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    obj.scale = (1.2, 1.2, 0.7)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    # bmesh：底部所有顶点向下拉伸（让底部尖）\n    me = obj.data\n    bm = bmesh.new()\n    bm.from_mesh(me)\n    for v in bm.verts:\n        if v.co.z < -_S * 0.05:\n            v.co.z -= (-v.co.z) * 1.2\n    bm.to_mesh(me); bm.free()\n\n    # Displace 增加岩石细节\n    tex = bpy.data.textures.new(_NAME + '_tex', 'VORONOI')\n    tex.noise_scale = 0.5\n    dm = obj.modifiers.new('Disp', 'DISPLACE')\n    dm.texture = tex\n    dm.strength = _S * 0.05\n    bpy.ops.object.shade_smooth()\n\n    # 材质（带顶面草地）\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    nt = mat.node_tree\n    bsdf = nt.nodes.get('Principled BSDF')\n    # 顶面绿色，侧面棕色，用 Z 坐标驱动 ColorRamp\n    coord = nt.nodes.new('ShaderNodeTexCoord')\n    sep = nt.nodes.new('ShaderNodeSeparateXYZ')\n    cr = nt.nodes.new('ShaderNodeValToRGB')\n    cr.color_ramp.elements[0].position = 0.4\n    cr.color_ramp.elements[0].color = (0.30, 0.18, 0.10, 1)\n    cr.color_ramp.elements[1].position = 0.65\n    cr.color_ramp.elements[1].color = (0.20, 0.50, 0.15, 1)\n    nt.links.new(coord.outputs['Generated'], sep.inputs['Vector'])\n    nt.links.new(sep.outputs['Z'], cr.inputs['Fac'])\n    if bsdf and 'Base Color' in bsdf.inputs:\n        nt.links.new(cr.outputs['Color'], bsdf.inputs['Base Color'])\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.85\n    obj.data.materials.append(mat)\n    print('[apply_template] floating_island 完成: size=' + str(_S))\nexcept Exception as _e:\n    import traceback; print('[apply_template] floating_island 失败:', _e); traceback.print_exc()\n"
})

# 58. crystal_cluster 水晶簇
TEMPLATES.append({
    "name": "crystal_cluster",
    "title": "水晶簇（多个 cone 簇拥 + 透射 BSDF）",
    "category": "fx",
    "description": "5~9 根六棱锥（cone vertices=6）随机角度站立 + 半透紫色 BSDF + IOR 1.55，魔幻奇幻 must-have。",
    "params": [
        {"name": "name",     "type": "string", "default": "Crystal", "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "count",    "type": "int",    "default": 7,         "description": "水晶柱数量"},
        {"name": "size",     "type": "float",  "default": 0.4,       "description": "整体半径"},
        {"name": "color",    "type": "rgb",    "default": [0.55, 0.30, 0.95], "description": "水晶色"}
    ],
    "code": "import bpy, math, random\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _N = max(1, int({{count}}))\n    _S = float({{size}})\n    _C = {{color|json}}\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b:\n        if 'Base Color' in b.inputs:\n            b.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n        if 'Roughness' in b.inputs:\n            b.inputs['Roughness'].default_value = 0.05\n        for k in ['Transmission Weight', 'Transmission']:\n            if k in b.inputs:\n                b.inputs[k].default_value = 0.85\n                break\n        if 'IOR' in b.inputs:\n            b.inputs['IOR'].default_value = 1.55\n        # 微自发光\n        if 'Emission' in b.inputs:\n            b.inputs['Emission'].default_value = (_C[0], _C[1], _C[2], 1.0)\n        elif 'Emission Color' in b.inputs:\n            b.inputs['Emission Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n        if 'Emission Strength' in b.inputs:\n            b.inputs['Emission Strength'].default_value = 1.0\n\n    for i in range(_N):\n        ang = i * 2 * math.pi / _N + random.random() * 0.3\n        r = random.random() * _S * 0.7\n        x = _LOC[0] + math.cos(ang) * r\n        y = _LOC[1] + math.sin(ang) * r\n        h = _S * (1.0 + random.random() * 1.0)\n        bpy.ops.mesh.primitive_cone_add(radius1=_S * 0.12 * (0.7 + random.random() * 0.6), radius2=_S * 0.04, depth=h, vertices=6, location=(x, y, _LOC[2] + h * 0.5))\n        cr = bpy.context.object; cr.name = _NAME + '_' + str(i + 1)\n        cr.rotation_euler = ((random.random() - 0.5) * 0.4, (random.random() - 0.5) * 0.4, random.random() * math.pi)\n        cr.data.materials.append(mat)\n    print('[apply_template] crystal_cluster 完成: ' + str(_N) + ' 根水晶')\nexcept Exception as _e:\n    import traceback; print('[apply_template] crystal_cluster 失败:', _e); traceback.print_exc()\n"
})

# 59. broken_floor_crack 地面裂痕
TEMPLATES.append({
    "name": "broken_floor_crack",
    "title": "地面裂痕（Plane subdivide + Voronoi Displace 凹陷）",
    "category": "fx",
    "description": "地面 plane + Voronoi 边缘距离 → Displace 朝下凹陷一条裂缝，再叠红色自发光（仅裂缝内）模拟岩浆/能量。",
    "params": [
        {"name": "name",     "type": "string", "default": "Crack",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "地面中心"},
        {"name": "size",     "type": "float",  "default": 6.0,       "description": "地面边长"},
        {"name": "lava",     "type": "boolean","default": True,      "description": "裂缝是否发红光（lava）"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _S = float({{size}})\n    _L = bool({{lava}})\n\n    bpy.ops.mesh.primitive_plane_add(size=_S, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    bpy.ops.mesh.subdivide(number_cuts=50)\n    bpy.ops.object.mode_set(mode='OBJECT')\n    tex = bpy.data.textures.new(_NAME + '_tex', 'VORONOI')\n    tex.distance_metric = 'DISTANCE_SQUARED'\n    tex.noise_scale = 0.6\n    dm = obj.modifiers.new('Disp', 'DISPLACE')\n    dm.texture = tex\n    dm.strength = -0.15\n    dm.mid_level = 0.0\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    nt = mat.node_tree\n    bsdf = nt.nodes.get('Principled BSDF')\n    if bsdf and 'Base Color' in bsdf.inputs:\n        bsdf.inputs['Base Color'].default_value = (0.20, 0.18, 0.16, 1.0)\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.9\n    if _L:\n        # Voronoi 边缘 → ColorRamp → Emission Mix\n        vor = nt.nodes.new('ShaderNodeTexVoronoi')\n        vor.feature = 'DISTANCE_TO_EDGE'\n        vor.inputs['Scale'].default_value = 4.0\n        cr = nt.nodes.new('ShaderNodeValToRGB')\n        cr.color_ramp.elements[0].color = (1.0, 0.30, 0.05, 1)\n        cr.color_ramp.elements[1].color = (0.05, 0.04, 0.04, 1)\n        cr.color_ramp.elements[0].position = 0.0\n        cr.color_ramp.elements[1].position = 0.05\n        nt.links.new(vor.outputs['Distance'], cr.inputs['Fac'])\n        if bsdf and 'Base Color' in bsdf.inputs:\n            nt.links.new(cr.outputs['Color'], bsdf.inputs['Base Color'])\n        # Emission：bsdf 4.x 自带 Emission 输入\n        em_cr = nt.nodes.new('ShaderNodeValToRGB')\n        em_cr.color_ramp.elements[0].color = (1.0, 0.30, 0.05, 1)\n        em_cr.color_ramp.elements[1].color = (0, 0, 0, 1)\n        em_cr.color_ramp.elements[0].position = 0.0\n        em_cr.color_ramp.elements[1].position = 0.05\n        nt.links.new(vor.outputs['Distance'], em_cr.inputs['Fac'])\n        for k in ['Emission', 'Emission Color']:\n            if bsdf and k in bsdf.inputs:\n                nt.links.new(em_cr.outputs['Color'], bsdf.inputs[k])\n                break\n        if bsdf and 'Emission Strength' in bsdf.inputs:\n            bsdf.inputs['Emission Strength'].default_value = 8.0\n    obj.data.materials.append(mat)\n    print('[apply_template] broken_floor_crack 完成: lava=' + str(_L))\nexcept Exception as _e:\n    import traceback; print('[apply_template] broken_floor_crack 失败:', _e); traceback.print_exc()\n"
})

# 60. floating_runes 飘浮符文
TEMPLATES.append({
    "name": "floating_runes",
    "title": "飘浮符文（多个小 plane + 自发光 + 浮空环绕）",
    "category": "fx",
    "description": "多个微小 plane 圆形排列 + 强自发光 + 不同高度浮空，模拟魔法符文圈。",
    "params": [
        {"name": "name",     "type": "string", "default": "Runes",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 1.5], "description": "圈中心"},
        {"name": "count",    "type": "int",    "default": 8,         "description": "符文数量"},
        {"name": "radius",   "type": "float",  "default": 1.2,       "description": "圈半径"},
        {"name": "color",    "type": "rgb",    "default": [0.20, 0.85, 0.95], "description": "符文光色"}
    ],
    "code": "import bpy, math, random\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _N = max(1, int({{count}}))\n    _R = float({{radius}})\n    _C = {{color|json}}\n\n    em_mat = bpy.data.materials.new(_NAME + '_em_mat')\n    em_mat.use_nodes = True\n    nt = em_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    em = nt.nodes.new('ShaderNodeEmission')\n    if 'Color' in em.inputs:\n        em.inputs['Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Strength' in em.inputs:\n        em.inputs['Strength'].default_value = 8.0\n    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])\n\n    for i in range(_N):\n        ang = i * 2 * math.pi / _N\n        x = _LOC[0] + math.cos(ang) * _R\n        y = _LOC[1] + math.sin(ang) * _R\n        z = _LOC[2] + (random.random() - 0.5) * 0.4\n        bpy.ops.mesh.primitive_plane_add(size=0.18, location=(x, y, z))\n        rn = bpy.context.object; rn.name = _NAME + '_' + str(i + 1)\n        rn.rotation_euler = (math.radians(90), 0, ang)\n        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n        rn.data.materials.append(em_mat)\n    print('[apply_template] floating_runes 完成: ' + str(_N) + ' 个符文')\nexcept Exception as _e:\n    import traceback; print('[apply_template] floating_runes 失败:', _e); traceback.print_exc()\n"
})

# 61. portal_swirl 传送门漩涡
TEMPLATES.append({
    "name": "portal_swirl",
    "title": "传送门漩涡（圆环 cylinder + 漩涡 plane + 自发光）",
    "category": "fx",
    "description": "外圈圆环（torus 扁） + 中央漩涡 plane（半透螺旋色）+ 内部 Point Light。",
    "params": [
        {"name": "name",     "type": "string", "default": "Portal",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 1.5], "description": "中心"},
        {"name": "radius",   "type": "float",  "default": 0.9,       "description": "门半径"},
        {"name": "color",    "type": "rgb",    "default": [0.30, 0.60, 1.0], "description": "门光色"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _R = float({{radius}})\n    _C = {{color|json}}\n\n    em_mat = bpy.data.materials.new(_NAME + '_em_mat')\n    em_mat.use_nodes = True\n    nt = em_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    em = nt.nodes.new('ShaderNodeEmission')\n    if 'Color' in em.inputs:\n        em.inputs['Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Strength' in em.inputs:\n        em.inputs['Strength'].default_value = 8.0\n    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])\n\n    # 外圈\n    bpy.ops.mesh.primitive_torus_add(major_radius=_R, minor_radius=_R * 0.05, major_segments=48, minor_segments=8, location=_LOC)\n    ring = bpy.context.object; ring.name = _NAME + '_ring'\n    ring.rotation_euler = (math.radians(90), 0, 0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    bpy.ops.object.shade_smooth()\n    ring.data.materials.append(em_mat)\n\n    # 中央 plane\n    bpy.ops.mesh.primitive_circle_add(radius=_R * 0.95, vertices=48, fill_type='NGON', location=_LOC)\n    pl = bpy.context.object; pl.name = _NAME + '_swirl'\n    pl.rotation_euler = (math.radians(90), 0, 0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    # 漩涡材质（用 Wave + Mapping rotate）\n    sw_mat = bpy.data.materials.new(_NAME + '_sw_mat')\n    sw_mat.use_nodes = True\n    nt2 = sw_mat.node_tree\n    for n in list(nt2.nodes):\n        nt2.nodes.remove(n)\n    out2 = nt2.nodes.new('ShaderNodeOutputMaterial')\n    em2 = nt2.nodes.new('ShaderNodeEmission')\n    if 'Color' in em2.inputs:\n        em2.inputs['Color'].default_value = (_C[0] * 0.5, _C[1] * 0.5, _C[2], 1.0)\n    if 'Strength' in em2.inputs:\n        em2.inputs['Strength'].default_value = 5.0\n    coord = nt2.nodes.new('ShaderNodeTexCoord')\n    map_n = nt2.nodes.new('ShaderNodeMapping')\n    wave = nt2.nodes.new('ShaderNodeTexWave')\n    wave.wave_type = 'RINGS'\n    wave.inputs['Scale'].default_value = 4.0\n    wave.inputs['Distortion'].default_value = 5.0\n    nt2.links.new(coord.outputs['Object'], map_n.inputs['Vector'])\n    nt2.links.new(map_n.outputs['Vector'], wave.inputs['Vector'])\n    nt2.links.new(wave.outputs['Color'], em2.inputs['Color'])\n    nt2.links.new(em2.outputs['Emission'], out2.inputs['Surface'])\n    pl.data.materials.append(sw_mat)\n\n    bpy.ops.object.light_add(type='POINT', location=_LOC)\n    lt = bpy.context.object; lt.name = _NAME + '_light'\n    lt.data.energy = 200\n    lt.data.color = (_C[0], _C[1], _C[2])\n    print('[apply_template] portal_swirl 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] portal_swirl 失败:', _e); traceback.print_exc()\n"
})

# 62. lightning_bolt 闪电
TEMPLATES.append({
    "name": "lightning_bolt",
    "title": "闪电（多段 cylinder 折线 + 强白色自发光）",
    "category": "fx",
    "description": "用 5~7 段细 cylinder 拼成 zigzag 折线 + 极强白色 emission，最后头尾各加发光球。",
    "params": [
        {"name": "name",     "type": "string", "default": "Bolt",    "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 4.0], "description": "起点（高空）"},
        {"name": "length",   "type": "float",  "default": 4.0,       "description": "总长"},
        {"name": "color",    "type": "rgb",    "default": [0.85, 0.92, 1.0], "description": "电光色（蓝白）"}
    ],
    "code": "import bpy, math, random\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _L = float({{length}})\n    _C = {{color|json}}\n\n    em_mat = bpy.data.materials.new(_NAME + '_em_mat')\n    em_mat.use_nodes = True\n    nt = em_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    em = nt.nodes.new('ShaderNodeEmission')\n    if 'Color' in em.inputs:\n        em.inputs['Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Strength' in em.inputs:\n        em.inputs['Strength'].default_value = 25.0\n    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])\n\n    n_seg = 6\n    pts = [(_LOC[0], _LOC[1], _LOC[2])]\n    for i in range(n_seg):\n        prev = pts[-1]\n        dx = (random.random() - 0.5) * 0.3\n        dy = (random.random() - 0.5) * 0.3\n        dz = -_L / n_seg\n        pts.append((prev[0] + dx, prev[1] + dy, prev[2] + dz))\n    for i in range(n_seg):\n        x1, y1, z1 = pts[i]\n        x2, y2, z2 = pts[i + 1]\n        mx, my, mz = (x1 + x2) / 2, (y1 + y2) / 2, (z1 + z2) / 2\n        dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)\n        bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=dist, vertices=6, location=(mx, my, mz))\n        seg = bpy.context.object; seg.name = _NAME + '_seg_' + str(i + 1)\n        # 朝向\n        from mathutils import Vector\n        direction = Vector((x2 - x1, y2 - y1, z2 - z1))\n        seg.rotation_euler = direction.to_track_quat('Z', 'X').to_euler()\n        seg.data.materials.append(em_mat)\n    print('[apply_template] lightning_bolt 完成: ' + str(n_seg) + ' 段')\nexcept Exception as _e:\n    import traceback; print('[apply_template] lightning_bolt 失败:', _e); traceback.print_exc()\n"
})

# 63. ribbon_streamer 缎带飘动
TEMPLATES.append({
    "name": "ribbon_streamer",
    "title": "缎带飘动（长 plane + Wave + Curve modifier）",
    "category": "fx",
    "description": "瘦长 plane 高细分 + Wave 让其波浪化 + Subsurf 平滑，模拟飘动的缎带 / 火影查克拉带。",
    "params": [
        {"name": "name",     "type": "string", "default": "Ribbon",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 1.5], "description": "中心"},
        {"name": "length",   "type": "float",  "default": 4.0,       "description": "缎带长度"},
        {"name": "width",    "type": "float",  "default": 0.15,      "description": "缎带宽度"},
        {"name": "color",    "type": "rgb",    "default": [0.95, 0.20, 0.30], "description": "缎带色"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _L = float({{length}})\n    _W = float({{width}})\n    _C = {{color|json}}\n\n    bpy.ops.mesh.primitive_plane_add(size=1, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    obj.scale = (_L, _W, 1.0)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    bpy.ops.mesh.subdivide(number_cuts=40)\n    bpy.ops.object.mode_set(mode='OBJECT')\n\n    wave = obj.modifiers.new('Wave', 'WAVE')\n    wave.use_x = True; wave.use_y = False\n    wave.height = 0.20\n    wave.width = 0.40\n    wave.speed = 0\n    sub = obj.modifiers.new('Sub', 'SUBSURF')\n    sub.levels = 2\n    bpy.ops.object.shade_smooth()\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.5\n    obj.data.materials.append(mat)\n    print('[apply_template] ribbon_streamer 完成: ' + str(_L) + 'x' + str(_W))\nexcept Exception as _e:\n    import traceback; print('[apply_template] ribbon_streamer 失败:', _e); traceback.print_exc()\n"
})

# 64. spell_aura 法术光环
TEMPLATES.append({
    "name": "spell_aura",
    "title": "法术光环（球壳 + 自发光半透 + 多层叠加）",
    "category": "fx",
    "description": "围绕角色脚下的球壳光环，多层 ico_sphere 缩放叠加 + 自发光 + 半透。",
    "params": [
        {"name": "name",     "type": "string", "default": "Aura",    "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 1.0], "description": "中心"},
        {"name": "radius",   "type": "float",  "default": 0.8,       "description": "光环半径"},
        {"name": "color",    "type": "rgb",    "default": [1.0, 0.30, 0.10], "description": "光环色"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _R = float({{radius}})\n    _C = {{color|json}}\n\n    em_mat = bpy.data.materials.new(_NAME + '_em_mat')\n    em_mat.use_nodes = True\n    nt = em_mat.node_tree\n    for n in list(nt.nodes):\n        nt.nodes.remove(n)\n    out = nt.nodes.new('ShaderNodeOutputMaterial')\n    em = nt.nodes.new('ShaderNodeEmission')\n    if 'Color' in em.inputs:\n        em.inputs['Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if 'Strength' in em.inputs:\n        em.inputs['Strength'].default_value = 4.0\n    tr = nt.nodes.new('ShaderNodeBsdfTransparent')\n    mix = nt.nodes.new('ShaderNodeMixShader')\n    mix.inputs[0].default_value = 0.7\n    nt.links.new(tr.outputs['BSDF'], mix.inputs[1])\n    nt.links.new(em.outputs['Emission'], mix.inputs[2])\n    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])\n    em_mat.blend_method = 'BLEND'\n\n    for i, scale in enumerate([1.0, 0.85, 0.7]):\n        bpy.ops.mesh.primitive_uv_sphere_add(radius=_R * scale, segments=24, ring_count=12, location=_LOC)\n        sp = bpy.context.object; sp.name = _NAME + '_layer_' + str(i + 1)\n        bpy.ops.object.shade_smooth()\n        sp.data.materials.append(em_mat)\n    print('[apply_template] spell_aura 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] spell_aura 失败:', _e); traceback.print_exc()\n"
})


# ============================================================
# 建筑/废墟（6 个）
# ============================================================

# 65. ruined_pillar 残破石柱
TEMPLATES.append({
    "name": "ruined_pillar",
    "title": "残破石柱（cylinder 顶部断裂 + Voronoi Displace 风化）",
    "category": "architecture",
    "description": "cylinder 主体 + 顶部用 bisect 切斜面（断裂感） + Voronoi 噪波 Displace 表面风化 + 灰白石材。",
    "params": [
        {"name": "name",     "type": "string", "default": "Pillar",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "height",   "type": "float",  "default": 3.0,       "description": "残柱高度"},
        {"name": "radius",   "type": "float",  "default": 0.30,      "description": "柱半径"}
    ],
    "code": "import bpy, math, random\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _H = float({{height}})\n    _R = float({{radius}})\n\n    bpy.ops.mesh.primitive_cylinder_add(radius=_R, depth=_H, vertices=20, location=(_LOC[0], _LOC[1], _LOC[2] + _H * 0.5))\n    obj = bpy.context.object; obj.name = _NAME\n    bpy.ops.object.shade_smooth()\n    # Voronoi 风化\n    tex = bpy.data.textures.new(_NAME + '_tex', 'VORONOI')\n    tex.noise_scale = 0.4\n    dm = obj.modifiers.new('Disp', 'DISPLACE')\n    dm.texture = tex\n    dm.strength = _R * 0.15\n    # 顶部断裂感：用 Edit mode bisect\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    angle = random.random() * 0.4 - 0.2\n    bpy.ops.mesh.bisect(plane_co=(0, 0, _H * 0.95), plane_no=(angle, angle, 1), use_fill=True, clear_outer=True)\n    bpy.ops.object.mode_set(mode='OBJECT')\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.65, 0.62, 0.55, 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.92\n    obj.data.materials.append(mat)\n    print('[apply_template] ruined_pillar 完成: h=' + str(_H))\nexcept Exception as _e:\n    import traceback; print('[apply_template] ruined_pillar 失败:', _e); traceback.print_exc()\n"
})

# 66. medieval_castle_tower 中世纪塔楼
TEMPLATES.append({
    "name": "medieval_castle_tower",
    "title": "中世纪塔楼（圆柱主体 + 锥顶 + 雉堞 + 窗孔）",
    "category": "architecture",
    "description": "圆柱主体（高） + 顶部锥形屋顶 + 一圈方形雉堞（cube Array 绕圆环） + 几个矩形窗孔。",
    "params": [
        {"name": "name",     "type": "string", "default": "Tower",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "height",   "type": "float",  "default": 8.0,       "description": "塔身高"},
        {"name": "radius",   "type": "float",  "default": 1.5,       "description": "塔半径"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _H = float({{height}})\n    _R = float({{radius}})\n\n    stone = bpy.data.materials.new(_NAME + '_stone')\n    stone.use_nodes = True\n    b = stone.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.55, 0.50, 0.45, 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.9\n\n    roof = bpy.data.materials.new(_NAME + '_roof')\n    roof.use_nodes = True\n    br = roof.node_tree.nodes.get('Principled BSDF')\n    if br and 'Base Color' in br.inputs:\n        br.inputs['Base Color'].default_value = (0.30, 0.18, 0.12, 1.0)\n\n    # 主体\n    bpy.ops.mesh.primitive_cylinder_add(radius=_R, depth=_H, vertices=24, location=(_LOC[0], _LOC[1], _LOC[2] + _H * 0.5))\n    body = bpy.context.object; body.name = _NAME + '_body'\n    bpy.ops.object.shade_smooth()\n    body.data.materials.append(stone)\n\n    # 锥顶\n    bpy.ops.mesh.primitive_cone_add(radius1=_R * 1.1, radius2=0, depth=_R * 1.5, vertices=24, location=(_LOC[0], _LOC[1], _LOC[2] + _H + _R * 0.75))\n    cone = bpy.context.object; cone.name = _NAME + '_roof'\n    bpy.ops.object.shade_smooth()\n    cone.data.materials.append(roof)\n\n    # 雉堞（一圈小 cube）\n    for i in range(12):\n        ang = i * 2 * math.pi / 12\n        x = _LOC[0] + math.cos(ang) * _R\n        y = _LOC[1] + math.sin(ang) * _R\n        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, _LOC[2] + _H + 0.15))\n        c = bpy.context.object; c.name = _NAME + '_battle_' + str(i + 1)\n        c.scale = (0.20, 0.20, 0.30)\n        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n        c.data.materials.append(stone)\n    print('[apply_template] medieval_castle_tower 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] medieval_castle_tower 失败:', _e); traceback.print_exc()\n"
})

# 67. wooden_house_facade 木屋立面
TEMPLATES.append({
    "name": "wooden_house_facade",
    "title": "木屋立面（墙体 + 三角屋顶 + 门 + 2 窗）",
    "category": "architecture",
    "description": "矩形墙体（3D cube） + 山墙顶（三角棱柱实现） + 居中门（cube 凹陷） + 左右两扇方窗（带十字木条）。",
    "params": [
        {"name": "name",     "type": "string", "default": "House",   "description": "对象名前缀"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "墙底中心"},
        {"name": "width",    "type": "float",  "default": 4.0,       "description": "宽 X"},
        {"name": "depth",    "type": "float",  "default": 3.0,       "description": "深 Y"},
        {"name": "wall_h",   "type": "float",  "default": 2.5,       "description": "墙高"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _W = float({{width}})\n    _D = float({{depth}})\n    _H = float({{wall_h}})\n\n    wall_mat = bpy.data.materials.new(_NAME + '_wall')\n    wall_mat.use_nodes = True\n    b = wall_mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (0.65, 0.50, 0.35, 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.75\n\n    roof_mat = bpy.data.materials.new(_NAME + '_roof')\n    roof_mat.use_nodes = True\n    br = roof_mat.node_tree.nodes.get('Principled BSDF')\n    if br and 'Base Color' in br.inputs:\n        br.inputs['Base Color'].default_value = (0.30, 0.20, 0.15, 1.0)\n\n    # 墙体\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1], _LOC[2] + _H * 0.5))\n    wall = bpy.context.object; wall.name = _NAME + '_wall'\n    wall.scale = (_W, _D, _H)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    wall.data.materials.append(wall_mat)\n\n    # 屋顶（三棱柱：用 cube + bisect 简化为 cone radius1 长方形版）\n    # 这里用 2 个倾斜 plane 拼山墙顶\n    roof_h = _W * 0.4\n    # 顶左右斜面\n    for sx in [-1, 1]:\n        bpy.ops.mesh.primitive_plane_add(size=1, location=(_LOC[0] + sx * _W * 0.25, _LOC[1], _LOC[2] + _H + roof_h * 0.5))\n        r = bpy.context.object; r.name = _NAME + '_roof_' + ('R' if sx > 0 else 'L')\n        r.rotation_euler = (0, sx * math.atan(roof_h / (_W * 0.5)), 0)\n        r.scale = (_W * 0.55, _D + 0.3, 1.0)\n        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)\n        r.data.materials.append(roof_mat)\n\n    # 门\n    door_w = 0.8; door_h = 1.9\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1] - _D * 0.5 - 0.005, _LOC[2] + door_h * 0.5))\n    door = bpy.context.object; door.name = _NAME + '_door'\n    door.scale = (door_w, 0.04, door_h)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    door_mat = bpy.data.materials.new(_NAME + '_door_mat')\n    door_mat.use_nodes = True\n    bd = door_mat.node_tree.nodes.get('Principled BSDF')\n    if bd and 'Base Color' in bd.inputs:\n        bd.inputs['Base Color'].default_value = (0.30, 0.20, 0.12, 1.0)\n    door.data.materials.append(door_mat)\n\n    # 2 窗\n    win_mat = bpy.data.materials.new(_NAME + '_win_mat')\n    win_mat.use_nodes = True\n    bw = win_mat.node_tree.nodes.get('Principled BSDF')\n    if bw and 'Base Color' in bw.inputs:\n        bw.inputs['Base Color'].default_value = (0.85, 0.92, 0.98, 1.0)\n    if bw and 'Roughness' in bw.inputs:\n        bw.inputs['Roughness'].default_value = 0.05\n    for sx in [-1, 1]:\n        bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0] + sx * _W * 0.32, _LOC[1] - _D * 0.5 - 0.005, _LOC[2] + _H * 0.55))\n        wn = bpy.context.object; wn.name = _NAME + '_win_' + ('R' if sx > 0 else 'L')\n        wn.scale = (0.6, 0.04, 0.6)\n        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n        wn.data.materials.append(win_mat)\n    print('[apply_template] wooden_house_facade 完成')\nexcept Exception as _e:\n    import traceback; print('[apply_template] wooden_house_facade 失败:', _e); traceback.print_exc()\n"
})

# 68. brick_wall_aged 老旧砖墙
TEMPLATES.append({
    "name": "brick_wall_aged",
    "title": "老旧砖墙（Plane + Brick Texture + Bump + 锈色）",
    "category": "architecture",
    "description": "立式 plane + 程序化 Brick Texture（节点） + Bump 让砖缝凹陷 + 锈红/灰色调。",
    "params": [
        {"name": "name",     "type": "string", "default": "BrickWall","description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 1.4], "description": "墙中心"},
        {"name": "width",    "type": "float",  "default": 5.0,       "description": "墙宽"},
        {"name": "height",   "type": "float",  "default": 2.8,       "description": "墙高"},
        {"name": "thickness","type": "float",  "default": 0.2,       "description": "墙厚"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _W = float({{width}})\n    _H = float({{height}})\n    _T = float({{thickness}})\n\n    bpy.ops.mesh.primitive_cube_add(size=1, location=_LOC)\n    obj = bpy.context.object; obj.name = _NAME\n    obj.scale = (_W, _T, _H)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    nt = mat.node_tree\n    bsdf = nt.nodes.get('Principled BSDF')\n    brick = nt.nodes.new('ShaderNodeTexBrick')\n    brick.inputs['Color1'].default_value = (0.55, 0.30, 0.22, 1)\n    brick.inputs['Color2'].default_value = (0.50, 0.28, 0.20, 1)\n    brick.inputs['Mortar'].default_value = (0.40, 0.40, 0.38, 1)\n    brick.inputs['Scale'].default_value = 8.0\n    brick.inputs['Mortar Size'].default_value = 0.025\n    if bsdf and 'Base Color' in bsdf.inputs:\n        nt.links.new(brick.outputs['Color'], bsdf.inputs['Base Color'])\n    if bsdf and 'Roughness' in bsdf.inputs:\n        bsdf.inputs['Roughness'].default_value = 0.92\n    bump = nt.nodes.new('ShaderNodeBump')\n    bump.inputs['Strength'].default_value = 0.5\n    nt.links.new(brick.outputs['Fac'], bump.inputs['Height'])\n    if bsdf and 'Normal' in bsdf.inputs:\n        nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])\n    obj.data.materials.append(mat)\n    print('[apply_template] brick_wall_aged 完成: ' + str(_W) + 'x' + str(_H) + 'm')\nexcept Exception as _e:\n    import traceback; print('[apply_template] brick_wall_aged 失败:', _e); traceback.print_exc()\n"
})

# 69. roof_tiles 屋顶瓦片
TEMPLATES.append({
    "name": "roof_tiles",
    "title": "屋顶瓦片（半圆 cylinder Array X+Y）",
    "category": "architecture",
    "description": "半圆形瓦片（cylinder vertices=8 横置裁半） + Array 双向重复，赤陶红色。",
    "params": [
        {"name": "name",     "type": "string", "default": "Tiles",   "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 3.0], "description": "瓦面中心"},
        {"name": "width",    "type": "float",  "default": 4.0,       "description": "瓦面宽 X"},
        {"name": "depth",    "type": "float",  "default": 3.0,       "description": "瓦面深 Y"},
        {"name": "color",    "type": "rgb",    "default": [0.65, 0.30, 0.20], "description": "瓦色"}
    ],
    "code": "import bpy, math\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _W = float({{width}})\n    _D = float({{depth}})\n    _C = {{color|json}}\n\n    tile_w = 0.10\n    tile_d = 0.30\n    nx = max(1, int(_W / tile_w))\n    ny = max(1, int(_D / tile_d))\n\n    bpy.ops.mesh.primitive_cylinder_add(radius=tile_w * 0.5, depth=tile_d, vertices=10, location=(_LOC[0] - _W * 0.5 + tile_w * 0.5, _LOC[1] - _D * 0.5 + tile_d * 0.5, _LOC[2] + tile_w * 0.25))\n    tile = bpy.context.object; tile.name = _NAME + '_tile'\n    tile.rotation_euler = (math.radians(90), 0, 0)\n    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)\n    bpy.ops.object.shade_smooth()\n    # 用 Edit bisect 切掉下半（只保留拱面）\n    bpy.ops.object.mode_set(mode='EDIT')\n    bpy.ops.mesh.select_all(action='SELECT')\n    bpy.ops.mesh.bisect(plane_co=(_LOC[0] - _W * 0.5 + tile_w * 0.5, _LOC[1] - _D * 0.5 + tile_d * 0.5, _LOC[2] + tile_w * 0.25), plane_no=(0, 0, -1), use_fill=False, clear_outer=False, clear_inner=True)\n    bpy.ops.object.mode_set(mode='OBJECT')\n\n    arrx = tile.modifiers.new('Arrx', 'ARRAY')\n    arrx.use_relative_offset = False\n    arrx.use_constant_offset = True\n    arrx.constant_offset_displace = (tile_w * 0.95, 0, 0)\n    arrx.count = nx\n    arry = tile.modifiers.new('Arry', 'ARRAY')\n    arry.use_relative_offset = False\n    arry.use_constant_offset = True\n    arry.constant_offset_displace = (0, tile_d * 0.85, 0)\n    arry.count = ny\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.85\n    tile.data.materials.append(mat)\n    print('[apply_template] roof_tiles 完成: ' + str(nx) + 'x' + str(ny) + ' 块瓦')\nexcept Exception as _e:\n    import traceback; print('[apply_template] roof_tiles 失败:', _e); traceback.print_exc()\n"
})

# 70. stairs_modular 模块化楼梯
TEMPLATES.append({
    "name": "stairs_modular",
    "title": "模块化楼梯（cube + Array 沿 +Y/+Z 等距）",
    "category": "architecture",
    "description": "1 阶 cube + Array 沿 +Y/+Z 等距复制 N 阶，可配 stone_steps 或现代水泥色。",
    "params": [
        {"name": "name",     "type": "string", "default": "Stairs",  "description": "对象名"},
        {"name": "location", "type": "vec3",   "default": [0, 0, 0], "description": "底中心"},
        {"name": "count",    "type": "int",    "default": 12,        "description": "阶数"},
        {"name": "step_w",   "type": "float",  "default": 1.4,       "description": "宽（X）"},
        {"name": "step_d",   "type": "float",  "default": 0.30,      "description": "进深（Y）"},
        {"name": "step_h",   "type": "float",  "default": 0.18,      "description": "高（Z）"},
        {"name": "color",    "type": "rgb",    "default": [0.65, 0.62, 0.58], "description": "踏步色（水泥灰）"}
    ],
    "code": "import bpy\ntry:\n    _NAME = {{name|json}}\n    _LOC = {{location|json}}\n    _N = max(1, int({{count}}))\n    _W = float({{step_w}})\n    _D = float({{step_d}})\n    _H = float({{step_h}})\n    _C = {{color|json}}\n\n    bpy.ops.mesh.primitive_cube_add(size=1, location=(_LOC[0], _LOC[1] + _D * 0.5, _LOC[2] + _H * 0.5))\n    s = bpy.context.object; s.name = _NAME\n    s.scale = (_W, _D, _H)\n    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)\n    bv = s.modifiers.new('Bev', 'BEVEL'); bv.affect = 'EDGES'; bv.width = 0.005; bv.segments = 2\n    arr = s.modifiers.new('Array', 'ARRAY')\n    arr.use_relative_offset = False\n    arr.use_constant_offset = True\n    arr.constant_offset_displace = (0, _D, _H)\n    arr.count = _N\n\n    mat = bpy.data.materials.new(_NAME + '_mat')\n    mat.use_nodes = True\n    b = mat.node_tree.nodes.get('Principled BSDF')\n    if b and 'Base Color' in b.inputs:\n        b.inputs['Base Color'].default_value = (_C[0], _C[1], _C[2], 1.0)\n    if b and 'Roughness' in b.inputs:\n        b.inputs['Roughness'].default_value = 0.85\n    s.data.materials.append(mat)\n    print('[apply_template] stairs_modular 完成: ' + str(_N) + ' 阶')\nexcept Exception as _e:\n    import traceback; print('[apply_template] stairs_modular 失败:', _e); traceback.print_exc()\n"
})


# ============================================================
# 写入
# ============================================================
if __name__ == '__main__':
    append_templates(TEMPLATES, batch_label='batch3_studio_cg_arch')
