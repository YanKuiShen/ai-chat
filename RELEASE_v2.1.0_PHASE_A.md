# RELEASE v2.1.0 Phase A — Plan-Execute-Reflect 范式

> **发版时间**：2026-05-18
> **前端版本号**：`package.json` 1.11.14 → **2.1.0**
> **本次范围**：v2.1.0 全套 7 Phase（A~G）的 **Phase A**（Plan-Execute-Reflect 三段循环）
> **Blender 插件**：`aichat_bridge` 仍 2.0.4（本版纯前端，不改插件）

## 🎯 一句话总结

让 MCP Agent 从「**有什么工具调什么工具，最后失忆+撞 30 轮上限**」升级到「**先 plan → 边干边 update → 卡住 reflect → 显式 mark_done 退出**」的可控范式。新增 5 个【**客户端工具**】完全在前端 JS 执行，0 网络往返毫秒返回，治旧版本两大顽疾：长时任务「漂移」和「停不下来」。

## 📦 Phase A 5 个客户端工具

| 工具 | 必传 | 作用 | 时机 |
|---|---|---|---|
| `plan_create` | `goal`, `steps:[{title,intent}]` | 拆 3~8 步骤，重置 `agentState.plan` | **第 1 轮强制** ⭐ |
| `plan_update_step` | `step_id`, `status` | 标进度（pending/in_progress/done/failed/skipped） | 每开始/完成一步 |
| `plan_get` | — | 看完整 plan + stats | 每 3~5 轮 |
| `reflect` | `observations`, `decision` | 记反思日志 | 遇阻时 |
| `mark_done` | `summary` | 唯一退出信号 → 主循环 break | **最后一轮强制** ⭐ |

## 📋 关键代码改动

- `CLIENT_TOOLS` 数组（line 12862）+ `_isClientTool` / `_runClientTool`（12949）
- `_planStats` / `agentPlanRender` / `agentPlanRenderReflections` / `agentPlanClear`（13080~13176）
- `AGENT_PLAN_PROMPT` 注入 system prompt 末尾（13178 + 13555）
- 工具表 `prepend(CLIENT_TOOLS)`（13395）
- 主循环分流 `if (_isClientTool(toolName))`（13719）
- `mark_done` 触发 break（13791~13796）
- UI `#agent-plan-panel` 卡片（1779~1791）
- 欢迎弹窗 `hasLaunched_v2.1.0`

## 🧪 验证

- ✅ JS 语法验证通过 511145 chars
- ✅ 5 工具 + 6 函数 + 4 UI 元素 + 主循环分流 + mark_done break 全部到位

## 📐 兼容性

完全向后兼容；`aichat_bridge` 不变；MCP 模式之外不受影响；现有 16 个 Blender 工具完全保留。

## 🚀 v2.1.0 全套 ROADMAP（Phase B~G 待办）

| Phase | 名称 | 估时 | 状态 |
|---|---|---|---|
| A | Plan-Execute-Reflect 三段循环 | 2 天 | ✅ 本版完成 |
| B | 暴露真·文件系统（`ai-chat-workspace/`） | 2 天 | ⏳ 待办 |
| C | bpy API 实时检索（cheatsheet + 在线 docs） | 1 天 | ⏳ 待办 |
| D | 多角色协作（Planner/Modeler/Critic 各独立 API+模型） | 4 天 | ⏳ ⭐ 核心 |
| E | bmesh / 几何节点模板库（10 个高频模板） | 2 天 | ⏳ 待办 |
| F | aichat_bridge 升级 2.0.4 → 2.1.0 | 1 天 | ⏳ 待办 |
| G | 重打 4 个 dmg/exe + README 重写 | 1 天 | ⏳ 待办 |

## 🎓 接力会话 prompt

```
我在 /Users/Apple/Desktop/ai-chat 项目继续 v2.1.0 Codex CAD 范式重构。
当前已完成 Phase A（Plan-Execute-Reflect 三段循环 + 5 个客户端工具）。
package.json 已 bump 到 2.1.0，CHANGELOG 顶部有完整 [2.1.0] 段，
末尾有 [v2.1.0 ROADMAP] 占位段（Phase B~G 工程蓝图）。
但 dist/ 里还是 v1.11.14 旧包（用户能继续用着，新 Phase A 改动尚未打包）。

任务：实施 Phase B~G。具体要求：
1. 工作目录路径放在 ~/Desktop/ai-chat-workspace/，每个建模 session 一子目录
2. 默认开启多 AI 协作（Planner/Modeler/Critic 三角色），UI 给每角色独立的
   API + 模型下拉，配上推荐模型提示
3. 全套做完不留半成品，每次会话尽量做完 1~2 个 Phase

请先读 CHANGELOG.md 末尾的 [v2.1.0 ROADMAP] + RELEASE_v2.1.0_PHASE_A.md 熟悉
当前状态，然后开干 Phase B（暴露真·文件系统）。
```
