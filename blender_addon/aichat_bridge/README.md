# 一键3D建模 · 使用说明

把「白歌的AI讨论组」网页里的聊天记录 → 自动转成 Blender 场景。

## 整体链路
```
聊天记录 ──Step1──▶ SceneSummary(JSON)
                 ──Step2──▶ 4 张多角度参考图
                 ──Step3──▶ SceneSpec(JSON 含尺寸/材质/光影)
                 ──Step4──▶ Blender Python 代码
                 ──Step5──▶ Blender 自动建模 & 渲染
```
5 步全在网页端完成；Step 5 一键推送到本机 Blender。

## 一、安装 Blender 插件
1. 把 `aichat_bridge/` 整个文件夹拷到 Blender addons 目录：
   - **macOS**: `~/Library/Application Support/Blender/<版本>/scripts/addons/`
   - **Windows**: `%APPDATA%\Blender Foundation\Blender\<版本>\scripts/addons/`
   - **Linux**: `~/.config/blender/<版本>/scripts/addons/`
2. 启动 Blender → Edit → Preferences → Add-ons → 搜索 **AIChat Bridge** → 勾选启用
3. 默认会自动监听 `http://127.0.0.1:9876`
4. 在 3D 视图按 **N** → 找到「AIChat」面板，确认显示「● 运行中」

> 也可以打包成 zip 后用 Add-ons → Install... 安装。

## 二、网页端使用流程
1. 启动 ai-chat 服务（`node server.js`），打开 `http://localhost:3456`
2. 切到 **摄影工具** → 新建项目 → 顶部子 tab 选 **🧊 一键3D建模**
3. 左侧选好：
   - 文本/视觉大模型 API（建议 GPT-4o / Claude-3.5 / Gemini-Pro-Vision）
   - 图像生成 API（建议 gpt-image-1 / DALL·E 3 / SD3 / FLUX）
   - Blender URL：默认 `http://127.0.0.1:9876`，点 🩺 测试连接
4. 中央依次点：
   - **Step 1** 📚 选择聊天记录（从你之前讨论场景的会话里挑）
   - **Step 2** ✨ 生成 SceneSummary
   - **Step 3** 📸 生成 4 张参考图（前/侧/顶/45°）
   - **Step 4** 📏 解析 SceneSpec（带视觉模型时会看图测算）
   - **Step 5** 🐍 生成 bpy 脚本
5. 点底部红色按钮 **🚀 一键推送 Blender 自动建模**，切到 Blender 窗口即可看到结果

## 三、后端 API
| 路径 | 方法 | 作用 |
| --- | --- | --- |
| `/api/image/generate` | POST | 图像生成代理，自动尝试 `/v1/images/generations`，失败 fallback 到 chat completions |
| `/api/blender/exec` | POST | （可选）后端转发到 Blender，用于服务部署在远端时 |
| `/api/blender/ping` | GET | 同上，连通性探测 |

## 四、Blender 插件 API
| 路径 | 方法 | 作用 |
| --- | --- | --- |
| `GET /ping` | 返回 `{ok, blender, queue_size}` |
| `POST /exec` | body `{code, scene_name}`，把代码入主线程队列异步执行 |
| `GET /log` | 最近 20 条执行日志 |

**线程安全**：HTTP 在后台线程接收，`bpy.app.timers` 每 0.2s 在主线程 `exec()`，避免 `bpy.data` 跨线程崩溃。

## 五、常见问题
- **测试连接失败**：先在 N 面板点「启动桥接」；防火墙放行 9876；端口冲突就在 Preferences 改端口。
- **图像生成失败**：换模型；或在 Step 3 跳过直接做 Step 4（视觉模型只看 SceneSummary 也能给合理估算）。
- **Blender 卡住**：生成的脚本可能含死循环 / 极大 mesh，到 Text 编辑器找 `aichat_<场景名>` 手动检查。
- **跨机器使用**：把网页端「Blender URL」填成 `http://<Blender所在机器IP>:9876`，并保证插件 host 改成 `0.0.0.0`。

## 六、数据
全部状态（SceneSummary / 4 张图 / SceneSpec / 代码）都跟随当前「摄影项目」一起持久化到 `data/sessions.json` 的 `photo_data.model3d` 字段，下次打开自动恢复。
