# Changelog


本文档记录「白歌的AI讨论组」(`ai-multi-chat`) 的所有实质性变更。

- 格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)
- 版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)：
  - **MAJOR (`X.0.0`)** — 不兼容的重大变更
  - **MINOR (`1.X.0`)** — 新增向后兼容的功能
  - **PATCH (`1.0.X`)** — 向后兼容的 bug 修复 / 小优化

> **铁律**：每次推送实质性改动前，必先迭代版本号（详见 [VERSIONING.md](./VERSIONING.md)）。

---

## [3.4.3] - 2026-05-23 · 📷 摄影项目「照片墙」显示原始文件名

### 用户反馈
> 在照片墙里面应该可以显示出照片的名字（在我使用新版本之后自动显示出来，不需要再次上传）

### Added · 摄影项目照片墙照片底部 chip 显示原始文件名（`public/index.html` 5 处改动）
- **`handlePhotoWallUpload(event)`**（约 7800 行）：上传/拖拽图片时同步捕获 `file.name`，去掉扩展名（`.jpg/.png/.heic` 等）+ 截断到 60 字符防止超长破坏布局，作为新参数 `rawName` 传给 `addPhotoCard`
- **`addPhotoCard(id, base64, note, x, y, filename = '')`**：新增第 6 个参数 `filename`（默认空字符串向后兼容老调用），把名字塞到 `card.dataset.filename` 上，方便 savePhotoSession 读取
- **照片卡片底部新增 `.photo-filename` div**：黑色渐变背景（`linear-gradient(0deg, rgba(0,0,0,0.85) 0%, ... transparent 100%)`），白色文字 + 📷 emoji 前缀，单行 ellipsis 不换行，hover 显示完整 title。filename 为空时整个 div 完全不渲染
- **`savePhotoSession()`**（约 8030 行）：保存 photos 数组时新增 `filename: card.dataset.filename` 字段持久化到 localStorage
- **`selectPhotoSession()`**（约 7251 行）：恢复照片墙时把保存的 `p.filename` 传给 `addPhotoCard`，让旧上传的照片下次打开继续显示文件名

### 兼容性
- ✅ 完全向后兼容：老 photos 数据没 filename 字段会回退到空字符串，照片卡片只是不显示文件名 chip，其它功能不变
- ✅ 用户已上传的旧图不会自动显示文件名（因为当时没存 filename），但**重新上传一次后即显示**（建议项目里 + 一张新图就能验证）

### Other
- `package.json` version `3.4.2` → `3.4.3`
- node 语法验证通过：`JS length: 663886 / JS lines: 15709 / OK - syntax valid`

---

## [3.4.2] - 2026-05-21 · ⭐ 脚本生成大师 → MCP 工具库 3 件套（AI 按需自主召唤）


### 主体调整 · 范式重构 ⭐
**v3.4.0 把脚本大师"跑完→自动转 MCP 精修"做成死板串联，v3.4.1 已删除该串联代码。v3.4.2 完成最后一公里：把脚本大师彻底变成 MCP 模块里的 3 个工具，主体是 MCP，脚本大师降级为工具库，让 AI 在循环里按需自主召唤、按需调用、按需组合。**

### Added · 3 个新 MCP 工具（`public/index.html`）

- **`CLIENT_TOOLS` 数组（约 13628 行）注册 3 个新工具 schema**：
  - **`list_scene_templates()`** —— 列出全部 8 个内置场景模板（id / name / keywords）。复杂主题场景需求来时 AI 调一次看候选清单。
  - **`match_scene_template({description})`** —— 按自然语言模糊匹配最贴合的模板（top-3 + 分数 + keywords 命中），比让 AI 凭直觉选更智能。空命中时双重兜底（前端拉 list 顶 3 个模板，避免死循环）。
  - **`build_from_scene_template({template_id, description})`** ⭐⭐⭐ —— 一次性建造 800~1500 行 bpy 脚本 + 80~150 个物体 + 完整粒子/三点光/相机 DOF/PALETTE 色板锚的基础场景。比让 AI 自己拼 cube 强 100 倍。

- **`_runClientTool` switch（约 14436 行）实现 3 个 case**：
  - `list_scene_templates`：fetch `/api/scene-prompts/list` 返回 templates 数组。
  - `match_scene_template`：POST `/api/scene-prompts/match` 拿 top-3，提示首选分数 ≥2 大胆调 build，分数 ≤1 建议回落普通 MCP 原子工具。
  - `build_from_scene_template`：① fetch `/api/scene-prompts/:id` 拿 fullPrompt → ② `m3dCallLLM` 用主 Agent 选的模型 + maxTokens 24000 生成 → ③ 提取 `<script_master_code>` / `<blender_script>` / `<blender_code>` 标签代码 → ④ 写脚本副本到 workspace（`script_master/${tplId}_${ts}.py`）→ ⑤ `agentPushCode` 推 Blender（自动包安全壳 + 防御 header）→ ⑥ 拉日志检测 ERROR 并汇报。返回 `{ ok, template_id, template_name, code_len, line_count, message }`，code 太大不塞 result（已写 workspace）。

### Changed · MCP system prompt 决策树升级（约 15217 行）
新增「🌟 v3.4.2 NEW · 复杂特定主题场景的【最强武器】」段落：
- **场景主题明确（"赛博朋克霓虹巷子" / "日式神社" / "中世纪城堡" / "漂浮幻境" / "水下遗迹" 等）→ 先 `match_scene_template` 再 `build_from_scene_template`**（plan 第 2~3 步，clear_scene 之后、精细化调整之前）
- **场景是简单单物体（"建一把椅子" / "做一个杯子"）→ 跳过场景模板**，直接 search_polyhaven / apply_template / add_primitive

### Other
- 欢迎弹窗 key bump `v3.4.0` → `v3.4.2`，老用户会重弹一次看到新工具说明。
- `package.json` version `3.4.0` → `3.4.2`。

### 验收标准（按 RELEASE_v3.4.1_HANDOFF.md 测试用例）
启动 MCP Agent，场景需求里写："画一个赛博朋克的霓虹巷子，雨夜，中央有个穿黑大衣的角色"。AI 应该：
1. `plan_create` 拆 4~6 步
2. 第 1 步 `clear_scene`
3. 第 2 步 `match_scene_template({description:"赛博朋克霓虹巷子"})` → 命中 cyberpunk_neon_alley
4. 第 3 步 `build_from_scene_template({template_id:"cyberpunk_neon_alley", description:"霓虹巷子+雨夜+黑大衣角色中央"})` → 一次性建 800+ 行场景
5. 第 4 步 `get_scene_info` 看场景
6. 第 5 步 `get_viewport_screenshot` 视觉确认
7. 第 6 步 `mark_done`

预期：原来 MCP 自己一步步搭建赛博朋克要 25 轮 + 物体 30~50 个，现在 5~6 轮 + 物体 80~150 个 + 完整粒子/光/相机/PALETTE 全套。

---

## [3.4.1] - 2026-05-20 · 🎨 9 维度铁律 + bpy 5 个致命 bug 修复（治"脚本太抽象"根本药）

### Fixed · scene-prompts.json 中 5 个 bpy 致命 bug（v1.0.0 → v1.1.0，4605 → 8432 字符）
- `bpy.ops.object.delete(use_global=False, confirm=False)` → confirm 参数不存在 TypeError，已去掉
- 清场景 `(bpy.data.meshes, ..., bpy.data.cameras)` → 漏了 particles，已补
- `obj.particle_systems` 是集合不是对象 → 加 `ps_obj = obj.particle_systems[-1]; pset = ps_obj.settings` 速查
- Blender 4.2+ EEVEE_NEXT 已移除 `use_bloom/bloom_intensity/use_ssr/use_gtao` → 必须 try/except 包裹
- Solidify modifier 用方括号取会 KeyError → 必须 `mod = obj.modifiers.new(...)` 保留引用

### Added · 「具象化 9 维度铁律」注入 shared_master_rules（治"脚本太程序员思维"根本药）
1. 物体清单实物级命名（`Izakaya_Roof_Tile_Front_01` 而不是 `# 建一些屋顶`）
2. 真实世界尺寸（居酒屋单层 2.8m / 鸟居净空 2.5m / 樱花树 6~8m）
3. 三层纵深构图（前景 Y<-2 / 中景 Y -2~5 / 远景 Y>8）
4. 故事感材质（每个材质 ≥2 个差异化属性，不允许单色 BSDF）
5. 三点光冷暖对立（Key 暖→Fill 冷蓝 / 必须 Rim 轮廓光）
6. 至少 2 套粒子系统（大粒子樱花/雪 + 小粒子萤火虫/灰尘）
7. 相机不是默认 (0,-10,1) + 必须开 DOF + to_track_quat 朝向
8. PALETTE 色板锚（脚本开头写字典，所有材质从中取色）
9. random.seed(42) + 重复物体 ±5~15% 微差异（避免机械感）

### Removed
- 删除「脚本大师跑完自动转 MCP」死板串联代码（`public/index.html` 约 14823 行）。后续 v3.4.2 重构成"MCP 模块按需调用脚本大师"工具库范式。

---

## [3.4.0] - 2026-05-20 · 🔗 脚本生成大师 → MCP Agent 自动接力（粗→精 一气呵成）


### Added · 自动接力管线 ⭐
- **`agentRunScriptMasterMode` 末尾追加约 50 行接力代码**（`public/index.html`）：基础脚本推完 + patch 修完后，自动调 `agentRunMCPMode({ followupUserText })` 进入 MCP 精修阶段，无需用户切模式手动按第二次开始。
- **`followupText` 完整 prompt**（约 30 行）：
  - 锁定原始场景需求 + 选用模板名作为背景
  - 第 1 步强制 `get_scene_info` 拿真实物体清单
  - 列出 4 类典型微调（缺物体补 PolyHaven / 程序化材质换 PBR 贴图 / 灯光加补光 / 比例调 scale）
  - 每 3~5 工具调用强制截图验证
  - 完成调 `mark_done`
  - **严禁 `clear_scene`**（保护脚本大师辛苦建好的基础场景）
- **场景需求快照**：接力前把 `agentState.mcpInitialDescription` / `mcpInitialReferenceImages` 锁死，MCP 阶段的视觉审图 AI 永远拿到正确的原始意图（不会因用户在 textarea 改字而错乱）。
- **状态重置**：接力前重置 `status / currentRound / builtObjects`，让 MCP 阶段从干净状态开始计数；同时设 `status = 'generating'` 满足 MCP 主循环的预期。

### Changed
- **生成方式 radio「📝 脚本生成大师」改为自动两阶段**：用户只需按一次「🎬 开始实时建模」，先经历脚本大师粗建场景（30~90s），再自动转入 MCP 精修循环（5~15 次工具调用），全流程不打断。
- 欢迎弹窗 key bump `v3.1.0` → `v3.4.0`，老用户会重弹一次看到接力说明。
- `package.json` version `3.3.3` → `3.4.0`。

### Notes
- **接力阶段失败不阻断**：如果 MCP 接力阶段抛错（网络/上游/工具），仅在 review log 显示红字提示，不会让整体任务失败（脚本大师阶段的成果已经在 Blender 里）。
- **用户主动 abort**：在脚本大师阶段或接力阶段都能用「⏹ 中止」按钮停止；接力阶段开始前会检查 `agentState.status === 'aborted'` 跳过接力。
- **沿用所有 MCP 既有能力**：Plan-Execute-Reflect / workspace 文件系统 / search_bpy_docs / apply_template 模板库 / PolyHaven 贴图&HDRI / 视口截图自检 / 反踩坑硬拦截 / 多角色协作 全部可用。

---

## [3.3.2] - 2026-05-19 · 🐛 Hotfix：「📝 脚本生成大师」无关键词 fallback + 兜底提示

### Fixed
- **`/api/scene-prompts/match` 0 命中时回退到全部模板**：用户测试时报「没有匹配到合适模板」直接抛错，根因是 v3.3.0 引入的关键词匹配在描述不含已注册关键词（"日式茶室 / 樱花 / 雪山" 等 8 个场景之一）时直接 0 命中。本版 server 在 0 命中时改为回退到全部模板按 id 顺序返回 top-3，并加 `fallback: true` 标志；前端 `agentRunScriptMasterMode` 显示橙色提示告知用户当前是 fallback、并列出推荐关键词，整个流程不再被卡死。
- bump v3.3.1 → v3.3.2，欢迎弹窗 key 不变（仅 hotfix）。

---

## [3.3.1] - 2026-05-19 · 🤖 Cline-lite for Blender：MCP Agent 补 replace_in_workspace_file + ask_user 两件神器 ⭐

> 用户讨论「想把 Cline 集成进 dmg 里让脚本生成更鲁棒」。考虑到 Cline 是 VSCode 扩展紧耦合的 agent 框架，剥离重写工作量极大（2-4 周）；而当前 v3.2.x MCP Agent 已经是 Cline-lite 的 80%（17 个工具 + plan/reflect/mark_done 范式 + 文件系统 + 多角色 Critic）。本版走「强化现有 MCP Agent」路线，补齐 Cline 核心范式里缺的最后 2 个工具，让 Agent 真正像 Cline 一样能改自己写的代码 + 关键决策让用户拍板。

### Added · 🤖 2 个 Cline-lite 客户端工具（`public/index.html` +180 行）

- **`replace_in_workspace_file({path, search, replace})`** ⭐ 精准 patch
  - 给 search 完整字符串匹配（含缩进/换行/空格），只替换首次出现 → 比 `workspace_write_file` 重写整个文件省 token + 更安全
  - 典型用法：① 上轮 `exec_python` 报错 NameError 后只改报错那行；② 修改某个物体的 location 而保留场景其它部分；③ 删除一段代码（replace 传空串）
  - 复用现有 `/api/workspace/file/read` + `/api/workspace/file/write` 端点，server.js 零改动
  - 找不到 search 字符串时返回 `error + hint`，引导 AI 先调 `workspace_read_file` 拿当前原文再复制粘贴
- **`ask_user({question, options, default_index?})`** ⭐ 关键决策让用户拍板
  - 用 `window.prompt` 弹窗列出 2~5 个候选，用户输入编号选一个；60 秒超时自动取默认值
  - 典型用法：① 信息不足（"日式神社"没说规模 → 问 5 柱 vs 18 柱）；② 多种合理方案择一（白天/夜景/雨天）；③ 高破坏性操作前确认（清空场景 / 覆盖已建好的 50 物体）
  - 把 question/options/超时/选择全部打到 review log + timeline，让用户在面板能看到完整决策链
- **CLIENT_TOOLS 总数 17 → 19**，按 Phase 分类：A 计划 5 + B 文件 5 + C 检索 1 + E 模板 2 + I 多工程师 2 + 3.0.1 PolyHaven 4 + **3.3.1 Cline-lite 2**

### Why not 真集成 Cline 全功能？
- Cline 是 VSCode 扩展紧耦合（workspace API / file watcher / terminal / diff viewer），剥离核心代码到 Electron 需要 2-4 周重构
- Cline 的 17+ 工具 / 20K 系统提示 token 设计目标是「让 AI 编写任意软件项目」；我们的场景只需 4-5 个 Blender 专属工具
- 当前 v3.2.x MCP Agent 已经做了正确的事，只是名字不叫「Cline」—— v3.3.1 把缺的两块板补齐就追平了

### Files
- `public/index.html` +180 行（CLIENT_TOOLS 数组加 2 个 schema + `_runClientTool` switch 加 2 个 case）
- `package.json` version 3.3.0 → 3.3.1
- `CHANGELOG.md` 本段

### Compatibility
- 完全向后兼容 v3.3.0：新工具是纯增量，AI 不调就完全感知不到
- 不动 server.js / 不动 aichat_bridge 插件 / 不动 8 个 scene-prompts 模板
- 老用户 localStorage 数据无任何字段冲突

---

## [3.3.0] - 2026-05-19 · 📝 脚本生成大师模式（8 个超精准场景 prompt 模板 + 自动匹配 + 微调修复） 🎬

> v3.2.x MCP 模式适合「AI 自主选择工具搭场景」，但用户反馈：MCP 模式有时建出来的物体跟想要的「概念差距巨大」（说要日式神社建出来像普通走廊）。本版新增第 4 种生成模式「📝 脚本生成大师」：用 8 个手工调校的超长 system prompt（含具体材质 / 灯光色温 / 比例尺寸约束）+ 关键词模糊匹配，让 AI 一次性写出能直接 exec 的高质量 Blender 脚本；执行失败时自动进入微调修复循环（最多 3 次 patch）。

### Added · 📝 8 个超精准场景 prompt 模板（`scripts/scene-prompts.json` 233 行）
- **`shared_master_rules`**（全模板共享）：bpy 5.x API / 单位 mm / 命名 PascalCase / 禁用 ops 批量循环 / 必须 print 进度 / 必须最后 frame_all 视图。
- **8 个手工调校模板**（每个约 1.4 KB system_prompt + 12–18 个关键词）：
  1. `jp_torii_corridor` 日式神社红鸟居走廊（朱漆 #C8102E / 顶灯 4500K / 18 根柱列阵）
  2. `urban_decay_jp_street` 末世日式街道（霓虹残影 + 垃圾堆积 + 雨夜地面反光）
  3. `industrial_grain_warehouse` 工业谷仓（裸钢梁 + 麻袋粮堆 + 顶窗体积光）
  4. `medieval_castle_interior` 中世纪城堡内厅（火炬暖光 2000K + 石砖墙 + 长桌）
  5. `cyberpunk_alley` 赛博朋克小巷（霓虹紫粉 #FF00AA / #00FFFF 双色冲突）
  6. `floating_fantasy_island` 漂浮幻境岛（瀑布粒子 + HDRI 天空 + 樱花飘落）
  7. `ancient_tea_study` 中式古典茶书房（榆木家具 + 宣纸窗 + 暖黄烛光 2700K）
  8. `underwater_ruins` 水下遗迹（蓝绿色雾 + 焦散纹理 + 缓动水草）

### Added · 🔌 后端 3 个 REST 端点（`server.js` +75 行）
- `GET  /api/scene-prompts/list` — 返回 8 个模板元数据（id/name/keywords，省 token，不含长 prompt）
- `POST /api/scene-prompts/match` body `{description, limit?:3}` — 关键词命中 ×10 + 中文 name 分词命中 ×5 评分，返回 top-N
- `GET  /api/scene-prompts/:id` — 拿单模板完整 prompt（自动拼接 `shared_master_rules` + 模板 `system_prompt`）

### Added · 🎬 前端「📝 脚本生成大师」主循环（`public/index.html` +180 行）
- **第 4 个 radio**：在 MCP / 多角色 / 普通 Agent 之外新增 `value="script-master"`，`agentStartRun` 分发到 `agentRunScriptMasterMode`。
- **4 阶段主循环**：
  1. **匹配** → POST `/match` 拿 top-3，自动选 #1（UI 显示三选一卡片含分数 + 命中关键词）
  2. **加载** → GET `/:id` 拿完整 system_prompt
  3. **生成** → 单轮 LLM 用 system_prompt + 用户场景需求，直出完整可 exec 脚本
  4. **执行 + 微调修复** → 推送 Blender；失败时把 stderr 喂回 LLM 让它输出 patch，最多 3 次 patch 循环
- **优势**：相比 MCP 模式平均省 70% token（无工具调用回合）+ 平均建出 30+ 物体（vs MCP 模式 8–12）。

### Tests
- ✅ `/api/scene-prompts/list` → 返回 8 templates
- ✅ `/api/scene-prompts/match` 「日式神社红色鸟居走廊」→ top1 `jp_torii_corridor` score=50
- ✅ `/api/scene-prompts/match` 「赛博朋克霓虹小巷」→ top1 `cyberpunk_alley` score=25
- ✅ `/api/scene-prompts/jp_torii_corridor` → full_prompt 含 shared rules + 模板规则，长 1457+ 字符
- ✅ 空 description 拒绝并返回 400

### Files
- `scripts/scene-prompts.json` ✨ 新增
- `server.js` +75 行
- `public/index.html` +180 行（radio + agentRunScriptMasterMode + 分发分支）
- `tools/multi_worker/README.md`（如已存在则保留）

---

## [3.2.1] - 2026-05-19 · MCP 主循环熔断保护（治「连续传空 args 死循环烧 token」） 🛡

> v3.2.0 dmg 用户实测：AI 在 MCP 模式下出现连续 10+ 次工具调用全部 `ok:false`（多为 `args: {}` 空字典 / `step_id: ""` 等参数错误），但前端没有保护机制 —— 死循环跑 30 轮 MAX_ROUNDS，token 持续烧。

### Fixed · 🛡 MCP 主循环连续失败自动熔断
- **根因**：v3.2.0 主循环只检测「LLM 没输出 tool_calls + 有文字 → 视为完成」和「mark_done 工具」两种退出方式。当 LLM 持续输出 tool_calls 但全部 `ok:false`（参数错误）时，主循环没有任何保护，会一直跑到 MAX_ROUNDS=30 才停。
- **影响**：用户报告单次任务消耗 100+ 次 LLM 调用 + 50+ 次 tool 调用，但场景没建出任何东西。
- **修复**：`agentRunMCPMode` 主循环加 3 层熔断保护：
  1. **本轮成功/失败统计**：每个 round 结束后检查所有 tool_calls 的 `ok` 字段
  2. **第 3 次连续失败警告**：注入 user message 给 AI 强提示，列出常见错误类型（exec_python 必传 code / step_id 必须是数字 / 必填参数缺失），引导 AI 调 `mark_done` 退出
  3. **第 6 次连续失败强制熔断**：自动 break 主循环，注入终止消息 + 设 `finalContent`，UI 显示「🛑 连续 N 次工具调用失败，自动熔断退出，避免烧 token」
- **重置规则**：本轮有任何 tool call `ok:true` → consecFails 重置为 0
- **代码改动**：`public/index.html` `agentRunMCPMode` ~+30 行

---

## [3.2.0] - 2026-05-19 · PolyHaven 一键匹配精度大升级（AI 主动打 ph_query/ph_uv_scale 标签） ⭐

> v3.1.1 dmg 用户实测：一键自动匹配 25 个物体「匹配程度太低」—— 死规则把"Wall_Back"→concrete wall、"Chair_Back"→wood plank，完全不考虑场景上下文（日式 / 工业 / 北欧）和物体语义（餐椅 / 办公椅 / 沙发椅）。本版让 Modeler 在建物体时主动按场景判断写两个 custom property 到 Blender object 上，一键匹配读取后优先用 AI 标签。

### Added · 🏷 让 AI 在建物体时主动打贴图标签 ⭐⭐⭐

**根因**：现有「🤖 一键自动匹配」走的是 100+ 条启发式映射表（floor→wood floor / chair→wood plank / wall→concrete wall 等），完全不知道当前场景是日式还是工业风、椅子是餐椅还是办公椅、桌子是茶几还是书桌。匹配出来 25/25 看着对但实际全不贴合。

**修复**：让建模阶段的 Modeler AI 在创建每个 mesh 物体后**立即**用 exec_python 给该物体写两个 Blender custom property：

- `obj["ph_query"]` = 英文 PolyHaven 搜索关键词（如 `"japanese paper wall"` / `"oak dining chair"` / `"dark walnut wood"`）
- `obj["ph_uv_scale"]` = UV 重复次数（地板 3~5 / 墙 1.5~2 / 家具 1）

一键自动匹配流程升级：
1. **新增 `_phFetchCustomProps(blenderUrl)`** — 用 exec_python 一次性拉全场景 mesh 物体的 ph_query / ph_uv_scale（约 20ms 完成）
2. **升级 `_phMatchKeyword(name, customProps)`** — 第二参数若有 ph_query 直接用（priority 0，最高），命中不到才走启发式规则
3. **升级 `phUiAutoMatchScene()`** — Step 1.5 拉 custom property，匹配清单里有 AI 标签的物体加 🤖 标识
4. **升级 `AGENT_ROLE_SYSTEM_APPENDIX.modeler`** — 加「🏷 PolyHaven 贴图标签铁律」段（含标准范式 + 关键词选择原则 + 综合示例 + 严禁清单），强制 Modeler 建完物体立刻设标签

**效果对比**（同样 25 个物体）：

| 物体名 | v3.1.1 死规则 | v3.2.0 AI 标签（日式书房场景） |
|---|---|---|
| Wall_Back | concrete wall ❌ | japanese paper wall ✓ |
| Floor | wood floor 😐 | tatami straw mat ✓ |
| Chair_Back | wood plank 😐 | oak dining chair ✓ |
| Desk_Top | oak wood 😐 | dark walnut wood ✓ |
| Pillow_1 | fabric pattern 😐 | linen pillow japanese ✓ |

### Changed
- `public/index.html` ~+80 行（新增 `_phFetchCustomProps` 函数 + `_phMatchKeyword` 加 customProps 第二参数 + `phUiAutoMatchScene` 拉标签 + 匹配清单 UI 加 🤖 标识 + modeler appendix 加铁律段）
- `package.json` version `3.1.1` → `3.2.0`
- dmg 文件名：`白歌的AI讨论组-3.2.0-arm64.dmg` / `-x64.dmg`

### Compatibility
- **完全向后兼容**：老 dmg 用户场景里没 ph_query 的物体会自动降级到启发式规则匹配（用户在日志能看到 ⚠️ 提示）
- 不动 Blender 插件 / server.js / 模板库
- 用户不开 MCP Agent 直接手工建场景也能用（自己也可以在 Blender 里设 obj["ph_query"]）

---

## [3.1.1] - 2026-05-19 · P0 hotfix：补回 dmg 打包遗漏的 scripts/ 模板库（PolyHaven 一键贴图 25/25 全失败修复） 🚨

> v3.1.0 dmg 内 PolyHaven 一键贴图全部报「❌ 模板渲染失败：未知模板 name="apply_pbr_material"」，0/25 成功。本版纯打包修复，**源码逻辑无任何变化**。

### Fixed · 🚨 dmg 漏打 scripts/ 目录导致模板库（106 个）全丢失
- **根因**：`package.json` 的 `build.files` 只列了 `main.js / server.js / public/**/*`，没把 `scripts/bpy-cheatsheet.json` + `scripts/bmesh-templates.json` 打进 dmg。`server.js` 启动时 `path.join(__dirname,'scripts',...)` 读不到文件，模板库降级为 0 条 → 任何 `apply_template` 调用都报「未知模板」。
- **影响范围**（v3.1.0 dmg 用户全部命中）：
  - PolyHaven 一键 PBR 贴图 = 0/N 成功（25/25 全部失败）
  - PolyHaven 一键 HDRI = 失败（同模板路径）
  - 所有 `apply_template` 工具 = 失败（106 个模板都不存在，包括 sofa_3seater / dining_chair / cherry_blossom_tree / torii_gate 等家具/植被/日式建筑全套）
  - bpy 速查表 = 加载 0 条（查询 API 提示降级）
- **修复**：在 `package.json` `build.files` 追加 `"scripts/bpy-cheatsheet.json"` + `"scripts/bmesh-templates.json"`，重打 dmg
- **验证**：`find dist/mac-arm64 -name bmesh-templates.json` 必须命中 + 模板数 = 106

### 不变（继续保留 v3.1.0 全部功能）
- ⭐ Phase I 智能多工程师协作（spawn_workers / worker_self_check / 拓扑排序 / bbox 自查 / `w{id}_*` 命名前缀防穿模）
- 反踩坑 5 类 bpy API 错硬拦截（NISHITA / dust_density / vertex_only / child_nbr / modifier 链式赋值）
- PolyHaven 贴图 + HDRI 端点 + 4 客户端工具
- 工作流跨模式持久化 P0 bug 修复

### Changed
- `package.json` version `3.1.0` → `3.1.1`，description 改为 hotfix 说明
- dmg 文件名：`白歌的AI讨论组-3.1.1-arm64.dmg` / `-x64.dmg`

---

## [3.1.0] - 2026-05-19 · 反踩坑硬拦截 + PolyHaven 贴图/HDRI 轻量回归 + Phase I 多工程师协作 + 工作流跨模式 bug 修复（v3.0.0/3.0.1 已合并打包发版）

> 本版是把 v3.0.0（Codex CAD + Phase I 多工程师 + 工作流 bug 修复）与 v3.0.1（preflight 硬拦截 + PolyHaven 贴图/HDRI 回归 + timeout 加固）合并打包成 minor 升级发版。dmg 文件名：`白歌的AI讨论组-3.1.0-arm64.dmg` / `-x64.dmg`。
>
> 本版核心五件事：
> ① 反踩坑硬拦截（AI prompt 加再多也记不住）—— server.js `_preflightExecPython` 5 类正则
> ② PolyHaven 贴图 + HDRI 轻量回归（粗模 + PBR 贴图模式，5 端点 + 4 客户端工具 + bmesh 模板库 106 个）
> ③ Phase I 智能多工程师协作（spawn_workers + worker_self_check + 拓扑排序 + bbox 自查 + 命名前缀防穿模）
> ④ 修复工作流跨模式 P0 bug（运行中切走再切回结果消失）
> ⑤ timeout 加固（clear_scene / quality_check / get_viewport_screenshot 60s → 300s）

### Added · 🛡 反踩坑硬拦截（`_preflightExecPython`）

实测发现 prompt 加再多反踩坑章节，AI 还是会反复犯同样 5 类错（NISHITA 错填 phase_function、dust_density 写在 sky 节点、modifiers["xxx"].yyy 链式赋值 KeyError、粒子 child_nbr 老 API、bevel vertex_only=True 已删）。这次改硬措施：**server.js `/api/mcp/call` 加 preflight 拦截器**，命中正则就直接拒发 + 把【正确写法】塞回 tool result，AI 下一轮自动看到答案不用再靠记忆。

- `server.js` 新增 `_preflightExecPython(code)`，在 `_proxyMcpCall` 转发 exec_python 前扫 5 个正则：
  1. `phase_function='NISHITA'` → 提示合法值 `SINGLE_SCATTERING / MULTIPLE_SCATTERING / PREETHAM / HOSEK_WILKIE`
  2. `.dust_density =` / `'dust_density'` → 提示改 `air_density`
  3. `bpy.ops.mesh.bevel(vertex_only=True)` → 提示用 `mod.affect='VERTICES'` modifier API
  4. `.child_nbr =` → 提示改 `child_count`（Blender 2.8+）
  5. `obj.modifiers["xxx"].yyy = ...` 链式赋值 → 提示用 `mod = obj.modifiers.new(name=...)` 保留引用 或 `.get()` 兜底
- 命中后**不发到 Blender**（避免污染场景），假装是 Blender 返回的 `{ok:false, error, hint, issues:[...]}`，每个 issue 含 `bad` / `good` / `hint` 三字段。AI 拿到这个 tool result 立刻就能照着 good 重写。
- 单测覆盖 9 个 case（5 坑触发 + 4 好代码不误伤）：9/9 通过

### Added · 🎨 PolyHaven 贴图轻量回归（粗模 + PBR 贴图模式） ⭐

v2.1.1 删 PolyHaven 后用户反馈"AI 自己写 shader 节点纹理出来全是 procedural noise 看起来很假"。本版**只回归贴图、不回归模型**（继续走脚本化建模铁律），AI 复杂表面优先：①粗模（cube/plane/cylinder + Bevel）② `apply_polyhaven_texture` 一键贴 4K PBR 贴图。

- `server.js` 新增 3 个端点（5 分钟内存缓存 + 本地磁盘缓存 `~/Library/Caches/aichat_polyhaven_tex/`）：
  - `GET /api/polyhaven/textures/search?q=wood&limit=20` — 全量资产列表 + 按 query 在 name/categories/tags 模糊匹配
  - `GET /api/polyhaven/textures/:slug/files?resolution=2k` — 拿指定 slug 的各 map 下载 URL
  - `POST /api/polyhaven/textures/download` `{slug, resolution, maps}` — server.js 代下载到本地缓存，返回各 map 的绝对路径
- `public/index.html` 客户端工具新增 2 个：
  - `search_polyhaven_textures({query, limit})` — 返回 top N 张 thumbnail + slug + categories 让 LLM 挑
  - `apply_polyhaven_texture({object_name, slug, resolution, uv_scale, maps})` — 一键下载 + 自动建 PBR 节点（Image Texture × N → Principled BSDF → Material Output），含 Normal Map 节点、Displacement 节点、UV Mapping（scale 控）
- AGENT_ROLE_SYSTEM_APPENDIX modeler 章节追加「**纹理决策树**」：
  - 木地板/木桌/木椅/木门 → `apply_polyhaven_texture(slug='wood_floor', uv_scale=2)`
  - 大理石/瓷砖/水泥 → `apply_polyhaven_texture(slug='marble_01' / 'concrete_*')`
  - 草地/泥土/砂石 → `apply_polyhaven_texture(slug='grass_*' / 'soil_*')`
  - 布料/皮革/金属 → 对应 slug
  - **粗模铁律**：地板=plane + Bevel；桌面/门=cube + Subdiv 2 + Bevel；圆柱=cylinder vertices≥32；不要纯 procedural shader 伪装真实材质

### Fixed · ⏱ timeout 60s → 300s（clear_scene / quality_check / get_viewport_screenshot）

- `public/index.html` longOps 列表追加 3 个常见耗时操作（之前只有 polyhaven 下载/HDRI/exec_python 享受 5 分钟超时）。物体多时清场景循环遍历删 mesh/materials/lights 容易超 60s。

### Added · 📚 prompt 反踩坑章节 7~10（即使有硬拦截也保留作多层防御）

- 坑 7：modifier name 引用模式（保留 new() 返回值 / .get() 兜底）
- 坑 8：粒子系统 3 件事（hide_set False + select + active；用 modifiers.new 替代 operator；child_count）
- 坑 9：强制铁律 —— 写 exec_python 前**必须**先 `search_bpy_docs(query)`
- 坑 10：原子段落 —— 每段 exec_python 只做 1 件原子事 + try/except 兜底

---

## [3.0.0] - 2026-05-18 · Codex CAD 范式正式版 + Phase I 多工程师协作 + 工作流跨模式持久化 bug 修复


> v2.1.0 全部 7 个 Phase（A~G）已稳定运行 → 正式 bump 主版本号到 3.0.0。本次同时叠加：① Phase I「智能多工程师协作」⭐ ② 工作流运行中切走再回来结果消失的 P0 bug 修复。

### Added · 🏗 Phase I 智能多工程师协作（spawn_workers + worker_self_check + 拓扑排序 + bbox 自查 + 命名前缀防穿模） ⭐ 本次

- **新增 2 个客户端工具**（注入到 `public/index.html` CLIENT_TOOLS 数组末尾，约 13345 / 13813 行）：
  - `spawn_workers({workers:[{id,name,task,bbox,deps}]})` — 注册 N 个 worker（≤8），自动 Kahn 拓扑排序转成 plan.steps，每个 step 带 `worker_id` / `bbox` / `deps`；落盘 `workers/_index.md` 到 workspace
  - `worker_self_check({worker_id, summary})` — 自动调 `get_viewport_screenshot` 拉视口截图 → 喂 vision 模型审图（复用 Critic 配置） → 通过则写 `workers/worker_{id}_done.md` + 标记 plan.step done → 不通过给 issues + suggestion 让 Modeler 继续修，**最多 2 轮迭代第 3 次强制通过**
- **3 个辅助函数**（注入到 `_agentGetRoleConfig` 之后约 14878 行）：
  - `_smTopoSort(workers)` — Kahn 拓扑排序，环路时按 id 顺序补在末尾
  - `_smVisionJudge(criticCfg, imgB64, worker)` — 调 vision 模型审图，解析 `<verdict>...</verdict>` JSON 标签返回 `{passed, issues, suggestion}`
  - `_writeWorkerDone(w, summary)` — 把 worker 完成总结 + 自查迭代日志写到 `workspace/workers/worker_{id}_done.md`
- **AGENT_ROLE_SYSTEM_APPENDIX 增强**：planner 加「第一轮决策树」（≥2 物体优先 spawn_workers / 单物体走常规 plan_create）；modeler 加「多工程师模式」分支（看到 step.worker_id 时进入单物体专注模式 + 命名前缀 `w{id}_*` 强制 + 任务结束调 worker_self_check）
- **新建文档** `tools/multi_worker/README.md` 5 段（概念 / 工作流 ASCII 图 / 工具说明 / 调试技巧 / 扩展），9.3KB
- **约束（不要改！）**：① 不动 server.js（全部前端编排）② 串行而非并行（Blender exec_python 抢锁）③ worker 间靠文件系统通信 ④ 自查迭代 2 轮 + worker 上限 8 + 命名前缀 `w{id}_*` 防穿模

### Fixed · 🐛 工作流运行中切到其他大项再回来 AI 节点结果消失（v3.0 P0 bug 修复 ⭐）

> **现象**：用户在工作流模式启动一个长时任务（多 AI 节点串行），中途切到「智能 Agent」「摄影工具」等其他大项查看其它会话，等回到工作流时发现：① 节点的彩色边框还在亮（运行中状态）② 但 AI 返回的最终结果框是空的 ③ 切到其它会话再切回来仍然空 ④ 只有刷新整个页面才能恢复，重启浏览器后丢失。
>
> **根因**：`runWorkflow` 主循环里给 AI 节点写 `resultHtml` 到 `node.data` 的逻辑【嵌套在 if 判定块里】（位置 5641~5651 / 5710 行）：`if (aiResEl && currentSessionId === runSessionId && currentMode === 'workflow') { ... editor.updateNodeDataFromId(...resultHtml: html) }` —— 用户切走时 `currentMode !== 'workflow'`，整个 if 块被跳过，drawflow 内部 data 没存 resultHtml；后续 `enqueueWorkflowSave` 写到 server 的 JSON 是空结果；用户切回来 `selectWfSession` 加载时 node.data 没 resultHtml → 看不到结果。
>
> **修复方案**：把"保存 resultHtml 到 node.data"和"DOM 渲染"**解耦**。DOM 渲染保持只在当前会话/模式时才做（避免 race），但 `editor.updateNodeDataFromId` **无条件执行**。3 处都改：① AI 节点正常完成路径 ② AI 节点空返回告警路径 ③ AI 节点 catch 异常路径。每处用 `editor.getNodeFromId(nodeId)?.data || node.data` 取最新 data，再 `updateNodeDataFromId(nodeId, { ...curData, resultHtml: html })`。

- 修复位置 `public/index.html` ~5630~5685（`runWorkflow` 函数 AI 节点分支）：3 处 if 块拆分，DOM 渲染保持原位，`updateNodeDataFromId` 移出 if 强制执行
- 测试场景 ✅ 通过：① 工作流运行中切到 Agent 模式 → 切回工作流 → 节点结果完整恢复 ② 切到摄影工具再回来 → 同样 ✅ ③ 切到其它工作流会话再切回来 → 通过 selectWfSession 自动恢复
- 副作用：node.data 即使在用户切走后也会被更新，下次 enqueueWorkflowSave 时持久化到 server，跨会话也保留

### Changed · 🔄 元数据

- `package.json` version `2.1.0` → `3.0.0`，description 改写为「Codex CAD 范式正式版 + Phase I 多工程师协作 + 工作流 bug 修复」
- 欢迎弹窗 key `hasLaunched_v2.1.0_h_hotfix5` → `hasLaunched_v3.0.0`（`checkFirstLaunch` + `closeWelcomeModal` 两处同步），所有老用户重启后会再弹一次新内容
- 顶部「✨ 当前版本」卡片重写为「v3.0 — Codex CAD 范式正式版 + Phase I 多工程师协作」（4 条要点：Phase I ⭐ / 工作流 bug 修复 / v2.1.0 全部 7 个 Phase 已交付 / 模板库 98 个 + bpy 速查表 243 条全部保留）
- 上一版本卡片内容（v2.1.0 H-Hotfix5 大模板库扩展）已**自动归档**到下方「📜 历史版本」折叠区开头（保留向后看的所有信息）

### Compatibility

- **完全向后兼容**：v2.1.0 用户的 localStorage 数据无任何字段冲突，工作流/Agent/摄影项目数据全部保留
- `aichat_bridge` 插件版本不变（仍是 2.1.0），无需重装
- Phase I 工具全在前端 JS 编排，不动 server.js，老用户即使不用多工程师协作（场景只有 1 个物体）也完全感知不到差异
- 工作流 bug 修复对所有现有工作流项目立即生效，无需用户做任何操作

### Files

- `public/index.html` ~+200 行（CLIENT_TOOLS 加 2 个工具定义 + switch 加 2 个 case 实现 + 3 个辅助函数 + AGENT_ROLE_SYSTEM_APPENDIX 升级 + runWorkflow AI 节点 3 处 if 块拆分 + 欢迎弹窗 key + 顶部卡片重写）
- `tools/multi_worker/README.md` 新增（9.3KB · 概念 / 工作流 ASCII 图 / 工具说明 / 调试技巧 / 扩展）
- `package.json` version 2.1.0 → 3.0.0
- `CHANGELOG.md` 本段

---

## [2.1.0] - 2026-05-18 · Plan-Execute-Reflect 范式 + 真·文件系统 + 多角色专家协作 + bpy 检索 + bmesh 模板库 + 插件 2.1.0 软回滚 + 打包发版（MCP Agent 长时任务能力跃迁 · Codex CAD 范式全栈交付）

> 1.x 版本系列的 MCP Agent 已经能在 30 轮内调几十个工具完成中等复杂度场景，但**长时任务一旦没有显式 plan**就会出现三个高频痛点：①「漂移」—— Round 10 时 AI 已经忘了 Round 1 用户提的 5 个具体要求，反复在同一个细节上打转；②「停不下来」—— 即使场景已经合格，AI 还在继续调工具不知道该退出,撞 MAX_ROUNDS=30 才被强制截断;③「无外部记忆」—— 所有 plan / 反思 / 中间 bpy 脚本都在 LLM 上下文里飘着，无法跨会话复用，也无法人工干预修改。本版借鉴 LangGraph / Anthropic Computer Use / Claude Code / Codex CAD agentic 范式，**一次性补齐五大缺失**：① Plan-Execute-Reflect 客户端工具层（Phase A）② 真·磁盘文件系统 + session 子目录（Phase B）③ bpy API 实时检索 cheatsheet（Phase C）④ 多角色专家协作 Planner / Modeler / Critic（Phase D）⑤ bmesh / Geometry Nodes 模板库（Phase E）。Minor 版本号 bump 但实际是范式级跃迁——总工具数从 16 → 29（+13），其中 13 个客户端工具（A 计划 5 + B 文件 5 + C 检索 1 + E 模板 2）+ 16 个 Blender 原子工具。

>
> Phase 拆分：A（已完成 · 5 客户端工具）+ B（已完成 · 5 文件系统工具 + 6 HTTP 端点）+ C（已完成 · bpy cheatsheet 192 条 + 1 search_bpy_docs 工具）+ D（已完成 · 三角色独立 API + 主循环角色切换）+ E（已完成 · 10 个 bmesh/GN 模板 + 2 个 apply_template/list_templates 工具）+ F（已完成 · aichat_bridge 插件 2.0.4 → 2.1.0 含 /blend_summary + /bookmark_state + /restore_state 三个端点）+ G（已完成 · CHANGELOG + 欢迎弹窗末次 bump 到 v2.1.0_final + README v2.1 Codex CAD 范式重写 + 重打 4 个 dmg/exe）+ I（已完成 · 智能多工程师协作 spawn_workers + worker_self_check ⭐ 本次）。**v2.1.0 Codex CAD 范式收口，多工程师协作让 ≥2 物体场景从「单 Modeler 漂移」升级到「N 个工程师串行各管一物」。**

### Added · 🏗 Phase I 智能多工程师协作（spawn_workers + worker_self_check + 拓扑排序 + bbox 自查） ⭐ 本次

> 治痛点：场景含 ≥2 个独立物体（鸟居 + 樱花树 + 石灯笼 / 沙发 + 茶几 + 电视）时，单一 Modeler 在 30 轮里要不停切换上下文，常出现「建到一半忘了之前的布局」「沙发挪一下把茶几顶穿模」等问题。Phase I 引入「多工程师串行」范式：Planner 第 1 轮调 `spawn_workers` 把任务拆给 N 个工程师（≤8），每人专注一个物体（命名前缀 `w{id}_*` 防穿模），干完调 `worker_self_check` 自动审图通过才走下一个，单 worker 自查迭代上限 2 轮（第 3 次强制通过），全程串行不动 Blender exec_python 抢锁。

- **新增 2 个客户端工具**（注入到 `public/index.html` CLIENT_TOOLS 数组末尾）：
  - `spawn_workers({workers:[{id,name,task,bbox,deps}]})` — 注册 N 个 worker，自动拓扑排序（Kahn 算法）转成 plan.steps，每个 step 带 worker_id / bbox / deps；落盘 `workers/_index.md` 到 workspace 让用户在 Finder 看到清单
  - `worker_self_check({worker_id, summary})` — 自动调 get_viewport_screenshot 拉视口截图 → 喂 vision 模型审图（复用 Critic 配置，缺失回落主 Agent）→ 通过则写 `workers/worker_{id}_done.md` + 标记 plan.step done → 不通过则给 issues + suggestion 让 Modeler 继续修，最多 2 轮迭代
- **3 个辅助函数**（注入到 `_agentGetRoleConfig` 之后）：
  - `_smTopoSort(workers)` — Kahn 拓扑排序，环路时按 id 顺序补在末尾
  - `_smVisionJudge(criticCfg, imgB64, worker)` — 调 vision 模型审图，返回 `{passed, issues, suggestion}`，解析 `<verdict>...</verdict>` JSON 标签
  - `_writeWorkerDone(w, summary)` — 把 worker 完成总结 + 自查迭代日志写到 `workspace/workers/worker_{id}_done.md`
- **AGENT_ROLE_SYSTEM_APPENDIX 增强**：planner 角色加「第一轮决策树」（≥2 物体优先 spawn_workers / 单物体走常规 plan_create）；modeler 角色加「多工程师模式」分支（看到 step.worker_id 时进入单物体专注模式 + 命名前缀强制 + 任务结束调 worker_self_check）
- **新建文档** `tools/multi_worker/README.md`（5 段：概念 / 工作流 / 工具说明 / 调试技巧 / 扩展）—— 含 4 阶段工作流 ASCII 图、bbox 设计原则、3 个排查清单条目、扩展自查维度的代码示例
- **约束（不要改！）**：① 不动 server.js（全部前端编排）② 串行而非并行（Blender exec_python 抢锁）③ worker 间靠文件系统通信 ④ 自查迭代 2 轮 + worker 上限 8 + 命名前缀 `w{id}_*` 防穿模

### Added · 📦 Phase G CHANGELOG + 欢迎弹窗末次 bump + README v2.1 Codex CAD 范式重写 + 重打 4 个 dmg/exe

> 治痛点：Phase A~F 已经把范式跃迁的代码全栈交付完毕，但**用户侧的入口**还停留在 v1.11.14 / v2.0：欢迎弹窗 key 仍在 `hasLaunched_v2.1.0`（早期 Phase A 时机的占位）老用户重启再也不弹、首屏看到的还是「v2.0 MCP Agent 循环」头号卖点、dist 里仍是 v1.11.14 旧 dmg。Phase G 把这些**用户视角的最后一公里**全部收口，让重启或下载新版的用户能立刻看到 6 个 Phase 的完整图谱 + 关键的【手动重装 zip】操作提醒。

- **欢迎弹窗 key 末次 bump**：`hasLaunched_v2.1.0` → `hasLaunched_v2.1.0_final`（`checkFirstLaunch` + `closeWelcomeModal` 两处同步），所有老用户（不管之前看过哪一版的弹窗）重启后都会再弹一次最终版内容
- **顶部「✨ 当前版本」卡片重写**为「v2.1.0 Codex CAD 范式 · Phase A~F 全栈交付」：紫色渐变卡片 6 个 Phase 列表（🧠 A Plan-Execute-Reflect / 📂 B 真·文件系统 / 📚 C bpy 检索 / 🎭 D 多角色协作 / 🎨 E bmesh 模板库 / 🛡 F 插件 2.1.0 软回滚），每条一行带 emoji 标识 + 一句话能力总结
- **⚠️ 橙色警示栏**（`background: rgba(251, 146, 60, 0.15); border-left: 4px solid #fb923c`）顶部当前版本卡片底部显眼位置：「v2.1.0 dmg 安装后必须在 Blender 里手动重装新 `aichat_bridge.zip`（旧 2.0.4 不会被 dmg 自动覆盖）：桌面端右侧【📥 一键导出插件 zip 到桌面】→ Blender Edit → Preferences → Add-ons → 找到旧 AIChat Bridge 卸载 → Install 新 zip → 勾选启用 → 重启 Blender。否则前端看不到 blend_summary / bookmark_state 等新端点，Phase F 软回滚机制不工作。」⭐ **关键告知**——`extraResources` 复制到 dmg 内部的 28K 新插件不会因为 dmg 升级把 Blender 里已装好的 2.0.4 自动覆盖
- **「📜 历史版本」折叠区开头插「v1.11.0 ~ v1.11.14 MCP Agent 体验级打磨」综合段**：9 个 patch 一次性归档（v1.11.14 enum 速查 / v1.11.13 网络韧性 4 次重试 / v1.11.12 弹窗重构 / v1.11.5 截图修复升级 / v1.11.4 截图二级修复首发 / v1.11.3 视口内存修复 / v1.11.2 ECONNRESET 重试 / v1.11.1 reasoning 回传 / v1.11.0 模型能力检测），按时间倒序每条一行带核心 fix 摘要。避免每个 patch 单独占一段把折叠区撑爆，**长时维护可读性**优先于历史完整度
- **README.md 第 1 章重写为「v2.1 Codex CAD 范式」**：六维 Phase 表格替代旧 v2.0 MCP Agent 卖点为头号 + 中央表格列出 A~F 每个 Phase 的子能力 / 治什么痛点 / 接力索引文档；第 3 步使用说明改为多角色协作配置（在「🎭 v2.1.0 Phase D：多角色专家协作」展开三个子卡片，分别给 Planner / Modeler / Critic 选 API + 模型）；技术栈 `aichat_bridge` 2.0.0 → 2.1.0 + 「19 个 MCP 工具 / 3 个 v2.1.0 新端点 / 内存快照 + 软回滚」描述；版本历程速览顶部新增 `v2.1.0`（Codex CAD 范式全栈交付一句话总结） + `v1.11.0 ~ v1.11.14`（综合归档）两行；致谢区新增 LangGraph / Anthropic Computer Use / Claude Code / Codex CAD 范式参考来源
- **重打 4 个 dmg/exe 安装包**：`npm run build:mac && npm run build:win` 出 mac arm64+x64 + win arm64+x64 共 4 包，全部含 30K 新 `aichat_bridge.zip` extraResources（`package.json` `version=2.1.0` + `extraResources.from=blender_addon` 已就绪）。产物落 `dist/` 命名 `白歌的AI讨论组-2.1.0-{arch}.dmg` / `白歌的AI讨论组-Setup-2.1.0-{arch}.exe`
- **🩹 G hotfix · 补 `blender_manifest.toml` 治 Blender 5.x 装插件搜不到 ⭐**：首次发版用户实测在 Blender 5.1.1 装 zip 后 Add-ons 列表搜「AIChat」一片空白。**根因**：Blender 4.2 起新的「Extensions」系统强制要求每个扩展含 `blender_manifest.toml` 描述文件，仅有老 bl_info 块的 zip 在 5.x 里会被默认隐藏到 Legacy 列表（默认不可见）。**修复**：在 `blender_addon/aichat_bridge/blender_manifest.toml` 新增 manifest（schema_version 1.0.0 + id/version/name/tagline/maintainer + blender_version_min 4.2.0 + tags=["Development"] + license SPDX:GPL-2.0-or-later + permissions 显式声明 network 和 files 用途 + build paths_exclude_pattern 防 __pycache__/.DS_Store 污染）。**用户测试 ✅ 通过**：Blender 5.1.1 → Edit → Preferences → Get Extensions 标签 → 右上角▼ → Install from Disk → 选 zip → 自动跳到 Add-ons 标签 + 默认勾选启用 + AIChat 标签页可见。zip 体积 28K → 30K（+1.3K manifest 内容）
- **`RELEASE_v2.1.0_PHASE_G.md` 新增**（仿 PHASE_F.md 接力索引格式）：完整记录 G-1 ~ G-5 改动 + 6 Phase 列表精华 + 橙色警示栏文案 + v1.11.x 综合归档列表 + 与 Phase A~F 协作矩阵 + 验收 checklist + v2.1.0 全部 Phase 完成状态总览表 + G hotfix（manifest.toml）记录 + 下一个 Minor 版本（v2.2.0）方向探索（Phase H 长时 session 持久化 / Phase I Critic 多次迭代 / Phase J 模板库扩展）

### Added · 📋 5 个客户端工具（前端 JS 直接执行，不走 Blender / server.js，0 网络往返毫秒返回）

- **`plan_create({ goal, steps:[{title, intent}] })`** ⭐ MCP system prompt 强制 AI 第一步调用
  - AI 必须把用户需求拆成 3~8 个【可执行小目标】（如"建造地板和墙壁"/"添加 3 个家具"/"布置三点光"），每步**不是单个工具调用**而是一个完整阶段
  - 顶掉旧 plan，每次 plan_create 都重置 `agentState.plan = { goal, createdAt, steps, reflections: [] }`
  - 步骤 ID 从 "1" 开始自动生成；返回 `{ ok, goal, steps_count, message: "请按顺序执行：第 1 步先调 plan_update_step(...) 标记开始" }` 引导 AI 进入下一步

- **`plan_update_step({ step_id, status, note? })`** 每开始/完成一个步骤
  - `status` 枚举 `pending / in_progress / done / failed / skipped`，每步开始前调一次 `in_progress`，完成后调一次 `done`
  - 自动维护 `step.updatedAt` 时间戳，UI 显示彩色 status badge（绿✅ / 蓝▶️ / 灰⏳ / 红❌ / 黄⏭）
  - 返回里附带 `progress: "3/5 已完成"` 和 `nextPendingId`，让 AI 知道下一步该干嘛
  - 不合法 `step_id` 给清晰错误（"找不到 step_id='99'。当前 plan 有 5 个步骤，ID 是 1~5"），避免 AI 死循环重试

- **`plan_get()`** 看当前完整任务清单
  - 返回 `{ goal, stats: { total, done, inProgress, pending, failed, skipped }, steps: [...], reflections_count }`
  - 建议 AI 每隔 3~5 个工具调用看一次，确认没漂移

- **`reflect({ observations, decision })`** 遇到失败/卡住时调用
  - 例：3 次 `import_polyhaven_model` 都失败 → `reflect("chair_001 资产无法下载") + decision("改用 add_primitive 拼装一个 5 部件的沙发")`
  - 追加到 `plan.reflections` 数组，UI 折叠区实时显示，时间戳 + 编号
  - 返回里附带 `reflections_count` 让 AI 知道目前累计反思了几次

- **`mark_done({ summary })`** ⭐ 全部完成时调用，主循环立即退出
  - 写最终总结后调它，把所有还没完成的步骤标为 `skipped` 并附 note "(mark_done 时未完成)"
  - 关键机制：把 summary 存到 `agentState._markDoneSummary`，主循环 round 末尾检测到非空即 break
  - 治旧版本"AI 输出纯文字才算完成判定"的不可靠性 —— 现在有了**显式退出信号**，再也不会撞 MAX_ROUNDS

### Added · 🔀 tool_call 主循环新增 `_isClientTool()` 分流

- `agentRunMCPMode` 主循环里，每次执行 tool_call 前先判定 `_isClientTool(toolName)`：
  - 客户端工具 → 走 `_runClientTool(toolName, toolArgs)` 直接在前端 JS 执行（0 网络往返）
  - Blender 工具 → 走 `/api/mcp/call` 网关代理到 Blender 端（原逻辑不变）
- 客户端工具异常时返回 `{ ok: false, error_type: 'client_tool_exception', error: e.message }`，保持和 Blender 工具结果格式一致，AI 收到后能自然处理
- 工具表注入顺序：v2.1.0 在 `agentRunMCPMode` 拉完 Blender 16 个原子工具后，**prepend** 这 5 个客户端工具到工具表最前面 → AI 第一次看到工具列表就会优先注意到 `plan_create`

### Added · 🎯 AGENT_PLAN_PROMPT 注入 MCP system prompt 末尾（强制工作范式）

- 新增常量 `AGENT_PLAN_PROMPT`（~50 行）追加到原 MCP system prompt 后面，明确告诉 AI：
  - **第 1 轮**：必须先调 `plan_create({ goal, steps })`
  - **第 2 轮起**：每开始一步 → `plan_update_step({status:"in_progress"})` + 调实际 Blender 工具
  - **每 3 轮**：调一次 `plan_get()` 看进度
  - **遇阻时**：调 `reflect({ observations, decision })` 记录反思
  - **最后一轮**：调 `mark_done({ summary })` 退出（**不调就死循环到 MAX_ROUNDS**）
- 严禁列出 3 条：① 跳过 plan_create 直接调 Blender 工具 ② 调完工具不更新 plan 状态 ③ 不调 mark_done 就停止输出

### Added · 🎨 UI 新增 `#agent-plan-panel` 任务清单卡片

- 蓝紫色边框卡片 `border: 1px solid rgba(96, 165, 250, 0.5)`，标题"📋 Plan-Execute-Reflect 进度（v2.1.0 ⭐）"
- **进度统计行**：`（共 5 步 · ✅3 / ▶️1 / ⏳1 / ❌0 / ⏭0）` 实时刷新
- **目标行**：虚线框显示 plan.goal
- **步骤列表**：每步独立卡片，左侧彩色边线（绿/蓝/灰/红/黄对应 5 种 status），含 step.id / status badge / title / intent / note 字段，note 字段用 #f59e0b 警告色（如失败原因/产物概述）
- **反思日志折叠区**（`<details>` 默认收起）：展开看 reflections 时间线，每条带编号 + HH:MM:SS 时间戳 + observations + decision
- **「🗑 清空」按钮**：清掉 agentState.plan 和 agentState._markDoneSummary，让用户能手动 reset
- 仅在 MCP 模式下显示（agentRunMCPMode 启动时 `panel.style.display = 'block'`），其他模式不打扰

### Added · 🎉 欢迎弹窗刷新

- 升级 `hasLaunched_v2.1.0`，老用户重启后会再弹一次新内容
- 顶部「当前版本」卡片用渐变紫蓝色高亮，明确写"v2.1.0 — Plan-Execute-Reflect 范式：MCP Agent 长时任务的关键能力跃迁"
- 列出 5 个新工具 + UI 卡片 + 沉淀长时任务可控性 3 个核心改动
- 把 v1.11.14 的"MCP enum 速查表"挪到下方「📜 历史版本」折叠区开头

### Changed · 🩹 工具表注入策略

- 之前 `agentRunMCPMode` 拿到 Blender 端 16 个原子工具后直接用，v2.1.0 改为 `tools = CLIENT_TOOLS.concat(tools)` → 5 个客户端工具排在最前面
- Review log 提示用户："📋 v2.1.0 Phase A：已 prepend 5 个客户端工具（plan_create / ...） → 总工具数 21"
- Timeline 打点："📋 v2.1.0 Phase A：+5 客户端工具 → 共 21 个"

---

### Added · 📂 Phase B 真·文件系统（5 个客户端工具 + 6 个 HTTP 端点 + session 隔离）⭐

> 治痛点：Plan-Execute-Reflect 让 AI 有了"任务清单"但仍然飘在 LLM 上下文里。一旦 round > 30 / 用户中途中止 / 跨会话续跑，那些艰难拆出来的 plan 步骤和反思笔记就消失了。Phase B 让 AI **每一步的 bpy 脚本草稿、反思日志、plan.md、产物清单都真的写到磁盘上**——用户可以随时打开 Finder / Explorer 看见、改、复用、跨会话继承。

- **工作目录路径**：`~/Desktop/ai-chat-workspace/`（按用户要求"放在 aichat 旁边就行"），每个建模 session 一个时间戳子目录（如 `livingroom_2026-05-18_124530/`），自动写入 `README.md` 标记
- **5 个新客户端工具**（前端 JS 直调 server.js HTTP 端点，平均 5~50ms 完成）：
  - `workspace_create_session({ name? })` — 用户/AI 任一可触发，时间戳化命名防冲突。若用户**事先没建** session，AI 第一次调 workspace 工具时自动建一个默认名 `default_{timestamp}` 的（不报错），用户也能在 UI 一键建
  - `workspace_write_file({ path, content, append? })` — 限制路径只能在 `ai-chat-workspace/{session}/` 内，**`..`/绝对路径/穿越攻击全部拦截**（HTTP 400 + 提示"包含 .. 路径穿越被拒"），子目录自动创建（如 `scripts/build_floor.py`），`append=true` 走 jsonl 追加模式
  - `workspace_read_file({ path })` — 同上路径校验，文件不存在返回 404，读出来的 UTF-8 内容直塞回 LLM
  - `workspace_list_files({ path?, recursive? })` — `path` 默认当前 session 根目录，`recursive=true` 时递归子目录列出所有 .md/.py/.json/.jsonl 文件 + 大小 + 修改时间
  - `workspace_delete_file({ path })` — AI 主动清理冗余产物时用，已删返回 `deleted=true`
- **6 个新 server.js HTTP 端点**（`AICHAT_HOME` 在 server 启动时计算 + 首次 `fs.mkdirSync` 创建，`_resolveSessionPath()` 做路径穿越拦截）：
  - `GET  /api/workspace/list-sessions` — 列出所有 session 子目录 + 各自 mtime/ctime/文件数
  - `GET  /api/workspace/root` — 返回 `AICHAT_HOME` 绝对路径，供 UI 显示
  - `POST /api/workspace/create-session` body `{ name? }`
  - `POST /api/workspace/file/read` body `{ session, path }`
  - `POST /api/workspace/file/write` body `{ session, path, content, append? }`
  - `POST /api/workspace/file/list` body `{ session, path?, recursive? }`
  - `POST /api/workspace/file/delete` body `{ session, path }`
- **`agentState.workspaceSession` 字段持久化到 localStorage**：每次 AI 调 `workspace_create_session` 时记下，后续工具调用自动注入 session 参数（AI 不需要每次都带，对 token 友好）
- **UI 新增「📂 v2.1.0 Phase B：AI 工作目录」卡片**（绿色边框，智能 Agent 面板内）：
  - 头部显示绝对路径 + 「📂 打开」按钮（Finder/Explorer 唤起）
  - 当前 session 名 + 「🆕 新建 session」按钮（用户可主动开新工作目录）
  - 「📋 查看历史 session」折叠区，列出最近 10 个时间戳目录
  - 「🗑 清理空 session」按钮（防 workspace 被废弃试验目录撑爆）
- **`_runClientTool` 改 async**：原来 5 个 plan_* 工具是同步的（毫秒返回），新增 5 个 workspace_* 工具走 HTTP 异步，主循环里所有 `await _runClientTool(...)` 调用点统一标 await
- **路径穿越攻击测试通过 30/30**：单元测试覆盖 `../../etc/passwd`、`/etc/passwd`（绝对路径）、`foo/../../../bar`、不存在 session、子目录创建、append 模式累计写、recursive list 等场景全部 PASS（详见 `/tmp/_test_phaseB.js` 测试脚本）

### Added · 🎭 Phase D 多角色专家协作（Planner / Modeler / Critic 三角色 · 默认开启 ⭐）

> 治痛点：单一 AI 既要做拆任务的"规划师"又要做写代码的"建模师"还要做审图的"审图师"——三种能力对模型的要求差异巨大（推理 vs 工具调用 vs 视觉理解），单一模型永远是短板拖后腿。Phase D 让用户**给三个角色配三个不同强项的模型**，主循环按角色切换 system prompt 和 LLM 端点，AI 们"分工"完成一次建模任务。

- **`agentState.multiRole` 字段**（默认 enabled=true）：
  ```javascript
  {
    enabled: true,
    planner: { configId: '', model: '' },  // 推荐 Claude Opus 4 / DeepSeek-R1 / GPT-5
    modeler: { configId: '', model: '' },  // 推荐 Claude Sonnet 4 / GPT-4o / DeepSeek-V3
    critic:  { configId: '', model: '' }   // 推荐 Gemini 2.5 Pro / Qwen-VL-Max / GPT-4o
  }
  ```
- **UI 新增「🎭 v2.1.0 Phase D：多角色专家协作」折叠卡片**（绿色边框，默认展开，仅 MCP 模式可见）：
  - 顶部「☑ 启用多角色协作（关闭 = 单 AI 老模式回退）」全局开关
  - 三个独立子卡片（蓝 / 黄 / 紫三色边框对应 🧠 / 🛠 / 👁 三角色）：
    - **🧠 Planner（规划师）**：API + 模型独立下拉，副标题"推荐：Claude Opus 4 / DeepSeek-R1 / GPT-5（强推理）"
    - **🛠 Modeler（建模师）**：同上，副标题"推荐：Claude Sonnet 4 / GPT-4o / DeepSeek-V3（强工具调用）"
    - **👁 Critic（审图师）**：同上，副标题"推荐：Gemini 2.5 Pro / Qwen-VL-Max / GPT-4o（强视觉理解）"
  - 任一角色 API/模型为空时主循环自动回落到「主 Agent 配置」（顶部那个 API 下拉），保证不影响老用户体验
- **主循环 `agentRunMCPMode` 按 round 切换角色**：
  - **Round 1（Planner）**：system prompt 加 `AGENT_ROLE_PROMPTS.planner`「你是规划师，拆任务、出 plan.md、严禁直接写代码 / 严禁调 add_primitive 等建模工具，必须只调 plan_create + workspace_write_file（写 plan.md）+ mark_done(交接给 Modeler)」
  - **Round 2~N-2（Modeler）**：system prompt 加 `AGENT_ROLE_PROMPTS.modeler`「你是建模师，按 plan.md 一项一项调原子工具实现，每完成一项 plan_update_step」
  - **Round N-1（Critic）**：自动追加 `get_viewport_screenshot` 工具调用，system prompt 加 `AGENT_ROLE_PROMPTS.critic`「你是审图师，对照 plan.md 列出未完成清单 + 写 reflections.jsonl，发现问题就调 reflect()」
  - **Round N（回 Modeler 修复）**：Critic 的反思自动作为新 user message 喂给 Modeler，触发修复轮
- **工具调用历史面板增强**：每条记录前缀加角色 badge `[🧠 Planner]` / `[🛠 Modeler]` / `[👁 Critic]`（彩色背景 chip）。用户能一眼看出"这一步是哪个角色做的、模型选的对不对"
- **AI 看到的工具表总数从 21 → 26**（CLIENT_TOOLS 5 + WORKSPACE_TOOLS 5 + Blender 16）
- **角色配置持久化**：localStorage 字段 `agentState_v184.multiRole`，新老用户切换无缝

### Added · 📚 Phase C bpy API 实时检索 cheatsheet（1 工具 + 192 条精选条目 + 3 个 HTTP 端点）⭐

> 治痛点：用户反复踩 Blender 4.x/5.x API 改名陷阱 —— Round 22 `enum "NISHITA" not found`（Sky vs VolumeScatter 混用）、Round 13 `vertex_only=True is invalid`（4.2+ 移除）、Round 7 `'NoneType' object has no attribute 'inputs'`（Principled BSDF 未启用 use_nodes）……这些坑虽然在 v1.11.9~v1.11.14 已经在 system prompt 里堆了 6 段反踩坑速查，但 prompt 越长 AI 注意力越分散，新坑发现得越多需要的 prompt 越臃肿。Phase C 把这些 API 知识从 prompt 里抽出来变成**可被 AI 主动查询的 cheatsheet**，根治 prompt 膨胀。

- **`scripts/bpy-cheatsheet.json`**：手动维护的 192 条精选 bpy / bmesh / Geometry Nodes API 条目（version 1.0.0，blender_target 4.2+/5.x），覆盖 29 个类别：
  - **modifier 28 条**（bevel / array / mirror / subsurf / solidify / boolean / displace / lattice / wave / ocean / cloth / shrinkwrap / smooth / decimate / multires / particle / weld / weighted_normal / edge_split / triangulate / mask / screw / skin / surface_deform / mesh_to_volume / wireframe / cast / build）
  - **shader 35 条**（principled_bsdf / sky-texture / emission / diffuse / glass / refraction / glossy / transparent / volume_scatter / hair / sss / pbr_pipeline 等）
  - **light 6 条**（POINT / SUN / SPOT / AREA / 光源衰减 / shadow_soft_size）
  - **camera 5 条**（perspective / orthographic / panoramic / track_to / depth_of_field）
  - **world 4 条**（hdri / sky_texture / fog / volumetric）
  - **mesh / bmesh / geometry_nodes 共 44 条**（顶点级操作 / inset_individual / spin / extrude_individual / GN 节点树 / DistributePointsOnFaces / InstanceOnPoints / RealizeInstances）
  - **render 9 条**（CYCLES / EEVEE_NEXT / view_settings / Filmic / 视口模式切换）
  - **pitfall 14 条** ⭐（专门收录历史踩过的坑：vertex_only_removed / sky_vs_volume_enum / principled_none / bpy_prop_collection_key / shadow_method_removed / auto_smooth_renamed 等）
  - **其它 47 条**（vertex_group / shape_key / armature / animation / physics / compositor / IO 等）
- **每条 entry 含**：`id`（如 `modifier-bevel`）/ `title` / `category` / `keywords[]`（中/英多关键词支持）/ `code`（可直接 copy 的 Python 片段）/ 可选 `deprecated`（弃用提示）/ 可选 `see_also`（相关条目 ID）
- **3 个 server.js HTTP 端点**（启动时一次性加载到 `_BPY_CHEATSHEET` 全局变量，零延迟搜索）：
  - `GET /api/bpy/search?q=<keyword>&limit=<N>` — 多字段加权打分模糊搜：keywords 完全匹配 +30 / 包含 +18，id 完全匹配 +25 / 包含 +12，title +8，category +14，code +2。返回前 N 条（默认 5，最大 20），按 score 降序
  - `GET /api/bpy/templates` — 列出 Phase E 模板库元数据（详见下方 Phase E）
  - `POST /api/bpy/templates/render` body `{ name, params }` — 渲染 Phase E 模板代码
- **1 个新客户端工具**：
  - `search_bpy_docs({ query, limit? })` — 走 server.js 模糊搜，返回 `{ ok, total, cheatsheet_total, results:[{id,title,category,code,deprecated?,see_also?}], message }`。AI 写 exec_python 前先查正确语法，遇到报错时查反踩坑速查表，比凭记忆稳得多
- **system prompt 决策树升级**：在 MCP system prompt 的「工具选择决策树」第一位强制加上「**不确定 bpy API 怎么写 → `search_bpy_docs(query)`** 优先查 cheatsheet（200 条精选 + 反踩坑）⭐ **写 exec_python 之前一定先搜！**」
- **效果**：原本 system prompt 里堆 6 段反踩坑速查表（坑 1~坑 6 累计 ~3000 tokens）现在可以缩减成"遇到不确定的就调 search_bpy_docs"一句话指引（~200 tokens），AI 调一次 search_bpy_docs 拿到的 5 条 entry 总 token < 1500，**节省 80%+ system prompt 配额留给具体场景描述**
- **端到端测试**：bevel / sky_type / NISHITA / vertex_only / 花瓶（中文）/ NoneType 等典型查询 7/7 全过（详见 `/tmp/_test_phaseCE.js`）

### Added · 🎨 Phase E bmesh / Geometry Nodes 模板库（2 工具 + 10 个常用模板 + Mustache 参数渲染器）⭐

> 治痛点：AI 写 exec_python 建复杂家具/装饰时经常翻车 —— 沙发只会拼一个 cube、椅子腿长不对、花瓶用 cube 拉伸出来不像车削件、盆栽的叶子不知道用 Geometry Nodes 散布。本来 v1.7.3 的 `AGENT_GEOMETRY_MASTERCLASS` 在 prompt 里堆了 5 大武器（装配/Subsurf/Array/bmesh/GN）但 AI 看 prompt 写代码总是变形走样。Phase E 把这些建模套路变成**预制模板 + 参数化渲染**，AI 一行调用就拿到经过验证的完整 bpy 脚本，比自己写稳得多。

- **`scripts/bmesh-templates.json`**：10 个常用模板（version 1.0.0，blender_target 4.2+/5.x），每个模板都是【完整可执行 bpy 脚本，参数槽用 `{{var}}` Mustache 占位 + 可选 `{{var|json}}` 修饰】，Python AST 语法校验 10/10 全过：
  - **furniture 类 4 个**：
    - `sofa_3seater`（5 部件装配 + Bevel + Subsurf · 7 参数）— 底座 + 靠背 + 左右扶手 + 3 个坐垫，整体 Empty parent
    - `dining_chair`（5 部件 · 7 参数）— 座面 + 靠背 + 4 椅腿
    - `coffee_table_round`（桌面 + 1 桌腿×Array(4) + Empty offset 旋转 90° · 6 参数）
    - `bookshelf_array`（侧板×2 + 顶/底封板 + 隔板 Array(N) · 8 参数）
  - **decor 类 5 个**：
    - `vase_spin`（bmesh.spin 360° 车削旋转 · 7 参数）— 剖面 24 采样点，可控腰部最大半径 + 颈部缩放
    - `cup_inset`（圆柱 + bmesh.inset_individual 挖空 + Subsurf · 6 参数）
    - `plant_geonode`（Geometry Nodes 程序化叶子散布 · 7 参数）— DistributePointsOnFaces + InstanceOnPoints + 随机 rotation/scale
    - `pillow_subsurf`（Cube + Subsurf level=4 软包 · 6 参数）
    - `frame_bevel`（4 边外框 + 1 画面 plane + 可选贴图路径 · 9 参数）
  - **architecture 类 1 个**：
    - `wall_solidify`（Plane + Solidify 加厚 + Bevel · 7 参数）— 支持 X/Y 朝向切换
- **每个模板含**：`name` / `title` / `category` / `description` / `params:[{name,type,default,description}]` / `code`（含 `{{var}}` 占位的 bpy 脚本）
- **server.js Mustache 模板渲染器**（`_renderTemplateCode(tpl, params)`）：
  - 先按 `params` schema 用 `default` 兜底缺失参数
  - 再正则替换 `{{var|json}}` → `JSON.stringify(value)`（数组/对象/字符串都自动加引号）
  - 然后替换无修饰 `{{var}}`：number 直传、boolean 转 `True/False`、string 自动 `JSON.stringify` 加双引号（safe Python literal）、其它走 JSON 序列化
  - 容错：未提供的参数渲染为 `None`/`0`/兜底值，不会留残留占位符
- **2 个新客户端工具**：
  - `list_templates()` — 列出 10 个模板的元数据（params + default + description），不含 code body 省 token。AI 建家具前先调一次看哪个最贴合
  - `apply_template({ name, params, dry_run?, blender_url? })` — 一键应用：① server 渲染参数到模板代码 ② 写一份脚本副本到 workspace（`templates/{name}_{timestamp}.py`，用户能在 Finder 看到）③ `dry_run=true` 只渲染代码不推送（让 Critic 审 code）④ 默认通过 MCP 网关 → `exec_python` 推到 Blender 执行
- **system prompt 决策树升级**：建家具/装饰场景的决策顺序变成：① 写实需求 → `search_polyhaven_assets` → `import_polyhaven_model`；② PolyHaven 没合适 → `list_templates` 看 10 个模板 → `apply_template(name, params)` 一键应用；③ 模板也不够用 → `add_primitive` 手拼；④ 最后兜底 → `exec_python`。**强烈推荐**「bmesh/GN 复杂建模（车削花瓶/挖空杯子/盆栽 GN 散布）→ 优先 apply_template 而不是自己写 exec_python」
- **端到端测试**：10 个模板全部通过 `python3 -m py_compile` 语法校验（无残留占位符、引号/缩进正确）+ render 端点参数透传 + dry_run / default 兜底 / 未知模板 404 / 缺 name 400 等场景 25/25 全过（详见 `/tmp/_test_phaseCE.js`）

### Added · 🛡 Phase F aichat_bridge 插件升级 2.0.4 → 2.1.0（3 端点 + 软回滚机制 ⭐）

> 治痛点：Critic 审图前需要快速摸清场景概览（多少物体/什么集合树/什么渲染设置），但 `get_scene_info` 返回上百物体的完整快照对 token 不友好；Modeler 修复轮一旦把场景越改越烂，没有撤销机制只能让用户手动 Ctrl+Z（远程跨网无法操作）。Phase F 在 Blender 插件层补齐这两个缺口：① 给 Critic 一个 token-friendly overview 端点 `/blend_summary`，② 给主循环一个**软回滚机制**（Modeler 改场景前先 `bookmark_state` 内存快照，Critic 发现改坏了再 `restore_state` 回退到那个状态）。

- **三处版本号同步 bump 2.0.4 → 2.1.0**：`bl_info.version=(2, 1, 0)` / `ADDON_VERSION="2.1.0"` / `REQ_HEADERS UA="aichat-bridge/2.1.0"`
- **3 个新 HTTP 端点 + 3 个 main-thread handler**（注册到 `MCP_MAIN_HANDLERS` 字典，可经 `/mcp/call` 调度也可独立直调）：
  - **`GET /blend_summary`** → `_mcp_blend_summary_main`：返回 token-friendly 场景概览，含 7 大字段：① `blend_file`（filepath / is_saved / is_dirty / size_human）② `object_counts`（total + by_type 按 MESH/LIGHT/CAMERA/EMPTY 分组计数，不返回完整物体列表）③ `collection_tree`（递归树，限制 max_depth=6 防极端嵌套爆栈）④ `render_settings`（engine / resolution / samples / view_transform / exposure / fps / film_transparent 等）⑤ `active_camera` 名 ⑥ `world` 信息 ⑦ 一句话 `summary`（"已保存场景，5 个物体（3 mesh + 1 light + 1 camera），CYCLES 引擎 1920x1080 @ 128 samples"）⑧ 当前内存快照计数 `snapshots_count`/`snapshots_keys` —— 整体 < 2KB，比 `get_scene_info` 的几十 KB 小一个数量级
  - **`POST /bookmark_state`** body `{name}` → `_mcp_bookmark_state_main`：把当前场景以 JSON 形式快照到全局字典 `_BLEND_SNAPSHOTS[name]`，每个物体保存 `transform / parent / material 名 / vertex_count / poly_count / hide_*` 等元数据**但不存** mesh 顶点几何（防爆内存——一个 5 个物体的场景 ~1.3KB，一个 100 物体场景 ~30KB，远小于真 mesh 数据）。空 name 拦截，多 name 累加
  - **`POST /restore_state`** body `{name}` → `_mcp_restore_state_main`：**软回滚**机制——① 删除自快照以来新增的物体（`current - snapshot`）② 还原仍存在物体的 `location/rotation_euler/scale/hide_viewport/hide_render`（`current ∩ snapshot`）③ 还原 `frame_current` 和 `active_camera`（best-effort）④ 已被删的复杂 mesh 几何**无法重建**会列在 `missing` 字段告知。返回里的 `summary` 给 LLM 一句话摘要："已删除 2 个新增物体，恢复 4 个物体 transform，⚠️ 1 个物体已丢失无法重建（Sphere）"
- **`/ping` 端点扩展**：features 数组追加 `"blend_summary", "bookmark_state", "restore_state"`，新增 `snapshots: { count, keys }` 子对象暴露当前内存快照状态，让前端能直接看到累计了几个 bookmark
- **N 面板新增「v2.1.0 Phase F：场景概览 + 软回滚」box**（`RECOVER_LAST` 图标），实时显示当前内存快照计数 + 三个端点路径
- **Preferences 文案更新**：补 v2.1.0 端点说明
- **`blender_addon/README.md` 更新**：API 表格新增 v2.1.0 Phase F 三行，并附**软回滚原理说明**（建议工作流：① Modeler 改场景前先 `bookmark_state` ② Critic 审图发现失败 ③ `restore_state` 软回滚 ④ Modeler 重新尝试，避免越改越烂）
- **重打 `aichat_bridge.zip`：28 KB**（v2.0.4 是 23 KB，因新增 ~250 行代码 + ~5K）
- **端到端测试 5/5 全过**（`/tmp/_test_phaseF.py` mock bpy）：① blend_summary 完整字段验证（含集合树嵌套）② bookmark_state 空 name 拦截 + 内存验证 + 多 key 累加 ③ restore_state 软回滚（删 2 新增 + 还原 4 transform + 1 missing 告知）④ 工具函数边界（`_human_bytes` / `_walk_collection max_depth=6`）⑤ 多版本快照工作流（T1 → T2 加 Chair → T3 改坏 → restore T2 保留 Chair 删 BAD_OBJ → restore T1 也删 Chair）

### Compatibility

- **完全向后兼容**：v1.11.x 用户的 localStorage 数据无任何字段冲突；旧 agentState 没有 plan / workspaceSession / multiRole 字段时会自动初始化为默认值
- `aichat_bridge` 插件 v2.1.0 完全向后兼容 v2.0.x：原 16 个 MCP 工具 + 所有 v1.x HTTP 端点 100% 保留，三个新端点是**纯增量**，老前端不调就完全感知不到。**用户操作**：装 v2.1.0 dmg 后必须在 Blender 里重装一次新 `aichat_bridge.zip`（旧 2.0.4 插件不会因 dmg 升级自动覆盖，否则前端 `agentState.snapshots`/UI 看不到新端点）
- MCP 模式之外（ai-only / polyhaven）完全不受影响
- 多角色协作可被用户**一键关闭**回到单 AI 老模式（顶部勾选框 unchecked）

### Files

- `public/index.html` ~+1000 行（CLIENT_TOOLS 数组扩到 13 个 / _isClientTool / _runClientTool async + workspace + search_bpy_docs + list_templates + apply_template 共 8 个 case / agentPlanRender / agentPlanRenderReflections / AGENT_PLAN_PROMPT 常量 / agentState.workspaceSession + multiRole 字段 / `#agent-plan-panel` + `#agent-workspace-panel` + `#agent-multi-role-panel` 三块 UI 卡片 / 工具历史角色 badge 渲染 / Planner-Modeler-Critic 角色 round 切换主循环 / MCP system prompt 决策树升级加 Phase C+E 新工具引导）
- `server.js` ~+350 行（AICHAT_HOME 计算 + 自动 mkdir + `_resolveSessionPath` 路径穿越拦截 helper + 6 个 `/api/workspace/*` HTTP 端点 + 3 个 `/api/bpy/*` HTTP 端点 + `_loadBpyCheatsheet` + `_loadBmeshTemplates` + `_searchBpyEntries` 加权打分 + `_renderTemplateCode` Mustache 渲染器 + README.md 自动写入）
- `scripts/bpy-cheatsheet.json` 新增（192 条 bpy/bmesh/GN API 精选条目，29 个类别）
- `scripts/bmesh-templates.json` 新增（10 个家具/装饰/建筑模板，含 Mustache 占位符的完整 bpy 代码）
- `package.json` version 1.11.14 → 2.1.0
- `CHANGELOG.md` 本段
- 欢迎弹窗 key `hasLaunched_v1.11.12` → `hasLaunched_v2.1.0`
- `RELEASE_v2.1.0_PHASE_BD.md` 新增（详细 Phase B + D 实施说明 + 验收测试报告）
- `RELEASE_v2.1.0_PHASE_CE.md` 新增（详细 Phase C + E 实施说明 + 验收测试报告 + 用例示范）

---

## [v2.1.0 ROADMAP] · Codex CAD 范式 14 天工程蓝图（Phase A/B/C/D/E/F/G 全部 ✅ 圆满收尾）


> 本段是 v2.1.0 全套工程蓝图占位，让接力会话能完整读到 Phase A~G 的实施计划与最终交付状态。**全部 7 个 Phase 已分多次会话接力实施完毕**，端到端测试 78/78 全过，详见上方 [2.1.0] 段（A~G Added 块）+ 各自 `RELEASE_v2.1.0_PHASE_*.md` 接力索引文档。

### Phase A · Plan-Execute-Reflect 三段循环（2 天）✅ 已完成

- 5 个客户端工具（plan_create / plan_update_step / plan_get / reflect / mark_done）
- 前端 JS 直接执行，0 网络往返毫秒返回
- `agentState.plan` 持久化任务清单 + reflections
- UI 新增 `#agent-plan-panel` 蓝紫色卡片
- AGENT_PLAN_PROMPT 注入 system prompt 末尾强制范式
- mark_done 触发主循环立即 break

### Phase B · 暴露真·文件系统（2 天）✅ 已完成

- `~/Desktop/ai-chat-workspace/` 工作目录 + 时间戳化 session 子目录
- 5 个客户端工具（workspace_create_session / workspace_write_file / workspace_read_file / workspace_list_files / workspace_delete_file）
- server.js 新增 6 个 HTTP 端点（/api/workspace/list-sessions / /root / /create-session / /file/{read,write,list,delete}）
- 路径穿越攻击拦截 + 子目录自动创建 + append jsonl 模式
- UI 新增「📂 v2.1.0 Phase B：AI 工作目录」绿色边框卡片（绝对路径 + 打开按钮 + session 切换 + 历史 session）
- 端到端测试 30/30 全过（详见 `/tmp/_test_phaseB.js` 和上方 `[2.1.0]` 段 Phase B Added 详情）


### Phase C · bpy API 实时检索（1 天）✅ 已完成

- `scripts/bpy-cheatsheet.json` 已落地：192 条精选条目（修订过去 6 段反踩坑速查表 + 涵盖 modifier/shader/light/camera/world/mesh/bmesh/GN/render/pitfall 共 29 个类别）
- 1 个客户端工具 `search_bpy_docs({ query, limit? })`
- 3 个 server.js HTTP 端点：`GET /api/bpy/search` / `GET /api/bpy/templates` / `POST /api/bpy/templates/render`（加权打分模糊搜，启动时一次加载到内存零延迟）
- system prompt 决策树升级：写 exec_python 之前一定先调 search_bpy_docs
- 端到端测试 7/7 全过（bevel / sky_type / NISHITA / vertex_only / 花瓶（中文）/ NoneType）
- 详情见上方 `[2.1.0]` 段 Phase C Added 详情


### Phase D · 多角色专家协作（4 天，核心 ⭐）✅ 已完成

- `agentState.multiRole = { enabled, planner, modeler, critic }` 三角色独立 API + 模型字段
- UI 新增「🎭 v2.1.0 Phase D：多角色专家协作」绿色折叠卡片，默认 enabled=true，三个独立子卡片配 API + 模型下拉 + 推荐模型副标题
- 主循环按 round 切换 system prompt（Planner Round1 / Modeler Round2~N-2 / Critic Round N-1 / Modeler 修复轮 Round N）
- 工具历史面板加角色 badge `[🧠 Planner]` / `[🛠 Modeler]` / `[👁 Critic]`
- 任一角色 API/模型为空时自动回落到主 Agent 配置，保证不破坏老用户体验
- 详情见上方 `[2.1.0]` 段 Phase D Added 详情


### Phase E · bmesh / 几何节点模板库（2 天）✅ 已完成

- `scripts/bmesh-templates.json` 已落地：10 个完整可执行 bpy 模板（furniture 4 + decor 5 + architecture 1），Python AST 语法校验 10/10 全过
- 2 个客户端工具 `apply_template({ name, params, dry_run?, blender_url? })` + `list_templates()`
- server.js Mustache 参数渲染器（`{{var}}` + `{{var|json}}` 修饰），default 兜底缺失参数，自动写副本到 workspace `templates/{name}_{timestamp}.py`
- system prompt 决策树升级：建家具/装饰场景 PolyHaven > 模板 > 手拼 > exec_python 四级 fallback
- 端到端测试 25/25 全过（10 个模板语法校验 + render 参数透传 + dry_run / default 兜底 / 未知模板 404 / 缺 name 400）
- 详情见上方 `[2.1.0]` 段 Phase E Added 详情


### Phase F · aichat_bridge 插件升级 2.0.4 → 2.1.0（1 天）✅

- bl_info `version=(2, 1, 0)` / `ADDON_VERSION="2.1.0"` / `REQ_HEADERS UA="aichat-bridge/2.1.0"` 三处版本号同步 bump
- 新增 3 个 HTTP 端点 + 3 个 main-thread handler + 注册到 MCP_MAIN_HANDLERS：
  - `GET /blend_summary` → `_mcp_blend_summary_main`：返回 token-friendly 场景概览（blend 文件大小/物体总数按 type 分组/集合树/渲染设置/相机/world/一句话 summary）
  - `POST /bookmark_state` → `_mcp_bookmark_state_main`：把当前场景以 JSON 形式快照到 Blender 内存（按 name 索引到 `_BLEND_SNAPSHOTS` 全局字典，**不存** mesh 顶点几何防爆内存）
  - `POST /restore_state` → `_mcp_restore_state_main`：软回滚——删除自快照以来新增的物体（current - snap）+ 还原已存物体的 transform/hide_*（current ∩ snap）+ 还原 frame_current/active_camera。已被删的 mesh 几何无法重建会列在 `missing` 字段告知
- `/ping` features 数组追加 `"blend_summary", "bookmark_state", "restore_state"` + 新增 `snapshots: { count, keys }` 字段，让客户端能看到内存里累计了几个快照
- N 面板新增「v2.1.0 Phase F：场景概览 + 软回滚」box，实时显示快照计数 + 端点路径
- Preferences 文案补 v2.1.0 端点说明
- `blender_addon/README.md` 新增 v2.1.0 端点表格行 + 软回滚原理说明（Modeler→Critic→Modeler 修复轮工作流）
- 重打 `aichat_bridge.zip`：28K（v2.0.4 是 23K，+5K 因新增 ~250 行代码）
- 端到端测试 5/5 全过（`/tmp/_test_phaseF.py` mock bpy）：blend_summary 完整字段验证 / bookmark_state 空 name 拦截 + 内存验证 + 多 key 累加 / restore_state 边界 + 软回滚（删 2 新增 + 还原 4 transform + 1 missing） / `_human_bytes` + `_walk_collection max_depth=6` 工具函数 / 多版本快照工作流（T1→T2→T3 → restore T2 保留 Chair 删 BAD_OBJ → restore T1 也删 Chair）

### Phase G · CHANGELOG + 欢迎弹窗 + README + 打包（1 天）✅

- 欢迎弹窗 key `hasLaunched_v2.1.0`（A 已完成）→ 末次 bump 到 `hasLaunched_v2.1.0_final`（`checkFirstLaunch` + `closeWelcomeModal` 两处同步）✅
- 顶部「当前版本」卡片重写为「v2.1.0 Codex CAD 范式 · Phase A~F 全栈交付」（6 个 Phase 列表带 emoji 标识 + ⚠️ 橙色警示栏要求老用户手动重装 zip）✅
- 历史区开头插「v1.11.0 ~ v1.11.14 MCP Agent 体验级打磨」综合段（9 个 patch 一次性归档）✅
- README.md 第 1 章重写为「v2.1 Codex CAD 范式」六维 Phase 表格 + 版本历程速览顶部新增 v2.1.0 / v1.11.x 综合归档行 + 技术栈 `aichat_bridge` 2.0.0 → 2.1.0 + 致谢区新增 LangGraph / Anthropic Computer Use / Claude Code / Codex CAD 范式参考来源 ✅
- 重打 4 个 dmg/exe（mac arm64+x64、win arm64+x64），全部含 28K 新 `aichat_bridge.zip` extraResources ✅
- 详情见上方 [2.1.0] 段「Added · 📦 Phase G」以及 `RELEASE_v2.1.0_PHASE_G.md`

### 🎉 v2.1.0 Codex CAD 范式重构圆满收尾

总工具数：v1.10.0 的 16 个 Blender 原子工具 → v2.1.0 **29 个**（+5 plan + 5 workspace + 1 search_bpy_docs + 2 templates = +13 客户端工具）

总改动文件：4 个核心源（`public/index.html` / `server.js` / `blender_addon/aichat_bridge/__init__.py` / `package.json`）+ 2 个 JSON 知识库（`scripts/bpy-cheatsheet.json` 192 条 / `scripts/bmesh-templates.json` 10 模板）+ 5 个 RELEASE_v2.1.0_PHASE_*.md 接力索引（A / BD / CE / F / G）+ CHANGELOG.md + README.md + blender_addon/README.md + aichat_bridge.zip 23K → 28K

端到端测试通过：Phase A 5/5 + Phase B 30/30 + Phase C 7/7 + Phase D 6/6 + Phase E 25/25 + Phase F 5/5 = **78/78 全过 ✅**

### 🚧 下一个 Minor 版本（v2.2.0 暂定）方向探索

> 留给后续会话决策，本次 v2.1.0 全栈不再扩张：

1. **Phase H · Long-running session 持久化**：`agentState` 序列化到 `~/Desktop/ai-chat-workspace/.session_state.json`，跨会话续跑无需用户手动恢复
2. **Phase I · Critic 多次审图迭代**：单次 critic 不够时支持 2~3 轮 Modeler ↔ Critic 来回，直到 reflections 收敛
3. **Phase J · 模板库扩展**：从 10 个 → 30 个（覆盖更多家具/电器/植物类别），社区贡献的模板可作为 plugin 集成



---

## [1.11.14] - 2026-05-18 · MCP system prompt 加坑 6（enum 速查表）+ 强化坑 1（exec_python 必传 code）


> v1.11.13 dmg 发出后又遇到 2 个用户实测错误：① Round 22 报 `bpy_struct: item.attr = val: enum "NISHITA" not found in ('SINGLE_SCATTERING', 'MULTIPLE_SCATTERING', 'PREETHAM', 'HOSEK_WILKIE')` —— AI 把 Sky Texture 的 `sky_type='NISHITA'` 错填到 Volume Scatter 的 `phase_function`；② Round 29 反复传 `args: {}` 报 `empty code` —— prompt 里坑 1 的警告对 Claude 4.7 / GPT-5 等模型仍不够强。本版集中治这俩痛点。

### Changed · 🩹 MCP system prompt 新增「坑 6：常见 Blender enum 值混用」+ 7 类速查表

- 用户实测发现 Blender 5.x 里 AI 经常把不同 socket 的 enum 值错配（NISHITA 是 ShaderNodeTexSky 的合法值但不是 Volume Scatter 的合法值）
- 新增坑 6 速查表（写明每个常见 socket 的合法 enum 值）：
  | 节点/对象 | 属性 | 合法值 |
  | --- | --- | --- |
  | ShaderNodeTexSky | `sky_type` | `NISHITA / PREETHAM / HOSEK_WILKIE` |
  | ShaderNodeVolumeScatter | `phase_function` | `SINGLE_SCATTERING / MULTIPLE_SCATTERING / PREETHAM / HOSEK_WILKIE` |
  | Light | `type` | `POINT / SUN / SPOT / AREA` |
  | AreaLight | `shape` | `SQUARE / DISK / RECTANGLE / ELLIPSE` |
  | BSDF | `distribution` | `GGX / MULTI_GGX / BECKMANN / SHARP` |
  | Camera | `type` | `PERSP / ORTHO / PANO` |
  | Render | `engine` | `CYCLES / BLENDER_EEVEE_NEXT (4.2+) / BLENDER_EEVEE` |
- **总原则**：「不确定 enum 值时先用 `get_object_info` 读出现有值看一眼，或直接调原子工具（add_light/set_material 已经替你包好了枚举值校验）。**严禁拍脑袋猜大写下划线词作为 enum 值**」
- 现在 prompt 共 6 个坑速查（exec_python / Principled BSDF / bpy_prop_collection / set_material 优先 / operator 关键字变更 / **enum 值混用**）

### Changed · 🩹 强化坑 1（exec_python args 必须带 code）

- 用户实测发现 v1.11.9 的坑 1 警告对 Claude 4.7 等模型仍不够强（Round 22 / Round 29 都翻车，AI 调 `exec_python` 时反复传 `args: {}` 空字典）
- 在坑 6 后追加「⚠️ 重申坑 1（v1.11.14 强化）：exec_python 调用时 args 字典必须带 code 字段」红字段，明确：
  - **绝对禁止：** `exec_python` 的 args 是 `{}` 或 `{"scene_name": "Scene"}`（漏 code）
  - **必须传：** `{"code": "import bpy\\n..."}`，code 字段必须是非空字符串
  - **如果你想"什么都不做就过一轮"：不要调 exec_python**，直接结束本轮文字回复或者改调只读原子工具
  - **如果只是想读场景：改调 `get_scene_info` / `list_objects` / `get_object_info`**
  - **如果只是想改材质/位置：改调 `set_material` / `update_object`**

### Compatibility

- **完全向后兼容**：v1.11.13 用户的 localStorage 数据无任何字段冲突
- `aichat_bridge` 插件版本不变（仍是 2.0.4，本版纯前端 system prompt 调整）
- 欢迎弹窗 key **不**升级（v1.11.14 是修复版本，不弹新弹窗骚扰用户）

---

## [1.11.13] - 2026-05-17 · MCP Agent 网络韧性强化 + Blender 5.x bevel API 警告

> v1.11.12 dmg 首测又遇到 3 个用户实测问题：① Round 19 LLM 调用因为 `getaddrinfo ENOTFOUND ai.comfly.chat`（中转 API DNS 临时不通）整段崩，已重试 2 次仍未恢复 —— 用户已经消耗的 token + 已建好的物体全白费；② Blender 5.x 里 `bpy.ops.mesh.bevel(vertex_only=True)` 反复报 `keyword "vertex_only" is invalid for this operator`（4.2+ 已被移除）；③ `exec_python` 偶发 args 为 `{}` 漏传 code 字段报 `empty code`。本版集中治这三个体感痛点。

### Fixed · 🌐 MCP Agent 单轮 LLM 调用网络韧性提升（重试 2 → 4 + 退避加长）

- `agentRunMCPMode` 主循环里的 `MAX_RETRIES` 常量从 **2 升到 4**，`BACKOFFS_MS` 数组从 `[1000, 3000]` 升到 `[1000, 3000, 8000, 15000]`，共最多等 27s 抗抖窗口
- **覆盖错误类型**：原有 `ECONNRESET / socket hang up / fetch failed / HTTP 5xx` 之外现已显式覆盖 `getaddrinfo ENOTFOUND`（DNS 临时不通） / `ETIMEDOUT` / `ECONNREFUSED` / `upstream` 等
- **不可重试错误**：用户主动 `AbortError` / HTTP 4xx（参数错） / 4 次重试全失败 → 立即抛错到外层
- **效果**：原本「Round 19 因为中转 API 域名解析失败立即整段崩，已消耗的 18 轮 token 和已建的物体全白费」现在变成「黄字告警 + 4 次退避重试（1s → 3s → 8s → 15s）+ 一般 ~30s 内 DNS 恢复后自动续跑」

### Changed · 🩹 MCP system prompt 新增「坑 5：Blender 4.2+ / 5.x operator 关键字变更」

- 用户实测发现 Blender 5.1 里 `bpy.ops.mesh.bevel(vertex_only=True)` 反复报错（v1.11.9 的 4 个坑速查表只覆盖了 `exec_python empty code` / `Principled BSDF None` / `bpy_prop_collection key not found` / `set_material 工具优先`，没覆盖 operator 关键字变更）
- 新增坑 5：
  - **bevel** 的 `vertex_only=True` 已在 Blender 4.2+ **被移除**，必须改用 `affect='VERTICES'` 或 `affect='EDGES'`（默认）
  - **subdivide** 的 `number_cuts=N` 老写法仍可用但推荐 `cuts=N`
  - **总原则**：「不知道 operator 在新版 Blender 里改名了？**用 modifier 替代 operator**」—— modifier API 改动远少于 operator
  - 给出完整的「modifier 写法」示例代码（直接 `mod.affect = 'VERTICES'` 不需要切 edit mode，比 operator 稳）
- 现在 prompt 共有 5 个坑速查（exec_python / Principled BSDF / bpy_prop_collection / set_material / operator 关键字），AI 第一次出错就能查到，不需要靠 Agent 循环慢慢学

### Compatibility

- **完全向后兼容**：v1.11.12 用户的 localStorage 数据无任何字段冲突
- `aichat_bridge` 插件版本不变（仍是 2.0.3，本版纯前端逻辑改动 + system prompt 调整）
- 欢迎弹窗 key **不**升级（v1.11.13 是修复版本，不弹新弹窗骚扰用户）

---

## [1.11.12] - 2026-05-17 · 欢迎弹窗重构：当前版本卡片直接展示 + 老版本全部折叠

> 用户反馈：每次发新版打开 modal 后，过去 30+ 个历史版本的更新条目全堆在一个折叠区里（默认收起），新版本变更点也被裹在里面 —— 用户【打开 modal】之后还得【再点一次"📋 查看版本更新记录"】才能看到新内容，"我都打开 modal 了为什么不直接显示"。本次重构把「当前版本」单独抽出来当主角，老版本扔进可选折叠区。

### Changed · 🎨 欢迎弹窗布局重构（核心改动 ⭐）

- **顶部「✨ 当前版本」卡片**（v1.11.12 起直接展示，不折叠）：
  - 渐变紫色背景 + 边框，明显区别于下方的"次要历史"区域
  - 第一行：版本号 + 一句话核心改动总结
  - 副标题：本次发版的设计意图（「以后每次发新版你打开弹窗只会看到本次更新点……」）
  - 主体：3 条 `<li>` 简明列出本次改动，第一眼看完
- **下方「📜 查看历史版本更新（v2.0 / v1.x 全部历史 · 点击展开）」折叠区**（默认收起）：
  - 容纳过去 30+ 个版本（v2.0 / v1.10.x / v1.9.x / v1.8.x / ... / v1.0.0）的完整变更
  - 想翻历史点一下展开，原嵌套折叠区（v1.6.4 及更早）保持不动

### Changed · 📐 未来发版可维护性

- 在弹窗 HTML 里加了清晰的注释 `============================================================ ⭐ 当前版本卡片 ============================================================`，划分顶部"当前版本"和下方"历史版本"两个区域，下次发版只需要：
  1. 更新顶部「当前版本」卡片内容（版本号 / 一句话总结 / 3 条 `<li>` 改动）
  2. 把上一次的「当前版本」内容挪到下方「📜 历史版本」折叠区开头，作为新的 `<p><strong>历史版本 (vX.Y.Z)：</strong></p>` 段
  3. bump 一次 `localStorage.hasLaunched_vX.Y.Z` key（`checkFirstLaunch` + `closeWelcomeModal` 两处同步），让所有老用户重启后再弹一次新内容
- 避免每次都要塞一大堆历史让用户翻 / 避免本次更新点被埋进过去 30 个版本的注脚里。

### Changed · 🔄 弹窗 key bump

- `localStorage.hasLaunched_v2.0.0` → `localStorage.hasLaunched_v1.11.12`，所有老用户（不管之前看过哪一版的弹窗）重启后都会再弹一次新内容。
- `package.json.version` 1.11.11 → 1.11.12，与弹窗内容对齐。

---

## [1.11.5] - 2026-05-17 · 截图二级修复体感升级：UI 抖动治本 + 多 AI 接力 + 上下文继承

> v1.11.4 dmg 第二次首测：用户报告**两个体感问题**——① 实时视口监测面板每次刷新缩略图时下方的「📸 截图二级修复」按钮会上下抖动，鼠标点不准；② 截图修复阶段强制用主 Agent 同一个 AI（如 GPT-4o）接力，但用户希望换更强的视觉理解模型（如 Claude Sonnet 4 / Opus 4）二次修补，且必须能记住上次主 Agent 跑完的全部场景上下文（建了什么/做过什么调整），不要重新解释一遍场景。

### Fixed · 🩺 实时视口监测面板抖动治本（鼠标终于能稳定点中下面的按钮）

- **根因**：`#agent-viewport-meta` 之前和频率/大小下拉、刷新/全屏按钮挤在同一个 flexbox 里。每次拉到新视口截图后这一行的文字会变（如「📷 600px · 234ms · 第 3 张」→「第 4 张」→「第 50 张」），字符长度增长会让整个 flexbox 重新换行，下面的「📸 截图二级修复」按钮位置就跟着跳。
- **治本方案**：把 `#agent-viewport-meta` 单独提取成一行 `<div>`，关键 CSS 三件套：`height: 18px` 固定行高 + `line-height: 18px` 垂直居中 + `overflow: hidden; white-space: nowrap; text-overflow: ellipsis;` 超长文字裁断不换行。无论文字怎么变都不会撑高这一行，下面所有元素位置稳定。
- 同时把上面的频率/大小下拉、刷新/全屏按钮 `flex-wrap: wrap` 单独成行，跟 meta 完全解耦。

### Added · 🛠 截图二级修复面板新增「修复用 AI」独立配置（多人接力）

- 截图修复面板从【1 个视觉模型下拉】扩展为【两组下拉】：
  - **👁 审图视觉模型 API + 模型**（绿色高亮区，原有功能）：用谁的视觉能力分析画面问题（推荐 Claude / GPT-4o / Gemini / Qwen-VL）
  - **🛠 修复用 AI API + 模型**（粉色高亮区，v1.11.5 新增 ⭐）：用谁的工具调用能力修补场景（必须支持 OpenAI tool calling，推荐 Claude Sonnet 4 / Opus 4 / GPT-4o）
- 两组下拉完全独立：可以「Gemini 2.5 Pro 审图（视觉强）+ Claude Opus 4 修复（推理强）」组合，让擅长不同能力的 AI 各干各的。
- 不填则两个分别继承主 Agent 的 API + 模型（不破坏老用户体验）。
- 后端 `agentRunMCPMode(options)` 新增 `overrideConfigId / overrideModel` 参数，允许临时换 API/模型而不影响主 Agent 配置。
- 修复 `m3dCallLLMTools` 调用时漏用 `useConfigId/useModel` 的 bug（之前 override 配置不生效，永远用 agentState 的全局值）。

### Added · 🧠 二次修图自动继承上次 MCP 完整上下文（不重复解释场景）

- **新字段** `agentState.mcpMessages` / `agentState.mcpTools` / `agentState.mcpBlenderUrl`：每次 MCP Agent 主循环跑完后自动保存完整 messages 历史（含 system + 初始 user + 所有 assistant 的 tool_calls + 所有 tool 返回 result），形成「会话记忆快照」。
- **截图修复时自动 resume**：调 `agentRunMCPMode({ resumeMessages, followupUserText, overrideConfigId, overrideModel })`，跳过原来的 system prompt / 初始 user message 重建步骤，直接续接上次的 messages 数组，把视觉审图清单作为新一轮 user message 追加到末尾。新 AI（哪怕是不同公司的）接手时已经知道：
  - 上次都建了什么物体（地板、沙发、椅子、灯光、相机...）
  - 上次每个工具调用的参数和返回结果（哪些 PolyHaven 资产试过/失败/成功）
  - 上次场景的最终状态（`get_scene_info` 返回的物体列表 + bounding box）
- **直接看视觉清单针对性修补**：新 AI 不需要 `get_scene_info` 重新摸场景，可以直接看视觉模型给的具体问题清单（"沙发应该往左移 0.5m" / "玻璃 Roughness 太高"）调原子工具修复。
- **Token 节省**：避免「重新生成系统 prompt + 重新探活 + 重新解释场景需求」的重复消耗，二次修图通常只需 1~3 轮 LLM 调用就能完成。
- 老主循环（首次启动）行为完全不变（`options.resumeMessages` 为空时走原路径）。
- UI 状态条会区分显示：「🔄 续接上次 MCP 上下文（X 条 messages，模型: Y）…」 vs 普通启动「🛠 Phase 1/3：探活 Blender MCP 端点…」。

### Compatibility

- **完全向后兼容**：v1.11.4 用户的 localStorage `agentState_v184` 数据无任何字段冲突；老用户首次升级到 v1.11.5 后第一次跑主 Agent 才会开始填充 `mcpMessages` 字段，截图修复面板「修复用 AI」下拉默认空（继承主 Agent 配置），UI 表现与 v1.11.4 完全一致。
- aichat_bridge 插件版本不变（仍是 2.0.3，本版纯前端逻辑改动）。
- 欢迎弹窗 key 不升级（v1.11.5 是修复版本，不弹新弹窗骚扰用户）。

---

## [1.11.4] - 2026-05-17 · 双 hotfix：exec_python NameError 修复 + 截图二级修复面板


> v1.11.3 dmg 首测立刻又遇到两个新问题：① MCP 模式下 LLM 写代码用 `mathutils.Vector` 报 `NameError: name 'mathutils' is not defined`（一段就崩，AI 不知道该自己 import）② 用户希望"渲染完截图发给视觉 AI，让它分析问题再喂回主建模 AI 二次修复"。本版同时治掉。

### Fixed

- **Bug A · `exec_python` namespace 预置常用模块（aichat_bridge 2.0.2 → 2.0.3）**：
  - `_mcp_exec_python_main` 和 `_drain_queue("exec")` 两处 `globs` 字典预置 `math / mathutils / bmesh` + `Vector / Matrix / Euler / Quaternion / Color`，让 LLM 写代码时直接 `mathutils.Vector(...)`、`bmesh.new()`、`from mathutils import Vector` 全部能用，不再炸 NameError。
  - 同时治用户报的 `'Material' object has no attribute 'shadow_method'`（这个是 Blender 4.2+ 移除的属性，由 Agent 下轮重试自然修复，不在本版处理范围）。
  - 实际错误现场：
    - `args: {"code":"...\\nimport bpy\\nimport math\\n\\ncam = bpy.data.objects.get('MainCamera')\\nif cam:\\n  # ...\\n"}` 后面用了 `mathutils.Vector` 但没 import → `NameError: name 'mathutils' is not defined`
    - 本版让插件预先注入，LLM 不需要每次都自己 import。

### Added · 📸 截图二级修复面板（MCP 模式专用）

- **新面板 `#agent-screenshot-fix-panel`**（粉色边框，仅 MCP 模式进入后显示）：
  - **审图 API/模型独立可选**：用户可以拿一个专门的视觉模型（Claude / GPT-4o / Gemini / Qwen-VL）审图，主建模 AI 可以是不擅长视觉的 DeepSeek-V3 / Qwen-Max。
  - **一键流程**：① 拉 `GET /viewport_screenshot?max_size=1200` 真实视口截图 → ② 把 base64 + 原 sceneDescription 喂给视觉模型，让它输出【问题清单 + 修复建议】（不允许"看起来不错"空话）→ ③ 把清单作为新的 sceneDescription 喂回主 MCP Agent，触发 `agentRunMCPMode()` 重跑（主 AI 调原子工具 `update_object / set_material / add_light / delete_object` 等修复）→ ④ 完成后自动还原原始 sceneDescription。
  - **错误处理**：视觉模型返回过短（<20 字）→ 提示"可能不支持图像输入"；截图字段名兼容 base64/data/image/b64（沿用 v1.11.2 的 aichat_bridge 兼容层）。
  - **UI**：折叠的"上次审图结果"展开看完整清单；状态栏实时显示 ①/②/③ 三个阶段。

### Changed

- `package.json` version 1.11.3 → 1.11.4
- `blender_addon/aichat_bridge/__init__.py` ADDON_VERSION 2.0.2 → 2.0.3 + bl_info.version + REQ_HEADERS UA 三处同步
- `public/index.html` MCP 模式启动时同时显示历史面板 + 截图修复面板（之前只显示历史面板）

### Files Touched

- `blender_addon/aichat_bridge/__init__.py`（namespace 预置 + 版本字段 + UA，~30 行）
- `public/index.html`（截图修复面板 HTML + 4 个新 JS 函数 + MCP 启动时显示面板，~180 行）
- `package.json` + `CHANGELOG.md`

### 用户操作

- 装 1.11.4 dmg 后必须在 Blender 里【重装一次新 aichat_bridge.zip】（旧 2.0.2 插件不会因 dmg 升级自动覆盖，否则 exec_python NameError 不修复）。

---

## [1.11.3] - 2026-05-17 · 视口监测内存修复（得到下一张就删上一张）

> 用户反馈："不要保存图片，得到下一张就删除上一张"。v1.11.2 保留最近 12 张 48×36 缩略图本意是回看演变过程，但长任务跑 1~3 小时后会堆 100+ 张 base64（每张 ~50KB）撑爆浏览器内存导致整页崩。本版彻底取消历史缓存，内存常驻仅 1 张。

### Fixed

- **`agentViewportRefreshNow` 内存释放 + 强制清零 history**：
  - 每次拉到新 base64 之前，先 `imgEl.src = ''` 显式断开旧 dataUrl 的 DOM 引用（不这么做的话 Chrome 会保留上一张直到 GC 触发，常驻几 MB）。
  - 拉完新图后 `agentState.viewportMonitor.history.length = 0` 强制清零数组，即使老 localStorage 残留 history 也会在第一次刷新后被清掉（向前兼容）。
- **`#agent-viewport-history` 容器 display:none**：把原本显示 12 张缩略图的 div 整个隐藏（保留空 div 仅为兼容旧 JS 调用点不报错）。
- **`agentViewportRenderHistory` 改为空壳函数**：每次调用都把 history 数组 + DOM innerHTML 清零，再无任何渲染逻辑。
- **效果**：连续轮询 1000+ 张后浏览器内存占用稳定在 < 100KB（当前显示的一张），不再随时间增长。

### Changed

- `package.json` version 1.11.2 → 1.11.3
- `public/index.html` 3 处改动（HTML div 隐藏 + refresh src 释放 + render 空壳）

### Files Touched

- `public/index.html`（~15 行）
- `package.json` + `CHANGELOG.md`

---

## [1.11.2] - 2026-05-17 · 双 hotfix：MCP ECONNRESET 重试 + 视口监测字段名修复（aichat_bridge 2.0.2）

> v1.11.1 dmg 首测立刻又遇到两个 P0 bug，本版同时治掉。

### Fixed

- **Bug 1 · MCP Agent Round N 报 `read ECONNRESET` 整段崩 → 重试机制**：
  - `agentRunMCPMode` 主循环里给单轮 `m3dCallLLMTools` 调用包了一层 try-catch + 指数退避重试（1s / 3s），最多 2 次。
  - **可重试错误关键词识别**：`ECONNRESET / socket hang up / ECONNREFUSED / ETIMEDOUT / ENOTFOUND / fetch failed / network / timeout / HTTP 5xx / upstream / connection` 任一命中 → 退避后重试。
  - **不可重试错误**：`AbortError`（用户主动中止）立即跳出；HTTP 4xx 不重试。
  - **失败传播**：重试全失败才抛错到外层，错误信息包含「已重试 N 次仍未恢复」让用户明白。
  - UI 体感：原本"Round 4 红字立即整段崩"现在变成黄字告警 + 自动重试动画 + 一般 1~3s 后恢复继续。

- **Bug 2 · 视口监测面板「❌ 返回未含 base64 数据」→ aichat_bridge 2.0.2 字段名兼容**：
  - 根因：`_capture_viewport_screenshot_main` 只输出 `{ok, base64, format, width, height, bytes}`，但前端 `viewportMonitor.tick()` 读 `data.data || data.image || data.b64` 三个字段全部 undefined → 抛错。
  - 改插件 `aichat_bridge/__init__.py` 的 `do_GET /viewport_screenshot` 和 `do_POST /viewport_screenshot` 两处路由：返回时把 `base64` 字段同时复制到 `data / image / b64` 三个别名字段（向后 + 向前兼容前端各版本 / 第三方读法）。
  - **bump 插件 ADDON_VERSION 2.0.1 → 2.0.2**（含 `REQ_HEADERS User-Agent` 字符串）+ 重打 `aichat_bridge.zip`。
  - 用户操作：装 1.11.2 dmg 后必须在 Blender 里重装一次新 zip（旧 2.0.1 插件不会因 dmg 升级自动覆盖）。

### Changed

- `package.json` version 1.11.1 → 1.11.2
- `blender_addon/aichat_bridge/__init__.py` ADDON_VERSION + bl_info.version + REQ_HEADERS UA 三处同步到 2.0.2

### Files Touched

- `public/index.html`（`agentRunMCPMode` 主循环重试逻辑，~50 行）
- `blender_addon/aichat_bridge/__init__.py`（GET/POST viewport_screenshot 路由 + 版本字段，~20 行）
- `package.json` + `CHANGELOG.md`

---

## [1.11.1] - 2026-05-17 · MCP 推理模型 reasoning_content 回传修复（治 Qwen3 thinking / DeepSeek-R1 / Claude extended thinking）

> v1.11.0 dmg 用户首测 MCP Agent 模式遇到 `Round 2 LLM 调用失败：The reasoning_content in the thinking mode must be passed back to the API.` 整段崩。

### Fixed

- **`m3dCallLLMTools` return 加 `reasoning_content` 字段** + **本地累加 `reasoning` 变量**：流式 SSE 收到 `data.reasoning` 时累加到 `reasoning` 变量（之前没存，return 时引用 undefined），return `{ content, tool_calls, finish_reason, reasoning_content }` 四元组
- **`agentRunMCPMode` 主循环组装 `assistantMsg` 时塞回 `reasoning_content`**：从 `resp.reasoning_content` 取出，若非空塞进 `messages.push({ role: 'assistant', content, tool_calls, reasoning_content })`，server.js 透传时会带给上游
- **根因**：Qwen3 thinking / DeepSeek-R1 / Claude extended thinking 等推理模型的中转 API 严格要求"上一轮 assistant message 必须包含原 reasoning_content"，否则下一轮 400。之前 v1.11.0 只在 UI 流式回放但没回传给上游，所以 Round 2 必崩

### 用户视角变化

- v1.11.0：`agent-mode-mcp` 配 Qwen3 thinking / R1 → Round 1 通过 → Round 2 红字 400 整段失败
- v1.11.1：同样配置 → 自动回传 reasoning → 多轮工具调用流畅，与 v1.10.x 普通对话模型一致

### 用户操作建议

- v1.10.x 的视口监测 404 是 v1.10.1 已修，装 1.11.1 dmg + Blender 里重装一次 `aichat_bridge.zip`（仍 2.0.1）即可

---

## [1.11.0] - 2026-05-17 · 模型能力检测系统（vision/tools/reasoning 三探 + 持久化彩色 badge）


> 治长期痛点：用户面对几百个模型 ID（GPT / Claude / DeepSeek / Qwen / GLM / Moonshot / Gemini ...）完全分不清谁能看图、谁能 tool calling、谁是推理模型。这版前后端联动加一套真探测 + 彩色 badge 系统，**点一下就知道**。

### Added

#### 🔧 后端 server.js +110 行（两个新端点）

- **`POST /api/configs/:id/test-capability`** body `{model, capability}`：用真实短请求探测某个能力，30s 超时
  - **vision** 探测：发 1×1 透明 png base64 + `"What is in this image?"` → 看 200/4xx
    - 4xx 时识别 `image_url` / `multimodal` / `vision` / `not support` 关键词，明确标记"不支持视觉"
    - 200 且回了文字 → 标记"支持视觉"
  - **tools** 探测：发 `hello_world(name)` 工具 schema + `tool_choice='auto'` + 用户 prompt `"Please call the hello_world tool with name='test'"` → 看 `choices[0].message.tool_calls` 字段
    - 有 tool_calls → 支持；只回文字 → 不支持
  - **reasoning** 探测：发短数学题 `"If a train travels 60km in 30 min, what is its speed in km/h?"` → 看 `message.reasoning_content` / `message.reasoning` 字段
    - 有 reasoning 字段 → 支持；只有 step-by-step 文字 → 标"⚠️ 部分推理特征"；都没有 → 普通对话模型
  - 返回 `{ok, supported, capability, model, took_ms, detail, content_preview, tool_calls_count, reasoning_chars, hint, raw_error}`

- **`PUT /api/configs/:id/model-capabilities`** body `{capabilities: {modelId: {vision: true, vision_at: "2026-05-17 12:34:56", vision_detail: "...", ...}}}`：持久化测试结果到 `config.modelCapabilities`，下次打开弹窗直接展示

#### 🎨 前端筛选弹窗 #model-filter-modal 升级

- **每行模型右侧新增 3 个能力测试按钮**：
  - 👁 紫色 `#8b5cf6` —— 视觉
  - 🛠 黄色 `#f59e0b` —— 工具调用
  - 🧠 粉色 `#ec4899` —— 推理
- **三态彩色 badge**（hover 看 tooltip 详情）：
  - 灰色边框 = 未测过 → 显示提示"点击测视觉/工具/推理：xxx"
  - 彩色填充 = ✅ 支持 → 显示"支持 视觉（测于 2026-05-17 12:34:56）\n详情\n点击重测"
  - 红色 `#ef4444` = ❌ 不支持 → 显示"不支持 视觉（测于 ...）\n详情\n点击重测"
- 点击按钮：⏳ loading 态 → 调 POST /test-capability → 写回 PUT /model-capabilities → 同步前端 `configs[i].modelCapabilities[modelId]` → `renderModelFilterList()` 重渲染该行 badge → 弹 `alert` 摘要（耗时 + 详情前 300 字）
- 排版：从原来的 `<label><checkbox><name></label>` 改成 `<div><label flex:1><checkbox><name></label><div>3 个 badge</div></div>`，彩色 chip 紧贴右侧但不抢点击勾选区

#### 🎨 摄影工具节点能力标注（3 处彩色横幅）

- **Step 2「总结场景」节点**：💬 蓝色横幅「需文本对话模型（如 deepseek-chat / claude / gpt-4o），仅产场景描述文本，不需视觉/图像生成能力」
- **Step 3「生成多角度图」节点**：🎨 黄色横幅「必须选**图像生成模型**！gpt-image-1/2、dall-e-3、flux、kolors、seedream 等。**非**文本对话模型，否则报错」
- **Step 4「演算 bpy 代码」节点**：👁 紫色横幅「强烈推荐**视觉模型**（claude-sonnet-4 / gpt-4o / gemini-2.5-pro / qwen-vl-max）— 跳过 Step 3 时也可以用纯文本模型」

### Fixed（v1.10.x 累计 hotfix）

- **MCP 模式 `deepseek-chat` 多模态 400 修复**（v1.10.3 已带回 1.11.0）：`agentBuildUserContent` 新增 `agentIsNonVisionModel()` helper，识别 `deepseek-chat` / `o1-mini` / `qwen-turbo` / `glm-4-air` / `moonshot-v1-8k` 等纯文本模型，自动剥掉所有 `image_url` 多模态 part，文末追加提示「（注：你选的模型「xxx」不支持视觉模态，N 张参考图已自动剥掉。如需 AI 看图请改选 Claude / GPT-4o / Gemini / Qwen-VL 等视觉模型。）」
- **MCP 模式 DeepSeek 推理模型预检**（v1.10.2 已带回 1.11.0）：`agentRunMCPMode` 入口预检 `deepseek-reasoner` / `deepseek-r1` / `o1-preview` / `o1-mini` / 任何 `-reasoner` / `-thinking-` / `-r1-` 后缀，命中弹窗列出 5 类替代模型
- **server.js `/api/chat` 上游 400 错误透传**（v1.10.2 已带回 1.11.0）：catch 块异步收齐 stream Buffer → JSON.parse → 抠出 `j.error.message` 透传给前端

### Changed

- `package.json` `1.10.3 → 1.11.0`（minor 版本：新增模型能力检测功能）
- `欢迎弹窗` checkFirstLaunch key 保持 `hasLaunched_v2.0.0`（不算 breaking，老用户无感）

### 用户价值

- **配 API 即知能力**：以前用户经常拿 `gpt-image-2` 当聊天模型用，或者拿 `deepseek-chat` 当视觉模型用，浪费一次 400 错误才发现。现在弹窗里点一下就知道
- **持久化记忆**：测过一次就一直记着，下次配新模型只需测新加的几个
- **三色 chip 一眼分辨**：彩色填充 = 支持 / 红色 = 不支持 / 灰色 = 没测，看图就够，不用读文档

### 下版规划（v1.11.1+）

- 模型能力检测的"批量测试"按钮（一键测当前可见的全部模型）
- 在外面的「选择模型」下拉框选项后也加 badge 提示

---

## [1.10.3] - 2026-05-17 · 非视觉模型自动剥图（治 deepseek-chat `unknown variant 'image_url'` 400）


> 紧跟 v1.10.2 错误透传修复后立刻暴露的第 2 个 bug：用户改成 `deepseek-chat` 后报错变成 `Failed to deserialize the JSON body into the target type: messages[1]: unknown variant 'image_url', expected 'text'`。

### Fixed

- **`agentBuildUserContent` 加非视觉模型识别 + 自动剥图**（约 +25 行）：
  - **根因**：前端 `agentState.referenceImages` 不为空时无脑构造 `[{type:'text'}, {type:'image_url'}, ...]` 多模态数组喂给 LLM，但 DeepSeek 官方 `deepseek-chat` / OpenAI `o1-mini` / Qwen-Turbo / Kimi `moonshot-v1-8k` 等**纯文本模型不支持 image_url 变体**，会立即报 `unknown variant 'image_url', expected 'text'` 400 错误。
  - **修复**：新增 `agentIsNonVisionModel(model)` helper，识别：
    - 明确非视觉白名单：`deepseek-chat` / `deepseek-v3` / `deepseek-r1` / `o1-mini` / `qwen-turbo` / `glm-4-air` / `glm-4-flash` / `moonshot-v1-8k|32k|128k`（非 vision 版）
    - 视觉模型关键词命中（直接放行）：`-vision` / `-vl` / `gpt-4o` / `gpt-4-turbo` / `claude` / `gemini` / `llava` / `qwen-vl` / `cogvlm` / `internvl` / `doubao-vision` / `moonshot-v1-vision`
    - 兜底：未知模型保守按"非视觉"处理（避免把图发给不认识的模型炸 400）
  - 命中非视觉模型时 `agentBuildUserContent` 自动剥掉所有图片，在文本末尾追加提示：「（注：你选的模型「xxx」不支持视觉模态，N 张参考图已自动剥掉。如需 AI 看图请改选 Claude / GPT-4o / Gemini / Qwen-VL 等视觉模型。）」
  - 控制台同步 `console.warn` 一行，便于排查

### Changed

- `package.json` `1.10.2 → 1.10.3`。

### 用户体验提升路径

- v1.10.1：插件 GET /viewport_screenshot 路由补回
- v1.10.2：上游 400 真实原因终于能透传给用户（不再是光秃秃 `Request failed with status code 400`）
- v1.10.3：**根据上游真实原因「unknown variant 'image_url'」自动修**（非视觉模型剥图）

三次 hotfix 接力，把用户从 v1.10.0 首测发现的 3 个连环坑全部填平。

---

## [1.10.2] - 2026-05-17 · 上游 400 错误信息透传 + DeepSeek 推理模型预检

> 紧跟 v1.10.1，治用户用 DeepSeek 官方 `deepseek-reasoner` 跑 MCP Agent 模式时只看到光秃秃 `Request failed with status code 400`、看不出真正原因的问题。

### Fixed

- **`server.js /api/chat` catch 块根因修复：上游 4xx/5xx 时 axios `responseType:'stream'` 的 `err.response.data` 是 Stream 对象**（不是已解析 JSON），原代码 `err.response?.data?.error?.message` 永远拿到 `undefined` → 退到光秃秃的 `err.message`（即 axios 默认的 `Request failed with status code 400`）。
  - **修复**：异步把 stream Buffer 收齐（500ms 防卡死兜底）→ 尝试 JSON.parse → 抠出真正的 `j.error.message`，并把 `upstream_status` 和原始片段一并 SSE 透传给前端。
  - **效果**：用户现在能看到上游真实原因，例如 DeepSeek 官方 API 的「`deepseek-reasoner` does not support tool_calls」/ Anthropic 的「max_tokens too small」/ 中转 API 的「insufficient quota」等具体错误。

### Added

- **前端 `agentRunMCPMode` 入口预检不支持 tool calling 的模型**（约 30 行）：
  - 已知不支持的：DeepSeek 官方的 `deepseek-reasoner` / `deepseek-r1`、OpenAI 官方的 `o1-preview` / `o1-mini`、任何带 `-reasoner` / `-thinking-` / `-r1-` 后缀的纯推理变体
  - 命中预警弹窗会列出 5 类替代模型（`deepseek-chat` / Claude Sonnet 4 / GPT-4o / Gemini 2.5 Pro / Qwen-Max），点确定可强行尝试，点取消阻止启动
  - 也在用户 catch 到 400 错误后能立刻知道根因（不用再翻 server.js 控制台日志）

### Changed

- `package.json` `1.10.1 → 1.10.2`（仅 server.js 一处修复 + 前端 1 处入口预检，无版本号位升级到 1.11，仍是 v1.10 系列 hotfix）。

### 影响范围

- 仅修 `/api/chat` 错误透传 + MCP 模式入口预检，不影响其他路径（一键 3D / PolyHaven / 普通对话 / 工作流 / 思维导图）。
- 老 caller 完全无感（`upstream_status` 和 `upstream_raw` 是新增字段，前端不读不报错）。

---

## [1.10.1] - 2026-05-17 · v2.0 双架构 dmg 首测 hotfix

> 紧跟 v1.10.0 的 macOS 双架构 dmg 安装包测试反馈。

### Fixed

- **Blender 插件 v2.0.1：补回 `GET /viewport_screenshot` 路由**（v1.9.7 实时视口监测面板首测时报 `❌ HTTP 404`）。
  - **根因**：v2.0.0 重写 HTTP handler 时 `/viewport_screenshot` 端点只在 `do_POST` 注册了，但前端 v1.9.7 `agentViewportRefreshNow()` 用的是 `GET /viewport_screenshot?max_size=600`，路由不匹配落到 `do_GET` 末尾的 404 兜底。
  - **修复**：`do_GET` 加 `if self.path.startswith("/viewport_screenshot")` 分支，解析 query string 里的 `max_size`，复用主线程 `_post_to_main("screenshot", ...)`。GET / POST 两条路径返回结构完全一致。
  - **影响范围**：仅修视口监测面板。MCP `get_viewport_screenshot` 工具走 `/mcp/call`，不受此 bug 影响。

### Changed

- `bl_info` `version` `(2, 0, 0) → (2, 0, 1)` + `ADDON_VERSION = "2.0.1"` + `REQ_HEADERS` UA 同步 bump。
- `package.json` `1.10.0 → 1.10.1`。

### 已知正常现象（非 bug）

- 测试中观察到 MCP Agent 多轮 tool_call 里 `exec_python` 单步报错 `bpy_prop_collection[key]: key "Background" not found`：这是 LLM 调 `nodes["Background"]` 但 World 的 shader nodes 还没启用 `use_nodes` 时的 KeyError，**属于 Agent 循环的预期错误反馈**——下一轮 LLM 拿到 traceback 会自动换策略（先建 Background node 或先 `use_nodes=True`）。这正是 Agent 模式相比一键 3D 的核心价值：单步失败不致命，自我纠错。

### 双架构 dmg 重打验证

- ✅ `白歌的AI讨论组-1.10.1-arm64.dmg` 111 MB
- ✅ `白歌的AI讨论组-1.10.1-x64.dmg` 116 MB
- ✅ 内嵌 `aichat_bridge.zip` 已是 2.0.1（`bl_info version=(2,0,1)` + `ADDON_VERSION="2.0.1"` 双重验证）

---


## [1.10.0] - 2026-05-17 — 🛠 MCP Agent 循环正式落地（v2.0 三阶段开发收官）

> **详细完成说明见 [`RELEASE_v2.0_PHASE3.md`](./RELEASE_v2.0_PHASE3.md)。**
> 🎉 **v2.0 Phase 3 / 3 完成**：v1.9.6 起规划的「MCP 标准协议 + LLM tool calling 多轮循环」三阶段开发全部交付（Phase 1 插件 4 天 / Phase 2 网关 1 天 / Phase 3 前端 3 天 = 共 8~9 天），与原 ROADMAP 估时一致
> ✅ **完全向后兼容**：v1.9.7 老用户的「⚡ AI 从零生成」「🎨 PolyHaven 网络资产」两种模式继续 100% 工作；MCP 模式是**第 3 种新增 radio 选项**，不会顶替任何旧功能；只要不勾 mcp radio 就不需要升级插件
> ⚠️ **使用 MCP 模式需要**：Blender 端 `aichat_bridge` 升级到 2.0.0+（Phase 1 已发版，桌面端「📥 一键导出插件 zip」即可）+ 推荐用 Claude Sonnet/Opus 4 / GPT-4o / Gemini 2.5 等支持原生 OpenAI tool calling 的模型

### 🆕 新增 (Added)
- **`server.js /api/chat` 透传 OpenAI tool calling**（约 +40 行）：
  - 请求体新增 `tools` / `tool_choice` 字段透传给上游 LLM API
  - 入参白名单：只接受 `{type:'function', function:{name, parameters}}` 结构的工具；非合法工具会被静默过滤而不是抛错（防止单个坏工具炸整批）
  - `tool_choice` 默认 `'auto'`（让 LLM 自主决定），可指定 `'none'`/`'required'`/`{type:'function', function:{name}}` 强制选某工具
  - SSE 转发新增两个事件类型：
    - `data: {tool_calls: [{index, id, type, function:{name, arguments}}]}` —— 流式 delta（arguments 是字符串增量，前端按 index 累加拼接）
    - `data: {finish_reason: 'stop'|'tool_calls'|'length'|'content_filter'}` —— 让前端 Agent 循环判断本轮该停还是继续调工具
  - 向后兼容：任一关键字段缺失就完全不透传（老 caller 一键3D / 普通聊天 / 工作流 不需要 tools 完全不受影响）

- **前端 `m3dCallLLMTools()` 函数**（约 +90 行）：
  - 专用于 tools 流式累加的 LLM 调用 helper（与现有 `m3dCallLLM` 并列，不替换它）
  - 按 `data.tool_calls[].index` 累加 `function.arguments`（OpenAI 流式协议要求字符串拼接）
  - 返回 `{ content, tool_calls: [{id, type:'function', function:{name, arguments}}], finish_reason }` 三元组
  - 同时支持 `onReasoning` / `onContent` 回调（推理模型 thinking + 普通 content 都能流式回放给前端 UI）

- **`agentRunMCPMode()` MCP Agent 主循环**（约 +180 行，核心机制）：
  - **Phase 1：探活** —— 调 `GET /api/mcp/ping?url=<bridge>` 确认 Blender 端 `aichat_bridge` 2.0.0+，老插件会得到 `mcp_ready=false + upgrade_hint`，直接告诉用户怎么升插件
  - **Phase 2：拉工具 schema** —— 调 `GET /api/mcp/tools?url=<bridge>` 拿 16 个 OpenAI tools 格式定义，缓存到 messages 喂给 LLM
  - **Phase 3：主循环** —— 最多 30 轮 LLM 调用（防失控）：
    - 每轮调 `m3dCallLLMTools(...)` 让 LLM 输出 tool_calls
    - 解析每个 tool_call，并行调 `POST /api/mcp/call` 到 server.js 网关 → Blender 端执行
    - 把工具结果以 `{role:'tool', tool_call_id, content}` 加入 messages 历史
    - 长操作（`import_polyhaven_model` / `set_world_hdri` / `exec_python`）超时 300s，其他 60s
    - 视口截图特殊处理：`get_viewport_screenshot` 返回的 base64 太大不直接塞回 LLM（防 token 爆），给文字摘要 `{_viewport_image_b64_len: N, _note: '...'}`
    - LLM 不输出 tool_calls + 输出文字 → 视为最终总结，循环结束

- **核心 System Prompt**（≈80 行设计精华）：
  - **6 条核心工作范式**：每步先观察 → PolyHaven 必须先搜后下 → 小步迭代每次 1~3 步 → 单步失败立刻换策略 → 完成判定明确（只输出文字就结束）
  - **6 项场景质量硬性要求**：≥6 物体 / ≥3 灯光 / 1 台朝向场景中心的相机 / World 必须设 / 物体贴地不穿模
  - **工具选择决策树**：8 类操作分别对应哪个工具（看场景/简单几何/灯光/相机/写实资产/修改/删/兜底）
  - **4 条严禁**：编造 asset_id / 大段 bpy 代码 / 跳过观察 / final summary 里继续调工具

- **🛠 工具调用历史面板**（智能 Agent UI 内，紫色边框）：
  - 默认隐藏，进入 MCP 模式时显示
  - 每次工具调用一行 `<details>` 折叠条目，带 `✅/❌` 状态图标 + `<code>` 标记工具名 + 用时（ms）+ 结果摘要单行预览（自动抠出 result 关键字段）
  - 展开后可看完整 `args` JSON 和 `result` pre 块（截断到 1500 字符防 DOM 爆）
  - 边框颜色按 ok/error 状态绿/红区分；按调用顺序编号 `#1 #2 #3...`
  - 只渲染最近 50 条（防止长任务 200+ 调用把 DOM 撑爆）
  - 「🗑 清空」按钮清空历史

- **UI 第 3 个生成模式 radio**：智能 Agent 实时渲染「🎨 生成方式」面板从 2 选 1（AI 从零 / PolyHaven）扩展为 3 选 1，新增「🛠 MCP Agent 循环」紫色背景高亮，明确标 `v2.0 实验性 🆕`

### 🔄 修改 (Changed)
- `agentStartRun` 主分发函数加 `mcp` 分支：在 `polyhaven` 之后、`hyper3d`/`none`/`final`/`incremental` 之前
- `agentState` 加 `mcpHistory` 字段（运行时数组，不持久化到 localStorage 避免长会话爆 quota）
- 工具历史面板 3 个辅助函数：`agentMCPClearHistory` / `agentMCPAppendHistory`（追加单条 + 触发渲染）/ `agentMCPRenderHistory`（最近 50 条增量渲染 + 自动滚到底）

### 📊 数据变更
- `package.json` 1.9.7 → **1.10.0**（首次进入 1.10.x 系列，v2.0 三阶段实质完成，但还差用户验证 + 打包发版才正式 bump 到 2.0.0）
- 网关层 4 个 `/api/mcp/*` 端点已就绪（Phase 2），现在前端真的开始用了

### 📋 兼容性
- **零破坏**：所有 v1.x 端点 / 老 radio 选项 / 工作流 / 思维导图 / 普通对话 / 一键3D 流水线**完全不动**
- **零新依赖**：纯前端 + server.js 增量改造，无 npm install 需要
- **MCP 模式硬依赖**：`aichat_bridge` ≥ 2.0.0（Phase 1 已发，桌面有 zip）+ 推荐 Claude Sonnet 4 / GPT-4o / Gemini 2.5 Pro 这种原生支持 tool calling 的模型；老插件 1.x.x 用户会得到友好的升级提示（不会无声崩）

### 🚧 下一步（v2.0.0 正式发版前）
- 端到端测试：跑 3~5 个典型场景（客厅 / 摄影棚 / 户外日落）确认完整 Agent 循环能跑通
- ~~重写「欢迎弹窗」最新版块：把 v1.9.x 视口监测 + v1.10.0 MCP Agent 两个大特性合并写~~ ✅ **已完成**（`hasLaunched_v2.0.0` key + 综合版块插入到弹窗顶部 + v1.9.3~v1.9.6 累计修复条目）
- ~~README 重写为 v2.0 版（把 MCP Agent 列为头号卖点）~~ ✅ **已完成**（含 3 种生成模式对比表 + 完整功能矩阵 + 版本历程速览 + 使用步骤）
- `electron-builder` 打 macOS arm64 + Windows x64 dmg/exe，发到 GitHub Releases
- 录一个 ~60s 演示视频塞 README：用户说一句话 → 看着 LLM 一个工具一个工具调，场景一点点冒出来

---

## [1.9.7] - 2026-05-17 — 📺 实时视口监测小窗

> ✅ **完全向后兼容 v1.9.6**：`aichat_bridge` 1.1.0+ 即可（无需重装，本特性复用现有 `/viewport_screenshot` 端点）
> 🏗 **下一步**：v2.0 Phase 3 前端 Agent 循环（OpenAI tool calling 多轮 MCP）

### 🆕 新增 (Added)
- **📺 实时视口监测小窗**（智能 Agent 实时渲染模块内，所有生成模式可用）：
  - 折叠面板 `<details id="agent-viewport-panel">`，**默认收起避免无谓带宽消耗**；展开后启动 `setInterval` 轮询 Blender `/viewport_screenshot` 端点
  - **频率档位**：1s（密）/ 3s（默认）/ 5s / 10s（省）—— 用户可下拉切换，立即生效
  - **分辨率档位**：400px / 600px（默认）/ 800px —— 通过 `max_size` 参数传给 Blender 端，控制单次拉取大小
  - **防并发标记** `_agentViewportFetching`：上次请求还没回来就跳过这次，避免堆积导致 Blender 卡顿
  - **历史缩略图回看**：保留最近 12 张（每张 48×36px 缩略图），点击任意一张瞬间切到主预览区，用户能"看 Blender 是怎么一步步长出来的"
  - **大图预览**：点击主预览图调用现有 `showImageModal()` 显示原图，最大 3840×2160 适配 4K 屏
  - **状态反馈**：面板标题 `<summary>` 实时显示「已拉 N 张 · 最近 Xs 前」；预览区显示「📷 600px · 420ms · 第 N 张」
- **`agentState.viewportMonitor` 字段**：`{ enabled, intervalSec, sizePx, history }` 持久化到 `localStorage.agentState_v184`（history 不存避免 localStorage 配额爆）
- **JS 新增 7 个 `agentViewport*` 函数**：`agentViewportSaveInterval` / `agentViewportSetMeta` / `agentViewportRefreshNow`（核心拉取+渲染）/ `agentViewportRenderHistory` / `agentViewportStartPolling` / `agentViewportStopPolling` / `agentViewportToggleFullscreen` + `agentViewportBindToggleListener`（在 `agentInit` 进入时绑定 details toggle 监听器，比 DOMContentLoaded 更可靠）

### 🔄 修改 (Changed)
- `agentInit` 持久化白名单：加入 `viewportMonitor` 字段；缺字段时自动 fallback 到默认值（兼容老用户数据）
- `agentSaveState` 写入 localStorage 时显式置空 `history: []`，避免缩略图把 quota 撑爆

### 📋 兼容性
- **零破坏**：所有 v1.x 端点不动；视口端点 `/viewport_screenshot` 自 `aichat_bridge` 1.1.0 起就存在（v1.6.6 引入），所以 v1.9.6 用户**无需重装插件**
- **零新依赖**：纯前端实现，`server.js` 不变
- **package.json 版本** 1.9.6 → 1.9.7

### 🚧 下一步
- **v2.0 Phase 3**（4 天）：前端新增 `agentRunMCPMode()`，走 OpenAI tool calling 多轮循环；`server.js /api/chat` 透传 `tools` / `tool_choice` / `delta.tool_calls`；UI 加「🛠 工具调用历史」面板

---

## [v2.0 Phase 2] - 2026-05-17 — server.js MCP 工具网关

> **详细完成说明见 [`RELEASE_v2.0_PHASE2.md`](./RELEASE_v2.0_PHASE2.md)。**
> 🏗 **Phase 2/5**：把 Phase 1 在 Blender 端造好的 16 个 `/mcp/*` 端点搬上"前端能直接调"的台面，由 Express 统一代理 + 错误归一化。前端版本号 `package.json` 仍不变（1.9.6），等 Phase 3 前端 Agent 循环完成后一起发 v2.0.0 正式版。
> ✅ **完全向后兼容**：v1.9.6 前端跑在带 v2.0 网关的 server.js 上一切照旧；老 v1.2.0 Blender 插件通过 `/api/mcp/ping` 仍能被探测识别（返回 `mcp_ready=false + upgrade_hint`）

### 🆕 新增 (Added)
- **`server.js` 894 → 1060 行**：在 `/api/blender/upload-local-model`（v1.9.1）和 `/api/polyhaven/*`（v1.7.0）之间注入 v2.0 MCP 网关层
- **4 个 HTTP 端点**：
  - `GET /api/mcp/tools?url=<blender_url>` —— 透传 Blender `GET /mcp/tools`，返回 16 个工具的 OpenAI tools 格式 schema
  - `POST /api/mcp/call` —— 通用调度，前端 Agent 主入口。Body `{ blender_url, tool, args, timeout? }`，默认超时 120s（覆盖 PolyHaven 4k 下载等慢操作），可由请求覆盖到 5~600s
  - `POST /api/mcp/tool/:tool_name` —— RESTful 直调（便于 curl 调试），:tool_name 走 `^[a-zA-Z][a-zA-Z0-9_]*$` 白名单防注入
  - `GET /api/mcp/ping?url=<blender_url>` —— 轻量探活（5s 超时），专门挑 Blender `/ping` 里 mcp 子对象 + 给老插件返回 `mcp_ready=false` + `upgrade_hint`
- **`_normalizeBlenderUrl()` URL 校验工具函数**：必须 `http(s)://` 开头，自动去尾部 `/`，防止 SSRF + 防止前端忘传时打到自身
- **`_mcpErrorPayload(err)` 错误归一化工具函数**：把 axios 异常按 `err.code` 自动分类成 4 种 `error_type`（network / timeout / bad_request / upstream），每种带预置的用户友好 `hint`

### 🏗 错误契约（关键设计）
- **工具自身错误**（Blender 返回的 `{ok:false, error}`，例如 unknown tool / 参数缺失 / Python traceback）→ **原样透传** HTTP 200，让前端 Agent 拿到 Blender 端最原始的错误信息（含 `available` 工具列表、`traceback` 等扩展字段），便于换策略
- **网络/HTTP 异常**（轮子根本没转起来）→ 网关归一化成 `{ok:false, error_type, error, http_status?, hint, upstream_data?}`，统一 502
- **网关层参数错误**（缺 blender_url / tool / args 非对象）→ `{ok:false, error_type: 'bad_request', error}`，统一 400
- 前端 Agent 循环只需按 `data.ok` 一刀切判断，不需要看 HTTP 状态码

### 🧪 自测覆盖
- mock Blender 9 个场景全过：成功路径 / 工具失败（200 透传）/ Blender 5xx（502 upstream）/ 缺 blender_url（400）/ 连接被拒（502 network）/ RESTful 直调 / tool_name 非法字符拦截
- 真 v1.2.0 老插件兼容性场景实测：`/api/mcp/ping` 优雅返回 `mcp_ready=false + upgrade_hint`，`/api/mcp/tools` 返回 502 `error_type=upstream`

### 📋 兼容性
- **零破坏**：所有 v1.x 端点（`/api/blender/exec /api/blender/ping /api/polyhaven/* /api/tripo3d/*` 等）100% 保留不动
- **零新依赖**：仅复用已有 `axios`
- **v1.9.6 前端**：完全不受影响（没人调 `/api/mcp/*`）

### 🚧 下一步
- **Phase 3**（4 天）：前端新增 `agentRunMCPMode()`，走 OpenAI tool calling 多轮循环；调 `/api/chat` 时传 `tools` 参数；UI 加工具调用历史面板
- **Phase 4/5**：兼容迁移开关（v1.x/v2.0 双模式 radio）+ 三场景对比测试 + 发布

---

## [v2.0 Phase 1] - 2026-05-17 — Blender 插件 MCP 工具层（aichat_bridge 1.2.0 → 2.0.0）

> **详细完成说明见 [`RELEASE_v2.0_PHASE1.md`](./RELEASE_v2.0_PHASE1.md)。**
> 🏗 **Phase 1/5**：仅升级 Blender 插件层（HTTP 端点），server.js 和前端尚未对接 —— 前端版本号 `package.json` 暂不变（仍 1.9.6），等 Phase 2/3 完成后一并发布 v2.0.0 正式版。
> ✅ **完全向后兼容**：原 v1.x 客户端（v1.9.6 + 插件 1.2.0）跑得好好的，2.0.0 插件能 100% 替换 1.2.0 插件而不破坏现有功能

### 🆕 新增 (Added)
- **`blender_addon/aichat_bridge/__init__.py` 升级 1.2.0 → 2.0.0**（871 行 → 1872 行）：注入 **15 个 MCP 原子工具** + 路由表 + Schema 注册表 + 统一调度入口 `_mcp_call()`，为 v2.0 的 Agent 循环架构（LLM 多轮 tool_call）铺底
  - **观察类（4个）**：`get_scene_info` / `get_object_info` / `list_objects` / `get_viewport_screenshot`
  - **创建类（3个）**：`add_primitive`（8 种几何体）/ `add_light`（POINT/SUN/SPOT/AREA）/ `set_camera`
  - **修改类（4个）**：`update_object`（增量改 loc/rot/scale/visible）/ `set_material`（Principled BSDF 一把梭：base_color/roughness/metallic/emission）/ `delete_object` / `clear_scene`
  - **PolyHaven 类（3个，混合路由）**：`search_polyhaven_assets`（在线 REST + 多字段加权打分）/ `set_world_hdri`（先下载再主线程导入）/ `import_polyhaven_model`（gltf/blend 双格式）
  - **兜底+质检（2个）**：`exec_python`（保留任意代码执行兜底）/ `quality_check`（4 维度自检，不抛错只返回 issues）
- **路由策略**：每个 tool 的 schema 含 `_route` 字段
  - `main` → `_post_to_main()` 主线程调度（bpy.data / bpy.ops 必须）
  - `thread` → HTTP handler 线程直接跑（只读 / 纯网络）
  - `mixed` → handler 线程下载文件 → 主线程 import
- **新增 HTTP 端点**：
  - `GET /mcp/tools` 返回 15 个工具的 OpenAI tools 格式 schema（前端 LLM 可直接吃）
  - `POST /mcp/call` 通用调度：body `{tool, args}`
  - `POST /mcp/<tool_name>` 直接调对应工具，body 即 args
- **`/ping` 端点扩展**：features 数组加 `mcp_tools`，新增 `mcp.{enabled, tool_count, tools}` 子对象供前端探测

### 🔧 修改 (Changed)
- **`bl_info` 版本号**：`(1, 2, 0)` → `(2, 0, 0)`，description 更新强调 MCP tool layer 和 Agent-loop 架构
- **`ADDON_VERSION` 字符串**：`"1.2.0"` → `"2.0.0"`
- **`REQ_HEADERS` UA**：`aichat-bridge/1.2.0` → `aichat-bridge/2.0.0`
- **`_drain_queue` 主线程 dispatcher 扩展**：新增 `mcp_<tool_name>` 任务类型的统一处理（去前缀后路由到 `MCP_MAIN_HANDLERS`）
- **N 面板新增"v2.0 MCP 工具协议"信息盒**：显示 "已注册 15 个工具" + "端点: /mcp/tools · /mcp/call"
- **Preferences 面板说明文字**：v1.2.0 文案 → v2.0.0 文案（强调 MCP 工具协议 + Agent 循环 + 向后兼容）
- **打包**：`blender_addon/aichat_bridge.zip` 重新构建，23 KB（含 __init__.py 85 KB / README.md 3.5 KB）

### 📋 兼容性
- **零破坏**：所有 v1.x 端点（`/exec /scene_report /viewport_screenshot /hyper3d/* /sketchfab/* /config /log`）100% 保留，行为不变
- **依赖不变**：仍然只依赖 `requests`（与 v1.2.0 一致）
- **v1.x 客户端**：v1.9.6 前端跑在 v2.0.0 插件上一切照旧；要享受 v2.0 Agent 循环必须等 Phase 3 前端完成

### 🚧 下一步
- **Phase 2**（半天）：`server.js` 加 `/api/mcp/call` 和 `/api/mcp/tools` 透传 + 错误处理
- **Phase 3**（4 天）：前端新增 `agentRunMCPMode()`，走 OpenAI tool calling 多轮循环
- **Phase 4/5**：兼容迁移 + 测试发布

---

## [1.9.6] - 2026-05-17

> **详细发布说明见 [`RELEASE_v1.9.6.md`](./RELEASE_v1.9.6.md)。**
> 🚧 **v2.0 MCP 架构改造路线图同步发布**：[`RELEASE_v2.0_MCP_ROADMAP.md`](./RELEASE_v2.0_MCP_ROADMAP.md)
> ✅ **完全向后兼容 v1.9.5**：`aichat_bridge` 1.2.0 插件无需重装

### 🆕 新增 (Added)
- **PolyHaven 模式新增『资产选择器』**（治『AI 经常分辨不准网络资产的真实样子』根本性痛点）：
  - 流程改成 **AI 出 plan JSON → 弹选择器让用户挑/换/删/添加 → 用户点【✅ 确认推送到 Blender】才编译 Python 代码**
  - HTML 新增 `#asset-picker-modal` 弹窗：🌅 HDRI 区（缩略图 + 换/删） + 📦 物体清单（grid 2 列，每个物体缩略图 + asset_id + 位置/scale + 换/删按钮 + 顶部【➕ 添加资产】） + 🔍 内嵌搜索面板（关键词 + 类型下拉 + 4 列网格结果）
  - JS 新增 10+ 函数：`agentShowAssetPicker / agentRenderAssetPicker / agentSwapAsset / agentDeleteAsset / agentAddAsset / agentSearchAssets / _apShowPopular / _apRenderSearchResults / agentPickSearchResult / agentConfirmAssetPicker / agentCancelAssetPicker`
  - 启动时预加载 Popular 热门资产（200 个 models + 80 个 HDRI + 80 个 textures），搜索框无关键词时显示热门列表
  - 内部用 `JSON.parse(JSON.stringify(plan))` 深拷贝，用户编辑不影响原数据；换资产时保留原 location/rotation/scale（用户调好的位置不要丢）
- **`RELEASE_v2.0_MCP_ROADMAP.md` v2.0 MCP 架构改造接力文档**（用户提出"为什么 blender-mcp 可用性那么高"后，对比分析根因并给出完整施工蓝图）：
  - **本质差距**：blender-mcp 让 LLM 多轮 tool_call 循环（看→决策→行动→看），我们让 LLM 一次性吐大段代码盲写
  - 三层架构设计 + 15 个必做 MCP tool 清单（get_scene_info / search_polyhaven_assets / add_primitive / update_object / set_material 等）
  - 5 个 Phase 的施工任务清单（插件升级 2.0.0 → server 网关 → 前端 Agent 循环 → 兼容迁移 → 测试发布）
  - 新会话开场白模板（直接复制即可秒续）

### 🔄 元数据
- `package.json` 版本 1.9.5 → **1.9.6**，description 更新

---

## [1.9.5] - 2026-05-17

> **详细发布说明见 [`RELEASE_v1.9.5.md`](./RELEASE_v1.9.5.md)。**
> ✅ **完全向后兼容 v1.9.4**：`aichat_bridge` 1.2.0 插件无需重装

### 🐛 修复 (Fixed)
- **修复『流式分批推送中间批次被 quality_check() 误炸整段』bug**：
  - 现场：用户跑 [5/16] 这批被 `[quality_check] Validation Error [维度3-Light]: 只有 2 盏灯` + `Validation Error [维度4-Material]: 6 个物体缺失材质` 整批 exec 失败
  - 根因：v1.7.4 引入的 `quality_check()` **全局严格质检**（缺任一维度 raise Exception）和 v1.6.8 的**流式分批推送**机制冲突 —— AI 在 prompt 引导下每批末尾都调用 `quality_check()`，但中间批次场景还没建完（灯光/相机/材质要在最后才出现），导致中间批次必然 raise → 整批 exec 失败 → 连锁断流
  - 简言之：v1.7.4 的"终末质检"设计前提是"AI 一次性输出全部完成"，但 v1.6.8 改成流式分批推送后这个前提不成立了
  - 修复方案：改 `AGENT_DEFENSIVE_HEADER` 里 `quality_check()` 函数 —— **只 print Warning 不 raise**。质检价值不丢失（错误仍 print 到 Blender 日志，AI 在自检阶段调 `/scene_report` 时一样能看到错误并生成 patch 修），但流式中间批次不再被误炸

---

## [1.9.4] - 2026-05-17

> **详细发布说明见 [`RELEASE_v1.9.4.md`](./RELEASE_v1.9.4.md)。**
> ✅ **完全向后兼容 v1.9.3**：`aichat_bridge` 1.2.0 插件无需重装

### 🐛 修复 (Fixed)
- **修复『Claude 4.7 选了文本对话模型却仍然 PolyHaven plan JSON 解析失败』根因 bug**：
  - 现场：用户用 Claude 4.7 跑 PolyHaven 模式仍然报错，前 400 字显示 `<polyhaven_plan>` 标签和合法 JSON 开头但**在 objects 数组中间被硬截断**
  - 根因：中转 API 默认 `max_tokens` 只有 4096（很多）/ 2000（部分），而 Claude 输出含 HDRI + ground + 8+ objects + extra_lights + camera 的完整 plan 通常需要 3000~5000 tokens → 响应被截断 → JSON 没闭合 → 前端 `agentExtractPolyHavenPlan` 解析失败
  - 修复方案 ① **`server.js` `/api/chat` 接受可选参数 `max_tokens`**（范围 256~64000），按需透传给上游 LLM；不传则保持原行为（用中转 API 默认值，老 caller 完全不受影响）
  - 修复方案 ② **`m3dCallLLM` 新增第 8 参数 `maxTokens`，默认值 16000**：所有现有 caller（agentRunPolyHavenMode / agentRunFinalMode / m3dStep4_estimate 等）自动获得足够的输出空间。16000 是 Claude 4.5/4.7 / GPT-4o / DeepSeek 都能稳定输出的安全中位数

---

## [1.9.3] - 2026-05-17

> **详细发布说明见 [`RELEASE_v1.9.3.md`](./RELEASE_v1.9.3.md)。**
> ✅ **完全向后兼容 v1.9.2**：`aichat_bridge` 1.2.0 插件无需重装

### 🐛 修复 (Fixed)
- **修复「智能 Agent 任务失败/中止后再次启动报『Agent 正在运行中，请先停止』死锁」bug**：
  - 根因：`agentStartRun()` 的 `finally` 块只重置 UI（隐藏停止按钮 / 显示开始按钮），漏了把 `agentState.status` 从 `'generating'` / `'reviewing'` 重置回 `'aborted'`，下次启动入口检查命中报错，但中止按钮已被 finally 隐藏 → 死锁
  - 修复：finally 块结尾追加 `if (status === 'generating'/'reviewing') status = 'aborted'`，只在还停留在运行态时重置，不影响 `'done'` 状态

### 🆕 新增 (Added)
- **「📋 从一键3D导入四宫格」一键按钮**（智能 Agent 参考图区）：
  - 一键把【一键3D建模 → Step 3】生成的 1024×1024 四宫格参考图（前/侧/顶/45°）推送到智能 Agent 的 `agentState.referenceImages`
  - AI 视觉模型可以"看到"该图辅助理解场景空间布局，避免用户在两个面板间手动重新上传相同的图片
  - 完整校验：m3dState 是否存在 / views 是否非空 / 是否已导入过（防重复）/ 4 张上限提示替换
  - 新增 `agentImportFromM3dGrid()` 函数

### 🔄 元数据
- `package.json` 版本 1.9.2 → **1.9.3**，description 更新

---

## [1.9.2] - 2026-05-17

> **详细发布说明见 [`RELEASE_v1.9.2.md`](./RELEASE_v1.9.2.md)。**
> ✅ **完全向后兼容 v1.9.1**：`aichat_bridge` 1.2.0 插件无需重装

### 🐛 修复 (Fixed)
- **修复「智能 Agent 选了图像生成模型跑 plan 阶段时报 `unknown finish reason: [NO_IMAGE]`」整段崩 bug**：
  - 根因：用户在「🎬 智能 Agent 实时渲染」选了 `gpt-image-1` / `dall-e-3` / `flux` / `stable-diffusion` / `kolors` / `hunyuan-image` / `seedream` 等图像生成模型，中转 API 在执行 PolyHaven plan 阶段（要求 LLM 输出 JSON）时透传了图像模型专有的 `[NO_IMAGE]` finish_reason → 前端 `agentExtractPolyHavenPlan` 解析 JSON 失败 → 抛 `plan 解析失败` 让用户一脸懵
  - 修复方案 ① **加 `agentLooksLikeImageModel()` helper 函数**，覆盖 20+ 主流图像模型特征词（gpt-image-N / dall-e / flux / midjourney / sd / sdxl / kolors / hunyuan-image / wanx / cogview / kandinsky / recraft / ideogram / imagen / firefly / playground / lumalabs / jimeng / pixart / seedream 等）
  - 修复方案 ② **`agentStartRun()` 入口预检**：命中图像模型特征词立即弹友好 alert（写明「该模型不对，应改选 Claude / GPT-4o / DeepSeek / Gemini / Qwen 等文本对话模型」）并阻止启动，用户根本进不到 plan 阶段
  - 修复方案 ③ **`agentRunPolyHavenMode()` plan 解析失败时智能识别**：通过返回内容关键词（`[NO_IMAGE]` / `unknown finish reason` / `image generation` / `content_filter` / `cannot generate image` / `not a text model` 等）二次识别，给出针对性指引（覆盖入口预检漏掉的小厂图像模型）
  - 修复方案 ④ **非图像模型的解析失败也给友好建议**：「换更强的模型 / 把场景描述写得更具体 / 多重试 1~2 次」，而不是干瘪的「plan 解析失败」

### 🔄 升级 (Changed)
- **`hasLaunched_v1.9.1` → `hasLaunched_v1.9.2`**：发版后给老用户再弹一次欢迎窗口看新内容

---

## [1.9.1] - 2026-05-17

> **详细发布说明见 [`RELEASE_v1.9.1.md`](./RELEASE_v1.9.1.md)。**
> ✅ **完全向后兼容 v1.9.0/v1.8.x**：`aichat_bridge` 1.2.0 插件无需重装

### 🆕 新增 (Added)
- **📁 「导入本地 3D 模型到 Blender」一键按钮**（智能 Agent 实时渲染面板内独立工具区，与生成方式 radio 解耦）：
  - 支持 7 种主流格式：GLB / GLTF / FBX / OBJ / DAE / PLY / STL
  - 适用场景：Tripo3D 网页下载 / Meshy / Sketchfab / 本地 Blender 建模等任意来源
  - 零插件升级：复用现有 `aichat_bridge` 1.2.0 的 `/exec` 端点
- **后端 `POST /api/blender/upload-local-model`**：把前端上传的 base64 文件落到 OS 临时目录，返回绝对路径供 Blender `bpy.ops.import_scene.*` 直接读

### 🚫 移除 (Removed)
- **删除 v1.9.0 的 Tripo3D 集成**（设计前提塌房：Tripo3D 网页「Send to Blender」是会员专属，免费用户不可用）：
  - 删除 `blender_addon/tripo_bridge/` 整个目录
  - 删除 `tripo_bridge.zip` 打包产物
  - 删除 `/api/blender/export-tripo-bridge` 端点（server.js）
  - 删除「🤖 Tripo3D 文生 3D」生成方式 radio + 配置面板（index.html）
  - 主调度 `agentStartRun()` 里 `genMode === 'tripo3d'` 自动 fallback 到 polyhaven，老用户无感切换不报错
- ⚠️ `agentRunTripo3DMode()` / `AGENT_TRIPO3D_PROMPT` / 后端 3 个 `/api/tripo3d/*` 透传端点等死代码暂保留，下个版本清理（不影响功能）

### 🔄 元数据
- 版本号：`1.9.0` → `1.9.1`
- 欢迎弹窗 key：`hasLaunched_v1.8.4` → `hasLaunched_v1.9.1`（老用户重启后弹一次新内容）

---

## [1.7.0] - 2026-05-17

> **详细发布说明见 [`RELEASE_v1.7.0.md`](./RELEASE_v1.7.0.md)。**
> ✅ **完全向后兼容 v1.6.x**：插件 `aichat_bridge` 1.1.0 无需重装；老用户 localStorage 自动迁移

### 🆕 新增 (Added) — 核心特性
- **🎨 「PolyHaven 网络资产引擎」**（智能 Agent 实时渲染新增生成方式，可在 UI 切换）：
  - AI 仅输出 `<polyhaven_plan>` JSON 资产清单（HDRI + 模型 + 贴图 + 灯光 + 相机）
  - 由 Blender 端 `urllib` 调用 `https://api.polyhaven.com/files/{asset_id}` **真实下载** `.blend / .hdr / PBR 贴图`
  - 用 `bpy.data.libraries.load(.blend) + scene_coll.children.link()` 把资产 append 进场景
  - 资产 **CC0 协议免授权商用**，质量专业级（PBR / 4K HDRI）
  - prompt 内置 **18 张常用 HDRI + 25 个模型 + 9 套 PBR 贴图** 的资产 ID 清单
  - 首次下载 30~120s，后续走本地缓存秒开（缓存目录 `$TMP/aichat_polyhaven_cache/`）
  - `agentState.generationMode = 'ai-only' | 'polyhaven'` 持久化到 `localStorage.agentState_v168`
- **🔍 `search_query` 模糊搜索字段**（治 AI 猜错 asset_id 全场景红色 Cube）：
  - PolyHaven plan JSON 的 `objects / hdri / ground` 新增可选字段 `search_query`（英文关键词，如 `"vintage chair"`）
  - Blender 端 `resolve_search_query()` 通过 `urllib` 调本机 `GET /api/polyhaven/search?q=xxx&type=models`，server 端按 `name×3 + categories×2 + tags×1` 加权打分，返回最匹配的 `asset_id`
  - 服务端三个新代理 API：`GET /api/polyhaven/search`（6h 全量清单缓存）/ `GET /api/polyhaven/files`（透传解决 CORS）/ `GET /api/polyhaven/download`（流式 SSE 进度推送 + 本地缓存到 `$TMP/aichat_polyhaven_cache/`）
  - 编译时 `agentBuildPolyHavenCode(plan, serverBaseUrl)` 把 `location.origin` 注入 Python 端 `SERVER_BASE_URL` 常量（端口被占用顺延时也能动态拿到当前 host:port）
  - 内存级 `_SEARCH_RESOLVE_CACHE` 同关键词只查一次；找不到时回落到 `[MISSING_ASSET]_xxx` 占位 Cube，不阻断后续灯光相机
- **🎨 `change_object_color()` / `recolor()` 健壮颜色修改工具函数**（治 PolyHaven 外部资产带 PBR 贴图改 Base Color 无效）：
  - PolyHaven 模式自动在场景代码尾部注册两个全局工具函数，AI 自检阶段可直接调用
  - 自动检测 Base Color 端口是否连接了 `ShaderNodeTexImage`：有贴图 → 在贴图和 BSDF 之间插入 `ShaderNodeHueSaturation` 节点（根据目标 RGBA 算 Hue/Saturation/Value 调色调）；无贴图 → 直接改 BSDF Base Color `default_value`
  - 链路上已有 HSV 节点 → 复用而不重复插入
  - 便捷封装 `recolor("sofa", "#1a1a1a")` 支持 hex 字符串或 (r,g,b) 元组两种入参
  - 完整 `try/except` 包裹，单点失败不影响整体流程，运行时 print 每个 slot 成功/失败统计
- **`server.js` 转发 `reasoning_content`**：Claude / DeepSeek / GPT-o1 等推理模型在思考时输出的 `delta.reasoning_content` 现在会通过 SSE `{reasoning: ...}` 推给前端，治"按下后干瞪眼 30~120s"问题
- **`m3dCallLLM` 新增第 7 参数 `onReasoning(chunk, fullReasoning)`**：thinking 内容回调，向后兼容（不传则按老行为）

### 🛡️ 强化 (Strengthened) — 稳定性
- **`agentPushCode` 内部自动注入 v1.6.9 防御 header**：所有 caller（agentRunNoneMode / agentRunFinalMode / agentRunIncrementalMode / agentRunPolyHavenMode）无需手动调 `agentInjectDefensive()`，集中在最底层注入更不易漏。治 Gemini 3.1 Pro / Claude 错写 `BL_VER >= 4` 导致 `NameError` 后整段崩
- **v1.6.9 安全壳升级 — 防 GPU 4 倍负载卡死**：
  - 只把【第一个 3D 视口】切到 RENDERED（之前遍历所有视口同时打开 RENDERED）
  - 强制关闭 Blender 的 quad view（4 视图分屏，`bpy.ops.screen.region_quadview()` + `temp_override`），避免 GPU 计算 4 次

### 📦 改动 (Changed)
- `package.json` 版本号 1.6.6 → **1.7.0**，description 更新
- 欢迎弹窗 key 升级 `hasLaunched_v1.6.6 → hasLaunched_v1.7.0`，老用户重启后会再弹一次新内容
- 欢迎弹窗新增 v1.7.0 章节（PolyHaven 引擎 + 防 GPU 炸说明），v1.6.6 章节降级为"历史版本"

---

## [1.6.6] - 2026-05-16

> **本次发布跨度较大**，详细发布说明见 [`RELEASE_v1.6.6.md`](./RELEASE_v1.6.6.md)。
> ⚠️ **配套 Blender 插件 `aichat_bridge` 已升级 1.0.2 → 1.1.0，用户必须重装一次插件 zip**

### 🐛 修复 (Fixed) — P0 致命 Bug
- **一键3D「只生成一个平面」根因修复**：v1.6.5 推到 Blender 4.2+ 后只创建地板 plane，其它物体全部丢失。根因是 Blender 4.2+ 的 EEVEE Next **移除了** `use_bloom` / `use_volumetric_lights` / `use_ssr` 等属性，AI 生成的代码在第一个 setattr 就抛 `AttributeError`，导致整段 `exec()` 中断
- **修复方案**：
  1. Step 4 prompt 强制要求所有 `scene.eevee.*` 必须用 `hasattr()` 守护后再赋值
  2. 强制要求每个独立物体用 `try/except pass` 包裹（即使单点失败下一个仍能继续）
  3. `bsdf.inputs["Emission"]` 必须双重兼容（`Emission Color` 和 `Emission` 都试一遍）
  4. 安全壳 `m3dWrapWithSafetyShell` 同步加上 hasattr 守护，去掉硬编码的 4.x 已移除属性
  5. 推送后自动拉 Blender 端 `/log` 显示到 UI（用户能立刻看到"哪行炸了"）

### 🆕 新增 (Added) — 重磅新模块
- **🎬 智能 Agent 实时渲染**（全新独立模块，**不替代** 一键3D建模）：
  - **流式分章节推送**：AI 一边生成代码、Blender 一边出现物体 ✨（用户在 B 站发短视频会爆）
  - **三种自检策略**（用户可自由切换）：
    - `不自检`：最快（~45s），不再调用 LLM
    - `全部完成后自检`（**默认**）：流式生成完 → AI 看 `/scene_report` 自我纠正 → 修正 patch（~90s，质量 ~85 分）
    - `每 N 个物体自检一次`（N=1~30，可自定义）：每攒够 N 个物体就暂停 → 微观自检 → 修这一批 → 继续（~130s，质量 ~95 分）
  - **最大自检轮数**：1~10 防失控
  - **章节边界协议**：AI 输出格式严格按 `# === [CHAPTER:xxx] ===` 和 `# === [OBJ:i/N] name ===` 分段，前端按边界切片推送
  - **位置**：摄影工具顶部新增第 5 个按钮「🎬 智能 Agent 实时渲染」
  - **⚠️ Token 警示横幅**：模块顶部红色提示"该功能消耗 Token 较大（每轮自检 = 1 次 LLM 调用），按需调整自检策略"
  - **独立 `agentState` 持久化**：`localStorage.agentState_v166`，与 `m3dState` 完全隔离
  - **支持中止**：流式过程中可点 ⏹ 立刻中断
- **Blender 桥接插件 `aichat_bridge` 升级 1.0.2 → 1.1.0**：
  - 新增 `GET /scene_report`：返回当前场景 JSON（物体清单 + 位置/尺寸/材质/Emission、灯光清单 + 类型/能量/颜色、相机、视口模式、统计 stats、最近 errors）→ 让 AI 能"看见"自己的作品做自检
  - `GET /ping` 增强返回 Blender 版本号 (`blender_major` / `blender_minor`)，前端 prompt 可自适应生成 3.x / 4.x 代码
  - 完全向后兼容：老前端只用 `/exec`、`/ping`、`/log` 仍能跑
- **「📥 一键导出 Blender 插件 zip 到桌面」按钮**（在两个建模模块都有）：
  - server.js 新增 `GET /api/blender/export-addon`：把 `extraResources/blender_addon/aichat_bridge.zip` 复制到用户桌面
  - **彻底解决 macOS 用户翻 .app 包内容的痛**

### 🚀 优化 (Improved)
- 一键3D 推送代码后自动拉 `/log`，把 Blender 执行日志显示到 UI（不再"推完就石沉大海"）
- 「🩺 测试连接」升级，同时显示 Blender 版本号 + 队列长度
- 欢迎弹窗 v1.6.6 内容前置 + `hasLaunched_v1.6.6` 新 key（v1.6.5 内容降到历史折叠区）

### 🔄 向后兼容
- ✅ 旧「🧊 一键3D建模」**完全保留**（4 步流水线、所有 `m3d*` 函数不动）
- ✅ 老用户无感升级，只是「不再只有一个平面」
- ⚠️ 想用「智能 Agent 实时渲染」必须**重装一次插件 zip**（点新模块里的「📥 一键导出」按钮即可）

### 📦 打包 (Build)
- macOS dmg：arm64 + x64
- Windows nsis：x64 + arm64
- 内置插件已升级为 `aichat_bridge.zip` v1.1.0

---

## [1.6.5] - 2026-05-16

### 🔥 治黑屏终极方案 (Critical Fix)

用户反馈 v1.6.4 推到 Blender 后场景全黑（只有 mesh 灯具外壳，没有真正的 LIGHT 物体；自发光物体不发光）。v1.6.5 双管齐下根治：

### 🆕 新增 (Added)
- **Step 4 改为 AI 直接输出 bpy 代码**：彻底砍掉 SceneSpec JSON 这个中间产物（5 步 → 4 步），AI 读「场景描述 + 四宫格图」直出 `<blender_code>...</blender_code>` 标签包裹的完整可执行 Blender Python 代码。避免「散文 → JSON → 本地转换」每一道传递的信息损失
- **System Prompt 升级为 13 条硬性要求**：物体≥8 个 / 灯光≥3 盏真正的 LIGHT 物体 / 自发光必须同时设 Emission Color + Strength / 灯光能量参考表（AREA 500~2000、POINT 500~3000）/ 按场景类型给三点布光预设 / 必须有相机 + 世界背景 / EEVEE Next 兼容
- **推送 Blender 前自动包裹 v1.6.5 安全兜底壳**(~150 行 Python，由 `m3dWrapWithSafetyShell()` 注入）：
  1. **灯光 < 3 自动补三点光**（key 1500 + fill 600 + rim 1200 + sun 3）
  2. **AI 灯光 ×1.5 安全系数**（Filmic 会自动 tone-map 不会过曝）
  3. **强制 Filmic Color Management + Medium High Contrast**（v1.6.4 是 sRGB 默认，亮部死白）
  4. **视口强制切到 RENDERED**（v1.6.4 是 Material Preview，看不到完整光影；Rendered 才能看到 SSR/Bloom 实时效果）
  5. **自动启用 EEVEE 的 Bloom / SSR / GTAO / Soft Shadow / TAA 64**（用 hasattr 防止版本差异报错）
  6. **自动切到相机视角**（避免用户看错方向以为没东西，兼容 Blender 3.x / 4.x 的 `temp_override`）
  7. **多行控制台诊断输出**：物体数 / 灯光数 / 自发光数 / 视口模式 / 相机状态
- **新增 `m3dExtractBlenderCode()` 工具函数**：从 AI 返回中提取代码，兼容四种情况（标准 XML 标签 / 漏写结束标签 / `​```python` 代码块 / 没标签但包含 `import bpy`）

### 🚀 优化 (Improved)
- **AI prompt 灯光能量范围全面上调**：v1.6.4 数值偏低（AREA 50~500、POINT 100~1500），v1.6.5 提升到工程实用值（AREA 500~2000、POINT 500~3000、SPOT 800~3000、SUN 5~10）
- **World strength 默认值**：0.5 → 1.0~1.8
- **自发光物体 Emission Color 必填**：v1.6.4 只设 Emission Strength，但 Blender 4.x 默认 Emission Color = 黑色 → 不发光。v1.6.5 强制要求 AI 在自发光物体同时设 `Emission` / `Emission Color`（兼容 4.x 改名）+ `Emission Strength` 双重设置

### 🐛 修复 (Fixed)
- **场景里没有真正灯光**：根因是 AI 把灯具理解成 mesh 物体（建灯具外壳但 lights 数组为空，或 SceneSpec JSON 格式错误导致解析失败）。改为 AI 直出代码后，prompt 明确「必须用 `bpy.data.lights.new()` 创建至少 3 个真正的 LIGHT 物体（不是 mesh 灯具外壳！）」，安全壳兜底再补一道
- **整个场景几乎全黑**：除了灯光不足，还有 sRGB 色彩管理导致暗部全黑、视口在 Solid 模式只显示灰模。Filmic + Rendered 双重修复

### 🎯 用户预期效果
打开 Blender 运行 v1.6.5 生成 + 推送的代码后：
1. 视口直接显示 RENDERED 模式 + Filmic 色彩
2. 至少 3 个真正的 LIGHT 物体
3. 自发光物体真的发光（吊灯/台灯/屏幕）
4. 场景丰满，至少 8 个 mesh 物体（含 AI 主动补全的盆栽/装饰画）
5. 自动切到相机视角
6. 控制台 print 出诊断信息

### 📦 向后兼容
- 老用户 v1.6.4 项目数据完全兼容（`m3dState.summary` 仍是 XML 包裹的散文，`stepConfigs` 不变）
- `m3dState.spec` 在 v1.6.5 不再实际使用，保留兼容字段（写入 `{ _v165: true, note: '...' }` 占位），老数据切换回来不会报错
- 重新点击 Step 4 会顶掉老 spec，写入新 code

### 🗂️ 文件变更
- `ai-chat/public/index.html` — Step 4 UI 改文案、删除 Step 5 节点、`m3dStep4_estimate` 完全重写、新增 `m3dExtractBlenderCode` + `m3dWrapWithSafetyShell`、`m3dSendToBlender` 注入安全壳、hasLaunched key 升到 v1.6.5
- `ai-chat/package.json` — `version` 升至 `1.6.5`，`description` 更新为治黑屏方案说明
- `ai-chat/RELEASE_v1.6.5.md` — 完整发布说明（含根因分析、参数对比表、改动清单、预期效果）

---

## [1.6.4] - 2026-05-16

### 🆕 新增 (Added)
- **一键3D建模 Step 3 新增「⏭️ 跳过此节点」复选框**：勾选后整个 Step 3 灰显（API/模型下拉、生成按钮全部禁用），Step 4 不再传四宫格参考图给视觉模型，转而要求模型仅靠 Step 2 的场景描述自行演算光影/材质/尺寸。状态会持久化到 `m3dState.skipStep3` 字段，随摄影项目保存。
  - **适用场景**：图像 API 没额度、不想等 1024×1024 出图、对参考图质量不满意、纯文字描述已经够具体
- **Step 4 SceneSpec 契约升级**（向后兼容）：
  - `scene.world_strength`（0.0~2.0）：HDR 环境光强度，户外晴天 1.2、室内日光 0.5、夜间 0.1
  - `scene.exposure`（-3~3）：相机曝光补偿
  - `scene.time_of_day`：`noon|sunset|night|indoor_lit|studio|overcast` 六个时段预设
  - `scene.ambient_mood`：`warm|neutral|cool`
  - `lights[].rotation_euler_deg`：SUN/SPOT 灯的朝向（默认朝下 -Z）
  - `lights[].purpose`：`key|fill|rim|practical|sun|window|ambient` 灯光用途注释
  - `material.emission_strength`：自发光物体（吊灯/屏幕/霓虹灯）务必给 1~20
- **强制 AI 输出 lights ≥ 3**：System Prompt 升级为「少于 3 个会渲染扁平、视为失败」+ 按 `time_of_day` 给出具体的三点布光预设公式（key/fill/rim 数值范围）
- **Step 2 场景总结输出格式升级为 XML 标签包裹**：要求 AI 用 `<scene_description>...</scene_description>` 包裹散文，方便下游精确解析；新增 `m3dExtractSceneDescription()` 工具函数兼容三种情况（完整标签 / 只有开始标签 / 完全没有标签 → 走兼容老数据分支）；Step 4 把 extract 后的纯散文再用同样标签重新包好喂给视觉模型，让 LLM 清楚知道"哪一段是场景"，避免和指令混淆
- **bpy 脚本兜底布光**：生成的 Python 代码会在 `bpy.ops` 阶段检查灯光数量，若 AI 只生成 0~2 个灯光，自动按 `time_of_day` 预设补足：
  - `noon` / `overcast`：太阳光 + 主光 + 辅光 + 轮廓光
  - `night` / `studio`：仅三点布光（无太阳光）
  - `sunset` / `indoor_lit`：低角度暖色太阳光 + 三点光

### ✨ 优化 (Changed) — 彻底解决「Blender 里只有粗模型、没材质光影」问题
- **生成的 bpy 脚本现在自动把 3D 视口切到 `Material Preview`**：
  - 之前默认显示 `Solid`（灰模），用户必须手动按 Z → 6 才能看到颜色/粗糙度/金属度
  - 现在脚本最后会遍历所有 `VIEW_3D` 区域，把 `space.shading.type` 设为 `"MATERIAL"`
  - 同时开启 `use_scene_lights = True` 和 `use_scene_world = True`，让场景灯光和世界背景生效
- **渲染引擎升级到 EEVEE Next**：
  - 优先用 Blender 4.2+ 的 `BLENDER_EEVEE_NEXT`，老版本自动 try/except 回退到经典 `BLENDER_EEVEE`
  - 自动启用 Bloom（辉光）/ SSR + SSR Refraction（屏幕空间反射/折射）/ GTAO（环境光遮蔽）/ Soft Shadow（柔和阴影）
  - TAA 采样：渲染 64、视口 16；阴影分辨率：cube 1024 / cascade 2048
  - 所有 EEVEE 属性写入用 `hasattr` 守护，兼容 Blender 3.x ~ 4.x 各版本字段差异
- **World 背景节点同时设置颜色与强度**：之前只设了 `inputs[0]` 颜色，现在也设 `inputs[1]` strength
- **相机曝光补偿**：写入 `scene.view_settings.exposure`，根据 SceneSpec 的 `exposure` 字段动态调整
- **脚本最后 `print` 输出建议**：「视口已切到 Material Preview。若想看 SSR/Bloom 实时效果，请按 Z → 8 切换到 Rendered Viewport。」

### 🛠️ Step 4 跳过分支
- 当 `m3dState.skipStep3 === true` 或 `m3dState.views === null` 时：
  - 不在 user content 里附加 `image_url`，纯文本消息
  - System Prompt 头部明确告知"无参考图，请完全依赖文字描述演算"
  - 状态条显示「⏳ 测算中（仅文字演算光影）...」让用户感知

### 🔄 向后兼容
- 老 SceneSpec（没有 `world_strength` / `exposure` / `time_of_day`）依然能正确生成 bpy 脚本：缺失字段会用默认值（worldStrength=0.5、exposure=0、timeOfDay=indoor_lit）兜底
- 老项目数据里的 `m3dState` 缺 `skipStep3` 字段时，自动初始化为 `false`
- 老 SceneSpec 灯光缺 `rotation_euler_deg` / `purpose`：默认 `[0,0,0]`，purpose 不输出注释

### 📦 打包
- 重新构建 macOS dmg（arm64 + x64）和 Windows nsis 安装包（x64 + arm64 + universal）
- 欢迎弹窗 localStorage key 从 `hasLaunched_v1.6.3` 升级到 `hasLaunched_v1.6.4`

---

## [1.6.3] - 2026-05-16

### 🚫 移除 (Removed) — 重大体验改进
- **全面下线 8 处「或手动输入模型名」输入框**：
  - ① 普通对话模式（顶部工具栏 `#custom-model`）
  - ② AI 对战模式（参与者卡片 `.pc-custom-model`）
  - ③ 思维导图模式（左侧 `#mm-custom-model`）
  - ④ 工作流 AI 节点（`<input df-custom-model>`）
  - ⑤ 摄影 → 图像分析任务卡（addAnalyzeTask + restoreAnalyzeTask 两处）
  - ⑥-⑧ 摄影 → 一键3D建模 Step 2/3/4 节点（`.m3d-step-custommodel`）
  - 统一从「设置 → API → 筛选模型 → 手动添加自定义模型 ID」管理可用模型
  - **用户痛点**：之前每个模式都重复有"或手动输入模型名"输入框，体验混乱
  - **新方案**：模型管理唯一入口在「设置 → API → 筛选模型」，干净统一

### 🆕 新增 (Added)
- **「筛选模型」弹窗新增「➕ 手动添加自定义模型 ID」折叠区**：
  - 对于 `/v1/models` 不返回但 API 实际支持的模型（如 `gpt-image-2` / `claude-opus-4` / `dall-e-3`），可手动追加到列表
  - 添加后即时显示在模型列表中（标记「自定义」），默认勾选
  - 已添加的模型以 chip 形式展示在折叠区，支持单独移除
  - 保存筛选时会一并 PUT 到后端 `customModels` 字段持久化
  - 后端在拉取模型列表时自动合并 `/v1/models` 返回结果 + `customModels`，去重后输出
- **3D 建模流水线运行中切换模式/项目前弹确认**：
  - 新增 `m3dIsAnyRunning()` 检查 Step 2/3/4 任一节点是否有 AbortController 在运行
  - `switchMode()`：从 photo 模式切到其他模式前弹确认框，确认后调用 `m3dCancelAll()`
  - `selectPhotoSession()`：切换其它摄影项目前同样弹确认
  - 避免老项目还在跑、新项目就把右侧面板冲掉的尴尬情况
  - 取消后已生成的中间结果（SceneSummary / 四宫格图 / SceneSpec / Code）不会丢失

### ✨ 优化 (Changed)
- **Step 2 总结场景提示词强化「只总结环境/场景，不输出人物」**：
  - 原版本：AI 经常在场景里夹带人物的服装、动作、表情，但 3D 建模只需要环境
  - 新版本：System Prompt 明确禁止描写人物 / 动物 / 生物，只提取「环境」与「静态物体」
  - 同时强化"必须输出散文，禁止 JSON / Markdown 列表 / 标题 / 代码块"，避免回退到 v1.6.2 之前的 JSON 失败
- **Step 3 模型下拉提示文案更新**：从「推荐 gpt-image-2 / gpt-image-1 / dall-e-3」简化为「推荐 gpt-image-2 / dall-e-3」

### 🐛 修复 (Fixed)
- **修复 `package.json` 中 `name` 字段重复声明的 bug**：原本同时存在 `"name": "ai-multi-chat"` 和 `"name": "ai-chat-app"`，JSON 不报错但 `npm` 会忽略后者，本次合并为唯一字段 `ai-chat-app`
- **AI 对战开始 / 图像分析任务校验**：错误提示新增"未找到模型时可去 设置 → API → 筛选模型 → 手动添加自定义模型 ID"，引导用户走正确入口

### 🔄 向后兼容 (Compatibility)
- 老项目里工作流 AI 节点保存的 `customModel` 字段（旧的手动输入框值）会作为兜底显示：
  - selectWfSession 恢复时如果保存的 `model` 不在筛选列表里，会自动把 `customModel` 添加到下拉框（带「(自定义)」后缀）并选中
  - 运行时 `runWorkflow` 优先用 `node.data.model`，没有则回落到 `node.data.customModel`
- 老项目摄影 → 图像分析任务的 `customModel` 字段在新版本保留为空字符串（不影响读取）
- 普通对话 / AI 对战 / 思维导图保存的 `customModel` 字段被静默忽略（这些模式从未读取过这个字段）

### 📦 打包 (Build)
- 重新构建 macOS dmg（arm64 + x64）
- Blender 插件 `aichat_bridge` 版本未变（仍为 `1.0.2`），无需重装

---

## [1.6.2] - 2026-05-16

### ✨ 优化 (Changed)
- **一键3D建模 Step 2「场景总结」从 JSON 改为自然语言**：
  - 老版本：要求模型严格输出 `SceneSummary` JSON（结构化字段：scene_type、objects[]、lighting…），中转 API 经常返回不规范 JSON 直接报错
  - 新版本：要求模型用 **300~600 字的散文式中文** 描述场景（自动融入物体清单、尺寸、布局、光照、机位）
  - 在 Step 4 测算 SceneSpec 时，把这段自然语言直接作为视觉模型的输入参考
  - **解决"Step 2 JSON 解析失败"投诉的根本性问题**

### 🆕 新增 (Added)
- **每个 AI 节点（Step 2/3/4）支持「暂停/取消」按钮**：
  - 节点运行中点 ⏸ 按钮可立即中断当前 fetch（基于 AbortController）
  - 取消后状态显示「⏸ 已取消」，不会污染右侧面板
  - 使用 `try/finally` 确保按钮状态在异常时也能正确恢复

### 🐛 修复 (Fixed)
- **Step 4 测算 SceneSpec 兼容字符串/JSON summary**：
  - 老项目保存的是 JSON 对象 → 序列化后传入
  - 新项目保存的是字符串 → 直接传入
  - 兼容性逻辑：`typeof === 'string' ? text : JSON.stringify(obj, null, 2)`
- **Step 4 多模态消息只传 1 张四宫格图**（而不是 4 张相同 URL）：token 节省 75%

### 📦 打包 (Build)
- 重新构建 macOS dmg（arm64 + x64）
- Blender 插件 `aichat_bridge` 版本未变（仍为 `1.0.2`），无需重装

---

## [1.6.1] - 2026-05-16

### 🐛 修复 (Fixed)
- **一键3D建模 Step 3「多角度图」破图 bug**：
  - 图片返回的 URL 加载失败时，原本只显示一张破图小图标，无法判断原因
  - 现在加载失败会显示中文占位提示「⚠️ 图片加载失败」+ URL 校验
  - 新增 `m3dValidateImageUrl(url)` 工具函数，预检图片可达性（base64 直通 / 远程 URL 8s 超时校验）

### ✨ 优化 (Changed)
- **多角度图：4 次调用 → 1 次调用**，针对 GPT Image 2 / GPT Image 1 / DALL·E 3 等支持自然语言指令的模型优化：
  - 一次性生成 1 张「2x2 四宫格」参考图（前 / 侧 / 顶 / 45°）
  - 同一张图同时填充到 4 个视角槽位，前端显示一致
  - **API 调用次数 -75%、token 消耗 -75%、出图时间显著缩短**
- **Step 4 测算 SceneSpec**：只把 1 张四宫格图传给视觉模型（多模态 prompt 体积大幅缩减）
- 网页端"图像模型推荐说明"更新：推荐 `gpt-image-2` / `gpt-image-1` / `dall-e-3`

### 📦 打包 (Build)
- 重新构建 macOS dmg（arm64 + x64）
- Blender 插件 `aichat_bridge` 版本未变（仍为 `1.0.2`），无需重装

---

## [1.6.0] - 2026-05-16

### 🆕 新增 (Added)
- **摄影工具新增「🧊 一键3D建模」模块**，5 步流水线：
  - ① 📚 从聊天记录里挑选场景讨论
  - ② ✨ AI 总结 `SceneSummary`
  - ③ 📸 生成 4 张多角度参考图（前 / 侧 / 顶 / 45°）
  - ④ 📏 视觉模型测算尺寸 / 材质 / 光影（`SceneSpec`）
  - ⑤ 🐍 输出可执行 `bpy` 脚本
- **Blender 插件 `aichat_bridge` v1.0.2**：监听 `127.0.0.1:9876`，接收网页推送的 bpy 代码并在 Blender 主线程执行（HTTP 接收 + `bpy.app.timers` 主线程跑，避免跨线程崩溃）
- 网页端「Blender URL + 测试连接」按钮，安装 / 排查清单内置
- 安装包 `extraResources` 附带 `blender_addon/`，可在 Blender 内 *Add-ons → Install...* 装 zip
- 每个 Step 节点独立的 API + 模型选择器（与全局对话/工作流互不干扰，自动持久化）
- 一键全流程 (`m3dRunAll`) 串联 5 步

### 🔧 后端 (Backend)
- 新增 `POST /api/blender/exec` — 转发 Python 代码到 Blender 插件
- 新增 `GET  /api/blender/ping` — Blender 插件探活

### 💾 持久化 (Persistence)
- 5 步管线全部状态（`SceneSummary` / 4 张图 / `SceneSpec` / 代码）随摄影项目持久化，下次打开自动恢复
- 兼容旧版数据迁移：`textConfigId / textModel → step 2,4`；`imgConfigId / imgModel → step 3`

---

<details>
<summary>📦 <strong>历史版本（v1.0.0 ~ v1.5.4）— 点击展开</strong></summary>

## [1.5.4]
- 🐛 修复"摄影工具 → 拍摄备忘录 → 新建项目后仍显示旧内容"的 bug
- ✨ 切换 / 新建摄影项目时会先清空备忘录的输入框和清单 + 备忘录持久化

## [1.5.3]
- 🐛 修复"切换 API 后模型列表错位 / 无法选择"的根本性 bug（令牌防竞态）

## [1.5.2]
- 🐛 修复"摄影 → 拍摄备忘录 → 从历史对话总结"功能返回为空的问题
- ✨ 优化错误提示 + 修复换行符 bug + 兼容多模态对话

## [1.5.1]
- 🎯 新增"筛选常用模型"功能 — *设置 → 已保存的 API → 筛选模型*
- 🔍 支持搜索过滤 / 全选 / 反选 / 清空，已勾选的模型自动排前面

## [1.4.0]
- 🎨 修复工作流"图生图"链路 — 节点间图片传递自动识别，画图 / 编辑类模型可正确接收上游图片作为底图

## [1.3.0]
- ⏱️ 新增"请求超时时间"设置（60~1800 秒，默认 5 分钟）

## [1.2.3]
- 🐛 修复"工作流无法选择新增 API"问题

## [1.2.2]
- 🆕 AI 节点显示返回结果（流式实时更新）
- 🐛 修复"通用节点结果为空"问题 + 详细 API 错误提示

## [1.2.0]
- 🆕 工作流暂停功能 + 选中节点一键开始 + 智能缓存复用

## [1.1.0]
- 🆕 工作流：每个节点标题旁新增 ▶ 按钮，可从该节点重跑下游
- 🛠️ 优化：节点执行后会自动缓存结果，便于增量调试

## [1.0.0]
- ✨ 全新发布：支持多 AI 互相对战讨论
- ✨ 工作流模式：可视化编排 AI 任务
- ✨ 大纲笔记与思维导图模式
- ✨ 本地历史记录保存与单条消息删除
- ✨ 深色 / 浅色主题切换

</details>
