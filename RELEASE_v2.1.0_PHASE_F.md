# v2.1.0 Phase F · aichat_bridge 插件 2.0.4 → 2.1.0

> 详细 Added/测试详情已写入 [`CHANGELOG.md`](./CHANGELOG.md) 的 [2.1.0] 段「Added · 🛡 Phase F」+ ROADMAP「Phase F ✅」。本文件做接力索引。

## ✅ 一句话总结

新增 **3 HTTP 端点 + 软回滚机制**：`GET /blend_summary`（场景概览）+ `POST /bookmark_state` / `POST /restore_state`（修复失败回滚）。三处版本号同步 bump 到 2.1.0，重打 zip 28K。端到端测试 5/5 全过。

## 📂 改动文件

- `blender_addon/aichat_bridge/__init__.py` ~+250 行：3 个 main-thread handler + 注册到 MCP_MAIN_HANDLERS + 2 处 HTTP 路由（do_GET 加 /blend_summary，do_POST 加 /bookmark_state + /restore_state）+ /ping snapshots 字段 + N 面板新 box + 三处版本号 bump
- `blender_addon/README.md`：API 表格新增 v2.1.0 三行 + 软回滚原理说明
- `blender_addon/aichat_bridge.zip`：23K → 28K 重打
- `CHANGELOG.md`：[2.1.0] 段顶部补 Phase F Added 块 + ROADMAP Phase F 标 ✅

## 🔬 三个端点设计精华

### 1) GET /blend_summary（token-friendly 场景概览）

返回 7 大字段：blend_file（filepath/is_saved/is_dirty/size_human）+ object_counts（total + by_type 按 MESH/LIGHT/CAMERA 分组）+ collection_tree（递归，max_depth=6）+ render_settings（engine/resolution/samples/view_transform/exposure 等）+ active_camera + world + 一句话 summary + snapshots_count/keys。整体 < 2KB，比 get_scene_info 的几十 KB 小一个数量级。**给 Critic 审图前快速摸场景用**。

### 2) POST /bookmark_state（场景内存快照）

把当前场景以 JSON 形式快照到全局字典 `_BLEND_SNAPSHOTS[name]`：每物体保存 transform / parent / material 名 / vertex_count / poly_count / hide_* 等元数据，**不存** mesh 顶点几何（防爆内存——5 物体场景 ~1.3KB，100 物体场景 ~30KB）。**给"修复失败回滚"用**。

### 3) POST /restore_state（软回滚机制）

软回滚行为：① 删除自快照以来新增的物体（current - snap）② 还原仍存在物体的 location/rotation/scale/hide_*（current ∩ snap）③ 还原 frame_current 和 active_camera（best-effort）④ 已被删的复杂 mesh 几何**无法重建**会列在 `missing` 字段告知。返回 `summary` 给 LLM 一句话摘要："已删除 2 个新增物体，恢复 4 个物体 transform，⚠️ 1 个物体已丢失无法重建（Sphere）"

## 🧪 端到端测试 5/5 全过

详见 `/tmp/_test_phaseF.py`（mock bpy + exec 加载插件源 + 取出三个 handler 真跑）：

1. **blend_summary 完整字段验证**（含集合树嵌套 Scene Collection → Furniture）
2. **bookmark_state 空 name 拦截 + 内存验证 + 多 key 累加**（baseline + before_furniture_fix 两个 key 同存）
3. **restore_state 边界 + 软回滚**（删 2 新增 Wall_NEW/Wall2_NEW + 还原 4 transform Cube/Floor/Sun/Camera + 1 missing Sphere 告知）
4. **工具函数边界**：`_human_bytes`（0/1023/1024/1.5MB 全过）+ `_walk_collection max_depth=6`（10 层嵌套被截断到 6 层，防极端嵌套爆栈）
5. **多版本快照工作流**：T1 → T2 加 Chair → T3 改坏 Cube + 加 BAD_OBJ → restore T2（保留 Chair 删 BAD_OBJ 还原 Cube）→ restore T1（也删 Chair）

输出片段：
```
[AIChat] INFO: bookmark_state 'baseline' = 5 objects (1.3 KB)
[AIChat] INFO: restore_state 'baseline': -2 new, ~4 transform, missing=1
  restore 摘要: 已删除 2 个新增物体，恢复 4 个物体 transform，⚠️ 1 个物体已丢失无法重建（Sphere）
  Cube 还原 OK: location=(0.0, 0.0, 1.0) rotation=(0.0, 0.0, 0.0)
🎉 全部 5 个测试通过 (5/5) — Phase F 实施完成 ✅
```

## 🔗 zip 完整性 verified

```
$ unzip -l aichat_bridge.zip
   105419  05-18-2026 17:27   aichat_bridge/__init__.py
     3598  05-16-2026 18:06   aichat_bridge/README.md

$ unzip -p aichat_bridge.zip aichat_bridge/__init__.py | grep -E '"version"|ADDON_VERSION|aichat-bridge/'
"version": (2, 1, 0),
ADDON_VERSION = "2.1.0"
REQ_HEADERS = {"User-Agent": "aichat-bridge/2.1.0"}
```

## 🎓 软回滚工作流（建议给 Modeler/Critic 主循环用）

```
1. Modeler 改场景前 → POST /bookmark_state {name:'before_furniture_fix'}
2. Modeler 跑工具调用建/改物体...
3. Critic 审图 → 发现失败 → reflect()
4. POST /restore_state {name:'before_furniture_fix'}（删新增 + 还原 transform）
5. Modeler 重新尝试，避免越改越烂
```

## 🤝 与 Phase A/B/C/D/E 协作矩阵

| Phase | 与 F 协作 |
| --- | --- |
| A · Plan-Execute-Reflect | Modeler 决定每轮要不要先 bookmark_state（plan 步骤层面） |
| B · 文件系统 | 快照的 summary 字段可以被 workspace_write_file 落到磁盘做长期归档 |
| C · bpy cheatsheet | search_bpy_docs 之外，AI 也能调 blend_summary 摸场景再决定查啥 |
| D · 多角色协作 | 关键! Modeler 改场景前 bookmark、Critic 审图后判断要不要 restore |
| E · bmesh 模板 | apply_template 失败时回退到 bookmark_state 之前的状态 |

## 🚧 下一步：Phase G（独立会话，1 天）

- 欢迎弹窗 key bump 到 `hasLaunched_v2.1.0_final`
- 折叠 v1.11.5~v1.11.14 到历史区
- README.md 第 1 章重写为「v2.1 Codex CAD 范式」
- 重打 4 个 dmg/exe（mac arm64+x64 / win arm64+x64）
- **⚠️ 用户操作**：装 v2.1.0 dmg 后必须在 Blender 里重装一次新 `aichat_bridge.zip`（旧 2.0.4 插件不会因 dmg 升级自动覆盖，否则前端 agentState.snapshots/UI 看不到新端点）

## 📌 接力下次会话 prompt

```
我在 /Users/Apple/Desktop/ai-chat 项目继续 v2.1.0 Codex CAD 范式重构。
当前已完成 Phase A/B/C/D/E/F（详见 CHANGELOG [2.1.0] 段 + ROADMAP）。
剩 Phase G 待做：
- 欢迎弹窗 key bump 到 hasLaunched_v2.1.0_final
- 折叠 v1.11.5~v1.11.14 到历史区
- README.md 第 1 章重写为「v2.1 Codex CAD 范式」
- 重打 4 个 dmg/exe（mac arm64+x64、win arm64+x64）
请先读 CHANGELOG [2.1.0] 段 + RELEASE_v2.1.0_PHASE_F.md，然后开干 Phase G。
```
