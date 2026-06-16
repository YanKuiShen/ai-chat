# Camera-first Environment Framework Implementation Plan

## 范围

本计划只覆盖 Phase 2：旁路验证。目标是在不重构现有“开始实时建模”主流程的前提下，新增一个可独立运行的框架层：

1. 用户选择参考图和文字需求。
2. 前端按节点配置模型。
3. 用户可选填或锁定焦距。
4. Vision Lead 生成 `reference_analysis.json`。
5. Scene Planner 生成 `camera_locked_scene_plan.json`。
6. 所有关键判断和错误写入明确日志。
7. JSON 和日志保存到 workspace，供用户查看，也为后续接入 MCP Agent 做准备。

暂不改脚本大师、MCP Agent、混元3D、素材库执行逻辑。
完整节点图 UI 放到 Phase 4 重构，本阶段先按节点模型组织状态、配置和日志，避免后续迁移成本。

## 现有基础

可以复用：

- `agentState.referenceImages`：现有智能 Agent 参考图数组。
- `agentState.multiRole`：现有 Planner / Modeler / Critic 多角色配置思路。
- `/api/configs/:id/models`：模型列表。
- `/api/model-capability/test` 与 `modelCapabilities`：能力检测。
- `m3dCallLLM(...)`：现有前端 LLM 调用。
- `/api/workspace/create-session` 与 `/api/workspace/file/write`：workspace 落盘。
- 场景匹配器 `smState` 的双模型选择 UI 模式：可作为节点配置 UI 参考。

需要新增的是更细颗粒度的节点配置和两段结构化 JSON 生成。

## 新增前端状态

在 `agentState` 下新增：

```js
cameraFramework: {
  enabled: false,
  profileName: 'high_quality_environment',
  nodes: {
    visionLead: { configId: '', model: '', recommended: '', visionEnabled: true, optional: false },
    scenePlanner: { configId: '', model: '', recommended: '', visionEnabled: false, optional: false },
    blenderCameraVisionCheck: { configId: '', model: '', recommended: '', visionEnabled: true, optional: true },
    atmosphereRefiner: { configId: '', model: '', recommended: '', visionEnabled: false, optional: true },
    shadowSoftnessRefiner: { configId: '', model: '', recommended: '', visionEnabled: true, optional: true },
    mcpExecutor: { configId: '', model: '', recommended: '', visionEnabled: false, optional: false },
    cameraQaCritic: { configId: '', model: '', recommended: '', visionEnabled: true, optional: false }
  },
  nodeRuns: [],
  referenceAnalysis: null,
  scenePlan: null,
  lastRunAt: null
}
```

第一阶段只实际调用 `visionLead` 与 `scenePlanner`。`blenderCameraVisionCheck`、`atmosphereRefiner`、`shadowSoftnessRefiner`、`mcpExecutor` 和 `cameraQaCritic` 先显示配置，作为后续接入点。

## UI 改动

在智能 Agent 实时渲染面板中新增一个折叠区：

标题：`相机优先环境框架（旁路验证）`

内容：

- 模式说明：先生成框架 plan，不直接改 Blender。
- 四个节点配置卡：
  - Vision Lead：推荐 Claude Opus 4.8 / Gemini 3.1 Pro。
  - Scene Planner：推荐 GPT-5.5 / Claude Opus 4.8。
  - Blender Camera Vision Check：可选，开启后截图 Blender 目标相机画面再让视觉模型复核。
  - Atmosphere Refiner：可选，用于根据 plan 调整空气透视、雾、颗粒和景深策略。
  - Shadow Softness Refiner：可选，开启后截图目标相机，分析影子软硬过渡和接触阴影。
  - MCP Executor：推荐 GPT-5.5 / Claude Sonnet 系列。
  - Camera QA Critic：推荐 Claude Opus 4.8 / Gemini 3.1 Pro。
- 每个节点包含 API 下拉、模型下拉、能力要求说明、是否可选、是否启用视觉增强。
- 可选视觉节点如果开启，必须先从 Blender 获取目标相机截图，再输出 JSON；如果关闭，则直接消费上游结构化 JSON。
- 按钮：
  - `生成参考图分析`
  - `生成相机锁定计划`
  - `保存到工作目录`
- 结果预览：
  - `reference_analysis.json`
  - `camera_locked_scene_plan.json`
- 用户可调参数：
  - 焦距输入：可留空让视觉模型估计，也可手动锁定，例如 24mm / 35mm / 50mm / 85mm。
  - 镜头畸变策略：自动 / 无 / 轻微桶形 / 轻微枕形。
  - 光源策略：自动分析 / 偏硬光 / 偏软光。
  - 空气透视：自动 / 关闭 / 轻微 / 中等 / 强。
- 日志预览：
  - 显示最新 decision log。
- 节点运行历史：
  - 显示每个节点是否启用、是否使用视觉、输入摘要、输出文件、耗时和错误。

UI 文案用中文。给 AI 的 prompt 可以用英文。

## Workspace 输出

如果当前没有 `agentState.workspaceSession`，运行前创建一个 session。

写入：

- `framework/reference_analysis.json`
- `framework/camera_locked_scene_plan.json`
- `framework/workflow_model_profile.json`
- `framework/decision_log.jsonl`
- `framework/node_runs.jsonl`
- `framework/notes.md`

写文件使用现有 `/api/workspace/file/write`。

## 节点运行记录

每个节点运行后追加 `framework/node_runs.jsonl`：

```json
{
  "at": "2026-06-17T12:00:00.000Z",
  "node_id": "shadow_softness_refiner",
  "enabled": true,
  "optional": true,
  "vision_enabled": true,
  "blender_screenshot": "framework/screenshots/shadow_softness_refiner_camera.png",
  "input_files": ["framework/camera_locked_scene_plan.json"],
  "output_files": ["framework/shadow_softness_patch.json"],
  "status": "ok",
  "duration_ms": 12000
}
```

可选视觉节点开启时：

1. 调 Blender 目标相机截图。
2. 将截图和上游 JSON 一起传给节点模型。
3. 输出结构化 JSON patch 或 critique。

可选视觉节点关闭时：

1. 不截图。
2. 直接读取上游 JSON。
3. 输出结构化 JSON 或跳过。
4. 在日志中记录 `vision_enabled: false`。

## Vision Lead 调用

输入：

- 用户场景描述。
- 第一张参考图，后续可扩展多图。
- 当前镜头安全余量默认值。
- 用户输入焦距和畸变策略。如果用户填写焦距，Vision Lead 仍可估计参考图焦距，但不得覆盖用户值。
- 用户光源策略偏好。如果用户选择自动，则 Vision Lead 分析硬光/软光。

输出必须是 JSON：

```json
{
  "image_summary": "",
  "lens": {
    "estimated_focal_length_mm": 0,
    "fov_deg": 0,
    "distortion": { "type": "none", "strength": 0 },
    "confidence": 0
  },
  "composition": {
    "horizon_y_norm": 0,
    "main_silhouette": "",
    "safe_subject_area": { "x": 0, "y": 0, "w": 0, "h": 0 },
    "overscan_recommendation": { "frame": 20, "ground": 30, "background": 40 }
  },
  "depth_layers": [],
  "lighting": {
    "key_direction": "",
    "shadow_direction": "",
    "color_temperature": "",
    "light_quality": "soft",
    "shadow_edge_quality": "soft_transition",
    "recommended_shadow_strategy": ""
  },
  "atmosphere": {
    "air_perspective": "medium",
    "particle_density": "subtle",
    "depth_haze": "misty_distance"
  },
  "risk_flags": []
}
```

Prompt 重点：

- 估计参考图镜头和透视。
- 找画面层次和地平线。
- 标记投影、接影、遮挡、接触、视差风险。
- 分析硬光源还是软光源，以及影子边缘过渡。
- 推荐空气颗粒、空气透视、雾、景深等淡化影子风险的策略。
- 不生成 Blender 代码。
- 不直接建议完整真实建模。
- 输出严格 JSON。

## Scene Planner 调用

输入：

- 用户场景描述。
- `reference_analysis.json`。
- 默认安全余量。
- 用户锁定焦距。
- 投影安全规则。
- 空气透视和软硬光策略。

输出必须是 `camera_locked_scene_plan.json`：

- `intent`
- `camera`
- `lighting`
- `layers`
- `qa`

Prompt 重点：

- 先匹配 Blender 相机焦距、FOV、sensor 和畸变策略。
- 如果用户输入焦距，`lens_matching.source` 必须是 `user_override`，并优先使用用户值。
- 每层必须标记 `zone: true_geometry | illusion`。
- `true_geometry` 层必须给出能投影/接影的建造方法。
- `illusion` 层必须给出外扩和隐藏边缘策略。
- 影子风险高时，必须选择硬光修正或软光淡化策略。
- 需要明确输出空气透视、颗粒、雾、接触阴影策略。
- 输出严格 JSON。

## 能力检查

启动前检查：

- Vision Lead 必须有 `vision` 能力。
- Scene Planner 必须能稳定输出结构化 JSON。
- 后续 MCP Executor 必须有 `tool_calling`。
- 后续 Camera QA Critic 必须有 `vision`。

第一版如果没有能力检测结果，只给警告，不强阻断。

## 错误处理

- 没有参考图：允许只基于文字生成 plan，但提示“镜头估计置信度低”。
- 用户输入焦距无效：提示用户改成数字毫米值，例如 24、35、50。
- Vision Lead 返回非 JSON：尝试提取最外层 `{...}`，失败则提示重试。
- Scene Planner 返回缺字段：前端做轻量 schema 校验并列出缺失字段。
- workspace 写入失败：UI 显示 JSON 结果，但提示未落盘。
- 模型不支持图片：提示用户更换 Vision Lead 模型。

所有错误都要追加到 `framework/decision_log.jsonl`，包括：

- 错误发生在哪个模块。
- 用户输入摘要。
- 模型或接口返回摘要。
- 系统采取的回退策略。
- 是否需要用户手动处理。

## 日志格式

`decision_log.jsonl` 每行一条 JSON：

```json
{
  "at": "2026-06-17T12:00:00.000Z",
  "module": "camera_solver",
  "event": "lens_user_override",
  "level": "info",
  "input_summary": "user focal length 35mm, vision estimated 28mm",
  "decision": "use user focal length",
  "reason": "user override has highest priority",
  "confidence": 1.0,
  "next_action": "generate camera_locked_scene_plan"
}
```

## 测试

手动测试：

1. 山景参考图 + “做可用于摄影后期的大环境”。
2. 室内窗边参考图 + “保留人物合成空间”。
3. 无参考图，只有文字需求。
4. Vision Lead 选择无视觉能力模型，确认警告。
5. 用户输入 35mm 焦距，确认 plan 记录 `source: user_override`。
6. 软光参考图，确认 plan 包含空气透视/颗粒/软阴影策略。
7. 关闭可选视觉节点，确认流程不截图也能生成 plan。
8. 打开可选视觉节点，确认会先请求 Blender 目标相机截图再输出。
9. 生成后检查 workspace 文件存在且 JSON 可解析。
10. 检查 `decision_log.jsonl` 包含焦距、光源、shadow router、错误或成功事件。
11. 检查 `node_runs.jsonl` 包含每个节点的启用状态、视觉状态和输出文件。

验收：

- 能生成 `reference_analysis.json`。
- 能生成 `camera_locked_scene_plan.json`。
- 用户焦距输入能覆盖视觉模型焦距估计。
- `true_geometry` 层不会被计划为纯贴片。
- plan 中包含镜头焦距、畸变、安全余量。
- plan 中包含硬光/软光判断、空气颗粒、空气透视和接触阴影策略。
- 所有关键判断和错误都写入明确日志。
- 可选视觉节点关闭时，系统能直接基于上游 JSON 输出。
- 可选视觉节点开启时，系统会先截取 Blender 目标相机画面再输出。
- 节点运行历史写入 `framework/node_runs.jsonl`。
- UI 能显示每个节点的模型配置和推荐模型。
- 不影响现有 MCP Agent、脚本大师、混元3D按钮。

## 后续接入点

Phase 3 再做：

- MCP Agent 启动时读取 `camera_locked_scene_plan.json`。
- Planner system prompt 注入 plan。
- Modeler 按 layer 执行。
- Critic 按目标相机和安全余量镜头 QA。

Phase 4 再做：

- 重构“开始实时建模”主流程为：
  参考图分析 → 镜头匹配 → 环境分层 → 投影路由 → 执行 → 相机 QA。
- 把固定面板重构为真正的节点图 UI，允许用户增删可选节点、调整顺序、保存节点工作流预设。
