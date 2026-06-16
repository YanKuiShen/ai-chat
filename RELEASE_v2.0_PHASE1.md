# 🚀 v2.0 Phase 1 完成说明 —— Blender 插件 aichat_bridge 升级 1.2.0 → 2.0.0

> 完成日期：2026/5/17 · 上游：v1.9.6
> 目标：按 [`RELEASE_v2.0_MCP_ROADMAP.md`](./RELEASE_v2.0_MCP_ROADMAP.md) Phase 1，给 Blender 插件加上 **MCP 工具协议层**（实际落地 **16 个**原子化操作端点，比路线图原计划的 15 个多 1 个），为后续 Phase 2/3 的 Agent 循环架构铺路。
>
> **与路线图的差异说明**：路线图列了 15 个 tool（含 `download_polyhaven_asset` 和 `append_polyhaven_blend` 两个），实际实现时把它们合并为单个 `import_polyhaven_model`（先下载再 import 一气呵成，更符合 Agent 调用习惯），同时新增了 `list_objects`（轻量列表）和 `clear_scene`（场景清理）两个高频实用工具，净结果 +1。

---

## ✅ 本次完成清单

### 1. 版本号 + bl_info 升级

| 字段 | 旧 | 新 |
|------|----|----|
| `bl_info.version` | `(1, 2, 0)` | `(2, 0, 0)` |
| `ADDON_VERSION` 字符串 | `"1.2.0"` | `"2.0.0"` |
| `REQ_HEADERS` UA | `aichat-bridge/1.2.0` | `aichat-bridge/2.0.0` |
| `bl_info.description` | v1.2.0 文案 | v2.0.0 加 MCP tool layer，强调 Agent-loop |

### 2. 新增 MCP Tool 实现层（约 700 行新代码）

`__init__.py` 文件从 871 行 → **1872 行**（83 KB）。在 `_capture_viewport_screenshot_main` 之后、`_Handler` class 之前注入：

#### 2.1 16 个 tool（其中 14 个有独立主线程 handler，另外 2 个特例：viewport_screenshot 复用 v1.2.0 任务、search_polyhaven_assets 走 handler 线程）

```
观察类（4个）
├─ _mcp_get_scene_info_main      复用 _collect_scene_report，objects 截 60 防爆 token
├─ _mcp_get_object_info_main     单物体详情：location/rotation/scale/dimensions/materials/world_bbox/mesh_stats
├─ _mcp_list_objects_main        轻量列表（仅 name/type/location），可按 type 过滤
└─ get_viewport_screenshot       特例：复用 v1.2.0 的 screenshot 主线程任务

创建类（3个）
├─ _mcp_add_primitive_main       支持 cube/sphere/ico_sphere/cylinder/cone/plane/torus/monkey
├─ _mcp_add_light_main           支持 POINT/SUN/SPOT/AREA + energy/color
└─ _mcp_set_camera_main          创建或更新相机（自动设 active），支持 lens/location/rotation

修改类（4个）
├─ _mcp_update_object_main       改 location/rotation/scale/visible（只传需要改的字段）
├─ _mcp_set_material_main        Principled BSDF 一把梭：base_color/roughness/metallic/emission
├─ _mcp_delete_object_main       删除指定物体
└─ _mcp_clear_scene_main         清空场景（默认保留相机+灯光，可指定全清）

PolyHaven 类（3个，混合路由）
├─ _polyhaven_search_api         (handler 线程) PolyHaven REST API + 多字段加权打分（asset_id +100 / name +20 / tags +10 / cats +5）
├─ _mcp_set_world_hdri_main      (主线程) 把已下载的 HDRI 设为世界环境
└─ _mcp_import_polyhaven_model_main  (主线程) 导入 PolyHaven 模型（支持 gltf/blend）

兜底+质检（2个）
├─ _mcp_exec_python_main         主线程兜底执行任意 Python（捕获 stdout）
└─ _mcp_quality_check_main       4 维度场景自检（不抛错，返回 issues 列表）
```

#### 2.2 路由表 + Schema 注册表

```python
MCP_MAIN_HANDLERS = { 14 个 main-thread tool 名 → 函数 }   # _drain_queue 用
MCP_TOOLS = [ 16 个 tool 的 OpenAI tools 格式 schema ]    # /mcp/tools 端点用
```

路由分布：`main`=13 / `thread`=1（PolyHaven 搜索）/ `mixed`=2（PolyHaven HDRI + 模型导入）。

每个 tool 的 schema 含 `_route` 字段标记调度策略：
- `main`：丢给 `_post_to_main()` 主线程
- `thread`：在 HTTP handler 线程直接跑（只读 / 纯网络）
- `mixed`：handler 线程下载文件 → 主线程 import

#### 2.3 统一调度入口 `_mcp_call(tool_name, args)`

供 `/mcp/call` 和 `/mcp/<tool_name>` 共用，返回 `{ok: true, data: ...}` 或 `{ok: false, error: ...}`。包含 PolyHaven HDRI/模型下载 → 主线程 import 的两段式实现。

### 3. 扩展 `_drain_queue` 主线程 dispatcher

新增 `mcp_<tool_name>` 任务前缀的统一处理：

```python
elif ttype.startswith("mcp_"):
    tool_name = ttype[4:]
    handler = MCP_MAIN_HANDLERS.get(tool_name)
    if handler is None:
        ref["error"] = "no main-thread handler for mcp tool: %s" % tool_name
    else:
        ref["data"] = handler(payload)
```

### 4. 新增 HTTP 端点

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/mcp/tools` | 返回 16 个工具的 OpenAI tools 格式 schema |
| POST | `/mcp/call` | 通用调度：body `{tool, args}` |
| POST | `/mcp/<tool_name>` | 直接调对应工具，body 即 args |
| GET | `/ping` | **更新**：features 加 `mcp_tools`，新增 `mcp.{enabled, tool_count, tools}` 子对象 |

老端点 `/exec /scene_report /viewport_screenshot /hyper3d/* /sketchfab/* /config /log` **全部保留**（向后兼容 v1.x 客户端）。

### 5. N 面板更新

新增"v2.0 MCP 工具协议"信息盒：
```
v2.0 MCP 工具协议
  已注册 15 个工具
  端点: /mcp/tools · /mcp/call

v1.2.0 增值能力（兼容保留）
  Hyper3D: MAIN_SITE (免费 trial)
  Sketchfab: 未配置
```

Preferences 面板说明文字也同步更新："v2.0.0 新增：MCP 工具协议（16 个原子工具）+ Agent 循环架构 / 向后兼容：v1.x 客户端继续可用"。

### 6. 重新打包

```
blender_addon/aichat_bridge.zip   23 KB（含 __init__.py 85 KB / README.md 3.5 KB）
```

---

## 🧪 自测建议

1. **安装 zip**：在 Blender 里 Edit → Preferences → Add-ons → Install... → 选 `aichat_bridge.zip` → 启用
2. **Ping 检查**：浏览器或 curl 访问 `http://127.0.0.1:9876/ping` → 返回应包含：
   ```json
   {
     "addon_version": "2.0.0",
     "features": [..., "mcp_tools"],
     "mcp": { "enabled": true, "tool_count": 16, "tools": [16 个名字] }
   }
   ```
3. **拉取 schema**：`curl http://127.0.0.1:9876/mcp/tools` → 返回 OpenAI tools 格式数组（应是 16 条）
4. **试调一个工具**：
   ```bash
   # 列出场景所有物体
   curl -X POST http://127.0.0.1:9876/mcp/call -H 'Content-Type: application/json' \
        -d '{"tool":"list_objects","args":{}}'

   # 加一个红色立方体
   curl -X POST http://127.0.0.1:9876/mcp/call -H 'Content-Type: application/json' \
        -d '{"tool":"add_primitive","args":{"type":"cube","location":[0,0,1],"name":"TestCube"}}'
   curl -X POST http://127.0.0.1:9876/mcp/call -H 'Content-Type: application/json' \
        -d '{"tool":"set_material","args":{"obj_name":"TestCube","base_color":[1,0,0],"roughness":0.5}}'

   # 搜 PolyHaven HDRI
   curl -X POST http://127.0.0.1:9876/mcp/call -H 'Content-Type: application/json' \
        -d '{"tool":"search_polyhaven_assets","args":{"query":"sunset","asset_type":"hdris","limit":5}}'

   # 质检
   curl -X POST http://127.0.0.1:9876/mcp/call -H 'Content-Type: application/json' \
        -d '{"tool":"quality_check","args":{}}'
   ```
5. **向后兼容**：原 `/exec` `/scene_report` `/viewport_screenshot` `/hyper3d/*` `/sketchfab/*` 全部应继续可用 —— v1.9.6 客户端不需要做任何改动

---

## 🚧 下一步：Phase 2

按 `RELEASE_v2.0_MCP_ROADMAP.md` Phase 2（半天工作量）：

- 在 `server.js` 新增 `POST /api/mcp/call` 透传到 Blender `/mcp/<tool_name>`
- 新增 `GET /api/mcp/tools` 透传 schema
- 统一错误处理 + 超时
- PolyHaven 代理（`/api/polyhaven/search` 等）保留给 Blender 端 MCP tool 内部调用

之后 Phase 3 才是大头：前端 Agent 循环（4 天工作量）。

---

## 📋 兼容性说明

- **v1.x 用户**：插件不重装也能用 v1.9.6（一切照旧），但要享受 v2.0 Agent 模式必须重装本 zip
- **零破坏**：所有 v1.x 端点 100% 保留，行为不变
- **依赖**：仍然只依赖 `requests`（与 v1.2.0 一致）

---

## 📝 关键文件清单

| 文件 | 改动 |
|------|------|
| `blender_addon/aichat_bridge/__init__.py` | 871 → **1872 行**：新增 MCP 工具层（~700 行）、扩展 dispatcher、新增 HTTP 路由、N 面板新增 MCP 状态盒 |
| `blender_addon/aichat_bridge.zip` | 重新打包，23 KB |
| `RELEASE_v2.0_PHASE1.md` | 本文件 |
| `CHANGELOG.md` | 新增 v2.0.0-phase1 段落 |

---

## 🔗 相关文档

- 上游：[`RELEASE_v1.9.6.md`](./RELEASE_v1.9.6.md)（资产选择器 · 临时止血方案）
- 全景蓝图：[`RELEASE_v2.0_MCP_ROADMAP.md`](./RELEASE_v2.0_MCP_ROADMAP.md)
- 参考：[`blender-mcp-main/addon.py`](./blender-mcp-main/addon.py)（ahujasid/blender-mcp）

> Phase 1 ✅ 完成 · Phase 2 🚧 待启动
