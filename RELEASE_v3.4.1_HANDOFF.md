# 🎯 v3.4.1 → v3.4.2 接力简报

## ✅ 上一对话（v3.4.1）已完成

### 1. scene-prompts.json 大幅升级（v1.0.0 → v1.1.0，4605 → 8432 字符）
路径：`ai-chat/scripts/scene-prompts.json` 的 `shared_master_rules` 字段。

**修复 5 个 bpy 致命 bug**（之前用户反复踩坑）：
- `bpy.ops.object.delete(use_global=False, confirm=False)` → confirm 参数不存在 TypeError，已去掉
- 清场景 `(bpy.data.meshes, ..., bpy.data.cameras)` → 漏了 particles，已补
- `obj.particle_systems` 是集合不是对象 → 加 `ps_obj = obj.particle_systems[-1]; pset = ps_obj.settings` 速查
- Blender 4.2+ EEVEE_NEXT 已移除 `use_bloom/bloom_intensity/use_ssr/use_gtao` → 必须 try/except 包裹
- Solidify modifier 用方括号取会 KeyError → 必须 `mod = obj.modifiers.new(...)` 保留引用

**新增「具象化 9 维度铁律」**（治"脚本太程序员思维"的根本药）：
1. 物体清单实物级命名（`Izakaya_Roof_Tile_Front_01` 而不是 `# 建一些屋顶`）
2. 真实世界尺寸（居酒屋单层 2.8m / 鸟居净空 2.5m / 樱花树 6~8m）
3. 三层纵深构图（前景 Y<-2 / 中景 Y -2~5 / 远景 Y>8）
4. 故事感材质（每个材质 ≥2 个差异化属性，不允许单色 BSDF）
5. 三点光冷暖对立（Key 暖→Fill 冷蓝 / 必须 Rim 轮廓光）
6. 至少 2 套粒子系统（大粒子樱花/雪 + 小粒子萤火虫/灰尘）
7. 相机不是默认 (0,-10,1) + 必须开 DOF + to_track_quat 朝向
8. PALETTE 色板锚（脚本开头写字典，所有材质从中取色）
9. random.seed(42) + 重复物体 ±5~15% 微差异（避免机械感）

### 2. 删除「脚本大师→MCP 自动串联」死板逻辑
路径：`ai-chat/public/index.html` 函数 `agentRunScriptMasterMode` 末尾（搜 `🎉 脚本生成大师完成`，约 14823 行）。  
原来生成完会强制 followupText 转 MCP 精修，已改为：
```js
agentAppendReviewLog(`<div ...>🎉 脚本生成大师完成！...</div>`);
// v3.4.1：移除"自动接力 MCP"逻辑。脚本大师现在是 MCP 的工具（build_base_scene），
// 由 AI 在 MCP 循环里按需召唤；直接选 "脚本生成大师" 模式只跑一次脚本不再串接。
}
```

---

## ⏸ 下一步未完成（核心诉求 ⭐ 30~45 分钟）

**把脚本大师变成 MCP 的 3 个新工具**，让 AI 在 MCP 循环里按需自主召唤（不是被动跑完串接）。

### 设计

在 MCP 工具表前加 3 个客户端工具（前端 JS 处理，复用现有 `/api/scene-prompts/*` 端点）：

#### 工具 1：`list_scene_templates()`
```js
{
  type: 'function',
  function: {
    name: 'list_scene_templates',
    description: '【脚本大师工具库 📝】列出全部 8 个场景模板的元数据（id/name/keywords）。AI 接到「画一个赛博朋克霓虹巷子」/「日式神社」等场景需求时，先调这个看哪个模板最贴合，再调 build_from_scene_template 一次性建好基础场景（800~1500 行 bpy）。',
    parameters: { type: 'object', properties: {} }
  }
}
```
实现：fetch `/api/scene-prompts/list` 返回 `{ok, templates:[{id,name,keywords}]}`。

#### 工具 2：`match_scene_template({description})`
```js
{
  type: 'function',
  function: {
    name: 'match_scene_template',
    description: '【脚本大师工具库 📝】按自然语言场景描述模糊匹配最贴合的模板（top-3）。返回 [{id,name,score,keywords}]。AI 用这个比死规则关键词命中更智能。',
    parameters: {
      type: 'object',
      properties: { description: { type: 'string', description: '场景需求自然语言' } },
      required: ['description']
    }
  }
}
```
实现：POST `/api/scene-prompts/match`，body `{description, limit:3}`。

#### 工具 3：`build_from_scene_template({template_id, description})`
```js
{
  type: 'function',
  function: {
    name: 'build_from_scene_template',
    description: '【脚本大师工具库 ⭐】一次性调用脚本大师建造基础场景：① 加载 template_id 的完整 system prompt（含 9 维度铁律 + 防踩坑速查）② 调主 Agent 选的模型生成 800~1500 行 bpy 脚本（含 _CHARACTER_PLACEHOLDER 中央人像位）③ 包安全壳推到 Blender 一次性执行 ④ 自动拉日志检测错误，如有就调 LLM 输出修复 patch。返回成功/失败 + 物体数 + 错误清单。AI 建议在 plan 早期阶段（清空场景之后、精细化调整之前）调这个工具一键打底。',
    parameters: {
      type: 'object',
      properties: {
        template_id: { type: 'string', description: '模板 id（先调 list_scene_templates 或 match_scene_template 拿到）' },
        description: { type: 'string', description: '场景具体描述（喂给脚本大师作为 user message）' }
      },
      required: ['template_id', 'description']
    }
  }
}
```
实现：基本复用 `agentRunScriptMasterMode` 函数的内部逻辑（拉 prompt → 调 m3dCallLLM → 提取 code → agentPushCode → 检日志 → 可选 patch），但要：
- 跳过 1/4「智能匹配」步骤（AI 已用工具 2 选好 id）
- 不要 set `agentSetStage` / `agentSetStatus`（那是给单独跑模式用的，MCP 模式不需要）
- 直接 fetch `/api/scene-prompts/${template_id}` 拿 fullPrompt
- 把生成的 code 写到 workspace（`workspace_write_file` 路径 `script_master/${template_id}.py`）方便用户审
- 返回 `{ok:true, template_id, template_name, code_len, line_count, builtObjects, errors:[]}`

### 关键插入点（按行号速查）

1. **`CLIENT_TOOLS` 数组定义**：约 `public/index.html:13260`。在数组末尾的 `]` 之前插 3 个工具 schema。
2. **`_runClientTool` switch**：约 `public/index.html:13658` 起。在 `case 'mark_done':` 之后、`case 'workspace_write_file':` 之前加 3 个 case。
3. **MCP system prompt 加一段「📝 脚本大师工具库决策树」**：约 `public/index.html:15247` 的 `## 💡 工具选择决策树` 块加一条规则：「**复杂特定主题场景（赛博朋克/日式神社/中世纪城堡等）→ 先 `match_scene_template` 再 `build_from_scene_template` 一键建好基础场景**，比让 AI 自己拼 cube 强 100 倍」。

### 注意点（避免踩坑）

- ⚠️ **不要在工具 3 里调 `agentRunScriptMasterMode` 整个函数**（会改 agentState.status / 触发 UI 状态机），只复用它的内部步骤
- ⚠️ build_from_scene_template 应该是 async，里面 fetch + m3dCallLLM 都要 await
- ⚠️ LLM 生成代码可能很长（800~1500 行），m3dCallLLM 调用记得传 maxTokens 24000
- ⚠️ 返回 result 时 code 太长不要塞到 result 字段里（>8000 字符会被 MCP 历史截断），存到 workspace 就够了，result 只返回 code_len / line_count
- ⚠️ 推 Blender 时 await `agentPushCode(code, 'ScriptMaster_' + template_id)`，timeout 用 300s（脚本大场景 mesh 多）
- ⚠️ 检日志的步骤可选，简化版可以省略 patch 自动修复，让 AI 在 MCP 循环里看 get_scene_info 自己判断要不要补

### 测试用例

启动 MCP Agent，在场景需求里写：
> 画一个赛博朋克的霓虹巷子，雨夜，中央有个穿黑大衣的角色

AI 应该：
1. `plan_create` 拆 4~6 步
2. 第 1 步 `clear_scene`
3. 第 2 步 `match_scene_template({description:"赛博朋克霓虹巷子"})` → 命中 cyberpunk_neon_alley
4. 第 3 步 `build_from_scene_template({template_id:"cyberpunk_neon_alley", description:"霓虹巷子+雨夜+黑大衣角色中央"})` → 一次性建 800+行场景
5. 第 4 步 `get_scene_info` 看场景
6. 第 5 步 `get_viewport_screenshot` 视觉确认
7. 第 6 步 `mark_done`

预期：原来「让 MCP 自己一步步搭建赛博朋克」要 25 轮 + 物体 30~50 个，现在直接 5~6 轮 + 物体 80~150 个 + 包含粒子/光/相机/PALETTE 全套。

### 接力清单 todo

- [ ] 在 `CLIENT_TOOLS` 末尾加 3 个工具 schema（约 80 行）
- [ ] 在 `_runClientTool` switch 加 3 个 case（约 130 行）
- [ ] 在 MCP system prompt 决策树加一条「场景模板工具优先」（约 5 行）
- [ ] node 语法校验通过（`node /tmp/_check_js.js`）
- [ ] 测试：MCP 模式输入「赛博朋克霓虹巷子」看 AI 是否主动用 match → build
- [ ] 更新 CHANGELOG 和欢迎弹窗 key（hasLaunched_v3.4.2）

---

## 关键文件行号速查

| 文件 | 位置 | 用途 |
|------|------|------|
| `public/index.html` | 13260 | `CLIENT_TOOLS = [`（注册新工具） |
| `public/index.html` | 13658 | `_runClientTool` switch（实现新工具） |
| `public/index.html` | 14684 | `agentRunScriptMasterMode` 函数（复用其内部逻辑） |
| `public/index.html` | 15247 | MCP system prompt 决策树（加优先级提示） |
| `public/index.html` | 14823 | v3.4.1 已删的「自动接力」标记位置 |
| `scripts/scene-prompts.json` | 整个文件 | v1.1.0 已升级 |
| `server.js` | 1841 | `/api/scene-prompts/list` 端点 |
| `server.js` | 1856 | `/api/scene-prompts/match` 端点 |
| `server.js` | 1891 | `/api/scene-prompts/:id` 端点 |

---

## 验收标准

完成后 MCP 模式下 AI 应能：
1. 看到 `list_scene_templates` / `match_scene_template` / `build_from_scene_template` 3 个新工具
2. 拿到复杂主题场景需求时**主动**调 `match_scene_template`
3. `build_from_scene_template` 一次调用产出 800~1500 行 bpy + 80~150 个物体
4. 跟后续 `get_scene_info` / `apply_polyhaven_texture` / `update_object` 等精修工具无缝衔接
5. 整体场景效果比纯 MCP 拼 cube 提升一个数量级
