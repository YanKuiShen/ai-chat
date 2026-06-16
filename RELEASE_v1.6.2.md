# 🚀 白歌的AI讨论组 — v1.6.2 发布说明

**发布时间**：2026-05-16
**版本**：`1.6.2`（PATCH，向后兼容）
**前一版本**：[v1.6.1](./RELEASE_v1.6.1.md)

---

## ✨ 本次重点

### 1. 🧊 一键3D建模 Step 2「场景总结」从 JSON 改为自然语言

**问题背景：**
v1.6.0 / v1.6.1 中 Step 2 要求模型严格输出 `SceneSummary` JSON（包含 `scene_type` / `objects[]` / `lighting` / `camera_suggest` 等字段）。但是大量中转 API（尤其是国内中转）：
- 经常给 JSON 前后塞 markdown 代码块
- 字段名英文/中文混乱
- 嵌套层级不规范
- 直接导致前端 `JSON.parse` 报错，整个流水线卡住

**v1.6.2 解决方案：**

| 项目 | 老版本 | 新版本 |
|------|--------|--------|
| **System Prompt** | "严格输出 SceneSummary JSON" | "用 300~600 字的散文式中文描述场景" |
| **输出格式** | 结构化 JSON 对象 | 自然语言字符串 |
| **解析逻辑** | `m3dParseJSON()` 容易失败 | `(result || '').trim()` 几乎不会失败 |
| **下游使用** | `JSON.stringify(summary)` | 字符串直接拼到 prompt 里 |

System Prompt 升级后，模型必须自然融入：
- ✅ 场景类型与整体氛围（室内/室外、视觉风格、情绪基调）
- ✅ 主要物体清单 + 尺寸 + 数量（例如"一张约 2 米长的实木桌""靠墙摆着 3 把布艺沙发"）
- ✅ 物体的相对布局
- ✅ 光照来源、色温、明暗
- ✅ 推荐主镜头机位

**效果：**
- 🎯 解决"Step 2 JSON 解析失败"投诉的根本性问题
- 📖 阅读体验更好（300~600 字的散文 > 一坨结构化 JSON）
- 🤖 几乎所有 LLM 都能稳定产出，不再挑模型

---

### 2. ⏸ 每个 AI 节点（Step 2/3/4）支持「暂停/取消」按钮

**新增交互：**
- Step 2/3/4 每个节点的「生成」按钮旁多了一个 ⏸ 按钮（默认隐藏）
- 节点开始运行 → ⏸ 显示
- 点 ⏸ → 立即中断当前 fetch（基于 `AbortController`）
- 取消后状态显示「⏸ 已取消」，不会污染右侧面板

**实现细节：**
- 新增全局 `m3dControllers = { 2: null, 3: null, 4: null }`
- `m3dStepStart(n)` / `m3dStepEnd(n)` / `m3dCancel(n)` 三个工具函数
- `m3dCallLLM` / `m3dGenImage` 都支持传入 `signal` 参数
- 使用 `try / catch (AbortError) / finally` 三段式确保按钮状态在异常时也能正确恢复

---

### 3. 🐛 Step 4 兼容字符串/JSON summary

**老项目数据（v1.6.0/1.6.1）：** `m3dState.summary` 是 JSON 对象
**新项目数据（v1.6.2+）：** `m3dState.summary` 是字符串

**兼容性逻辑：**
```js
const summaryText = (typeof m3dState.summary === 'string')
  ? m3dState.summary
  : JSON.stringify(m3dState.summary, null, 2);
```

老项目打开 v1.6.2 不会丢数据，可以直接接着用。

---

### 4. 🎨 Step 4 多模态消息只传 1 张四宫格图

继 v1.6.1 的"4 张图 → 1 张四宫格"优化后，v1.6.2 进一步在 Step 4 测算时也只把这 1 张图传给视觉模型：

| 项目 | v1.6.0 | v1.6.1 | v1.6.2 |
|------|--------|--------|--------|
| Step 3 出图次数 | 4 次 | 1 次 | 1 次 |
| Step 4 多模态图数量 | 4 张 | 4 张（重复 URL） | **1 张** |
| 总 token 消耗 | 100% | ~50% | **~25%** |

---

## 📦 安装方式

### macOS

下载 dmg：
- Apple Silicon (M1/M2/M3): `白歌的AI讨论组-1.6.2-arm64.dmg`
- Intel: `白歌的AI讨论组-1.6.2-x64.dmg`

### Windows

下载安装包：
- `白歌的AI讨论组-Setup-1.6.2-x64.exe`
- `白歌的AI讨论组-Setup-1.6.2-arm64.exe`

### Blender 插件 `aichat_bridge`

**版本未变（仍为 1.0.2），从 v1.6.0/1.6.1 升级到 v1.6.2 无需重装插件。**

---

## ⚠️ 升级注意

- ✅ **完全向后兼容**：老的摄影项目数据可以直接打开，自动迁移
- ✅ **不需要重装 Blender 插件**
- ⚠️ **首次启动会显示更新弹窗**（因为 `hasLaunched` 键升级到 `v1.6.2`）

---

## 🔗 相关链接

- 📋 [完整变更日志 CHANGELOG.md](./CHANGELOG.md)
- 📐 [版本管理规范 VERSIONING.md](./VERSIONING.md)
- 🆕 [v1.6.1 发布说明](./RELEASE_v1.6.1.md)
- 🆕 [v1.6.0 发布说明](./RELEASE_v1.6.0.md)

---

**贡献者**：白歌 + Cline AI
**反馈邮箱**：1455714025@qq.com
