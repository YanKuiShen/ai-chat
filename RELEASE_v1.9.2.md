# v1.9.2 修复「智能 Agent 选了图像生成模型」体验崩溃 bug

> 发布日期：2026/5/17
> 上游版本：v1.9.1
> 关键词：**[NO_IMAGE] / unknown finish reason / plan 解析失败 / 图像生成模型预检**

---

## 🐛 bug 现场

用户报告：

```
❌ AI 返回的 JSON 解析失败。原始返回前 400 字：
unknown finish reason: [NO_IMAGE]
❌ 运行失败：plan 解析失败
```

复现步骤：
1. 打开「🎬 智能 Agent 实时渲染」
2. 选了一个**图像生成模型**（例如 `gpt-image-1` / `dall-e-3` / `flux` / `stable-diffusion-3` / `kolors` / `hunyuan-image` / `seedream` 等）
3. 点「🎬 开始实时建模」
4. PolyHaven / Tripo3D 模式跑 plan 阶段时整段崩

---

## 🔍 根因分析

「智能 Agent」的所有引擎（AI 从零 / PolyHaven / Tripo3D / Hyper3D）都需要 LLM 输出一段【纯文本】（bpy 代码或资产清单 JSON）。

但用户的中转 API 在收到「图像生成模型」请求时：
- ① 底层模型只会返回图片或图片 URL，不会输出 JSON
- ② 当用户的 prompt 没有要求生图（例如 PolyHaven plan 是「输出 JSON」），中转 API 拿到的 `finish_reason` 是图像模型专有的 `[NO_IMAGE]` / `content_filter` / `image_generation` 等非标准值
- ③ 中转 API 把这个原始 finish_reason 拼成字符串透传给前端：`"unknown finish reason: [NO_IMAGE]"`

前端 `agentExtractPolyHavenPlan(result)` 拿到这段字符串当然解析不出 JSON → 抛 `plan 解析失败` → 用户一脸懵。

---

## ✅ v1.9.2 修复

### 1. 加 `agentLooksLikeImageModel()` helper

通过模型名特征词识别图像生成模型，覆盖 20+ 主流图像模型：

```js
function agentLooksLikeImageModel(model) {
  const imgKeywords = [
    'image-1', 'image-2', 'image-3',     // gpt-image-N
    'dall-e', 'dalle',                    // dall-e-2/3
    'flux',                               // flux / flux-pro / flux-schnell
    'midjourney', 'mj-',
    'stable-diffusion', 'sd-', 'sdxl', 'sd3',
    'kolors',                             // 快手 Kolors
    'hunyuan-image', 'hunyuan-dit',       // 腾讯混元图
    'wanx', 'wan-image',                  // 阿里通义万相
    'cogview',                            // 智谱 CogView
    'kandinsky', 'recraft', 'ideogram',
    'imagen',                             // Google Imagen
    'firefly',                            // Adobe Firefly
    'playground', 'lumalabs', 'photon',
    'jimeng',                             // 字节即梦
    'pixart',
    'doubao-seedream', 'seedream',        // 字节豆包-Seedream
  ];
  return imgKeywords.some(k => m.includes(k));
}
```

### 2. 入口预检：`agentStartRun()` 早期拦截

```js
if (agentLooksLikeImageModel(agentState.model)) {
  alert('⚠️ 检测到你选了图像生成模型「' + agentState.model + '」\n\n' +
    '「🎬 智能 Agent 实时渲染」需要的是【文本对话 LLM】（用来生成 Blender Python 代码或 PolyHaven 资产清单 JSON），不是图像生成模型。\n\n' +
    '请在上方「API + 模型」处改选以下文本对话模型：\n' +
    '  • Claude (claude-sonnet-4 / claude-opus-4 等)\n' +
    '  • OpenAI 系列 (gpt-4o / gpt-4-turbo / o1)\n' +
    '  • DeepSeek (deepseek-chat / deepseek-reasoner)\n' +
    '  • Gemini (gemini-2.5-pro / gemini-2.0-flash)\n' +
    '  • Qwen (qwen-max / qwen-plus)\n\n' +
    '图像生成模型仅用于「📸 一键3D建模 → Step 3 多角度参考图」节点。');
  return;
}
```

→ 用户根本进不到 plan 阶段，直接看到「该模型不对，应该选什么」的明确指引。

### 3. 兜底防御：`agentRunPolyHavenMode()` plan 解析失败时智能识别

万一用户的模型名不在 `agentLooksLikeImageModel` 黑名单（例如某些小厂的图像模型），plan 解析失败时通过返回内容关键词二次识别：

```js
const isImageModelError = /\[NO_IMAGE\]|unknown finish reason|finish_reason|image generation|content_filter|no image generated|image model|cannot generate image|not a text model/i.test(rawText)
  || agentLooksLikeImageModel(agentState.model);

if (isImageModelError) {
  // 弹出和入口预检一致的引导文案
  agentAppendReviewLog(`<div style="color:var(--danger); font-weight:600;">
    ❌ 模型「${agentState.model}」看起来是【图像生成模型】，不是【文本对话 LLM】
    ...请改选 Claude / GPT-4o / DeepSeek / Gemini 等文本对话模型
  </div>`);
}
```

而不是干瘪的「plan 解析失败」，让用户一头雾水。

### 4. 非图像模型的解析失败也给出友好建议

```
❌ AI 返回的 JSON 解析失败（模型可能没按 <polyhaven_plan> 标签格式输出）
💡 建议：
① 换更强的模型（如 Claude Opus 4 / GPT-4o / DeepSeek Reasoner）
② 把场景描述写得更具体
③ 多重试 1~2 次（LLM 偶尔会漏标签）
```

---

## 📝 修改清单

| 文件 | 改动 |
|------|------|
| `package.json` | 版本 1.9.1 → **1.9.2** + 更新 description |
| `public/index.html` | ① 加 `agentLooksLikeImageModel()` 函数（20+ 关键词）<br>② `agentStartRun()` 入口预检 + alert<br>③ `agentRunPolyHavenMode()` plan 解析失败时智能识别错误<br>④ 升级 `hasLaunched_v1.9.1` → `hasLaunched_v1.9.2`（让用户重启后看到新弹窗） |
| `RELEASE_v1.9.2.md` | 本文件 |
| `CHANGELOG.md` | 新增 v1.9.2 段落 |

---

## 🧪 测试

### 用例 1：选 `gpt-image-1` 启动 Agent
- 入口预检命中 → 弹 alert → 阻止启动 ✅

### 用例 2：选 `flux-pro` 启动 Agent
- 入口预检命中 → 弹 alert → 阻止启动 ✅

### 用例 3：选 `claude-sonnet-4` 启动 Agent + PolyHaven 模式
- 入口预检不命中 → 正常进入 plan 阶段 → 生成 JSON 成功 ✅

### 用例 4：边缘情况 —— 模型名很普通（如 `unknown-model-v1`）但中转 API 实际指向图像模型
- 入口预检不命中 → 进入 plan 阶段 → 中转 API 返回 `[NO_IMAGE]` → 兜底防御命中 → 弹出针对性引导 ✅

---

## 🚀 下一步（新会话）

打开新会话直接执行：

```bash
cd /Users/Apple/Desktop/ai-chat && npm run build:mac
```

打包成功后 `dist/白歌的AI讨论组-1.9.2-arm64.dmg` + `dist/白歌的AI讨论组-1.9.2-x64.dmg`。
