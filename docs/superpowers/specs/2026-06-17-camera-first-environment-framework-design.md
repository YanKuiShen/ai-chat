# Camera-first Environment Framework Design

## 目标

实时渲染的环境建模目标不是生成一个完整可绕看的 3D 世界，而是生成一个在目标相机和轻微调整范围内可信的摄影后期环境。

用户给参考图，比如一座山，系统不必完整建出整座山。它需要先匹配参考图的镜头、构图、光影和空间层次，再决定哪些元素必须是真几何，哪些可以用远景贴片、雾、HDRI、matte painting 或低模轮廓制造视觉欺骗。

核心原则：

- 相机优先：先解参考图镜头，再建场景。
- 用户可锁定焦距：视觉模型可以估计焦距，但用户输入的焦距优先级最高。
- 投影安全：参与投影、接影、遮挡、接触或视差的元素必须是真几何。
- 影子风险要被摄影技术吸收：用空气颗粒、空气透视、雾、景深、软硬光源策略降低影子穿帮风险。
- 镜头安全余量：不能只服务一个死镜头，要支持后期轻微平移、裁切、推拉和变焦。
- 节点可配置：所有关键 AI 节点都暴露给前端，用户可以按自己的 API 和最佳模型自由配置。
- 全程明确日志：每个判断、覆盖、失败和回路都要写入可读日志。

## 非目标

- 不在第一阶段重构现有“开始实时建模”主流程。
- 不替换现有脚本大师、MCP Agent、混元3D 和素材库。
- 不追求整座山、整座城市或整套环境在所有角度都真实。
- 不让远景贴片或 HDRI 错误参与主体投影。

## 模块

### 1. Reference Analyzer

由强视觉模型驱动，把参考图解析成结构化摄影信息，而不是直接生成场景 prompt。

输出 `reference_analysis.json`，包含：

- 镜头估计：焦距、FOV、广角/长焦倾向、镜头畸变。
- 构图：地平线、消失点、主体区域、山体/建筑/天空画面占比。
- 深度层：前景、中景、远景。
- 光影：主光方向、影子方向、色温、雾气。
- 风险标记：接影面、投影物、遮挡物、需要视差的区域。

第一版可以使用视觉模型输出结构化 JSON，辅以前端少量可调参数。不要一开始投入复杂 CV 算法。

### 2. Camera Solver

在建模前先把参考图镜头映射到 Blender 相机。

Camera Solver 必须支持用户手动输入焦距。优先级为：

1. 用户锁定焦距。
2. EXIF 或用户提供的镜头信息。
3. 视觉模型估计焦距。
4. 系统默认焦距。

需要设置或记录：

- `camera.data.lens`
- `sensor_width`
- `sensor_fit`
- 目标画幅比例
- 地平线位置
- 参考图焦距估计
- 参考图镜头畸变
- 必要时的后期 lens distortion 参数
- 焦距来源：用户输入、EXIF、视觉估计或默认值
- 焦距置信度与覆盖日志

硬顺序：Reference Analyzer 先估计镜头，Camera Solver 先设置 Blender 相机，之后才允许 Layer Planner 和 MCP Executor 摆几何和远景贴片。

### 2.5 Atmosphere and Shadow Control

影子不只靠几何准确，也要靠摄影语言控制。系统需要先判断参考图更接近硬光还是软光，再选择影子策略。

硬光源适用：

- 晴天直射阳光、舞台聚光、强烈建筑投影。
- 影子边缘清晰，必须更重视真实几何和投影方向。
- QA 要重点检查影子来源、方向和接触阴影。

软光源适用：

- 阴天、雾天、窗边漫射光、森林散射光。
- 影子边缘过渡柔和，可用环境雾和空气透视降低精确投影压力。
- QA 重点检查光色统一和接触阴影可信度，而不是硬边影子精度。

推荐技术：

- 空气颗粒：增加体积雾、漂浮微粒、轻微噪声，降低远景边缘和影子硬穿帮。
- 空气透视：远景降低对比度、饱和度和清晰度。
- 景深：用焦平面控制远景 illusion 层的细节暴露。
- 接触阴影：人物脚底、石头底部、建筑底部必须保留可信暗部。
- 光源软硬控制：根据分析结果设置 area light size、sun angle、volume density 和 shadow softness。

### 3. Layer Planner

把环境拆成前景、中景、远景，并为每层指定用途、画面区域、建造方式和风险。

示例：

- 前景地面：真几何，接收人物/道具影子。
- 中景岩石或树：真几何，提供视差和投影。
- 远山轮廓：视觉欺骗，用低模轮廓、billboard、matte texture、雾。
- 天空和云：视觉欺骗，用 HDRI、云平面、体积雾。

### 4. Shadow Geometry Router

这是安全阀，决定每层是 `true_geometry` 还是 `illusion`。

判为 `true_geometry` 的条件：

- 会接收主体或道具影子。
- 会投影到主体区域、地面或近景。
- 和人物/主体有脚底、手部、坐姿接触关系。
- 挡在主体前面，形成前景遮挡。
- 镜头运动或景深里会产生明显视差。
- 位于画面下半部、近景或中景，且画面占比大。

允许 `illusion` 的条件：

- 超远景，不投影到主体区域。
- 天空、云层、远山轮廓、远处树林或城市剪影。
- 只提供色块、轮廓、氛围和深度感。
- 可被雾、景深、低对比隐藏边缘。
- 不遮挡主体，也不接触主体。

硬性禁止：任何 `true_geometry` 层都不能只用 billboard、纯图片平面或 HDRI 表达。可以低模，可以简化，但必须有能正确投影和接影的几何体。

### 5. MCP Executor

执行层不重新解释参考图，只消费 `camera_locked_scene_plan.json`。

它可以选择：

- 脚本大师：生成大环境底稿。
- bmesh / Geometry Nodes 模板：生成稳定几何。
- PolyHaven / 本地素材库：补近景和中景真实材质、资产。
- 混元3D：只用于镜头中需要近看或互动的复杂物体。
- Blender MCP 工具：布尔、倒角、细分、平滑、灯光、相机、截图和软回滚。

### 6. Camera QA Critic

验收只围绕目标相机和安全余量镜头，不要求所有角度都完美。

检查项：

- 参考图构图相似度。
- 镜头焦距和透视是否一致。
- 山体、建筑、天空在画面中的占比是否合理。
- 前中远景层次是否成立。
- 影子是否有可信来源。
- 脚底或接触面是否稳定。
- 遮挡边缘是否由真实几何支撑。
- 远景贴片是否露边。
- 光色、雾气、景深和对比度是否统一。
- 硬光/软光策略是否匹配参考图。
- 空气颗粒和空气透视是否合理淡化远景和影子风险。
- 用户锁定焦距是否被实际应用。

失败回路：

- 构图失败：回到 Camera Solver。
- 层次失败：回到 Layer Planner。
- 投影失败：回到 Shadow Geometry Router 和 MCP Executor。
- 氛围失败：只调灯光、雾、材质、色调。
- 焦距失败：回到 Camera Solver，优先让用户确认或覆盖焦距。

## 日志

所有关键判断都要写明确日志，方便用户和后续 Agent 追踪原因。

建议写入 `framework/decision_log.jsonl`，每行一条事件：

- `lens_estimated`：视觉模型估计焦距。
- `lens_user_override`：用户输入焦距覆盖估计。
- `camera_solver_applied`：Blender 相机参数被确定。
- `light_quality_detected`：判断硬光源或软光源。
- `atmosphere_strategy_selected`：选择空气颗粒、雾、景深、空气透视策略。
- `shadow_router_decision`：某层被判为 true_geometry 或 illusion。
- `qa_failed`：QA 失败和回路建议。
- `qa_passed`：QA 通过和分数。

日志必须写清：

- 模块名。
- 输入摘要。
- 决策结果。
- 决策理由。
- 置信度。
- 下一步建议。

## 镜头安全余量

系统不能只生成一个固定死镜头。需要生成一个比最终画面稍大的可信区域，方便后期轻微调整。

建议默认：

- 目标画面外扩 15% 到 25%。
- 地面和接影区外扩至少 30%。
- 远景 illusion 层外扩 40%。
- 支持轻微 pan、tilt、dolly、zoom 和 crop。

Camera QA Critic 需要抽查 3 到 5 个轻微偏移镜头，确认不会露出贴片边缘、地面断裂、投影缺失或前景穿帮。

## 核心数据契约

### `reference_analysis.json`

```json
{
  "image_summary": "misty mountain scene with foreground ground and midground ridge",
  "lens": {
    "estimated_focal_length_mm": 28,
    "fov_deg": 65,
    "distortion": { "type": "barrel", "strength": 0.03 }
  },
  "composition": {
    "horizon_y_norm": 0.42,
    "main_silhouette": "mountain ridge in upper-middle frame",
    "safe_subject_area": { "x": 0.34, "y": 0.18, "w": 0.32, "h": 0.62 },
    "overscan_recommendation": { "frame": 20, "ground": 30, "background": 40 }
  },
  "depth_layers": [
    { "id": "foreground_ground", "depth": "foreground", "screen_area": "bottom third" },
    { "id": "midground_ridge", "depth": "midground", "screen_area": "middle band" },
    { "id": "far_mountain", "depth": "background", "screen_area": "upper middle" }
  ],
  "lighting": {
    "key_direction": "upper_left",
    "shadow_direction": "lower_right",
    "color_temperature": "cool_misty_daylight"
  },
  "risk_flags": [
    "foreground_ground_receives_shadow",
    "midground_ridge_needs_parallax",
    "far_mountain_can_be_illusion_with_fog"
  ]
}
```

### `camera_locked_scene_plan.json`

```json
{
  "version": 1,
  "intent": {
    "type": "environment_background",
    "target": "camera_view_illusion",
    "reference_summary": "mountain environment viewed from a fixed camera"
  },
  "camera": {
    "locked": true,
    "target_frame": "16:9",
    "lens_matching": {
      "enabled": true,
      "source": "user_override",
      "reference_lens_class": "wide_standard",
      "user_focal_length_mm": 28,
      "estimated_focal_length_mm": 28,
      "estimated_fov_deg": 65,
      "confidence": 0.72,
      "perspective_character": "slight_wide_angle_foreground_expansion",
      "distortion": {
        "type": "barrel",
        "strength_estimate": 0.03,
        "apply_in_blender": "compositor_lens_distortion_or_post"
      },
      "blender_camera": {
        "lens_mm": 28,
        "sensor_width_mm": 36,
        "sensor_fit": "AUTO"
      }
    },
    "safe_envelope": {
      "enabled": true,
      "frame_overscan_percent": 20,
      "ground_overscan_percent": 30,
      "background_overscan_percent": 40,
      "allowed_adjustments": {
        "pan_deg": 5,
        "tilt_deg": 3,
        "dolly_percent": 8,
        "zoom_percent": 10,
        "crop_percent": 15
      }
    }
  },
  "lighting": {
    "key_direction": "upper_left",
    "shadow_direction": "lower_right",
    "light_quality": "soft",
    "shadow_softness_strategy": "large area light + mist + contact shadows",
    "atmosphere": "misty distance haze",
    "air_perspective": {
      "enabled": true,
      "distance_contrast_falloff": "medium",
      "particle_density": "subtle"
    }
  },
  "layers": [
    {
      "id": "foreground_ground",
      "depth": "foreground",
      "zone": "true_geometry",
      "shadow_interaction": ["receives_shadow", "contact_surface"],
      "build_method": "bmesh terrain + PBR material"
    },
    {
      "id": "midground_ridge",
      "depth": "midground",
      "zone": "true_geometry",
      "shadow_interaction": ["casts_shadow", "parallax"],
      "build_method": "lowpoly mesh + displacement"
    },
    {
      "id": "far_mountain_silhouette",
      "depth": "background",
      "zone": "illusion",
      "shadow_interaction": [],
      "build_method": "billboard/matte plane + fog"
    }
  ],
  "qa": {
    "camera_view_only": true,
    "checks": [
      "reference_composition_match",
      "shadow_source_valid",
      "ground_contact_valid",
      "occlusion_edges_supported",
      "no_visible_billboard_shadow_error"
    ]
  }
}
```

### `workflow_model_profile.json`

```json
{
  "profile_name": "high_quality_environment",
  "nodes": {
    "vision_lead": {
      "config_id": "user_claude_api",
      "model": "claude-opus-4.8",
      "required_capabilities": ["vision", "structured_json"]
    },
    "scene_planner": {
      "config_id": "user_openai_api",
      "model": "gpt-5.5",
      "required_capabilities": ["reasoning", "structured_json"]
    },
    "mcp_executor": {
      "config_id": "user_openai_api",
      "model": "gpt-5.5",
      "required_capabilities": ["tool_calling", "code"]
    },
    "camera_qa_critic": {
      "config_id": "user_claude_api",
      "model": "claude-opus-4.8",
      "required_capabilities": ["vision", "critique"]
    }
  }
}
```

示例里的模型名是推荐默认值，实际运行时由前端 API 配置和用户可用模型决定。

## 前端配置原则

所有关键 AI 调用节点都必须暴露给用户配置：

- Vision Lead
- Scene Planner
- MCP Executor
- Camera QA Critic

每个节点需要：

- API 配置下拉。
- 模型下拉。
- 推荐模型提示。
- 能力要求提示。
- 启动前能力检查。

预设建议：

- 快速
- 高质量
- 省钱
- 本地优先

用户可以一键使用推荐组合，也可以逐节点覆盖。配置随 workspace 落盘。

## 实施路线

### Phase 1：框架定义

完成模块职责、数据契约、投影安全规则、镜头余量规则和 AI 节点颗粒度设计。

### Phase 2：旁路验证

不改现有开始按钮，新增一个旁路能力：输入参考图和文字需求，生成 `reference_analysis.json` 与 `camera_locked_scene_plan.json` 并保存到 workspace。

### Phase 3：接入 Agent

把 plan 注入现有 Planner / Modeler / Critic。先不改工具实现，让 Agent 按 plan 执行。

### Phase 4：重构工作流

最后再把实时渲染主流程改成：

参考图分析 → 镜头匹配 → 环境分层 → 投影路由 → 执行 → 相机 QA。

## 验收标准

- 用户上传山景参考图后，系统能输出结构化 `reference_analysis.json`。
- 系统能生成包含焦距、畸变、安全余量、分层和投影判定的 `camera_locked_scene_plan.json`。
- 用户输入焦距时，plan 必须记录 `source: user_override` 并优先应用。
- 被判定为 `true_geometry` 的层不会被计划为纯贴片。
- 远景可以被计划为 illusion，但必须外扩并有雾/景深/遮挡策略。
- plan 必须包含硬光/软光判断和空气透视/颗粒策略。
- 每次运行必须写入 `framework/decision_log.jsonl`。
- 前端能为每个 AI 节点配置不同 API 和模型。
- QA 能区分构图问题、投影问题、层次问题和氛围问题，并给出回路建议。
