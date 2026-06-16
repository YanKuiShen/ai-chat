# 🚀 v1.6.5 治黑屏终极版 —— AI 直出 bpy 代码 + 安全兜底壳

## 🐛 诊断到的根因

用户反馈：**「Blender 里没有灯光、没有材质，整个场景几乎全黑」**

经过截图分析（用户场景里只有 `acrylic_sphere_1~4` / `softbox_body` / `wall_wash_light_left/right` 等 mesh 物体，没有一个真正的 LIGHT 物体），定位到 **v1.6.4 的两个根因**：

| 现象 | 根因 |
|---|---|
| 「场景没有光源」 | AI 把灯具理解成 mesh 物体（建灯具外壳，但 lights 数组为空，或者 SceneSpec 里 type/格式错误导致解析失败） |
| 「自发光物体不发光」 | `make_material` 函数只设了 `Emission Strength`，但 Blender 4.x 默认 `Emission Color` = 黑色，strength=10 也不会发光 |
| 「信息每次传递都损失」 | SceneSpec JSON 是中间瓶颈：聊天 → 散文 → 图 → SceneSpec → 本地 m3dSpecToBpy → bpy。AI 把视觉信息硬塞结构化字段，本地转换又只用了子集 |

## 🔥 v1.6.5 治黑屏方案：**双管齐下**

### 改动 A：Step 4 改为 AI 直出 bpy 代码（砍掉 SceneSpec JSON 中间产物）

**v1.6.4 流程：**
```
Step 4: AI 读场景描述 + 图 → 输出 SceneSpec JSON
Step 5: 本地 m3dSpecToBpy(spec) → bpy 代码
推送 Blender
```

**v1.6.5 流程：**
```
Step 4: AI 读场景描述 + 图 → 直接输出 <blender_code>...</blender_code> 标签包裹的可执行 bpy 代码
推送 Blender（自动包裹安全兜底壳）
```

**5 步 → 4 步**，砍掉 SceneSpec 这个信息瓶颈，避免每次结构化传递的语义丢失。

### 改动 B：System Prompt 强制约束（13 条硬性要求）

让 AI 直出代码，但代码必须满足：

1. ✅ 必须用 `<blender_code>...</blender_code>` 标签包起来
2. ✅ 必须 `import bpy, math` + 先清空场景
3. ✅ **物体 ≥ 8 个**（地面/墙壁/家具/装饰），且要主动补全场景里没显式提到但符合常理的物体（盆栽/装饰画/吊灯）
4. ✅ **自发光物体必须同时设 Emission Color + Emission Strength**（缺一不可），兼容 Blender 4.x 改名后的 `Emission Color` 属性
5. ✅ **必须用 `bpy.data.lights.new()` 创建至少 3 个真正的 LIGHT 物体**（不是 mesh 灯具外壳！）
6. ✅ **灯光能量参考表（v1.6.4 数值偏低 7~10 倍 → v1.6.5 一次性给够）**：
   - SUN：5~10
   - AREA（室内主灯/补光）：500~2000
   - POINT（吊灯/台灯）：500~3000
   - SPOT（轮廓光/重点光）：800~3000
7. ✅ 必须设置相机 + 世界背景（`world_strength` 1.0~1.8）
8. ✅ EEVEE Next 兼容老版本

### 改动 C：推送前自动包裹「v1.6.5 安全兜底壳」

不论 AI 输出什么代码，网页端都会在末尾追加一段安全壳代码：

```python
# 1) 灯光检查：< 3 个自动补三点光（key 1500 + fill 600 + rim 1200 + 兜底 SUN 3）
if len([o for o in bpy.data.objects if o.type == 'LIGHT']) < 3:
    # 自动创建三点布光 + 太阳光
    ...

# 2) AI 给的所有灯光 ×1.5 安全系数（Filmic 会自动 tone-map 不会过曝）
for l in bpy.data.objects:
    if l.type == 'LIGHT' and not l.name.startswith('_safety_'):
        l.data.energy *= 1.5

# 3) 强制 Filmic Color Management + Medium High Contrast
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.look = 'Medium High Contrast'

# 4) 强制视口切到 RENDERED（v1.6.4 是 MATERIAL Preview，看不到完整光影）
sp.shading.type = 'RENDERED'
sp.shading.use_scene_lights_render = True
sp.shading.use_scene_world_render = True

# 5) 启用 EEVEE 的 Bloom / SSR / GTAO / Soft Shadow / TAA 64

# 6) 自动切到相机视角（避免用户看错方向以为没东西）
bpy.ops.view3d.view_camera()  # 兼容 Blender 3.x / 4.x 的 temp_override

# 7) 控制台诊断输出：物体数 / 灯光数 / 自发光数 / 视口 / 相机
print("[v1.6.5 安全壳] ✅ 场景生成完成")
print("  📦 物体: %d 个 / 💡 灯光: %d 个 / ✨ 自发光物体: %d 个")
print("  🎬 视口: RENDERED + Filmic")
print("  📷 已切相机视角")
```

→ **即使 AI 偶尔忘了某些必备项（灯光太少、Filmic 没设、视口忘切），安全壳会兜底补上**。

---

## 📊 关键参数对比

| 项 | v1.6.4 | v1.6.5 |
|---|---|---|
| **流程步骤** | 5 步（含 SceneSpec → m3dSpecToBpy 中间产物） | **4 步**（AI 直出 bpy 代码） |
| 兜底 key 灯能量 | 200 | **1500** (×7.5) |
| 兜底 fill 灯能量 | 60 | **600** (×10) |
| 兜底 rim 灯能量 | 120 | **1200** (×10) |
| 兜底 sun 能量 | 4 | **3+8（拆分两盏）** |
| AI prompt AREA 灯范围 | 50~500 | **500~2000** (×4) |
| AI prompt POINT 灯范围 | 100~1500 | **500~3000** |
| World strength 默认 | 0.5 | **1.0~1.8** |
| 自发光 Emission Color | ❌ 没设（默认黑）| ✅ 设为 base_color |
| 视口着色模式 | Material Preview | **Rendered** |
| Color Management | sRGB（默认）| **Filmic + Medium High Contrast** |
| 灯光 ×1.5 安全系数 | ❌ 无 | **✅ 自动追加** |
| 自动切相机视角 | ❌ | **✅ 自动切** |
| 控制台诊断输出 | 简单 1 行 | **多行完整诊断** |
| Blender 4.x 自发光属性兼容 | ❌（只识别 Emission Strength） | **✅（同时识别 Emission Color / Emission）** |

---

## 🛠️ 改动清单

### `ai-chat/public/index.html`

1. **Step 4 节点 UI 升级**
   - 标题 `4️⃣ 测算尺寸/材质/光影` → `4️⃣ 智能演算 → 直接出 Blender 代码`
   - 按钮文案 `📏 解析 SceneSpec` → `🐍 演算并直出 bpy 代码`
   - 删除 Step 5 节点（不再需要本地代码生成）
   - 增加说明文字：「AI 直接输出可执行 bpy 代码（含光源/材质/相机/EEVEE 设置/视口 RENDERED），主动补全场景里没显式提到的合理物体（盆栽/装饰画/吊灯等），跳过 SceneSpec JSON 中间产物，避免信息每次传递的损失」

2. **`m3dStep4_estimate()` 完全重写**
   - System Prompt 从「输出 SceneSpec JSON」改为「输出 `<blender_code>...</blender_code>` 标签代码」
   - 包含 13 条硬性要求（光源类型、能量参考表、自发光双重设置、物体数量、相机、世界背景、EEVEE）
   - 含完整代码示例片段

3. **新增 `m3dExtractBlenderCode(text)` 工具函数**
   - 兼容四种情况：
     1. 标准 `<blender_code>...</blender_code>` 标签
     2. 漏写结束标签
     3. 没标签但有 ```` ```python ```` 代码块
     4. 没任何标签但包含 `import bpy` → 直接用全文

4. **新增 `m3dWrapWithSafetyShell(userCode)` 安全壳函数**
   - 在 AI 代码末尾追加 v1.6.5 安全壳（~150 行 Python）
   - 灯光 < 3 → 自动补三点光 + 太阳光
   - 强制 Filmic Color Management
   - 视口切 RENDERED
   - AI 灯光 ×1.5 安全系数
   - 自动切相机视角（兼容 Blender 3.x / 4.x）
   - 多行控制台诊断输出

5. **`m3dSendToBlender()` 升级**
   - 推送前调用 `m3dWrapWithSafetyShell()` 包裹代码
   - 确认对话框显示「已自动包裹 v1.6.5 安全兜底壳」

6. **欢迎弹窗 hasLaunched key**
   - `hasLaunched_v1.6.4` → `hasLaunched_v1.6.5`

### `ai-chat/package.json`

- `version`: `1.6.4` → `1.6.5`
- `description` 更新为 v1.6.5 治黑屏方案说明

---

## 🎯 用户预期效果

打开 Blender，运行 v1.6.5 生成 + 推送的代码后：

1. ✅ **视口直接显示 RENDERED 模式 + Filmic 色彩**，画面立即有光影
2. ✅ **至少 3 个真正的 LIGHT 物体**（不是 mesh 灯具外壳）
3. ✅ **自发光物体真的发光**（吊灯/台灯/屏幕）
4. ✅ **场景丰满**，至少 8 个 mesh 物体（含主动补全的盆栽/装饰画等）
5. ✅ **自动切到相机视角**，不会"看错方向以为没东西"
6. ✅ Blender 控制台 print 出诊断信息：「物体 X 个 / 灯光 Y 个 / 自发光 Z 个 / 视口 RENDERED + Filmic / 已切相机视角」
7. ✅ Bloom / SSR / GTAO / 软阴影全开，画面有真实光感

---

## 📦 升级路径

- 老用户：保留 `v1.6.4` 项目数据全部兼容（`m3dState.summary` 仍是 XML 包裹的散文，`stepConfigs` 不变）
- `m3dState.spec` 在 v1.6.5 不再实际使用，但保留兼容字段，老数据切换回来不会报错
- 重新生成 Step 4 时会顶掉老 spec，写入新 code

---

## 🚧 已知限制

- AI 输出代码 quality 仍依赖底层模型（建议用 GPT-4o / Claude 3.5 / DeepSeek-V3 等推理强的模型，避免老 GPT-3.5 / 千问-Lite 等）
- 部分 base64 图过大时，`/api/chat` 可能超时，可以勾选「⏭️ 跳过此节点（让 Step 4 仅靠场景描述演算）」走仅文字分支
- Blender 3.6+ 推荐，老于 3.6 可能 Bloom/SSR 部分参数不兼容（hasattr 已经做了兜底，但效果会减弱）
