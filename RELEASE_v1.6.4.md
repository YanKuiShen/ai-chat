# 白歌的AI讨论组 v1.6.4 发布说明

> 发布时间：2026-05-16  
> 主题：**Step 3 可跳过 + 一键3D 彻底解决「只有粗模型、没材质光影」**

---

## 🎯 痛点对照表

| 用户反馈痛点 | v1.6.3 现状 | v1.6.4 解决方案 |
|---|---|---|
| 1️⃣ 图像 API 没额度，但还想出 3D 模型 | Step 3 必须执行才能进 Step 4 | **新增「⏭️ 跳过此节点」复选框，跳过后 Step 4 仅靠文字演算** |
| 2️⃣ Blender 里只有灰色粗模型，看不到材质 | bpy 脚本没切视口着色，默认 `Solid` | **脚本自动切到 `Material Preview`，含 HDRI 环境光 + 场景灯光** |
| 3️⃣ 测算尺寸/材质/光影节点不加上 Blender 灯光和场景亮度 | SceneSpec lights 字段太弱，AI 经常给 0~2 个灯 | **强制 lights ≥ 3 + 新增 world_strength / exposure / time_of_day / purpose 字段，AI 不生成自动兜底三点布光** |

---

## 🚀 一键操作流程对比

### ❌ v1.6.3 之前
1. Step 1：选聊天记录
2. Step 2：生成场景描述
3. Step 3：**必须出图（否则 Step 4 没参考图导致光影信息缺失）**
4. Step 4：测算 SceneSpec（lights 经常只有 0~2 个）
5. Step 5：生成 bpy 脚本
6. 推送 Blender → **打开看到一堆灰色 cube/sphere，得手动按 Z → 6 切材质预览**

### ✅ v1.6.4 之后
1. Step 1：选聊天记录
2. Step 2：生成场景描述
3. Step 3：**勾选「⏭️ 跳过此节点」** → 跳过出图
4. Step 4：直接测算（仅靠文字演算，lights ≥ 3，含 time_of_day 预设）
5. Step 5：生成 bpy 脚本（EEVEE Next + Material 视口 + 兜底布光）
6. 推送 Blender → **打开立刻看到完整材质和光影效果**

---

## 📐 SceneSpec 字段升级矩阵

```json
{
  "scene": {
    "name": "场景名",
    "unit": "m",
    "world_bg_color": [R, G, B],
    "world_strength": 0.0~2.0,        // 🆕 v1.6.4：HDR 环境光强度
    "exposure": -3~3,                  // 🆕 v1.6.4：相机曝光补偿
    "time_of_day": "noon|sunset|night|indoor_lit|studio|overcast",  // 🆕 v1.6.4
    "ambient_mood": "warm|neutral|cool"  // 🆕 v1.6.4
  },
  "lights": [
    {
      "type": "POINT|SUN|AREA|SPOT",
      "location": [x, y, z],
      "rotation_euler_deg": [rx, ry, rz],  // 🆕 v1.6.4：SUN/SPOT 方向
      "color": [R, G, B],
      "energy": 数值,
      "size": 数值,
      "purpose": "key|fill|rim|practical|sun|window|ambient"  // 🆕 v1.6.4
    }
  ],
  "objects": [
    {
      ...,
      "material": {
        "emission_strength": 0~20  // ⚠️ v1.6.4 强化：自发光物体务必给 1~20
      }
    }
  ]
}
```

### 各时段 time_of_day 预设公式

| time_of_day | 太阳光 | 主光 (Key) | 辅光 (Fill) | 轮廓光 (Rim) | world_strength |
|---|---|---|---|---|---|
| `noon` | SUN energy 3~5, [1,0.95,0.85] | AREA 200, 中性 | AREA 60, 偏冷蓝 | - | 1.2 |
| `sunset` | SUN energy 2, [1,0.6,0.3] 低角度 | AREA 150, 暖橙 | AREA 45, 暖 | - | 0.7 |
| `night` | ❌ 无 | POINT 暖光 400, [1,0.8,0.6] | POINT 120 | POINT 240 | 0.05 |
| `indoor_lit` | SUN 2 从窗户 | AREA 200 吸顶 | AREA 60 | - | 0.5 |
| `studio` | ❌ 无 | AREA 500 强 | AREA 100 弱 | SPOT 200 边缘 | 0.2 |
| `overcast` | SUN 1.5 中性弱 | AREA 100 | AREA 30 | - | 1.0 |

---

## 🐍 生成的 Blender Python 脚本变化对比

### v1.6.3 渲染设置段（约 6 行）
```python
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
print("场景生成完成")
```

### v1.6.4 渲染设置段（约 30 行）
```python
# 优先用 Blender 4.2+ 的 EEVEE Next；老版本回退
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except Exception:
    try: scene.render.engine = "BLENDER_EEVEE"
    except: pass

scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# 启用 EEVEE 视觉效果
try:
    ee = scene.eevee
    for _attr, _val in [
        ("use_bloom", True),
        ("use_ssr", True), ("use_ssr_refraction", True),
        ("use_gtao", True),
        ("use_soft_shadows", True),
        ("taa_render_samples", 64), ("taa_samples", 16),
        ("shadow_cube_size", "1024"), ("shadow_cascade_size", "2048")
    ]:
        if hasattr(ee, _attr):
            try: setattr(ee, _attr, _val)
            except: pass
except Exception: pass

# 相机曝光
scene.view_settings.exposure = exposure_value

# ⭐ 关键：切视口到 Material Preview
try:
    for _area in bpy.context.screen.areas:
        if _area.type == "VIEW_3D":
            for _sp in _area.spaces:
                if _sp.type == "VIEW_3D":
                    _sp.shading.type = "MATERIAL"
                    if hasattr(_sp.shading, "use_scene_lights"):
                        _sp.shading.use_scene_lights = True
                    if hasattr(_sp.shading, "use_scene_world"):
                        _sp.shading.use_scene_world = True
except Exception: pass

print("✅ 场景生成完成: N 个对象 / M 个灯光")
print("💡 视口已切到 Material Preview。若想看 SSR/Bloom 实时效果，请按 Z → 8 切换到 Rendered Viewport。")
```

### v1.6.4 灯光段新增「兜底布光」
```python
# === 兜底布光：AI 灯光不足 3 个时自动补充 ===
if len([o for o in bpy.data.objects if o.type == 'LIGHT']) < 3:
    print("⚠️ AI 只生成了 N 个灯光，按 time_of_day=xxx 自动补足兜底布光")
    
    # 兜底太阳光（户外/室内日光时段）
    _sun = bpy.data.lights.new(name="Fallback_Sun", type="SUN")
    _sun.energy = 2; _sun.color = (1, 0.95, 0.9)
    _sun_obj = bpy.data.objects.new("Fallback_Sun", _sun)
    bpy.context.collection.objects.link(_sun_obj)
    _sun_obj.location = (0, 0, 10)
    _sun_obj.rotation_euler = (math.radians(50), 0, math.radians(45))
    
    # 兜底三点布光：主光 + 辅光 + 轮廓光
    _key = bpy.data.lights.new(name="Fallback_Key", type="AREA")
    _key.energy = 200; _key.size = 3
    _key_obj = ...; _key_obj.location = (3, -3, 4); ...
    
    _fill = bpy.data.lights.new(name="Fallback_Fill", type="AREA")
    _fill.energy = 60; _fill.size = 4
    _fill_obj = ...; _fill_obj.location = (-3, -2, 3); ...
    
    _rim = bpy.data.lights.new(name="Fallback_Rim", type="SPOT")
    _rim.energy = 120; _rim.spot_size = math.radians(60)
    _rim_obj = ...; _rim_obj.location = (0, 4, 4); ...
```

---

## 🔄 向后兼容保证

| 项目 | 兼容性 |
|---|---|
| 老 SceneSpec（缺 world_strength / exposure / time_of_day） | ✅ 用默认值兜底（0.5 / 0 / indoor_lit） |
| 老 SceneSpec 灯光（缺 rotation / purpose） | ✅ 默认朝下 `[0,0,0]`，无 purpose 注释 |
| 老项目数据（无 skipStep3 字段） | ✅ 自动初始化为 `false` |
| Blender 3.x 老版本（无 EEVEE Next） | ✅ try/except 回退到 BLENDER_EEVEE |
| Blender 老版本（无 use_ssr_refraction / use_soft_shadows 属性） | ✅ hasattr 守护，不存在则跳过 |
| 老的 4 张分图 views（v1.6.0 之前） | ✅ m3dRender 2x2 网格兼容渲染 |

---

## 📦 安装包升级提示

1. **强烈推荐升级**：v1.6.4 解决的是 v1.6.0~1.6.3 全程困扰用户的「打开 Blender 看到一堆灰模」问题
2. **localStorage key 更新**：`hasLaunched_v1.6.4`，升级后会再次弹欢迎窗口（仅 1 次）
3. **下载地址**：项目 `dist/` 目录下：
   - macOS：`白歌的AI讨论组-1.6.4-arm64.dmg` / `白歌的AI讨论组-1.6.4-x64.dmg`
   - Windows：`白歌的AI讨论组-Setup-1.6.4-x64.exe` / `白歌的AI讨论组-Setup-1.6.4-arm64.exe` / `白歌的AI讨论组-Setup-1.6.4.exe`（通用）
   - Blender 插件：`aichat_bridge.zip`（与 v1.6.0+ 兼容，无需重装）

---

## 🐛 已知问题与下一版预告

### v1.6.4 已知限制
- **跳过 Step 3 时，Step 4 完全依赖文字描述质量**：如果 Step 2 的场景描述里没明确写时段/物体材质，AI 可能输出比较泛的 SceneSpec
- **Material Preview 仍然需要显卡支持 OpenGL 4.3+**：极老的核显（>10 年）可能仍然显示灰模
- **EEVEE Next 在某些 Blender 4.2 内部版本里 use_bloom 属性已被移除**：脚本会安全跳过，但 Bloom 效果会缺失（用 Cycles 渲染时不影响）

### v1.6.5 候选改动
- 在 Step 4 预览面板底部显示「💡 灯光 N 个 · 环境 X · 视口 Material」实时统计
- 支持从一键3D 项目直接导出 .blend 文件（不用打开 Blender）
- Blender 端插件添加「一键截图返回」功能，把渲染结果回传到网页
