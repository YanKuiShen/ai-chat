# 🎯 v3.4.2 → v3.4.3+ 接力简报

## ✅ 上一对话（v3.4.2）已完成

**主线**：完成 v3.4.1 接力简报里规划的「把脚本生成大师变成 MCP 模块的 3 个工具」改造，让 MCP Agent 在循环里按需自主召唤脚本大师一次性建好基础场景，之后再用其它原子工具精修。**主体仍是 MCP，脚本大师降级为工具库**。

### 1. 注册 3 个新 MCP 客户端工具（`public/index.html` 约 13628 行起）

`CLIENT_TOOLS` 数组末尾新增 3 个工具 schema：

#### 工具 1：`list_scene_templates()`
- 列出全部内置场景模板（id / name / keywords）
- AI 接到「赛博朋克霓虹巷子」/「日式神社」/「中世纪城堡」等具体主题需求时，先调这个看哪些模板可选
- 调用：`fetch('/api/scene-prompts/list')`

#### 工具 2：`match_scene_template({description})`
- 按自然语言场景描述模糊匹配最贴合的模板（top-3，含命中分数与关键词）
- 比 AI 看 list_scene_templates 凭直觉选更智能
- 双重兜底：空命中时拉 list 顶 3 个模板，避免死循环
- 调用：`POST /api/scene-prompts/match` body `{description, limit:3}`
- 返回 `{ ok, matches, top_score, fallback, message }`，提示首选 score≥2 时大胆调 build；分数 ≤1 时建议回落普通 MCP 原子工具

#### 工具 3：`build_from_scene_template({template_id, description})` ⭐⭐⭐
- 一次性建造 800~1500 行 bpy + 80~150 个物体 + 完整粒子/三点光/相机 DOF/PALETTE 色板锚的基础场景
- **6 步流程（在 `_runClientTool` switch 约 14500 行实现）**：
  1. fetch `/api/scene-prompts/${tplId}` 拿 fullPrompt
  2. `m3dCallLLM` 用主 Agent 选的模型 + maxTokens 24000 生成
  3. 提取 `<script_master_code>` / `<blender_script>` / `<blender_code>` 标签代码（兼容 3 种）
  4. 写脚本副本到 workspace（`script_master/${tplId}_${ts}.py`）方便用户审
  5. `agentPushCode` 推 Blender（自动包安全壳 + 防御 header）
  6. 拉 Blender 日志检测 ERROR 关键字并汇报
- **跳过模板匹配步骤**（AI 已通过工具 2 选好）
- **不触发 UI 状态机**（不调 `agentSetStage` / `agentSetStatus`，因为 MCP 模式有自己的 UI 栈）
- 返回 `{ ok, template_id, template_name, code_len, line_count, workspace_path, blender_errors, message }`
- code 太大不塞 result 字段（已写到 workspace），AI 后续要看代码请用 `workspace_read_file` 读

### 2. MCP system prompt 决策树升级（约 15217 行）

新增「🌟 v3.4.2 NEW · 复杂特定主题场景的【最强武器】」段落：
- **场景主题明确（"赛博朋克霓虹巷子" / "日式神社" / "中世纪城堡" 等）→ 先 `match_scene_template` 再 `build_from_scene_template`**（plan 第 2~3 步，clear_scene 之后、精细化调整之前）
- **场景是简单单物体（"建一把椅子" / "做一个杯子"）→ 跳过场景模板**，直接 search_polyhaven / apply_template / add_primitive

### 3. 元数据更新

- `package.json` version `3.4.0` → `3.4.2`，description 重写为新工具说明
- 欢迎弹窗 key bump `hasLaunched_v3.4.0` → `hasLaunched_v3.4.2`，老用户重启会再弹一次
- `CHANGELOG.md` 顶部新增 `[3.4.2]` 段（v3.4.1 一起补归档）

### 4. 验证

- node 语法验证通过：`node /tmp/_check_v342.js` → `JS length: 663034 / JS lines: 15697 / OK - syntax valid`
- ✅ 完全向后兼容：v3.4.0/3.4.1 的所有 MCP / PolyHaven / 一键 3D 流程不动；CLIENT_TOOLS 数组从 16 → 19，新工具是纯增量

---

## ⏸ 下一步可选优化方向（30 分钟 ~ 数天）

### A. 验收测试（必做 · 30 分钟）

按 v3.4.1 接力简报的测试用例：启动 MCP Agent，场景需求里写「画一个赛博朋克的霓虹巷子，雨夜，中央有个穿黑大衣的角色」。AI 应该：
1. `plan_create` 拆 4~6 步
2. 第 1 步 `clear_scene`
3. 第 2 步 `match_scene_template({description:"赛博朋克霓虹巷子"})` → 命中 cyberpunk_neon_alley
4. 第 3 步 `build_from_scene_template({template_id:"cyberpunk_neon_alley", description:"霓虹巷子+雨夜+黑大衣角色中央"})` → 一次性建 800+ 行场景
5. 第 4 步 `get_scene_info` 看场景
6. 第 5 步 `get_viewport_screenshot` 视觉确认
7. 第 6 步 `mark_done`

预期：原来要 25 轮 + 物体 30~50 个，现在 5~6 轮 + 物体 80~150 个 + 完整粒子/光/相机/PALETTE 全套。

### B. 把已删的「自动接力」选项做成可选开关（低优先级 · 1~2 小时）

v3.4.1 删了死板串联代码（脚本大师跑完自动转 MCP），但部分用户还是想要这个流程（不用配置 MCP 直接一键到底）。可以加个 checkbox「📝 脚本大师跑完后自动转 MCP 精修」，默认关闭：
- 关闭：脚本大师只跑一次（v3.4.1+ 行为）
- 开启：恢复 v3.4.0 的死板串联

### C. scene-prompts.json 模板扩展（持续优化 · 数小时）

当前 8 个模板（jp_torii / urban_decay_jp / industrial_grain / medieval_castle / cyberpunk_alley / floating_fantasy / ancient_tea_study / underwater_ruins）覆盖范围有限。可以扩展：
- 现代办公室 / 客厅 / 卧室
- 太空舱内饰 / 火星基地
- 童话城堡内厅 / 巫师塔
- 海底珊瑚礁 / 雪山木屋
- 摄影棚 / 直播间

每个模板需要一段 1.5~2KB 的 system_prompt（含 9 维度铁律 + 防踩坑速查 + 风格关键词）+ 8~15 个 keywords 用于 match。

### D. 改进 build_from_scene_template 的错误反馈链（中优先级 · 2~3 小时）

当前 step 6 拉 Blender 日志只是 print 给用户看，没有反馈给 AI。可以让 AI 拿到错误后**自动调用一次 patch**：
1. 检测到 ERROR 时，再调一次 LLM 让它输出 80 行修复 patch
2. patch 推 Blender 后再拉日志确认
3. 最多 2 轮 patch

这相当于把 v3.4.1 之前 `agentRunScriptMasterMode` 的 patch 修复机制搬过来。但要注意不要把整段脚本重写，只输出修复片段。

### E. workspace 工具改进（低优先级 · 1 小时）

当前 build_from_scene_template 把脚本写到 `script_master/${tplId}_${timestamp}.py`，时间戳化文件名很长。可以：
- 同名覆盖（`script_master/${tplId}_latest.py`）+ 同时保留时间戳归档（`script_master/${tplId}_${timestamp}.py`）
- 同步写一个 `script_master/${tplId}.md` 索引（含描述、生成时间、行数）

---

## 关键文件行号速查（v3.4.2 状态）

| 文件 | 位置 | 用途 |
|------|------|------|
| `public/index.html` | 13628 | `CLIENT_TOOLS` 数组：3 个新工具 schema 注释起点 |
| `public/index.html` | 13637 | `list_scene_templates` schema |
| `public/index.html` | 13645 | `match_scene_template` schema |
| `public/index.html` | 13659 | `build_from_scene_template` schema |
| `public/index.html` | 14441 | `_runClientTool` switch：list_scene_templates case |
| `public/index.html` | 14460 | match_scene_template case |
| `public/index.html` | 14500 | build_from_scene_template case（核心 6 步） |
| `public/index.html` | 14684 | `agentRunScriptMasterMode` 函数（v3.4.1 已删自动接力） |
| `public/index.html` | 15217 | MCP system prompt 决策树（v3.4.2 已加场景模板优先级） |
| `public/index.html` | 2886 | `checkFirstLaunch` 欢迎弹窗 key（v3.4.2） |
| `scripts/scene-prompts.json` | 整个文件 | v1.1.0 已升级（含 9 维度铁律 + 5 个 bpy bug 修复） |
| `server.js` | 1841 | `/api/scene-prompts/list` 端点 |
| `server.js` | 1856 | `/api/scene-prompts/match` 端点 |
| `server.js` | 1891 | `/api/scene-prompts/:id` 端点 |

---

## 验收标准（v3.4.2 完成度）

完成 v3.4.2 后 MCP 模式下 AI 应能：
1. ✅ 看到 `list_scene_templates` / `match_scene_template` / `build_from_scene_template` 3 个新工具
2. ⏳ 拿到复杂主题场景需求时**主动**调 `match_scene_template`（依赖 LLM 理解 system prompt 决策树，需用户实测）
3. ⏳ `build_from_scene_template` 一次调用产出 800~1500 行 bpy + 80~150 个物体（依赖 scene-prompts.json v1.1.0 + 模型质量）
4. ⏳ 跟后续 `get_scene_info` / `apply_polyhaven_texture` / `update_object` 等精修工具无缝衔接
5. ⏳ 整体场景效果比纯 MCP 拼 cube 提升一个数量级

`✅` = 代码已完成 · `⏳` = 待用户实测验证

---

## 给下一个 AI 的话（直接复制粘贴）

> v3.4.2 已完成核心改造（脚本大师 → MCP 工具库 3 件套），node 语法验证通过。
>
> 接下来需要**用户实测验证**（启动 MCP Agent，输入「赛博朋克霓虹巷子」看 AI 是否主动 match → build），如果验收通过就可以打 dmg 发版了。
>
> 如果实测发现：
> - **AI 不主动调新工具** → 检查 system prompt 决策树位置（约 15217 行），可能需要把场景模板段落移到决策树最顶部，或加红色高亮强调
> - **build_from_scene_template 生成的脚本质量不好** → 检查 scene-prompts.json 的 9 维度铁律落实情况，可能需要再加更具体的 bpy API 范例
> - **Blender 报错** → 检查 `agentPushCode` 的安全壳（v1.6.5 安全壳）是否覆盖了 scene-prompts.json 输出代码可能踩的新坑，或者把错误反馈给 AI 让它自动 patch（参见上方 D 优化）
>
> 详细 todo 见上方 A~E 段落。
