# 人物参考图输入端设计

## 目标

在「智能 Agent 实时渲染」流程里新增一个人物图输入端，让 AI Chat 不再只是生成通用 Blender 场景，而是能围绕真实人物/角色图生成适合后期合成的背景环境。

这个功能服务的是二次元摄影、Cos 摄影、角色图大后期：用户上传一张普通人物图，即使图里有原背景，系统也要提取人物位置、地面关系、构图和光线等关键线索，然后让 Blender Agent 生成匹配的人物背景场景、相机、地面、灯光和渲染分层。

默认原则：人物是后期合成主体，不在 Blender 里重新生成或建模人物。

## 第一版范围

第一版支持「普通有背景人物图」，不是只支持透明 PNG。它通过一个统一入口支持三种构图模式：

- 全身站立：重点识别头顶点、脚底接触点、地面、相机高度、焦距倾向、阴影方向和人物预留区域。
- 半身/特写：重点识别脸部或上半身中心、肩线、焦距倾向、背景纵深、景深空间和光色匹配。
- 坐姿/蹲姿/复杂姿态：重点识别人像 mask、轮廓范围、主要接触面、大致地面/平台关系、前景遮挡可能性和安全背景区域。

第一版采用「自动分析 + 用户轻量校准」模式。自动分析给出起点，用户可以手动修正关键点，避免纯自动在二次元图、Cos 图、复杂背景图上误判。

## 非目标

- 不做完整 PS 替代品。
- 第一版不追求像素级完美抠图。
- 默认不在 Blender 里生成或替换人物。
- 不依赖单一云服务。
- 抠图失败时不阻断实时渲染，仍允许用户用手动点位和视觉模型分析继续。

## 用户流程

1. 用户进入「摄影工具」->「智能 Agent 实时渲染」。
2. 用户在新增的「人物参考图」面板上传人物图。
3. 系统执行背景移除和人物图分析。
4. UI 显示原图、透明人物预览、检测到的人物范围和建议校准点。
5. 用户确认或选择构图模式：全身、半身、复杂姿态。
6. 用户调整关键辅助线/点：
   - 头顶点。
   - 脚底点或主要接触区域。
   - 人物中心线。
   - 可见地平线/地面参考线。
   - 目标画面里的人物放置区域。
7. 系统生成 `character_constraints`。
8. 实时渲染 Agent 启动时，把这些约束注入 MCP prompt，并保存到 workspace。
9. Agent 只生成环境，围绕人物预留区匹配相机、地面、灯光和背景。
10. 完成时输出适合合成的分层渲染：环境层、深度层、阴影层，可选前景遮挡层。

## UI 位置

人物参考图面板放在 `photo-agent3d-view` 内，也就是「智能 Agent 实时渲染」界面里，靠近场景描述和参考图控件。它不应该变成新的顶级模式。

建议面板结构：

- 人物图：上传/拖拽图片、替换图片、清除图片。
- 分析预览：原图、mask/透明人物预览、检测 bbox。
- 构图模式：分段控件，全身 / 半身 / 复杂姿态。
- 校准：在图片上做轻量点位/线条编辑。
- 生成约束：可折叠的 JSON 风格摘要，方便调试。

默认体验要尽量简单：上传图片，看一眼预览，必要时调几个点，然后开始 Agent。

## 数据模型

前端把人物参考图状态保存在 `agentState.characterReference`。

建议结构：

```json
{
  "image": {
    "name": "character.jpg",
    "mime": "image/jpeg",
    "width": 1440,
    "height": 2160,
    "dataUrl": "data:image/jpeg;base64,..."
  },
  "matting": {
    "ok": true,
    "method": "rembg",
    "maskDataUrl": "data:image/png;base64,...",
    "cutoutDataUrl": "data:image/png;base64,..."
  },
  "mode": "full_body",
  "calibration": {
    "headPoint": {"x": 0.51, "y": 0.08},
    "footPoint": {"x": 0.52, "y": 0.92},
    "subjectCenter": {"x": 0.51, "y": 0.49},
    "horizonLine": {"y": 0.42},
    "subjectFrame": {"x": 0.32, "y": 0.08, "w": 0.38, "h": 0.84}
  },
  "constraints": {
    "shotType": "full_body",
    "focalLengthHintMm": 50,
    "cameraHeightHintM": 1.2,
    "cameraAngle": "slightly_low",
    "groundPlane": "visible_floor_contact",
    "reservedSubjectArea": "center",
    "lightingHint": "key from upper left",
    "doNotBuildCharacter": true
  }
}
```

所有点位坐标使用图片空间里的 `0..1` 归一化坐标，这样图片缩放后点位不会失效。

## 后端 API

在 `server.js` 里新增一组小型人物图分析 API。

建议接口：

- `POST /api/character/remove-bg`
  - 输入：图片 base64 或 data URL。
  - 输出：mask PNG、透明人物 PNG、bbox、使用方法、warning。
  - 第一版本地实现：Python helper，优先用 `rembg`。
  - 后续兼容：RMBG、BiRefNet、SAM。

- `POST /api/character/analyze`
  - 输入：原图，可选 mask。
  - 输出：建议模式、bbox、头顶/脚底/接触点/地平线估计、光线说明、焦距倾向。
  - 第一版可以复用现有视觉模型能力，但 UI 不直接感知具体调用方式。

- `POST /api/character/constraints`
  - 输入：自动分析结果 + 用户校准结果。
  - 输出：最终给 Agent 用的 `character_constraints`。
  - 初期也可以放在前端生成，但保留接口边界方便以后升级。

## 抠图策略

使用分层降级策略：

1. 第一版优先接本地 `rembg`，因为它简单、成熟，也常见于 Stable Diffusion WebUI 工作流。
2. 方法名保持通用，后续可以增加 RMBG、BiRefNet、SAM。
3. 抠图失败时返回 `ok:false` 和 warning，但不阻断用户手动校准。

UI 上要把抠图表达成辅助预览，而不是硬性依赖。

## Agent 集成

当存在人物约束时，把它作为高优先级场景约束注入 MCP Agent prompt 和工具循环。

Agent 规则：

- 不创建人物/角色模型，除非用户明确要求生成占位假人。
- 围绕人物预留区构建环境。
- 地面或主要接触面要对齐脚底/接触点。
- 相机取景、焦距倾向、机位高度要匹配人物图。
- 尽量匹配人物图里的光向和色温。
- 人物区域要干净，不要在脸部/身体背后堆太复杂的高对比元素。
- 只在有助于合成时增加前景遮挡物，默认不要遮住人物。
- 优先输出适合 PS 合成的分层：环境层、深度层、阴影层、前景遮挡层。

约束需要保存到 workspace：

- `character_constraints.json`
- 可选 `character_analysis.md`

## Blender 输出预期

全身人物参考图：

- 有地面，并且视觉上能承接人物脚底。
- 相机适合全身/人像构图。
- 人物区域有足够留白。
- 光线方向支持可信的接触阴影。
- 完成后输出渲染分层。

半身/特写人物参考图：

- 背景支持人像构图。
- 相机和纵深更适合上半身画面。
- 脸部/上半身区域不拥挤。
- 光色和整体情绪匹配人物图。

坐姿/蹲姿/复杂姿态：

- 接触面合理。
- 场景有可用的前中后景纵深。
- Agent 不强行精确复刻人体，只围绕合成需求构建环境。

## 错误处理

- 抠图不可用：提示 warning，允许手动校准和 LLM 视觉分析继续。
- 视觉分析不可用：允许用户手动选择模式和点位。
- 全身模式缺少脚底/接触点：开始 Agent 前提示用户补点。
- Blender MCP 不可用：沿用现有 ping 失败逻辑。
- 约束太弱：注入保守默认相机/地面设置，并在 review log 里提示。

## 测试与验收

手动验收：

- 上传一张复杂背景的全身站立人物图，能显示 mask 预览，允许修正头顶/脚底，Agent 能生成地面对齐的场景。
- 上传半身人像，不强制要求脚底点，Agent 生成适合人像背景纵深的场景。
- 上传坐姿/蹲姿图片，用户能标记接触区域，Agent 生成合理接触面。
- 抠图失败时，仍能通过手动点位启动 Agent。
- Agent prompt 里包含 `doNotBuildCharacter: true`。
- workspace 里生成 `character_constraints.json`。
- 完成后生成分层渲染，或明确记录无法生成的原因。

技术检查：

- 没有人物图时，现有实时渲染流程保持不变。
- 现有参考图上传不受影响。
- `agentState` 保存/恢复人物参考信息，但避免重复保存过大的图片数据。
- 大图上传到后端抠图前要压缩/缩放，避免内存暴涨。

## 实现顺序

1. 在 `public/index.html` 添加数据模型和 UI 面板。
2. 添加前端图片上传、预览和校准覆盖层。
3. 添加 `/api/character/remove-bg`，接本地 helper，并做失败降级。
4. 生成约束并保存到 workspace。
5. 把约束注入 MCP Agent prompt。
6. 增加分层渲染期望和 review log 可见性。
7. 增加手动测试用例，并更新 README 或交接文档。

## 仍需决策

- 第一版抠图后端具体用什么：建议从 `rembg` 开始，环境稳定后再加 RMBG/BiRefNet。
- `/api/character/analyze` 是否第一版就调用视觉模型，还是先以手动校准为主。
- 是否在 Blender 中放一个低透明度人物占位平面用于构图预览。默认不做，因为主要目标是生成后期合成背景。
