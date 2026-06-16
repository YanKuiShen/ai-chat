# 📋 v3.4.3 接力简报

> 生成时间：2026-05-23
> 上一版：v3.4.2（脚本生成大师 → MCP 工具库 3 件套）
> 本版：v3.4.3（用户反馈：照片墙补显示原始文件名）

---

## 📋 给下一个 AI 的话（直接复制粘贴）

> 接力 v3.4.3 → v3.4.4。请打开 `ai-chat/RELEASE_v3.4.3_HANDOFF.md` 看完整接力简报。
>
> v3.4.3 已完成的核心工作（用户反馈一行字：「在照片墙里面应该可以显示出照片的名字（在我使用新版本之后自动显示出来，不需要再次上传）」）：
> 1. ✅ `handlePhotoWallUpload`（约 7800 行）：上传 / 拖拽时同步捕获 `file.name` 去扩展名 + 截 60 字符 → 当作第 6 个参数 `rawName` 传给 `addPhotoCard`
> 2. ✅ `addPhotoCard(id, base64, note, x, y, filename = '')`：新增 `filename` 第 6 参，把它写到 `card.dataset.filename`，并在照片底部叠一层 `.photo-filename` div（黑色渐变 chip + 📷 emoji + 单行 ellipsis + hover title 看完整名）
> 3. ✅ `savePhotoSession()`（约 8030 行）：保存 photos 数组时新增 `filename: card.dataset.filename` 字段持久化
> 4. ✅ `selectPhotoSession()`（约 7251 行）：恢复时把保存的 `p.filename` 传进 `addPhotoCard`
> 5. ✅ 元数据：`package.json` 3.4.2 → 3.4.3 / 欢迎弹窗 key `hasLaunched_v3.4.2` → `hasLaunched_v3.4.3` / `CHANGELOG.md` 顶部新增 `[3.4.3]` 段
> 6. ✅ node 语法验证通过：`JS length: 663862 / JS lines: 15711 / OK - syntax valid`
>
> **兼容性**：用户老 photo 数据没 filename 字段会 fallback 到空串（不渲染 chip），其它功能不变；老图必须重新上传一次才会显示文件名（因为当时根本没存）。
>
> **下一版方向（用户尚未提需求时可选做）**：
>
> A. 测试验收 v3.4.2 脚本生成大师 3 个 MCP 工具（match_scene_template / build_from_scene_template）：MCP 模式跑「赛博朋克霓虹巷子」/「日式神社」等，看 AI 是否主动调 match→build 一次性建好基础场景。详见 `RELEASE_v3.4.2_HANDOFF.md`。
>
> B. 给「图像分析」分析卡也加文件名 chip（目前只在「照片墙」里加了；分析卡用的是同一份 base64 但走另一条 addAnalyzeTask 路径，没传 filename）。
>
> C. 让用户能手动改 filename（hover 出现 ✏️ 按钮 / 双击 chip 进入编辑态），存 `card.dataset.filename`。
>
> D. 把 filename 喂给视觉模型作上下文（图像分析任务时 AI 看到「这张图叫 IMG_海边日落.jpg」就知道是户外/晚上）。

---

## ✅ v3.4.3 完成的具体改动

### 1. `public/index.html`（5 处修改 · ≈30 行净增）

#### a. `handlePhotoWallUpload(event)` — 约 7800 行
- 同步捕获 `file.name` → `replace(/\.[^./]+$/, '')` 去扩展名 → `slice(0, 60)` 截 60 字符防止超长破坏布局
- 作为新参数 `rawName` 传给 `addPhotoCard(photoId, base64, '', null, null, rawName)`

```js
const rawName = (file.name || '').replace(/\.[^./]+$/, '').slice(0, 60) || '';
addPhotoCard(photoId, base64, '', null, null, rawName);
```

#### b. `addPhotoCard(id, base64, note, x, y, filename = '')` — 约 7827 行
- 第 6 个参数 `filename` 默认空串（向后兼容老调用）
- `card.dataset.filename = filename || ''` 把名字塞到 dataset
- HTML 末尾插一层 `.photo-filename` div：
  - `position: absolute; bottom: 0; left: 0; right: 0`
  - `background: linear-gradient(0deg, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.55) 60%, rgba(0,0,0,0) 100%)` 黑色渐变
  - `color: white; font-size: 12px; font-weight: 500; padding: 16px 10px 8px 10px`
  - `📷 ${safeFilename}` 前缀 emoji
  - `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` 单行 ellipsis
  - `title="${safeFilename}"` hover 看完整文件名
  - `pointer-events: none` 不挡住点击
- filename 为空时整个 div **完全不渲染**（条件渲染）

#### c. `savePhotoSession()` — 约 8030 行
```js
photos.push({
  id: card.id,
  base64: card.querySelector('img').src,
  note: card.querySelector('textarea').value,
  x: parseFloat(card.style.left) || 0,
  y: parseFloat(card.style.top) || 0,
  filename: card.dataset.filename || ''  // v3.4.3 新增
});
```

#### d. `selectPhotoSession()` — 约 7251 行
```js
photos.forEach(p => addPhotoCard(p.id, p.base64, p.note, p.x, p.y, p.filename || ''));
```

#### e. 欢迎弹窗 key 升级
```js
// checkFirstLaunch
const hasLaunched = localStorage.getItem('hasLaunched_v3.4.3');
// closeWelcomeModal
localStorage.setItem('hasLaunched_v3.4.3', 'true');
```

### 2. `package.json`
- `version: "3.4.2"` → `"3.4.3"`
- `description` 重写：`v3.4.3 照片墙补显示原始文件名（上传/拖拽时自动捕获 file.name 去后缀截 60 字符 → 存到 photos[].filename → 渲染时画到照片底部黑色渐变 chip 里 + 切换项目时通过 addPhotoCard(.., filename) 重建）...`

### 3. `CHANGELOG.md`
- 顶部新增 `## [3.4.3] - 2026-05-23 · 📷 摄影项目「照片墙」显示原始文件名` 段（含用户反馈引用 + 5 处改动详解 + 兼容性说明）

---

## 🧪 验收测试用例

### 路径 A · 上传新图（应自动显示文件名）
1. 打开 ai-chat → 摄影工具 → 新建项目（或选已有）
2. 点【上传图片】或拖拽文件到照片墙 → 选 `IMG_海边日落.jpg`
3. **期望**：照片卡片底部显示 `📷 IMG_海边日落`（黑色渐变 chip · 单行 ellipsis · hover 看完整名）

### 路径 B · 切换项目重启（应保留文件名）
1. 上传 N 张图后 → 切到另一个项目 → 切回来
2. **期望**：所有上传的图片都还显示 `📷 文件名`（filename 字段持久化到 localStorage）

### 路径 C · 老用户兼容（旧图不显示，新图自动显示）
1. v3.4.2 用户升级到 v3.4.3 后打开摄影项目
2. **期望**：老照片不显示文件名 chip（因为当时根本没存 filename），但新上传的图立刻显示

### 路径 D · 边缘情况
- 文件名超过 60 字符 → 截断到前 60 字符
- 文件名只有扩展名 `.png` → 去后缀后是空串 → fallback 到空，不渲染 chip
- 中英文混合文件名 `IMG_海边日落.jpg` → 正常显示
- 含特殊字符如 `<script>` → `escapeHtml(filename)` 保护

---

## 🚧 未做但可考虑的扩展

### 1. 图像分析任务卡也加文件名 chip
当前用户从「照片墙 → 分析按钮」跳转到「图像分析」时，分析卡用 base64 但**没传 filename**。
- 改：`analyzePhotoFromWall(id)` 把 `card.dataset.filename` 一起传给 `addAnalyzeTask`
- 改：`addAnalyzeTask(base64, skipSave, filename)` 接受 filename，在分析卡 `.analyze-task-img-preview` 上叠一层 chip

### 2. 用户手动编辑文件名
- hover 卡片底部 chip 时显示 ✏️ 按钮 → 双击进编辑态
- 输入新名 → blur / Enter 保存到 `card.dataset.filename` + 调 `savePhotoSession()`

### 3. 让 AI 读取文件名作上下文
- 「图像分析」prompt 末尾追加：「该图片原始文件名为：${filename}（含拍摄场景、地点、日期等隐藏信息）」
- 让视觉模型在分析时知道「IMG_20260520_海边日落_F1.4_85mm.jpg」隐含的相机参数 + 场景信息

### 4. 文件名搜索 / 过滤
- 照片墙顶部加搜索框 → 只显示文件名匹配的卡片
- 切到 grid 视图（缩略图列表）→ 按文件名 / 上传时间排序

---

## 📂 关键文件 / 行号速查

| 修改点 | 文件 | 大概行号 |
|--------|------|----------|
| `handlePhotoWallUpload` 改 | `public/index.html` | 约 7789~7826 |
| `addPhotoCard` 改 | `public/index.html` | 约 7827~7910 |
| `savePhotoSession` 改 | `public/index.html` | 约 8023~8070 |
| `selectPhotoSession` 恢复 | `public/index.html` | 约 7251 |
| 欢迎弹窗 key | `public/index.html` | 约 2886 / 2893 |
| version | `package.json` | 第 3 行 |
| CHANGELOG | `CHANGELOG.md` | 顶部 [3.4.3] 段 |

---

## 📋 todo 清单（v3.4.4 起）

- [ ] 测试验收 v3.4.2 脚本生成大师 3 个 MCP 工具（match→build 自主召唤）
- [ ] 「图像分析」分析卡也加文件名 chip（同一文件名透传）
- [ ] 用户能手动改文件名（双击 chip 编辑态）
- [ ] 文件名喂给视觉模型作上下文（隐含相机/场景信息）
- [ ] 摄影项目加搜索框（按文件名过滤照片）

---

> **提示**：用户的反馈一般都很实用且体感强（这次是「不要让我再上传一次」），优先尊重「重启后自动生效」的零迁移习惯，避免要求用户手动操作。
