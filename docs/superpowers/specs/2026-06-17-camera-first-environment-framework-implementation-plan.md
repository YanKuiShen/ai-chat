# Camera-first Environment Framework Implementation Plan

## 范围

本计划只覆盖 Phase 2：旁路验证。目标是在不重构现有“开始实时建模”主流程的前提下，新增一个可独立运行的框架层：

1. 用户选择参考图和文字需求。
2. 前端按节点配置模型。
3. Vision Lead 生成 `reference_analysis.json`。
4. Scene Planner 生成 `camera_locked_scene_plan.json`。
5. 两份 JSON 保存到 workspace，供用户查看，也为后续接入 MCP Agent 做准备。

暂不改脚本大师、MCP Agent、混元3D、素材库执行逻辑。

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
    visionLead: { configId: '', model: '', recommended: '' },
    scenePlanner: { configId: '', model: '', recommended: '' },
    mcpExecutor: { configId: '', model: '', recommended: '' },
    cameraQaCritic: { configId: '', model: '', recommended: '' }
  },
  referenceAnalysis: null,
  scenePlan: null,
  lastRunAt: null
}
```

第一阶段只实际调用 `visionLead` 与 `scenePlanner`。`mcpExecutor` 和 `cameraQaCritic` 先显示配置，作为后续接入点。

## UI 改动

在智能 Agent 实时渲染面板中新增一个折叠区：

标题：`相机优先环境框架（旁路验证）`

内容：

- 模式说明：先生成框架 plan，不直接改 Blender。
- 四个节点配置卡：
  - Vision Lead：推荐 Claude Opus 4.8 / Gemini 3.1 Pro。
  - Scene Planner：推荐 GPT-5.5 / Claude Opus 4.8。
  - MCP Executor：推荐 GPT-5.5 / Claude Sonnet 系列。
  - Camera QA Critic：推荐 Claude Opus 4.8 / Gemini 3.1 Pro。
- 每个节点包含 API 下拉、模型下拉、能力要求说明。
- 按钮：
  - `生成参考图分析`
  - `生成相机锁定计划`
  - `保存到工作目录`
- 结果预览：
  - `reference_analysis.json`
  - `camera_locked_scene_plan.json`

UI 文案用中文。给 AI 的 prompt 可以用英文。

## Workspace 输出

如果当前没有 `agentState.workspaceSession`，运行前创建一个 session。

写入：

- `framework/reference_analysis.json`
- `framework/camera_locked_scene_plan.json`
- `framework/workflow_model_profile.json`
- `framework/notes.md`

写文件使用现有 `/api/workspace/file/write`。

## Vision Lead 调用

输入：

- 用户场景描述。
- 第一张参考图，后续可扩展多图。
- 当前镜头安全余量默认值。

输出必须是 JSON：

```json
{
  "image_summary": "",
  "lens": {
    "estimated_focal_length_mm": 0,
    "fov_deg": 0,
    "distortion": { "type": "none", "strength": 0 }
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
    "color_temperature": ""
  },
  "risk_flags": []
}
```

Prompt 重点：

- 估计参考图镜头和透视。
- 找画面层次和地平线。
- 标记投影、接影、遮挡、接触、视差风险。
- 不生成 Blender 代码。
- 不直接建议完整真实建模。
- 输出严格 JSON。

## Scene Planner 调用

输入：

- 用户场景描述。
- `reference_analysis.json`。
- 默认安全余量。
- 投影安全规则。

输出必须是 `camera_locked_scene_plan.json`：

- `intent`
- `camera`
- `lighting`
- `layers`
- `qa`

Prompt 重点：

- 先匹配 Blender 相机焦距、FOV、sensor 和畸变策略。
- 每层必须标记 `zone: true_geometry | illusion`。
- `true_geometry` 层必须给出能投影/接影的建造方法。
- `illusion` 层必须给出外扩和隐藏边缘策略。
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
- Vision Lead 返回非 JSON：尝试提取最外层 `{...}`，失败则提示重试。
- Scene Planner 返回缺字段：前端做轻量 schema 校验并列出缺失字段。
- workspace 写入失败：UI 显示 JSON 结果，但提示未落盘。
- 模型不支持图片：提示用户更换 Vision Lead 模型。

## 测试

手动测试：

1. 山景参考图 + “做可用于摄影后期的大环境”。
2. 室内窗边参考图 + “保留人物合成空间”。
3. 无参考图，只有文字需求。
4. Vision Lead 选择无视觉能力模型，确认警告。
5. 生成后检查 workspace 文件存在且 JSON 可解析。

验收：

- 能生成 `reference_analysis.json`。
- 能生成 `camera_locked_scene_plan.json`。
- `true_geometry` 层不会被计划为纯贴片。
- plan 中包含镜头焦距、畸变、安全余量。
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
