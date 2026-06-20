# 混元 3D 外部服务桥接提示

本安装包不内置混元 3D 本体、模型权重或推理环境，只保留调用接口。用户需要自行部署一个兼容服务，然后让本软件通过 `HUNYUAN_BASE_URL` 指向它。

## 默认地址

默认服务地址：

```text
http://127.0.0.1:8767
```

如果你的混元服务部署在其他端口或其他机器，请在启动本软件前设置环境变量：

```bat
set HUNYUAN_BASE_URL=http://127.0.0.1:8767
```

PowerShell 示例：

```powershell
$env:HUNYUAN_BASE_URL = "http://127.0.0.1:8767"
```

远程机器示例：

```powershell
$env:HUNYUAN_BASE_URL = "http://192.168.1.88:8767"
```

## 必须实现的接口

### 1. 健康检查

```http
GET /health
```

返回示例：

```json
{
  "ok": true,
  "running": true,
  "model_loaded": false,
  "service": "hunyuan3d"
}
```

### 2. 图生 3D

```http
POST /generate/from-image
Content-Type: application/json
```

请求示例：

```json
{
  "image": "base64 或 data:image/png;base64,...",
  "texture": true
}
```

返回示例：

```json
{
  "ok": true,
  "glb_base64": "GLB 文件的 base64",
  "size": 1234567,
  "has_texture": false
}
```

本软件会把 `glb_base64` 落盘到：

```text
%USERPROFILE%\Desktop\ai-chat-workspace\_hunyuan3d_models
```

然后再通过 Blender 桥接导入场景。

### 3. 预热模型

```http
POST /load-models
```

返回示例：

```json
{
  "ok": true,
  "model_loaded": true
}
```

## 本软件侧接口

前端不会直接调用外部混元服务，而是调用本软件内置网关：

```http
GET  /api/hunyuan/status
POST /api/hunyuan/warmup
POST /api/hunyuan/generate
POST /api/hunyuan/start
```

其中 `/api/hunyuan/start` 在销售版中只会尝试检测已有外部服务，不会内置启动混元本体。看到“销售版保留混元3D接口，但不内置启动混元服务”是正常行为。

## 实时渲染工作流中的使用方式

1. 先启动外部混元 3D 服务。
2. 确认 `GET http://127.0.0.1:8767/health` 返回 `ok: true`。
3. 打开本软件的实时渲染页面。
4. 勾选“启用混元”。
5. 点击“检测混元服务”。
6. 检测通过后再启动节点工作流。

## 常见问题

### 检测失败

检查：

- 外部混元服务是否已启动。
- `HUNYUAN_BASE_URL` 是否指向正确地址。
- 防火墙是否允许本机访问该端口。
- 服务是否实现了 `/health`。

### 生成卡住或超时

实时渲染里有单独的“混元响应时间”设置，默认 180 秒，可按服务速度调高。大模型首次加载通常更慢，建议先调用 `/api/hunyuan/warmup` 或在 UI 中预热/检测后再正式运行。

### 返回格式不兼容

必须返回 `ok: true` 和 `glb_base64`。如果你的服务只返回文件 URL，需要在桥接服务里先下载 GLB 并转成 base64。

## 最小兼容服务伪代码

```python
from flask import Flask, request, jsonify

app = Flask(__name__)
model_loaded = False

@app.get("/health")
def health():
    return jsonify(ok=True, model_loaded=model_loaded, service="hunyuan3d")

@app.post("/load-models")
def load_models():
    global model_loaded
    # TODO: 初始化你的混元模型
    model_loaded = True
    return jsonify(ok=True, model_loaded=True)

@app.post("/generate/from-image")
def generate_from_image():
    data = request.get_json() or {}
    image = data.get("image")
    if not image:
        return jsonify(ok=False, error="缺少 image 字段")
    # TODO: 调用你的 image-to-3D 推理，得到 GLB bytes
    glb_base64 = "..."
    return jsonify(ok=True, glb_base64=glb_base64, size=0, has_texture=False)

app.run(host="127.0.0.1", port=8767)
```

