# Realtime Render Node Workflow Implementation Plan

## Scope

本计划只覆盖智能 Agent 实时渲染的新节点式工作流。旧 Drawflow、一键 3D 建模、PS 辅助、普通聊天、营销页不进入本轮实现范围。

目标是把 `photo-agent3d-view` 从旧的自由 MCP Agent 循环，逐步改成严格编排的实时渲染节点运行时。旧代码只复用 API、Blender 工具、Hunyuan、截图、日志和工作目录能力。

权威设计文档：

- `docs/superpowers/specs/2026-06-17-realtime-render-node-workflow-design.md`

## Current Implementation Status

As of 2026-06-17, the new realtime node workflow is partially implemented in `public/index.html` and `server.js`.

Implemented:

- Runtime mode is fixed to `node-workflow` for realtime rendering. Legacy realtime Agent UI is hidden and its side effects are disabled.
- Global image size: `1K / 2K / 4K`.
- White-matte threshold: default `80`, persisted in `agentState_v184`.
- Realtime workflow model slots:
  - Image Model 1
  - White Matte Model 1.1
  - Prompt Model A
  - Prompt Model B
  - Image Model 2A
  - Image Model 2B
  - Mask Check LMM
  - Global Planning AI
  - Task Modeler AI
  - Task Check AI
  - Task Revision AI
  - Placement AI
  - Lighting AI
  - White Matte Compare AI
  - Total Revision AI
- Startup preflight checks required model slots before the workflow starts:
  - text input requires Image Model 1 and White Matte Model 1.1
  - image input skips those two slots
  - downstream nodes must be configured before cleanup begins
- Diagnostic dry-run mode:
  - bypasses external image/LLM/Hunyuan/Blender calls
  - still executes the realtime workflow node order, state transitions, artifacts, Split Ledger, task queue, isolation checks, placement, lighting, and white-matte gate
  - skips model-slot preflight only while dry-run is enabled
  - is intended for workflow debugging, not production rendering
  - can be launched from the realtime panel via `文本诊断` or `图片分支诊断`, or from DevTools via `window.rtwRunDiagnosticSelfTest()` / `window.rtwRunImageInputDiagnosticSelfTest()`
- Workflow requirement audit:
  - generated after Phase 8 white-matte gate passes
  - also generated as a partial report when the workflow fails or is aborted
  - creates a `workflow_requirement_audit` artifact
  - checks the 18 user-defined workflow rules against current run state, node logs, artifacts, Split Ledger, world context, task queue, screenshots, and scores
  - reports `pass / warn / fail` in the realtime workflow log and timeline summary
  - `npm run check:realtime-workflow` now verifies that every `R1` through `R18` is represented in the audit map and that R18 validates all structured contract fields
- Node timeline and node run state.
- Top-level global workflow board:
  - green for completed or legally skipped nodes
  - yellow for waiting nodes
  - blue for the running node
  - red for failed nodes
  - styled as a dark realtime render cockpit with scanline grid, status glow, running-node pulse, one-shot error shake, and reduced-motion fallback
  - grouped by input, split, Hunyuan world, AI task queue, and white-matte gate phases
  - includes startup readiness checks for input type, global image size, white-matte threshold, model slots, and Blender bridge URL
  - includes a Three.js/geometry diagnostic placeholder for future `world_bbox`, `safe_volume`, camera/focal, and AI task queue visualization
  - includes current-node contract fields for inputs, outputs, model, tool, error, revision reason, and score
  - includes visible node runtime logs and node artifact summaries without rendering raw base64 values
- Workflow board snapshots:
  - saved as `workflow_board_snapshot` artifacts
  - can be copied to clipboard
  - can be downloaded as JSON from the board
- Backend realtime workflow ledger:
  - `POST /api/realtime-workflows/snapshot`
  - `GET /api/realtime-workflows`
  - `GET /api/realtime-workflows/:runId`
  - stores lightweight run snapshots in `data/realtime_workflows`
  - filters large artifact values and keeps only artifact IDs, metadata, and summaries
  - run IDs use millisecond timestamp plus a random suffix to avoid overwriting runs started in the same second
  - keeps only the newest 200 realtime workflow runs and prunes old `rtw_*` run directories without touching user asset libraries or app configuration
  - selected historical runs can be reviewed from the board with node status grid, historical artifact summaries, and historical log summaries
  - diagnostic dry-runs flush the snapshot, refresh the run list, and load the just-written run to prove the replay chain is closed
- Node run state records model slots for AI calls, MCP tool metadata for Blender calls, and check scores for inspection nodes.
- AI model slots now have explicit personas embedded into prompts:
  - every persona defines role, operating stance, responsibilities, hard boundaries, output discipline, and failure bias
  - image, vision, text, Blender-code, check, placement, lighting, white-matte, and revision nodes all inject the matching persona into model context
  - personas keep pre-white-matte work focused on geometry, scale, placement, basic light, and auditability rather than texture/final-render styling
- `npm run check:realtime-workflow` validates the realtime-only path, including inline script syntax, legacy UI hiding, node graph coverage, board rendering markers, ledger persistence, artifact summary safety, retry evidence, dry-run branches, image input skips, and reference-guided image generation.
- Cleanup node through `/api/mcp/call` `exec_python` with a realtime-workflow namespace cleanup for `RTW_` / `AI_TASK_` Collections, transient datablocks, and `rtw_` scene state.
- Cleanup does not touch user asset library files or persisted app/API configuration.
- Input router:
  - image input is normalized by global image size
  - smaller images are not enlarged or recompressed
  - text input routes to Image Model 1
- Realtime reference image upload preserves the original data URL up to a 4K max side; the actual `1K / 2K / 4K` normalization happens inside the workflow input router.
- Text-to-initial-reference image node.
- White-matte seed image node is reference-guided from `initial_reference_image`, not regenerated from text alone.
- Prompt A node is vision-guided from the current reference image.
- Image 2A node is reference-guided from the current reference image and Prompt A clean-image prompt.
- Prompt B node is vision-guided from the current reference image and explicitly receives Prompt A output.
- Image 2B node is reference-guided from the current reference image and Prompt B reference prompt.
- Split Ledger initialization with ownership, masks, reasons, branch image artifact IDs, and AI task queue.
- Mask Interlock check now has two layers:
  - structure-level checks for missing ids, missing masks, duplicate masks, and complete-object violations
  - LMM visual checks over the source reference image, Hunyuan clean image, and AI task reference image before Hunyuan starts
- `/api/generate-texture` supports `style: "raw"` so workflow image nodes do not inherit texture/PBR suffixes.
- Hunyuan world generation from Image 2A clean image through `/api/hunyuan/generate`.
- Hunyuan GLB import into a dedicated Blender Collection with a run-specific object prefix.
- World measurement after import:
  - `world_bbox`
  - `camera`
  - `focal_length`
  - `safe_volume`
- Global Planning AI runs only after world measurement and rewrites/freezes the sequential AI task queue.
- Sequential AI task execution:
  - each task runs in order
  - each task uses a unique `task_id`
  - each task uses a unique `object_prefix`
  - each task uses a dedicated Blender Collection
  - generated objects are forced into the task Collection
  - objects without the task prefix are renamed with the prefix
  - generated Python is preflight-blocked if it tries to add particles, volume/fog/atmosphere, image textures, PBR/PolyHaven maps, displacement, or compositor nodes before white-matte approval
- Task isolation check:
  - hides Hunyuan and other AI task Collections
  - keeps only the current task Collection and camera visible
  - captures a screenshot at the global workflow image size
  - sends the screenshot to the task check model
  - locks the task only when the check passes the threshold
- Local task revision loop:
  - failed checks call the local revision model
  - revision is scoped to the current task Collection
  - default max revisions: `2`
- Placement AI:
  - runs after all AI tasks are locked
  - may only adjust existing AI task object transforms
  - must not edit Hunyuan world geometry or add final render effects
- Basic Lighting AI:
  - runs after placement
  - may only add/adjust basic lights, world color, clipping, shadows, and matte-friendly render settings
  - must not add particles, atmosphere, PBR texture detail, or final render mood
- Final white-matte comparison:
  - captures the current white-matte scene at the global workflow image size
  - compares it against the white-matte baseline when available, otherwise the normalized input/reference image
  - uses the customizable white-matte threshold
  - asks the independent Total Revision AI node for a revision plan if the score is below threshold
  - can route one bounded global revision loop back through Global Planning AI and the sequential AI task queue
  - stops if the white-matte score is still below threshold after the bounded revision loop

## Skill Loading Recommendations

GitHub survey notes:

- OpenAI's public `openai/skills` catalog defines the Codex-compatible skill shape: a skill is a folder with `SKILL.md` plus optional scripts, references, assets, and agents.
- Public Three.js skill packs split useful browser 3D expertise into scene graph, renderer, geometry, materials, loaders, lighting, shadows, performance, R3F, and optimizer skills.
- Blender MCP / Blender web pipeline skills are most relevant where nodes need `bpy`, GLB/glTF export/import, scene hierarchy inspection, material survival, and timeout-safe automation.
- Computer vision / SAM-style skills are relevant to split/mask nodes, especially where mask hints need stronger segmentation or visual conflict diagnostics.

Recommended node mapping:

- `hunyuan_world`: load `blender-mcp` / `blender-web-pipeline` skills for import, dedicated Collection creation, GLB sanity checks, and Blender automation.
- `measure_world`: load `threejs-webgl` + `threejs-geometry` for future browser-side bbox, safe_volume, camera frustum, and scale diagnostics; load `blender-mcp` for authoritative Blender measurement.
- `global_planner`: load `threejs-geometry` for task bbox/safe-volume visualization rules, but keep final task queue decisions in the node persona and measured Blender context.
- `task_modeling` and `task_revision`: load `blender-mcp` for isolated `bpy` generation and Collection/object-prefix discipline; use `threejs-geometry` only for diagnostic previews, not final Blender generation.
- `task_collection` and `task_isolation_check`: load `blender-mcp` for visibility isolation and screenshots; load `threejs-webgl` for future lightweight Collection preview and camera-frustum overlays.
- `placement`: load `threejs-geometry` for bbox/contact/safe-volume reasoning and `blender-mcp` for actual transform application.
- `basic_lighting`: load focused Three.js lighting/shadow knowledge only for preview diagnostics; actual node must stay in matte-safe Blender lighting.
- `white_matte_compare`: load computer-vision / image comparison / segmentation skills for future difference overlays, but keep LMM scoring bound to global image size and white-matte rules.
- `prompt_a`, `prompt_b`, `split_ledger`, and `mask_interlock`: load computer-vision/SAM-style skills when mask hints need segmentation rigor; otherwise keep them as LMM-led ledger/audit nodes.
- `react-three-fiber`: defer until the frontend moves from `public/index.html` to React. It is not recommended for the current static frontend path.

Not yet implemented:

- Pixel-level raster mask IoU/intersection checks. The LMM visual mask interlock is implemented; precise pixel masks can be added later when masks are materialized as image artifacts.
- Post-white-matte stages: PBR textures, particles, atmosphere, final render lighting, final composite.

## Existing Entry Points

主要现有入口：

- UI 容器：`public/index.html` 的 `photo-agent3d-view`
- 旧状态：`agentState`
- 旧启动：`agentStartRun()`
- 旧清场：`agentClearBlenderForNewScene()`
- 旧 MCP 循环：`agentRunMCPMode()`
- LLM 调用：`m3dCallLLM(...)`
- 生图代理：`server.js` `/api/generate-texture`
- Hunyuan 代理：`server.js` `/api/hunyuan/generate`
- Blender MCP 代理：`server.js` `/api/mcp/call`
- Workspace：`server.js` `/api/workspace/*`

## Implementation Strategy

采用渐进替换：

1. 保留现有实时渲染 UI 外壳。
2. 新增 `realtimeWorkflowState` 和 helper，不直接把新状态塞进旧 MCP messages。
3. 先让 `agentStartRun()` 能进入新 runner shell，并完成清场、输入路由、图片基准和节点日志。
4. 再逐步接入 Split Ledger、Hunyuan 世界、测量、AI task queue。
5. 旧 `agentRunMCPMode()` 代码暂时保留为能力库，但实时渲染入口固定进入新 node workflow。

这样可以随时用一个 feature flag 或生成方式选项回退到旧实时渲染。

## Phase 1: Runtime Shell

### Goals

- 新增实时渲染专用状态。
- 新增全局图片尺寸和白膜阈值。
- 新增节点日志和 artifact registry。
- 新增清场节点。
- 让启动按钮进入新 workflow shell，但不删除旧 Agent 代码。

### Frontend Changes

In `public/index.html`:

- Add:
  - `let realtimeWorkflowState = createRealtimeWorkflowInitialState();`
  - `createRealtimeWorkflowInitialState()`
  - `rtwGetGlobalSettingsFromDom()`
  - `rtwSetNodeStatus(nodeId, status, patch)`
  - `rtwAppendLog(nodeId, level, message, extra)`
  - `rtwRegisterArtifact(type, value, meta)`
  - `rtwRenderTimeline()`
  - `rtwRunWorkflow()`
- Add UI controls inside `photo-agent3d-view`:
  - Global image size: `1K / 2K / 4K`
  - White matte threshold: default `80`
- Runtime mode: fixed `New node workflow`
- Add a compact node timeline panel showing the authoritative node list.

### Startup Behavior

`agentStartRun()` should:

1. Save existing UI state.
2. Force `agentState.realtimeWorkflowMode = "node-workflow"`.
3. Call `rtwRunWorkflow()`.

### Cleanup Node

`rtwRunCleanupNode()` should:

1. Read Blender URL from global settings.
2. Call `/api/mcp/call` with `exec_python` and a scoped namespace cleanup script.
3. Remove only `RTW_` / `AI_TASK_` Collections, transient RTW datablocks, and `rtw_` / `aichat_rtw_` scene state.
4. Log removed objects / collections.
5. Never touch `data/asset_library`, `data/configs.json`, asset index, PolyHaven cache, or user files.

### Verification

- Starting node workflow creates a `runId`.
- Cleanup node appears in timeline.
- If Blender is connected, cleanup writes `ok`.
- If Blender is offline, cleanup fails with clear error and workflow stops before generation.
- Global image size and threshold are persisted with realtime workflow state.

## Phase 2: Input Router and White-Matte Baseline

### Goals

- Implement text/image input split.
- Enforce global image size.
- Text input creates `initial_reference_image`.
- Text input then creates `white_matte_image`.
- Image input skips image model 1 and normalizes input image.

### UI Changes

Add or adapt controls in realtime panel:

- Input mode display: automatic from scene text + reference image presence.
- Image Model 1 config/model.
- Image Model 1.1 config/model.
- Artifact preview strip:
  - initial reference image
  - white matte baseline
  - normalized input image

### Node Functions

- `rtwRunInputRouterNode()`
- `rtwRunTextToInitialReferenceImageNode()`
- `rtwRunWhiteMatteSeedImageNode()`
- `rtwRunNormalizeInputImageNode()`

### API Usage

Use existing `/api/generate-texture`.

Mapping:

- `1K` -> `1024x1024`
- `2K` -> `2048x2048`
- `4K` -> `4096x4096`

Rules:

- Use `withoutEnlargement` behavior where resizing is local.
- Do not add per-node size selectors.

### Prompt Notes

Internal prompts can be English.

Image Model 1 should create the initial target image from text.

Image Model 1.1 should create a white/clay/matte interpretation based on Model 1 output, preserving composition and object silhouette.

### Verification

- Pure text run never calls image normalization first.
- Pure text run produces `initial_reference_image`.
- Pure text run produces `white_matte_image` from `initial_reference_image`.
- Image run does not call Image Model 1.
- Any screenshot or generated image used by checks has max side matching global image size.

## Phase 3: Split Ledger

### Goals

- Implement sequential Prompt A -> Image 2A -> Prompt B -> Image 2B.
- Prompt B must receive Prompt A outputs.
- Create Split Ledger and mask interlock check.

### UI Changes

Add node config cards:

- Prompt Model A
- Image Model 2A
- Prompt Model B
- Image Model 2B
- Mask Check LMM

Add Split Ledger panel:

- Region/object name
- Owner: `hunyuan` or `ai`
- Mask artifact
- Reason
- Confidence
- Conflict status

### Node Functions

- `rtwRunImageSplitRouterNode()`
- `rtwRunPromptModelANode()`
- `rtwRunHunyuanCleanImageNode()`
- `rtwRunPromptModelBNode()`
- `rtwRunAITaskReferenceImageNode()`
- `rtwRunSplitLedgerNode()`
- `rtwRunMaskInterlockCheckNode()`
- `rtwRunMaskVisualInterlockNode()`

### Verification

- Prompt B cannot run if Prompt A output is missing.
- Split Ledger is written even if conflicts exist.
- Structure or LMM visual mask conflicts stop before Hunyuan world generation unless user explicitly retries after revision.

## Phase 4: Hunyuan World and Measurement

### Goals

- Generate Hunyuan world from clean image.
- Import into Blender as a dedicated world Collection.
- Measure bbox, camera, focal length, and safe volume.

### Node Functions

- `rtwRunHunyuanWorldGenerationNode()`
- `rtwRunImportHunyuanWorldNode()`
- `rtwRunMeasureWorldContextNode()`

### API Usage

- Hunyuan: `/api/hunyuan/generate`
- Blender import: `/api/mcp/call` `exec_python` or an existing import helper.
- Measurement: `/api/mcp/call` `get_scene_info` and `get_object_info`.
- Collection: `/api/mcp/call` `create_collection`.

### Verification

- Hunyuan world objects are in a known Collection.
- `worldContext.worldBBox` exists.
- `worldContext.camera` exists or a clear missing-camera error is logged.
- AI task planner is blocked until measurement succeeds.

## Phase 5: Sequential AI Task Queue

### Goals

- Global planner creates ordered AI modeling tasks.
- Tasks run strictly one by one.
- Each task has `taskId`, prefix, and Collection.
- Task check isolates the current Collection.

### Node Functions

- `rtwRunGlobalPlanningNode()`
- `rtwRunTaskQueueNode()`
- `rtwRunSingleTaskModelingNode(task)`
- `rtwRunTaskIsolationCheckNode(task)`
- `rtwRunLocalTaskRevisionNode(task)`
- `rtwRunTaskLockNode(task)`

### Task Shape

```js
{
  taskId,
  title,
  objectPrefix,
  collectionName,
  targetMask,
  referenceCrop,
  bboxHint,
  dependencies,
  status,
  checkScores,
  logs
}
```

### Modeling Rules

- Complete object first.
- Do not split one tree into trunk / branches / leaves tasks.
- Any object that casts shadows, receives shadows, projects, or occludes must be modeled as one complete object task.
- Task modeling may only create or modify objects with its prefix and Collection.

### Isolation Check

Before check:

- Hide Hunyuan world Collection.
- Hide all other task Collections.
- Show current task Collection.
- Show camera and required references.
- Capture screenshot at global image size.

After check:

- Restore visibility according to workflow state.

### Verification

- Two AI modeling tasks never run at the same time.
- Each object created by a task uses the prefix.
- Each task has a Collection.
- Check screenshot only contains current task and necessary references.
- Below-threshold task loops to local revision.
- Above-threshold task locks and queue advances.

## Phase 6: Placement, Basic Lighting, White-Matte Gate

### Goals

- Run placement after all tasks lock.
- Run basic lighting after placement.
- Run final white-matte comparison before texture/particle/atmosphere/final render.

### Node Functions

- `rtwRunPlacementAINode()`
- `rtwRunBasicLightingAINode()`
- `rtwRunWhiteMatteCompareNode()`
- `rtwRunGlobalRevisionNode()`

### Rules

- Placement AI is independently configurable.
- Lighting AI is independently configurable.
- Basic lighting can set only geometry-adjacent light/shadow setup.
- Before white-matte pass, do not add:
  - particles
  - air perspective
  - complex materials
  - PBR textures
  - final render mood

### Verification

- White-matte threshold defaults to 80.
- Threshold is editable in UI and state.
- Failed white-matte comparison loops to global revision, not texture.
- Passed white-matte comparison unlocks post-white-matte nodes.

## Phase 7: Post White-Matte Nodes

These are visible in the graph but can remain disabled until white-matte passes:

- Texture node.
- Particle scatter node.
- Atmospheric perspective node.
- Final render lighting node.
- Final composite check.
- Completion output.

Initial implementation can show them as locked placeholders.

## File Organization

The first pass may stay in `public/index.html` to reduce churn, but new functions should be grouped under clear comments:

```js
// ==================== Realtime Node Workflow v1 ====================
```

Once stable, move to separate frontend files:

- `public/realtime-workflow/state.js`
- `public/realtime-workflow/runtime.js`
- `public/realtime-workflow/nodes.js`
- `public/realtime-workflow/ui.js`

No split should happen before the runtime is working, because current app packaging is single-file oriented.

## Workspace Outputs

Use current workspace APIs to write:

- `realtime/run_manifest.json`
- `realtime/global_settings.json`
- `realtime/node_runs.jsonl`
- `realtime/split_ledger.json`
- `realtime/task_queue.json`
- `realtime/world_context.json`
- `realtime/artifacts/*.json`
- `realtime/logs/*.jsonl`

Image artifacts can initially remain base64 in state for UI preview, but durable references should move toward workspace files once the runner stabilizes.

## Test Plan

Static checks:

- Search for accidental changes to old Drawflow or PS modules.
- Confirm `data/asset_index.json` is not modified by this work.
- Confirm global size options are exactly 1K / 2K / 4K.

Runtime smoke tests:

1. Launch app.
2. Open realtime render panel.
3. Select `node-workflow` mode.
4. Set global image size to 1K.
5. Run with Blender offline:
   - Cleanup node fails clearly.
   - No generation node runs after failure.
6. Run text input with a configured image model:
   - Initial reference image appears.
   - White matte baseline appears.
   - Node logs show model and outputs.
7. Run image input:
   - Image Model 1 is skipped.
   - Normalized image artifact appears.
8. Run Prompt A/B:
   - B log contains A output reference.
   - Split Ledger appears.

Blender integration tests:

- Connected Blender clear scene removes old objects.
- Hunyuan import creates/uses world Collection.
- Measurement node records bbox and camera/focal length.
- Task isolation toggles Collection visibility correctly.

## Rollback

- Keep legacy Agent mode available until Phase 6 passes.
- Feature flag:

```js
agentState.realtimeWorkflowMode = "node-workflow" | "legacy"
```

- If a phase breaks, users can switch back to `legacy` without losing existing Agent state.

## First Code Change Checklist

1. Add state constructor and helpers.
2. Add runtime mode, image size, threshold controls.
3. Add timeline renderer.
4. Add `rtwRunWorkflow()`.
5. Add cleanup node.
6. Gate `agentStartRun()` through runtime mode.
7. Verify legacy mode still calls old flow.
8. Verify node mode stops after cleanup if later nodes are not implemented yet.
