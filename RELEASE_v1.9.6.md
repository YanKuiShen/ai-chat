# v1.9.6 PolyHaven 资产选择器（AI 出草案 → 用户挑选 → 再推送）

> 发布日期：2026/5/17 · 上游：v1.9.5
> 关键词：**资产选择器 / 用户确认 / 缩略图挑选 / 防 AI 瞎猜**
> 🚨 **v2.0 MCP 改造规划文档同步发布**（详见 `RELEASE_v2.0_MCP_ROADMAP.md`）

---

## 🐛 痛点

之前 PolyHaven 模式：**AI 出资产清单 JSON → 前端直接编译 + 推送**。  
但 AI 经常**分辨不准**网络资产的真实样子，导致：

- 同样叫 `vintage_chair` 的 asset_id，实物可能是欧式宫廷、北欧极简、维多利亚风格里的任何一种 —— AI 只能"猜"
- AI 经常基于 asset_id **名字**而非**实物**做决策，下载下来才发现完全不对路
- 用户拿到结果只能重跑整个 Round 1（消耗一轮完整的 LLM token），效率极低

## 🔧 修复方案

把 PolyHaven 模式改成 **"AI 出草案 → 弹选择器让用户挑/换/删/添加 → 用户点【✅ 确认推送】才编译 Python 代码推到 Blender"**。

### 资产选择器 UI（`#asset-picker-modal`）

1. **🌅 HDRI 环境光区**：缩略图 + asset_id + 清晰度/强度，可【🔄 换】/【❌ 删】
2. **📦 物体清单区**（grid 2 列）：每个物体显示缩略图 + 名字 + asset_id + 位置/scale，行内有【🔄 换】/【❌ 删】按钮，顶部有【➕ 添加资产】按钮
3. **🔍 内嵌搜索面板**（默认隐藏，点【🔄 换】/【➕ 添加】时弹出）：
   - 关键词输入框（自动填当前 asset_id 作为搜索建议）
   - 类型下拉（模型/HDRI/贴图）
   - 搜索结果以 4 列网格显示，每个结果显示缩略图 + asset_id
   - 调 `/api/polyhaven/search`（server.js 端 6h 缓存 + 多字段加权打分）
   - 无关键词时显示 Popular 热门列表（启动时从 `/api/polyhaven/list-popular` 预加载 200 个 models + 80 个 HDRI + 80 个 textures）
4. **底部**：【取消】+【✅ 确认推送到 Blender】

### 关键改动

| 文件 | 改动 |
|------|------|
| `package.json` | 版本 1.9.5 → **1.9.6** + 更新 description |
| `public/index.html` | ① 新增 `#asset-picker-modal` HTML 弹窗（HDRI 区 + 物体清单 + 搜索面板）<br>② 新增 10+ JS 函数：`agentShowAssetPicker / agentRenderAssetPicker / agentSwapAsset / agentDeleteAsset / agentAddAsset / agentSearchAssets / _apShowPopular / _apRenderSearchResults / agentPickSearchResult / agentConfirmAssetPicker / agentCancelAssetPicker`<br>③ 改 `agentRunPolyHavenMode`：plan 解析成功后 `await agentShowAssetPicker(plan)`，用户确认后才走 `agentBuildPolyHavenCode(confirmedPlan)` |
| `RELEASE_v1.9.6.md` | 本文件 |
| `CHANGELOG.md` | 新增 v1.9.6 段落 |

### 流程对比

```
v1.9.5（旧）:
  AI 出 plan JSON → 编译代码 → 直接推 Blender → 用户傻眼

v1.9.6（新）:
  AI 出 plan JSON → 弹选择器
    ├ 用户对着缩略图换 5 个不合适的 asset_id
    ├ 用户删掉 2 个多余的物体
    ├ 用户搜 "monstera plant" 加 1 个龟背竹
    └ 点【✅ 确认推送】
  → 用 confirmedPlan 编译代码 → 推 Blender → 满意 ✅
```

### 数据流安全

- 选择器内部用 `JSON.parse(JSON.stringify(plan))` **深拷贝** plan，编辑不影响原数据
- 换资产时保留原物体的 `location / rotation_deg / scale`（用户调好的位置不要被改丢）
- 用户取消 → 返回 `null` → `agentRunPolyHavenMode` 抛 `'用户取消'` 错误 → finally 块正常重置状态

---

## 🚧 v2.0 MCP 改造规划同步发布

用户反馈："为什么网上看到的 Claude 通过 MCP 操控 Blender 可用性那么高，我们的差距这么大？"

**回答**：因为路线本质不同。详见 `RELEASE_v2.0_MCP_ROADMAP.md`：

| 维度 | blender-mcp（MCP 路线） | 我们当前 |
|------|------------------------|----------|
| 交互模式 | LLM 多轮 `tool_call` 循环（看→决策→行动→看） | LLM 一次性吐几百行代码或大 JSON |
| 场景反馈 | 每步 `get_scene_info()` 拿真实状态 | 全程盲写，最后才一次 `/scene_report` |
| 错误恢复 | 单个 tool_call 失败立刻换策略 | 一段代码炸了整批崩 |
| 资产挑选 | LLM `search_polyhaven_assets` 看返回再选 | 200 个 asset_id 塞 prompt 让 LLM 猜 |
| 修改粒度 | "把沙发挪到 (1,0,0)" 1 个 tool_call | 重新写整段 patch 代码 |
| AI 角色 | Agent（自主决策者） | Translator（描述→代码翻译机） |

**v1.9.6 是临时止血方案**（资产选择交还给用户），v2.0 才是架构层面的彻底重构（让 LLM 像人一样"边看边干"）。

---

## 🚀 打包

```bash
cd /Users/Apple/Desktop/ai-chat && npm run build:mac
```

产物：`dist/白歌的AI讨论组-1.9.6-arm64.dmg` + `dist/白歌的AI讨论组-1.9.6-x64.dmg`

## 🧪 测试

1. 智能 Agent 选 PolyHaven 模式（Claude 4.7 / GPT-4o）
2. 输入「我要建一个北欧极简风格的客厅」
3. ✅ 期望：AI 生成 plan 后**弹出选择器**，显示 HDRI 缩略图 + 8~12 个物体清单
4. 测试操作：
   - 点物体行的【🔄 换】→ 搜索 "wooden table" → 选中替换
   - 点【❌ 删】→ 物体从清单消失
   - 点顶部【➕ 添加资产】→ 搜索 "monstera plant" → 选中追加
   - 点【✅ 确认推送到 Blender】→ 用最终 confirmedPlan 推送
5. ❌ 之前：plan 解析完就直接推送，用户没机会看就已经下载完了

