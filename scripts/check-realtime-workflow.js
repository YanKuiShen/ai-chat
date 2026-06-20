#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const htmlPath = path.join(root, 'public', 'index.html');
const serverPath = path.join(root, 'server.js');
const hunyuanServicePath = path.join(root, '3d', 'hunyuan3d_service.py');

const html = fs.readFileSync(htmlPath, 'utf8');
const server = fs.readFileSync(serverPath, 'utf8');
const hunyuanService = fs.existsSync(hunyuanServicePath) ? fs.readFileSync(hunyuanServicePath, 'utf8') : '';

const checks = [];

function check(name, pass, detail = '') {
  checks.push({ name, pass: !!pass, detail });
}

function inlineScriptSyntaxResult() {
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)]
    .map(m => m[1])
    .filter(s => s.trim());
  try {
    scripts.forEach((script, index) => {
      try {
        new Function(script);
      } catch (e) {
        e.message = `inline script #${index + 1}: ${e.message}`;
        throw e;
      }
    });
    return { ok: true, count: scripts.length, error: '' };
  } catch (e) {
    return { ok: false, count: scripts.length, error: e.message || String(e) };
  }
}

function countRequirementDefs() {
  const block = html.match(/const RTW_REQUIREMENT_DEFS = \[([\s\S]*?)\];/);
  if (!block) return 0;
  return [...block[1].matchAll(/\['R\d+'/g)].length;
}

function requirementIds() {
  const block = html.match(/const RTW_REQUIREMENT_DEFS = \[([\s\S]*?)\];/);
  if (!block) return [];
  return [...block[1].matchAll(/\['(R\d+)'/g)].map(m => m[1]);
}

function aiPersonaIds() {
  const block = html.match(/const RTW_AI_PERSONAS = \{([\s\S]*?)\n\};\nconst RTW_IMAGE_TARGETS/);
  if (!block) return [];
  return [...block[1].matchAll(/^\s{2}([a-zA-Z0-9]+): \{/gm)].map(m => m[1]);
}

function countNodeDefs() {
  const block = html.match(/const RTW_NODE_DEFS = \[([\s\S]*?)\];/);
  if (!block) return 0;
  return [...block[1].matchAll(/\['[a-z0-9_]+',/g)].length;
}

function phaseNodeIds() {
  const block = html.match(/const RTW_PHASE_DEFS = \[([\s\S]*?)\];/);
  if (!block) return [];
  const ids = [];
  for (const phase of block[1].matchAll(/\[\s*'[^']+'\s*,\s*'[^']+'\s*,\s*\[([\s\S]*?)\]\s*\]/g)) {
    ids.push(...[...phase[1].matchAll(/'([a-z0-9_]+)'/g)].map(m => m[1]));
  }
  return ids;
}

function functionBody(name) {
  return extractFunctionBody(`function ${name}`);
}

function serverFunctionBody(name) {
  return extractFunctionBody(`function ${name}`, server);
}

function asyncFunctionBody(name) {
  return extractFunctionBody(`async function ${name}`);
}

function extractFunctionBody(marker, source = html) {
  const start = source.indexOf(marker);
  if (start < 0) return '';
  const sigOpen = source.indexOf('(', start + marker.length);
  if (sigOpen < 0) return '';
  let parenDepth = 0;
  let sigClose = -1;
  let quote = '';
  let escaped = false;
  for (let i = sigOpen; i < source.length; i++) {
    const ch = source[i];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (ch === '\\') {
        escaped = true;
      } else if (ch === quote) {
        quote = '';
      }
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch;
      continue;
    }
    if (ch === '(') parenDepth++;
    if (ch === ')') {
      parenDepth--;
      if (parenDepth === 0) {
        sigClose = i;
        break;
      }
    }
  }
  if (sigClose < 0) return '';
  const open = source.indexOf('{', sigClose);
  if (open < 0) return '';
  let depth = 0;
  quote = '';
  escaped = false;
  for (let i = open; i < source.length; i++) {
    const ch = source[i];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (ch === '\\') {
        escaped = true;
      } else if (ch === quote) {
        quote = '';
      }
      continue;
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch;
      continue;
    }
    if (ch === '{') depth++;
    if (ch === '}') {
      depth--;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  return source.slice(start);
}

const inlineSyntax = inlineScriptSyntaxResult();
const renderTimelineBody = functionBody('rtwRenderTimeline');
const currentArtifactPanelBlock = (() => {
  const match = renderTimelineBody.match(/const artifactItems = Object\.values\(realtimeWorkflowState\.artifacts \|\| \{\}\)[\s\S]*?const readinessItems = readiness\.checks/);
  return match ? match[0] : '';
})();
const selectedLedgerArtifactRowsBlock = (() => {
  const match = renderTimelineBody.match(/const selectedLedgerArtifactRows = selectedLedgerArtifacts[\s\S]*?const selectedLedgerLogs =/);
  return match ? match[0] : '';
})();
const requirementAuditBody = functionBody('rtwBuildRequirementAuditReport');
const requirementIdList = requirementIds();
const aiPersonaIdList = aiPersonaIds();

check('RTW requirement audit has 18 rules', countRequirementDefs() === 18, `count=${countRequirementDefs()}`);
check('Requirement audit covers every RTW rule id',
  requirementIdList.length === 18 &&
  requirementIdList.every(id => new RegExp(`${id}:\\s*rtwMakeRequirement`).test(requirementAuditBody)) &&
  /const items = RTW_REQUIREMENT_DEFS\.map\(\(\[id, title\]\) => \(\{ id, title, \.\.\.auditMap\[id\] \}\)\)/.test(requirementAuditBody) &&
  /summary = items\.reduce/.test(requirementAuditBody) &&
  /rtwRegisterArtifact\('workflow_requirement_audit'/.test(requirementAuditBody),
  `ids=${requirementIdList.join(',')}`
);
check('Every realtime AI model slot has a detailed persona',
  /const RTW_AI_PERSONAS = \{/.test(html) &&
  /function rtwPersonaPrompt/.test(html) &&
  aiPersonaIdList.length >= 14 &&
  ['image1', 'promptA', 'promptB', 'image2A', 'image2B', 'maskChecker', 'globalPlanner', 'taskModeler', 'taskChecker', 'taskRevision', 'placement', 'lighting', 'atmosphericPerspective', 'perspectiveCompare']
    .every(id => aiPersonaIdList.includes(id)) &&
  /responsibilities/.test(html.match(/const RTW_AI_PERSONAS = \{([\s\S]*?)\n\};\nconst RTW_IMAGE_TARGETS/)?.[1] || '') &&
  /boundaries/.test(html.match(/const RTW_AI_PERSONAS = \{([\s\S]*?)\n\};\nconst RTW_IMAGE_TARGETS/)?.[1] || '') &&
  /failureBias/.test(html.match(/const RTW_AI_PERSONAS = \{([\s\S]*?)\n\};\nconst RTW_IMAGE_TARGETS/)?.[1] || ''),
  `personas=${aiPersonaIdList.join(',')}`
);
check('Realtime AI prompts inject their node personas',
  /rtwPersonaPrompt\('image1'\)/.test(functionBody('rtwBuildInitialReferencePrompt')) &&
  /rtwPersonaPrompt\('promptA'\)/.test(functionBody('rtwPromptASystem')) &&
  /rtwPersonaPrompt\('promptB'\)/.test(functionBody('rtwPromptBSystem')) &&
  /rtwPersonaPrompt\('image2A'\)/.test(asyncFunctionBody('rtwRunImage2ANode')) &&
  /rtwPersonaPrompt\('image2B'\)/.test(asyncFunctionBody('rtwRunImage2BNode')) &&
  /rtwPersonaPrompt\('maskChecker'\)/.test(functionBody('rtwBuildMaskVisualInterlockPrompt')) &&
  /rtwPersonaPrompt\('globalPlanner'\)/.test(functionBody('rtwGlobalPlannerSystem')) &&
  /rtwPersonaPrompt\(slotId\)/.test(functionBody('rtwTaskModelerSystem')) &&
  /rtwPersonaPrompt\('taskChecker'\)/.test(functionBody('rtwTaskCheckerPrompt')) &&
  /rtwPersonaPrompt\('placement'\)/.test(asyncFunctionBody('rtwRunPlacementNode')) &&
  /rtwPersonaPrompt\('lighting'\)/.test(asyncFunctionBody('rtwRunBasicLightingNode')) &&
  /rtwPersonaPrompt\('atmosphericPerspective'\)/.test(asyncFunctionBody('rtwRunAtmosphericPerspectiveNode')) &&
  /rtwPersonaPrompt\('perspectiveCompare'\)/.test(functionBody('rtwPerspectiveComparePrompt'))
);
check('Realtime HTML inline script parses', inlineSyntax.ok, inlineSyntax.ok ? `inline scripts=${inlineSyntax.count}` : inlineSyntax.error);
check('Diagnostic buttons exist',
  /文本诊断/.test(html) &&
  /图片分支诊断/.test(html) &&
  /rtwRunImageInputDiagnosticSelfTest\(\)/.test(html)
);
check('Diagnostic self-test function is exposed', /window\.rtwRunDiagnosticSelfTest = rtwRunDiagnosticSelfTest/.test(html));
check('Image input diagnostic function is exposed',
  /async function rtwRunImageInputDiagnosticSelfTest/.test(html) &&
  /window\.rtwRunImageInputDiagnosticSelfTest = rtwRunImageInputDiagnosticSelfTest/.test(html) &&
  /mode === 'image'\s*\?\s*rtwRunImageInputDiagnosticSelfTest/.test(html) &&
  /agentState\.referenceImages = \[rtwDryRunImageDataUrl\('image input diagnostic reference'\)\]/.test(asyncFunctionBody('rtwRunImageInputDiagnosticSelfTest')) &&
  /if \(descEl\) descEl\.value = '';/.test(asyncFunctionBody('rtwRunImageInputDiagnosticSelfTest')) &&
  /await rtwRunWorkflow\(\);/.test(asyncFunctionBody('rtwRunImageInputDiagnosticSelfTest'))
);
check('Diagnostic URL auto-run exists',
  /rtw_diagnostic/.test(html) &&
  /function rtwMaybeAutoRunDiagnosticFromUrl/.test(html) &&
  /rtwMaybeAutoRunDiagnosticFromUrl\(\);/.test(html)
);
check('Diagnostic URL failure modes exist',
  /failure_models/.test(html) &&
  /failure_input/.test(html) &&
  /function rtwRunStartupFailureDiagnostic/.test(html)
);
check('Legacy realtime UI is mode-gated',
  /function rtwUpdateModeVisibility/.test(html) &&
  /#photo-agent3d-view #agent-legacy-token-banner/.test(html) &&
  !/#photo-agent3d-view #agent-viewport-panel/.test(html) &&
  /id="agent-viewport-panel"/.test(html) &&
  /id="agent-rtw-viewport-dock"/.test(html) &&
  /display: none !important;/.test(html) &&
  /agent-legacy-generation-card/.test(html) &&
  /agent-legacy-status-card/.test(html) &&
  /agent-legacy-timeline-card/.test(html) &&
  /agent-legacy-review-log-card/.test(html) &&
  /agent-legacy-m3d-grid-import-btn/.test(html) &&
  /agent-legacy-code-preview-card/.test(html) &&
  /asset-library-panel/.test(html) &&
  /sm-panel/.test(html) &&
  /agent-mcp-history-panel/.test(html) &&
  /agent-plan-panel/.test(html) &&
  /agent-screenshot-fix-panel/.test(html) &&
  /agent-imggen-card/.test(html) &&
  /agent-rtw-model-slots-card/.test(html)
);
check('Hunyuan3D interface UI is hidden without deleting implementation',
  /#btn-mode-hy3dtest,\s*\n\s*#btn-photo-hy3dtest,\s*\n\s*#photo-hy3dtest-view/.test(html) &&
  /display: none !important;/.test(html) &&
  /id="photo-hy3dtest-view"/.test(html) &&
  /id="btn-mode-hy3dtest"/.test(html) &&
  /id="btn-photo-hy3dtest"/.test(html) &&
  /function agentHunyuan3dCheckStatus/.test(html) &&
  /async function rtwRunHunyuanWorldNode/.test(html) &&
  /fetch\('\/api\/hunyuan\/generate'/.test(functionBody('rtwRunHunyuanWorldNode'))
);
check('Realtime Hunyuan service controls remain visible in node workflow',
  /id="agent-rtw-hunyuan-dock"/.test(html) &&
  /function rtwDockRealtimeHunyuanPanel/.test(html) &&
  /card\.style\.display = 'none'/.test(functionBody('rtwDockRealtimeHunyuanPanel')) &&
  /rtwDockRealtimeHunyuanPanel\(\);/.test(functionBody('rtwUpdateModeVisibility')) &&
  /rtwDockRealtimeHunyuanPanel\(\);/.test(functionBody('rtwRenderTimeline')) &&
  /window\.rtwDockRealtimeHunyuanPanel = rtwDockRealtimeHunyuanPanel/.test(html) &&
  /id="agent-hunyuan3d-enabled"/.test(html) &&
  /id="agent-rtw-hunyuan-control-strip"/.test(html) &&
  /id="agent-rtw-hunyuan-progress"/.test(html) &&
  /id="agent-rtw-hunyuan-progress-fill"/.test(html) &&
  /#agent-rtw-hunyuan-dock\s*\{[\s\S]*?display: none !important;/.test(html) &&
  /data-rtw-hunyuan-actions="true"/.test(html) &&
  /#agent-rtw-hunyuan-control-strip button/.test(html) &&
  /min-height: 34px !important/.test(html) &&
  /grid-template-columns: minmax\(0, 1fr\) minmax\(0, 1fr\)/.test(html) &&
  /id="agent-rtw-hunyuan-enabled"/.test(html) &&
  /id="agent-rtw-hunyuan-status"/.test(html) &&
  /agentHunyuan3dToggle\(\)/.test(html) &&
  /function agentHunyuan3dToggleFromRealtime/.test(html) &&
  /function agentHunyuan3dStartFromButton/.test(html) &&
  /启动\/连接混元服务/.test(html) &&
  /agentHunyuan3dCheckStatus\(\)/.test(html) &&
  /id="agent-hunyuan3d-progress"/.test(html) &&
  /id="agent-hunyuan3d-progress-fill"/.test(html) &&
  /function rtwSetHunyuanUiState/.test(html) &&
  /agent-rtw-hunyuan-control-strip/.test(functionBody('rtwSetHunyuanUiState')) &&
  /agent-rtw-hunyuan-progress-fill/.test(functionBody('rtwSetHunyuanUiState')) &&
  /正式运行必须先启用并检测混元世界服务/.test(html) &&
  !/'agent-hunyuan3d-card'/.test(functionBody('rtwUpdateModeVisibility'))
);
check('Realtime Hunyuan service preloads models after start or status check',
  /app\.post\('\/api\/hunyuan\/warmup'/.test(server) &&
  /HUNYUAN_BASE_URL \+ '\/load-models'/.test(server) &&
  /parsePositiveTimeoutSec\(req\.body\?\.timeout, 600\)/.test(server) &&
  /function agentHunyuan3dWarmupInBackground/.test(html) &&
  /fetch\('\/api\/hunyuan\/warmup'/.test(functionBody('agentHunyuan3dWarmupInBackground')) &&
  /timeout: warmupTimeoutSec/.test(functionBody('agentHunyuan3dWarmupInBackground')) &&
  /warming:\s*\{/.test(functionBody('rtwSetHunyuanUiState')) &&
  /async function agentHunyuan3dToggle\(\)[\s\S]*?agentHunyuan3dWarmupInBackground\(\);/.test(html) &&
  /agentHunyuan3dWarmupInBackground\(\);/.test(asyncFunctionBody('agentHunyuan3dCheckStatus'))
);
check('Realtime workflow has separate AI and Hunyuan timeout controls',
  /id="agent-rtw-ai-timeout"/.test(html) &&
  /id="agent-rtw-hunyuan-timeout"/.test(html) &&
  /id="agent-rtw-ai-timeout" min="30" max="900"/.test(html) &&
  /id="agent-rtw-hunyuan-timeout" min="1" value="180"/.test(html) &&
  /aiTimeoutSec: 180/.test(html) &&
  /hunyuanTimeoutSec: 180/.test(html) &&
  /AI节点响应时间/.test(html) &&
  /混元响应时间/.test(html) &&
  /timeout: settings\.aiTimeoutSec/.test(functionBody('rtwCallTextModel')) &&
  /timeout: settings\.aiTimeoutSec/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /timeout: settings\.hunyuanTimeoutSec/.test(asyncFunctionBody('rtwRunHunyuanWorldNode')) &&
  /AI节点响应时间 \${settings\.aiTimeoutSec}s/.test(html) &&
  /混元响应时间 \${settings\.hunyuanTimeoutSec}s/.test(html) &&
  /aiTimeoutSec: agentState\.realtimeWorkflowGlobal\?\.aiTimeoutSec \|\| 180/.test(html) &&
  /hunyuanTimeoutSec: agentState\.realtimeWorkflowGlobal\?\.hunyuanTimeoutSec \|\| 180/.test(html) &&
  /const hunyuanTimeoutSec = Math\.max\(1, parseInt\(hunyuanTimeoutRaw, 10\) \|\| agentState\.realtimeWorkflowGlobal\?\.hunyuanTimeoutSec \|\| 180\);/.test(html) &&
  /hunyuanTimeoutSec = Math\.max\(1, parseInt\(rtwHunyuanTimeoutEl\.value, 10\) \|\| 180\);/.test(html) &&
  /parsePositiveTimeoutSec\(timeout, 180\)/.test(server) &&
  /timeoutSecToAxiosTimeoutMs\(timeoutSec\)/.test(server) &&
  /生成超时（超过\$\{timeoutSec\}秒）/.test(server)
);
check('Realtime Hunyuan resource probe selects params before generation',
  /\['resource_probe', '资源探测'/.test(html) &&
  /\['image_2a', 'resource_probe'\]/.test(html) &&
  /\['resource_probe', 'hunyuan_world'\]/.test(html) &&
  /async function rtwRunResourceProbeNode/.test(html) &&
  /\/api\/system\/resources/.test(asyncFunctionBody('rtwRunResourceProbeNode')) &&
  /function rtwSelectHunyuanProfile/.test(html) &&
  /memory\.available_bytes/.test(functionBody('rtwSelectHunyuanProfile')) &&
  /function rtwHunyuanParameterKnowledgeBase/.test(html) &&
  /parameter_knowledge = rtwHunyuanParameterKnowledgeBase/.test(functionBody('rtwHunyuanProfileTemplate')) &&
  /hunyuanParameterKnowledge/.test(asyncFunctionBody('rtwRunResourceProbeNode')) &&
  /world_context\.hunyuanParameterKnowledge/.test(functionBody('rtwGlobalPlannerSystem')) &&
  /shape_params/.test(functionBody('rtwHunyuanProfileTemplate')) &&
  /await rtwRunResourceProbeNode\(\);\s*await rtwRunHunyuanWorldNode\(\);/.test(asyncFunctionBody('rtwRunWorkflow')) &&
  /shape_params: shapeParams/.test(asyncFunctionBody('rtwRunHunyuanWorldNode')) &&
  /app\.get\('\/api\/system\/resources'/.test(server) &&
  /available_bytes/.test(server) &&
  /normalizeHunyuanShapeParams/.test(server) &&
  /shape_params: safeShapeParams/.test(server) &&
  /def _build_shape_kwargs/.test(hunyuanService) &&
  /_pipeline_shapegen\(image=image, \*\*shape_kwargs\)/.test(hunyuanService)
);
check('Realtime visual split classification feeds downstream branch prompts',
  /function rtwBuildImageSplitRouterPrompt/.test(html) &&
  /function rtwValidateVisualClassificationOutput/.test(html) &&
  /image_split_router: rtwValidateVisualClassificationOutput/.test(functionBody('rtwValidateNodeOutput')) &&
  /rtwCallVisionModelMulti\('image_split_router', 'promptA'/.test(asyncFunctionBody('rtwRunImageSplitRouterNode')) &&
  /visual_task_classification/.test(asyncFunctionBody('rtwRunImageSplitRouterNode')) &&
  /const visualContext = rtwVisualClassificationContext\(\);/.test(functionBody('rtwPromptAUser')) &&
  /const visualContext = rtwVisualClassificationContext\(\);/.test(functionBody('rtwPromptBUser')) &&
  /visual_task_classification/.test(functionBody('rtwVisualClassificationContext')) &&
  /source_reference_artifact/.test(functionBody('rtwVisualClassificationContext')) &&
  /Use the upstream visual_task_classification/.test(asyncFunctionBody('rtwRunImage2ANode')) &&
  /Use the upstream visual_task_classification/.test(asyncFunctionBody('rtwRunImage2BNode')) &&
  /visualClassification/.test(asyncFunctionBody('rtwRunSplitLedgerNode'))
);
check('Realtime nodes can be routed through local Codex without API keys',
  /id="agent-rtw-local-codex"/.test(html) &&
  /id="agent-rtw-codex-model"/.test(html) &&
  /id="agent-rtw-codex-reasoning"/.test(html) &&
  /id="agent-rtw-codex-speed"/.test(html) &&
  /gpt-5\.5/.test(html) &&
  /gpt-5\.4-mini/.test(html) &&
  /gpt-5\.3-codex-spark/.test(html) &&
  /function rtwNormalizeLocalCodexSettings/.test(html) &&
  /codexModel/.test(functionBody('rtwGetGlobalSettingsFromDom')) &&
  /codexReasoningEffort/.test(functionBody('rtwGetGlobalSettingsFromDom')) &&
  /codexSpeed/.test(functionBody('rtwGetGlobalSettingsFromDom')) &&
  /codex_model: settings\.codexModel/.test(asyncFunctionBody('rtwCallLocalCodexTextModel')) &&
  /codex_reasoning_effort: settings\.codexReasoningEffort/.test(asyncFunctionBody('rtwCallLocalCodexTextModel')) &&
  /codex_speed: settings\.codexSpeed/.test(asyncFunctionBody('rtwCallLocalCodexTextModel')) &&
  /codex_model: settings\.codexModel/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /codex_reasoning_effort: settings\.codexReasoningEffort/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /codex_speed: settings\.codexSpeed/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /本地 Codex 接管推理节点/.test(html) &&
  /图片节点默认走 Codex \$imagegen/.test(html) &&
  /function rtwUseLocalCodex/.test(html) &&
  /function rtwCallLocalCodexTextModel/.test(html) &&
  /fetch\('\/api\/local-codex\/chat'/.test(functionBody('rtwCallLocalCodexTextModel')) &&
  /if \(rtwUseLocalCodex\(\)\) \{[\s\S]*rtwCallLocalCodexTextModel/.test(asyncFunctionBody('rtwCallTextModel')) &&
  /const RTW_IMAGE_MODEL_SLOT_IDS/.test(html) &&
  /function rtwRequiredModelSlotsForCurrentMode/.test(html) &&
  /if \(rtwUseLocalCodex\(\)\) \{[\s\S]*return \[\];/.test(functionBody('rtwRequiredModelSlotsForCurrentMode')) &&
  /rtwUseLocalCodex\(\) && !rtwIsImageModelSlot\(slotId\)/.test(functionBody('rtwRequireConfiguredModelSlot')) &&
  /rtwRequiredModelSlotsForCurrentMode\(inputType\)/.test(functionBody('rtwValidateRequiredModelSlots')) &&
  !/本地 Codex 模式仍需要真实生图模型槽位/.test(functionBody('rtwValidateRequiredModelSlots')) &&
  /\/api\/local-codex\/image/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /localCodexImagegen: true/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /Codex \$imagegen/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /\/api\/generate-texture/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /realImageRequired: true/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  !/localCodexPlaceholder: true/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  !/instant-placeholder/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  !/rtwBuildLocalCodexVisualBrief/.test(html) &&
  !/rtwLocalCodexImageDataUrl/.test(html) &&
  !/rtwCallLocalCodexTextModel/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
  /app\.post\('\/api\/local-codex\/image'/.test(server) &&
  /\$imagegen/.test(server) &&
  /_localCodexReadImageFile/.test(server) &&
  /function rtwIsLocalCodexPlaceholderArtifact/.test(html) &&
  /rtwIsLocalCodexPlaceholderArtifact\(cleanArtifact\)/.test(asyncFunctionBody('rtwRunHunyuanWorldNode')) &&
  /检测到旧的本地 Codex 占位图/.test(asyncFunctionBody('rtwRunHunyuanWorldNode')) &&
  !/async function rtwRunLocalCodexWorldFallbackNode/.test(html) &&
  !/RTW_CODEX_WORLD_RESULT/.test(html) &&
  !/localCodexWorldFallback: true/.test(html) &&
  !/if \(rtwUseLocalCodex\(\)\) return;/.test(functionBody('rtwValidateRequiredModelSlots')) &&
  /本地 Codex 接管文本\/视觉\/代码节点/.test(functionBody('rtwInspectWorkflowReadiness')) &&
  /图片节点走 Codex \$imagegen/.test(functionBody('rtwInspectWorkflowReadiness')) &&
  /!agentState\.hunyuan3dEnabled/.test(asyncFunctionBody('rtwRunWorkflow')) &&
  !/rtwUseLocalCodex\(\) && inputType === 'text'/.test(asyncFunctionBody('rtwRunWorkflow')) &&
  /app\.post\('\/api\/local-codex\/chat'/.test(server) &&
  /function _buildLocalCodexPrompt/.test(server) &&
  /function _normalizeLocalCodexOptions/.test(server) &&
  /function _appendLocalCodexOptionArgs/.test(server) &&
  /model_reasoning_effort/.test(server) &&
  /service_tier="fast"/.test(server) &&
  /features\.fast_mode=true/.test(server) &&
  /'--sandbox', 'read-only'/.test(server) &&
  /'--ephemeral'/.test(server)
);
check('Realtime model slots explain required capabilities with MUST and TIP',
  /const RTW_MODEL_SLOT_CAPABILITIES = \{/.test(html) &&
  /function rtwRenderModelSlotCapabilityTips/.test(html) &&
  /window\.rtwRenderModelSlotCapabilityTips = rtwRenderModelSlotCapabilityTips/.test(html) &&
  /setTimeout\(\(\) => rtwRenderModelSlotCapabilityTips\(\), 0\)/.test(html) &&
  /data-rtw-slot-capability/.test(functionBody('rtwRenderModelSlotCapabilityTips')) &&
  /rtwRenderModelSlotCapabilityTips\(\);/.test(functionBody('rtwUpdateModeVisibility')) &&
  /rtwRenderModelSlotCapabilityTips\(\);/.test(functionBody('rtwRenderTimeline')) &&
  /rtw-slot-capability-badge must/.test(html) &&
  /rtw-slot-capability-badge tip/.test(html) &&
  /文生图能力/.test(html) &&
  /图生图能力/.test(html) &&
  /视觉理解能力/.test(html) &&
  /Blender MCP\/工具调用能力/.test(html) &&
  /推荐：/.test(html) &&
  /结构化 JSON/.test(html) &&
  aiPersonaIdList.every(id => new RegExp(`${id}:\\s*\\{[\\s\\S]*?must:[\\s\\S]*?tip:`, 'm').test(html.match(/const RTW_MODEL_SLOT_CAPABILITIES = \{([\s\S]*?)\n\};\nconst RTW_AI_PERSONAS/)?.[0] || ''))
);
check('One-click 3D has original direct AI Blender script path',
  /id="m3d-direct-ai-card"/.test(html) &&
  /AI直跑脚本到 Blender/.test(html) &&
  /function m3dBuildDirectAiScriptSystemPrompt/.test(html) &&
  /function m3dRunDirectAiScript/.test(html) &&
  /function m3dRunDirectAiScriptToBlender/.test(html) &&
  /Do not imitate, quote, or depend on any third-party leaked system prompt/.test(functionBody('m3dBuildDirectAiScriptSystemPrompt')) &&
  /#m3d-direct-ai-card button/.test(html) &&
  /#m3d-direct-ai-card\s*\{[\s\S]*?min-height: 128px/.test(html) &&
  /m3dCallLLM\([\s\S]*?m3dBuildDirectAiScriptSystemPrompt\(\)/.test(asyncFunctionBody('m3dRunDirectAiScript')) &&
  /await m3dSendToBlender\(\)/.test(asyncFunctionBody('m3dRunDirectAiScript')) &&
  !/claude fable/i.test(html)
);
check('Global UI uses unified cockpit skin across app surfaces',
  /Global unified cockpit skin/.test(html) &&
  /--ui-shell-bg/.test(html) &&
  /#workflow-area/.test(html) &&
  /#photo-area/.test(html) &&
  /#mindmap-area/.test(html) &&
  /#welcome-modal \.modal-content/.test(html) &&
  /#settings-modal \.modal-content/.test(html) &&
  /#photo-wall-view/.test(html) &&
  /#photo-analyze-view/.test(html) &&
  /#photo-memo-view/.test(html) &&
  /#workflow-log/.test(html) &&
  /#drawflow-container/.test(html) &&
  /#mm-outline-view/.test(html) &&
  /\.photo-card/.test(html) &&
  /\.input-container/.test(html) &&
  /#photo-model3d-view/.test(html) &&
  /#m3d-direct-ai-card/.test(html)
);
check('Realtime render input is docked at the top as one wide panel',
  (html.match(/id="agent-rtw-input-dock"/g) || []).length === 1 &&
  (html.match(/id="agent-rtw-input-card"/g) || []).length === 1 &&
  (html.match(/id="agent-scene-desc"/g) || []).length === 1 &&
  /function rtwDockRealtimeInputPanel/.test(html) &&
  /dock\.appendChild\(card\)/.test(functionBody('rtwDockRealtimeInputPanel')) &&
  /rtwDockRealtimeInputPanel\(\);/.test(functionBody('rtwUpdateModeVisibility')) &&
  /rtwDockRealtimeInputPanel\(\);/.test(functionBody('rtwRenderTimeline')) &&
  /window\.rtwDockRealtimeInputPanel = rtwDockRealtimeInputPanel/.test(html) &&
  /#agent-rtw-input-card textarea#agent-scene-desc/.test(html) &&
  /min-height: 108px !important/.test(html) &&
  (() => {
    const start = html.indexOf('id="photo-agent3d-view"');
    const end = html.indexOf('id="photo-memo-view"', start);
    const agentView = start >= 0 && end > start ? html.slice(start, end) : '';
    return agentView.indexOf('id="agent-rtw-input-dock"') > agentView.indexOf('id="agent-legacy-token-banner"') &&
      agentView.indexOf('id="agent-rtw-input-dock"') < agentView.indexOf('id="agent-rtw-timeline-card"');
  })()
);
check('Post-production realtime entry waits for photo session restore',
  /async function switchPostPhotoView\(view\)/.test(html) &&
  /await switchMode\('photo'\);\s*\n\s*switchPhotoView\(view\);/.test(functionBody('switchPostPhotoView')) &&
  /await selectPhotoSession\(lastSessionIds\.photo/.test(functionBody('switchMode')) &&
  /await selectPhotoSession\(sessions\[0\]\.id, sessions\[0\]\.name\);/.test(functionBody('switchMode')) &&
  /await createNewPhotoSession\(\);/.test(functionBody('switchMode')) &&
  /await selectPhotoSession\(session\.id, session\.name\);/.test(asyncFunctionBody('createNewPhotoSession'))
);
check('Realtime UI has a consistent control surface layer',
  /--ui-surface-strong/.test(html) &&
  /--ui-control-bg/.test(html) &&
  /--ui-focus-ring/.test(html) &&
  /#photo-agent3d-view :is\(input, textarea, select\)/.test(html) &&
  /#photo-agent3d-view :is\(input, textarea, select\):focus-visible/.test(html) &&
  /#photo-agent3d-view ::-webkit-scrollbar-thumb/.test(html) &&
  /#agent-rtw-input-card::before/.test(html)
);
check('Legacy realtime side effects are disabled in node workflow',
  /function rtwDisableLegacyRealtimeSideEffects/.test(html) &&
  /rtwDisableLegacyRealtimeSideEffects\(\);/.test(functionBody('rtwUpdateModeVisibility')) &&
  /agentState\.viewportMonitor\.enabled = false;/.test(functionBody('rtwDisableLegacyRealtimeSideEffects')) &&
  /agentViewportStopPolling\(\)/.test(functionBody('rtwDisableLegacyRealtimeSideEffects')) &&
  /agentStopPolyHavenPoll\(\)/.test(functionBody('rtwDisableLegacyRealtimeSideEffects'))
);
check('Global realtime workflow board has live color states',
  /const RTW_PHASE_DEFS = \[/.test(html) &&
  /const RTW_EDGE_DEFS = \[/.test(html) &&
  /const RTW_STARMAP_NODE_IDS = \[/.test(html) &&
  /const RTW_STARMAP_EDGE_DEFS = \[/.test(html) &&
  /RTW_EDGE_DEFS\.forEach/.test(functionBody('rtwSyncThreeWorkflowScene')) &&
  /const mapEdgeItems = RTW_STARMAP_EDGE_DEFS\.map/.test(functionBody('rtwRenderTimeline')) &&
  /\['task_revision', 'task_modeling'\]/.test(html) &&
  /\['placement', 'basic_lighting'\]/.test(html) &&
  phaseNodeIds().length === countNodeDefs() &&
  new Set(phaseNodeIds()).size === countNodeDefs() &&
  /function rtwInspectWorkflowReadiness/.test(html) &&
  /data-rtw-readiness-panel="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-readiness-item=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-readiness-status=/.test(functionBody('rtwRenderTimeline')) &&
  /启动前就绪检查/.test(functionBody('rtwRenderTimeline')) &&
  /missingSlots/.test(functionBody('rtwInspectWorkflowReadiness')) &&
  /rtwRequiredModelSlotsForCurrentInput\(inputType\)/.test(functionBody('rtwInspectWorkflowReadiness')) &&
  /data-rtw-runtime-log-panel="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-runtime-log-row=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-runtime-log-level=/.test(functionBody('rtwRenderTimeline')) &&
  /节点运行日志/.test(functionBody('rtwRenderTimeline')) &&
  /输入 \/ 输出 \/ 模型 \/ 错误 \/ 修改原因 \/ 检查得分/.test(functionBody('rtwRenderTimeline')) &&
  /runtimeLogs/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-observability-grid="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-artifact-panel="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-artifact-row=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-artifact-type=/.test(functionBody('rtwRenderTimeline')) &&
  /节点产物/.test(functionBody('rtwRenderTimeline')) &&
  /initial_reference_image \/ 分支记录 \/ 检查结果/.test(functionBody('rtwRenderTimeline')) &&
  /rtwSummarizeArtifactValue\(artifact\.value\)/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-global-workflow-board="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-phase-stepper="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-phase-step=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-phase-board="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-phase=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-active-node-detail="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-active-contract-grid="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-active-contract-field=/.test(functionBody('rtwRenderTimeline')) &&
  /function rtwSummarizeContractValue/.test(html) &&
  /\['输入', activeContract\.inputs\]/.test(functionBody('rtwRenderTimeline')) &&
  /\['输出', activeContract\.outputs\]/.test(functionBody('rtwRenderTimeline')) &&
  /\['模型', activeContract\.model/.test(functionBody('rtwRenderTimeline')) &&
  /\['工具', activeContract\.tool/.test(functionBody('rtwRenderTimeline')) &&
  /\['错误', activeContract\.error/.test(functionBody('rtwRenderTimeline')) &&
  /\['原因', activeContract\.reason/.test(functionBody('rtwRenderTimeline')) &&
  /\['分数', typeof activeContract\.score === 'number'/.test(functionBody('rtwRenderTimeline')) &&
  /activeNodeDef/.test(functionBody('rtwRenderTimeline')) &&
  /当前关注节点/.test(functionBody('rtwRenderTimeline')) &&
  /复制看板快照/.test(functionBody('rtwRenderTimeline')) &&
  /rtwCopyWorkflowBoardSnapshot\(\)/.test(functionBody('rtwRenderTimeline')) &&
  /下载JSON/.test(functionBody('rtwRenderTimeline')) &&
  /rtwDownloadWorkflowBoardSnapshot\(\)/.test(functionBody('rtwRenderTimeline')) &&
  /durationFor/.test(functionBody('rtwRenderTimeline')) &&
  /startedAt/.test(functionBody('rtwRenderTimeline')) &&
  /finishedAt/.test(functionBody('rtwRenderTimeline')) &&
  /耗时/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-board-summary="true"/.test(functionBody('rtwRenderTimeline')) &&
  /repeat\(auto-fit, minmax\(128px, 1fr\)\)/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-node-card=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-status=/.test(functionBody('rtwRenderTimeline')) &&
  /completedCount/.test(functionBody('rtwRenderTimeline')) &&
  /failedCount/.test(functionBody('rtwRenderTimeline')) &&
  /runningNode/.test(functionBody('rtwRenderTimeline')) &&
  /金色/.test(functionBody('rtwRenderTimeline')) &&
  /灰色/.test(functionBody('rtwRenderTimeline')) &&
  /中心星云/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-active=/.test(functionBody('rtwRenderTimeline')) &&
  /skipped:\s*\{[\s\S]*?label:\s*'已跳过'[\s\S]*?color:\s*'var\(--accent2\)'/.test(functionBody('rtwRenderTimeline'))
);
check('Realtime cockpit UI has 3D diagnostic styling and accessible motion',
  /Realtime Render Cockpit/.test(html) &&
  /--rtw-cockpit-bg/.test(html) &&
  /@keyframes rtwCockpitSweep/.test(html) &&
  /@keyframes rtwNodePulse/.test(html) &&
  /@keyframes rtwViewportFloat/.test(html) &&
  /prefers-reduced-motion: reduce/.test(html) &&
  /data-rtw-viewport-panel="true"/.test(functionBody('rtwRenderTimeline')) &&
  /id="agent-rtw-viewport-dock"/.test(functionBody('rtwRenderTimeline')) &&
  /id="agent-rtw-diagnostic-metrics"/.test(functionBody('rtwRenderTimeline')) &&
  /function rtwDockRealtimeViewportPanel/.test(html) &&
  /dock\.appendChild\(panel\)/.test(functionBody('rtwDockRealtimeViewportPanel')) &&
  /agentViewportStartPolling\(\)/.test(functionBody('rtwDockRealtimeViewportPanel')) &&
  /rtwDockRealtimeViewportPanel\(\);/.test(functionBody('rtwUpdateModeVisibility')) &&
  /rtwDockRealtimeViewportPanel\(\);/.test(functionBody('rtwRenderTimeline')) &&
  /#agent-rtw-diagnostic-metrics[\s\S]*?repeat\(2, minmax\(0, 1fr\)\)/.test(html) &&
  !/#photo-agent3d-view #agent-viewport-panel/.test(html) &&
  /agent-viewport-panel/.test(html) &&
  /world_bbox/.test(functionBody('rtwRenderTimeline')) &&
  /safe_volume/.test(functionBody('rtwRenderTimeline')) &&
  /camera \/ focal/.test(functionBody('rtwRenderTimeline')) &&
  /rtw-cockpit-actions/.test(functionBody('rtwRenderTimeline'))
);
check('Workflow artifact panels use summaries instead of raw values',
  /data-rtw-artifact-panel="true"/.test(currentArtifactPanelBlock) &&
  /rtwSummarizeArtifactValue\(artifact\.value\)/.test(currentArtifactPanelBlock) &&
  !/src="\$\{.*artifact\.value/.test(currentArtifactPanelBlock) &&
  /data-rtw-ledger-artifact-panel="true"/.test(renderTimelineBody) &&
  /valueSummary/.test(selectedLedgerArtifactRowsBlock) &&
  !/artifact\.value(?!Summary)/.test(selectedLedgerArtifactRowsBlock)
);
check('Global realtime workflow board is top-level in Agent view',
  (() => {
    const start = html.indexOf('id="photo-agent3d-view"');
    const end = html.indexOf('id="photo-memo-view"', start);
    const agentView = start >= 0 && end > start ? html.slice(start, end) : '';
    return (html.match(/id="agent-rtw-timeline-card"/g) || []).length === 1 &&
      /实时查看全局工作流/.test(agentView) &&
      agentView.indexOf('id="agent-rtw-timeline-card"') > agentView.indexOf('id="agent-legacy-token-banner"') &&
      agentView.indexOf('id="agent-rtw-timeline-card"') < agentView.indexOf('id="agent-rtw-config-grid"');
  })()
);
check('Workflow board diagnostics inspect rendered DOM states',
  /function rtwInspectWorkflowBoardStatus/.test(html) &&
  /document\.querySelector\('\[data-rtw-global-workflow-board="true"\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelectorAll\('\[data-rtw-node-card\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelectorAll\('\[data-rtw-phase\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelectorAll\('\[data-rtw-phase-step\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelector\('\[data-rtw-active-node-detail="true"\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelector\('\[data-rtw-runtime-log-panel="true"\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelectorAll\('\[data-rtw-runtime-log-row\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelector\('\[data-rtw-artifact-panel="true"\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelectorAll\('\[data-rtw-artifact-row\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelector\('\[data-rtw-active-contract-grid\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /document\.querySelectorAll\('\[data-rtw-active-contract-field\]'\)/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /activeDetailPresent/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /runtimeLogPanelPresent/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /runtimeLogCount/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /artifactPanelPresent/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /artifactRowCount/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /activeContractGridPresent/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /activeContractFieldCount/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /completedCount/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /phaseCount/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /phaseStepCount/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /failedCount/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /readiness/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /function rtwLogWorkflowBoardDiagnostic/.test(html) &&
  /rtwLogWorkflowBoardDiagnostic\('complete'\)/.test(asyncFunctionBody('rtwRunDiagnosticSelfTest')) &&
  /rtwLogWorkflowBoardDiagnostic\('complete'\)/.test(asyncFunctionBody('rtwRunImageInputDiagnosticSelfTest')) &&
  /rtwLogWorkflowBoardDiagnostic\('failure'\)/.test(asyncFunctionBody('rtwRunStartupFailureDiagnostic')) &&
  /window\.rtwInspectWorkflowBoardStatus = rtwInspectWorkflowBoardStatus/.test(html) &&
  /window\.rtwRegisterWorkflowBoardSnapshot = rtwRegisterWorkflowBoardSnapshot/.test(html) &&
  /window\.rtwCopyWorkflowBoardSnapshot = rtwCopyWorkflowBoardSnapshot/.test(html) &&
  /window\.rtwDownloadWorkflowBoardSnapshot = rtwDownloadWorkflowBoardSnapshot/.test(html) &&
  /window\.rtwLogWorkflowBoardDiagnostic = rtwLogWorkflowBoardDiagnostic/.test(html) &&
  /window\.rtwLastBoardDiagnostic/.test(html)
);
check('Workflow board snapshots are saved as artifacts',
  /function rtwRegisterWorkflowBoardSnapshot/.test(html) &&
  /workflow_board_snapshot/.test(functionBody('rtwRegisterWorkflowBoardSnapshot')) &&
  /rtwRegisterArtifact\('workflow_board_snapshot'/.test(functionBody('rtwRegisterWorkflowBoardSnapshot')) &&
  /readiness: board\.readiness \|\| null/.test(functionBody('rtwBuildPersistableWorkflowSnapshot')) &&
  /phaseStatuses/.test(functionBody('rtwRegisterWorkflowBoardSnapshot')) &&
  /nodeStatuses/.test(functionBody('rtwRegisterWorkflowBoardSnapshot')) &&
  /rtwRegisterWorkflowBoardSnapshot\(`diagnostic_\$\{expectation\}`\)/.test(functionBody('rtwLogWorkflowBoardDiagnostic')) &&
  /rtwRegisterWorkflowBoardSnapshot\('workflow_passed'\)/.test(asyncFunctionBody('rtwRunWorkflow')) &&
  /rtwRegisterWorkflowBoardSnapshot\('workflow_failed'\)/.test(asyncFunctionBody('rtwRunWorkflow')) &&
  /rtwRegisterWorkflowBoardSnapshot\('workflow_aborted'\)/.test(asyncFunctionBody('rtwRunWorkflow'))
);
check('Workflow board snapshot can be copied from the board',
  /async function rtwCopyWorkflowBoardSnapshot/.test(html) &&
  /rtwRegisterWorkflowBoardSnapshot\('manual_copy'\)/.test(asyncFunctionBody('rtwCopyWorkflowBoardSnapshot')) &&
  /navigator\.clipboard\.writeText/.test(asyncFunctionBody('rtwCopyWorkflowBoardSnapshot')) &&
  /看板快照已复制/.test(asyncFunctionBody('rtwCopyWorkflowBoardSnapshot')) &&
  /看板快照复制失败/.test(asyncFunctionBody('rtwCopyWorkflowBoardSnapshot'))
);
check('Workflow board snapshot can be downloaded as JSON',
  /function rtwDownloadWorkflowBoardSnapshot/.test(html) &&
  /rtwRegisterWorkflowBoardSnapshot\('manual_download'\)/.test(functionBody('rtwDownloadWorkflowBoardSnapshot')) &&
  /new Blob\(\[text\], \{ type: 'application\/json;charset=utf-8' \}\)/.test(functionBody('rtwDownloadWorkflowBoardSnapshot')) &&
  /URL\.createObjectURL/.test(functionBody('rtwDownloadWorkflowBoardSnapshot')) &&
  /\.download = `\$\{safeRunId\}_workflow_board_\$\{stamp\}\.json`;/.test(functionBody('rtwDownloadWorkflowBoardSnapshot')) &&
  /URL\.revokeObjectURL/.test(functionBody('rtwDownloadWorkflowBoardSnapshot')) &&
  /看板快照JSON已下载/.test(functionBody('rtwDownloadWorkflowBoardSnapshot'))
);
check('Workflow state is persisted to a backend realtime ledger',
  /const REALTIME_WORKFLOW_DIR = path\.join\(DATA_DIR, 'realtime_workflows'\);/.test(server) &&
  /const REALTIME_WORKFLOW_INDEX_FILE = path\.join\(REALTIME_WORKFLOW_DIR, 'index\.json'\);/.test(server) &&
  /const REALTIME_WORKFLOW_MAX_RUNS = 200;/.test(server) &&
  /function _sanitizeRealtimeWorkflowSnapshot/.test(server) &&
  /function _pruneRealtimeWorkflowRuns/.test(server) &&
  /runs: Array\.isArray\(index\.runs\) \? index\.runs\.slice\(0, REALTIME_WORKFLOW_MAX_RUNS\) : \[\]/.test(server) &&
  /_safeRealtimeRunId\(runId\)/.test(serverFunctionBody('_pruneRealtimeWorkflowRuns')) &&
  /safeRunId !== runId \|\| !runId\.startsWith\('rtw_'\) \|\| keepRunIds\.has\(runId\)/.test(serverFunctionBody('_pruneRealtimeWorkflowRuns')) &&
  /fs\.rmSync\(path\.join\(REALTIME_WORKFLOW_DIR, runId\), \{ recursive: true, force: true \}\)/.test(serverFunctionBody('_pruneRealtimeWorkflowRuns')) &&
  /app\.get\('\/api\/realtime-workflows'/.test(server) &&
  /app\.get\('\/api\/realtime-workflows\/:runId'/.test(server) &&
  /app\.post\('\/api\/realtime-workflows\/snapshot'/.test(server) &&
  /fs\.appendFileSync\(eventsFile/.test(server) &&
  /fs\.writeFileSync\(snapshotFile/.test(server) &&
  /const writtenIndex = _writeRealtimeWorkflowIndex\(\{ runs: \[runSummary, \.\.\.existing\] \}\);/.test(server) &&
  /const prune = _pruneRealtimeWorkflowRuns\(writtenIndex\);/.test(server) &&
  /summary: runSummary, prune/.test(server) &&
  /function rtwBuildPersistableWorkflowSnapshot/.test(html) &&
  /async function rtwPostWorkflowLedgerSnapshot/.test(html) &&
  /function rtwPersistWorkflowState/.test(html) &&
  /async function rtwFlushWorkflowLedger/.test(html) &&
  /\/api\/realtime-workflows\/snapshot/.test(html) &&
  /rtwSummarizeArtifactValue/.test(functionBody('rtwBuildPersistableWorkflowSnapshot')) &&
  /rtwPostWorkflowLedgerSnapshot\(currentReason\)/.test(functionBody('rtwPersistWorkflowState')) &&
  /rtwPersistWorkflowState\(`node_\$\{nodeId\}_\$\{status\}`/.test(html) &&
  /rtwPersistWorkflowState\(`log_\$\{nodeId\}`/.test(html) &&
  /rtwPersistWorkflowState\('workflow_started'/.test(asyncFunctionBody('rtwRunWorkflow')) &&
  /function rtwCreateRunId/.test(html) &&
  /slice\(0, 17\)/.test(functionBody('rtwCreateRunId')) &&
  /Math\.random\(\)\.toString\(36\)\.slice\(2, 8\)/.test(functionBody('rtwCreateRunId')) &&
  /realtimeWorkflowState\.runId = rtwCreateRunId\(\);/.test(asyncFunctionBody('rtwRunWorkflow')) &&
  !/realtimeWorkflowState\.runId = 'rtw_' \+ new Date\(\)\.toISOString\(\)\.replace\(\.\*\)\.slice\(0, 14\)/.test(html) &&
  /window\.rtwBuildPersistableWorkflowSnapshot = rtwBuildPersistableWorkflowSnapshot/.test(html) &&
  /window\.rtwPostWorkflowLedgerSnapshot = rtwPostWorkflowLedgerSnapshot/.test(html) &&
  /window\.rtwPersistWorkflowState = rtwPersistWorkflowState/.test(html) &&
  /window\.rtwFlushWorkflowLedger = rtwFlushWorkflowLedger/.test(html)
);
check('Workflow board elapsed time refreshes without rebuilding animated board',
  /let _rtwBoardLastTick = 0;/.test(html) &&
  /function rtwUpdateWorkflowLiveTimers/.test(html) &&
  /data-rtw-live-elapsed="true"/.test(html) &&
  /agentState\.realtimeWorkflowMode === 'node-workflow'/.test(functionBody('agentStartTimer')) &&
  /realtimeWorkflowState\?\.status === 'running'/.test(functionBody('agentStartTimer')) &&
  /now - _rtwBoardLastTick >= 1000/.test(functionBody('agentStartTimer')) &&
  /rtwUpdateWorkflowLiveTimers\(\);/.test(functionBody('agentStartTimer')) &&
  !/rtwRenderTimeline\(\);/.test(functionBody('agentStartTimer'))
);
check('Node retry state clears stale terminal fields',
  /n\.runCount = \(Number\(n\.runCount \|\| 0\) \|\| 0\) \+ 1;/.test(functionBody('rtwSetNodeStatus')) &&
	  /n\.startedAt = now;/.test(functionBody('rtwSetNodeStatus')) &&
	  /n\.finishedAt = '';/.test(functionBody('rtwSetNodeStatus')) &&
	  /n\.error = '';/.test(functionBody('rtwSetNodeStatus')) &&
	  /n\.ocap = null;/.test(functionBody('rtwSetNodeStatus')) &&
	  /n\.reason = '';/.test(functionBody('rtwSetNodeStatus')) &&
  /n\.score = null;/.test(functionBody('rtwSetNodeStatus')) &&
  /if \(status === 'ok' \|\| status === 'skipped'\)/.test(functionBody('rtwSetNodeStatus'))
);
check('Failed nodes expose retry actions with previous error context',
  /function rtwBuildRetryInstruction/.test(html) &&
  /realtimeWorkflowState\.retryContext/.test(html) &&
  /Contract\/error message/.test(functionBody('rtwBuildRetryInstruction')) &&
  /Original node inputs/.test(functionBody('rtwBuildRetryInstruction')) &&
  /rtwBuildRetryInstruction\(nodeId\)/.test(asyncFunctionBody('rtwCallTextModel')) &&
	  /rtwBuildRetryInstruction\(nodeId\)/.test(asyncFunctionBody('rtwGenerateImageArtifact')) &&
	  /data-rtw-failed-action-bar="true"/.test(html) &&
	  /data-rtw-failed-retry=/.test(html) &&
	  /再次尝试 · 带 OCAP 重试/.test(html)
	);
	check('All realtime gates attach OCAP recovery contracts',
	  /function rtwCreateOcap/.test(html) &&
	  /function rtwDefaultOcapForNode/.test(html) &&
	  /function rtwErrorWithOcap/.test(html) &&
	  /function rtwOcapFromError/.test(html) &&
	  /ocap: nodeRun\.ocap \|\| null/.test(functionBody('rtwCreateNodeContractLog')) &&
	  /status === 'failed' && !n\.ocap/.test(functionBody('rtwSetNodeStatus')) &&
	  /rtwDefaultOcapForNode\(nodeId, n\.error \|\| patch\.error \|\| ''\)/.test(functionBody('rtwSetNodeStatus')) &&
	  /OCAP/.test(functionBody('rtwBuildRetryInstruction')) &&
	  /ocap: retryOcap/.test(asyncFunctionBody('rtwRetryFailedNode')) &&
	  /ocap: run\.ocap \|\| null/.test(functionBody('rtwBuildPersistableWorkflowSnapshot')) &&
	  /ocap: run\.ocap \|\| null/.test(functionBody('rtwRegisterWorkflowBoardSnapshot')) &&
	  /function _sanitizeRealtimeOcap/.test(server) &&
	  /ocap: _sanitizeRealtimeOcap\(node\?\.ocap\)/.test(server) &&
	  /ocap: _sanitizeRealtimeOcap\(log\?\.ocap\)/.test(server) &&
	  /throw rtwErrorWithOcap\(nodeId, err/.test(functionBody('rtwOutputContractError')) &&
	  /throw rtwErrorWithOcap\(nodeId, message/.test(functionBody('rtwValidatePreAtmosphereCode')) &&
	  /rtwErrorWithOcap\('input_router', message/.test(functionBody('rtwValidateRequiredModelSlots')) &&
	  /ocap: rtwOcapFromError\(failedNodeId, e\)/.test(asyncFunctionBody('rtwRunWorkflow'))
	);
	check('Node contract logs are recorded per retry attempt',
  /runCount: Number\(nodeRun\.runCount \|\| 0\) \|\| 0/.test(functionBody('rtwCreateNodeContractLog')) &&
  /attemptId: `\$\{nodeId\}:\$\{Number\(nodeRun\.runCount \|\| 0\) \|\| 0\}:\$\{status\}`/.test(functionBody('rtwCreateNodeContractLog')) &&
  /const runCount = Number\(nodeRun\.runCount \|\| 0\) \|\| 0;/.test(functionBody('rtwAppendNodeContractLog')) &&
  /log\.status === status && Number\(log\.runCount \|\| 0\) === runCount/.test(functionBody('rtwAppendNodeContractLog')) &&
  /runCount: Number\(run\.runCount \|\| 0\) \|\| 0/.test(functionBody('rtwBuildPersistableWorkflowSnapshot')) &&
  /runCount: Number\(node\?\.runCount \|\| 0\)/.test(server)
);
check('Recovered node attempts are surfaced on board and ledger',
  /function rtwNodeAttemptStats/.test(html) &&
  /failedAttempts > 0 && \['ok', 'skipped'\]\.includes\(run\.status \|\| ''\)/.test(functionBody('rtwNodeAttemptStats')) &&
  /const recoveredCount = RTW_NODE_DEFS\.filter/.test(functionBody('rtwRenderTimeline')) &&
  /恢复历史/.test(functionBody('rtwRenderTimeline')) &&
  /恢复 \$\{attempts\.failedAttempts\}/.test(functionBody('rtwRenderTimeline')) &&
  /recoveredNodes/.test(functionBody('rtwInspectWorkflowBoardStatus')) &&
  /attemptStats/.test(functionBody('rtwBuildPersistableWorkflowSnapshot')) &&
  /recoveredCount: board\.recoveredCount \|\| 0/.test(functionBody('rtwBuildPersistableWorkflowSnapshot')) &&
  /attemptStats: node\?\.attemptStats && typeof node\.attemptStats === 'object'/.test(server) &&
  /recoveredCount: Number\(snapshot\.summary\?\.recoveredCount \|\| 0\)/.test(server)
);
check('Realtime ledger keeps retry log evidence',
  /runCount: Number\(log\?\.runCount \|\| 0\)/.test(server) &&
  /attemptId: String\(log\?\.attemptId \|\| ''\)\.slice\(0, 180\)/.test(server) &&
  /error: String\(log\?\.error \|\| ''\)\.slice\(0, 1000\)/.test(server) &&
  /reason: String\(log\?\.reason \|\| ''\)\.slice\(0, 1000\)/.test(server) &&
  /recoveredCount: Number\(snapshot\.summary\?\.recoveredCount \|\| 0\)/.test(server) &&
  /readinessOk: snapshot\.summary\?\.readiness/.test(server) &&
  /readinessBlockingCount: Number\(snapshot\.summary\?\.readiness\?\.blockingCount \|\| 0\)/.test(server) &&
  /fs\.appendFileSync\(eventsFile/.test(server)
);
check('Realtime workflow readiness updates when model slots change',
  /function rtwSaveAndRefresh/.test(html) &&
  /window\.rtwSaveAndRefresh = rtwSaveAndRefresh/.test(html) &&
  /id="agent-scene-desc"[^>]*oninput="rtwSaveAndRefresh\(\)"/.test(html) &&
  /id="agent-bridge-url"[^>]*oninput="rtwSaveAndRefresh\(\)"/.test(html) &&
  /agentRenderRefImages\(\);\s*agentSaveState\(\);\s*rtwRenderTimeline\(\);/.test(asyncFunctionBody('agentHandleRefUpload')) &&
  /agentRenderRefImages\(\);\s*agentSaveState\(\);\s*rtwRenderTimeline\(\);/.test(functionBody('agentRemoveRefImage')) &&
  /rtwRenderTimeline\(\);/.test(asyncFunctionBody('rtwOnModelSlotConfigChange')) &&
  /id="agent-rtw-slot-image1-model"[^>]*onchange="agentSaveState\(\); rtwRenderTimeline\(\)"/.test(html) &&
  /id="agent-rtw-slot-perspectiveCompare-model"[^>]*onchange="agentSaveState\(\); rtwRenderTimeline\(\)"/.test(html)
);
check('Workflow ledger can be read from the global board',
  /let realtimeWorkflowLedgerState = \{ status: 'idle', runs: \[\], selected: null, error: '', updatedAt: '' \};/.test(html) &&
  /data-rtw-ledger-panel="true"/.test(functionBody('rtwRenderTimeline')) &&
  /刷新记录/.test(functionBody('rtwRenderTimeline')) &&
  /rtwFetchWorkflowLedger\(\)/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-run=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-selected="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-node-grid="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-node=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-node-status=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-detail-grid="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-artifact-panel="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-artifact=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-artifact-type=/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-log-panel="true"/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-log=/.test(functionBody('rtwRenderTimeline')) &&
  /历史产物/.test(functionBody('rtwRenderTimeline')) &&
  /历史日志/.test(functionBody('rtwRenderTimeline')) &&
  /就绪阻断/.test(functionBody('rtwRenderTimeline')) &&
  /selectedNodeGrid/.test(functionBody('rtwRenderTimeline')) &&
  /selectedLedgerArtifacts/.test(functionBody('rtwRenderTimeline')) &&
  /selectedLedgerLogs/.test(functionBody('rtwRenderTimeline')) &&
  /data-rtw-ledger-validation=/.test(functionBody('rtwRenderTimeline')) &&
  /async function rtwFetchWorkflowLedger/.test(html) &&
  /\/api\/realtime-workflows\?limit=/.test(functionBody('rtwFetchWorkflowLedger')) &&
  /async function rtwLoadWorkflowLedgerRun/.test(html) &&
  /\/api\/realtime-workflows\/\$\{encodeURIComponent\(safeRunId\)\}/.test(functionBody('rtwLoadWorkflowLedgerRun')) &&
  /async function rtwRefreshLedgerAfterDiagnostic/.test(html) &&
  /await rtwFlushWorkflowLedger\('diagnostic_ledger_flush'\)/.test(asyncFunctionBody('rtwRefreshLedgerAfterDiagnostic')) &&
  /await rtwFetchWorkflowLedger\(\)/.test(asyncFunctionBody('rtwRefreshLedgerAfterDiagnostic')) &&
  /await rtwLoadWorkflowLedgerRun\(targetRunId\)/.test(asyncFunctionBody('rtwRefreshLedgerAfterDiagnostic')) &&
  /await rtwRefreshLedgerAfterDiagnostic\(realtimeWorkflowState\.runId\)/.test(asyncFunctionBody('rtwRunDiagnosticSelfTest')) &&
  /await rtwRefreshLedgerAfterDiagnostic\(realtimeWorkflowState\.runId\)/.test(asyncFunctionBody('rtwRunImageInputDiagnosticSelfTest')) &&
  /window\.rtwFetchWorkflowLedger = rtwFetchWorkflowLedger/.test(html) &&
  /window\.rtwLoadWorkflowLedgerRun = rtwLoadWorkflowLedgerRun/.test(html) &&
  /window\.rtwRefreshLedgerAfterDiagnostic = rtwRefreshLedgerAfterDiagnostic/.test(html)
);
check('Workflow ledger detail is normalized without mutating current run',
  /function rtwNormalizeWorkflowLedgerDetail/.test(html) &&
  /missingNodeIds/.test(functionBody('rtwNormalizeWorkflowLedgerDetail')) &&
  /expectedNodeCount: RTW_NODE_DEFS\.length/.test(functionBody('rtwNormalizeWorkflowLedgerDetail')) &&
  /artifacts: Array\.isArray\(snapshot\.artifacts\)/.test(functionBody('rtwNormalizeWorkflowLedgerDetail')) &&
  /logs: Array\.isArray\(snapshot\.logs\)/.test(functionBody('rtwNormalizeWorkflowLedgerDetail')) &&
  /selected: detail/.test(functionBody('rtwLoadWorkflowLedgerRun')) &&
  !/realtimeWorkflowState\\s*=\\s*detail/.test(functionBody('rtwLoadWorkflowLedgerRun')) &&
  /实时工作流记录损坏：latest\.json 无法解析/.test(server)
);
check('Realtime run mode is fixed to node workflow',
  /<input type="hidden" id="agent-rtw-mode" value="node-workflow">/.test(html) &&
  /id="agent-rtw-run-controls"/.test(html) &&
  /启动节点工作流/.test(html) &&
  !/开始实时建模/.test(html) &&
  !/<option value="legacy">/.test(html) &&
  /agentState\.realtimeWorkflowMode = 'node-workflow';\s*await rtwRunWorkflow\(\);\s*return;/.test(html)
);
check('Cleanup clears the active Blender scene without deleting project assets/config',
  /RTW_CLEANUP_RESULT=/.test(html) &&
  /policy: 'full_blender_scene'/.test(html) &&
  /rtwCallMcp\('cleanup', 'clear_scene'/.test(asyncFunctionBody('rtwRunCleanupNode')) &&
  /keep_camera: false, keep_lights: false/.test(asyncFunctionBody('rtwRunCleanupNode')) &&
  /world_reset/.test(asyncFunctionBody('rtwRunCleanupNode')) &&
  /项目资产库和配置文件未触碰/.test(html)
);
check('Deferred revision slots are validated only when needed',
  /function rtwRequireConfiguredModelSlot/.test(html) &&
  !/'taskRevision'/.test(functionBody('rtwRequiredModelSlotsForCurrentInput')) &&
  !/'totalRevision'/.test(functionBody('rtwRequiredModelSlotsForCurrentInput')) &&
  !/'whiteMatteSeed'/.test(functionBody('rtwRequiredModelSlotsForCurrentInput')) &&
  !/'whiteMatteCompare'/.test(functionBody('rtwRequiredModelSlotsForCurrentInput')) &&
  /rtwRequireConfiguredModelSlot\('taskRevision', nodeId/.test(html) &&
  !/rtwRequireConfiguredModelSlot\('totalRevision', 'total_revision'/.test(html)
);
check('Legacy scene-template hints are stripped in node workflow',
  /function rtwStripLegacySceneTemplateHints/.test(html) &&
  /【场景模板参考】/.test(html) &&
  /rtwStripLegacySceneTemplateHints\(descEl\?\.value \|\| agentState\.sceneDescription \|\| ''\)/.test(html)
);
check('Dry-run image generation branch exists', /function rtwDryRunImageDataUrl/.test(html) && /诊断模式生成模拟/.test(html));
check('Dry-run text\/vision model branch exists', /function rtwDryRunTextModelResponse/.test(html) && /诊断模式模拟模型调用/.test(html));
check('Dry-run Blender MCP branch exists', /function rtwDryRunMcpResponse/.test(html) && /诊断模式模拟 Blender 工具/.test(html));
check('Dry-run Hunyuan world branch exists', /诊断模式模拟混元世界生成与导入/.test(html));
check('Failure and abort audits exist', /outcome: 'failed'/.test(html) && /outcome: 'aborted'/.test(html));
check('Workflow audit artifact exists', /workflow_requirement_audit/.test(html));
check('Structured node log contracts exist',
  /function rtwCreateNodeContractLog/.test(html) &&
  /kind: 'node_contract'/.test(functionBody('rtwCreateNodeContractLog')) &&
  /inputs: nodeRun\.inputs \|\| \{\}/.test(functionBody('rtwCreateNodeContractLog')) &&
  /outputs/.test(functionBody('rtwCreateNodeContractLog')) &&
  /model: nodeRun\.model \|\| null/.test(functionBody('rtwCreateNodeContractLog')) &&
  /tool: nodeRun\.tool \|\| null/.test(functionBody('rtwCreateNodeContractLog')) &&
  /error: nodeRun\.error \|\| ''/.test(functionBody('rtwCreateNodeContractLog')) &&
  /reason/.test(functionBody('rtwCreateNodeContractLog')) &&
  /score/.test(functionBody('rtwCreateNodeContractLog')) &&
  /function rtwValidateNodeLogContracts/.test(html) &&
  /allNodesHaveStructuredContracts/.test(html)
);
check('Node model outputs have contract validation',
  /function rtwValidateNodeOutput/.test(html) &&
  /function rtwValidatePromptAOutput/.test(html) &&
  /function rtwValidatePromptBOutput/.test(html) &&
  /function rtwValidateGlobalPlannerOutput/.test(html) &&
  /function rtwValidateTaskCheckOutput/.test(html) &&
  /function rtwValidateVisualGateOutput/.test(html) &&
  /function rtwValidateCodeOutput/.test(html) &&
  /function rtwValidateImageArtifactOutput/.test(html) &&
  /rtwValidateNodeOutput\('prompt_a', rtwExtractJsonObject/.test(html) &&
  /rtwValidateNodeOutput\('prompt_b', rtwExtractJsonObject/.test(html) &&
  /rtwValidateNodeOutput\('global_planner', rtwExtractJsonObject/.test(html) &&
  /rtwValidateNodeOutput\('task_isolation_check', rtwExtractJsonObject/.test(html) &&
  /rtwValidateNodeOutput\('perspective_gate', rtwExtractJsonObject/.test(html) &&
  /rtwValidateCodeOutput\(nodeId, code/.test(html) &&
  /rtwValidateImageArtifactOutput\(nodeId, artifactType, dataUrl\)/.test(html)
);
check('R18 audit validates all structured contract fields',
  /hasInputs/.test(functionBody('rtwValidateNodeLogContracts')) &&
  /hasOutputs/.test(functionBody('rtwValidateNodeLogContracts')) &&
  /hasModel/.test(functionBody('rtwValidateNodeLogContracts')) &&
  /hasTool/.test(functionBody('rtwValidateNodeLogContracts')) &&
  /hasError/.test(functionBody('rtwValidateNodeLogContracts')) &&
  /hasReason/.test(functionBody('rtwValidateNodeLogContracts')) &&
  /hasScore/.test(functionBody('rtwValidateNodeLogContracts')) &&
  /allNodesHaveStructuredContracts: logContracts\.ok/.test(requirementAuditBody) &&
  /failedContracts: logContracts\.failed/.test(requirementAuditBody) &&
  /taskCheckScores: taskChecks\.map/.test(requirementAuditBody) &&
  /perspectiveGateScore: nodes\.perspective_gate\?\.score/.test(requirementAuditBody)
);
check('Startup validation failures are audited',
  /rtwSetNodeStatus\('input_router', 'running', \{ inputs: \{ textPresent: false, imageCount: 0 \} \}\)/.test(html) &&
  /const inputType = desc \? 'text' : \(hasImageInput \? 'image' : ''\)/.test(html) &&
  /rtwValidateRequiredModelSlots\(inputType\)/.test(html)
);
check('Input routing treats any text as image1 and pure image enters visual split directly',
  /const inputType = desc \? 'text' : \(hasImageInput \? 'image' : ''\)/.test(html) &&
  /rtwNormalizeDataImage\(realtimeWorkflowState\.input\.image, settings\.imageSize\)/.test(asyncFunctionBody('rtwRunInputRouterNode')) &&
  /input_aux_reference_image/.test(asyncFunctionBody('rtwRunInputRouterNode')) &&
  /纯图片输入跳过主参考图生成/.test(asyncFunctionBody('rtwRunInputRouterNode')) &&
  !/await rtwRunWhiteMatteSeedNode\(\);/.test(asyncFunctionBody('rtwRunWorkflow')) &&
  !/white_matte_seed/.test(functionBody('rtwRunInputRouterNode'))
);
check('Reference-guided image proxy exists', /reference_image/.test(server) && /reference_guided/.test(server));
check('Realtime docs exist',
  fs.existsSync(path.join(root, 'docs', 'superpowers', 'specs', '2026-06-17-realtime-render-node-workflow-design.md')) &&
  fs.existsSync(path.join(root, 'docs', 'superpowers', 'specs', '2026-06-17-realtime-render-node-workflow-implementation-plan.md'))
);

const failed = checks.filter(c => !c.pass);
for (const c of checks) {
  const mark = c.pass ? 'ok' : 'FAIL';
  console.log(`${mark} - ${c.name}${c.detail ? ` (${c.detail})` : ''}`);
}

if (failed.length > 0) {
  console.error(`\nRealtime workflow check failed: ${failed.length} issue(s)`);
  process.exit(1);
}

console.log(`\nRealtime workflow check passed: ${checks.length} checks`);
