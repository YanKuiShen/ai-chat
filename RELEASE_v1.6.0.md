# 🚀 白歌的AI讨论组 — v1.6.0 发布交付清单

> **发布日期**：2026-05-16  
> **核心主题**：摄影工具新增「一键 3D 建模」模块 + Blender 插件 `aichat_bridge`

---

## 📦 一、交付产物

| # | 产物 | 路径 | 大小 | 用途 |
|---|------|------|------|------|
| 1 | macOS dmg (Apple Silicon) | `dist/白歌的AI讨论组-1.6.0-arm64.dmg` | **111 MB** | M1/M2/M3 Mac 安装包 |
| 2 | macOS dmg (Intel) | `dist/白歌的AI讨论组-1.6.0-x64.dmg` | **116 MB** | Intel Mac 安装包 |
| 3 | Blender 插件 zip | `blender_addon/aichat_bridge.zip` | **6.0 KB** | 用户在 Blender 中通过"安装插件"加载 |
| 4 | Blender 插件源码 | `blender_addon/aichat_bridge/` | — | 可读源码（含 README） |

> ✅ **dmg 已内嵌 blender_addon**：安装应用后，插件 zip 位于  
> `白歌的AI讨论组.app/Contents/Resources/blender_addon/aichat_bridge.zip`

---

## 🔢 二、版本号一致性表

| 文件 | 字段 | 版本 |
|------|------|------|
| `package.json` | `version` | `1.6.0` ✅ |
| `package.json` | `description` | `… v1.6.0 …` ✅ |
| `public/index.html` | 更新弹窗标题 | `v1.6.0` ✅ |
| `public/index.html` | `localStorage` key | `hasLaunched_v1.6.0` ✅ |
| `blender_addon/aichat_bridge/__init__.py` | `bl_info.version` | `(1, 0, 2)` ✅ |
| `CHANGELOG.md` | 顶部章节 | `[1.6.0] - 2026-05-16` ✅ |

---

## ✨ 三、本次新增功能（用户视角）

### 1. 摄影工具 → 「一键 3D 建模」5 步工作流

| 步骤 | 名称 | 输入 | 产出 |
|------|------|------|------|
| 1 | 抓取聊天记录 | 当前对话 | 原始文本 |
| 2 | 模型总结场景设定 | 文本 + 选定模型 | 结构化场景 JSON |
| 3 | 多角度图片生成 | 场景 JSON + 选定图像模型 | 4 视角参考图 |
| 4 | AI 测算尺寸/材质/光影 | 场景 + 图片 | 物理参数 JSON |
| 5 | 生成 Blender Python 代码 | 步骤 4 结果 | 可执行 .py 脚本 |

### 2. Blender 端 `aichat_bridge` 插件

- 在 Blender 中本地启动 HTTP 服务（默认 `127.0.0.1:3457`）
- 接收 ai-chat 桌面端推送的代码并自动 `exec()` 执行
- 内置安全审查（黑名单：`os.system`、`subprocess`、`__import__('os')` 等）
- N 面板控件：开关服务 / 端口设置 / 日志查看

---

## 🧪 四、本地验证步骤

### macOS 端
```bash
open /Users/Apple/Desktop/ai-chat/dist/白歌的AI讨论组-1.6.0-arm64.dmg
# 拖入 Applications → 启动 → 摄影工具 → 一键3D建模
```

### Blender 端
```
Blender → Edit → Preferences → Add-ons → Install...
选择：白歌的AI讨论组.app/Contents/Resources/blender_addon/aichat_bridge.zip
启用：AI Chat Bridge
N 面板 → AI Bridge → Start Server
```

### 联调
桌面端工作流执行到第 5 步 → 自动 POST 到 `http://127.0.0.1:3457/exec` → Blender 视口实时建模 🎬

---

## 📚 五、文档

| 文档 | 作用 |
|------|------|
| `CHANGELOG.md` | 全量版本变更日志（含 v1.0.0 ~ v1.6.0） |
| `VERSIONING.md` | 版本号迭代铁律 + 发布 checklist |
| `blender_addon/README.md` | 插件安装/调试/安全说明 |
| `RELEASE_v1.6.0.md` | **本文档**，发布交付清单 |

---

## 🔄 六、下次迭代提示

按照 `VERSIONING.md` 铁律，**任何实质性改动前**必先：
1. 决定版本号：MAJOR / MINOR / PATCH
2. 同步更新 6 个版本字段（见上方一致性表）
3. 在 `CHANGELOG.md` 顶部新增章节
4. `npm run build:addon` + `npm run build:mac`
5. 更新 `RELEASE_vX.X.X.md`

---

**🎉 v1.6.0 发布完成！**
