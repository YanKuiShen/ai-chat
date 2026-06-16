#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1 H-Hotfix5 批 5：cheatsheet 50 条新增"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import append_cheat

E = []

# === enum 反踩坑（4 条，治图 2） ===
E.append({"id":"enum-sky-vs-volume","category":"enum-trap","title":"⛔ sky_type vs phase_function 防混淆（图 2 治根）","keywords":["sky_type","phase_function","NISHITA","PREETHAM","HOSEK_WILKIE","SINGLE_SCATTERING","MULTIPLE_SCATTERING","enum"],"code":"# 这俩枚举完全无关 — 千万不要互填！\n# 1) ShaderNodeTexSky.sky_type 合法值：\n#    'NISHITA' / 'PREETHAM' / 'HOSEK_WILKIE'\nsky = nodes.new('ShaderNodeTexSky')\nsky.sky_type = 'NISHITA'   # ✓\n\n# 2) ShaderNodeVolumeScatter 没有 phase_function！只有 Anisotropy 标量\nvs = nodes.new('ShaderNodeVolumeScatter')\nvs.inputs['Anisotropy'].default_value = 0.3\n\n# 3) PrincipledVolume 也没有 phase_function 枚举\n# 4) 'phase_function' 这个字段名只在某些 PBR 体积渲染器（不是 Cycles/EEVEE）里有","deprecated":"图 2 bug：AI 把 sky_type='NISHITA' 错填到 ShaderNodeVolumeScatter.phase_function 上整段崩","see_also":["shader-sky-texture","shader-volume-scatter"]})

E.append({"id":"enum-light-type-shape","category":"enum-trap","title":"Light type / shape 合法值速查","keywords":["light","type","shape","POINT","SUN","SPOT","AREA","SQUARE","DISK","RECTANGLE","ELLIPSE"],"code":"bpy.ops.object.light_add(type='AREA')   # type 合法值: POINT / SUN / SPOT / AREA\nlt = bpy.context.object.data\nlt.shape = 'RECTANGLE'    # AREA shape 合法值: SQUARE / DISK / RECTANGLE / ELLIPSE\nlt.size = 2.0\nlt.size_y = 1.0   # 仅 RECTANGLE / ELLIPSE 用","deprecated":"shape 只对 AREA 有效，POINT/SUN/SPOT 没有","see_also":["light-area"]})

E.append({"id":"enum-render-engine","category":"enum-trap","title":"Render engine / Cycles device 枚举","keywords":["render engine","CYCLES","EEVEE_NEXT","BLENDER_EEVEE_NEXT","WORKBENCH","device","CPU","GPU"],"code":"# 4.2+ EEVEE 改名 EEVEE_NEXT\nbpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'   # or 'CYCLES' / 'BLENDER_WORKBENCH'\n# Cycles GPU\nbpy.context.scene.cycles.device = 'GPU'   # or 'CPU'","deprecated":"4.2+: 'BLENDER_EEVEE' → 'BLENDER_EEVEE_NEXT'","see_also":[]})

E.append({"id":"enum-bsdf-distribution","category":"enum-trap","title":"BSDF distribution 合法枚举","keywords":["distribution","GGX","MULTI_GGX","BECKMANN","SHARP"],"code":"# Glass / Glossy BSDF distribution 合法值：GGX / MULTI_GGX / BECKMANN / SHARP\ng = nodes.new('ShaderNodeBsdfGlass')\ng.distribution = 'GGX'   # ✓\n# 'PRINCIPLED' 不是合法值（那是另一个节点 ShaderNodeBsdfPrincipled）","deprecated":"","see_also":[]})

# === 地形组合食谱（8 条） ===
E.append({"id":"recipe-terrain-multi-displace","category":"recipe","title":"地形：多 Displace 叠层组合食谱","keywords":["terrain","displace","voronoi","clouds","起伏","subdivide"],"code":"# 关键：plane 不 subdivide，displace 没效果！\nbpy.ops.mesh.primitive_plane_add(size=30)\nobj = bpy.context.object\nbpy.ops.object.mode_set(mode='EDIT')\nbpy.ops.mesh.subdivide(number_cuts=80)\nbpy.ops.object.mode_set(mode='OBJECT')\n# 第 1 层：大山（Voronoi）\nt1 = bpy.data.textures.new('big','VORONOI'); t1.noise_scale = 3.0\nm1 = obj.modifiers.new('D1','DISPLACE'); m1.texture = t1; m1.strength = 2.0\n# 第 2 层：中起伏（Clouds）\nt2 = bpy.data.textures.new('mid','CLOUDS'); t2.noise_scale = 0.8\nm2 = obj.modifiers.new('D2','DISPLACE'); m2.texture = t2; m2.strength = 0.6\n# 第 3 层：细颗粒\nt3 = bpy.data.textures.new('det','CLOUDS'); t3.noise_scale = 0.2\nm3 = obj.modifiers.new('D3','DISPLACE'); m3.texture = t3; m3.strength = 0.1\nobj.modifiers.new('Sub','SUBSURF').levels = 1\nbpy.ops.object.shade_smooth()","deprecated":"","see_also":["modifier-displace","modifier-subsurf"]})

E.append({"id":"recipe-shrinkwrap-on-terrain","category":"recipe","title":"物体贴地：Shrinkwrap 到地形表面","keywords":["shrinkwrap","贴地","terrain","conform"],"code":"# 让物体（树/石头）自动贴附到崎岖地面\nm = obj.modifiers.new('SW','SHRINKWRAP')\nm.target = terrain_obj\nm.wrap_method = 'PROJECT'\nm.use_project_z = True\nm.use_negative_direction = False\nm.offset = 0.0","deprecated":"","see_also":["modifier-shrinkwrap"]})

E.append({"id":"recipe-boolean-valley","category":"recipe","title":"地形挖山谷：Boolean DIFFERENCE","keywords":["boolean","valley","河道","切山谷"],"code":"# 用 cube/cylinder 做 cutter，从 terrain 上挖一条山谷\nbpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0))\ncutter = bpy.context.object; cutter.scale = (15, 0.8, 0.5)\ncutter.hide_render = True; cutter.hide_viewport = True\nm = terrain.modifiers.new('Bool','BOOLEAN')\nm.operation = 'DIFFERENCE'\nm.object = cutter\nm.solver = 'EXACT'","deprecated":"","see_also":["modifier-boolean"]})

E.append({"id":"recipe-stair-step-terrain","category":"recipe","title":"梯田/阶梯地形：Math Floor + Displace","keywords":["stair","step","terrain","梯田","阶梯"],"code":"# 在 shader 里用 Math Floor 把高度量化成阶梯\nimport bpy\nmat = obj.active_material\nnt = mat.node_tree\nfloor = nt.nodes.new('ShaderNodeMath')\nfloor.operation = 'FLOOR'\nmul = nt.nodes.new('ShaderNodeMath')\nmul.operation = 'MULTIPLY'\nmul.inputs[1].default_value = 5.0\ndiv = nt.nodes.new('ShaderNodeMath')\ndiv.operation = 'DIVIDE'\ndiv.inputs[1].default_value = 5.0\n# noise → mul → floor → div → displacement","deprecated":"","see_also":[]})

E.append({"id":"recipe-shade-auto-smooth","category":"recipe","title":"shade_smooth + auto_smooth 组合（4.x/5.x 兼容）","keywords":["shade_smooth","auto_smooth","版本兼容"],"code":"bpy.ops.object.shade_smooth()\n# 4.x 写法：\nif hasattr(obj.data, 'use_auto_smooth'):\n    obj.data.use_auto_smooth = True\n    obj.data.auto_smooth_angle = math.radians(30)\nelse:\n    # 5.x：use_auto_smooth 已移除\n    bpy.ops.object.shade_auto_smooth(angle=math.radians(30))","deprecated":"5.x: use_auto_smooth 字段被移除，必须用 ops","see_also":["mesh-shade-smooth"]})

E.append({"id":"recipe-plane-must-subdivide","category":"recipe","title":"⚠️ plane 不 subdivide displace 没效果（常见崩根因）","keywords":["plane","subdivide","displace","为什么不动"],"code":"# 错的：\nbpy.ops.mesh.primitive_plane_add(size=10)\nobj = bpy.context.object\nm = obj.modifiers.new('D','DISPLACE')\nm.strength = 2.0   # ❌ 看不到效果！plane 只有 4 顶点\n\n# 对的：\nbpy.ops.object.mode_set(mode='EDIT')\nbpy.ops.mesh.select_all(action='SELECT')\nbpy.ops.mesh.subdivide(number_cuts=50)   # ✓ 必须 subdivide\nbpy.ops.object.mode_set(mode='OBJECT')","deprecated":"","see_also":["modifier-displace"]})

E.append({"id":"recipe-decimate-after-displace","category":"recipe","title":"Displace 后 Decimate 减面（性能优化）","keywords":["decimate","performance","optimize","poly count"],"code":"# subdivide+displace 后面数爆炸，Decimate ratio=0.3 减面\nm = obj.modifiers.new('Dec','DECIMATE')\nm.decimate_type = 'COLLAPSE'\nm.ratio = 0.3","deprecated":"","see_also":["modifier-decimate"]})

E.append({"id":"recipe-rocks-scatter","category":"recipe","title":"地形上散布岩石：GN Distribute Points","keywords":["rocks","scatter","gn","distribute"],"code":"mod = terrain.modifiers.new('GN','NODES')\nnt = bpy.data.node_groups.new('rocks','GeometryNodeTree')\nmod.node_group = nt\n# Distribute Points + Instance on Points + ObjectInfo(rock_proto)","deprecated":"","see_also":["gn-instance-on-points"]})

# === 天空大气（6 条） ===
E.append({"id":"recipe-sky-noon","category":"recipe","title":"NISHITA 正午时段（蓝天白云）","keywords":["nishita","noon","正午","蓝天"],"code":"sky.sky_type = 'NISHITA'\nsky.sun_elevation = math.radians(60)\nsky.sun_intensity = 1.0\nsky.air_density = 1.0\nsky.dust_density = 1.0","deprecated":"","see_also":["shader-sky-texture"]})

E.append({"id":"recipe-sky-sunset","category":"recipe","title":"NISHITA 黄昏时段（橙红天）","keywords":["nishita","sunset","黄昏","橙色"],"code":"sky.sky_type = 'NISHITA'\nsky.sun_elevation = math.radians(5)\nsky.sun_intensity = 0.7\nsky.dust_density = 4.0   # 关键：高 dust 让红黄色调更浓","deprecated":"","see_also":[]})

E.append({"id":"recipe-sky-night","category":"recipe","title":"夜空（深蓝 + 月亮）","keywords":["night","夜空","月亮","moon"],"code":"sky.sun_elevation = math.radians(-25)\n# Sky 节点输出会很暗，叠一层深蓝 background\nbg.inputs['Color'].default_value = (0.02, 0.04, 0.10, 1.0)\nbg.inputs['Strength'].default_value = 0.05\n# 月亮：单独 Sun light + 大 size\nbpy.ops.object.light_add(type='SUN')\nlt = bpy.context.object\nlt.data.energy = 0.5\nlt.data.color = (0.85, 0.92, 1.0)\nlt.data.angle = math.radians(2)","deprecated":"","see_also":["light-sun"]})

E.append({"id":"recipe-sky-color-grade","category":"recipe","title":"Sky 调色：ColorRamp 后期","keywords":["sky","colorramp","调色","grade"],"code":"# Sky → ColorRamp → Background\ncr = nt.nodes.new('ShaderNodeValToRGB')\ncr.color_ramp.elements[0].color = (1.0, 0.6, 0.4, 1)   # 远色\ncr.color_ramp.elements[1].color = (0.5, 0.7, 1.0, 1)   # 近色\nnt.links.new(sky.outputs['Color'], cr.inputs['Fac'])\nnt.links.new(cr.outputs['Color'], bg.inputs['Color'])","deprecated":"","see_also":[]})

E.append({"id":"recipe-world-volume-mist","category":"recipe","title":"世界级雾（World Volume）","keywords":["world","volume","mist","fog","世界雾"],"code":"world = bpy.context.scene.world\nworld.use_nodes = True\nnt = world.node_tree\nvs = nt.nodes.new('ShaderNodeVolumeScatter')\nvs.inputs['Density'].default_value = 0.02\nvs.inputs['Anisotropy'].default_value = 0.3\nwo = nt.nodes.get('World Output')\nnt.links.new(vs.outputs['Volume'], wo.inputs['Volume'])","deprecated":"","see_also":["world-volume-mist","shader-volume-scatter"]})

E.append({"id":"recipe-volume-domain","category":"recipe","title":"Volume Domain 设置（Cube 包体）","keywords":["volume","domain","cube","包体"],"code":"bpy.ops.mesh.primitive_cube_add(size=1)\nobj = bpy.context.object\nobj.scale = (40, 40, 5)   # 大 domain\nbpy.ops.object.transform_apply(scale=True)\nobj.display_type = 'WIRE'\n# 然后赋 Volume 材质（VolumeScatter / VolumePrincipled）","deprecated":"","see_also":[]})

# === 水体（5 条） ===
E.append({"id":"recipe-water-ocean","category":"recipe","title":"Ocean modifier 海洋","keywords":["ocean","海洋","wave"],"code":"bpy.ops.mesh.primitive_plane_add(size=20)\nobj = bpy.context.object\nm = obj.modifiers.new('Ocean','OCEAN')\nm.spatial_size = 20\nm.choppiness = 1.5\nm.depth = 100","deprecated":"","see_also":["modifier-wave"]})

E.append({"id":"recipe-water-caustics","category":"recipe","title":"焦散假效（Voronoi 投光）","keywords":["caustics","焦散","voronoi"],"code":"# Cycles 真焦散开 cycles.use_caustics_*\n# 假焦散：在地面 plane 上贴 Voronoi 自发光\nv = nt.nodes.new('ShaderNodeTexVoronoi')\nv.feature = 'DISTANCE_TO_EDGE'\nv.inputs['Scale'].default_value = 8.0\n# 接 Emission","deprecated":"","see_also":[]})

E.append({"id":"recipe-water-reflective-plane","category":"recipe","title":"倒影 plane（双层水面）","keywords":["reflective","倒影","mirror","plane"],"code":"# 上层透明水 + 下层镜面 plane\n# 上层：Roughness=0.05 / Transmission=1\n# 下层：Metallic=1 / Roughness=0\n# 中间填半透白色 noise mask 做波纹","deprecated":"","see_also":[]})

E.append({"id":"recipe-water-wave-normal","category":"recipe","title":"水面法线扰动：Wave → Bump → Normal","keywords":["water","wave","normal","bump","波纹"],"code":"wave = nt.nodes.new('ShaderNodeTexWave')\nwave.wave_type = 'BANDS'\nwave.inputs['Scale'].default_value = 8.0\nwave.inputs['Distortion'].default_value = 5.0\nbump = nt.nodes.new('ShaderNodeBump')\nbump.inputs['Strength'].default_value = 0.1\nnt.links.new(wave.outputs['Fac'], bump.inputs['Height'])\nnt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])","deprecated":"","see_also":[]})

E.append({"id":"recipe-water-river","category":"recipe","title":"河流（Curve 弯道 + Bevel + 水材质）","keywords":["river","河流","curve","bezier"],"code":"bpy.ops.curve.primitive_bezier_curve_add()\ncv = bpy.context.object\ncv.data.dimensions = '2D'\ncv.data.bevel_depth = 1.0   # 河宽\ncv.data.fill_mode = 'BOTH'","deprecated":"","see_also":["modifier-curve"]})

# === 粒子/GN（8 条） ===
E.append({"id":"gn-distribute-points-on-faces","category":"gn","title":"GN：Distribute Points on Faces","keywords":["distribute","points","scatter","散布"],"code":"dp = nt.nodes.new('GeometryNodeDistributePointsOnFaces')\ndp.inputs['Density'].default_value = 100.0   # 每平米点数\n# Mesh in → Points out","deprecated":"","see_also":["gn-instance-on-points"]})

E.append({"id":"gn-instance-on-points","category":"gn","title":"GN：Instance on Points","keywords":["instance","散布物体"],"code":"ip = nt.nodes.new('GeometryNodeInstanceOnPoints')\noi = nt.nodes.new('GeometryNodeObjectInfo')\noi.inputs['Object'].default_value = proto_obj\nnt.links.new(oi.outputs['Geometry'], ip.inputs['Instance'])","deprecated":"","see_also":["gn-realize-instances"]})

E.append({"id":"gn-realize-instances","category":"gn","title":"GN：Realize Instances（散布后实化）","keywords":["realize","instances"],"code":"ri = nt.nodes.new('GeometryNodeRealizeInstances')\n# Instances 是不能后续操作的，realize 后变 Mesh","deprecated":"","see_also":[]})

E.append({"id":"gn-set-position","category":"gn","title":"GN：Set Position","keywords":["set position","position","offset"],"code":"sp = nt.nodes.new('GeometryNodeSetPosition')\n# Position / Offset 输入；可接 Noise 让顶点位移","deprecated":"","see_also":[]})

E.append({"id":"gn-curve-line","category":"gn","title":"GN：Curve Line（电线/绳子骨架）","keywords":["curve line","电线","wire"],"code":"cl = nt.nodes.new('GeometryNodeCurvePrimitiveLine')\ncl.inputs['Start'].default_value = (0,0,0)\ncl.inputs['End'].default_value = (10,0,0)","deprecated":"","see_also":[]})

E.append({"id":"gn-geometry-proximity","category":"gn","title":"GN：Geometry Proximity（与目标距离）","keywords":["proximity","距离","mask"],"code":"gp = nt.nodes.new('GeometryNodeProximity')\ngp.target_element = 'FACES'\n# 距离值可驱动 Density / Scale","deprecated":"","see_also":[]})

E.append({"id":"recipe-particle-hair","category":"recipe","title":"Particle Hair 静态草地（旧 API）","keywords":["particle","hair","grass"],"code":"obj.modifiers.new('Hair','PARTICLE_SYSTEM')\npsys = obj.particle_systems[-1]\ns = psys.settings\ns.type = 'HAIR'\ns.count = 1000\ns.hair_length = 0.3\ns.render_type = 'OBJECT'\ns.instance_object = blade_obj","deprecated":"4.x 推荐改用 GN，但 PARTICLE_SYSTEM 仍可用","see_also":["modifier-particle"]})

E.append({"id":"recipe-smoke-domain","category":"recipe","title":"烟雾 domain（FLUID modifier）","keywords":["smoke","fluid","烟"],"code":"obj.modifiers.new('Fluid','FLUID')\nm = obj.modifiers['Fluid']\nm.fluid_type = 'DOMAIN'\nm.domain_settings.domain_type = 'GAS'","deprecated":"","see_also":[]})

# === 特效自发光（6 条） ===
E.append({"id":"recipe-emission-strength","category":"recipe","title":"自发光强度速查表（cycles/EEVEE 同量纲）","keywords":["emission","strength","发光强度"],"code":"# 太阳: 100~1000+\n# 灯泡: 5~30\n# 屏幕/UI: 1~3\n# 霓虹: 8~20\n# 月亮: 0.3~1\n# 萤火虫: 5~15（小 mesh + 高 strength）\nem.inputs['Strength'].default_value = 10.0","deprecated":"","see_also":["shader-emission"]})

E.append({"id":"recipe-emission-color-compat","category":"recipe","title":"自发光双重兼容（Emission / Emission Color）","keywords":["emission","emission color","版本兼容","3.x","4.x"],"code":"# 4.x: bsdf.inputs['Emission Color'] / 3.x: bsdf.inputs['Emission']\nfor key in ['Emission Color', 'Emission']:\n    if key in bsdf.inputs:\n        bsdf.inputs[key].default_value = (1.0, 0.5, 0.2, 1.0)\n        break\nif 'Emission Strength' in bsdf.inputs:\n    bsdf.inputs['Emission Strength'].default_value = 5.0","deprecated":"3.x 名 'Emission'，4.x 改名 'Emission Color'","see_also":["shader-principled"]})

E.append({"id":"recipe-bloom-glare","category":"recipe","title":"合成器 Glare 节点（Bloom 替代）","keywords":["bloom","glare","compositor"],"code":"# 4.2+ EEVEE Next 取消了内置 Bloom，改在合成器加 Glare\nbpy.context.scene.use_nodes = True\nnt = bpy.context.scene.node_tree\ng = nt.nodes.new('CompositorNodeGlare')\ng.glare_type = 'FOG_GLOW'\ng.threshold = 1.0\ng.size = 7","deprecated":"4.2+: EEVEE Next 没有 Bloom，必须合成器","see_also":[]})

E.append({"id":"recipe-emission-mix","category":"recipe","title":"局部自发光（Mix Shader）","keywords":["emission","mix","local"],"code":"# 用 mask（Voronoi/Image）混合 BSDF + Emission\nmix = nt.nodes.new('ShaderNodeMixShader')\nnt.links.new(mask.outputs['Fac'], mix.inputs['Fac'])\nnt.links.new(bsdf.outputs[0], mix.inputs[1])\nnt.links.new(em.outputs[0], mix.inputs[2])","deprecated":"","see_also":[]})

E.append({"id":"recipe-lens-flare","category":"recipe","title":"Lens Flare（合成器手作）","keywords":["lens flare","耀斑","glare"],"code":"# Glare 节点 'STREAKS' 类型 = 镜头条纹\ng = nt.nodes.new('CompositorNodeGlare')\ng.glare_type = 'STREAKS'\ng.streaks = 6\ng.angle_offset = 0.5","deprecated":"","see_also":[]})

E.append({"id":"recipe-tone-mapping","category":"recipe","title":"Tone Mapping（Filmic / AgX 4.0+）","keywords":["filmic","agx","tone mapping","曝光"],"code":"# 4.0+ 默认 view transform 是 AgX；3.x 默认 Filmic\nbpy.context.scene.view_settings.view_transform = 'AgX'   # 4.0+\n# 或: 'Filmic' / 'Standard'\nbpy.context.scene.view_settings.look = 'AgX - Medium High Contrast'\nbpy.context.scene.view_settings.exposure = 0.0   # EV","deprecated":"","see_also":[]})

# === 摄影棚（6 条） ===
E.append({"id":"recipe-three-point-numbers","category":"recipe","title":"三点布光数值参考","keywords":["three point","key","fill","rim","studio"],"code":"# Key 主光：Area size=2 / energy=800 / 前 45°\n# Fill 补光：Area size=3 / energy=300 / 对侧低位\n# Rim 轮廓：Spot energy=600 / 后上方\n# 比例：Key:Fill:Rim ≈ 4:1.5:3","deprecated":"","see_also":["light-three-point"]})

E.append({"id":"recipe-color-management","category":"recipe","title":"Color Management 速查","keywords":["color management","filmic","display","sRGB"],"code":"s = bpy.context.scene\ns.view_settings.view_transform = 'AgX'   # 4.0+ 默认\ns.view_settings.exposure = 0.0\ns.view_settings.gamma = 1.0\ns.display_settings.display_device = 'sRGB'\ns.sequencer_colorspace_settings.name = 'sRGB'","deprecated":"","see_also":["recipe-tone-mapping"]})

E.append({"id":"recipe-lut-compositor","category":"recipe","title":"自定义 LUT（Compositor）","keywords":["LUT","compositor","color grade"],"code":"nt = bpy.context.scene.node_tree\nlut = nt.nodes.new('CompositorNodeColorBalance')\nlut.lift = (1.0, 0.95, 0.92, 1.0)\nlut.gamma = (1.05, 1.0, 0.98, 1.0)\nlut.gain = (1.0, 1.05, 1.10, 1.0)","deprecated":"","see_also":[]})

E.append({"id":"recipe-hdri-fallback","category":"recipe","title":"⚠️ PolyHaven 已下线（图 1 治根）","keywords":["polyhaven","hdri","下线","替代方案"],"code":"# v2.1 G-Hotfix3：search_polyhaven_assets / import_polyhaven_model / set_world_hdri 已禁用\n# 想要 HDRI 天空 → apply_template('sky_nishita', {time_preset: 'noon'})\n# 想要装饰物体 → apply_template('xxx', {...}) 或 add_primitive 拼装\n# 不要再调任何 polyhaven_xxx 工具 — 它们已从工具表过滤","deprecated":"v2.1 G-Hotfix3 起 PolyHaven 远程下载彻底下线","see_also":["world-hdri"]})

E.append({"id":"recipe-softbox-energy","category":"recipe","title":"柔光箱 Area Light 能量参考","keywords":["softbox","area light","energy"],"code":"# 1×1m 柔光箱: energy=500~1000W\n# 0.6×0.6m: 700~900\n# 1.5×1.5m: 1200~2000\nlt.data.shape = 'SQUARE'\nlt.data.size = 0.6\nlt.data.energy = 800","deprecated":"","see_also":["light-area"]})

E.append({"id":"recipe-camera-portrait","category":"recipe","title":"人像相机参数（85mm + f/1.8）","keywords":["camera","portrait","人像","85mm","景深"],"code":"cam.data.lens = 85\ncam.data.dof.use_dof = True\ncam.data.dof.focus_object = subject\ncam.data.dof.aperture_fstop = 1.8\ncam.data.dof.aperture_blades = 6","deprecated":"","see_also":["camera-dof"]})

# === 二次元卡通渲染（6 条） ===
E.append({"id":"recipe-toon-bsdf","category":"recipe","title":"Toon BSDF（Cycles 卡通）","keywords":["toon","cel","cartoon","bsdf"],"code":"# Cycles 专属\nt = nt.nodes.new('ShaderNodeBsdfToon')\nt.component = 'DIFFUSE'   # or 'GLOSSY'\nt.inputs['Color'].default_value = (0.8, 0.6, 0.5, 1)\nt.inputs['Size'].default_value = 0.5\nt.inputs['Smooth'].default_value = 0.05","deprecated":"EEVEE 不支持，须 Cycles","see_also":[]})

E.append({"id":"recipe-cel-shading-ramp","category":"recipe","title":"Cel-shading：阶梯化 ColorRamp","keywords":["cel","ramp","constant","卡通阴影"],"code":"# Diffuse → ColorRamp(CONSTANT 插值) → BSDF\ndi = nt.nodes.new('ShaderNodeBsdfDiffuse')\ncr = nt.nodes.new('ShaderNodeValToRGB')\ncr.color_ramp.interpolation = 'CONSTANT'   # ★ 关键\ncr.color_ramp.elements[0].color = (0.5, 0.4, 0.4, 1)   # 暗\ncr.color_ramp.elements[1].color = (1.0, 0.95, 0.9, 1) # 亮","deprecated":"","see_also":["shader-color-ramp"]})

E.append({"id":"recipe-outline-solidify","category":"recipe","title":"卡通描边：Solidify + Backface Cull","keywords":["outline","solidify","backface","卡通描边"],"code":"m = obj.modifiers.new('Outline','SOLIDIFY')\nm.thickness = -0.01   # 负值朝内\nm.offset = 1.0\nm.use_flip_normals = True\n# 第二个材质 slot：纯黑 + 关 backface\nblack_mat = bpy.data.materials.new('outline')\nblack_mat.use_nodes = True\nblack_mat.use_backface_culling = True","deprecated":"","see_also":["modifier-solidify"]})

E.append({"id":"recipe-cel-rim-light","category":"recipe","title":"卡通 Rim Light（Fresnel + Emission）","keywords":["rim","fresnel","卡通边缘"],"code":"fr = nt.nodes.new('ShaderNodeFresnel')\nfr.inputs['IOR'].default_value = 2.5\ncr = nt.nodes.new('ShaderNodeValToRGB')\ncr.color_ramp.interpolation = 'CONSTANT'\nem = nt.nodes.new('ShaderNodeEmission')\nem.inputs['Strength'].default_value = 2.0\n# fresnel → ramp(constant) → mix shader fac → bsdf+emission","deprecated":"","see_also":["shader-fresnel"]})

E.append({"id":"recipe-cel-ramp-shadow","category":"recipe","title":"卡通阴影：Diffuse Shader To Color → Ramp","keywords":["shader","to","rgb","cel"],"code":"# 经典 cel：用 Diffuse + ShaderToRGB（EEVEE only）\ns2c = nt.nodes.new('ShaderNodeShaderToRGB')\nnt.links.new(diffuse.outputs[0], s2c.inputs[0])\nnt.links.new(s2c.outputs['Color'], cr.inputs['Fac'])","deprecated":"ShaderToRGB 仅 EEVEE 支持","see_also":[]})

E.append({"id":"recipe-anime-hair-highlight","category":"recipe","title":"二次元头发高光（环状 Anisotropic）","keywords":["hair","anime","二次元","头发"],"code":"# Anisotropic + UV 环绕\nani = nt.nodes.new('ShaderNodeBsdfAnisotropic')\nani.inputs['Roughness'].default_value = 0.2\nani.inputs['Anisotropy'].default_value = 0.9","deprecated":"","see_also":[]})

# === 其它（5 条凑足 50） ===
E.append({"id":"recipe-bisect-cut","category":"recipe","title":"bmesh.ops.bisect_plane 切割","keywords":["bisect","cut","切割"],"code":"bpy.ops.object.mode_set(mode='EDIT')\nbpy.ops.mesh.select_all(action='SELECT')\nbpy.ops.mesh.bisect(plane_co=(0,0,0.5), plane_no=(0,0,1), use_fill=True, clear_outer=True)\nbpy.ops.object.mode_set(mode='OBJECT')","deprecated":"","see_also":[]})

E.append({"id":"recipe-empty-as-parent","category":"recipe","title":"用 Empty 做 parent 整体管理","keywords":["empty","parent","root"],"code":"bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,0))\nroot = bpy.context.object; root.name = 'MyAssembly_root'\nfor p in parts:\n    p.parent = root\n    p.matrix_parent_inverse = root.matrix_world.inverted()","deprecated":"","see_also":[]})

E.append({"id":"recipe-track-to","category":"recipe","title":"Track To 让物体始终对准目标","keywords":["track to","aim","look at"],"code":"con = obj.constraints.new('TRACK_TO')\ncon.target = target_obj\ncon.track_axis = 'TRACK_NEGATIVE_Z'\ncon.up_axis = 'UP_Y'","deprecated":"","see_also":["camera-track-to"]})

E.append({"id":"recipe-modifier-not-operator","category":"recipe","title":"⭐ 用 modifiers.new() 而非 operator","keywords":["modifier","operator","best practice"],"code":"# ✓ 推荐（4.2+ 稳定）：\nm = obj.modifiers.new('Bev','BEVEL')\nm.affect = 'EDGES'; m.width = 0.03\n\n# ❌ 不推荐（依赖 active object）：\n# bpy.ops.object.modifier_add(type='BEVEL')","deprecated":"","see_also":[]})

E.append({"id":"recipe-step-id-numeric","category":"recipe","title":"⚠️ plan_update_step 必须传纯数字 step_id（图 3 治根）","keywords":["step_id","plan_update_step","正则","纯数字"],"code":"# ❌ 错的：step_id='4 एक्टिंग}' / step_id='step-1' / step_id='第 1 步'\n# ✓ 对的：step_id='1' / step_id='2' / step_id='3'\n# v2.1 H-Hotfix5 起前端会强制正则 /^\\d+$/ 校验，传杂字符直接 ok:false\nplan_update_step({step_id: '1', status: 'in_progress'})\n# 不知道当前 step 列表？先调 plan_get() 拿\nplan_get()","deprecated":"图 3 bug：AI 传 '4 एक्टिंग}' 死循环根因","see_also":[]})


if __name__ == '__main__':
    append_cheat(E, batch_label='batch5_cheat50')
