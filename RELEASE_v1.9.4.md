# v1.9.4 修复 PolyHaven plan JSON 被截断的根因

> 发布日期：2026/5/17 · 上游：v1.9.3 · 关键词：**max_tokens 截断 / Claude 4.7 输出被截**

---

## 🐛 现场

用户报告：在「智能 Agent → PolyHaven 模式」用 Claude 4.7 跑，仍然报：

```
❌ AI 返回的 JSON 解析失败（模型可能没按 <polyhaven_plan> 标签格式输出）。
原始返回前 400 字：
<polyhaven_plan>
{
  "scene_name": "心海拍摄计划 - 小棚水波幽蓝布光",
  "world_strength": 0.08,
  "hdri": { "asset_id": "vignaioli_night", ... },
  "ground": { ... },
  "objects": [
    { "asset_id": "Ottoman_01", "name": "subject_stool_kokomi_seat",
```

> 💡 建议：① 换更强的模型 ② 把场景描述写得更具体 ③ 多重试 1~2 次  
> **我用 Claude 4.7 也报错啊！**

## 🔍 根因

观察「前 400 字」可以看出 AI **完全正确输出了 `<polyhaven_plan>` 标签和合法 JSON 开头**，但响应在 `"subject_stool_kokomi_seat",` 后面**被硬切断**了。这不是 AI 的问题，是 **中转 API 默认 `max_tokens` 限制太低**（很多默认 2000~4096），而 Claude 4.7 输出一份含 HDRI + ground + 8 个 objects + extra_lights + camera 的完整 plan 通常需要 3000~5000 tokens。

之前 v1.9.2 加的"图像生成模型识别"代码在这里命中不到（Claude 4.7 不在图像模型黑名单），所以走了通用 fallback 提示，但根本不是模型选错。

## 🔧 修复方案

### `server.js`
- `/api/chat` 端点新增可选参数 `max_tokens`，范围 `256~64000`，按需透传给上游 LLM 请求
- 没传则保持原行为（用中转 API 的默认值，老 caller 完全不受影响）

### `public/index.html`
- `m3dCallLLM()` 新增第 8 个参数 `maxTokens`，**默认值 `16000`**（足够 Claude 输出 10+ 物体的完整 plan）
- 因为默认值生效，所有现有 caller 自动获得足够的输出空间，包括：
  - `agentRunPolyHavenMode()` ⭐ 本次 bug 的主要场景
  - `agentRunNoneMode` / `agentRunFinalMode` / `agentRunIncrementalMode` / `agentRunTripo3DMode`
  - 一键3D Step 2（场景描述）/ Step 4（bpy 代码）
  - 思维导图 AI 生成 / 摄影备忘录 / 图像分析任务等

### 16000 的取值依据
- Claude 4.5/4.7 max_output_tokens 上限 ~64k，OpenAI gpt-4o ~16k，DeepSeek ~8k
- 16000 是个安全中位数，覆盖 PolyHaven plan JSON / bpy 完整代码所需，不会触发上游 hard limit

---

## 📝 修改清单

| 文件 | 改动 |
|------|------|
| `package.json` | 版本 1.9.3 → **1.9.4** + 更新 description |
| `server.js` | `/api/chat` 接受 `max_tokens` 参数，组装 reqBody 时按需注入 |
| `public/index.html` | `m3dCallLLM` 新增 `maxTokens` 参数（默认 16000） |
| `RELEASE_v1.9.4.md` | 本文件 |
| `CHANGELOG.md` | 新增 v1.9.4 段落 |

---

## 🧪 测试

1. 智能 Agent 选 Claude 4.7 + PolyHaven 模式
2. 输入复杂场景（≥ 8 个物体）
3. ✅ 期望：plan JSON 完整闭合，正常推送到 Blender 下载 PolyHaven 资产
4. ❌ 之前：JSON 在中间被截断，前端解析失败弹"建议换模型"

---

## 🚀 打包

```bash
cd /Users/Apple/Desktop/ai-chat && npm run build:mac
```

产物：`dist/白歌的AI讨论组-1.9.4-arm64.dmg` + `dist/白歌的AI讨论组-1.9.4-x64.dmg`
