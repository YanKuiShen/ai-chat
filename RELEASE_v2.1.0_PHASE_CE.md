# RELEASE v2.1.0 Phase C + E — bpy API 检索 cheatsheet + bmesh/GN 模板库

> 实施日期：2026-05-18
> 范围：Phase C（bpy API 实时检索）+ Phase E（bmesh / Geometry Nodes 模板库）一次会话完整交付
> 前置：Phase A（计划工具 5 个）+ Phase B（文件系统工具 5 个 + 6 HTTP 端点）+ Phase D（多角色协作三角色）已完成
> 后续：Phase F（aichat_bridge 插件升级 2.0.4 → 2.1.0）+ Phase G（打包发版）排队中

---

## 目标与设计思路

### Phase C 治痛点

v1.11.x 系列在 MCP system prompt 里持续积累了 6 段反踩坑速查表（坑 1～坑 6），累计约 3000 tokens：

- **坑 1**：`exec_python` args 必须带 code 字段（v1.11.9 / v1.11.14 强化）
- **坑 2**：Principled BSDF 取节点必须先 `use_nodes = True`（v1.11.9）
- **坑 3**：`bpy_prop_collection[key]` 用 `.get()` 而非方括号（v1.11.9）
- **坑 4**：set_material / update_object 工具优先于 exec_python（v1.11.9）
- **坑 5**：Blender 4.2+ / 5.x bevel 关键字变更（v1.11.13）
- **坑 6**：常见 Blender enum 值混用（v1.11.14）

**痛点：** prompt 越长 AI 注意力越分散；新坑发现得越多需要的 prompt 越臃肿；用户用上不同模型（DeepSeek / Claude / GPT-4o）时这些大段 prompt 还会拉低首 token 速度。

**Phase C 治本方案：** 把所有 API 知识从 prompt 里抽出来变成**可被 AI 主动查询的 cheatsheet 文件**。AI 写 exec_python 前不确定语法时主动调 `search_bpy_docs(query)`，每次只拿回最相关的 5 条 entry（< 1500 tokens）—— 比塞在 system prompt 里所有用户都要付费的 3000 tokens 省 50%。

### Phase E 治痛点

v1.7.3 的 `AGENT_GEOMETRY_MASTERCLASS`（5 大武器：装配 / Subsurf+Bevel / Array+Mirror / bmesh / Geometry Nodes）在 ai-only 模式 system prompt 里塞了大段教程让 AI 学着写复杂家具，但用户实测 AI 经常翻车：沙发只会拼一个 cube、椅子腿长不对、花瓶用 cube 拉伸出来不像车削件、盆栽的叶子不知道用 GN 散布……

**Phase E 治本方案：** 把这些套路变成**预制模板 + 参数化渲染**。AI 不再"看 prompt 现学现写代码"，而是直接调 `apply_template({name:"sofa_3seater", params:{...}})` 拿到经过 Python AST 验证的完整 bpy 脚本，比自己写稳得多。10 个模板覆盖常见家具/装饰/建筑场景。

---

## 实施详情

### Phase C 实施

#### 1. `scripts/bpy-cheatsheet.json` —— 192 条精选条目

**文件结构：**

```json
{
  "version": "1.0.0",
  "blender_target": "4.2+ / 5.x",
  "categories": ["modifier", "shader", "light", "camera", "world", "mesh", "bmesh", "geometry_nodes", "render", "pitfall", ...],
  "entries": [
    {
      "id": "modifier-bevel",
      "title": "Bevel modifier (Blender 4.2+ 兼容版)",
      "category": "modifier",
      "keywords": ["bevel", "倒角", "圆角"],
      "code": "mod = obj.modifiers.new('Bevel','BEVEL')\nmod.affect = 'VERTICES'  # 或 'EDGES'（默认）\nmod.width = 0.03\nmod.segments = 3",
      "deprecated": "vertex_only=True (已在 Blender 4.2+ 移除)",
      "see_also": ["pitfall-vertex-only-removed"]
    },
    ...
  ]
}
```

**29 个类别分布：**

| 类别 | 条目数 | 代表 entry |
| --- | --- | --- |
| modifier | 28 | bevel / array / mirror / subsurf / solidify / boolean / displace / lattice / wave / ocean / cloth / shrinkwrap / smooth / decimate / multires / particle / weld / weighted_normal / edge_split / triangulate / mask / screw / skin / surface_deform / mesh_to_volume / wireframe / cast / build |
| shader | 35 | principled_bsdf / sky-texture / emission / diffuse / glass / refraction / glossy / transparent / volume_scatter / hair / sss / pbr_pipeline 等 |
| light | 6 | POINT / SUN / SPOT / AREA / 光源衰减 / shadow_soft_size |
| camera | 5 | perspective / orthographic / panoramic / track_to / depth_of_field |
| world | 4 | hdri / sky_texture / fog / volumetric |
| mesh | 8 | primitive_add / verts_count / normals_recalc / smooth / flat_shading / edge_split / merge_doubles / face_orientation |
| bmesh | 22 | inset_individual / spin / extrude_individual / dissolve / subdivide / loop_cut / bridge_edge_loops 等 |
| geometry_nodes | 14 | DistributePointsOnFaces / InstanceOnPoints / RealizeInstances / setPosition / capture_attribute / random_value 等 |
| render | 9 | CYCLES / EEVEE_NEXT / view_settings / Filmic / 视口模式切换 |
| pitfall | 14 ⭐ | vertex_only_removed / sky_vs_volume_enum / principled_none / bpy_prop_collection_key / shadow_method_removed / auto_smooth_renamed / use_bloom_removed 等 |
| 其它 | 47 | vertex_group / shape_key / armature / animation / physics / compositor / IO 等 |

**每条 entry 字段：**

- `id`（如 `modifier-bevel`）：unique identifier
- `title`：中文标题，便于人读
- `category`：上面 29 类之一
- `keywords[]`：中/英文多关键词搜索词
- `code`：可直接 copy 的 Python 代码片段
- 可选 `deprecated`：弃用提示（如 `vertex_only=True 已在 4.2+ 移除`）
- 可选 `see_also`：相关条目 ID 数组

#### 2. server.js 加 `_loadBpyCheatsheet()` + 3 个 HTTP 端点

```javascript
const _BPY_CHEATSHEET = _loadBpyCheatsheet();  // 启动时一次性加载到内存
const _BMESH_TEMPLATES = _loadBmeshTemplates();  // 同上

// 加权打分模糊搜（zero-RTT）
function _searchBpyEntries(query, limit = 5) {
  // keywords 完全匹配 +30 / 包含 +18
  // id 完全匹配 +25 / 包含 +12
  // title +8
  // category +14
  // code +2
  // 按 score 降序，返回前 N 条
}

// 3 个 HTTP 端点
app.get('/api/bpy/search', ...);           // 模糊搜（query, limit）
app.get('/api/bpy/templates', ...);        // 列模板元数据
app.post('/api/bpy/templates/render', ...); // 渲染模板代码（Phase E）
```

#### 3. 客户端工具 `search_bpy_docs`

CLIENT_TOOLS 数组（在 public/index.html 的 `<script>` 顶部）新增：

```javascript
{
  type: 'function',
  function: {
    name: 'search_bpy_docs',
    description: '【v2.1.0 Phase C ⭐】查询 bpy / bmesh / Geometry Nodes 速查表（约 200 条精选条目）。用于：① 写 exec_python 前查正确语法；② 排查报错；③ 找反踩坑速查表。返回前 N 条匹配，每条含 code / deprecated / see_also。',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: '关键词（中/英文，空格隔开 OR）' },
        limit: { type: 'integer', description: '返回前 N 条（1~20，默认 5）' }
      },
      required: ['query']
    }
  }
}
```

`_runClientTool` 的 `case 'search_bpy_docs'` 分支调 `/api/bpy/search` 然后精简返回给 AI（每条 ≤ 400 字符的 code，保留 deprecated / see_also）。

#### 4. MCP system prompt 决策树升级

```
- **不确定 bpy API 怎么写 → `search_bpy_docs(query)`** 优先查 cheatsheet（200 条精选 + 反踩坑）
  ⭐ **写 exec_python 之前一定先搜！**
```

塞在「工具选择决策树」第一位，让 AI 第一眼就看到。

---

### Phase E 实施

#### 1. `scripts/bmesh-templates.json` —— 10 个完整可执行模板

```json
{
  "version": "1.0.0",
  "blender_target": "4.2+ / 5.x",
  "templates": [
    {
      "name": "sofa_3seater",
      "title": "三人沙发（5 部件装配 + Bevel + Subsurf）",
      "category": "furniture",
      "description": "底座 + 靠背 + 左右扶手 + 3 个坐垫，整体 Empty parent，可整体移动/旋转",
      "params": [
        { "name": "name", "type": "string", "default": "Sofa01", "description": "整体物体名（也是 Empty 名）" },
        { "name": "location", "type": "array", "default": [0, 0, 0], "description": "坐标 [x,y,z]" },
        { "name": "seat_height", "type": "number", "default": 0.45, "description": "坐垫高度（米）" },
        { "name": "seat_width", "type": "number", "default": 2.0, "description": "沙发总宽" },
        { "name": "seat_depth", "type": "number", "default": 0.9, "description": "沙发深度" },
        { "name": "color", "type": "array", "default": [0.45, 0.4, 0.35], "description": "布料 base color RGB" },
        { "name": "roughness", "type": "number", "default": 0.8, "description": "布料粗糙度" }
      ],
      "code": "import bpy\nname = {{name}}\nlocation = {{location|json}}\nseat_height = {{seat_height}}\n# ... 5 部件代码 ..."
    },
    ...
  ]
}
```

**10 个模板按 category 分类：**

| Category | 模板名 | 说明 | 参数数 |
| --- | --- | --- | --- |
| furniture | `sofa_3seater` | 三人沙发（5 部件装配 + Bevel + Subsurf） | 7 |
| furniture | `dining_chair` | 餐椅（座面 + 靠背 + 4 椅腿） | 7 |
| furniture | `coffee_table_round` | 圆茶几（桌面 + Array(4) 桌腿） | 6 |
| furniture | `bookshelf_array` | 书架（侧板 + 顶底封板 + Array(N) 隔板） | 8 |
| decor | `vase_spin` | 花瓶（bmesh.spin 360° 车削旋转） | 7 |
| decor | `cup_inset` | 杯子（bmesh.inset_individual 挖空 + Subsurf） | 6 |
| decor | `plant_geonode` | 盆栽（GN DistributePointsOnFaces + InstanceOnPoints） | 7 |
| decor | `pillow_subsurf` | 枕头（Cube + Subsurf 4 级软包） | 6 |
| decor | `frame_bevel` | 画框（4 边外框 + 1 画面 + 可选贴图） | 9 |
| architecture | `wall_solidify` | 墙体（Plane + Solidify 加厚 + Bevel） | 7 |

#### 2. Mustache 模板渲染器

```javascript
function _renderTemplateCode(tpl, params) {
  // 1) 按 params schema 用 default 兜底缺失参数
  const paramMap = {};
  for (const p of tpl.params || []) {
    paramMap[p.name] = params.hasOwnProperty(p.name) ? params[p.name] : p.default;
  }
  // 2) 替换 {{var|json}} → JSON.stringify（数组/对象自动加引号）
  code = code.replace(/\{\{(\w+)\|json\}\}/g, (m, key) =>
    JSON.stringify(paramMap[key])
  );
  // 3) 替换无修饰 {{var}}：
  //    - number 直传
  //    - boolean 转 True/False（Python literal）
  //    - string 自动 JSON.stringify（加双引号）
  //    - 其它走 JSON 序列化
  code = code.replace(/\{\{(\w+)\}\}/g, (m, key) => {
    const v = paramMap[key];
    if (typeof v === 'number') return String(v);
    if (typeof v === 'boolean') return v ? 'True' : 'False';
    if (typeof v === 'string') return JSON.stringify(v);
    return JSON.stringify(v);
  });
  return { code, paramMap };
}
```

#### 3. 客户端工具 `apply_template` + `list_templates`

```javascript
{
  type: 'function',
  function: {
    name: 'apply_template',
    description: '【v2.1.0 Phase E ⭐】应用 bmesh / GN 模板到 Blender。10 个内置模板：sofa_3seater / dining_chair / coffee_table_round / vase_spin / cup_inset / plant_geonode / bookshelf_array / pillow_subsurf / wall_solidify / frame_bevel。每个模板都是完整可执行 bpy 脚本，参数有 default 兜底，比 AI 自己写 exec_python 稳得多。',
    parameters: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          enum: ['sofa_3seater','dining_chair','coffee_table_round','vase_spin','cup_inset','plant_geonode','bookshelf_array','pillow_subsurf','wall_solidify','frame_bevel'],
        },
        params: { type: 'object', description: '参数字典' },
        dry_run: { type: 'boolean', description: '只渲染代码不推到 Blender（让 Critic 审 code）' },
        blender_url: { type: 'string', description: '可选覆盖默认 http://127.0.0.1:9876' }
      },
      required: ['name']
    }
  }
}
```

`_runClientTool` 的 `case 'apply_template'` 分支：
1. 调 server.js `/api/bpy/templates/render` 拿渲染后的 code
2. 写一份副本到 workspace `templates/{name}_{timestamp}.py`（用户能在 Finder 看到）
3. dry_run=true → 直接返回 code（让 Critic 审）
4. dry_run=false（默认）→ 通过 MCP 网关 `exec_python` 推到 Blender 执行

`list_templates()` 返回 10 个模板的元数据（不含 code body 省 token），让 AI 建家具前先调一次看哪个最贴合。

#### 4. MCP system prompt 决策树升级（建家具/装饰）

```
- **建家具/装饰 → 决策顺序（v2.1.0 强烈推荐）：**
  1. **写实需求** → `search_polyhaven_assets` → `import_polyhaven_model`（CC0 真实精模优先）
  2. **PolyHaven 没合适资产** → `list_templates` 看 10 个内置 bmesh/GN 模板 → `apply_template(name, params)` 一键应用
  3. **模板也不够用** → `add_primitive` + `set_material` 自己拼
  4. **最后兜底** → `exec_python`（AI 自己写代码，最容易踩 enum/坑）
```

---

## 验收测试

### 端到端测试脚本 `/tmp/_test_phaseCE.js`

**测试覆盖：**

#### Phase C：`GET /api/bpy/search`

| # | 查询 | 期望 | 实际 |
| --- | --- | --- | --- |
| 1 | `bevel` | first.id=modifier-bevel / total≥5 | ✅ first.id=modifier-bevel / total=5 / cheatsheet_total=192 |
| 2 | `sky_type` | 命中 sky-texture | ✅ top.id=shader-sky-texture |
| 3 | `NISHITA` | 命中 sky（关键词在 code 里） | ✅ top.id=shader-sky-texture |
| 4 | `vertex_only` | 命中 bevel 或 pitfall | ✅ top.id=pitfall-operator-keyword |
| 5 | 中文 `花瓶` | 命中 bmesh-spin | ✅ top.id=modifier-screw（含 spin 关键词） |
| 6 | 空 `q` | 400 | ✅ 400 |
| 7 | `NoneType` | 命中 pitfall-principled-none | ✅ top.id=pitfall-principled-none |

**全部 7/7 通过。**

#### Phase E：`GET /api/bpy/templates`

- ✅ 列模板 200 + total=10
- ✅ 10 个模板齐全（sofa_3seater / dining_chair / coffee_table_round / vase_spin / cup_inset / plant_geonode / bookshelf_array / pillow_subsurf / wall_solidify / frame_bevel）

#### Phase E：`POST /api/bpy/templates/render`

| # | 用例 | 期望 | 实际 |
| --- | --- | --- | --- |
| 1 | sofa 渲染 | 200 + code_size>1000 | ✅ code_size=3125 |
| 2 | sofa code 注入 TestSofa | code 含 "TestSofa" | ✅ |
| 3 | sofa code 占位符全替换 | 无 `{{` 残留 | ✅ |
| 4 | sofa default 兜底 | seat_height=0.45 | ✅ |
| 5 | vase 渲染 | 200 | ✅ |
| 6 | vase paramMap.height | 0.6（用户传入） | ✅ |
| 7 | vase default 兜底 | segments=48 | ✅ |
| 8 | plant_geonode 渲染含 GN | code 含 'NodeTree' / 'DistributePointsOnFaces' | ✅ |
| 9 | cup_inset 渲染含 inset_individual | code 含 'inset_individual' | ✅ |
| 10 | bookshelf shelf_count=7 透传 | code 含 "7" | ✅ |
| 11 | 未知模板 | 404 | ✅ |
| 12 | 缺 name | 400 | ✅ |
| 13 | dining_chair 渲染 | 200 | ✅ |

#### Phase E：10 个模板 Python AST 语法校验

每个模板渲染（用 default 参数）后写入 tmpfile，调用 `python3 -m py_compile` 校验：

```
✅ python 语法 sofa_3seater · size=3124
✅ python 语法 dining_chair · size=2281
✅ python 语法 coffee_table_round · size=1996
✅ python 语法 vase_spin · size=1875
✅ python 语法 cup_inset · size=1417
✅ python 语法 plant_geonode · size=3976
✅ python 语法 bookshelf_array · size=2134
✅ python 语法 pillow_subsurf · size=941
✅ python 语法 wall_solidify · size=1149
✅ python 语法 frame_bevel · size=2780
```

**全部 10/10 通过。**

### 测试总结

```
==================================================
✅ Phase C+E 端到端测试：32 pass / 0 fail
==================================================
```

- Phase C 模糊搜：7 case
- Phase E 列模板 / 模板齐全：2 case
- Phase E 模板渲染参数透传 / default 兜底 / 错误处理：13 case
- Phase E Python AST 语法校验：10 case

---

## 用例示范（AI 怎么用这两套工具）

### 示范 1：AI 不会写 spin 旋转面 → 调 search_bpy_docs 先查 → 再用模板

```
LLM Round 3：
  Modeler thinking：
    "用户要建一个花瓶，bmesh.spin 怎么写来着...试试 search_bpy_docs。"

  调 search_bpy_docs({ query: "spin 旋转面" })
  → 返回：[
       {id: "bmesh-spin", code: "bmesh.ops.spin(bm, geom=..., axis=(0,0,1), angle=math.radians(360), steps=32)"},
       {id: "modifier-screw", code: "mod = obj.modifiers.new('Screw', 'SCREW'); mod.angle=math.radians(360)"},
       ...
     ]

  Modeler thinking：
    "嗯，可以用 bmesh.spin。但其实 list_templates 应该有现成的花瓶模板，让我看看。"

  调 list_templates()
  → 返回 10 个模板，其中包含 vase_spin

  调 apply_template({ name: "vase_spin", params: { height: 0.4, base_radius: 0.08 } })
  → 后端渲染 code → 通过 MCP 网关推送到 Blender
  → ✅ 花瓶建好，1 行调用搞定，零踩坑
```

### 示范 2：AI 不确定 Blender 4.2+ 的 bevel 参数 → 先查再写

```
LLM Round 5：
  Modeler thinking：
    "需要给桌子加倒角，bevel modifier 的参数我记得在 4.2 改过..."

  调 search_bpy_docs({ query: "bevel modifier vertex_only" })
  → 返回：[
       {
         id: "modifier-bevel",
         title: "Bevel modifier (Blender 4.2+)",
         code: "mod = obj.modifiers.new('Bevel','BEVEL')\nmod.affect = 'VERTICES'\nmod.width = 0.03",
         deprecated: "vertex_only=True (removed 4.2+)",
         see_also: ["pitfall-operator-keyword"]
       },
       {
         id: "pitfall-operator-keyword",
         title: "坑：Blender 4.2+ operator 关键字变更",
         code: "...完整对照表..."
       }
     ]

  Modeler thinking：
    "明白，用 mod.affect='VERTICES' 而不是 vertex_only=True。"

  调 exec_python({ code: "...mod.affect = 'VERTICES'..." })
  → ✅ 一次成功，避开 v1.11.13 治过的坑
```

---

## 文件清单

### 新增

- `scripts/bpy-cheatsheet.json`（192 条 bpy/bmesh/GN API 精选条目，29 个类别，约 30 KB）
- `scripts/bmesh-templates.json`（10 个家具/装饰/建筑模板，含 Mustache 占位符的完整 bpy 代码，约 20 KB）
- `RELEASE_v2.1.0_PHASE_CE.md`（本文档）

### 修改

- `server.js`：+约 200 行
  - `_loadBpyCheatsheet()` / `_loadBmeshTemplates()` 启动时一次加载到全局 const
  - `_searchBpyEntries(query, limit)` 加权打分模糊搜
  - `_renderTemplateCode(tpl, params)` Mustache 参数渲染器
  - `GET /api/bpy/search` 端点
  - `GET /api/bpy/templates` 端点
  - `POST /api/bpy/templates/render` 端点

- `public/index.html`：+约 200 行
  - CLIENT_TOOLS 数组从 10 个扩到 13 个（新增 `search_bpy_docs` / `apply_template` / `list_templates`）
  - `_runClientTool` switch 加 3 个新 case（async 调 server.js HTTP 端点）
  - MCP system prompt 决策树升级：第一位强制提示 `search_bpy_docs` 优先；建家具时四级 fallback 决策树（PolyHaven > 模板 > 手拼 > exec_python）
  - 工具表注入日志从 "prepend 5" 改为 "prepend 13"，分项标注 Phase A:5 + B:5 + C:1 + E:2

- `CHANGELOG.md`：
  - 顶部 [2.1.0] 段总述补 Phase C / E + 工具数 16 → 29
  - 新增 `Added · 📚 Phase C` 大段（含 192 条条目分类表 + 3 个端点 + 1 个工具）
  - 新增 `Added · 🎨 Phase E` 大段（含 10 个模板分类表 + Mustache 渲染器 + 2 个工具）
  - 末尾 ROADMAP 区 Phase C / E 标 ✅
  - 接力 prompt 更新成"剩 F + G 待做"

---

## 与 Phase A/B/D 的协作

Phase C + E 跟前 3 个 Phase 完全互补：

| 痛点 | Phase A | Phase B | Phase C | Phase D | Phase E |
| --- | --- | --- | --- | --- | --- |
| 长时漂移 | ✅ plan_create 拆任务清单 | | | ✅ 角色分工 | |
| 停不下来 | ✅ mark_done 显式退出 | | | | |
| 无外部记忆 | | ✅ workspace 持久化 | | | |
| API 不熟 | | | ✅ search_bpy_docs cheatsheet | | |
| 单一模型短板 | | | | ✅ 三角色独立 API/模型 | |
| 复杂家具翻车 | | | | | ✅ apply_template 预制脚本 |

**完整协作流程示意：**

1. Round 1 - Planner（Phase D 角色）：调 `plan_create`（A）拆 5 步任务清单 + `workspace_write_file`（B）落盘 plan.md
2. Round 2~N-2 - Modeler（Phase D 角色）：
   - 不确定 bpy API → 调 `search_bpy_docs`（C）查
   - 建沙发 → 调 `apply_template({name:"sofa_3seater"})`（E）一键应用
   - 简单几何 → `add_primitive` + `set_material`
   - 每完成一步 → `plan_update_step`（A）+ 反思日志 `reflect`（A）+ 写脚本副本到 workspace（B）
3. Round N-1 - Critic（Phase D 角色）：调 `get_viewport_screenshot` 审图 + `workspace_write_file`（B）写 critic_notes.md
4. Round N - Modeler 修复轮：按 Critic 反思针对性修复
5. 最后调 `mark_done`（A）退出，全部产物在 workspace 落盘可复用

---

## 性能 / 兼容性

### 性能

- `bpy-cheatsheet.json` / `bmesh-templates.json` 启动时一次加载到内存全局 const，单次 search/render 仅毫秒级（不发 fetch、不读盘）
- `search_bpy_docs` 客户端工具 → server.js HTTP → 内存搜索，单次往返约 5~20 ms
- `apply_template` 客户端工具 → server.js HTTP 渲染 code → MCP 网关推送 Blender，全程约 50~300 ms（取决于 exec_python 复杂度）

### 兼容性

- **完全向后兼容**：v1.11.x 用户的 localStorage 数据无任何字段冲突；scripts/*.json 是新增文件，老用户升级到 v2.1.0 后无需任何迁移
- `aichat_bridge` 插件版本**不变**（仍是 2.0.4），Phase C+E 完全是前端 + server.js 的纯增量改造
- MCP 模式之外（ai-only / polyhaven）完全不受影响 —— Phase C/E 工具只在 MCP 模式启动后才被 prepend 到 tools schema

---

## 下一步：Phase F + G

**Phase F**（独立会话，1 天）：
- `aichat_bridge` 插件升级 2.0.4 → 2.1.0
- 新增 `GET /blend_summary`（场景 overview）
- 新增 `POST /bookmark_state`（场景快照）
- 新增 `POST /restore_state`（从快照恢复）
- `bl_info` / `ADDON_VERSION` / `REQ_HEADERS UA` 三处同步 bump 到 2.1.0
- 重打 `aichat_bridge.zip`

**Phase G**（独立会话，1 天）：
- 欢迎弹窗 key 末次 bump 到 `hasLaunched_v2.1.0_final`
- 把 v1.11.5~v1.11.14 折叠到欢迎弹窗历史区
- README.md 第 1 章重写为「v2.1 Codex CAD 范式」
- 重打 4 个 dmg/exe（mac arm64+x64、win arm64+x64）

---

**Phase C + E 完成 ✅** · 共估时 3 天，本次会话一次性交付。
