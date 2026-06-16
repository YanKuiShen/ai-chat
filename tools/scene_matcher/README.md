# 🎯 场景模板智能匹配器（Scene Matcher）

> ai-chat v2.1.0 Phase H 引入的「自然语言 → 7 维特征向量 → 加权欧氏距离 → Top-K 模板推荐」工具。
> 面板挂在「🎬 智能 Agent 实时渲染」视图，主输入框 `#agent-scene-desc` 下方折叠面板 `#sm-panel` 中。

- 模板总数：**98**（id 1~98，与 `ai-chat/scripts/bmesh-templates.json` 顺序一致）
- 数据源：`ai-chat/tools/scene_matcher/data.js`
- 生成器：`ai-chat/tools/scene_matcher/export.js`
- 前端加载：`ai-chat/public/scene_features.json`（fetch 加载）
- 人读表格：`ai-chat/tools/scene_matcher/features_table.md`
- localStorage key：`sm_state_v210h`

---

## 1. 7 维特征定义

> ⚠️ 真实 key 以 `scene_features.json → feature_keys` 为准，不要用早期文档里写的 `terrain/sky/lighting/mood/scale/detail/palette`（那是占位草稿）。

| # | key | 中文标签 | 取值含义（0 → 1） |
|---|---|---|---|
| 1 | `ground_rough` | 地面粗糙度 | 0 = 镜面平整  →  1 = 极崎岖凹凸（terrain / 雪地 / 裂痕） |
| 2 | `cloud_amount` | 云量 | 0 = 无云  →  1 = 厚云密布 |
| 3 | `cloud_blur` | 云模糊度 | 0 = 锐利积云  →  1 = 朦胧/雾感 |
| 4 | `struct_complex` | 结构复杂度 | 0 = 单 primitive  →  1 = 多部件机械（车/电车/电线杆） |
| 5 | `texture_rich` | 纹理丰富度 | 0 = 纯色塑料  →  1 = PBR 木纹/砖墙 |
| 6 | `dynamic` | 动态程度 | 0 = 纯静态  →  1 = 粒子/瀑布/闪电/缎带 |
| 7 | `color_warm` | 色调冷暖 | 0 = 冰蓝钢灰  →  0.5 = 中性  →  1 = 日落金红 |

所有维度都被规范到 `[0, 1]`。手工标注（98 条都有），数据稳定可复现。

模板覆盖类别（10 类）：
室内家具 · 自然场景 · 日式二次元 · 都市街道 · 室内场景 · 摄影棚 · CG特效 · 建筑废墟 · 武器装备 · 载具

---

## 2. 加权欧氏距离公式

```
       ┌─────────────────────────────┐
d  =   │  Σᵢ  wᵢ · (qᵢ − tᵢ)²   │
       │  ─────────────────────  │   ← 再开方
       │        Σᵢ  wᵢ           │
       └─────────────────────────────┘
```

- `qᵢ`：用户需求的第 i 维分量（由提取 AI 给出）
- `tᵢ`：模板的第 i 维分量
- `wᵢ`：第 i 维权重，**默认 1.0**；勾选「AI 推权重」后由提取 AI 在 JSON 里返回 `weights` 字段（每个维度可以不同）
- 分母 `Σwᵢ` 做归一化，让距离始终落在 `[0, 1]` 量级，方便和阈值比

JS 实现（节选自 `index.html → smCalcDistance`）：

```js
function smCalcDistance(a, b, weights) {
  let sum = 0, wSum = 0;
  for (const k of smState.featureKeys) {
    const va = parseFloat(a[k]);
    const vb = parseFloat(b[k]);
    if (!isFinite(va) || !isFinite(vb)) continue;
    const w = (weights && isFinite(weights[k])) ? weights[k] : 1.0;
    sum  += w * (va - vb) * (va - vb);
    wSum += w;
  }
  return wSum === 0 ? Infinity : Math.sqrt(sum / wSum);
}
```

---

## 3. 双 AI 调用时序

```
用户输入「崎岖地面 + 薄云 + 冷色调」
        │
        ▼
┌──────────────────────────────────┐
│ ① 提取 AI                       │   ← #sm-extract-config + #sm-extract-model
│   自然语言 → JSON                 │     prompt 要求严格输出 {features:{...}, weights?:{...}}
│   { features:{...7维...},        │
│     weights? :{...7维...} }      │   ← 仅当勾选「AI 推权重」时才请求 weights
└──────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────┐
│ ② 本地算距离                    │
│   对 98 条模板逐条算 smCalcDistance │
│   排序 → 取 Top-K (默认 3)       │
└──────────────────────────────────┘
        │
        ▼
   ┌─────────────────────┐
   │ minDist ≤ threshold ?│
   └─────────────────────┘
        │             │
   是 ↙              ↘ 否
┌──────────┐    ┌────────────────────────────┐
│ 渲染 Top-K│    │ ③ 扩展 AI 兜底             │
│ 卡片     │    │  扩展 AI 接收用户描述 +     │
│  + 「📥 塞│    │  提取 AI 算好的 query 向量， │
│  回需求」│    │  生成一段新的场景 prompt    │
└──────────┘    │  追加到结果区               │
                └────────────────────────────┘
```

涉及函数（全部在 `index.html` 中，统一 `sm` 前缀）：

| 函数 | 作用 |
|---|---|
| `smInit()` | 加载 `scene_features.json` + 恢复 localStorage + 绑事件 |
| `smSaveState()` | 配置改动落盘 |
| `smOnExtractConfigChange()` / `smOnExtendConfigChange()` | 双下拉联动模型列表 |
| `smMatchAndAnalyze()` | 主入口：取 textarea → 调提取 AI → 算距离 → 渲染 / 调扩展 AI |
| `smCallExtractAI(configId, model, desc)` | 调用提取 AI，返回 `{features, weights?}` |
| `smCallExtendAI(configId, model, desc, queryFeatures)` | 阈值兜底时调用，返回新模板 prompt |
| `smCalcDistance(a, b, weights)` | 上面的加权欧氏距离 |
| `smRenderResults(query, weights, topK, threshold, needExtend, extended)` | 渲染 Top-K 卡片 + 扩展模板 |
| `smInjectIntoSceneDesc(templateName)` | 「📥 塞回需求」按钮回调，把模板 prompt 追加到 `#agent-scene-desc` |
| `smClearResults()` | 清空结果区 |

`smInit()` 已在 `agentInit()` 末尾用 `try { smInit(); } catch(e){}` 调用，所以切到 Agent 视图就会自动加载。

---

## 4. 阈值 / AI 推权重的作用

### 阈值（`#sm-threshold`，默认 `0.30`）

- 距离越小越像。归一化后的 `[0,1]` 量级里：
  - `d < 0.15` 几乎是同一类模板
  - `0.15 ≤ d ≤ 0.30` 比较接近，可直接用
  - `d > 0.30` 模板库里没有特别合身的 → 自动触发扩展 AI 兜底
- 阈值只影响「匹配 vs 兜底生成」的切换点，**不影响 Top-K 排序**。
- 滑块范围 `0.10 ~ 1.00`，步长 `0.05`，值同步显示在 `#sm-threshold-val`。

### AI 推权重（`#sm-ai-weights` checkbox）

- 默认 **关**，所有维度权重 = 1.0（等权欧氏距离）。
- 开启后，提取 AI 会被要求额外输出 `weights` 字段，让 AI 自己判断「这次需求里哪几个维度最关键」。
  - 例如用户说「**崎岖**地面 + **冷**色调」时，AI 应该把 `ground_rough` 和 `color_warm` 的权重调高（如 2.5），把其他维度调低（如 0.5），结果会更精准。
- AI 没返回 weights、或返回值不是有限数时，对应维度自动回落到 1.0。

---

## 5. 如何扩展模板库

只要 3 步：

```bash
# 1. 编辑数据
$EDITOR ai-chat/tools/scene_matcher/data.js
#    在 TEMPLATES 末尾追加一行：
#    [99, 'desert_dunes', '自然场景', '沙漠沙丘',
#         [0.75, 0.05, 0.10, 0.40, 0.80, 0.10, 0.85]],
#    7 个数字按 FEATURE_KEYS 顺序：ground_rough, cloud_amount, cloud_blur,
#                                  struct_complex, texture_rich, dynamic, color_warm
#    全部取 [0, 1]。

# 2. 重新导出
node ai-chat/tools/scene_matcher/export.js
#    会生成：
#    - ai-chat/public/scene_features.json   (前端 fetch)
#    - ai-chat/tools/scene_matcher/features_table.md (人读表格)

# 3. 刷新浏览器
#    smInit() 会重新 fetch，#sm-template-count 上的数字会自动更新
```

打标的小贴士：
- 先看一眼 `features_table.md` 里类似类别的几条参考，保持风格一致。
- 数值不用纠结小数第三位，**0.05 一档**够用；7 维之间相对差异比绝对值更重要。
- 想强调某个维度时，给到 `0.85+`；想压低时 `0.10-`；中性默认 `0.50`。
- `cloud_amount` / `cloud_blur` 对家具/武器/室内类一律给 `0`，没必要造云。

---

## 附：DOM ID 速查

| ID | 用途 |
|---|---|
| `#sm-panel` | 折叠面板根 `<details>` |
| `#sm-template-count` | 「(98 个模板)」标签 |
| `#sm-extract-config` / `#sm-extract-model` | 提取 AI 双下拉 |
| `#sm-extend-config`  / `#sm-extend-model`  | 扩展 AI 双下拉 |
| `#sm-threshold` / `#sm-threshold-val` | 阈值滑块 + 数值显示 |
| `#sm-ai-weights` | 「AI 推权重」checkbox |
| `#sm-results` | 结果展示区（Top-K 卡片 + 扩展模板） |
| `#agent-scene-desc` | 主场景需求 textarea（「📥 塞回需求」目标） |
| localStorage key | `sm_state_v210h` |

---

_生成于 v2.1.0 Phase H · 校对：node ai-chat/tools/scene_matcher/export.js && /tmp/_test_sm.js_
