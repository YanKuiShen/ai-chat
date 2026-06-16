# 版本迭代规范 (Versioning)

> **铁律：每次推送实质性更新（新功能 / bug 修复 / 文档调整）前，必须先迭代版本号。**
> 任何代码改动落地，都先把版本号往前推一格，再写代码。

---

## 一、语义化版本 (SemVer)

格式：`MAJOR.MINOR.PATCH`，例如 `1.6.0`

| 部分 | 何时 +1 | 示例 |
|---|---|---|
| **MAJOR**（主版本） | 不兼容的重大变更 / 推倒重写 / 移除核心功能 | `1.x.x → 2.0.0` |
| **MINOR**（次版本） | 新增向后兼容的功能模块 | 新增「一键3D建模」: `1.5.5 → 1.6.0` |
| **PATCH**（修订版本） | 向后兼容的 bug 修复 / 小优化 / 文案调整 | 修一个按钮: `1.6.0 → 1.6.1` |

> MINOR 升级时 PATCH 归零；MAJOR 升级时 MINOR 和 PATCH 都归零。

---

## 二、每次更新必改的位置（5 处同步清单）

| # | 文件 | 位置 | 修改内容 |
|---|---|---|---|
| 1 | `package.json` | `"version"` | 主版本号 |
| 2 | `package.json` | `"description"` | 描述里的 `v X.Y.Z` |
| 3 | `public/index.html` | "版本更新记录 (vX.Y.Z)" 段 | 新增本次条目，**旧版本顺移到「历史版本」** |
| 4 | `public/index.html` | `checkFirstLaunch` / `closeWelcomeModal` 里的 `hasLaunched_vX.Y.Z` | 新版本会重新弹欢迎窗给用户看更新 |
| 5 | `CHANGELOG.md` | 顶部新增 `## [X.Y.Z] - YYYY-MM-DD` | 详尽记录本次变更 |
| 6（可选）| `blender_addon/aichat_bridge/__init__.py` | `bl_info["version"]` | **仅当插件本次有变更**时升 |

---

## 三、推荐工作流

```
1. 想改东西                ┐
2. 先决定本次属于哪一级 ►   MAJOR / MINOR / PATCH ?
3. CHANGELOG.md 顶部草拟条目│
4. 同步以上 5/6 处版本号   │
5. 写代码 / 修 bug          │
6. npm run dev 自测         │
7. git commit -m "chore(release): vX.Y.Z - 一句话主旨"
8. （视需要）npm run build:mac / build:win / build:addon
```

---

## 四、一键版本号一致性检查

```bash
cd /Users/Apple/Desktop/ai-chat
echo "=== 各文件中的版本号 ===" && \
grep -nE "\"version\"" package.json && \
grep -nE "v1\.[0-9]+\.[0-9]+" public/index.html | head -3 && \
grep -nE "\"version\":" blender_addon/aichat_bridge/__init__.py && \
head -20 CHANGELOG.md | grep -E "^## \["
```

期望输出：所有数字一致（除 Blender 插件可独立外）。

---

## 五、版本号区间约定

- `1.x.x` — 当前主线（多AI对话 + 工作流 + 摄影工具 + 一键3D建模）
- `2.0.0` 留给：未来若要切到 Tauri / 全面重构 UI 框架 / 引入云端账号体系
