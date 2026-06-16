# 🚀 白歌的AI讨论组 — v1.6.1 发布交付清单

> **发布日期**：2026-05-16  
> **版本类型**：PATCH（向后兼容的 bug 修复 + 优化）  
> **核心主题**：修复「一键3D建模 Step 3 破图 bug」+ 多角度图改为单图四宫格（针对 GPT Image 2 优化）

---

## 📦 一、交付产物

| # | 产物 | 路径 | 大小 | 用途 |
|---|------|------|------|------|
| 1 | macOS dmg (Apple Silicon) | `dist/白歌的AI讨论组-1.6.1-arm64.dmg` | ~111 MB | M1/M2/M3 Mac 安装包 |
| 2 | macOS dmg (Intel) | `dist/白歌的AI讨论组-1.6.1-x64.dmg` | ~116 MB | Intel Mac 安装包 |
| 3 | Blender 插件 zip | `blender_addon/aichat_bridge.zip` | 6.0 KB | **未变更**，仍为 v1.0.2，无需重装 |

> ✅ **dmg 已内嵌 blender_addon**：安装应用后，插件 zip 位于  
> `白歌的AI讨论组.app/Contents/Resources/blender_addon/aichat_bridge.zip`

---

## 🔢 二、版本号一致性表

| 文件 | 字段 | 版本 |
|------|------|------|
| `package.json` | `version` | `1.6.1` ✅ |
| `package.json` | `description` | `… v1.6.1 …` ✅ |
| `public/index.html` | 更新弹窗标题 | `v1.6.1` ✅ |
| `public/index.html` | `localStorage` key | `hasLaunched_v1.6.1` ✅ |
| `blender_addon/aichat_bridge/__init__.py` | `bl_info.version` | `(1, 0, 2)` ⚠️ 本次未变更 |
| `CHANGELOG.md` | 顶部章节 | `[1.6.1] - 2026-05-16` ✅ |

---

## 🐛 三、本次修复（用户视角）

### 🐛 修复：Step 3 多角度图破图 bug
- **症状**：第 3 步生成图片后，4 个视角格子里只有破图小图标，无法判断是 URL 失效、CORS、还是网络问题
- **修复**：
  - 新增 `m3dValidateImageUrl(url)` 预检图片可达性
  - base64 数据直接通过；远程 URL 8 秒超时
  - 加载失败时弹出中文提示：「⚠️ 图片返回了但浏览器无法加载（可能是 URL 已过期、CORS 限制或链接失效）」

### ✨ 优化：多角度图 4 次调用 → 1 次调用
- **背景**：v1.6.0 是依次发起 4 次图像 API 请求（前/侧/顶/45°），慢、贵、还容易出现 4 张图风格不一致
- **优化**（v1.6.1 起）：
  - 改为**一次性生成 1 张 1024×1024 的 2x2 四宫格图**
  - 用自然语言 prompt 描述布局（左上=前视图、右上=侧视图、左下=俯视图、右下=45°）
  - 同一张图填充到 4 个视角槽位，前端显示风格强一致
- **收益**：
  - API 调用次数 **-75%**（4 次 → 1 次）
  - Step 4 多模态视觉模型只收 1 张图，**token 消耗 -75%**
  - 出图等待时间显著缩短
- **推荐图像模型**：`gpt-image-2` / `gpt-image-1` / `dall-e-3`（这些模型对自然语言版式指令理解最好）

---

## 🧪 四、本地验证步骤

### 1. 验证版本号一致性

```bash
cd /Users/Apple/Desktop/ai-chat
echo "=== 各文件中的版本号 ===" && \
grep -nE '"version"' package.json && \
grep -nE 'v1\.6\.[0-9]+|hasLaunched_v' public/index.html | head -3 && \
head -20 CHANGELOG.md | grep -E "^## \["
```

期望全部出现 `1.6.1`。

### 2. 安装 dmg 验证

```bash
open /Users/Apple/Desktop/ai-chat/dist/白歌的AI讨论组-1.6.1-arm64.dmg
# 拖入 Applications → 启动 → 应该弹出"v1.6.1 欢迎窗"
# 摄影工具 → 一键3D建模 → Step 3 出图 → 应该是 1 张四宫格
```

### 3. 联调（与 Blender 插件 v1.0.2）

```
Blender → N 面板 → AI Bridge → Start Server (127.0.0.1:9876)
桌面端 → 摄影工具 → 一键3D建模 → 跑完 5 步 → "推送到 Blender"
→ Blender 视口实时建模 🎬
```

---

## 📚 五、相关文档

| 文档 | 作用 |
|------|------|
| `CHANGELOG.md` | 全量版本变更日志（[1.6.1] 已置顶） |
| `VERSIONING.md` | 版本号迭代铁律 + 5 处同步清单 |
| `RELEASE_v1.6.0.md` | 上一版（含一键3D建模首发说明） |
| `RELEASE_v1.6.1.md` | **本文档**，发布交付清单 |
| `blender_addon/README.md` | 插件安装/调试/安全说明 |

---

## 🔄 六、下次迭代提示

- 若仅做小修小补 → `1.6.1 → 1.6.2`（PATCH）
- 若新增功能（如 Step 6 自动渲染输出 PNG） → `1.6.x → 1.7.0`（MINOR）
- 若推倒重写或不兼容变更 → `1.x.x → 2.0.0`（MAJOR）

---

**🎉 v1.6.1 发布完成！**
