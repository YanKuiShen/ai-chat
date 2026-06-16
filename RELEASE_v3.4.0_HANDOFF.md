# 🚀 v3.4.0 接力任务 — 脚本大师 + MCP Agent 自动串联

> 这是给【下一个对话】的完整接力简报。本次（v3.3.3）已修完脚本生成大师的 SyntaxError 致命 bug，但用户最初提出的"脚本生成大师和 MCP Agent 循环组合"需求**还未实现**。下面是详细背景和接力方案。

---

## 📋 用户原话（最终目标）

> 将脚本生成大师和MCP Anget循环组合在一起，接受命令之后 开始生成脚本，然后进行MCP Agent 循环（生成的脚本被应用于此）

---

## ✅ v3.3.x 已完成的部分

1. **v3.3.2 — 0 命中报错根因修复**
   - 症结：`build.files` 漏打 `scripts/scene-prompts.json` → server 端 list 永远返回 0 个模板
   - 修复：`package.json` 的 `build.files` 加上 `scripts/scene-prompts.json` + 前后端双 fallback 兜底（server 直接返回 fallback:true 标志，前端再加一层 `/api/scene-prompts/list` 兜底）
   - 重打 mac dmg（arm64 + x64），实测验收通过

2. **v3.3.3 — 致命 SyntaxError 修复**
   - 症结：`scene-prompts.json` 让 AI 输出 `<blender_script>...</blender_script>`，但前端 `agentRunScriptMasterMode` 只识别 `<script_master_code>` → 走 fallback 把整段（含标签行）推给 Blender → `SyntaxError on line 130`（那一行是 `<blender_script>`）
   - 修复：前端标签提取扩展到 4 个正则（`script_master_code` / `blender_script` 各两种），并加 `replace` 剥光残留标签行
   - 重打 mac dmg arm64+x64，已部署到 `dist/`

---

## ❌ 还没做的事 — 这是本次接力的核心

### 用户期望的完整工作流

```
用户在「📝 脚本生成大师」radio 模式下点【🎬 开始实时建模】
  ↓
Step 1: 模板匹配 + 加载 system prompt（已实现 ✅）
  ↓
Step 2: LLM 生成 800~1500 行 bpy 脚本（已实现 ✅）
  ↓
Step 3: 推送到 Blender 一次性执行（已实现 ✅）
  ↓
Step 4: 拉日志 → 如有 ERROR 自动 patch 修复（已实现 ✅，但只是 1 轮简单修复）
  ↓
🆕 Step 5: 【新增】自动接入 MCP Agent 循环
   - 把已建好的场景作为"底"
   - 切换到 MCP 模式，喂给 Agent 一段类似的提示：
     "脚本已建好基础场景（含 _CHARACTER_PLACEHOLDER），请先 get_scene_info 看现有物体，
      然后基于用户原始需求 ${desc} 做精细化调整（补缺、修材质、调灯光、加细节）。
      可调任意 MCP 工具，最后 mark_done 收尾"
   - 让 MCP Agent 主循环接管，做 5~30 轮 tool_call 精修
```

### 设计思路

`agentRunScriptMasterMode` 函数（在 `public/index.html` 第 14688 行附近）跑完后，**不要 return**，改为：

1. 把场景描述快照存到 `agentState.mcpInitialDescription` / `mcpInitialReferenceImages`
2. 构造一段 followupUserText，说明"基础场景已用脚本大师建好"
3. 调用 `agentRunMCPMode({ followupUserText, resumeMessages: null })`（不需要 resume 老消息，从零启动 MCP 循环）
4. 这样进度面板会自然切换到 MCP 阶段，工具调用历史也会显示

---

## 🛠 具体实施步骤（给下个对话的 prompt）

### 1. 在 `agentRunScriptMasterMode` 末尾追加 MCP 接力

定位 `public/index.html` 中 `agentRunScriptMasterMode` 函数末尾（搜索 `🎉 脚本生成大师完成`），在该 log 行**之后**插入：

```javascript
  // === v3.4.0：自动接力 MCP Agent 循环做精细化调整 ===
  if (agentState.status === 'aborted') return;
  
  agentAppendReviewLog(`<div style="color:#a78bfa; font-weight:600;">🔗 v3.4.0：自动接力 MCP Agent 循环（基于已生成场景做精修）</div>`);
  agentAppendTimeline('info', '🔗 切换到 MCP Agent 循环阶段');
  
  // 锁定场景需求快照（让 MCP Agent 知道用户的原始意图）
  agentState.mcpInitialDescription = desc;
  agentState.mcpInitialReferenceImages = Array.isArray(agentState.referenceImages) 
    ? agentState.referenceImages.slice() : [];
  
  const followupText = `【背景】用户的场景需求："${desc}"
  
基础场景已经由【脚本生成大师】用模板「${chosen.name}」一次性建好（含 _CHARACTER_PLACEHOLDER 中央占位人像位 + 全套粒子/光/相机），现在轮到你做【精细化调整】。

## 🎯 你的任务

1. **第 1 步必须调 \`get_scene_info\`** 看当前场景的真实物体清单、灯光、相机、材质
2. 对比用户原始需求，找出脚本可能漏掉/不够好的地方：
   - 物体缺失？（如用户提到"樱花树"但脚本没建？→ search_polyhaven_assets + import_polyhaven_model 补）
   - 材质过于程序化？（→ search_polyhaven_textures + apply_polyhaven_texture 换 PBR 真实贴图）
   - 灯光不戏剧化？（→ add_light / update_object 加补光）
   - 比例失调？（→ update_object 调 scale）
3. **每 3~5 个工具调用后用 \`get_viewport_screenshot\` 看效果**
4. 完成时调 \`mark_done\` 退出

## ⚠️ 严禁

- **禁止 clear_scene**（基础场景是脚本大师辛苦生成的，清掉就白干了）
- 禁止重复生成已有物体
- 不要做大改造，只做"锦上添花"的微调（5~15 个工具调用即可）`;
  
  try {
    agentState.status = 'generating';
    agentState.currentRound = 0;
    agentState.builtObjects = 0; // 让 MCP 重新计数
    await agentRunMCPMode({ followupUserText: followupText });
  } catch (e) {
    if (e.name !== 'AbortError' && agentState.status !== 'aborted') {
      agentAppendReviewLog(`<div style="color:var(--danger);">❌ MCP 接力阶段失败：${e.message}</div>`);
      // 不抛错，因为脚本大师阶段已经成功了
    }
  }
```

### 2. ⚠️ 注意点

- `agentRunMCPMode` 当前签名是 `async function agentRunMCPMode(options = {})`，本身就支持 `followupUserText` 参数（v1.11.5 加的，原本给二次截图修复用）
- 当 `options.resumeMessages` 为 null/undefined 时，MCP 主循环会走"全新启动"路径：自己 ping MCP、拉 tool schema、构造完整 system prompt + user message，followupText 会作为 user 内容的一部分
- **关键**：MCP 模式启动时会读 `agentState.configId` / `agentState.model`，所以**用户在脚本大师模式下选的模型必须同时支持 tool calling**（不支持 tool calling 的模型会在 MCP 启动时被预检拦下并弹 confirm 让用户决定）
- `agentState.generationMode` 此时仍是 'script-master'，**不要改成 'mcp'**（避免污染用户的 radio 选择）

### 3. UI 改动建议（可选）

在脚本生成大师的描述里说明这个新行为，让用户预期它不只是单次脚本：
- 找到 radio 那段（搜索 `📝 脚本生成大师 ⭐ NEW`）
- title 改为 `针对单一场景的超高精度模式：脚本大师 800~1500 行一次性生成基础场景 → 自动接力 MCP Agent 做精细化调整 → 完成`

### 4. 测试用例

用户最后报错那段需求："urban_decay_jp_street（日本街道、自动售货机、樱花树）"
- 跑完脚本大师 → 应该看到"🔗 v3.4.0：自动接力 MCP Agent..."
- 然后 MCP 阶段第 1 个工具应该是 `get_scene_info` 看现有 12+ 个物体
- 接下来可能调 `search_polyhaven_textures` 给沥青路面加贴图、`add_light` 加点霓虹光
- 最后 `mark_done` 收尾

### 5. 版本号 bump

- `package.json`：3.3.3 → **3.4.0**
- `CHANGELOG.md`：加一段 `## 3.4.0 (2026-05-20)` 说明
- 欢迎弹窗 key：`hasLaunched_v3.4.0`（如果 banner 文案要更新）

---

## 📂 关键文件 / 行号速查

| 文件 | 关键内容 | 行号 |
|------|---------|------|
| `public/index.html` | `agentRunScriptMasterMode` 函数 | ~14688 |
| `public/index.html` | 函数末尾 `🎉 脚本生成大师完成！` log | ~14820 |
| `public/index.html` | `agentRunMCPMode` 函数定义 | ~15050 |
| `public/index.html` | radio "📝 脚本生成大师" UI | ~3700 |
| `scripts/scene-prompts.json` | 8 个场景模板 | - |
| `server.js` | `/api/scene-prompts/match` + `/list` + `/:id` | ~搜索 scene-prompts |
| `package.json` | `build.files` | - |

---

## 🚦 接力清单（给下个对话 copy-paste）

- [ ] 在 `agentRunScriptMasterMode` 末尾插入 MCP 接力代码（上面 Step 1 的代码块）
- [ ] 测试：手动跑一次脚本大师 → 看是否自动接力到 MCP → 看 MCP 是否调了 get_scene_info
- [ ] （可选）改 radio title 文案说明新行为
- [ ] bump v3.3.3 → v3.4.0，写 CHANGELOG
- [ ] 重打 mac dmg arm64 + x64
- [ ] attempt_completion

---

## 💡 给下个对话的 system 风格提示

> 这是接力 v3.3.x 系列。当前用户的最终诉求是【脚本大师 + MCP Agent 自动串联】。
> 上一对话已修完脚本大师的致命 SyntaxError（v3.3.3），但**串联功能还未实现**。
> 请打开 `RELEASE_v3.4.0_HANDOFF.md` 看完整接力简报，然后实施 Step 1 的代码插入即可。
> 工程量预估：30~60 分钟（含测试 + 打包）。
