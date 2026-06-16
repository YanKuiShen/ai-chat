# AI Chat v3.4.4 交接文档 - Blender 建模工具扩展

## ✅ 已完成工作

### 插件端新增 6 个高精度建模工具

**文件**: `blender_addon/aichat_bridge/__init__.py`

| 工具名 | 功能 | 参数 | 代码位置 |
|--------|------|------|----------|
| `boolean_union` | 布尔并集 | `target_name`, `tool_name` | 1279-1304 行 |
| `boolean_difference` | 布尔差集 | `target_name`, `tool_name` | 1305-1329 行 |
| `boolean_intersect` | 布尔交集 | `target_name`, `tool_name` | 1331-1354 行 |
| `add_subdivision` | 细分曲面 | `name`, `levels`(1-5), `render_levels` | 1357-1379 行 |
| `add_bevel` | 倒角 | `name`, `width`, `segments`, `affect`(EDGES/VERTICES) | 1380-1402 行 |
| `smart_smooth` | 智能平滑 | `name`, `angle_limit` | 1404-1425 行 |

**修改清单**:
1. ✅ 新增 6 个 handler 函数 (`_mcp_boolean_union_main` 等)
2. ✅ MCP_MAIN_HANDLERS 路由表添加新工具（第 1430-1435 行）
3. ✅ MCP_TOOLS schema 添加新工具定义（第 1593-1645 行）

---

## 📋 下一阶段待办

### P0 必须做（阻塞）

#### 1. server.js - 添加新工具的 preflight 检查
**位置**: `server.js` 第 918-1002 行 `_preflightExecPython()` 函数

**需要添加的规则（完整代码）**:
```javascript
// 坑 6：boolean 工具 target_name 不存在时 Blender 崩溃
// 位置：在 _preflightExecPython 函数的 issues 数组检查之后、return null 之前
const BOOLEAN_TOOLS = ['boolean_union', 'boolean_difference', 'boolean_intersect'];
if (BOOLEAN_TOOLS.includes(toolName)) {
  // boolean 工具走工具级检查，不是代码检查
  const targetName = args?.target_name;
  const toolName2 = args?.tool_name;
  if (!targetName || typeof targetName !== 'string' || !targetName.trim()) {
    return {
      ok: false,
      error_type: 'preflight_param',
      error: 'boolean 工具的 target_name 不能为空',
      hint: 'target_name 必须是已存在的 Blender 物体名'
    };
  }
  if (!toolName2 || typeof toolName2 !== 'string' || !toolName2.trim()) {
    return {
      ok: false,
      error_type: 'preflight_param',
      error: 'boolean 工具的 tool_name 不能为空',
      hint: 'tool_name 必须是已存在的 Blender 物体名（布尔后会删除）'
    };
  }
}

// 坑 7：add_subdivision levels 超出范围（1-5）
if (toolName === 'add_subdivision') {
  const levels = args?.levels;
  if (levels !== undefined && (typeof levels !== 'number' || levels < 1 || levels > 5)) {
    return {
      ok: false,
      error_type: 'preflight_param',
      error: 'add_subdivision 的 levels 必须在 1-5 范围内',
      hint: 'levels 太高（如 6+）会卡死 Blender，建议 view=2, render=3'
    };
  }
}

// 坑 8：add_bevel affect 枚举值错误
if (toolName === 'add_bevel') {
  const affect = args?.affect;
  if (affect !== undefined && affect !== 'EDGES' && affect !== 'VERTICES') {
    return {
      ok: false,
      error_type: 'preflight_param',
      error: "add_bevel 的 affect 必须是 'EDGES' 或 'VERTICES'",
      hint: "Blender 4.2+ 用 affect 替代已移除的 vertex_only=True"
    };
  }
}
```

#### 2. index.html - 在 CLIENT_TOOLS 注册新工具
**位置**: `index.html` 约第 13069 行 `const CLIENT_TOOLS = [` 之后

**需要添加 6 个工具定义（完整代码）**:
```javascript
// 位置：在 CLIENT_TOOLS 数组中，search_polyhaven_textures 之前添加

// ========== v3.4.4 新增建模工具 ==========

// 布尔并集
{
  name: 'boolean_union',
  description: '【v3.4.4 ⭐】布尔并集：将 target 和 cutter 两个物体合并为一个（cutter 被删除）。用于创建复杂形状如 L 形 / 门洞。',
  parameters: {
    type: 'object',
    properties: {
      target_name: { type: 'string', description: '目标物体名（被保留）' },
      tool_name: { type: 'string', description: '工具物体名（会被删除并合并）' }
    },
    required: ['target_name', 'tool_name']
  }
},

// 布尔差集
{
  name: 'boolean_difference',
  description: '【v3.4.4 ⭐】布尔差集：从 target 减去 cutter 部分（cutter 被删除）。用于创建门洞/窗洞/雕刻。',
  parameters: {
    type: 'object',
    properties: {
      target_name: { type: 'string', description: '目标物体名（被挖空）' },
      tool_name: { type: 'string', description: '工具物体名（会被删除）' }
    },
    required: ['target_name', 'tool_name']
  }
},

// 布尔交集
{
  name: 'boolean_intersect',
  description: '【v3.4.4 ⭐】布尔交集：只保留 target 和 cutter 的重叠部分（cutter 被删除）。用于提取复杂形状的交叉区域。',
  parameters: {
    type: 'object',
    properties: {
      target_name: { type: 'string', description: '目标物体名（被保留）' },
      tool_name: { type: 'string', description: '工具物体名（会被删除）' }
    },
    required: ['target_name', 'tool_name']
  }
},

// 细分曲面
{
  name: 'add_subdivision',
  description: '【v3.4.4 ⭐】添加细分曲面修改器（Catmull-Clark），使物体更平滑。levels 不能超过 5（太高会卡死 Blender）。',
  parameters: {
    type: 'object',
    properties: {
      name: { type: 'string', description: '物体名' },
      levels: { type: 'integer', description: '视口细分层级（1-5），默认 2' },
      render_levels: { type: 'integer', description: '渲染细分层级，默认比 levels 高 1' }
    },
    required: ['name']
  }
},

// 倒角
{
  name: 'add_bevel',
  description: '【v3.4.4 ⭐】添加倒角修改器（Blender 4.2+ 兼容，affect="EDGES" 而非已移除的 vertex_only=True）。用于圆滑边缘。',
  parameters: {
    type: 'object',
    properties: {
      name: { type: 'string', description: '物体名' },
      width: { type: 'number', description: '倒角宽度，默认 0.05' },
      segments: { type: 'integer', description: '倒角段数，默认 3' },
      affect: { type: 'string', enum: ['EDGES', 'VERTICES'], description: '影响边或顶点，默认 EDGES' }
    },
    required: ['name']
  }
},

// 智能平滑
{
  name: 'smart_smooth',
  description: '【v3.4.4 ⭐】智能平滑：自动设置法线平滑和 auto_smooth_angle，使物体表面光滑无棱角。',
  parameters: {
    type: 'object',
    properties: {
      name: { type: 'string', description: '物体名' },
      angle_limit: { type: 'number', description: '角度阈值（度），默认 30' }
    },
    required: ['name']
  }
},

// ========== 原有工具保持不变 ==========
```

#### 3. index.html - 更新 MCP system prompt
**位置**: `index.html` 约第 15592 行左右的 system prompt

**需要添加的内容（完整代码）**:
```javascript
// 位置：在 modeler system prompt 的「禁止」部分之后添加

### 🏷 v3.4.4 新工具决策树 ⭐⭐⭐

**布尔运算工具（需要两个物体）**：
- 合并两个物体 → `boolean_union(target_name, tool_name)`
- 挖空/开门洞 → `boolean_difference(target_name, tool_name)`
- 提取交叉区域 → `boolean_intersect(target_name, tool_name)`

**细分与平滑（单个物体）**：
- 平滑几何体（枕头/人体/有机形态）→ `add_subdivision(name, levels=2, render_levels=3)`
- 圆滑边缘（机械零件/建筑）→ `add_bevel(name, width=0.05, segments=3, affect='EDGES')`
- 自动平滑着色（无硬边）→ `smart_smooth(name, angle_limit=30)`

### 🔧 布尔运算常见错误

❌ 错误：`target_name` 或 `tool_name` 不存在 → Blender 崩溃
✅ 正确：先用 `get_scene_info` 确认两个物体都存在

❌ 错误：两个物体都是非 MESH 类型
✅ 正确：布尔只能用于 MESH 类型物体

### 反踩坑速查（v3.4.4 新增）

| 错误 | 正确 |
|------|------|
| `levels=6`（太高） | `levels=2`（view）/ `render_levels=3` |
| `affect='VERTICES'` 写错 | 只能是 `'EDGES'` 或 `'VERTICES'` |
| boolean 工具缺参数 | 必须同时传 `target_name` 和 `tool_name` |
```

---

### P1 建议做 - 贴图精度提升（v3.5.0 重点）

#### 现有贴图功能分析

| 功能 | 状态 | 文件位置 |
|------|------|----------|
| `search_polyhaven_textures` | ✅ 已实现 | index.html CLIENT_TOOLS |
| `apply_polyhaven_texture` | ✅ 已实现 | index.html _runClientTool |
| `apply_pbr_material` 模板 | ✅ 已实现 | scripts/bmesh-templates.json |
| `ph_query` / `ph_uv_scale` 属性 | ✅ 已实现 | aichat_bridge |
| server.js 贴图代理 | ✅ 已实现 | server.js 约 1180-1350 行 |

#### 贴图精度问题诊断

1. **AI 仍倾向程序纹理**：虽然有 PBR 贴图工具，但 AI 常忘记使用
2. **缺少 UV 编辑工具**：无法自动投射/展开 UV
3. **缺少贴图烘焙工具**：无法烘焙法线/AO/置换贴图
4. **缺少三平面投射**：复杂几何体无法快速贴图

#### 贴图精度提升方案（详细实现）

**方案 A：增强 AI 贴图决策（快速实现）**
```javascript
// 在 modeler system prompt 中强化贴图决策树
// 位置：index.html 约 15592 行，AGENT_ROLE_PROMPTS.modeler

贴图决策树（必须按顺序检查）：
1. 复杂表面（木地板/砖墙/大理石/布料/皮革）→ 
   search_polyhaven_textures(query="wood floor", limit=5) → 
   apply_polyhaven_texture(object_name, slug, resolution="2k")
2. 简单表面（单色塑料/基础色）→ set_material + PBR 参数
3. 金属表面（黄铜/不锈钢/铝合金）→ 必须用 PBR 贴图
4. 自然表面（草地/泥土/岩石）→ 必须用 PBR 贴图

// 禁止：AI 不能用程序纹理（Noise/Voronoi/Distorted Noise 等）伪装真实材质
```

**方案 B：新增 UV 智能投射工具（中等实现）**
```python
# 位置：blender_addon/aichat_bridge/__init__.py，约 1425 行后添加

def _mcp_smart_uv_project_main(payload):
    """智能 UV 投射 - 自动选择最佳投射方式"""
    name = (payload.get("name") or "").strip()
    island_margin = float(payload.get("island_margin") or 0.02)
    angle_limit = float(payload.get("angle_limit") or 66.0)
    method = payload.get("method") or "smart"  # smart / cube / cylinder / sphere
    
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        
        if method == "smart":
            bpy.ops.uv.smart_project(angle_limit=math.radians(angle_limit), island_margin=island_margin)
        elif method == "cube":
            bpy.ops.uv.cube_project()
        elif method == "cylinder":
            bpy.ops.uv.cylinder_project()
        elif method == "sphere":
            bpy.ops.uv.sphere_project()
        
        bpy.ops.object.mode_set(mode='OBJECT')
        return {"ok": True, "data": {"name": obj.name, "method": method, "island_margin": island_margin}}
    except Exception as e:
        return {"ok": False, "error": "smart_uv_project: %s" % e}

# MCP_TOOLS schema 添加：
{
    "name": "smart_uv_project",
    "description": "智能 UV 投射 - 自动选择最佳投射方式（smart/cube/cylinder/sphere）",
    "_route": "main",
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string", "description": "物体名"},
        "island_margin": {"type": "number", "description": "岛间距，默认 0.02"},
        "angle_limit": {"type": "number", "description": "角度限制（度），默认 66"},
        "method": {"type": "string", "enum": ["smart", "cube", "cylinder", "sphere"], "description": "投射方式，默认 smart"}
    }, "required": ["name"]}
}
```

**方案 C：新增三平面投射工具（中等实现）**
```python
# 位置：blender_addon/aichat_bridge/__init__.py，约 1450 行后添加

def _mcp_triplanar_projection_main(payload):
    """三平面投射 - 复杂几何体快速贴图"""
    name = (payload.get("name") or "").strip()
    scale = float(payload.get("scale") or 1.0)
    
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    
    try:
        mat = obj.data.materials.get("Triplanar_Mat")
        if not mat:
            mat = bpy.data.materials.new(name="Triplanar_Mat")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        
        # 创建三平面投射节点组
        output = nt.nodes.new('ShaderNodeOutputMaterial')
        output.location = (600, 0)
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (300, 0)
        nt.links.new(bsdf.outputs[0], output.inputs[0])
        
        # 添加 Texture Coordinate + Mapping
        tex_coord = nt.nodes.new('ShaderNodeTexCoord')
        tex_coord.location = (-800, 0)
        mapping = nt.nodes.new('ShaderNodeMapping')
        mapping.location = (-600, 0)
        mapping.inputs['Scale'].default_value = (scale, scale, scale)
        nt.links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
        
        return {"ok": True, "data": {"name": obj.name, "material": "Triplanar_Mat", "scale": scale}}
    except Exception as e:
        return {"ok": False, "error": "triplanar_projection: %s" % e}
```

**方案 D：扩展 PolyHaven 贴图类别（快速实现）**
```javascript
// 位置：server.js，约 1250 行 _polyhavenFetchAssetList 之后

// 增加贴图子分类搜索
function _polyhavenSearchTexturesByCategory(assets, category, query, limit) {
  // category: wood_floor / wood_wall / metal / fabric / stone / concrete 等
  const filtered = assets.filter(a => {
    const cats = (a.categories || []).map(c => c.toLowerCase());
    return cats.some(c => c.includes(category.toLowerCase()));
  });
  return _polyhavenScoreAndPick(filtered, query, limit);
}
```

---

### P2 建议做

4. **扩展场景模板库**（+20 模板）
   - 文件: `blender_addon/aichat_bridge/__init__.py`
   - 位置: 查找 `SCENE_TEMPLATES` 或类似结构

5. **实现实时过程动画功能**
   - 需要前端 UI 支持
   - 建议放在 `index.html` 的 Agent 面板

---

### P3 可选

6. **清理 `blender-mcp-main` 冗余代码**
   - 路径: `blender-mcp-main/`
   - 确认哪些代码已被 `aichat_bridge` 替代

7. **材质节点自动化**
   - 新增 `build_material_nodes` 工具
   - 让 AI 能构建复杂节点树

---

## 🔍 关键代码位置速查表

| 用途 | 文件 | 行数 | 说明 |
|------|------|------|----------|
| 插件工具定义 | `blender_addon/aichat_bridge/__init__.py` | 1273-1489 | 6 个新工具的 handler |
| 插件工具路由 | `blender_addon/aichat_bridge/__init__.py` | 1430-1435 | MCP_MAIN_HANDLERS |
| 插件工具 schema | `blender_addon/aichat_bridge/__init__.py` | 1593-1645 | MCP_TOOLS 定义 |
| server.js preflight | `server.js` | 918-1002 | `_preflightExecPython()` 函数 |
| server.js 贴图代理 | `server.js` | 约 1180-1350 | PolyHaven 贴图端点 |
| 前端 CLIENT_TOOLS | `index.html` | 约 13069-13284 | 客户端工具注册 |
| 前端贴图工具 | `index.html` | `_runClientTool` case | search/apply_polyhaven_texture |
| 前端工具检查 | `index.html` | 约 13284 | `isClientTool()` 函数 |
| MCP system prompt | `index.html` | 约 15592-15640 | Agent 系统提示 |
| PBR 材质模板 | `scripts/bmesh-templates.json` | apply_pbr_material | 自动构建 PBR 节点链 |
| 工具加载逻辑 | `index.html` | 约 14061-14063 | prepend CLIENT_TOOLS |

---

## 💡 新工具使用场景

### boolean_union / boolean_difference / boolean_intersect
- **场景**: 合并两个物体 / 从一个物体减去另一个 / 取交集
- **典型用法**: "把这两个立方体合并成一个" / "在这个墙上开个门洞"
- **参数**: `target_name` (要被操作的物体), `tool_name` (工具物体)
- **注意**: 需要两个物体都存在，目标物体要有足够的几何体

### add_subdivision
- **场景**: 平滑几何体 / 增加细分
- **典型用法**: "给这个球加细分让它更平滑" / "枕头需要更高的细分"
- **参数**: `name`, `levels`(1-5), `render_levels`
- **注意**: levels 太高会增加渲染负担，建议 view=2, render=3

### add_bevel
- **场景**: 创建倒角 / 圆边
- **典型用法**: "给这个盒子加倒角让它看起来更真实" / "机械零件需要斜切边"
- **参数**: `name`, `width`, `segments`, `affect`
- **注意**: Blender 4.2+ 用 `affect` 代替 `vertex_only`

### smart_smooth
- **场景**: 自动平滑着色
- **典型用法**: "平滑这个物体但不要过曝" / "根据角度自动平滑"
- **参数**: `name`, `angle_limit`
- **注意**: angle_limit 控制平滑的阈值（通常 30-60 度）

---

## 🧪 测试用例清单

### 布尔运算工具测试

| 测试用例 | 输入 | 预期结果 |
|---------|------|----------|
| boolean_union 正常 | target="Cube", tool="Cylinder" | 返回 ok:true, cutter 删除 |
| boolean_union 缺参数 | target="", tool="" | 返回 ok:false, error 提示 |
| boolean_difference 正常 | target="Cube", tool="Sphere" | 返回 ok:true, 球形空洞 |
| boolean_difference 非 MESH | target="Light", tool="Cube" | 返回 ok:false, 类型错误 |
| boolean_intersect 正常 | target="Cube", tool="Torus" | 返回 ok:true, 交叉部分 |

### 细分与平滑工具测试

| 测试用例 | 输入 | 预期结果 |
|---------|------|----------|
| add_subdivision levels=3 | name="Sphere", levels=3 | 返回 ok:true, modifier 添加 |
| add_subdivision levels=6 | name="Cube", levels=6 | 返回 ok:false, 超出范围 |
| add_bevel 正常 | name="Cube", width=0.1 | 返回 ok:true, Bevel modifier |
| add_bevel affect='VERTICES' | name="Cube", affect='VERTICES' | 返回 ok:true |
| smart_smooth 正常 | name="Torus", angle_limit=45 | 返回 ok:true, 平滑着色 |

---

## 🔧 用户测试发现的新问题（v3.4.4 打包测试）

### 问题 1：材质节点访问 None 对象
**错误**：`'NoneType' object has no attribute 'inputs'`
**原因**：AI 尝试访问材质节点时，该节点可能不存在（如 Emission node 未正确创建）
**建议**：在 bpy 代码中增加空值检查

### 问题 2：EEVEE 颜色映射枚举值错误
**错误**：`enum "High Contrast" not found in ('None', 'AgX - Punchy', 'AgX - Greyscale', ...)`
**原因**：正确的枚举值是 `AgX - High Contrast`（含前缀），AI 写的是 `High Contrast`（缺少前缀）
**建议**：在 preflight 中添加正则检查：
```javascript
// 坑 9：EEVEE 颜色映射/合成器预设枚举值错误
if (/view_settings\.view_transform\s*=\s*['"]High Contrast['"]/i.test(code) || 
    /film_grain\.preset\s*=\s*['"]High Contrast['"]/i.test(code)) {
  issues.push({
    type: 'enum_misuse',
    bad: "view_transform = 'High Contrast'",
    good: "view_transform = 'AgX - High Contrast'  # 必须加 'AgX - ' 前缀",
    hint: "Blender 4.x EEVEE/AgX 颜色映射枚举值格式是 'AgX - xxx'，不是直接写 xxx"
  });
}
```

### 问题 3：建模精度差 - 参考图没有被正确使用 ⚠️⚠️⚠️

**用户反馈**：AI 生成的复古电视机和参考图差距很大（左图是 AI 生成的，右图是参考图）

**根因分析**：
1. **参考图可能没有被传给 AI** - MCP 模式下需要检查 `agentState.referenceImages` 是否正确传递
2. **AI 没有进行视觉反馈循环** - AI 没有调 `get_viewport_screenshot` 看效果后再修正

**已有的"边看边干"机制（但可能没生效）**：
- ✅ `mcpAllowScreenshotTool` 开关（默认 true）控制 AI 是否能看到 `get_viewport_screenshot` 工具
- ✅ Critic 角色机制（Round N-1）会自动调 `get_viewport_screenshot` 审图
- ✅ worker_self_check 会自动截图审图

**检查清单**：
1. **确认参考图已上传**：用户需要在智能 Agent 面板上传参考图（或用「📋 从一键3D导入四宫格」）
2. **确认 AI 能看到参考图**：`mcpAllowScreenshotTool` 开关是否打开？
3. **确认视觉模型**：AI 模型是否支持视觉？（Claude / GPT-4o / Gemini / Qwen-VL）
4. **确认 MCP 模式**：是否使用了「🛠 MCP Agent 循环」模式（不是「📝 脚本生成大师」）？

### 问题 4：缺少强制视觉反馈循环 ⚠️⚠️⚠️

**建议修复**：在 MCP Agent 的 system prompt 中强化"边看边干"要求

**需要在 index.html 中添加的规则**：
```javascript
// 位置：在 modeler system prompt 中添加

### 🔄 边看边干强制规则 ⭐⭐⭐

**每完成 2-3 个工具调用后必须**：
1. 调 `get_viewport_screenshot` 看当前 Blender 视口效果
2. 对比参考图，检查比例/材质/位置是否正确
3. 如有问题立刻修正，不要等到最后

**参考图使用规则**：
- 如果用户上传了参考图，必须以参考图为准
- 参考图中的比例、材质、颜色 > 文字描述
- 建完每个物体后要对比参考图确认效果

**禁止**：
- ❌ 建完所有物体后再看效果（太晚发现问题）
- ❌ 只看文字描述不看参考图
- ❌ 不调 get_viewport_screenshot 直接结束
```

---

## 🏷 PolyHaven 贴图标签铁律（已有，保持）

AI 每次创建 mesh 后必须设置 `ph_query` 和 `ph_uv_scale` 属性：
```python
obj["ph_query"] = "wood floor"  # 英文关键词
obj["ph_uv_scale"] = 2.0       # UV 缩放
```

---

## 📝 注意事项

1. **上下文快到时**: 建议先完成 P0 的 3 个必须项，确保新工具能被 AI 识别和使用
2. **向后兼容**: 新工具不影响现有工具，新旧工具可以共存
3. **测试建议**: 每个新工具在 Blender 中手动测试一次，确认参数正确
4. **错误处理**: 检查 Blender 端返回的错误格式，确保前端能正确解析
5. **贴图优先**: v3.5.0 重点提升贴图精度，AI 应优先使用 PBR 贴图而非程序纹理
6. **布尔安全**: boolean 工具操作前先确认两个物体都存在
7. **材质安全**: 访问 node.inputs 前先检查 node 是否为 None
8. **枚举前缀**: Blender 4.x 枚举值常带前缀（如 `AgX - `），AI 常漏写

---

**交接时间**: 2026-06-11
**下一步**: 完成 P0 的 3 个必须项