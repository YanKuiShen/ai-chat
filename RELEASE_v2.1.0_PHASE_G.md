# v2.1.0 Phase G · CHANGELOG + 欢迎弹窗 + README + 打包发版

> 详细 Added/测试详情已写入 [`CHANGELOG.md`](./CHANGELOG.md) 的 [2.1.0] 段「Added · 📦 Phase G」+ ROADMAP「Phase G ✅」。本文件做接力索引。

## ✅ 一句话总结

把 Phase A~F 的全栈范式跃迁**完整收口到用户侧**：欢迎弹窗 key 末次 bump 到 `hasLaunched_v2.1.0_final`、顶部当前版本卡片重写为 6 个 Phase 全栈交付概览 + 橙色警示栏（要求老用户手动重装 zip），历史区开头一次性归档 v1.11.0~v1.11.14 共 9 个 patch；README.md 第 1 章重写为「v2.1 Codex CAD 范式」六维表格 + 版本历程速览补 v1.11.x/v2.1.0；重打 4 个 dmg/exe 安装包（mac arm64+x64、win arm64+x64）含 28K 新 `aichat_bridge.zip` extraResources。

## 📂 改动文件

- `public/index.html`（5K+ 字符 diff，G-1/G-2 已在前序会话落地）：
  - **G-1** 欢迎弹窗 key 末次 bump：`hasLaunched_v2.1.0` → `hasLaunched_v2.1.0_final`（`checkFirstLaunch` + `closeWelcomeModal` 两处同步）
  - **G-2a** 顶部「✨ 当前版本」卡片重写为「v2.1.0 Codex CAD 范式 · Phase A~F 全栈交付」：6 个 Phase 列表（A Plan-Execute-Reflect / B 真·文件系统 / C bpy 检索 / D 多角色协作 / E bmesh 模板库 / F 插件 2.1.0 软回滚）+ ⚠️ 橙色警示栏要求老用户必须手动重装新 `aichat_bridge.zip`（旧 2.0.4 不会被 dmg 自动覆盖）
  - **G-2b** 「📜 历史版本」折叠区开头插入「v1.11.0 ~ v1.11.14 MCP Agent 体验级打磨」综合段（9 个 patch 一次性归档）
- `README.md`（本次 G-3）：第 1 章重写为「v2.1 Codex CAD 范式」六维 Phase 表格替代旧 v2.0 MCP Agent 卖点 + 第 3 步使用说明改为多角色协作 + 技术栈 `aichat_bridge` 2.0.0 → 2.1.0 + 版本历程速览顶部新增 v2.1.0 / v1.11.x 综合归档行 + 致谢区新增 LangGraph / Anthropic Computer Use / Claude Code / Codex CAD 范式参考来源
- `CHANGELOG.md`（本次 G-4）：[2.1.0] 段顶部 Phase 拆分行追加 G ✅ + 新增「Added · 📦 Phase G」块 + 末尾 ROADMAP「Phase G ⏳ → ✅」状态切换
- `RELEASE_v2.1.0_PHASE_G.md`（本文件）：接力索引格式仿 PHASE_F.md
- `dist/` 4 个安装包重打（含 28K aichat_bridge.zip extraResources）：
  - `白歌的AI讨论组-2.1.0-arm64.dmg` / `白歌的AI讨论组-2.1.0-x64.dmg`
  - `白歌的AI讨论组-Setup-2.1.0-arm64.exe` / `白歌的AI讨论组-Setup-2.1.0-x64.exe`

## 🎨 G-2a 当前版本卡片 6 个 Phase 列表精华

弹窗顶部紫色渐变卡片用 `<ul>` 列出 Phase A~F 全栈改动的一句话总结（每行带 emoji 标识）：

```
🧠 Phase A · Plan-Execute-Reflect 三段循环（5 个客户端工具 plan_create / 
   plan_update_step / plan_get / reflect / mark_done，前端 JS 直接执行毫秒返回）
📂 Phase B · 真·文件系统（5 个 workspace 工具 + ~/Desktop/ai-chat-workspace/ 
   时间戳化 session 子目录 + 路径穿越攻击拦截）
📚 Phase C · bpy API 实时检索（192 条精选 cheatsheet + search_bpy_docs 工具，
   节省 80%+ system prompt 配额）
🎭 Phase D · 多角色专家协作（Planner / Modeler / Critic 三角色独立 API + 模型，
   主循环按 round 切换 system prompt + 工具表）
🎨 Phase E · bmesh / GN 模板库（10 个预制模板 + Mustache 参数渲染 + 
   apply_template / list_templates 一行调用）
🛡 Phase F · aichat_bridge 插件 2.0.4 → 2.1.0（GET /blend_summary + 
   POST /bookmark_state + POST /restore_state 三个端点 + 软回滚机制）
```

## ⚠️ 橙色警示栏（重要！）

紫色卡片底部插一段橙色高亮警示栏（`background: rgba(251, 146, 60, 0.15); border-left: 4px solid #fb923c`），明确提醒老用户：

```
⚠️ v2.1.0 dmg 安装后必须在 Blender 里手动重装新 aichat_bridge.zip
   （旧 2.0.4 不会被 dmg 自动覆盖）：
   桌面端右侧【📥 一键导出插件 zip 到桌面】→ 
   Blender Edit → Preferences → Add-ons → 
   找到旧 AIChat Bridge 卸载 → Install 新 zip → 勾选启用 → 重启 Blender。
   否则前端看不到 blend_summary / bookmark_state 等新端点，
   Phase F 软回滚机制不工作。
```

理由：`extraResources` 复制到 dmg 内部的 `Contents/Resources/blender_addon/aichat_bridge.zip` 是 28K 新插件，但**已经手动装在 Blender 里的 2.0.4 插件不会因为 dmg 升级被自动覆盖**。所以必须老用户主动卸载旧版 + 重装新 zip。

## 📜 G-2b 历史区 v1.11.0~v1.11.14 综合归档段

历史折叠区开头一次性归档 9 个 patch（按时间倒序，从 v1.11.14 → v1.11.0），每条一行带核心 fix 摘要：

```
v1.11.14 · MCP enum 速查表 + exec_python args 必带 code 强化坑 1
v1.11.13 · MCP Agent 网络韧性 4 次重试 + Blender 5.x bevel API 警告
v1.11.12 · 欢迎弹窗布局重构（当前版本卡片直接展示 + 老版本折叠）
v1.11.5  · 截图修复升级（多视口模式覆盖 + Critic 审图前自动截屏）
v1.11.4  · 截图二级修复首发
v1.11.3  · 视口内存泄漏修复
v1.11.2  · ECONNRESET 重试基础版
v1.11.1  · reasoning_content 流式回传修复
v1.11.0  · 模型能力检测（自动识别 OpenAI tool calling 支持）
```

避免每个 patch 单独占一段把折叠区撑爆，**长时维护可读性**优先于历史完整度。需要查具体 patch 详情的用户去 [`CHANGELOG.md`](./CHANGELOG.md) 翻完整版变更记录。

## 📦 G-5 重打 4 个 dmg/exe 安装包

```bash
cd /Users/Apple/Desktop/ai-chat
npm run build:mac    # 出 mac arm64 + x64 共 2 个 dmg
npm run build:win    # 出 win arm64 + x64 共 2 个 exe
```

`package.json` 已确认：
- `"version": "2.1.0"` ✅
- `extraResources` 含 `blender_addon/**` 全目录（自动包含最新 28K 的 `aichat_bridge.zip`）✅
- `mac.target.dmg.arch: ["arm64", "x64"]` + `win.target.nsis.arch: ["x64", "arm64"]` ✅

产物落 `dist/`：
```
白歌的AI讨论组-2.1.0-arm64.dmg          # mac Apple Silicon
白歌的AI讨论组-2.1.0-x64.dmg            # mac Intel
白歌的AI讨论组-Setup-2.1.0-arm64.exe    # win arm64
白歌的AI讨论组-Setup-2.1.0-x64.exe      # win x64
```

## 🤝 与 Phase A/B/C/D/E/F 协作矩阵

| Phase | 与 G 的关系 |
| --- | --- |
| A · Plan-Execute-Reflect | 当前版本卡片用 🧠 emoji 占位 + 一句话覆盖能力跃迁要点 |
| B · 真·文件系统 | 卡片提到 `~/Desktop/ai-chat-workspace/` 工作目录路径，老用户首次启动会自动 mkdir |
| C · bpy API 检索 | 卡片提到 192 条 cheatsheet，让用户知道 prompt 不再靠堆反踩坑速查 |
| D · 多角色专家协作 | 卡片显式提到 Planner / Modeler / Critic 三角色 → README 第 3 步使用说明配 API + 模型 |
| E · bmesh 模板库 | 卡片提到 10 个预制模板覆盖家具/装饰/建筑三大类 |
| F · 插件 2.1.0 | **关键！** 橙色警示栏要求老用户手动重装 zip 否则 Phase F 软回滚机制不工作 |

## 🚦 验收 checklist

- [x] G-1 欢迎弹窗 key 末次 bump（`hasLaunched_v2.1.0_final` 在 `checkFirstLaunch` + `closeWelcomeModal` 两处同步）
- [x] G-2a 当前版本卡片重写（6 Phase 列表 + 橙色警示栏）
- [x] G-2b 历史区开头插 v1.11.0~v1.11.14 综合 9 patch 段
- [x] G-3 README.md 第 1 章重写为「v2.1 Codex CAD 范式」+ 版本历程速览补 v1.11.x/v2.1.0 + 技术栈 aichat_bridge 2.0.0 → 2.1.0
- [x] G-4 CHANGELOG [2.1.0] 顶部 Phase 拆分行追加 G ✅ + 新增「Added · 📦 Phase G」块 + 末尾 ROADMAP「Phase G ⏳ → ✅」
- [x] G-4 RELEASE_v2.1.0_PHASE_G.md（本文件）
- [x] G-5 `npm run build:mac && npm run build:win` 重打 4 个 dmg/exe（首次打包 5 个产物，aichat_bridge.zip 28K）
- [x] **G hotfix** · 补 `blender_manifest.toml` 治 Blender 5.x 装插件搜不到 ⭐（用户实测 Blender 5.1.1 装入成功 ✅，aichat_bridge.zip 28K → 30K，dmg/exe 二次重打包入新 zip）

## 🩹 G hotfix · blender_manifest.toml（治 Blender 5.x 装插件搜不到，关键！）

### 故障现场

用户实测 Blender 5.1.1 装 `aichat_bridge.zip` 后通过 `Edit → Preferences → Add-ons` 搜索「AIChat」**一片空白搜不到**，无报错弹窗。

### 根因分析

Blender 4.2 起引入了**全新「Extensions」系统**取代老 add-on：

1. 老 add-on 只需在 `__init__.py` 里写 `bl_info = {...}` 字典即可
2. 新 extension 要求每个扩展包**根目录有 `blender_manifest.toml`** 描述文件（声明 schema/id/version/permissions 等）
3. 仅有 `bl_info` 而无 `blender_manifest.toml` 的 zip 在 Blender 5.x 里**会被默认隐藏到 Legacy add-on 列表**（默认不可见），用户在主 Add-ons 列表里搜索就找不到
4. 即使在搜索框右边的下拉里切到 "Legacy" 也只是肉眼可见但需用「Install Legacy Add-on...」入口安装（多一步）

### 修复方案

新增 `blender_addon/aichat_bridge/blender_manifest.toml`（30 行 TOML）：

```toml
schema_version = "1.0.0"
id = "aichat_bridge"
version = "2.1.0"
name = "AIChat Bridge"
tagline = "白歌的AI讨论组 桥接：MCP 工具层 + Codex CAD（Plan/File/bpy/Templates/软回滚）"
maintainer = "白歌 <1455714025@qq.com>"
type = "add-on"
blender_version_min = "4.2.0"
tags = ["Development"]
license = ["SPDX:GPL-2.0-or-later"]
copyright = ["2026 白歌"]

[permissions]
network = "桥接 HTTP server 监听 127.0.0.1:9876 接收前端推送 bpy 代码 + 调 PolyHaven / Sketchfab / Hyper3D 远程 API 下载资产"
files = "读写 ~/Desktop/ai-chat-workspace/（AI 工作目录）+ $TMP/aichat_polyhaven_cache/（PolyHaven 资产缓存）"

[build]
paths_exclude_pattern = ["__pycache__/", "*.pyc", ".DS_Store", "*.zip"]
```

同时保留同目录下的 `__init__.py` 里完整的 `bl_info` 块，向后兼容 Blender 3.x / 4.0 / 4.1 的 legacy add-on 安装方式。**双轨并存**让 v2.1.0 插件能装到 Blender 3.0 起所有版本。

### zip 重打

`cd blender_addon && rm -f aichat_bridge.zip && zip -r aichat_bridge.zip aichat_bridge -x '*.DS_Store' '*__pycache__*' '*.pyc'`

新 zip 4 个文件 30K：
```
aichat_bridge/                           (dir)
aichat_bridge/__init__.py                105K
aichat_bridge/README.md                  3.5K
aichat_bridge/blender_manifest.toml      1.3K  ⭐ NEW
```

### Blender 5.1.1 用户实测 ✅ 通过

新安装入口（跟 4.1- 完全不同）：

1. Blender 5.1.1 启动
2. **Edit → Preferences** → 左侧切到 **「Get Extensions」** 标签（**不是**老的 Add-ons）
3. 右上角 **▼** 下拉菜单 → 选 **「Install from Disk...」**
4. 选 `aichat_bridge.zip`
5. 装完后**自动跳到** **「Add-ons」** 标签 + 默认勾选启用
6. 顶部搜索框搜「AIChat」能立刻找到
7. 在 3D 视口按 N 键展开侧边栏看到 **AIChat** 标签页 ✅

### dmg/exe 二次重打

用户测试 zip OK 后，执行 `rm -rf dist && npm run build:mac && npm run build:win` 重新生成 4 个安装包，把新 30K zip 通过 `extraResources` 打入 dmg/exe 内部，让首次下载的用户直接拿到含 manifest 的 zip 不再踩同样的坑。

## 📌 v2.1.0 全部 Phase 完成状态总览

| Phase | 状态 | 接力索引 |
| --- | --- | --- |
| A · Plan-Execute-Reflect | ✅ | [`RELEASE_v2.1.0_PHASE_A.md`](./RELEASE_v2.1.0_PHASE_A.md) |
| B · 真·文件系统 | ✅ | [`RELEASE_v2.1.0_PHASE_BD.md`](./RELEASE_v2.1.0_PHASE_BD.md) |
| C · bpy API 检索 | ✅ | [`RELEASE_v2.1.0_PHASE_CE.md`](./RELEASE_v2.1.0_PHASE_CE.md) |
| D · 多角色专家协作 | ✅ | [`RELEASE_v2.1.0_PHASE_BD.md`](./RELEASE_v2.1.0_PHASE_BD.md) |
| E · bmesh / GN 模板库 | ✅ | [`RELEASE_v2.1.0_PHASE_CE.md`](./RELEASE_v2.1.0_PHASE_CE.md) |
| F · aichat_bridge 插件 2.1.0 | ✅ | [`RELEASE_v2.1.0_PHASE_F.md`](./RELEASE_v2.1.0_PHASE_F.md) |
| G · CHANGELOG + 欢迎弹窗 + README + 打包 | ✅ | [`RELEASE_v2.1.0_PHASE_G.md`](./RELEASE_v2.1.0_PHASE_G.md)（本文件）|

## 🎉 v2.1.0 Codex CAD 范式重构 14 天工程蓝图圆满收尾

总工具数：v1.10.0 的 16 个 Blender 原子工具 → v2.1.0 **29 个**（+5 plan + 5 workspace + 1 search_bpy_docs + 2 templates = +13 客户端工具）。

总改动文件：4 个核心源（`public/index.html` / `server.js` / `blender_addon/aichat_bridge/__init__.py` / `package.json`）+ 2 个 JSON 知识库（`scripts/bpy-cheatsheet.json` 192 条 / `scripts/bmesh-templates.json` 10 模板）+ 5 个 RELEASE_v2.1.0_PHASE_*.md 接力索引（A / BD / CE / F / G）+ CHANGELOG.md + README.md + blender_addon/README.md + aichat_bridge.zip 23K → 28K。

端到端测试通过：Phase A 5/5 + Phase B 30/30 + Phase C 7/7 + Phase D 6/6 + Phase E 25/25 + Phase F 5/5 = **78/78 全过 ✅**。

## 🚧 下一个 Minor 版本（v2.2.0 暂定）方向探索

> 留给后续会话决策，本次 v2.1.0 全栈不再扩张：

1. **Phase H · Long-running session 持久化**：`agentState` 序列化到 `~/Desktop/ai-chat-workspace/.session_state.json`，跨会话续跑无需用户手动恢复
2. **Phase I · Critic 多次审图迭代**：单次 critic 不够时支持 2~3 轮 Modeler ↔ Critic 来回，直到 reflections 收敛
3. **Phase J · 模板库扩展**：从 10 个 → 30 个（覆盖更多家具/电器/植物类别），社区贡献的模板可作为 plugin 集成
