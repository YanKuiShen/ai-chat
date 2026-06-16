# 🚀 v1.7.0 发布说明 · PolyHaven 网络资产引擎 + 防 GPU 炸

> **发布日期**：2026-05-17
> **版本号**：1.7.0
> **配套插件版本**：`aichat_bridge` 1.1.0（无需重装，向后兼容）
> **本次发布是 MINOR 升级**：新增「PolyHaven 网络资产引擎」+ `search_query` 模糊搜索 + `change_object_color` 工具函数 + 4 项跨会话累积的稳定性修复，完全向后兼容 v1.6.x


---

## 🎨 1. 新增「PolyHaven 网络资产引擎」⭐ 核心特性

### 设计哲学

- **保留**「⚡ AI 从零生成」(原引擎，AI 直接写 bpy 代码，速度快但几何粗糙)
- **新增**「🎨 PolyHaven 网络资产」(AI 只输出资产清单 JSON，由 Blender 端 urllib **真实下载** PBR 模型/HDRI/材质)

### 工作原理

```
用户场景描述
       ↓
[前端 AI] 输出 <polyhaven_plan> JSON
       ↓
{
  "hdri": { "asset_id": "studio_small_03", "resolution": "2k" },
  "ground": { "texture_id": "wood_planks_grey" },
  "objects": [
    { "asset_id": "vintage_wooden_chair", "location": [0,0,0], "scale": 1.0 },
    { "asset_id": "wooden_table_02", "location": [0,2,0], "scale": 1.2 },
    ...
  ],
  "camera": { "location": [7,-7,5], ... }
}
       ↓
[前端] agentBuildPolyHavenCode() 编译成 Blender Python 代码
       ↓
[Blender 端] urllib 调用 https://api.polyhaven.com/files/{asset_id}
       ↓
[Blender 端] 下载 .blend / .hdr / .jpg 到本地缓存目录
       ↓
[Blender 端] bpy.data.libraries.load(.blend) + scene_coll.children.link()
       ↓
✅ 真实 PBR 资产组装到场景，CC0 协议免授权商用
```

### 资产库（前端 prompt 内置常用 ID 清单）

- **18 张 HDRI**：摄影棚 / 蓝天 / 日落 / 室内 / 户外 / 夜景 / 工厂等场景
- **25 个模型**：椅子/桌子/沙发/书架/盆栽/电视/灯具/装饰物等
- **9 套 PBR 贴图**：木地板/砖墙/水泥/金属等

### 性能与体验

| 维度 | AI 从零 | PolyHaven |
|---|---|---|
| 速度 | ~45s | 首次 30~120s（下载）/ 后续 ~30s（本地缓存命中） |
| 几何质量 | 粗糙（cube/sphere 拼接） | 专业级（带 UV/法线/PBR） |
| 材质质量 | AI 凭空猜 | 真实 PBR（diffuse/normal/roughness） |
| HDRI 环境 | 纯色背景 | 4K HDRI 环境光 + 反射 |
| 网络依赖 | 无 | 首次需访问 polyhaven.com |
| 资产授权 | N/A | CC0 协议，免授权商用 |

### UI 切换

- 在「🎬 智能 Agent 实时渲染」面板新增「🎨 生成方式」单选框
- 默认 `ai-only`,用户可自由切换到 `polyhaven`
- 状态持久化到 `localStorage.agentState_v168.generationMode`

---

## 🔍 1.1 `search_query` 模糊搜索 ⭐ v1.7.0 新增

### 痛点

AI 输出 `<polyhaven_plan>` 时容易猜错 `asset_id`(PolyHaven 的真实 ID 是 snake_case 英文,例如 `vintage_wooden_chair`)。猜错的资产会全部走 `[MISSING_ASSET]_xxx` 占位 Cube 兜底,画面里全是红色立方体。

### 解决方案

为 `objects / hdri / ground` 三类资产新增 `search_query` 备用字段。AI 不确定具体 ID 时填【英文关键词】(如 `"chair"`、`"wooden table"`、`"plant"`),Blender 端走如下流程:

```
AI 输出 { "search_query": "vintage chair" }
         ↓
Blender 端 resolve_search_query() 调本机:
  GET http://127.0.0.1:3456/api/polyhaven/search?q=vintage+chair&type=models
         ↓
server.js 后端代理:
  1) 拉 https://api.polyhaven.com/assets?type=models 全量清单(6h 缓存)
  2) 对 1500+ 模型做 name×3 + categories×2 + tags×1 加权打分
  3) 排序后返回 Top 3
         ↓
Blender 端拿到最高分 asset_id="vintage_wooden_chair" → 走原 append 流程
```

### 三个 PolyHaven 后端代理 API(`server.js`)

| 端点 | 用途 | 缓存策略 |
|---|---|---|
| `GET /api/polyhaven/search?q=xxx&type=models\|hdris\|textures&limit=8` | 加权模糊搜索 | 全量清单 6h |
| `GET /api/polyhaven/files?asset_id=xxx` | 透传 `https://api.polyhaven.com/files/{asset_id}`(解决 CORS) | 无 |
| `GET /api/polyhaven/download?url=xxx&filename=xxx` | 流式 SSE 下载(实时进度推送) | 写入 `$TMP/aichat_polyhaven_cache/`,已存在则跳过 |

### AI prompt 字段示例

```json
{
  "search_query": "vintage chair",
  "name": "chair_1",
  "location": [0, 0, 0],
  "expected_dimensions_m": [0.5, 0.5, 0.9]
}
```

`asset_id` 和 `search_query` **任填一个即可**(同时填则优先 `asset_id`)。

### 实现细节

- 编译时由 `agentBuildPolyHavenCode(plan, serverBaseUrl)` 把 `location.origin` 注入 Python 端 `SERVER_BASE_URL` 常量(因 server 端口可能因占用顺延,必须动态拿当前 host:port)
- Blender 端 `resolve_search_query()` 有内存级 `_SEARCH_RESOLVE_CACHE`,同一关键词在一次 plan 里只查一次
- 找不到时返回 `None` → 上层走 `[MISSING_ASSET]_xxx` 占位 Cube 兜底,不阻断后续灯光/相机

---

## 🎨 1.2 `change_object_color` / `recolor` 工具函数 · v1.7.0 新增

### 痛点

PolyHaven 下载的 `.blend` 资产**自带 PBR 贴图**(沙发原色是米白等)。如果 AI 想改成黑色,直接 `bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.05, 1)` **完全无效**,因为 Base Color 端口被 `ShaderNodeTexImage` 占用了。

### 解决方案

在 PolyHaven 生成代码的尾部自动注册两个全局工具函数,AI 在自检阶段可直接调用:

**`change_object_color(obj, target_color_rgba, brightness_factor=1.0)`**

工作流(自动判断有/无贴图两种情况):
1. 遍历该物体的所有材质,进入 `node_tree`,找到 Principled BSDF
2. 检查 Base Color 端口是否连接了 `ShaderNodeTexImage`(贴图):
   - **有贴图** → 在【贴图】和【BSDF】之间插入 `ShaderNodeHueSaturation` 节点,根据 `target_color_rgba` 算出 Hue/Saturation/Value 调整色调(例:变黑 → Value 降到 0.1)
   - **无贴图** → 直接修改 BSDF Base Color
3. 链路上已有 `HueSaturation` 节点 → 复用而不重复插入

**`recolor(obj_name_or_obj, hex_or_rgb, brightness=1.0)`** —— 便捷封装,支持 hex 字符串

```python
recolor("sofa", "#1a1a1a")                                       # 把白沙发变黑
recolor(obj, (1, 0, 0), brightness=0.6)                          # 变红 + 暗一点
change_object_color(bpy.data.objects["sofa"], (0.05,0.05,0.05,1))
```

完整 `try/except` 包裹,单点失败不影响整体流程。运行时会 print 出每个 slot 的成功/失败统计。

---

## 🛡️ 2. v1.6.9 防御 header 自动注入(治 AI 错写 BL_VER 整段崩)


### 痛点

- Gemini 3.1 Pro / Claude 等 AI 偶尔会忘记定义 `BL_VER` 全局变量，直接用 `BL_VER >= 4` 导致 `NameError`
- 一旦 `exec()` 抛 `NameError`，整段代码中断，只剩下最先创建的地板 plane

### 解决方案

把 v1.6.9 的防御 header（`BL_VER / IS_4_PLUS / IS_5_PLUS` 等关键变量定义 + quad view 关闭逻辑）**自动注入到每次 `agentPushCode` 调用**：

```js
async function agentPushCode(code, sceneName) {
  const url = agentState.bridgeUrl.trim().replace(/\/+$/, '');
  const wrappedCode = agentInjectDefensive(code);  // v1.7.0 自动注入
  const res = await fetch(url + '/exec', {
    method: 'POST',
    body: JSON.stringify({ code: wrappedCode, ... })
  });
  ...
}
```

集中在最底层注入，**所有 caller**（agentRunNoneMode / agentRunFinalMode / agentRunIncrementalMode / agentRunPolyHavenMode）都无需手动调 `agentInjectDefensive()`，更不易漏。

---

## 🚀 3. 防 GPU 4 倍负载卡死（v1.6.9 安全壳升级）

### 痛点

- v1.6.5 安全壳遍历所有 3D 视口同时打开 RENDERED 模式
- 用户如果开了 Blender 的 **quad view（4 视图分屏）**，GPU 直接 ×4 负载 → 卡死

### 解决方案

1. **只切第一个 3D 视口**到 RENDERED（不再遍历）
2. **强制关闭 quad view**（用 `bpy.ops.screen.region_quadview()` + `temp_override`）

代码（已在 v1.6.9 安全壳中实现）：

```python
# 4) v1.6.9：只切【第一个 3D 视口】到 RENDERED + 强制关闭 quad view（防 GPU 4 倍负载）
try:
    _first_v3d = None
    for _area in _bpy_safety.context.screen.areas:
        if _area.type == "VIEW_3D":
            _first_v3d = _area
            break
    if _first_v3d:
        # 关闭 quad view（4 视图）→ 只渲染 1 个视口
        try:
            for _sp in _first_v3d.spaces:
                if _sp.type == "VIEW_3D" and getattr(_sp, "region_quadviews", None):
                    with _bpy_safety.context.temp_override(area=_first_v3d):
                        _bpy_safety.ops.screen.region_quadview()
                    break
        except Exception:
            pass
        # 只切第一个视口到 RENDERED
        for _sp in _first_v3d.spaces:
            if _sp.type == "VIEW_3D":
                _sp.shading.type = "RENDERED"
                break
        print("[v1.6.9 安全壳] ✓ 第一个 3D 视口已切到 RENDERED（已关闭 quad view 防 GPU 炸）")
except Exception as _e:
    print("[v1.6.9 安全壳] ⚠️ 视口切换失败:", _e)
```

---

## 💭 4. server.js 转发 reasoning_content（治推理模型空白）

### 痛点

- Claude / DeepSeek / GPT-o1 等推理模型在思考阶段会输出 `reasoning_content` 而不是 `content`
- 老版本 server.js 只转发 `content` 字段 → 用户按下后 30~120 秒**干瞪眼**，以为系统卡了

### 解决方案

`server.js` 的 `/api/chat` SSE 转发层新增对 `delta.reasoning_content` 的支持：

```js
if (data.choices && data.choices[0].delta) {
  const delta = data.choices[0].delta;
  if (delta.reasoning_content) {
    sendEvent({ reasoning: delta.reasoning_content });  // v1.7.0 新增
  }
  if (delta.content) {
    sendEvent({ content: delta.content });
  }
}
```

`m3dCallLLM` 同步新增 `onReasoning` 第 7 参数（向后兼容，不传则按老行为）：

```js
async function m3dCallLLM(configId, model, messages, sysPrompt, signal, onChunk, onReasoning) {
  // ...
  else if (data.reasoning) {
    reasoning += data.reasoning;
    if (onReasoning) onReasoning(data.reasoning, reasoning);
  }
}
```

---

## 📋 实施清单

### 前端（`ai-chat/public/index.html`）
- [x] 新增 `AGENT_POLYHAVEN_PROMPT` 常量（500+ 行 prompt，含 52 个 PolyHaven 常用资产 ID）
- [x] 新增 `agentExtractPolyHavenPlan(text)` —— 从 AI 返回中提取 JSON
- [x] 新增 `agentBuildPolyHavenCode(plan)` —— 把 JSON 编译成 Blender Python（含 urllib 下载 + bpy.ops.wm.append + HDRI 节点构造）
- [x] 新增 `agentRunPolyHavenMode()` —— 引擎入口，AI 出 JSON → 编译 → 一次推送
- [x] `agentStartRun()` 按 `generationMode` 分流（polyhaven 走新引擎，否则走老引擎）
- [x] `agentPushCode()` 内部自动调用 `agentInjectDefensive()`
- [x] UI 新增「🎨 生成方式」单选框 (`agent-gen-mode`)
- [x] `agentInit` / `agentSaveState` 持久化 `generationMode`
- [x] 欢迎弹窗 `hasLaunched_v1.7.0` 升级 + v1.7.0 章节

### 后端（`ai-chat/server.js`）
- [x] `/api/chat` SSE 转发 `delta.reasoning_content` 为 `{reasoning: ...}`
- [x] `m3dCallLLM` 新增第 7 参 `onReasoning`，向后兼容

### Blender 插件（`ai-chat/blender_addon/aichat_bridge/__init__.py`）
- 无改动（1.1.0 已足够，PolyHaven 引擎完全在 `/exec` 端口内完成）
- [x] `npm run build:addon` 重新打包 zip（保持 1.1.0 不变）

### 文档
- [x] `package.json` 1.6.6 → 1.7.0 + description 更新
- [x] `RELEASE_v1.7.0.md`（本文件）
- [x] `CHANGELOG.md` 顶部 `[1.7.0]` 章节

### 打包（留给用户手动）
- [ ] `npm run build:mac`（耗时长，留给用户）
- [ ] `npm run build:win`（耗时长，留给用户）

---

## 📊 v1.6.6 → v1.7.0 改动统计

| 类型 | 行数 |
|---|---|
| `public/index.html` 新增 PolyHaven 引擎 | ~600 行 |
| `public/index.html` 修 `agentPushCode` + 欢迎弹窗 | ~40 行 |
| `server.js` reasoning_content 转发 | ~6 行 |
| 文档（本文件 + CHANGELOG） | ~250 行 |
| **总计** | **~900 行** |

---

## 🆘 升级注意

1. **完全向后兼容**：老用户的 `agentState_v168` localStorage 会自动迁移，`generationMode` 默认 `ai-only`
2. **Blender 插件 1.1.0 即可**，无需重装
3. **首次使用 PolyHaven 模式**：建议先用 `1k` HDRI + 6 个模型试一次（约 30~60s），确认能正常下载
4. **如果 polyhaven.com 在你的网络环境无法访问**：仍可使用「⚡ AI 从零生成」模式（PolyHaven 模式只在用户主动选择时才走网络）
5. **资产缓存目录**：在 Blender 端为 `$TMP/aichat_polyhaven_cache/`，重复使用同一资产不会重复下载

---

## 🙏 致谢

感谢用户提的金点子：
- **「让 AI 输出资产清单 JSON 而不是 mesh 代码」** → 直接催生了 PolyHaven 引擎，让画质从「cube 拼接」跨越到「PBR 专业级」

这就是从「AI 写代码」到 **「AI 调度生态」** 的关键一跃。
