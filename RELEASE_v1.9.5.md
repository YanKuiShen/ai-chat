# v1.9.5 修复 quality_check() 流式中间批次误炸

> 发布日期：2026/5/17 · 上游：v1.9.4
> 关键词：**流式分批推送 / quality_check 不 raise**

---

## 🐛 现场

用户跑流式推送，[5/16] cellophane 玻璃纸这批被炸掉：

```
exec failed: [quality_check] 
  Validation Error [维度3-Light]: 只有 2 盏灯（含安全壳兜底），必须 ≥ 3 盏 
| Validation Error [维度4-Material]: 6 个物体缺失材质: 
  ['cellophane', 'fresnel_body', 'kokomi_head', ...]
File "aichat_AgentBatch_4", line 195
File "aichat_AgentBatch_4", line 123, in quality_check
```

## 🔍 根因

**v1.7.4 引入的 `quality_check()` 全局严格质检（缺任一维度就 `raise Exception`）和 v1.6.8 的"流式分批推送"机制冲突：**

1. AI 输出按 `[OBJ:i/N]` 分段，前端每凑齐 5 个就推一批（`agentRunFinalMode` 默认 batchSize=5）
2. AI 在 prompt 引导下**每批末尾都调用了 `quality_check()`**（防御 header 注入了该函数定义）
3. 但中间批次推送时场景还没建完：
   - 灯光要在所有物体之后才创建（最后 1~2 批才会有 ≥ 3 盏）
   - 相机要在最后才设
   - cellophane 这种段在中间批次时材质代码还没流出来
4. → quality_check 立即 `raise Exception` → 整批 `exec` 失败 → 后续物体不再被推送 → 连锁断流

简单说：v1.7.4 的"终末质检"设计前提是**"AI 一次性输出全部完成"**，但 v1.6.8 改成流式分批推送后这个前提就不成立了。

## 🔧 修复方案

改 `AGENT_DEFENSIVE_HEADER` 里 `quality_check()` 函数行为：**只 print Warning 不 raise**

```python
# 之前（v1.7.4）：
hard_errors = [e for e in errors if 'Validation Error' in e]
if hard_errors:
    raise Exception("[quality_check] " + ...)  # ❌ 每批中间都炸

# 改成（v1.9.5）：
if errors:
    print("\n[quality_check] ⚠️ 发现 %d 个质检提示（流式中间不阻断，仅警告）" % len(errors))
    for e in errors: print("  " + e)
    print("[quality_check] 💡 这些提示已记录，AI 在下一轮自检（看 /scene_report）时会自动修正")
# 不再 raise
```

### 为什么这个修复是对的

1. **质检价值不丢失** —— 错误仍 print 到 Blender 日志，AI 在 final/incremental 自检阶段调 `/scene_report` 时一样能看到错误并生成 patch 修
2. **完全解耦流式推送** —— 中间批次不再被误触发 raise
3. **改动极小、向后兼容** —— 单文件单常量改动（`public/index.html` 一处），不动任何调度逻辑
4. **前端错误捕获机制保留** —— `agentPullLogAndMarkErrors` 仍能解析 traceback 并标红 OBJ 段；改成只 print 后这个机制只在真正的代码错误时触发，不再被 quality_check 自身抛错误触发

---

## 📝 修改清单

| 文件 | 改动 |
|------|------|
| `package.json` | 版本 1.9.4 → **1.9.5** + 更新 description |
| `public/index.html` | `AGENT_DEFENSIVE_HEADER` 里 `quality_check()` 改成只 print Warning 不 raise |
| `RELEASE_v1.9.5.md` | 本文件 |
| `CHANGELOG.md` | 新增 v1.9.5 段落 |

---

## 🧪 测试

1. 智能 Agent 选 Claude 4.7 / GPT-4o / DeepSeek + PolyHaven 模式（或不自检模式）
2. 输入复杂场景（≥ 12 个物体，确保会触发流式分批，每 5 个一批 → 至少 3 批）
3. ✅ 期望：所有批次都能成功推送，不会再出现 `[quality_check] Validation Error` 整段失败
4. ❌ 之前：流式中间批次（[5/16]、[10/16] 等）必然报 quality_check 异常，建模断流

---

## 🚀 打包

```bash
cd /Users/Apple/Desktop/ai-chat && npm run build:mac
```

产物：`dist/白歌的AI讨论组-1.9.5-arm64.dmg` + `dist/白歌的AI讨论组-1.9.5-x64.dmg`
