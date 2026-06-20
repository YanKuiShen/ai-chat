bl_info = {
    "name": "AIChat Bridge",
    "author": "白歌",
    "version": (2, 1, 0),

    "blender": (3, 0, 0),
    "location": "View3D > N Panel > AIChat",
    "description": "Bridge for 白歌的AI讨论组. v2.1.0 智能体 3D 建模工作流: 新增 GET /blend_summary（场景文件大小/物体总数/集合树/渲染设置 overview，给 Critic 审图前用） + POST /bookmark_state（场景 JSON 快照到 Blender 内存，给修复失败回滚用） + POST /restore_state（从快照恢复）。v2.0.4 hotfix: exec_python 空 code 时返回 hint 教 AI 改用原子工具或正确传 code 参数。v2.0.3: exec_python / exec 任务的 namespace 预置 math/mathutils/bmesh + Vector/Matrix/Euler/Quaternion/Color。v2.0 MCP tool layer (16 atomic tools) for Agent-loop architecture.",

    "category": "Development",
}



import bpy
import json
import os
import io
import time
import queue
import shutil
import base64
import zipfile
import tempfile
import threading
import traceback
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import requests
except ImportError:
    requests = None  # 老版 Blender 可能没 requests，会在调用时报错

# ---------- 全局状态 ----------
EXEC_QUEUE = queue.Queue()       # 主线程任务队列：{type, payload, event, result_ref}
LOG_RING = []                    # 最近 N 条执行日志
LOG_MAX = 30
_server = None
_server_thread = None
_timer_registered = False

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876

ADDON_VERSION = "2.1.0"



# Hyper3D Rodin 内置免费 trial key（来自 blender-mcp 项目，全球用户共享每日额度）
RODIN_FREE_TRIAL_KEY = "k9TcfFoEhNd9cCPP2guHAHHHkctZHIRhZDywZ1euGUXwihbYLpOjQhofby80NJez"

# 这些 key 由前端 /config 接口动态写入，启动时为空
RUNTIME_CONFIG = {
    "hyper3d_api_key": "",       # 用户设的 Hyper3D / fal.ai key（空时用 trial）
    "hyper3d_mode": "MAIN_SITE", # MAIN_SITE | FAL_AI
    "sketchfab_api_key": "",     # 用户的 Sketchfab API token
}


def push_log(level, msg):
    LOG_RING.append({
        "t": time.strftime("%H:%M:%S"),
        "level": level,
        "msg": str(msg)[:600],
    })
    while len(LOG_RING) > LOG_MAX:
        LOG_RING.pop(0)
    print(f"[AIChat] {level}: {msg}")


def _sanitize_exec_code(code):
    """Patch common AI-generated Blender code hazards before execution."""
    if not code or not isinstance(code, str):
        return code or ""
    original = code
    code = re.sub(
        r'^[ \t]*bpy\.ops\.wm\.save_as_mainfile\s*\([^\r\n]*\)[ \t]*$',
        '# [AIChat Bridge] removed save_as_mainfile: bridge exec does not save .blend directly',
        code,
        flags=re.MULTILINE,
    )
    code = re.sub(
        r'view_settings\.view_transform\s*=\s*["\']Filmic["\']',
        'view_settings.view_transform = "AgX"',
        code,
    )
    code = re.sub(
        r'view_settings\.look\s*=\s*["\']Medium High Contrast["\']',
        'view_settings.look = "AgX - Medium High Contrast"',
        code,
    )
    code = re.sub(
        r'view_settings\.look\s*=\s*["\']High Contrast["\']',
        'view_settings.look = "AgX - High Contrast"',
        code,
    )
    code = re.sub(
        r'view_settings\.look\s*=\s*["\']Base Contrast["\']',
        'view_settings.look = "AgX - Base Contrast"',
        code,
    )
    code = re.sub(
        r'if\s+__name__\s*==\s*["\']__main__["\']\s*:\s*\n([ \t]+)main\s*\(\s*\)',
        '# [AIChat Bridge] bridge exec calls main() directly\nmain()',
        code,
    )
    code = re.sub(
        r'([A-Za-z_][\w.]*)\.get\(\s*["\']Principled BSDF["\']\s*\)',
        r'_aichat_find_principled(\1)',
        code,
    )
    if '_aichat_find_principled(' in code and not re.search(r'def\s+_aichat_find_principled\s*\(', code):
        code = '''# [AIChat Bridge] Blender 5.x safe Principled BSDF lookup
def _aichat_find_principled(nodes):
    try:
        getter = getattr(nodes, "get", None)
        if getter:
            node = getter("Principled BSDF")
            if node:
                return node
    except Exception:
        pass
    try:
        for node in nodes:
            if getattr(node, "type", "") == "BSDF_PRINCIPLED":
                return node
    except Exception:
        pass
    try:
        return nodes.new(type="ShaderNodeBsdfPrincipled")
    except Exception:
        pass
    return None

''' + code
    if code != original:
        push_log("WARN", "sanitized exec code: removed save_as_mainfile, fixed Blender 5.x AgX look enum, patched __main__ guard, and/or patched Principled BSDF lookup")
    return code


# ============================================================
# Scene Report (v1.1.0+, AI 自检用)
# ============================================================
def _safe_vec3(v):
    try:
        return [round(float(x), 4) for x in v]
    except Exception:
        return None


def _safe_color4(v):
    try:
        out = [round(float(x), 4) for x in v]
        return out if len(out) >= 3 else None
    except Exception:
        return None


def _get_material_info(obj):
    info = {"material": None, "base_color": None, "emission_strength": 0.0, "has_emission": False}
    try:
        if not getattr(obj, "data", None): return info
        if not hasattr(obj.data, "materials") or len(obj.data.materials) == 0: return info
        mat = obj.data.materials[0]
        if mat is None: return info
        info["material"] = mat.name
        if not getattr(mat, "use_nodes", False) or mat.node_tree is None: return info
        bsdf = None
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node; break
        if bsdf is None: return info
        if "Base Color" in bsdf.inputs:
            info["base_color"] = _safe_color4(bsdf.inputs["Base Color"].default_value)
        es = 0.0
        if "Emission Strength" in bsdf.inputs:
            try: es = float(bsdf.inputs["Emission Strength"].default_value)
            except Exception: es = 0.0
        info["emission_strength"] = round(es, 4)
        info["has_emission"] = es > 0.01
    except Exception:
        pass
    return info


def _collect_scene_report():
    report = {
        "ok": True, "addon_version": ADDON_VERSION,
        "blender": {"version_string": bpy.app.version_string, "version": list(bpy.app.version),
                    "major": bpy.app.version[0], "minor": bpy.app.version[1]},
        "engine": None, "view_transform": None, "viewport_shading": None,
        "active_camera": None, "frame_current": None, "objects": [],
        "stats": {"mesh_count": 0, "light_count": 0, "emissive_mesh_count": 0,
                  "has_camera": False, "has_world_bg": False, "total_polygons": 0},
        "recent_errors": [],
    }
    try:
        scene = bpy.context.scene
        report["engine"] = getattr(scene.render, "engine", None)
        report["frame_current"] = scene.frame_current
        try: report["view_transform"] = scene.view_settings.view_transform
        except Exception: pass
        try:
            for area in bpy.context.screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            report["viewport_shading"] = space.shading.type; break
                    break
        except Exception: pass
        cam = scene.camera
        if cam is not None:
            report["active_camera"] = cam.name
            report["stats"]["has_camera"] = True
        if scene.world is not None: report["stats"]["has_world_bg"] = True
        total_poly = 0
        for obj in bpy.data.objects:
            entry = {"name": obj.name, "type": obj.type,
                     "location": _safe_vec3(obj.location),
                     "rotation_euler": _safe_vec3(obj.rotation_euler),
                     "scale": _safe_vec3(obj.scale), "dimensions": _safe_vec3(obj.dimensions)}
            if obj.type == "MESH":
                report["stats"]["mesh_count"] += 1
                mat_info = _get_material_info(obj)
                entry.update(mat_info)
                if mat_info["has_emission"]: report["stats"]["emissive_mesh_count"] += 1
                try:
                    poly_count = len(obj.data.polygons) if obj.data else 0
                    entry["polygons"] = poly_count
                    total_poly += poly_count
                except Exception: pass
            elif obj.type == "LIGHT":
                report["stats"]["light_count"] += 1
                try:
                    ld = obj.data
                    entry["light_type"] = ld.type
                    entry["energy"] = round(float(ld.energy), 4)
                    entry["color"] = _safe_color4(ld.color)
                except Exception: pass
            report["objects"].append(entry)
        report["stats"]["total_polygons"] = total_poly
        for e in LOG_RING[-LOG_MAX:]:
            if e.get("level") == "ERROR":
                report["recent_errors"].append(e)
    except Exception as e:
        report["ok"] = False
        report["error"] = "collect failed: %s" % e
        report["traceback"] = traceback.format_exc(limit=6)
    return report


# ============================================================
# v1.2.0：主线程任务派发 & 等待结果（视口截图 / GLB 导入需要主线程）
# ============================================================
def _post_to_main(task_type, payload, timeout=120):
    """投递一个任务到主线程队列，并阻塞等待结果返回。timeout=120s"""
    ev = threading.Event()
    result_ref = {"data": None, "error": None}
    EXEC_QUEUE.put({"type": task_type, "payload": payload, "event": ev, "result_ref": result_ref})
    if not ev.wait(timeout=timeout):
        return {"ok": False, "error": "main thread timeout (>%ds)" % timeout}
    if result_ref["error"]:
        return {"ok": False, "error": result_ref["error"]}
    return {"ok": True, "data": result_ref["data"]}


# ============================================================
# v1.2.0：Hyper3D Rodin 文生 3D 模型
# ============================================================
REQ_HEADERS = {"User-Agent": "aichat-bridge/2.1.0"}




def _hyper3d_get_key():
    """优先用用户设的 key；没设就用全球共享 trial key"""
    k = (RUNTIME_CONFIG.get("hyper3d_api_key") or "").strip()
    return k if k else RODIN_FREE_TRIAL_KEY


def _hyper3d_create_job(text_prompt=None, images=None, bbox_condition=None):
    """创建 Rodin 任务，返回 job 信息（含 subscription_key 或 request_id）"""
    if requests is None:
        return {"error": "requests 模块未安装。请在 Blender Python 控制台执行: import pip; pip.main(['install', 'requests'])"}
    mode = RUNTIME_CONFIG.get("hyper3d_mode", "MAIN_SITE")
    api_key = _hyper3d_get_key()
    is_trial = api_key == RODIN_FREE_TRIAL_KEY
    try:
        if mode == "MAIN_SITE":
            files = []
            if images:
                # images: [(suffix, base64), ...]
                for i, (suffix, b64) in enumerate(images):
                    raw = base64.b64decode(b64) if isinstance(b64, str) else b64
                    files.append(("images", (f"{i:04d}{suffix}", raw)))
            files.append(("tier", (None, "Sketch")))
            files.append(("mesh_mode", (None, "Raw")))
            if text_prompt:
                files.append(("prompt", (None, text_prompt)))
            if bbox_condition:
                files.append(("bbox_condition", (None, json.dumps(bbox_condition))))
            r = requests.post(
                "https://hyperhuman.deemos.com/api/v2/rodin",
                headers={"Authorization": f"Bearer {api_key}", **REQ_HEADERS},
                files=files, timeout=60,
            )
            data = r.json()
            data["_mode"] = mode
            data["_is_trial"] = is_trial
            return data
        elif mode == "FAL_AI":
            req = {"tier": "Sketch"}
            if images: req["input_image_urls"] = images
            if text_prompt: req["prompt"] = text_prompt
            if bbox_condition: req["bbox_condition"] = bbox_condition
            r = requests.post(
                "https://queue.fal.run/fal-ai/hyper3d/rodin",
                headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json", **REQ_HEADERS},
                json=req, timeout=60,
            )
            data = r.json()
            data["_mode"] = mode
            data["_is_trial"] = is_trial
            return data
        else:
            return {"error": "Unknown mode: %s" % mode}
    except Exception as e:
        return {"error": "create_job failed: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _hyper3d_poll_job(subscription_key=None, request_id=None):
    if requests is None:
        return {"error": "requests not installed"}
    mode = RUNTIME_CONFIG.get("hyper3d_mode", "MAIN_SITE")
    api_key = _hyper3d_get_key()
    try:
        if mode == "MAIN_SITE":
            if not subscription_key: return {"error": "subscription_key 为空"}
            r = requests.post(
                "https://hyperhuman.deemos.com/api/v2/status",
                headers={"Authorization": f"Bearer {api_key}", **REQ_HEADERS},
                json={"subscription_key": subscription_key}, timeout=30,
            )
            data = r.json()
            return {"status_list": [j["status"] for j in data.get("jobs", [])], "raw": data}
        elif mode == "FAL_AI":
            if not request_id: return {"error": "request_id 为空"}
            r = requests.get(
                f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}/status",
                headers={"Authorization": f"KEY {api_key}", **REQ_HEADERS}, timeout=30,
            )
            return r.json()
    except Exception as e:
        return {"error": "poll failed: %s" % e}


def _hyper3d_download_glb(task_uuid=None, request_id=None):
    """下载生成完成的 GLB 文件，返回本地路径"""
    if requests is None:
        return None, "requests not installed"
    mode = RUNTIME_CONFIG.get("hyper3d_mode", "MAIN_SITE")
    api_key = _hyper3d_get_key()
    try:
        if mode == "MAIN_SITE":
            if not task_uuid: return None, "task_uuid 为空"
            r = requests.post(
                "https://hyperhuman.deemos.com/api/v2/download",
                headers={"Authorization": f"Bearer {api_key}", **REQ_HEADERS},
                json={"task_uuid": task_uuid}, timeout=30,
            )
            data = r.json()
            glb_url = None
            for item in data.get("list", []):
                if item.get("name", "").endswith(".glb"):
                    glb_url = item["url"]; break
            if not glb_url: return None, "no .glb in download list"
        else:  # FAL_AI
            if not request_id: return None, "request_id 为空"
            r = requests.get(
                f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}",
                headers={"Authorization": f"Key {api_key}", **REQ_HEADERS}, timeout=30,
            )
            data = r.json()
            glb_url = data.get("model_mesh", {}).get("url")
            if not glb_url: return None, "no model_mesh.url in response"
        # 下载 GLB
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
        gr = requests.get(glb_url, stream=True, timeout=180)
        gr.raise_for_status()
        for chunk in gr.iter_content(chunk_size=8192):
            tf.write(chunk)
        tf.close()
        return tf.name, None
    except Exception as e:
        return None, "download failed: %s" % e


def _import_glb_main_thread(filepath, mesh_name, location=None, scale=None):
    """主线程：导入 GLB 文件，rename，setlocation/scale"""
    try:
        existing = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=filepath)
        bpy.context.view_layer.update()
        new_objs = [o for o in bpy.data.objects if o not in existing]
        if not new_objs:
            return {"ok": False, "error": "no objects imported from GLB"}
        # 找根 mesh / 父 empty
        meshes = [o for o in new_objs if o.type == "MESH"]
        if len(new_objs) == 1 and new_objs[0].type == "MESH":
            root = new_objs[0]
        elif len(new_objs) == 2:
            empties = [o for o in new_objs if o.type == "EMPTY"]
            if len(empties) == 1 and len(empties[0].children) == 1 and empties[0].children[0].type == "MESH":
                child = empties[0].children[0]
                child.parent = None
                bpy.data.objects.remove(empties[0])
                root = child
            else:
                root = meshes[0] if meshes else new_objs[0]
        else:
            root = meshes[0] if meshes else new_objs[0]
        try:
            if mesh_name:
                root.name = mesh_name
                if root.data and hasattr(root.data, "name"):
                    root.data.name = mesh_name
        except Exception: pass
        if location:
            try: root.location = location
            except Exception: pass
        if scale:
            try:
                if isinstance(scale, (int, float)):
                    root.scale = (float(scale), float(scale), float(scale))
                else:
                    root.scale = tuple(scale)
            except Exception: pass
        info = {
            "name": root.name, "type": root.type,
            "location": list(root.location), "scale": list(root.scale),
        }
        return {"ok": True, "imported": info}
    except Exception as e:
        return {"ok": False, "error": "import_glb: %s" % e, "traceback": traceback.format_exc(limit=4)}


# ============================================================
# v1.2.0：Sketchfab 搜索 + 下载
# ============================================================
def _sketchfab_search(query, count=12, downloadable=True, categories=None):
    if requests is None: return {"error": "requests not installed"}
    api_key = (RUNTIME_CONFIG.get("sketchfab_api_key") or "").strip()
    if not api_key:
        return {"error": "Sketchfab API key 未配置（前端设置里填一下）"}
    params = {"type": "models", "q": query, "count": count, "downloadable": downloadable, "archives_flavours": False}
    if categories: params["categories"] = categories
    try:
        r = requests.get("https://api.sketchfab.com/v3/search",
                         headers={"Authorization": f"Token {api_key}", **REQ_HEADERS},
                         params=params, timeout=30)
        if r.status_code == 401: return {"error": "Sketchfab 401: API key 无效"}
        if r.status_code != 200: return {"error": "HTTP %d: %s" % (r.status_code, r.text[:200])}
        data = r.json() or {}
        # 简化输出：只保留 uid / name / thumbnail / description / categories / user
        results = []
        for it in (data.get("results") or [])[:count]:
            thumb = ""
            try:
                imgs = (it.get("thumbnails") or {}).get("images") or []
                # 选 400~800px 之间
                for img in imgs:
                    if 400 <= (img.get("width") or 0) <= 800:
                        thumb = img.get("url") or ""; break
                if not thumb and imgs: thumb = imgs[0].get("url", "")
            except Exception: pass
            results.append({
                "uid": it.get("uid"), "name": it.get("name"),
                "description": (it.get("description") or "")[:200],
                "thumbnail": thumb,
                "user": (it.get("user") or {}).get("username"),
                "license": (it.get("license") or {}).get("slug"),
                "viewerUrl": it.get("viewerUrl"),
            })
        return {"ok": True, "count": len(results), "results": results}
    except Exception as e:
        return {"error": "sketchfab_search: %s" % e}


def _sketchfab_download_to_temp(uid):
    """下载 Sketchfab 模型 zip 并解压，返回主 .glb / .gltf 路径"""
    if requests is None: return None, "requests not installed"
    api_key = (RUNTIME_CONFIG.get("sketchfab_api_key") or "").strip()
    if not api_key: return None, "Sketchfab API key 未配置"
    try:
        r = requests.get(f"https://api.sketchfab.com/v3/models/{uid}/download",
                         headers={"Authorization": f"Token {api_key}", **REQ_HEADERS},
                         timeout=30)
        if r.status_code == 401: return None, "401 API key 无效"
        if r.status_code != 200: return None, "HTTP %d" % r.status_code
        data = r.json() or {}
        gltf_url = (data.get("gltf") or {}).get("url")
        if not gltf_url: return None, "no gltf.url（模型可能不可下载或要 Pro 会员）"
        mr = requests.get(gltf_url, timeout=120)
        if mr.status_code != 200: return None, "model download HTTP %d" % mr.status_code
        temp_dir = tempfile.mkdtemp(prefix="aichat_sketchfab_")
        zip_path = os.path.join(temp_dir, f"{uid}.zip")
        with open(zip_path, "wb") as f: f.write(mr.content)
        # 安全解压（防 zip slip）
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                target = os.path.abspath(os.path.join(temp_dir, info.filename))
                if not target.startswith(os.path.abspath(temp_dir)):
                    return None, "zip slip detected"
                if ".." in info.filename: return None, "path traversal detected"
            zf.extractall(temp_dir)
        # 找主文件
        main = None
        for f in os.listdir(temp_dir):
            if f.endswith(".gltf") or f.endswith(".glb"):
                main = os.path.join(temp_dir, f); break
        if not main: return None, "no .gltf/.glb in zip"
        return main, None
    except Exception as e:
        return None, "sketchfab download: %s" % e


# ============================================================
# v1.2.0：视口截图（必须主线程）
# ============================================================
def _capture_viewport_screenshot_main(max_size=800):
    """主线程：调用 bpy.ops.screen.screenshot_area，返回 base64 PNG"""
    try:
        area = None
        for a in bpy.context.screen.areas:
            if a.type == "VIEW_3D": area = a; break
        if not area: return {"ok": False, "error": "no VIEW_3D area"}
        # 临时文件
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tf.close()
        filepath = tf.name
        try:
            with bpy.context.temp_override(area=area):
                bpy.ops.screen.screenshot_area(filepath=filepath)
        except Exception as e:
            return {"ok": False, "error": "screenshot_area failed: %s" % e}
        # 加载并缩放（避免 base64 过大）
        try:
            img = bpy.data.images.load(filepath)
            w, h = img.size[0], img.size[1]
            if max(w, h) > max_size and max_size > 0:
                scale = max_size / max(w, h)
                new_w, new_h = int(w * scale), int(h * scale)
                img.scale(new_w, new_h)
                img.file_format = "PNG"
                img.save()
                w, h = new_w, new_h
            bpy.data.images.remove(img)
        except Exception as e:
            push_log("WARN", "screenshot resize failed: %s" % e)
            w, h = 0, 0
        # 读 + base64
        with open(filepath, "rb") as f: raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        try: os.unlink(filepath)
        except Exception: pass
        return {"ok": True, "base64": b64, "format": "png", "width": w, "height": h, "bytes": len(raw)}
    except Exception as e:
        return {"ok": False, "error": str(e), "traceback": traceback.format_exc(limit=4)}


# ============================================================
# v3.6.0：多角度截图 —— AI 自主视觉闭环
# ============================================================
def _multi_angle_screenshot_main(payload):
    """主线程：从多个预设角度对场景进行 OpenGL 截图，返回各角度 base64 PNG + 文字摘要。
    不改变用户当前视口，使用临时 Camera 拍完即删。"""
    import math
    try:
        max_size = int(payload.get("max_size") or 512)
        angles_param = payload.get("angles")  # 可选：用户自定义角度列表

        # —— 1. 计算场景 bounding box，确定最佳拍摄距离 ——
        scene = bpy.context.scene
        all_objs = [o for o in scene.objects if o.type == 'MESH' and o.visible_get()]
        if not all_objs:
            # 空场景 fallback：用原点 + 5m 距离
            bbox_center = (0.0, 0.0, 0.0)
            bbox_radius = 5.0
        else:
            xs, ys, zs = [], [], []
            for obj in all_objs:
                try:
                    for corner in obj.bound_box:
                        world_pt = obj.matrix_world @ __import__('mathutils').Vector(corner)
                        xs.append(world_pt.x); ys.append(world_pt.y); zs.append(world_pt.z)
                except Exception:
                    loc = obj.location
                    xs.append(loc.x); ys.append(loc.y); zs.append(loc.z)
            cx = (min(xs) + max(xs)) / 2.0
            cy = (min(ys) + max(ys)) / 2.0
            cz = (min(zs) + max(zs)) / 2.0
            bbox_center = (cx, cy, cz)
            dx = max(xs) - min(xs)
            dy = max(ys) - min(ys)
            dz = max(zs) - min(zs)
            bbox_radius = max(math.sqrt(dx*dx + dy*dy + dz*dz) / 2.0, 1.0)

        dist = bbox_radius * 2.8  # 确保整个场景在画面内

        # —— 2. 定义预设角度 ——
        # 每个角度：(名称, 球坐标 theta 方位角, phi 俯仰角)
        # theta: 0=+Y 方向（正前方），逆时针；phi: 0=水平，正值=向上看
        default_angles = [
            ("front_45deg",   math.radians(30),   math.radians(30)),   # 正前 45° 俯视（最常用）
            ("front_level",   math.radians(0),     math.radians(5)),    # 正面平视
            ("left_side",     math.radians(90),    math.radians(15)),   # 左侧
            ("top_down",      math.radians(0),     math.radians(85)),   # 俯视 Top-down
        ]

        # 如果场景有活动 Camera，追加一个相机视角
        if scene.camera:
            default_angles.append(("active_camera", None, None))

        if angles_param and isinstance(angles_param, list):
            # 用户自定义角度覆盖
            custom_angles = []
            for a in angles_param:
                name = a.get("name", "custom")
                theta = math.radians(float(a.get("theta", 30)))
                phi = math.radians(float(a.get("phi", 30)))
                custom_angles.append((name, theta, phi))
            if custom_angles:
                default_angles = custom_angles

        # —— 3. 创建临时相机 ——
        cam_data = bpy.data.cameras.new("_MultiAngle_TempCam")
        cam_obj = bpy.data.objects.new("_MultiAngle_TempCam", cam_data)
        scene.collection.objects.link(cam_obj)
        old_camera = scene.camera
        scene.camera = cam_obj

        # 设置渲染分辨率
        old_res_x = scene.render.resolution_x
        old_res_y = scene.render.resolution_y
        old_pct = scene.render.resolution_percentage
        old_fmt = scene.render.image_settings.file_format
        old_path = scene.render.filepath

        scene.render.resolution_x = max_size
        scene.render.resolution_y = max_size
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = 'PNG'

        results = []
        errors = []

        for angle_name, theta, phi in default_angles:
            try:
                if angle_name == "active_camera" and old_camera:
                    # 使用场景原有相机位置
                    cam_obj.location = old_camera.location.copy()
                    cam_obj.rotation_euler = old_camera.rotation_euler.copy()
                    if old_camera.data:
                        cam_data.lens = old_camera.data.lens
                        cam_data.clip_start = old_camera.data.clip_start
                        cam_data.clip_end = old_camera.data.clip_end
                else:
                    # 球坐标 → 笛卡尔坐标
                    cx, cy, cz = bbox_center
                    cam_x = cx + dist * math.sin(theta) * math.cos(phi)
                    cam_y = cy - dist * math.cos(theta) * math.cos(phi)
                    cam_z = cz + dist * math.sin(phi)
                    cam_obj.location = (cam_x, cam_y, cam_z)

                    # 让相机朝向场景中心
                    direction = __import__('mathutils').Vector(bbox_center) - __import__('mathutils').Vector((cam_x, cam_y, cam_z))
                    rot_quat = direction.to_track_quat('-Z', 'Y')
                    cam_obj.rotation_euler = rot_quat.to_euler()

                    # 自动 FOV
                    cam_data.lens = 35
                    cam_data.clip_start = 0.1
                    cam_data.clip_end = max(dist * 4, 1000)

                # 临时文件
                tf = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                tf.close()
                filepath = tf.name
                scene.render.filepath = filepath

                # OpenGL 渲染（比 Cycles 快 100 倍）
                try:
                    bpy.ops.render.opengl(write_still=True)
                except Exception:
                    # Blender 5.x 可能 API 变更，fallback 到 screenshot
                    try:
                        bpy.ops.render.render(write_still=True)
                    except Exception as e2:
                        errors.append({"angle": angle_name, "error": str(e2)})
                        try: os.unlink(filepath)
                        except Exception: pass
                        continue

                # 读取并缩放
                try:
                    img = bpy.data.images.load(filepath)
                    w, h = img.size[0], img.size[1]
                    if max(w, h) > max_size and max_size > 0:
                        scale = max_size / max(w, h)
                        new_w, new_h = int(w * scale), int(h * scale)
                        img.scale(new_w, new_h)
                        img.file_format = "PNG"
                        img.save()
                        w, h = new_w, new_h
                    bpy.data.images.remove(img)
                except Exception as e:
                    push_log("WARN", "multi_angle resize failed for %s: %s" % (angle_name, e))
                    w, h = max_size, max_size

                # 读 base64
                with open(filepath, "rb") as f:
                    raw = f.read()
                b64 = base64.b64encode(raw).decode("ascii")
                try: os.unlink(filepath)
                except Exception: pass

                results.append({
                    "angle": angle_name,
                    "base64": b64,
                    "format": "png",
                    "width": w,
                    "height": h,
                    "bytes": len(raw),
                })
            except Exception as e:
                errors.append({"angle": angle_name, "error": str(e)})

        # —— 4. 清理：恢复原始设置，删除临时相机 ——
        scene.camera = old_camera
        scene.render.resolution_x = old_res_x
        scene.render.resolution_y = old_res_y
        scene.render.resolution_percentage = old_pct
        scene.render.image_settings.file_format = old_fmt
        scene.render.filepath = old_path

        bpy.data.objects.remove(cam_obj, do_unlink=True)
        bpy.data.cameras.remove(cam_data)

        # —— 5. 生成文字摘要（给 LLM 用的精简信息）——
        summary = "多角度截图完成：%d 张成功" % len(results)
        if errors:
            summary += "，%d 张失败" % len(errors)
        angle_list = [r["angle"] for r in results]
        summary += "。角度：%s。" % ", ".join(angle_list)
        summary += "场景中心=(%.1f, %.1f, %.1f)，包围球半径=%.1f，拍摄距离=%.1f" % (
            bbox_center[0], bbox_center[1], bbox_center[2], bbox_radius, dist)

        return {
            "ok": True,
            "data": {
                "screenshots": results,
                "summary": summary,
                "bbox_center": list(bbox_center),
                "bbox_radius": round(bbox_radius, 2),
                "distance": round(dist, 2),
                "errors": errors if errors else None,
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "traceback": traceback.format_exc(limit=4)}


# ============================================================
# v2.0.0：MCP Tool 层 —— 16 个原子化操作端点
# ----------------------------------------------------------------
# 设计原则：
#   1. 涉及 bpy.data / bpy.ops 的改动必须走 _post_to_main（主线程）
#   2. 只读 / 纯网络的工具（搜索 PolyHaven）可在 HTTP handler 线程直接跑
#   3. 混合型（下载文件→主线程加载）拆成两段
#   4. 统一返回结构：{"ok": True, ...} 或 {"ok": False, "error": "..."}
#   5. 所有工具的入参由 MCP_TOOLS schema 严格定义（OpenAI function tools 格式）
# ============================================================

# ---------- 工具：通用主线程取物体 ----------
def _ensure_collection_link(obj):
    """主线程：确保 obj 被链接到当前 collection（add_* 自动会链接，但直接 new 不会）"""
    try:
        coll = bpy.context.collection
        if obj.name not in coll.objects:
            coll.objects.link(obj)
    except Exception:
        try: bpy.context.scene.collection.objects.link(obj)
        except Exception: pass


# ============================================================
# 观察类（read-only）
# ============================================================
def _mcp_get_scene_info_main(payload):
    """完整版 scene info：复用 _collect_scene_report，并精简部分字段以减小 token 占用"""
    full = _collect_scene_report()
    # 把 objects 列表限制在 60 个（防爆 token）
    if isinstance(full.get("objects"), list) and len(full["objects"]) > 60:
        full["objects_truncated"] = True
        full["objects_total"] = len(full["objects"])
        full["objects"] = full["objects"][:60]
    return {"ok": True, "data": full}


def _mcp_get_object_info_main(payload):
    """单个物体详细信息（含 bbox / materials slot / mesh stats）"""
    name = (payload.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if obj is None:
        return {"ok": False, "error": "object not found: %s" % name}
    info = {
        "name": obj.name, "type": obj.type,
        "location": _safe_vec3(obj.location),
        "rotation_euler": _safe_vec3(obj.rotation_euler),
        "scale": _safe_vec3(obj.scale),
        "dimensions": _safe_vec3(obj.dimensions),
        "visible": bool(obj.visible_get()) if hasattr(obj, "visible_get") else True,
        "materials": [],
    }
    try:
        for slot in obj.material_slots:
            if slot.material:
                info["materials"].append({"name": slot.material.name})
    except Exception:
        pass
    if obj.type == "MESH":
        try:
            mesh = obj.data
            if mesh:
                info["mesh"] = {
                    "vertices": len(mesh.vertices),
                    "edges": len(mesh.edges),
                    "polygons": len(mesh.polygons),
                }
        except Exception:
            pass
        info.update(_get_material_info(obj))
        # bbox（world）
        try:
            import mathutils as _mu
            corners = [obj.matrix_world @ _mu.Vector(c) for c in obj.bound_box]
            xs = [c.x for c in corners]; ys = [c.y for c in corners]; zs = [c.z for c in corners]
            info["world_bbox"] = {
                "min": [round(min(xs),4), round(min(ys),4), round(min(zs),4)],
                "max": [round(max(xs),4), round(max(ys),4), round(max(zs),4)],
            }
        except Exception:
            pass
    elif obj.type == "LIGHT":
        try:
            ld = obj.data
            info["light"] = {
                "type": ld.type,
                "energy": round(float(ld.energy), 4),
                "color": _safe_color4(ld.color),
            }
        except Exception:
            pass
    elif obj.type == "CAMERA":
        try:
            cd = obj.data
            info["camera"] = {
                "lens": round(float(cd.lens), 4),
                "sensor_width": round(float(cd.sensor_width), 4),
                "type": cd.type,
            }
        except Exception:
            pass
    return {"ok": True, "data": info}


def _mcp_list_objects_main(payload):
    """轻量列表（仅 name/type/location），可加 type 过滤"""
    filter_type = (payload.get("type") or "").upper().strip() or None
    out = []
    for obj in bpy.data.objects:
        if filter_type and obj.type != filter_type:
            continue
        out.append({
            "name": obj.name, "type": obj.type,
            "location": _safe_vec3(obj.location),
        })
    return {"ok": True, "data": {"count": len(out), "objects": out}}


# ============================================================
# 创建类
# ============================================================
_PRIMITIVE_OPS = {
    "cube": ("primitive_cube_add", {"size": 2.0}),
    "sphere": ("primitive_uv_sphere_add", {"radius": 1.0}),
    "ico_sphere": ("primitive_ico_sphere_add", {"radius": 1.0}),
    "cylinder": ("primitive_cylinder_add", {"radius": 1.0, "depth": 2.0}),
    "cone": ("primitive_cone_add", {"radius1": 1.0, "depth": 2.0}),
    "plane": ("primitive_plane_add", {"size": 2.0}),
    "torus": ("primitive_torus_add", {"major_radius": 1.0, "minor_radius": 0.25}),
    "monkey": ("primitive_monkey_add", {"size": 2.0}),
}


def _mcp_add_primitive_main(payload):
    ptype = (payload.get("type") or "cube").lower().strip()
    if ptype not in _PRIMITIVE_OPS:
        return {"ok": False, "error": "unsupported primitive: %s（支持：%s）" % (ptype, ",".join(_PRIMITIVE_OPS.keys()))}
    op_name, defaults = _PRIMITIVE_OPS[ptype]
    location = tuple(payload.get("location") or (0, 0, 0))
    rotation = tuple(payload.get("rotation") or (0, 0, 0))
    name = payload.get("name")
    try:
        before = set(bpy.data.objects)
        kwargs = dict(defaults)
        kwargs["location"] = location
        kwargs["rotation"] = rotation
        getattr(bpy.ops.mesh, op_name)(**kwargs)
        new_objs = [o for o in bpy.data.objects if o not in before]
        if not new_objs:
            return {"ok": False, "error": "primitive op didn't create any object"}
        root = new_objs[0]
        scale = payload.get("scale")
        if scale is not None:
            if isinstance(scale, (int, float)):
                root.scale = (float(scale), float(scale), float(scale))
            else:
                root.scale = tuple(scale)
        if name:
            try: root.name = name
            except Exception: pass
        return {"ok": True, "data": {
            "name": root.name, "type": root.type,
            "location": _safe_vec3(root.location),
            "rotation_euler": _safe_vec3(root.rotation_euler),
            "scale": _safe_vec3(root.scale),
        }}
    except Exception as e:
        return {"ok": False, "error": "add_primitive: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_light_main(payload):
    ltype = (payload.get("type") or "POINT").upper().strip()
    if ltype not in ("POINT", "SUN", "SPOT", "AREA"):
        return {"ok": False, "error": "unsupported light type: %s" % ltype}
    location = tuple(payload.get("location") or (0, 0, 5))
    energy = payload.get("energy")
    color = payload.get("color")
    name = payload.get("name")
    try:
        before = set(bpy.data.objects)
        bpy.ops.object.light_add(type=ltype, location=location)
        new_objs = [o for o in bpy.data.objects if o not in before]
        if not new_objs:
            return {"ok": False, "error": "light_add didn't create any object"}
        root = new_objs[0]
        if name:
            try: root.name = name
            except Exception: pass
        if energy is not None:
            try: root.data.energy = float(energy)
            except Exception: pass
        if color is not None and isinstance(color, (list, tuple)) and len(color) >= 3:
            try: root.data.color = (float(color[0]), float(color[1]), float(color[2]))
            except Exception: pass
        return {"ok": True, "data": {
            "name": root.name, "type": root.type,
            "light_type": ltype,
            "location": _safe_vec3(root.location),
            "energy": round(float(root.data.energy), 4),
            "color": _safe_color4(root.data.color),
        }}
    except Exception as e:
        return {"ok": False, "error": "add_light: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_set_camera_main(payload):
    """创建或更新相机，并设为 active。优先选名为 'Camera' 的；没有则新建"""
    location = payload.get("location")
    rotation = payload.get("rotation")
    lens = payload.get("lens")
    name = payload.get("name")
    try:
        # 找现有相机
        cam_obj = None
        if name:
            cam_obj = bpy.data.objects.get(name)
            if cam_obj and cam_obj.type != "CAMERA":
                cam_obj = None
        if cam_obj is None:
            # 找场景里第一个 camera
            for obj in bpy.data.objects:
                if obj.type == "CAMERA":
                    cam_obj = obj; break
        if cam_obj is None:
            # 新建
            cam_data = bpy.data.cameras.new("Camera")
            cam_obj = bpy.data.objects.new(name or "Camera", cam_data)
            bpy.context.collection.objects.link(cam_obj)
        if name and cam_obj.name != name:
            try: cam_obj.name = name
            except Exception: pass
        if location is not None:
            try: cam_obj.location = tuple(location)
            except Exception: pass
        if rotation is not None:
            try: cam_obj.rotation_euler = tuple(rotation)
            except Exception: pass
        if lens is not None:
            try: cam_obj.data.lens = float(lens)
            except Exception: pass
        bpy.context.scene.camera = cam_obj
        return {"ok": True, "data": {
            "name": cam_obj.name,
            "location": _safe_vec3(cam_obj.location),
            "rotation_euler": _safe_vec3(cam_obj.rotation_euler),
            "lens": round(float(cam_obj.data.lens), 4),
            "is_active": True,
        }}
    except Exception as e:
        return {"ok": False, "error": "set_camera: %s" % e, "traceback": traceback.format_exc(limit=4)}


# ============================================================
# 修改类
# ============================================================
def _mcp_update_object_main(payload):
    name = (payload.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if obj is None:
        return {"ok": False, "error": "object not found: %s" % name}
    try:
        if "location" in payload and payload["location"] is not None:
            obj.location = tuple(payload["location"])
        if "rotation" in payload and payload["rotation"] is not None:
            obj.rotation_euler = tuple(payload["rotation"])
        if "scale" in payload and payload["scale"] is not None:
            s = payload["scale"]
            if isinstance(s, (int, float)):
                obj.scale = (float(s), float(s), float(s))
            else:
                obj.scale = tuple(s)
        if "visible" in payload and payload["visible"] is not None:
            obj.hide_viewport = not bool(payload["visible"])
            obj.hide_render = not bool(payload["visible"])
        return {"ok": True, "data": {
            "name": obj.name,
            "location": _safe_vec3(obj.location),
            "rotation_euler": _safe_vec3(obj.rotation_euler),
            "scale": _safe_vec3(obj.scale),
        }}
    except Exception as e:
        return {"ok": False, "error": "update_object: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_set_material_main(payload):
    """通过 Principled BSDF 给物体设材质。已有材质就直接改，没有就新建。
    支持：base_color / roughness / metallic / emission_color / emission_strength"""
    name = (payload.get("obj_name") or payload.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "obj_name 不能为空"}
    obj = bpy.data.objects.get(name)
    if obj is None:
        return {"ok": False, "error": "object not found: %s" % name}
    if not hasattr(obj, "data") or not hasattr(obj.data, "materials"):
        return {"ok": False, "error": "object %s cannot accept materials" % name}
    try:
        # 取或建材质
        mat = None
        if len(obj.data.materials) > 0 and obj.data.materials[0] is not None:
            mat = obj.data.materials[0]
        if mat is None:
            mat_name = "%s_mat" % name
            mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
            if len(obj.data.materials) == 0:
                obj.data.materials.append(mat)
            else:
                obj.data.materials[0] = mat
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = None
        for node in nt.nodes:
            if node.type == "BSDF_PRINCIPLED":
                bsdf = node; break
        if bsdf is None:
            bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
            out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
            if out is None:
                out = nt.nodes.new("ShaderNodeOutputMaterial")
            nt.links.new(bsdf.outputs[0], out.inputs[0])
        bc = payload.get("base_color")
        if bc is not None and isinstance(bc, (list, tuple)) and len(bc) >= 3:
            a = float(bc[3]) if len(bc) >= 4 else 1.0
            bsdf.inputs["Base Color"].default_value = (float(bc[0]), float(bc[1]), float(bc[2]), a)
        if "roughness" in payload and payload["roughness"] is not None:
            try: bsdf.inputs["Roughness"].default_value = float(payload["roughness"])
            except Exception: pass
        if "metallic" in payload and payload["metallic"] is not None:
            try: bsdf.inputs["Metallic"].default_value = float(payload["metallic"])
            except Exception: pass
        ec = payload.get("emission_color")
        if ec is not None and isinstance(ec, (list, tuple)) and len(ec) >= 3 and "Emission" in bsdf.inputs:
            a = float(ec[3]) if len(ec) >= 4 else 1.0
            try: bsdf.inputs["Emission"].default_value = (float(ec[0]), float(ec[1]), float(ec[2]), a)
            except Exception:
                # Blender 4.x 改名为 "Emission Color"
                if "Emission Color" in bsdf.inputs:
                    bsdf.inputs["Emission Color"].default_value = (float(ec[0]), float(ec[1]), float(ec[2]), a)
        if "emission_strength" in payload and payload["emission_strength"] is not None:
            try:
                if "Emission Strength" in bsdf.inputs:
                    bsdf.inputs["Emission Strength"].default_value = float(payload["emission_strength"])
            except Exception: pass
        return {"ok": True, "data": {
            "obj": obj.name,
            "material": mat.name,
            "base_color": _safe_color4(bsdf.inputs["Base Color"].default_value),
            "roughness": round(float(bsdf.inputs["Roughness"].default_value), 4),
            "metallic": round(float(bsdf.inputs["Metallic"].default_value), 4),
        }}
    except Exception as e:
        return {"ok": False, "error": "set_material: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_delete_object_main(payload):
    name = (payload.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if obj is None:
        return {"ok": False, "error": "object not found: %s" % name}
    try:
        bpy.data.objects.remove(obj, do_unlink=True)
        return {"ok": True, "data": {"deleted": name}}
    except Exception as e:
        return {"ok": False, "error": "delete: %s" % e}


def _mcp_clear_scene_main(payload):
    """清空场景。v2.1.0 G-Hotfix2:默认彻底清空(含相机+灯光+空物体),AI 不传参也能干净起步。
    需保留传 keep_camera=true / keep_lights=true。
    用 bpy.data.objects.remove() 而不是 ops.delete()——前者忽视 view layer 可见性,
    能删隐藏/不可选的灯光(治用户报"清空后旧灯还在"bug)"""
    keep_camera = payload.get("keep_camera", False)
    keep_lights = payload.get("keep_lights", False)
    removed = []
    try:
        for obj in list(bpy.data.objects):
            if keep_camera and obj.type == "CAMERA":
                continue
            if keep_lights and obj.type == "LIGHT":
                continue
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                removed.append(obj.name)
            except Exception:
                pass
        return {"ok": True, "data": {"removed_count": len(removed), "removed": removed[:30]}}
    except Exception as e:
        return {"ok": False, "error": "clear_scene: %s" % e}


# ============================================================
# 兜底 exec_python（主线程，捕获 stdout，超时同步）
# ============================================================
def _mcp_exec_python_main(payload):
    code = payload.get("code") or ""
    if not code:
        # v2.0.4：AI 经常传空 {} 或漏掉 code 字段 → 给详细 hint 教它怎么改
        return {
            "ok": False,
            "error": "empty code",
            "hint": "exec_python 必须传 code 参数（非空字符串）。常见错误：① 你传了 {} 或漏掉 code 字段 → 正确格式 {\"code\": \"import bpy\\nbpy.ops.mesh.primitive_cube_add()\"} ② 如果只是想查询场景，请改调 get_scene_info / list_objects / get_object_info 原子工具，不需要走 exec_python ③ 如果要改材质/位置，请改调 set_material / update_object 原子工具，更稳定不会崩",
            "received_payload_keys": list(payload.keys()) if isinstance(payload, dict) else None
        }
    code = _sanitize_exec_code(code)

    buf = io.StringIO()
    # v2.0.3 预置 namespace：解决 LLM 写代码时直接用 mathutils.Vector / bmesh.new()
    # 报 NameError: name 'mathutils' is not defined 的硬伤
    globs = {"__name__": "__aichat_mcp__", "bpy": bpy}
    try:
        import math as _math
        import mathutils as _mu
        import bmesh as _bm
        from mathutils import Vector, Matrix, Euler, Quaternion, Color
        globs.update({
            "math": _math, "mathutils": _mu, "bmesh": _bm,
            "Vector": Vector, "Matrix": Matrix, "Euler": Euler,
            "Quaternion": Quaternion, "Color": Color,
        })
    except Exception:
        pass
    # v3.5.0：自动兼容 Blender 5.x 已废弃的 EEVEE 属性
    # AI 经常生成 scene.eevee.use_bloom = True 等代码，在 5.x 会 AttributeError
    _EEVEE_DEPRECATED_ATTRS = [
        'use_bloom', 'bloom_threshold', 'bloom_knee', 'bloom_radius',
        'bloom_color', 'bloom_intensity', 'bloom_clamp',
        'use_ssr', 'use_ssr_refraction', 'use_ssr_halfres',
        'ssr_quality', 'ssr_max_roughness', 'ssr_thickness', 'ssr_border_fade',
        'use_volumetric_lights', 'use_volumetric_shadows',
        'volumetric_start', 'volumetric_end',
        'use_gtao', 'gtao_distance', 'gtao_factor',
        'use_soft_shadows', 'shadow_method',
        'taa_render_samples', 'taa_samples',
    ]
    # 对每个废弃属性，把直接赋值替换成 hasattr 守护
    for _attr in _EEVEE_DEPRECATED_ATTRS:
        # 匹配 .xxx = value 或 .xxx=value（只替换 eevee 相关的）
        _pat = re.compile(r'(\b\w+\.eevee\.)' + _attr + r'\s*=\s*(.+)')
        if _pat.search(code):
            code = _pat.sub(
                lambda m: 'if hasattr(' + m.group(1).rstrip('.') + ', "' + _attr + '"): ' + m.group(0),
                code
            )
    try:
        import contextlib
        with contextlib.redirect_stdout(buf):
            exec(compile(code, "<mcp_exec_python>", "exec"), globs)
        out = buf.getvalue()
        return {"ok": True, "data": {"executed": True, "stdout": out[:4000]}}
    except Exception as e:
        tb = traceback.format_exc(limit=8)
        return {"ok": False, "error": "%s" % e, "traceback": tb, "stdout": buf.getvalue()[:2000]}


# ============================================================
# 质检（不抛错，返回结构化判定）
# ============================================================
def _mcp_quality_check_main(payload):
    rep = _collect_scene_report()
    issues = []
    stats = rep.get("stats", {})
    # 1) 相机
    if not stats.get("has_camera"):
        issues.append({"severity": "error", "code": "no_camera", "msg": "场景没有相机，无法渲染"})
    # 2) 光源
    if (stats.get("light_count") or 0) == 0 and (stats.get("emissive_mesh_count") or 0) == 0:
        issues.append({"severity": "warn", "code": "no_light", "msg": "没有灯光也没有自发光物体，画面会发黑"})
    # 3) 世界背景
    if not stats.get("has_world_bg"):
        issues.append({"severity": "warn", "code": "no_world_bg", "msg": "没有 World 背景，建议加 HDRI 或纯色"})
    # 4) 物体太多
    if (stats.get("mesh_count") or 0) > 200:
        issues.append({"severity": "info", "code": "too_many_meshes", "msg": "网格数 >200，渲染可能会慢"})
    # 5) 物体太少
    if (stats.get("mesh_count") or 0) == 0:
        issues.append({"severity": "warn", "code": "no_mesh", "msg": "场景空空如也"})
    summary = {"errors": sum(1 for i in issues if i["severity"] == "error"),
               "warnings": sum(1 for i in issues if i["severity"] == "warn"),
               "infos": sum(1 for i in issues if i["severity"] == "info")}
    return {"ok": True, "data": {"summary": summary, "issues": issues, "stats": stats}}


# ============================================================
# v2.1.0：场景 overview + 快照/回滚（Critic 审图前用 + 修复失败回滚用）
# ----------------------------------------------------------------
# 三个端点：
#   GET  /blend_summary       → token-friendly 概览（文件/物体计数/集合树/渲染设置）
#   POST /bookmark_state      → 把当前场景以 JSON 形式快照到 Blender 内存（按 name 索引）
#   POST /restore_state       → 从快照恢复（删掉新增物体 + 还原已存物体的 transform）
# 注意：bookmark_state 不存 mesh 顶点数据（爆内存），只存 transform / parent / material 名等元数据。
# 所以 restore_state 是"软回滚"——能撤销 transform 改动 + 删除自快照以来新增的物体，
# 但已被删的复杂 mesh 几何数据不在快照里所以回不来（在响应 missing 字段告知）。
# ============================================================

# 内存里的快照字典（key = 用户给的 name，value = 完整快照 dict）
_BLEND_SNAPSHOTS = {}


def _human_bytes(n):
    try:
        n = float(n)
    except Exception:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0:
            return ("%d %s" % (int(n), unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%.1f PB" % n


def _walk_collection(coll, recursive=True, depth=0, max_depth=6):
    """递归收集集合树结构。返回 {name, objects_count, children}。带 max_depth 防极端嵌套爆栈"""
    try:
        out = {
            "name": getattr(coll, "name", "?"),
            "objects_count": len(coll.objects) if hasattr(coll, "objects") else 0,
            "children": [],
        }
        if recursive and depth < max_depth and hasattr(coll, "children"):
            for child in coll.children:
                out["children"].append(_walk_collection(child, True, depth + 1, max_depth))
        return out
    except Exception:
        return {"name": "?", "objects_count": 0, "children": []}


def _mcp_blend_summary_main(payload):
    """主线程：返回 token-friendly 场景 overview（文件/物体计数/集合树/渲染设置）"""
    try:
        data = {"addon_version": ADDON_VERSION}
        # 1) blend 文件信息
        fp = bpy.data.filepath or ""
        size_bytes = 0
        if fp and os.path.exists(fp):
            try: size_bytes = os.path.getsize(fp)
            except Exception: size_bytes = 0
        data["blend_file"] = {
            "filepath": fp,
            "is_saved": bool(fp),
            "is_dirty": bool(getattr(bpy.data, "is_dirty", False)),
            "size_bytes": size_bytes,
            "size_human": _human_bytes(size_bytes) if size_bytes > 0 else "(unsaved)",
        }
        # 2) 物体计数（按 type 分组）
        by_type = {}
        for obj in bpy.data.objects:
            t = obj.type
            by_type[t] = by_type.get(t, 0) + 1
        data["object_counts"] = {
            "total": len(bpy.data.objects),
            "by_type": by_type,
        }
        # 3) 集合树
        scene = bpy.context.scene
        try:
            data["collection_tree"] = _walk_collection(scene.collection, True)
        except Exception:
            data["collection_tree"] = None
        # 4) 渲染设置
        rs = scene.render
        engine = getattr(rs, "engine", "") or ""
        samples = None
        try:
            if engine == "CYCLES":
                samples = int(getattr(scene.cycles, "samples", 0) or 0)
            elif engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
                samples = int(getattr(scene.eevee, "taa_render_samples", 0) or 0)
        except Exception:
            samples = None
        view_transform = None
        exposure = None
        try:
            view_transform = scene.view_settings.view_transform
            exposure = round(float(scene.view_settings.exposure), 4)
        except Exception:
            pass
        data["render_settings"] = {
            "engine": engine,
            "resolution_x": int(rs.resolution_x),
            "resolution_y": int(rs.resolution_y),
            "resolution_percentage": int(rs.resolution_percentage),
            "frame_start": int(scene.frame_start),
            "frame_end": int(scene.frame_end),
            "frame_current": int(scene.frame_current),
            "fps": int(rs.fps),
            "film_transparent": bool(getattr(rs, "film_transparent", False)),
            "samples": samples,
            "view_transform": view_transform,
            "exposure": exposure,
            "image_format": getattr(getattr(rs, "image_settings", None), "file_format", None),
        }
        # 5) 相机/世界
        cam = scene.camera
        data["active_camera"] = cam.name if cam else None
        world = scene.world
        if world is not None:
            data["world"] = {"name": world.name, "use_nodes": bool(getattr(world, "use_nodes", False))}
        else:
            data["world"] = None
        # 6) 一句话总结（给 LLM 当 system 提示用）
        bt_str = " + ".join(["%d %s" % (cnt, t.lower())
                             for t, cnt in sorted(by_type.items(), key=lambda x: -x[1])][:5])
        sum_str = "%s场景，%d 个物体（%s），%s 引擎 %dx%d" % (
            "已保存" if fp else "未保存",
            len(bpy.data.objects),
            bt_str or "无物体",
            engine or "(默认)",
            rs.resolution_x,
            rs.resolution_y,
        )
        if samples is not None:
            sum_str += " @ %d samples" % samples
        if cam is None:
            sum_str += "，⚠️ 没有相机"
        data["summary"] = sum_str
        # 7) 快照存量（让客户端能看到当前 bookmark_state 累计了几个）
        data["snapshots_count"] = len(_BLEND_SNAPSHOTS)
        data["snapshots_keys"] = sorted(_BLEND_SNAPSHOTS.keys())[:20]
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": "blend_summary: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _serialize_object_for_snapshot(obj):
    """主线程：把单个物体序列化成轻量 dict（不含 mesh 顶点数据，只存元数据）"""
    try:
        entry = {
            "type": obj.type,
            "location": _safe_vec3(obj.location),
            "rotation_euler": _safe_vec3(obj.rotation_euler),
            "scale": _safe_vec3(obj.scale),
            "hide_viewport": bool(obj.hide_viewport),
            "hide_render": bool(obj.hide_render),
            "parent": obj.parent.name if obj.parent else None,
        }
        # 第一个 material slot 的材质名
        try:
            if hasattr(obj, "material_slots") and len(obj.material_slots) > 0:
                slot = obj.material_slots[0]
                if slot and slot.material:
                    entry["material"] = slot.material.name
        except Exception: pass
        # 类型相关元数据
        if obj.type == "MESH":
            try:
                m = obj.data
                if m:
                    entry["mesh_name"] = m.name
                    entry["vertex_count"] = len(m.vertices)
                    entry["poly_count"] = len(m.polygons)
            except Exception: pass
        elif obj.type == "LIGHT":
            try:
                ld = obj.data
                entry["light_type"] = ld.type
                entry["energy"] = round(float(ld.energy), 4)
                entry["color"] = _safe_color4(ld.color)
            except Exception: pass
        elif obj.type == "CAMERA":
            try:
                cd = obj.data
                entry["lens"] = round(float(cd.lens), 4)
                entry["sensor_width"] = round(float(cd.sensor_width), 4)
            except Exception: pass
        return entry
    except Exception:
        return {"type": getattr(obj, "type", "?"), "_serialize_error": True}


def _mcp_bookmark_state_main(payload):
    """主线程：把当前场景以 JSON 形式快照到 _BLEND_SNAPSHOTS 内存字典"""
    name = (payload.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "name 不能为空（用作快照标识，例如 'baseline' / 'before_furniture_fix'）"}
    try:
        objects = {}
        for obj in bpy.data.objects:
            objects[obj.name] = _serialize_object_for_snapshot(obj)
        scene = bpy.context.scene
        snap = {
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "addon_version": ADDON_VERSION,
            "objects": objects,
            "render_engine": getattr(scene.render, "engine", None),
            "frame_current": int(scene.frame_current),
            "active_camera": scene.camera.name if scene.camera else None,
        }
        _BLEND_SNAPSHOTS[name] = snap
        # 估算大小（对用户透明）
        try:
            blob = json.dumps(snap, ensure_ascii=False)
            est_bytes = len(blob.encode("utf-8"))
        except Exception:
            est_bytes = 0
        push_log("INFO", "bookmark_state '%s' = %d objects (%s)" % (name, len(objects), _human_bytes(est_bytes)))
        return {"ok": True, "data": {
            "name": name,
            "saved_at": snap["saved_at"],
            "objects_count": len(objects),
            "bytes_estimate": est_bytes,
            "bytes_human": _human_bytes(est_bytes),
            "snapshot_keys": sorted(_BLEND_SNAPSHOTS.keys()),
        }}
    except Exception as e:
        return {"ok": False, "error": "bookmark_state: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_restore_state_main(payload):
    """主线程：从 _BLEND_SNAPSHOTS 恢复
    行为（软回滚）：
      - 删除自快照以来新增的物体（current - snapshot）
      - 还原仍存在物体的 location / rotation / scale / hide_*（current ∩ snapshot）
      - 已被删的复杂 mesh 物体（snapshot - current）无法重建，列在 missing 里告知
      - 还原 frame_current / active_camera（best-effort）
    """
    name = (payload.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "name 不能为空（指定要恢复的快照 key）"}
    snap = _BLEND_SNAPSHOTS.get(name)
    if snap is None:
        keys = sorted(_BLEND_SNAPSHOTS.keys())
        return {"ok": False, "error": "快照 '%s' 不存在。当前快照列表：%s" % (
            name, keys if keys else "(空，先调 POST /bookmark_state)"
        )}
    try:
        snap_objects = snap.get("objects") or {}
        current_names = set(o.name for o in bpy.data.objects)
        snap_names = set(snap_objects.keys())
        # 1) 删掉新增的（current - snap）
        to_delete = sorted(current_names - snap_names)
        deleted = []
        for n in to_delete:
            obj = bpy.data.objects.get(n)
            if obj is None: continue
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
                deleted.append(n)
            except Exception as e:
                push_log("WARN", "restore_state delete '%s' failed: %s" % (n, e))
        # 2) 还原仍存在的 transform（current ∩ snap）
        to_restore = sorted(current_names & snap_names)
        restored = 0
        for n in to_restore:
            obj = bpy.data.objects.get(n)
            if obj is None: continue
            entry = snap_objects.get(n) or {}
            try:
                if entry.get("location") is not None:
                    obj.location = tuple(entry["location"])
                if entry.get("rotation_euler") is not None:
                    obj.rotation_euler = tuple(entry["rotation_euler"])
                if entry.get("scale") is not None:
                    obj.scale = tuple(entry["scale"])
                obj.hide_viewport = bool(entry.get("hide_viewport", False))
                obj.hide_render = bool(entry.get("hide_render", False))
                restored += 1
            except Exception as e:
                push_log("WARN", "restore_state '%s' transform failed: %s" % (n, e))
        # 3) 已丢失的（snap - current）只统计无法重建
        missing = sorted(snap_names - current_names)
        # 4) 还原 frame_current / active_camera（best-effort）
        scene = bpy.context.scene
        try:
            if snap.get("frame_current") is not None:
                scene.frame_current = int(snap["frame_current"])
        except Exception: pass
        cam_name = snap.get("active_camera")
        if cam_name:
            cam_obj = bpy.data.objects.get(cam_name)
            if cam_obj and cam_obj.type == "CAMERA":
                try: scene.camera = cam_obj
                except Exception: pass
        push_log("INFO", "restore_state '%s': -%d new, ~%d transform, missing=%d" % (
            name, len(deleted), restored, len(missing)
        ))
        summary = "已删除 %d 个新增物体，恢复 %d 个物体 transform" % (len(deleted), restored)
        if missing:
            preview = ", ".join(missing[:3]) + ("…" if len(missing) > 3 else "")
            summary += "，⚠️ %d 个物体已丢失无法重建（%s）" % (len(missing), preview)
        return {"ok": True, "data": {
            "name": name,
            "saved_at": snap.get("saved_at"),
            "deleted_count": len(deleted),
            "deleted": deleted[:30],
            "restored_count": restored,
            "missing_count": len(missing),
            "missing": missing[:30],
            "summary": summary,
        }}
    except Exception as e:
        return {"ok": False, "error": "restore_state: %s" % e, "traceback": traceback.format_exc(limit=4)}


# ============================================================
# v3.5.0 新增：布尔运算工具（高精度建模核心）
# ============================================================
def _mcp_boolean_union_main(payload):
    """主线程：布尔并集 - 将两个物体合并为一个"""
    target_name = (payload.get("target_name") or payload.get("target") or "").strip()
    tool_name = (payload.get("tool_name") or payload.get("cutter") or "").strip()
    if not target_name or not tool_name:
        return {"ok": False, "error": "target_name 和 tool_name 都不能为空"}
    target = bpy.data.objects.get(target_name)
    tool = bpy.data.objects.get(tool_name)
    if not target: return {"ok": False, "error": "目标物体不存在: %s" % target_name}
    if not tool: return {"ok": False, "error": "工具物体不存在: %s" % tool_name}
    if target.type != 'MESH' or tool.type != 'MESH':
        return {"ok": False, "error": "两个物体都必须是 MESH 类型"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        mod = target.modifiers.new(name="Boolean_Union", type='BOOLEAN')
        mod.operation = 'UNION'
        mod.object = tool
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(tool, do_unlink=True)
        return {"ok": True, "data": {"name": target.name, "operation": "UNION", "cutter_removed": tool_name}}
    except Exception as e:
        return {"ok": False, "error": "boolean_union: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_boolean_difference_main(payload):
    """主线程：布尔差集 - 从目标物体减去工具物体"""
    target_name = (payload.get("target_name") or payload.get("target") or "").strip()
    tool_name = (payload.get("tool_name") or payload.get("cutter") or "").strip()
    if not target_name or not tool_name:
        return {"ok": False, "error": "target_name 和 tool_name 都不能为空"}
    target = bpy.data.objects.get(target_name)
    tool = bpy.data.objects.get(tool_name)
    if not target: return {"ok": False, "error": "目标物体不存在: %s" % target_name}
    if not tool: return {"ok": False, "error": "工具物体不存在: %s" % tool_name}
    if target.type != 'MESH' or tool.type != 'MESH':
        return {"ok": False, "error": "两个物体都必须是 MESH 类型"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        mod = target.modifiers.new(name="Boolean_Difference", type='BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = tool
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(tool, do_unlink=True)
        return {"ok": True, "data": {"name": target.name, "operation": "DIFFERENCE", "cutter_removed": tool_name}}
    except Exception as e:
        return {"ok": False, "error": "boolean_difference: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_boolean_intersect_main(payload):
    """主线程：布尔交集 - 保留两个物体的重叠部分"""
    target_name = (payload.get("target_name") or payload.get("target") or "").strip()
    tool_name = (payload.get("tool_name") or payload.get("cutter") or "").strip()
    if not target_name or not tool_name:
        return {"ok": False, "error": "target_name 和 tool_name 都不能为空"}
    target = bpy.data.objects.get(target_name)
    tool = bpy.data.objects.get(tool_name)
    if not target: return {"ok": False, "error": "目标物体不存在: %s" % target_name}
    if not tool: return {"ok": False, "error": "工具物体不存在: %s" % tool_name}
    if target.type != 'MESH' or tool.type != 'MESH':
        return {"ok": False, "error": "两个物体都必须是 MESH 类型"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        mod = target.modifiers.new(name="Boolean_Intersect", type='BOOLEAN')
        mod.operation = 'INTERSECT'
        mod.object = tool
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(tool, do_unlink=True)
        return {"ok": True, "data": {"name": target.name, "operation": "INTERSECT", "cutter_removed": tool_name}}
    except Exception as e:
        return {"ok": False, "error": "boolean_intersect: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_subdivision_main(payload):
    """主线程：添加细分曲面修改器"""
    name = (payload.get("name") or "").strip()
    levels = int(payload.get("levels") or payload.get("subdivision_levels") or 2)
    render_levels = int(payload.get("render_levels") or levels + 1)
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    if levels > 5: return {"ok": False, "error": "细分层级不能超过 5（太高会卡死 Blender）"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Subdivision", type='SUBSURF')
        mod.levels = levels
        mod.render_levels = render_levels
        mod.subdivision_type = 'CATMULL_CLARK'
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name, "levels": levels, "render_levels": render_levels}}
    except Exception as e:
        return {"ok": False, "error": "add_subdivision: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_bevel_main(payload):
    """主线程：添加倒角修改器（Blender 4.2+ 兼容）"""
    name = (payload.get("name") or "").strip()
    width = float(payload.get("width") or payload.get("bevel_width") or 0.05)
    segments = int(payload.get("segments") or 3)
    affect = payload.get("affect") or "EDGES"
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    if affect not in ("EDGES", "VERTICES"): return {"ok": False, "error": "affect 必须是 'EDGES' 或 'VERTICES'"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Bevel", type='BEVEL')
        mod.width = width
        mod.segments = segments
        mod.affect = affect
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name, "width": width, "segments": segments, "affect": affect}}
    except Exception as e:
        return {"ok": False, "error": "add_bevel: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_smart_smooth_main(payload):
    """智能平滑：设置 auto_smooth + shade_smooth（兼容 Blender 4.1+ / 5.x）"""
    try:
        obj_name = payload.get("name")
        angle_limit = payload.get("angle_limit", 30)
        obj = bpy.data.objects.get(obj_name)
        if not obj or obj.type != 'MESH':
            return {"ok": False, "error": "smart_smooth: object not found or not mesh"}
        
        # shade smooth
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shade_smooth()
        
        # Blender 4.1+ 移除了 use_auto_smooth，改用 Smooth by Angle 修改器
        # 先检查是否已有该修改器，避免重复添加
        has_smooth_modifier = any(m.type == 'SMOOTH' for m in obj.modifiers)
        if not has_smooth_modifier:
            mod = obj.modifiers.new(name="SmoothByAngle", type='SMOOTH')
            mod.factor = 1.0
            mod.angle = math.radians(angle_limit)
        
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": "smart_smooth: %s" % e, "traceback": traceback.format_exc(limit=4)}


# ============================================================
# v3.4.5 新增：10 个高可操控性建模工具
# ============================================================

def _mcp_smart_uv_project_main(payload):
    """主线程：智能 UV 投射（smart/cube/cylinder/sphere）"""
    name = (payload.get("name") or "").strip()
    method = (payload.get("method") or "smart").lower()
    island_margin = float(payload.get("island_margin") or 0.02)
    angle_limit = float(payload.get("angle_limit") or 66.0)
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    valid_methods = ("smart", "cube", "cylinder", "sphere")
    if method not in valid_methods:
        return {"ok": False, "error": "method 必须是 %s 之一" % str(valid_methods)}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        if method == "smart":
            bpy.ops.uv.smart_project(angle_limit=math.radians(angle_limit), island_margin=island_margin)
        elif method == "cube":
            bpy.ops.uv.cube_project()
        elif method == "cylinder":
            bpy.ops.uv.cylinder_project()
        elif method == "sphere":
            bpy.ops.uv.sphere_project()
        bpy.ops.object.mode_set(mode='OBJECT')
        return {"ok": True, "data": {"name": obj.name, "method": method, "island_margin": island_margin}}
    except Exception as e:
        try: bpy.ops.object.mode_set(mode='OBJECT')
        except: pass
        return {"ok": False, "error": "smart_uv_project: %s" % e}


def _mcp_add_modifier_main(payload):
    """主线程：通用修改器添加（Array/Mirror/Solidify/SimpleDeform/Shrinkwrap/Wireframe/Displace/Cast/Lattice/Remesh）"""
    name = (payload.get("name") or "").strip()
    mod_type = (payload.get("modifier_type") or "").upper()
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    valid_types = {
        "ARRAY": "Array", "MIRROR": "Mirror", "SOLIDIFY": "Solidify",
        "SIMPLE_DEFORM": "SimpleDeform", "SHRINKWRAP": "Shrinkwrap",
        "WIREFRAME": "Wireframe", "DISPLACE": "Displace", "CAST": "Cast",
        "LATTICE": "Lattice", "REMESH": "Remesh", "SCREW": "Screw",
        "SKIN": "Skin", "TRIANGULATE": "Triangulate", "WELD": "Weld",
        "CURVE": "Curve", "EDGE_SPLIT": "EdgeSplit"
    }
    if mod_type not in valid_types:
        return {"ok": False, "error": "modifier_type 必须是 %s 之一" % list(valid_types.keys())}
    props = payload.get("properties") or {}
    try:
        mod = obj.modifiers.new(name=valid_types[mod_type], type=mod_type)
        applied_props = {}
        for k, v in props.items():
            if hasattr(mod, k):
                try:
                    # 数组属性（如 relative_offset_displace）需要按索引赋值
                    attr = getattr(mod, k)
                    if hasattr(attr, '__len__') and not isinstance(v, str):
                        if isinstance(v, (list, tuple)):
                            for i, val in enumerate(v):
                                if i < len(attr):
                                    attr[i] = val
                        else:
                            setattr(mod, k, v)
                    else:
                        setattr(mod, k, v)
                    applied_props[k] = v
                except Exception as pe:
                    applied_props[k] = "FAILED: %s" % pe
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name, "type": mod_type, "applied_properties": applied_props}}
    except Exception as e:
        return {"ok": False, "error": "add_modifier: %s" % e}


def _mcp_parent_objects_main(payload):
    """主线程：设置父子关系（把 children 挂到 parent 下面）"""
    parent_name = (payload.get("parent_name") or "").strip()
    children_names = payload.get("children_names") or []
    keep_transform = payload.get("keep_transform") if payload.get("keep_transform") is not None else True
    if not parent_name: return {"ok": False, "error": "parent_name 不能为空"}
    if not children_names or not isinstance(children_names, list):
        return {"ok": False, "error": "children_names 必须是非空数组"}
    parent = bpy.data.objects.get(parent_name)
    if not parent: return {"ok": False, "error": "父物体不存在: %s" % parent_name}
    linked = []
    errors = []
    for cn in children_names:
        cn = (cn or "").strip()
        child = bpy.data.objects.get(cn)
        if not child:
            errors.append("子物体不存在: %s" % cn)
            continue
        try:
            if keep_transform:
                child.parent = parent
                child.matrix_parent_inverse = parent.matrix_world.inverted()
            else:
                child.parent = parent
            linked.append(cn)
        except Exception as e:
            errors.append("%s: %s" % (cn, e))
    return {"ok": True, "data": {"parent": parent_name, "linked": linked, "errors": errors}}


def _mcp_snap_to_ground_main(payload):
    """主线程：自动贴地（把物体最低点对齐到 Z=target_z）"""
    name = (payload.get("name") or "").strip()
    target_z = float(payload.get("target_z") or 0.0)
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.context.view_layer.update()
        from mathutils import Vector
        min_z = min((obj.matrix_world @ Vector(v)).z for v in obj.bound_box)
        offset = target_z - min_z
        obj.location.z += offset
        return {"ok": True, "data": {"name": obj.name, "old_min_z": round(min_z, 4), "offset": round(offset, 4), "new_location_z": round(obj.location.z, 4)}}
    except Exception as e:
        return {"ok": False, "error": "snap_to_ground: %s" % e}


def _mcp_duplicate_object_main(payload):
    """主线程：复制物体（独立副本或链接副本）"""
    name = (payload.get("name") or "").strip()
    new_name = (payload.get("new_name") or "").strip()
    linked = bool(payload.get("linked"))
    location = payload.get("location")
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        if linked:
            new_obj = obj.copy()
        else:
            new_obj = obj.copy()
            if obj.data:
                new_obj.data = obj.data.copy()
        if new_name:
            new_obj.name = new_name
        bpy.context.collection.objects.link(new_obj)
        if location and isinstance(location, (list, tuple)) and len(location) >= 3:
            new_obj.location = (float(location[0]), float(location[1]), float(location[2]))
        # 复制材质槽
        for slot in obj.material_slots:
            if slot.material and not linked:
                pass  # data.copy() 已经复制了材质引用
        return {"ok": True, "data": {"original": obj.name, "new_name": new_obj.name, "linked": linked, "location": list(new_obj.location)}}
    except Exception as e:
        return {"ok": False, "error": "duplicate_object: %s" % e}


def _mcp_apply_modifier_main(payload):
    """主线程：应用修改器（把 modifier 结果固化到 mesh）"""
    name = (payload.get("name") or "").strip()
    modifier_name = (payload.get("modifier_name") or "").strip()
    apply_all = bool(payload.get("apply_all"))
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        applied = []
        if apply_all:
            for mod in list(obj.modifiers):
                try:
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    applied.append(mod.name)
                except Exception as me:
                    applied.append("%s (FAILED: %s)" % (mod.name, me))
        else:
            if not modifier_name:
                return {"ok": False, "error": "modifier_name 不能为空（或设 apply_all=true 应用全部）"}
            mod = obj.modifiers.get(modifier_name)
            if not mod:
                return {"ok": False, "error": "修改器不存在: %s，已有: %s" % (modifier_name, [m.name for m in obj.modifiers])}
            bpy.ops.object.modifier_apply(modifier=modifier_name)
            applied.append(modifier_name)
        return {"ok": True, "data": {"name": obj.name, "applied": applied, "remaining_modifiers": [m.name for m in obj.modifiers]}}
    except Exception as e:
        return {"ok": False, "error": "apply_modifier: %s" % e}


def _mcp_separate_by_material_main(payload):
    """主线程：按材质拆分物体"""
    name = (payload.get("name") or "").strip()
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    try:
        existing = set(o.name for o in bpy.data.objects)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='MATERIAL')
        bpy.ops.object.mode_set(mode='OBJECT')
        new_objects = [o.name for o in bpy.data.objects if o.name not in existing and o.name != name]
        return {"ok": True, "data": {"original": name, "new_objects": new_objects, "total_parts": len(new_objects) + 1}}
    except Exception as e:
        try: bpy.ops.object.mode_set(mode='OBJECT')
        except: pass
        return {"ok": False, "error": "separate_by_material: %s" % e}


def _mcp_render_image_main(payload):
    """主线程：渲染当前视角为图片"""
    output_path = (payload.get("output_path") or "").strip()
    resolution_x = int(payload.get("resolution_x") or 1920)
    resolution_y = int(payload.get("resolution_y") or 1080)
    samples = int(payload.get("samples") or 64)
    use_viewport = bool(payload.get("use_viewport"))
    if not output_path:
        import tempfile
        output_path = os.path.join(tempfile.gettempdir(), "aichat_render_%d.png" % int(time.time()))
    try:
        scene = bpy.context.scene
        old_rx, old_ry = scene.render.resolution_x, scene.render.resolution_y
        scene.render.resolution_x = resolution_x
        scene.render.resolution_y = resolution_y
        scene.render.filepath = output_path
        scene.render.image_settings.file_format = 'PNG'
        if hasattr(scene.eevee, 'taa_render_samples'):
            scene.eevee.taa_render_samples = samples
        bpy.ops.render.render(write_still=True, use_viewport=use_viewport)
        scene.render.resolution_x, scene.render.resolution_y = old_rx, old_ry
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        return {"ok": True, "data": {"output_path": output_path, "resolution": [resolution_x, resolution_y], "file_size_kb": round(file_size / 1024, 1)}}
    except Exception as e:
        return {"ok": False, "error": "render_image: %s" % e}


def _mcp_render_layers_main(payload):
    """主线程：分层渲染（环境RGBA + 深度 + AO阴影）到一个目录，供摄影后期合成用。EEVEE Next。
    env=环境(8bit RGBA), depth=深度(16bit归一化), shadow=AO接触暗部(16bit，引擎不支持AO pass时自动省略)。"""
    output_dir = (payload.get("output_dir") or "").strip()
    resolution_x = int(payload.get("resolution_x") or 1920)
    resolution_y = int(payload.get("resolution_y") or 1080)
    samples = int(payload.get("samples") or 64)
    _t = payload.get("transparent")
    transparent = True if _t is None else bool(_t)
    if not output_dir:
        # 默认落到 workspace（用户易找），失败再回退临时目录
        try:
            output_dir = os.path.join(os.path.expanduser("~"), "Desktop", "ai-chat-workspace", "_render_layers", "layers_%d" % int(time.time()))
        except Exception:
            output_dir = os.path.join(tempfile.gettempdir(), "aichat_layers_%d" % int(time.time()))
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        return {"ok": False, "error": "无法创建输出目录: %s" % e}

    scene = bpy.context.scene
    vl = bpy.context.view_layer
    prev = {}
    try:
        # 1) 引擎 → EEVEE Next（兼容不同 Blender 版本的 engine id）
        prev["engine"] = scene.render.engine
        eng_set = None
        for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = eng
                eng_set = eng
                break
            except Exception:
                continue

        # 2) 分辨率 / 采样 / 透明底
        prev["rx"] = scene.render.resolution_x
        prev["ry"] = scene.render.resolution_y
        prev["film"] = scene.render.film_transparent
        prev["use_nodes"] = scene.use_nodes
        prev["fp"] = scene.render.filepath
        scene.render.resolution_x = resolution_x
        scene.render.resolution_y = resolution_y
        scene.render.film_transparent = bool(transparent)
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = samples

        # 3) passes：深度恒有；AO 需引擎支持（hasattr 守护，不支持时降级）
        vl.use_pass_z = True
        ao_ok = False
        try:
            if hasattr(vl, "use_pass_ambient_occlusion"):
                vl.use_pass_ambient_occlusion = True
                if hasattr(scene.eevee, "use_gtao"):
                    scene.eevee.use_gtao = True
                ao_ok = True
        except Exception:
            ao_ok = False

        # 4) compositor：不破坏用户已有节点 —— 记录现有节点，只追加自己的，渲染后删除
        scene.use_nodes = True
        nt = scene.node_tree
        existing = set(nt.nodes)
        rl = nt.nodes.new("CompositorNodeRLayers")
        rl.location = (-500, 0)
        out = nt.nodes.new("CompositorNodeOutputFile")
        out.location = (500, 0)
        out.base_path = output_dir

        written = []
        # env 层（复用 File Output 默认 slot[0]）：PNG 8bit RGBA/RGB
        s_env = out.file_slots[0]
        s_env.path = "env"
        s_env.use_node_format = False
        s_env.format.file_format = "PNG"
        s_env.format.color_mode = "RGBA" if transparent else "RGB"
        s_env.format.color_depth = "8"
        nt.links.new(rl.outputs["Image"], out.inputs[0])
        written.append("env")

        # depth 层：Normalize 归一化 → PNG 16bit BW（近浅远深）
        if "Depth" in rl.outputs:
            norm = nt.nodes.new("CompositorNodeNormalize")
            norm.location = (0, -250)
            s_d = out.file_slots.new("depth")
            s_d.use_node_format = False
            s_d.format.file_format = "PNG"
            s_d.format.color_mode = "BW"
            s_d.format.color_depth = "16"
            nt.links.new(rl.outputs["Depth"], norm.inputs[0])
            nt.links.new(norm.outputs[0], out.inputs[-1])
            written.append("depth")

        # shadow/AO 层：PNG 16bit BW（引擎无 AO pass 时省略）
        if ao_ok and "AO" in rl.outputs:
            s_s = out.file_slots.new("shadow")
            s_s.use_node_format = False
            s_s.format.file_format = "PNG"
            s_s.format.color_mode = "BW"
            s_s.format.color_depth = "16"
            nt.links.new(rl.outputs["AO"], out.inputs[-1])
            written.append("shadow")

        # 5) 渲染（触发 File Output 写盘）
        frame = scene.frame_current
        bpy.ops.render.render(write_still=False)

        # 6) 收集生成的文件（File Output 命名 {slot}{frame:04d}.png）
        results = {}
        for slot in written:
            cand = os.path.join(output_dir, "%s%04d.png" % (slot, frame))
            if not os.path.exists(cand):
                try:
                    for f in sorted(os.listdir(output_dir)):
                        if f.startswith(slot) and f.lower().endswith(".png"):
                            cand = os.path.join(output_dir, f)
                            break
                except Exception:
                    pass
            if os.path.exists(cand):
                results[slot] = cand

        # 7) 清理自己加的节点 + 还原渲染设置（不破坏用户原 compositor）
        for n in list(nt.nodes):
            if n not in existing:
                try:
                    nt.nodes.remove(n)
                except Exception:
                    pass
        scene.use_nodes = prev["use_nodes"]
        scene.render.resolution_x = prev["rx"]
        scene.render.resolution_y = prev["ry"]
        scene.render.film_transparent = prev["film"]
        scene.render.filepath = prev["fp"]

        return {"ok": True, "data": {
            "output_dir": output_dir,
            "engine": eng_set,
            "layers": results,
            "layer_count": len(results),
            "ao_available": ao_ok,
            "resolution": [resolution_x, resolution_y],
            "note": "env=环境(RGBA), depth=深度16bit归一化(近浅远深), shadow=AO接触暗部16bit"
                    + ("" if ao_ok else " · 当前引擎无 AO pass，仅出 env+depth"),
        }}
    except Exception as e:
        return {"ok": False, "error": "render_layers: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_render_layers_main(payload):
    """主线程：分层渲染，供摄影后期 PS 合成自备人物用。
    一次渲出三层到 output_dir（EEVEE Next + compositor File Output）：
      - env    : 环境成品（RGBA，可透明底），8bit PNG
      - depth  : 归一化深度（近浅远深），16bit PNG
      - shadow : AO 环境光遮蔽（接触暗部），16bit PNG（引擎无 AO 通道时自动跳过）
    """
    import glob
    output_dir = (payload.get("output_dir") or "").strip()
    resolution_x = int(payload.get("resolution_x") or 1920)
    resolution_y = int(payload.get("resolution_y") or 1080)
    samples = int(payload.get("samples") or 64)
    transparent = payload.get("transparent")
    transparent = True if transparent is None else bool(transparent)
    if not output_dir:
        output_dir = os.path.join(os.path.expanduser("~"), "Desktop", "ai-chat-workspace",
                                  "_render_layers", "layers_%d" % int(time.time()))
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        return {"ok": False, "error": "无法创建输出目录: %s" % e}

    scene = bpy.context.scene
    vl = bpy.context.view_layer
    backup = {
        "engine": scene.render.engine,
        "rx": scene.render.resolution_x,
        "ry": scene.render.resolution_y,
        "film": bool(getattr(scene.render, "film_transparent", False)),
        "filepath": scene.render.filepath,
    }
    try:
        # 1) 引擎：EEVEE Next（兼容 4.2+ 的 BLENDER_EEVEE_NEXT 与 5.x 的 BLENDER_EEVEE）
        engine_set = None
        for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
            try:
                scene.render.engine = eng
                engine_set = eng
                break
            except Exception:
                continue
        scene.render.resolution_x = resolution_x
        scene.render.resolution_y = resolution_y
        scene.render.film_transparent = bool(transparent)
        try:
            if hasattr(scene.eevee, "taa_render_samples"):
                scene.eevee.taa_render_samples = samples
        except Exception:
            pass

        # 2) 开启 passes（深度 + AO，全部防御）
        try:
            vl.use_pass_z = True
        except Exception:
            pass
        ao_ok = False
        try:
            if hasattr(vl, "use_pass_ambient_occlusion"):
                vl.use_pass_ambient_occlusion = True
                if hasattr(scene.eevee, "use_gtao"):
                    scene.eevee.use_gtao = True
                ao_ok = True
        except Exception:
            ao_ok = False

        # 3) 合成器 File Output（注意：会重建 scene 合成节点树）
        scene.use_nodes = True
        nt = scene.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        rl = nt.nodes.new("CompositorNodeRLayers")
        rl.location = (0, 0)
        fout = nt.nodes.new("CompositorNodeOutputFile")
        fout.location = (500, 0)
        fout.base_path = output_dir
        try:
            fout.file_slots.clear()
        except Exception:
            while len(fout.file_slots) > 0:
                fout.file_slots.remove(fout.inputs[0])

        def _add_slot(slot_name, mode, depth):
            fout.file_slots.new(slot_name)
            slot = fout.file_slots[slot_name]
            slot.use_node_format = False
            slot.format.file_format = 'PNG'
            slot.format.color_mode = mode
            slot.format.color_depth = depth
            return slot

        layers = ["env"]
        # env: RGBA/RGB 8bit
        _add_slot("env", "RGBA" if transparent else "RGB", "8")
        nt.links.new(rl.outputs["Image"], fout.inputs["env"])
        # depth: 归一化 BW 16bit
        if "Depth" in rl.outputs:
            norm = nt.nodes.new("CompositorNodeNormalize")
            norm.location = (250, -250)
            nt.links.new(rl.outputs["Depth"], norm.inputs[0])
            _add_slot("depth", "BW", "16")
            nt.links.new(norm.outputs[0], fout.inputs["depth"])
            layers.append("depth")
        # shadow(AO): BW 16bit
        if ao_ok and "AO" in rl.outputs:
            _add_slot("shadow", "BW", "16")
            nt.links.new(rl.outputs["AO"], fout.inputs["shadow"])
            layers.append("shadow")

        # 4) 渲染（File Output 在合成阶段自动写盘；主输出另存免污染）
        scene.render.filepath = os.path.join(output_dir, "_main_")
        scene.render.image_settings.file_format = 'PNG'
        bpy.ops.render.render(write_still=True)

        # 5) File Output 文件名带帧号后缀（如 env0001.png）→ 扫描真实路径
        frame = scene.frame_current
        result_files = {}
        for slot_name in layers:
            cand = os.path.join(output_dir, "%s%04d.png" % (slot_name, frame))
            if os.path.exists(cand):
                result_files[slot_name] = cand
            else:
                g = sorted(glob.glob(os.path.join(output_dir, slot_name + "*.png")))
                if g:
                    result_files[slot_name] = g[-1]

        note = "env=环境成品(8bit%s) / depth=归一化深度(16bit,近浅远深) / shadow=AO接触暗部(16bit)。" % (",透明底" if transparent else "")
        if not ("shadow" in result_files):
            note += " 注意：当前引擎无 AO 通道，已跳过 shadow 层。"
        return {"ok": True, "data": {
            "output_dir": output_dir,
            "layers": result_files,
            "engine": engine_set,
            "resolution": [resolution_x, resolution_y],
            "transparent": bool(transparent),
            "note": note,
        }}
    except Exception as e:
        return {"ok": False, "error": "render_layers: %s" % e, "traceback": traceback.format_exc(limit=4)}
    finally:
        try:
            scene.render.engine = backup["engine"]
            scene.render.resolution_x = backup["rx"]
            scene.render.resolution_y = backup["ry"]
            scene.render.film_transparent = backup["film"]
            scene.render.filepath = backup["filepath"]
        except Exception:
            pass


def _mcp_set_world_main(payload):
    """主线程：设置世界背景（颜色/强度/使用节点）"""
    color = payload.get("color") or payload.get("bg_color")
    strength = payload.get("strength")
    try:
        world = bpy.context.scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        result = {"name": world.name}
        if bg:
            if color and isinstance(color, (list, tuple)) and len(color) >= 3:
                a = float(color[3]) if len(color) >= 4 else 1.0
                bg.inputs[0].default_value = (float(color[0]), float(color[1]), float(color[2]), a)
                result["color"] = list(color[:3])
            if strength is not None and len(bg.inputs) > 1:
                bg.inputs[1].default_value = float(strength)
                result["strength"] = float(strength)
        return {"ok": True, "data": result}
    except Exception as e:
        return {"ok": False, "error": "set_world: %s" % e}


def _mcp_set_vertex_color_main(payload):
    """主线程：给物体添加顶点色图层并填充指定颜色"""
    name = (payload.get("name") or "").strip()
    color = payload.get("color") or [1, 1, 1, 1]
    layer_name = (payload.get("layer_name") or "Color").strip()
    if not name: return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj: return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH': return {"ok": False, "error": "物体必须是 MESH 类型"}
    if not isinstance(color, (list, tuple)) or len(color) < 3:
        return {"ok": False, "error": "color 必须是 [R,G,B] 或 [R,G,B,A] 数组"}
    try:
        mesh = obj.data
        if not mesh.vertex_colors:
            mesh.vertex_colors.new(name=layer_name)
        vcol = mesh.vertex_colors.get(layer_name) or mesh.vertex_colors.active
        r, g, b = float(color[0]), float(color[1]), float(color[2])
        a = float(color[3]) if len(color) >= 4 else 1.0
        for loop in vcol.data:
            loop.color = (r, g, b, a)
        return {"ok": True, "data": {"name": obj.name, "layer": vcol.name, "color": [r, g, b, a], "loop_count": len(vcol.data)}}
    except Exception as e:
        return {"ok": False, "error": "set_vertex_color: %s" % e}


# ============================================================
# v3.5.0 新增：30 个高精度建模工具 handler 函数
# ============================================================

def _mcp_set_origin_main(payload):
    """主线程：设置物体原点"""
    name = (payload.get("name") or "").strip()
    origin_type = payload.get("origin_type") or "ORIGIN_GEOMETRY"
    valid = ["GEOMETRY_ORIGIN", "ORIGIN_GEOMETRY", "ORIGIN_CURSOR",
             "ORIGIN_CENTER_OF_MASS", "ORIGIN_CENTER_OF_VOLUME"]
    if origin_type not in valid:
        origin_type = "ORIGIN_GEOMETRY"
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.origin_set(type=origin_type)
        return {"ok": True, "data": {"name": obj.name, "origin_type": origin_type,
                                      "location": list(obj.location)}}
    except Exception as e:
        return {"ok": False, "error": "set_origin: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_apply_transform_main(payload):
    """主线程：应用物体变换（位置/旋转/缩放固化到 mesh 数据）"""
    name = (payload.get("name") or "").strip()
    apply_location = bool(payload.get("apply_location", False))
    apply_rotation = bool(payload.get("apply_rotation", True))
    apply_scale = bool(payload.get("apply_scale", True))
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(
            location=apply_location,
            rotation=apply_rotation,
            scale=apply_scale
        )
        return {"ok": True, "data": {"name": obj.name,
                                      "applied_location": apply_location,
                                      "applied_rotation": apply_rotation,
                                      "applied_scale": apply_scale}}
    except Exception as e:
        return {"ok": False, "error": "apply_transform: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_join_objects_main(payload):
    """主线程：合并多个 MESH 物体为一个"""
    names = payload.get("names") or []
    target_name = (payload.get("target_name") or "").strip()
    if not names or len(names) < 2:
        return {"ok": False, "error": "names 至少需要 2 个物体名"}
    objs = []
    for n in names:
        o = bpy.data.objects.get(n)
        if not o:
            return {"ok": False, "error": "物体不存在: %s" % n}
        if o.type != 'MESH':
            return {"ok": False, "error": "物体必须是 MESH 类型: %s" % n}
        objs.append(o)
    try:
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        active = bpy.data.objects.get(target_name) if target_name else objs[0]
        if not active:
            active = objs[0]
        bpy.context.view_layer.objects.active = active
        bpy.ops.object.join()
        result_name = bpy.context.active_object.name
        return {"ok": True, "data": {"name": result_name, "joined_count": len(names)}}
    except Exception as e:
        return {"ok": False, "error": "join_objects: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_set_dimensions_main(payload):
    """主线程：设置物体的精确尺寸（米）"""
    name = (payload.get("name") or "").strip()
    dimensions = payload.get("dimensions") or []
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    if not dimensions or len(dimensions) != 3:
        return {"ok": False, "error": "dimensions 必须是 [x, y, z] 三元素列表（米）"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        current_dims = obj.dimensions
        for i, d in enumerate(dimensions):
            if d and float(d) > 0 and current_dims[i] > 0:
                obj.scale[i] *= float(d) / current_dims[i]
        bpy.ops.object.transform_apply(scale=True)
        return {"ok": True, "data": {"name": obj.name, "dimensions": list(obj.dimensions)}}
    except Exception as e:
        return {"ok": False, "error": "set_dimensions: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_mirror_modifier_main(payload):
    """主线程：添加镜像修改器"""
    name = (payload.get("name") or "").strip()
    axis_x = bool(payload.get("axis_x", True))
    axis_y = bool(payload.get("axis_y", False))
    axis_z = bool(payload.get("axis_z", False))
    use_clip = bool(payload.get("use_clip", True))
    merge_threshold = float(payload.get("merge_threshold") or 0.001)
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Mirror", type='MIRROR')
        mod.use_axis[0] = axis_x
        mod.use_axis[1] = axis_y
        mod.use_axis[2] = axis_z
        mod.use_clip = use_clip
        mod.merge_threshold = merge_threshold
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name,
                                      "axis": [axis_x, axis_y, axis_z]}}
    except Exception as e:
        return {"ok": False, "error": "add_mirror_modifier: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_solidify_modifier_main(payload):
    """主线程：添加实体化修改器（给平面/薄壁增加厚度）"""
    name = (payload.get("name") or "").strip()
    thickness = float(payload.get("thickness") or 0.1)
    offset = float(payload.get("offset") or -1.0)
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
        mod.thickness = thickness
        mod.offset = offset
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name,
                                      "thickness": thickness}}
    except Exception as e:
        return {"ok": False, "error": "add_solidify_modifier: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_array_modifier_main(payload):
    """主线程：添加阵列修改器（复制并按偏移排列）"""
    name = (payload.get("name") or "").strip()
    count = int(payload.get("count") or 3)
    offset_x = float(payload.get("offset_x") or 0.0)
    offset_y = float(payload.get("offset_y") or 0.0)
    offset_z = float(payload.get("offset_z") or 0.0)
    relative = bool(payload.get("relative", True))
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    if count < 1 or count > 100:
        return {"ok": False, "error": "count 必须在 1~100 之间"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Array", type='ARRAY')
        mod.count = count
        if relative:
            mod.use_relative_offset = True
            mod.use_constant_offset = False
            rx = offset_x if (offset_x != 0 or offset_y != 0 or offset_z != 0) else 1.0
            mod.relative_offset_displace[0] = rx
            mod.relative_offset_displace[1] = offset_y
            mod.relative_offset_displace[2] = offset_z
        else:
            mod.use_relative_offset = False
            mod.use_constant_offset = True
            mod.constant_offset_displace[0] = offset_x
            mod.constant_offset_displace[1] = offset_y
            mod.constant_offset_displace[2] = offset_z
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name, "count": count}}
    except Exception as e:
        return {"ok": False, "error": "add_array_modifier: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_set_shade_type_main(payload):
    """主线程：设置物体着色方式（SMOOTH 或 FLAT）"""
    name = (payload.get("name") or "").strip()
    shade_type = (payload.get("shade_type") or "SMOOTH").upper()
    if shade_type not in ("SMOOTH", "FLAT"):
        return {"ok": False, "error": "shade_type 必须是 SMOOTH 或 FLAT"}
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH':
        return {"ok": False, "error": "物体必须是 MESH 类型"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        if shade_type == 'SMOOTH':
            bpy.ops.object.shade_smooth()
        else:
            bpy.ops.object.shade_flat()
        return {"ok": True, "data": {"name": obj.name, "shade_type": shade_type}}
    except Exception as e:
        return {"ok": False, "error": "set_shade_type: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_uv_unwrap_main(payload):
    """主线程：UV 展开"""
    name = (payload.get("name") or "").strip()
    method = (payload.get("method") or "smart").lower()
    if method not in ("smart", "unwrap", "cube", "sphere", "cylinder"):
        method = "smart"
    island_margin = float(payload.get("island_margin") or 0.02)
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH':
        return {"ok": False, "error": "物体必须是 MESH 类型"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        if method == "smart":
            bpy.ops.uv.smart_project(island_margin=island_margin)
        elif method == "unwrap":
            bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=island_margin)
        elif method == "cube":
            bpy.ops.uv.cube_project()
        elif method == "sphere":
            bpy.ops.uv.sphere_project()
        elif method == "cylinder":
            bpy.ops.uv.cylinder_project()
        bpy.ops.object.mode_set(mode='OBJECT')
        return {"ok": True, "data": {"name": obj.name, "method": method}}
    except Exception as e:
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception:
            pass
        return {"ok": False, "error": "uv_unwrap: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_set_parent_main(payload):
    """主线程：设置父子关系"""
    parent_name = (payload.get("parent_name") or "").strip()
    child_name = (payload.get("child_name") or "").strip()
    keep_transform = bool(payload.get("keep_transform", True))
    if not parent_name or not child_name:
        return {"ok": False, "error": "parent_name 和 child_name 都不能为空"}
    parent = bpy.data.objects.get(parent_name)
    child = bpy.data.objects.get(child_name)
    if not parent:
        return {"ok": False, "error": "父物体不存在: %s" % parent_name}
    if not child:
        return {"ok": False, "error": "子物体不存在: %s" % child_name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        child.select_set(True)
        parent.select_set(True)
        bpy.context.view_layer.objects.active = parent
        bpy.ops.object.parent_set(type='OBJECT', keep_transform=keep_transform)
        return {"ok": True, "data": {"parent": parent_name, "child": child_name,
                                      "keep_transform": keep_transform}}
    except Exception as e:
        return {"ok": False, "error": "set_parent: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_clear_parent_main(payload):
    """主线程：清除父子关系"""
    name = (payload.get("name") or "").strip()
    keep_transform = bool(payload.get("keep_transform", True))
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        clear_type = 'CLEAR_KEEP_TRANSFORM' if keep_transform else 'CLEAR'
        bpy.ops.object.parent_clear(type=clear_type)
        return {"ok": True, "data": {"name": obj.name, "keep_transform": keep_transform}}
    except Exception as e:
        return {"ok": False, "error": "clear_parent: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_rename_object_main(payload):
    """主线程：重命名物体"""
    name = (payload.get("name") or "").strip()
    new_name = (payload.get("new_name") or "").strip()
    if not name or not new_name:
        return {"ok": False, "error": "name 和 new_name 都不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    old_name = obj.name
    obj.name = new_name
    if obj.data:
        obj.data.name = new_name
    return {"ok": True, "data": {"old_name": old_name, "new_name": obj.name}}


def _mcp_create_collection_main(payload):
    """主线程：创建集合并把物体加入其中"""
    collection_name = (payload.get("collection_name") or "").strip()
    object_names = payload.get("object_names") or []
    parent_collection = (payload.get("parent_collection") or "").strip()
    if not collection_name:
        return {"ok": False, "error": "collection_name 不能为空"}
    try:
        col = bpy.data.collections.get(collection_name)
        if not col:
            col = bpy.data.collections.new(collection_name)
            if parent_collection:
                pc = bpy.data.collections.get(parent_collection)
                if pc:
                    pc.children.link(col)
                else:
                    bpy.context.scene.collection.children.link(col)
            else:
                bpy.context.scene.collection.children.link(col)
        added = []
        for n in object_names:
            obj = bpy.data.objects.get(n)
            if obj and obj.name not in col.objects:
                col.objects.link(obj)
                added.append(n)
        return {"ok": True, "data": {"collection": col.name, "added_objects": added}}
    except Exception as e:
        return {"ok": False, "error": "create_collection: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_set_object_visibility_main(payload):
    """主线程：设置物体可见性（视口/渲染）"""
    name = (payload.get("name") or "").strip()
    hide_viewport = payload.get("hide_viewport")
    hide_render = payload.get("hide_render")
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    if hide_viewport is not None:
        obj.hide_viewport = bool(hide_viewport)
    if hide_render is not None:
        obj.hide_render = bool(hide_render)
    return {"ok": True, "data": {"name": obj.name,
                                  "hide_viewport": obj.hide_viewport,
                                  "hide_render": obj.hide_render}}


def _mcp_set_custom_property_main(payload):
    """主线程：在物体上设置自定义属性"""
    name = (payload.get("name") or "").strip()
    prop_name = (payload.get("prop_name") or "").strip()
    prop_value = payload.get("prop_value")
    if not name or not prop_name:
        return {"ok": False, "error": "name 和 prop_name 都不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    obj[prop_name] = prop_value
    return {"ok": True, "data": {"name": obj.name, "prop": prop_name, "value": prop_value}}


def _mcp_add_empty_main(payload):
    """主线程：添加空物体（Empty）"""
    name = (payload.get("name") or "Empty").strip()
    location = payload.get("location") or [0, 0, 0]
    empty_type = (payload.get("empty_type") or "PLAIN_AXES").upper()
    size = float(payload.get("size") or 1.0)
    valid_types = ["PLAIN_AXES", "ARROWS", "SINGLE_ARROW", "CIRCLE",
                   "CUBE", "SPHERE", "CONE", "IMAGE"]
    if empty_type not in valid_types:
        empty_type = "PLAIN_AXES"
    try:
        loc = (float(location[0]), float(location[1]), float(location[2]))
        bpy.ops.object.empty_add(type=empty_type, location=loc)
        obj = bpy.context.active_object
        obj.name = name
        obj.empty_display_size = size
        return {"ok": True, "data": {"name": obj.name, "type": empty_type,
                                      "location": list(obj.location)}}
    except Exception as e:
        return {"ok": False, "error": "add_empty: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_decimate_modifier_main(payload):
    """主线程：添加精简修改器（减面）"""
    name = (payload.get("name") or "").strip()
    ratio = float(payload.get("ratio") or 0.5)
    decimate_type = (payload.get("decimate_type") or "COLLAPSE").upper()
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    if ratio <= 0 or ratio > 1:
        return {"ok": False, "error": "ratio 必须在 (0, 1] 之间"}
    if decimate_type not in ("COLLAPSE", "UNSUBDIV", "DISSOLVE"):
        decimate_type = "COLLAPSE"
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
        mod.decimate_type = decimate_type
        if decimate_type == "COLLAPSE":
            mod.ratio = ratio
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name, "ratio": ratio}}
    except Exception as e:
        return {"ok": False, "error": "add_decimate_modifier: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_displace_modifier_main(payload):
    """主线程：添加置换修改器（用噪点纹理扭曲表面）"""
    name = (payload.get("name") or "").strip()
    strength = float(payload.get("strength") or 0.5)
    mid_level = float(payload.get("mid_level") or 0.5)
    texture_name = (payload.get("texture_name") or "").strip()
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Displace", type='DISPLACE')
        mod.strength = strength
        mod.mid_level = mid_level
        if texture_name:
            tex = bpy.data.textures.get(texture_name)
            if tex:
                mod.texture = tex
        else:
            tex = bpy.data.textures.new("DisplaceNoise", type='CLOUDS')
            tex.noise_scale = 1.0
            mod.texture = tex
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name, "strength": strength}}
    except Exception as e:
        return {"ok": False, "error": "add_displace_modifier: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_lattice_deform_main(payload):
    """主线程：添加晶格变形（Lattice + Lattice modifier）"""
    import mathutils
    name = (payload.get("name") or "").strip()
    points_u = int(payload.get("points_u") or 4)
    points_v = int(payload.get("points_v") or 4)
    points_w = int(payload.get("points_w") or 4)
    scale_factor = float(payload.get("scale_factor") or 1.2)
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bbox_corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
        min_c = mathutils.Vector((min(c.x for c in bbox_corners),
                                   min(c.y for c in bbox_corners),
                                   min(c.z for c in bbox_corners)))
        max_c = mathutils.Vector((max(c.x for c in bbox_corners),
                                   max(c.y for c in bbox_corners),
                                   max(c.z for c in bbox_corners)))
        center = (min_c + max_c) / 2
        size = (max_c - min_c) * scale_factor
        bpy.ops.object.add(type='LATTICE', location=center)
        lattice_obj = bpy.context.active_object
        lattice_obj.name = name + "_Lattice"
        lattice_obj.scale = (max(size.x, 0.01), max(size.y, 0.01), max(size.z, 0.01))
        lat = lattice_obj.data
        lat.points_u = points_u
        lat.points_v = points_v
        lat.points_w = points_w
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Lattice", type='LATTICE')
        mod.object = lattice_obj
        return {"ok": True, "data": {"name": obj.name, "lattice": lattice_obj.name,
                                      "modifier": mod.name}}
    except Exception as e:
        return {"ok": False, "error": "add_lattice_deform: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_screw_modifier_main(payload):
    """主线程：添加螺旋修改器（旋转体/螺旋体）"""
    import math
    name = (payload.get("name") or "").strip()
    angle = float(payload.get("angle") or 6.283185)
    screw_offset = float(payload.get("screw_offset") or 0.0)
    steps = int(payload.get("steps") or 32)
    axis = (payload.get("axis") or "Z").upper()
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    if axis not in ("X", "Y", "Z"):
        axis = "Z"
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Screw", type='SCREW')
        mod.angle = angle
        mod.screw_offset = screw_offset
        mod.steps = steps
        mod.axis = axis
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name,
                                      "angle_deg": math.degrees(angle), "axis": axis}}
    except Exception as e:
        return {"ok": False, "error": "add_screw_modifier: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_skin_modifier_main(payload):
    """主线程：添加皮肤修改器"""
    name = (payload.get("name") or "").strip()
    use_smooth_shade = bool(payload.get("use_smooth_shade", True))
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH':
        return {"ok": False, "error": "物体必须是 MESH 类型"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Skin", type='SKIN')
        mod.use_smooth_shade = use_smooth_shade
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name}}
    except Exception as e:
        return {"ok": False, "error": "add_skin_modifier: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_wireframe_modifier_main(payload):
    """主线程：添加线框修改器"""
    name = (payload.get("name") or "").strip()
    thickness = float(payload.get("thickness") or 0.02)
    use_even_offset = bool(payload.get("use_even_offset", True))
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Wireframe", type='WIREFRAME')
        mod.thickness = thickness
        mod.use_even_offset = use_even_offset
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name, "thickness": thickness}}
    except Exception as e:
        return {"ok": False, "error": "add_wireframe_modifier: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_curve_object_main(payload):
    """主线程：添加曲线物体（Bezier / NURBS / Path）"""
    name = (payload.get("name") or "Curve").strip()
    curve_type = (payload.get("curve_type") or "BEZIER").upper()
    location = payload.get("location") or [0, 0, 0]
    if curve_type not in ("BEZIER", "NURBS", "PATH"):
        curve_type = "BEZIER"
    try:
        loc = (float(location[0]), float(location[1]), float(location[2]))
        if curve_type == "PATH":
            bpy.ops.curve.primitive_nurbs_path_add(location=loc)
        elif curve_type == "NURBS":
            bpy.ops.curve.primitive_nurbs_curve_add(location=loc)
        else:
            bpy.ops.curve.primitive_bezier_curve_add(location=loc)
        obj = bpy.context.active_object
        obj.name = name
        return {"ok": True, "data": {"name": obj.name, "curve_type": curve_type,
                                      "location": list(obj.location)}}
    except Exception as e:
        return {"ok": False, "error": "add_curve_object: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_set_material_nodes_main(payload):
    """主线程：用 Principled BSDF 节点方式设置材质（Blender 4.2+ 兼容）"""
    name = (payload.get("name") or "").strip()
    material_name = (payload.get("material_name") or "").strip()
    base_color = payload.get("base_color") or [0.8, 0.8, 0.8, 1.0]
    metallic = float(payload.get("metallic") or 0.0)
    roughness = float(payload.get("roughness") or 0.5)
    specular = float(payload.get("specular") or 0.5)
    emission_color = payload.get("emission_color")
    emission_strength = float(payload.get("emission_strength") or 0.0)
    alpha = float(payload.get("alpha") or 1.0)
    ior = float(payload.get("ior") or 1.45)
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    try:
        mat_name = material_name or ("Mat_" + name)
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        output = nodes.new('ShaderNodeOutputMaterial')
        bsdf.location = (0, 0)
        output.location = (300, 0)
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        c = base_color
        bsdf.inputs['Base Color'].default_value = (
            float(c[0]), float(c[1]), float(c[2]),
            float(c[3]) if len(c) > 3 else 1.0)
        bsdf.inputs['Metallic'].default_value = metallic
        bsdf.inputs['Roughness'].default_value = roughness
        for sp_key in ('Specular IOR Level', 'Specular'):
            try:
                bsdf.inputs[sp_key].default_value = specular
                break
            except (KeyError, Exception):
                pass
        try:
            bsdf.inputs['IOR'].default_value = ior
        except (KeyError, Exception):
            pass
        if alpha < 1.0:
            bsdf.inputs['Alpha'].default_value = alpha
            mat.blend_method = 'BLEND'
        if emission_color and emission_strength > 0:
            ec = emission_color
            for em_key in ('Emission Color', 'Emission'):
                try:
                    bsdf.inputs[em_key].default_value = (float(ec[0]), float(ec[1]), float(ec[2]), 1.0)
                    break
                except (KeyError, Exception):
                    pass
            try:
                bsdf.inputs['Emission Strength'].default_value = emission_strength
            except (KeyError, Exception):
                pass
        if obj.data and hasattr(obj.data, 'materials'):
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
        return {"ok": True, "data": {"name": obj.name, "material": mat.name,
                                      "metallic": metallic, "roughness": roughness}}
    except Exception as e:
        return {"ok": False, "error": "set_material_nodes: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_add_subdivision_and_sculpt_main(payload):
    """主线程：添加多分辨率修改器（Multires，雕刻专用）"""
    name = (payload.get("name") or "").strip()
    levels = int(payload.get("levels") or 3)
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    if levels > 6:
        return {"ok": False, "error": "levels 不能超过 6"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    if obj.type != 'MESH':
        return {"ok": False, "error": "物体必须是 MESH 类型"}
    try:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new(name="Multires", type='MULTIRES')
        for _ in range(levels):
            bpy.ops.object.multires_subdivide(modifier=mod.name, mode='CATMULL_CLARK')
        return {"ok": True, "data": {"name": obj.name, "modifier": mod.name, "levels": levels}}
    except Exception as e:
        return {"ok": False, "error": "add_subdivision_and_sculpt: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_align_objects_main(payload):
    """主线程：对齐多个物体"""
    names = payload.get("names") or []
    axis = (payload.get("axis") or "X").upper()
    align_mode = (payload.get("align_mode") or "first").lower()
    align_value = payload.get("align_value")
    if not names:
        return {"ok": False, "error": "names 不能为空"}
    if axis not in ("X", "Y", "Z"):
        return {"ok": False, "error": "axis 必须是 X / Y / Z"}
    objs = []
    for n in names:
        o = bpy.data.objects.get(n)
        if not o:
            return {"ok": False, "error": "物体不存在: %s" % n}
        objs.append(o)
    try:
        axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
        if align_value is not None:
            target = float(align_value)
        elif align_mode == "first":
            target = objs[0].location[axis_idx]
        elif align_mode == "min":
            target = min(o.location[axis_idx] for o in objs)
        elif align_mode == "max":
            target = max(o.location[axis_idx] for o in objs)
        elif align_mode == "center":
            target = sum(o.location[axis_idx] for o in objs) / len(objs)
        else:
            target = objs[0].location[axis_idx]
        for o in objs:
            loc = list(o.location)
            loc[axis_idx] = target
            o.location = loc
        return {"ok": True, "data": {"aligned_count": len(objs), "axis": axis, "target_value": target}}
    except Exception as e:
        return {"ok": False, "error": "align_objects: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_distribute_objects_main(payload):
    """主线程：均匀分布多个物体"""
    names = payload.get("names") or []
    axis = (payload.get("axis") or "X").upper()
    spacing = payload.get("spacing")
    start_value = payload.get("start_value")
    if not names or len(names) < 2:
        return {"ok": False, "error": "names 至少需要 2 个物体名"}
    if axis not in ("X", "Y", "Z"):
        return {"ok": False, "error": "axis 必须是 X / Y / Z"}
    objs = []
    for n in names:
        o = bpy.data.objects.get(n)
        if not o:
            return {"ok": False, "error": "物体不存在: %s" % n}
        objs.append(o)
    try:
        axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
        cnt = len(objs)
        if spacing is not None:
            sp = float(spacing)
            start = float(start_value) if start_value is not None else objs[0].location[axis_idx]
        else:
            positions = sorted([o.location[axis_idx] for o in objs])
            start = positions[0]
            end_val = positions[-1]
            sp = (end_val - start) / (cnt - 1) if cnt > 1 else 1.0
        for i, o in enumerate(objs):
            loc = list(o.location)
            loc[axis_idx] = start + i * sp
            o.location = loc
        return {"ok": True, "data": {"distributed_count": cnt, "axis": axis, "spacing": sp}}
    except Exception as e:
        return {"ok": False, "error": "distribute_objects: %s" % e, "traceback": traceback.format_exc(limit=4)}


def _mcp_get_modifier_list_main(payload):
    """主线程：获取物体的所有修改器列表"""
    name = (payload.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "name 不能为空"}
    obj = bpy.data.objects.get(name)
    if not obj:
        return {"ok": False, "error": "物体不存在: %s" % name}
    modifiers = [{"name": mod.name, "type": mod.type,
                  "show_viewport": mod.show_viewport,
                  "show_render": mod.show_render}
                 for mod in obj.modifiers]
    return {"ok": True, "data": {"name": obj.name, "modifiers": modifiers, "count": len(modifiers)}}


def _mcp_set_render_settings_main(payload):
    """主线程：设置渲染参数"""
    engine = (payload.get("engine") or "").upper()
    resolution_x = payload.get("resolution_x")
    resolution_y = payload.get("resolution_y")
    samples = payload.get("samples")
    output_format = (payload.get("output_format") or "").upper()
    resolution_percentage = payload.get("resolution_percentage")
    film_transparent = payload.get("film_transparent")
    scene = bpy.context.scene
    render = scene.render
    changes = {}
    if engine in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
        render.engine = engine
        changes["engine"] = engine
    if resolution_x:
        render.resolution_x = int(resolution_x)
        changes["resolution_x"] = render.resolution_x
    if resolution_y:
        render.resolution_y = int(resolution_y)
        changes["resolution_y"] = render.resolution_y
    if resolution_percentage:
        render.resolution_percentage = int(resolution_percentage)
        changes["resolution_percentage"] = render.resolution_percentage
    if samples is not None:
        if render.engine == 'CYCLES':
            scene.cycles.samples = int(samples)
            changes["cycles_samples"] = int(samples)
        else:
            try:
                scene.eevee.taa_render_samples = int(samples)
                changes["eevee_samples"] = int(samples)
            except AttributeError:
                pass
    if output_format in ("PNG", "JPEG", "OPEN_EXR", "TIFF"):
        render.image_settings.file_format = output_format
        changes["output_format"] = output_format
    if film_transparent is not None:
        render.film_transparent = bool(film_transparent)
        changes["film_transparent"] = bool(film_transparent)
    return {"ok": True, "data": {"changed": changes, "current_engine": render.engine}}


# ============================================================
# MCP 主线程任务路由表（_drain_queue 用）
# ============================================================
MCP_MAIN_HANDLERS = {
    # v3.5.0 新增：30 个高精度建模工具路由
    "set_origin": _mcp_set_origin_main,
    "apply_transform": _mcp_apply_transform_main,
    "join_objects": _mcp_join_objects_main,
    "set_dimensions": _mcp_set_dimensions_main,
    "add_mirror_modifier": _mcp_add_mirror_modifier_main,
    "add_solidify_modifier": _mcp_add_solidify_modifier_main,
    "add_array_modifier": _mcp_add_array_modifier_main,
    "set_shade_type": _mcp_set_shade_type_main,
    "uv_unwrap": _mcp_uv_unwrap_main,
    "set_parent": _mcp_set_parent_main,
    "clear_parent": _mcp_clear_parent_main,
    "rename_object": _mcp_rename_object_main,
    "create_collection": _mcp_create_collection_main,
    "set_object_visibility": _mcp_set_object_visibility_main,
    "set_custom_property": _mcp_set_custom_property_main,
    "add_empty": _mcp_add_empty_main,
    "add_decimate_modifier": _mcp_add_decimate_modifier_main,
    "add_displace_modifier": _mcp_add_displace_modifier_main,
    "add_lattice_deform": _mcp_add_lattice_deform_main,
    "add_screw_modifier": _mcp_add_screw_modifier_main,
    "add_skin_modifier": _mcp_add_skin_modifier_main,
    "add_wireframe_modifier": _mcp_add_wireframe_modifier_main,
    "add_curve_object": _mcp_add_curve_object_main,
    "set_material_nodes": _mcp_set_material_nodes_main,
    "add_subdivision_and_sculpt": _mcp_add_subdivision_and_sculpt_main,
    "align_objects": _mcp_align_objects_main,
    "distribute_objects": _mcp_distribute_objects_main,
    "get_modifier_list": _mcp_get_modifier_list_main,
    "set_render_settings": _mcp_set_render_settings_main,
    # v3.4.5 新增 10 个高可操控性工具
    "smart_uv_project": _mcp_smart_uv_project_main,
    "add_modifier": _mcp_add_modifier_main,
    "parent_objects": _mcp_parent_objects_main,
    "snap_to_ground": _mcp_snap_to_ground_main,
    "duplicate_object": _mcp_duplicate_object_main,
    "apply_modifier": _mcp_apply_modifier_main,
    "separate_by_material": _mcp_separate_by_material_main,
    "render_image": _mcp_render_image_main,
    "render_layers": _mcp_render_layers_main,
    "render_layers": _mcp_render_layers_main,
    "set_world": _mcp_set_world_main,
    "set_vertex_color": _mcp_set_vertex_color_main,
    # v3.5.0 新增布尔/细分工具
    "boolean_union": _mcp_boolean_union_main,
    "boolean_difference": _mcp_boolean_difference_main,
    "boolean_intersect": _mcp_boolean_intersect_main,
    "add_subdivision": _mcp_add_subdivision_main,
    "add_bevel": _mcp_add_bevel_main,
    "smart_smooth": _mcp_smart_smooth_main,
    # 原有工具
    "get_scene_info": _mcp_get_scene_info_main,
    "get_object_info": _mcp_get_object_info_main,
    "list_objects": _mcp_list_objects_main,
    "add_primitive": _mcp_add_primitive_main,
    "add_light": _mcp_add_light_main,
    "set_camera": _mcp_set_camera_main,
    "update_object": _mcp_update_object_main,
    "set_material": _mcp_set_material_main,
    "delete_object": _mcp_delete_object_main,
    "clear_scene": _mcp_clear_scene_main,
    "exec_python": _mcp_exec_python_main,
    "quality_check": _mcp_quality_check_main,
    # v2.1.0 Phase F：场景 overview + 软回滚
    "blend_summary": _mcp_blend_summary_main,
    "bookmark_state": _mcp_bookmark_state_main,
    "restore_state": _mcp_restore_state_main,
    # v3.6.0：多角度截图
    "multi_angle_screenshot": _multi_angle_screenshot_main,
}


# ============================================================
# MCP Tools Schema（OpenAI function tools 格式，用于 /mcp/tools 端点）
# ----------------------------------------------------------------
# 每条：{name, description, parameters: {type:object, properties:{}, required:[]}, _route}
# _route：
#   'main'  → _post_to_main 主线程
#   'thread'→ handler 线程直接跑
#   'mixed' → 先 handler 线程下载再主线程 import
# ============================================================
MCP_TOOLS = [
    # ---------- 观察 ----------
    {
        "name": "get_scene_info",
        "description": "获取当前 Blender 场景的完整快照（物体列表/坐标/材质/灯光/相机/渲染设置）。每次决定下一步操作前都应该先调用此工具看清当前真实状态。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_object_info",
        "description": "获取单个物体的详细信息（位置/旋转/缩放/材质槽/网格统计/世界 bbox）。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名（区分大小写）"},
        }, "required": ["name"]},
    },
    {
        "name": "list_objects",
        "description": "列出所有物体（精简版：仅 name/type/location）。可按 type 过滤（MESH/LIGHT/CAMERA/EMPTY）。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "type": {"type": "string", "description": "过滤类型，留空返回全部"},
        }, "required": []},
    },
    {
        "name": "get_viewport_screenshot",
        "description": "截取当前 3D 视口截图，返回 base64 PNG。用于让 AI 用视觉确认场景效果。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "max_size": {"type": "integer", "description": "最大边长（像素），默认 800", "default": 800},
        }, "required": []},
    },
    # ---------- 创建 ----------
    {
        "name": "add_primitive",
        "description": "添加基本几何体（cube/sphere/cylinder/cone/plane/torus/ico_sphere/monkey）。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["cube","sphere","ico_sphere","cylinder","cone","plane","torus","monkey"]},
            "location": {"type": "array", "items": {"type": "number"}, "description": "[x,y,z] 世界坐标，默认 [0,0,0]"},
            "rotation": {"type": "array", "items": {"type": "number"}, "description": "[rx,ry,rz] 欧拉角弧度"},
            "scale": {"description": "数字或 [sx,sy,sz]"},
            "name": {"type": "string", "description": "可选自定义物体名"},
        }, "required": ["type"]},
    },
    {
        "name": "add_light",
        "description": "添加灯光（POINT/SUN/SPOT/AREA）。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["POINT","SUN","SPOT","AREA"]},
            "location": {"type": "array", "items": {"type": "number"}},
            "energy": {"type": "number", "description": "功率（W），SUN 通常 5~10，POINT 通常 500~2000"},
            "color": {"type": "array", "items": {"type": "number"}, "description": "[r,g,b] 0~1"},
            "name": {"type": "string"},
        }, "required": ["type"]},
    },
    {
        "name": "set_camera",
        "description": "创建或更新场景相机（自动设为 active）。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "location": {"type": "array", "items": {"type": "number"}},
            "rotation": {"type": "array", "items": {"type": "number"}, "description": "欧拉角弧度"},
            "lens": {"type": "number", "description": "焦距 mm，默认 50"},
            "name": {"type": "string"},
        }, "required": []},
    },
    # ---------- 修改 ----------
    {
        "name": "update_object",
        "description": "修改物体的位置/旋转/缩放/可见性（只传需要改的字段即可）。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "location": {"type": "array", "items": {"type": "number"}},
            "rotation": {"type": "array", "items": {"type": "number"}},
            "scale": {"description": "数字或 [sx,sy,sz]"},
            "visible": {"type": "boolean"},
        }, "required": ["name"]},
    },
    {
        "name": "set_material",
        "description": "给物体设置 Principled BSDF 材质参数。已有材质就改，没有就新建。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "obj_name": {"type": "string"},
            "base_color": {"type": "array", "items": {"type": "number"}, "description": "[r,g,b] 或 [r,g,b,a] 0~1"},
            "roughness": {"type": "number", "description": "0~1"},
            "metallic": {"type": "number", "description": "0~1"},
            "emission_color": {"type": "array", "items": {"type": "number"}},
            "emission_strength": {"type": "number"},
        }, "required": ["obj_name"]},
    },
    {
        "name": "delete_object",
        "description": "删除指定物体。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
        }, "required": ["name"]},
    },
    {
        "name": "clear_scene",
        "description": "清空场景物体。默认保留相机和灯光。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "keep_camera": {"type": "boolean", "default": True},
            "keep_lights": {"type": "boolean", "default": True},
        }, "required": []},
    },
    # ---------- 兜底 ----------
    {
        "name": "exec_python",
        "description": "兜底：执行任意 Blender Python 代码（仅在没有合适的原子工具时使用）。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Python 代码"},
        }, "required": ["code"]},
    },
    {
        "name": "quality_check",
        "description": "对场景做 4 维度自检（相机/灯光/世界背景/网格数），返回结构化 issues 列表（不抛错）。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    # ---------- v3.5.0 新增布尔/细分工具 ----------
    {
        "name": "boolean_union",
        "description": "布尔并集：将 target 和 cutter 两个物体合并为一个（cutter 被删除）。用于创建复杂形状如 L 形 / 门洞。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "target_name": {"type": "string", "description": "目标物体名（被保留）"},
            "tool_name": {"type": "string", "description": "工具物体名（会被删除并合并）"},
        }, "required": ["target_name", "tool_name"]},
    },
    {
        "name": "boolean_difference",
        "description": "布尔差集：从 target 减去 cutter 部分（cutter 被删除）。用于创建门洞/窗洞/雕刻。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "target_name": {"type": "string", "description": "目标物体名（被挖空）"},
            "tool_name": {"type": "string", "description": "工具物体名（会被删除）"},
        }, "required": ["target_name", "tool_name"]},
    },
    {
        "name": "boolean_intersect",
        "description": "布尔交集：只保留 target 和 cutter 的重叠部分（cutter 被删除）。用于提取复杂形状的交叉区域。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "target_name": {"type": "string", "description": "目标物体名（被保留）"},
            "tool_name": {"type": "string", "description": "工具物体名（会被删除）"},
        }, "required": ["target_name", "tool_name"]},
    },
    {
        "name": "add_subdivision",
        "description": "添加细分曲面修改器（Catmull-Clark），使物体更平滑。levels 不能超过 5。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
            "levels": {"type": "integer", "description": "视口细分层级（1-5），默认 2"},
            "render_levels": {"type": "integer", "description": "渲染细分层级，默认比 levels 高 1"},
        }, "required": ["name"]},
    },
    {
        "name": "add_bevel",
        "description": "添加倒角修改器（Blender 4.2+ 兼容，affect='EDGES' 而非 vertex_only=True）。用于圆滑边缘。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
            "width": {"type": "number", "description": "倒角宽度，默认 0.05"},
            "segments": {"type": "integer", "description": "倒角段数，默认 3"},
            "affect": {"type": "string", "enum": ["EDGES", "VERTICES"], "description": "影响边或顶点，默认 EDGES"},
        }, "required": ["name"]},
    },
    {
        "name": "smart_smooth",
        "description": "智能平滑：自动设置法线平滑和 auto_smooth_angle，使物体表面光滑无棱角。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
            "angle_limit": {"type": "number", "description": "角度阈值（度），默认 30"},
        }, "required": ["name"]},
    },
    # ---------- v3.4.5 新增 10 个高可操控性工具 ----------
    {
        "name": "smart_uv_project",
        "description": "智能 UV 投射（smart/cube/cylinder/sphere），PBR 贴图的前置步骤。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
            "method": {"type": "string", "enum": ["smart","cube","cylinder","sphere"], "description": "投射方式，默认 smart"},
            "island_margin": {"type": "number", "description": "岛间距，默认 0.02"},
            "angle_limit": {"type": "number", "description": "角度限制（度），默认 66"},
        }, "required": ["name"]},
    },
    {
        "name": "add_modifier",
        "description": "通用修改器添加（Array/Mirror/Solidify/SimpleDeform/Shrinkwrap/Wireframe/Displace/Cast/Remesh/Screw/Skin/Triangulate/Weld/Curve/EdgeSplit）。比 exec_python 稳，不用切 edit mode。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
            "modifier_type": {"type": "string", "enum": ["ARRAY","MIRROR","SOLIDIFY","SIMPLE_DEFORM","SHRINKWRAP","WIREFRAME","DISPLACE","CAST","LATTICE","REMESH","SCREW","SKIN","TRIANGULATE","WELD","CURVE","EDGE_SPLIT"], "description": "修改器类型（大写）"},
            "properties": {"type": "object", "description": "修改器属性字典，如 {\"count\":4, \"relative_offset_displace\":[1.5,0,0]} 用于 ARRAY"},
        }, "required": ["name", "modifier_type"]},
    },
    {
        "name": "parent_objects",
        "description": "设置父子关系（把多个 children 挂到一个 parent 下面）。组合装配的基础。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "parent_name": {"type": "string", "description": "父物体名"},
            "children_names": {"type": "array", "items": {"type": "string"}, "description": "子物体名数组"},
            "keep_transform": {"type": "boolean", "description": "是否保持子物体世界坐标不变（默认 true）"},
        }, "required": ["parent_name", "children_names"]},
    },
    {
        "name": "snap_to_ground",
        "description": "自动贴地：计算物体世界坐标 bbox 最低点，把它对齐到 Z=target_z（默认 0）。治穿地/飘空。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
            "target_z": {"type": "number", "description": "目标 Z 坐标，默认 0（地面）"},
        }, "required": ["name"]},
    },
    {
        "name": "duplicate_object",
        "description": "复制物体（独立副本或链接副本），可选设新位置。比 exec_python 更安全。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "要复制的物体名"},
            "new_name": {"type": "string", "description": "新物体名"},
            "linked": {"type": "boolean", "description": "是否链接副本（共享 mesh 数据），默认 false"},
            "location": {"type": "array", "items": {"type": "number"}, "description": "新位置 [x,y,z]"},
        }, "required": ["name"]},
    },
    {
        "name": "apply_modifier",
        "description": "应用修改器（把 modifier 结果固化到 mesh）。布尔运算后或需要导出时常用。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
            "modifier_name": {"type": "string", "description": "要应用的修改器名"},
            "apply_all": {"type": "boolean", "description": "是否应用全部修改器（true 时忽略 modifier_name）"},
        }, "required": ["name"]},
    },
    {
        "name": "separate_by_material",
        "description": "按材质拆分物体：一个 mesh 上有多种材质时拆成多个独立物体。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
        }, "required": ["name"]},
    },
    {
        "name": "render_layers",
        "description": "【v3.8.1 分层渲染 ⭐ 摄影合成】把当前相机视角分层渲染输出到一个目录：env(环境·8bit RGBA) + depth(深度·16bit归一化,近浅远深) + shadow(AO接触暗部·16bit,引擎不支持时自动省略)。供导入 PS 贴自备人物：depth 控前后遮挡/加雾景深，shadow 画接触阴影。EEVEE Next 引擎。场景搭完后调用。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "output_dir": {"type": "string", "description": "输出目录（留空自动建临时目录）"},
            "resolution_x": {"type": "integer", "description": "宽度，默认 1920"},
            "resolution_y": {"type": "integer", "description": "高度，默认 1080"},
            "samples": {"type": "integer", "description": "EEVEE 采样数，默认 64"},
            "transparent": {"type": "boolean", "description": "环境层透明底(RGBA)，默认 true"},
        }, "required": []},
    },
    {
        "name": "render_image",
        "description": "渲染当前相机视角为 PNG 图片，保存到指定路径。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "output_path": {"type": "string", "description": "输出文件路径（留空自动保存到临时目录）"},
            "resolution_x": {"type": "integer", "description": "宽度，默认 1920"},
            "resolution_y": {"type": "integer", "description": "高度，默认 1080"},
            "samples": {"type": "integer", "description": "EEVEE 采样数，默认 64"},
        }, "required": []},
    },
    {
        "name": "render_layers",
        "description": "【分层渲染 ⭐ 摄影合成专用】渲染当前相机视角，一次输出三层 PNG 到 output_dir，供 PS 合成自备人物：env=环境成品(8bit,默认透明底) / depth=归一化深度(16bit,近浅远深,控制前后遮挡和雾) / shadow=AO接触暗部(16bit)。用 EEVEE Next。⚠️会重建 scene 合成器节点树。场景搭完、相机定好后调它出最终交付层。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "output_dir": {"type": "string", "description": "输出目录（留空自动到临时目录）。建议传 workspace 子目录，如 ~/Desktop/ai-chat-workspace/<session>/layers"},
            "resolution_x": {"type": "integer", "description": "宽度，默认 1920"},
            "resolution_y": {"type": "integer", "description": "高度，默认 1080"},
            "samples": {"type": "integer", "description": "EEVEE 采样数，默认 64"},
            "transparent": {"type": "boolean", "description": "环境层是否透明底（默认 true，方便 PS 单独处理环境）"},
        }, "required": []},
    },
    {
        "name": "set_world",
        "description": "设置世界背景（颜色和强度）。不用写 exec_python。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "color": {"type": "array", "items": {"type": "number"}, "description": "[R,G,B] 或 [R,G,B,A] 0~1"},
            "strength": {"type": "number", "description": "背景强度（0~2，室内 0.3~0.8，户外 1.0~1.5）"},
        }, "required": []},
    },
    {
        "name": "set_vertex_color",
        "description": "给物体添加顶点色图层并用指定颜色填充全部顶点。简单上色无需贴图。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "物体名"},
            "color": {"type": "array", "items": {"type": "number"}, "description": "[R,G,B] 或 [R,G,B,A] 0~1"},
            "layer_name": {"type": "string", "description": "顶点色图层名，默认 Color"},
        }, "required": ["name"]},
    },
    # ---------- v3.5.0 新增：29 个高精度建模工具 schema ----------
    {"name": "set_origin", "description": "设置物体原点。ORIGIN_GEOMETRY=几何中心, ORIGIN_CURSOR=3D 光标, ORIGIN_CENTER_OF_MASS=质量中心。布尔运算前必须统一原点。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "物体名"}, "origin_type": {"type": "string", "enum": ["GEOMETRY_ORIGIN","ORIGIN_GEOMETRY","ORIGIN_CURSOR","ORIGIN_CENTER_OF_MASS","ORIGIN_CENTER_OF_VOLUME"], "description": "默认 ORIGIN_GEOMETRY"}}, "required": ["name"]}},
    {"name": "apply_transform", "description": "应用物体变换（把位置/旋转/缩放固化到 mesh 数据，scale 变 1,1,1）。布尔运算前必须先 apply_scale。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "apply_location": {"type": "boolean", "description": "默认 false"}, "apply_rotation": {"type": "boolean", "description": "默认 true"}, "apply_scale": {"type": "boolean", "description": "默认 true ⭐"}}, "required": ["name"]}},
    {"name": "join_objects", "description": "合并多个 MESH 物体为一个。names 里所有物体合并，结果保留 target_name 的名字。", "_route": "main",
     "parameters": {"type": "object", "properties": {"names": {"type": "array", "items": {"type": "string"}, "description": ">=2 个物体名"}, "target_name": {"type": "string", "description": "合并结果保留此名"}}, "required": ["names"]}},
    {"name": "set_dimensions", "description": "设置物体精确尺寸（米）。dimensions=[x,y,z]，0 跳过该轴。自动 apply_scale。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "dimensions": {"type": "array", "items": {"type": "number"}, "description": "[x,y,z] 米"}}, "required": ["name", "dimensions"]}},
    {"name": "add_mirror_modifier", "description": "添加镜像修改器。默认 X 轴，use_clip 防穿过中心。建对称物体必备。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "axis_x": {"type": "boolean", "description": "默认 true"}, "axis_y": {"type": "boolean"}, "axis_z": {"type": "boolean"}, "use_clip": {"type": "boolean", "description": "默认 true"}, "merge_threshold": {"type": "number", "description": "默认 0.001"}}, "required": ["name"]}},
    {"name": "add_solidify_modifier", "description": "添加实体化修改器。给平面增加厚度（墙壁/窗框）。offset: -1=向内,0=居中,1=向外。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "thickness": {"type": "number", "description": "厚度（米），默认 0.1"}, "offset": {"type": "number", "description": "默认 -1"}}, "required": ["name"]}},
    {"name": "add_array_modifier", "description": "添加阵列修改器。沿轴复制 N 份。relative=true 时 offset 相对物体尺寸。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "count": {"type": "integer", "description": "默认 3"}, "offset_x": {"type": "number"}, "offset_y": {"type": "number"}, "offset_z": {"type": "number"}, "relative": {"type": "boolean", "description": "默认 true"}}, "required": ["name", "count"]}},
    {"name": "set_shade_type", "description": "设置着色方式：SMOOTH（曲面）/ FLAT（硬边）。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "shade_type": {"type": "string", "enum": ["SMOOTH","FLAT"], "description": "默认 SMOOTH"}}, "required": ["name"]}},
    {"name": "uv_unwrap", "description": "UV 展开：smart/unwrap/cube/sphere/cylinder。PBR 贴图前必须先展 UV。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "method": {"type": "string", "enum": ["smart","unwrap","cube","sphere","cylinder"], "description": "默认 smart"}, "island_margin": {"type": "number", "description": "默认 0.02"}}, "required": ["name"]}},
    {"name": "set_parent", "description": "设置父子关系：child 挂到 parent 下面。keep_transform=true 保持世界坐标不变。", "_route": "main",
     "parameters": {"type": "object", "properties": {"parent_name": {"type": "string"}, "child_name": {"type": "string"}, "keep_transform": {"type": "boolean", "description": "默认 true"}}, "required": ["parent_name", "child_name"]}},
    {"name": "clear_parent", "description": "清除父子关系。keep_transform=true 保持当前位置不变。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "keep_transform": {"type": "boolean", "description": "默认 true"}}, "required": ["name"]}},
    {"name": "rename_object", "description": "重命名物体（同时重命名 mesh 数据）。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string", "description": "当前名"}, "new_name": {"type": "string"}}, "required": ["name", "new_name"]}},
    {"name": "create_collection", "description": "创建集合并把物体加入。用于组织场景层级。", "_route": "main",
     "parameters": {"type": "object", "properties": {"collection_name": {"type": "string"}, "object_names": {"type": "array", "items": {"type": "string"}}, "parent_collection": {"type": "string"}}, "required": ["collection_name"]}},
    {"name": "set_object_visibility", "description": "设置物体可见性。hide_viewport=true 视口隐藏，hide_render=true 渲染隐藏。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "hide_viewport": {"type": "boolean"}, "hide_render": {"type": "boolean"}}, "required": ["name"]}},
    {"name": "set_custom_property", "description": "在物体上设置自定义属性（如 ph_query / ph_uv_scale）。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "prop_name": {"type": "string"}, "prop_value": {"description": "字符串/数字/布尔"}}, "required": ["name", "prop_name", "prop_value"]}},
    {"name": "add_empty", "description": "添加空物体（Empty）。用于定位/父子层级根节点。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "location": {"type": "array", "items": {"type": "number"}}, "empty_type": {"type": "string", "enum": ["PLAIN_AXES","ARROWS","SINGLE_ARROW","CIRCLE","CUBE","SPHERE","CONE"], "description": "默认 PLAIN_AXES"}, "size": {"type": "number", "description": "默认 1.0"}}, "required": []}},
    {"name": "add_decimate_modifier", "description": "添加精简修改器减少多边形。ratio=0.5 减半。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "ratio": {"type": "number", "description": "0~1，默认 0.5"}, "decimate_type": {"type": "string", "enum": ["COLLAPSE","UNSUBDIV","DISSOLVE"], "description": "默认 COLLAPSE"}}, "required": ["name"]}},
    {"name": "add_displace_modifier", "description": "添加置换修改器用噪点纹理使表面凹凸。自动创建 Clouds 噪点。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "strength": {"type": "number", "description": "默认 0.5"}, "mid_level": {"type": "number", "description": "默认 0.5"}, "texture_name": {"type": "string", "description": "留空自动创建"}}, "required": ["name"]}},
    {"name": "add_lattice_deform", "description": "添加晶格变形（创建 Lattice + 修改器）。晶格自动包裹物体 bbox。编辑晶格顶点可非线性扭曲物体。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "points_u": {"type": "integer", "description": "默认 4"}, "points_v": {"type": "integer", "description": "默认 4"}, "points_w": {"type": "integer", "description": "默认 4"}, "scale_factor": {"type": "number", "description": "默认 1.2"}}, "required": ["name"]}},
    {"name": "add_screw_modifier", "description": "添加螺旋修改器将 2D 轮廓旋转生成旋转体（花瓶/柱子）。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "angle": {"type": "number", "description": "弧度，默认 6.283185（360°）"}, "screw_offset": {"type": "number", "description": "螺旋偏移，0=纯旋转"}, "steps": {"type": "integer", "description": "默认 32"}, "axis": {"type": "string", "enum": ["X","Y","Z"], "description": "默认 Z"}}, "required": ["name"]}},
    {"name": "add_skin_modifier", "description": "添加皮肤修改器沿 mesh 边框生成管状体。适合树木/触手/骨骼。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "use_smooth_shade": {"type": "boolean", "description": "默认 true"}}, "required": ["name"]}},
    {"name": "add_wireframe_modifier", "description": "添加线框修改器把 mesh 边转为有厚度的管状线框。用于栅格/钢结构。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "thickness": {"type": "number", "description": "默认 0.02"}, "use_even_offset": {"type": "boolean", "description": "默认 true"}}, "required": ["name"]}},
    {"name": "add_curve_object", "description": "添加曲线物体：BEZIER/NURBS/PATH。可作动画路径/管道轮廓。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "curve_type": {"type": "string", "enum": ["BEZIER","NURBS","PATH"], "description": "默认 BEZIER"}, "location": {"type": "array", "items": {"type": "number"}}}, "required": []}},
    {"name": "set_material_nodes", "description": "用 Principled BSDF 节点设置材质（Blender 4.2+ 兼容）。支持自发光/透明/IOR。比 set_material 更强大。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "material_name": {"type": "string"}, "base_color": {"type": "array", "items": {"type": "number"}, "description": "[R,G,B,A] 0~1"}, "metallic": {"type": "number"}, "roughness": {"type": "number"}, "specular": {"type": "number"}, "emission_color": {"type": "array", "items": {"type": "number"}}, "emission_strength": {"type": "number"}, "alpha": {"type": "number"}, "ior": {"type": "number", "description": "默认 1.45"}}, "required": ["name"]}},
    {"name": "add_subdivision_and_sculpt", "description": "添加多分辨率修改器（Multires）用于雕刻。先建低面数基础形再用此工具。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "levels": {"type": "integer", "description": "1~6，默认 3"}}, "required": ["name"]}},
    {"name": "align_objects", "description": "对齐多个物体：把指定轴坐标对齐到同一值。align_mode: first/min/max/center。", "_route": "main",
     "parameters": {"type": "object", "properties": {"names": {"type": "array", "items": {"type": "string"}}, "axis": {"type": "string", "enum": ["X","Y","Z"], "description": "默认 X"}, "align_mode": {"type": "string", "enum": ["first","min","max","center"], "description": "默认 first"}, "align_value": {"type": "number"}}, "required": ["names"]}},
    {"name": "distribute_objects", "description": "均匀分布多个物体沿轴等间距排列。spacing=null 自动计算均匀间距。", "_route": "main",
     "parameters": {"type": "object", "properties": {"names": {"type": "array", "items": {"type": "string"}}, "axis": {"type": "string", "enum": ["X","Y","Z"], "description": "默认 X"}, "spacing": {"type": "number"}, "start_value": {"type": "number"}}, "required": ["names"]}},
    {"name": "get_modifier_list", "description": "获取物体所有修改器列表（名称/类型/是否显示）。apply_modifier 前确认修改器名。", "_route": "main",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "set_render_settings", "description": "设置渲染参数：引擎/分辨率/采样数/输出格式/透明背景。", "_route": "main",
     "parameters": {"type": "object", "properties": {"engine": {"type": "string", "enum": ["CYCLES","BLENDER_EEVEE","BLENDER_EEVEE_NEXT","BLENDER_WORKBENCH"]}, "resolution_x": {"type": "integer"}, "resolution_y": {"type": "integer"}, "resolution_percentage": {"type": "integer"}, "samples": {"type": "integer"}, "output_format": {"type": "string", "enum": ["PNG","JPEG","OPEN_EXR","TIFF"]}, "film_transparent": {"type": "boolean"}}, "required": []}},
    # ---------- v3.6.0：多角度截图 ----------
    {
        "name": "multi_angle_screenshot",
        "description": "【v3.6.0 视觉闭环 ⭐】自动从 4~5 个预设角度（正前 45° 俯视 / 正面平视 / 左侧 / 俯视 Top-down / 相机视角）对场景拍摄 OpenGL 截图。自动计算场景 bounding box 确定最佳拍摄距离，使用临时 Camera 拍完即删，不影响用户视口。比 get_viewport_screenshot 更全面——不依赖用户手动拉视口角度，AI 能同时看到正面/侧面/俯视，发现穿模/缺失/比例问题。Critic 审图和 Modeler 自检都应该优先用这个。",
        "_route": "main",
        "parameters": {"type": "object", "properties": {
            "max_size": {"type": "integer", "description": "每张截图最大边长（像素），默认 512。建议 384~512 平衡清晰度和传输速度", "default": 512},
            "angles": {"type": "array", "description": "可选：自定义角度列表，覆盖默认预设。每项 {name, theta, phi}（度）。留空用默认 4~5 角度。",
                       "items": {"type": "object", "properties": {
                           "name": {"type": "string", "description": "角度名称"},
                           "theta": {"type": "number", "description": "方位角（度），0=正前方"},
                           "phi": {"type": "number", "description": "俯仰角（度），0=水平，90=正上方"},
                       }}},
        }, "required": []},
    },
]


def _mcp_call(tool_name, args):
    """统一调用入口。供 /mcp/call 和 /mcp/<name> 共用。"""
    args = args or {}
    # 找 schema
    schema = next((t for t in MCP_TOOLS if t["name"] == tool_name), None)
    if schema is None:
        return {"ok": False, "error": "unknown tool: %s" % tool_name, "available": [t["name"] for t in MCP_TOOLS]}
    route = schema.get("_route", "main")
    try:
        if route == "main":
            # 特例：viewport_screenshot 复用现有任务类型
            if tool_name == "get_viewport_screenshot":
                r = _post_to_main("screenshot", {"max_size": int(args.get("max_size") or 800)}, timeout=20)
                if not r["ok"]: return r
                return {"ok": True, "data": r["data"]}
            r = _post_to_main("mcp_%s" % tool_name, args, timeout=60)
            if not r["ok"]: return r
            return r["data"]  # 主线程函数自己已经返回 {ok, data} 格式
    except Exception as e:
        push_log("ERROR", "mcp_call %s: %s" % (tool_name, e))
        return {"ok": False, "error": "%s: %s" % (tool_name, e),
                "traceback": traceback.format_exc(limit=4)}


def _mcp_tools_schema():
    """返回去除 _route 字段的 schema 列表（OpenAI tools 格式）"""
    out = []
    for t in MCP_TOOLS:
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get("parameters") or {"type": "object", "properties": {}},
            },
        })
    return out


# ============================================================
# HTTP Handler
# ============================================================

class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): return

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        try: return json.loads(raw.decode("utf-8") or "{}")
        except Exception: return {}

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        if self.path.startswith("/ping"):
            self._send_json(200, {
                "ok": True, "addon_version": ADDON_VERSION,
                "blender": bpy.app.version_string,
                "blender_version": list(bpy.app.version),
                "blender_major": bpy.app.version[0],
                "blender_minor": bpy.app.version[1],
                "queue_size": EXEC_QUEUE.qsize(),
                "features": ["exec", "scene_report", "viewport_screenshot",
                             "hyper3d_text_to_3d", "sketchfab_search", "sketchfab_import",
                             "mcp_tools",
                             # v2.1.0 Phase F：场景 overview + 软回滚（独立端点，不走 /mcp）
                             "blend_summary", "bookmark_state", "restore_state"],
                "mcp": {
                    "enabled": True,
                    "tool_count": len(MCP_TOOLS),
                    "tools": [t["name"] for t in MCP_TOOLS],
                },
                # v2.1.0 Phase F：暴露当前内存里的快照状态，让客户端能看到累计了几个
                "snapshots": {
                    "count": len(_BLEND_SNAPSHOTS),
                    "keys": sorted(_BLEND_SNAPSHOTS.keys())[:20],
                },
                "hyper3d_mode": RUNTIME_CONFIG.get("hyper3d_mode", "MAIN_SITE"),
                "hyper3d_using_trial": not bool(RUNTIME_CONFIG.get("hyper3d_api_key")),
                "sketchfab_configured": bool(RUNTIME_CONFIG.get("sketchfab_api_key")),
            })
            return
        if self.path == "/mcp/tools":
            # 返回 OpenAI tools 格式的 schema 列表
            self._send_json(200, {"ok": True, "tools": _mcp_tools_schema(),
                                  "addon_version": ADDON_VERSION,
                                  "count": len(MCP_TOOLS)})
            return
        if self.path.startswith("/viewport_screenshot"):
            # v1.10.1 修复：兼容前端 v1.9.7 的 GET /viewport_screenshot?max_size=600
            # （之前只在 do_POST 注册，导致前端「实时视口监测」面板报 HTTP 404）
            # v2.0.2 修复：补齐前端期望的字段别名（data / image / b64），
            # 之前 _capture_viewport_screenshot_main 只输出 base64 字段，
            # 而前端 viewportMonitor.tick() 读 data.data || data.image || data.b64
            # → 拿不到值 → 抛「返回未含 base64 数据」
            try:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                max_size = int(qs.get("max_size", ["800"])[0])
            except Exception:
                max_size = 800
            result = _post_to_main("screenshot", {"max_size": max_size}, timeout=20)
            if not result["ok"]:
                self._send_json(500, result); return
            payload = dict(result["data"] or {})
            b64 = payload.get("base64") or payload.get("data") or payload.get("image") or payload.get("b64") or ""
            if b64:
                # 同时提供 4 个字段，兼容老前端 / 新前端 / 第三方
                payload["base64"] = b64
                payload["data"] = b64
                payload["image"] = b64
                payload["b64"] = b64
            self._send_json(200, payload)
            return
        if self.path.startswith("/log"):
            self._send_json(200, {"ok": True, "log": list(LOG_RING)})
            return
        if self.path.startswith("/scene_report"):
            try: self._send_json(200, _collect_scene_report())
            except Exception as e:
                push_log("ERROR", "scene_report: %s" % e)
                self._send_json(500, {"ok": False, "error": str(e)})
            return
        # ---------- v2.1.0 Phase F：场景 overview（Critic 审图前用） ----------
        if self.path.startswith("/blend_summary"):
            r = _post_to_main("mcp_blend_summary", {}, timeout=20)
            if not r["ok"]:
                self._send_json(500, r); return
            self._send_json(200, r["data"])
            return
        if self.path.startswith("/config"):
            self._send_json(200, {"ok": True,
                "hyper3d_mode": RUNTIME_CONFIG.get("hyper3d_mode"),
                "hyper3d_using_trial": not bool(RUNTIME_CONFIG.get("hyper3d_api_key")),
                "sketchfab_configured": bool(RUNTIME_CONFIG.get("sketchfab_api_key")),
            })
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        # ---------- v2.0：MCP 统一入口 ----------
        # POST /mcp/call          { tool, args } → 通用调度
        # POST /mcp/<tool_name>   { ...args }    → 直接调对应工具
        if path == "/mcp/call":
            data = self._read_body()
            tool_name = data.get("tool") or data.get("name")
            args = data.get("args") or data.get("arguments") or {}
            if not tool_name:
                self._send_json(400, {"ok": False, "error": "缺少 tool 字段"}); return
            push_log("INFO", "MCP call: %s args=%s" % (tool_name, str(args)[:120]))
            res = _mcp_call(tool_name, args)
            self._send_json(200, res)
            return
        if path.startswith("/mcp/"):
            tool_name = path[len("/mcp/"):].strip("/")
            if tool_name in ("tools", "call", ""):
                self._send_json(400, {"ok": False, "error": "reserved path"}); return
            args = self._read_body() or {}
            push_log("INFO", "MCP call: %s args=%s" % (tool_name, str(args)[:120]))
            res = _mcp_call(tool_name, args)
            self._send_json(200, res)
            return
        # ---------- 0) 配置写入（前端 settings 同步过来）----------
        if path == "/config":
            data = self._read_body()
            for k in ("hyper3d_api_key", "hyper3d_mode", "sketchfab_api_key"):
                if k in data: RUNTIME_CONFIG[k] = (data[k] or "").strip()
            push_log("INFO", "config updated: hyper3d_mode=%s, hyper3d_user_key=%s, sketchfab=%s" % (
                RUNTIME_CONFIG.get("hyper3d_mode"),
                bool(RUNTIME_CONFIG.get("hyper3d_api_key")),
                bool(RUNTIME_CONFIG.get("sketchfab_api_key"))))
            self._send_json(200, {"ok": True, "updated": True})
            return
        # ---------- 1) 通用 exec ----------
        if path == "/exec":
            data = self._read_body()
            code = _sanitize_exec_code(data.get("code", ""))
            scene_name = data.get("scene_name", "AIScene")
            if not code:
                self._send_json(400, {"ok": False, "error": "empty code"}); return
            EXEC_QUEUE.put({"type": "exec", "payload": {"code": code, "scene_name": scene_name},
                            "event": None, "result_ref": None})
            push_log("INFO", "queued exec, %d chars, scene=%s" % (len(code), scene_name))
            self._send_json(200, {"ok": True, "queued": True, "queue_size": EXEC_QUEUE.qsize()})
            return
        # ---------- v2.1.0 Phase F：场景快照（修复失败回滚用） ----------
        if path == "/bookmark_state":
            data = self._read_body()
            r = _post_to_main("mcp_bookmark_state",
                              {"name": (data.get("name") or "").strip()},
                              timeout=30)
            if not r["ok"]:
                self._send_json(500, r); return
            self._send_json(200, r["data"])
            return
        if path == "/restore_state":
            data = self._read_body()
            r = _post_to_main("mcp_restore_state",
                              {"name": (data.get("name") or "").strip()},
                              timeout=60)
            if not r["ok"]:
                self._send_json(500, r); return
            self._send_json(200, r["data"])
            return
        # ---------- 2) 视口截图（主线程）----------
        if path == "/viewport_screenshot":
            # v2.0.2 同 do_GET：补齐字段别名（data / image / b64）兼容前端
            data = self._read_body()
            max_size = int(data.get("max_size", 800) or 800)
            result = _post_to_main("screenshot", {"max_size": max_size}, timeout=20)
            if not result["ok"]: self._send_json(500, result); return
            payload = dict(result["data"] or {})
            b64 = payload.get("base64") or payload.get("data") or payload.get("image") or payload.get("b64") or ""
            if b64:
                payload["base64"] = b64
                payload["data"] = b64
                payload["image"] = b64
                payload["b64"] = b64
            self._send_json(200, payload)
            return
        # ---------- 3) Hyper3D Rodin 文生 3D ----------
        if path == "/hyper3d/create":
            # handler 线程发起 HTTP 请求（不需要主线程）
            data = self._read_body()
            text_prompt = data.get("text_prompt") or data.get("prompt")
            images = data.get("images")  # [(suffix, base64)] 或 URL list（FAL_AI 模式）
            bbox = data.get("bbox_condition")
            res = _hyper3d_create_job(text_prompt=text_prompt, images=images, bbox_condition=bbox)
            push_log("INFO", "hyper3d create: %s" % (str(res)[:200]))
            self._send_json(200, res)
            return
        if path == "/hyper3d/poll":
            data = self._read_body()
            res = _hyper3d_poll_job(
                subscription_key=data.get("subscription_key"),
                request_id=data.get("request_id"),
            )
            self._send_json(200, res)
            return
        if path == "/hyper3d/import":
            # 1) 后端线程下载 GLB → 2) 主线程导入
            data = self._read_body()
            task_uuid = data.get("task_uuid")
            request_id = data.get("request_id")
            mesh_name = data.get("name") or "Hyper3D_asset"
            location = data.get("location")
            scale = data.get("scale", 1.0)
            push_log("INFO", "hyper3d download GLB...")
            local_path, err = _hyper3d_download_glb(task_uuid=task_uuid, request_id=request_id)
            if err:
                self._send_json(200, {"ok": False, "error": err}); return
            push_log("INFO", "hyper3d GLB → %s" % local_path)
            r = _post_to_main("import_glb",
                              {"filepath": local_path, "name": mesh_name, "location": location, "scale": scale},
                              timeout=30)
            try: os.unlink(local_path)
            except Exception: pass
            self._send_json(200, r["data"] if r["ok"] else {"ok": False, "error": r.get("error")})
            return
        # ---------- 4) Sketchfab ----------
        if path == "/sketchfab/search":
            data = self._read_body()
            res = _sketchfab_search(
                query=data.get("query", ""),
                count=int(data.get("count", 12)),
                downloadable=bool(data.get("downloadable", True)),
                categories=data.get("categories"),
            )
            self._send_json(200, res)
            return
        if path == "/sketchfab/import":
            data = self._read_body()
            uid = data.get("uid")
            mesh_name = data.get("name") or "Sketchfab_model"
            location = data.get("location")
            scale = data.get("scale", 1.0)
            if not uid: self._send_json(400, {"ok": False, "error": "uid 为空"}); return
            push_log("INFO", "sketchfab download uid=%s..." % uid)
            local_path, err = _sketchfab_download_to_temp(uid)
            if err: self._send_json(200, {"ok": False, "error": err}); return
            r = _post_to_main("import_glb",
                              {"filepath": local_path, "name": mesh_name, "location": location, "scale": scale},
                              timeout=60)
            # 清理整个临时目录
            try: shutil.rmtree(os.path.dirname(local_path))
            except Exception: pass
            self._send_json(200, r["data"] if r["ok"] else {"ok": False, "error": r.get("error")})
            return
        self._send_json(404, {"ok": False, "error": "not found"})


# ============================================================
# 主线程定时器（处理 EXEC_QUEUE）
# ============================================================
def _drain_queue():
    try:
        while not EXEC_QUEUE.empty():
            item = EXEC_QUEUE.get_nowait()
            ttype = item.get("type", "exec")
            payload = item.get("payload", {})
            event = item.get("event")
            ref = item.get("result_ref") or {"data": None, "error": None}
            try:
                if ttype == "exec":
                    code = _sanitize_exec_code(payload.get("code", ""))
                    scene_name = payload.get("scene_name", "AIScene")
                    text_name = "aichat_%s" % scene_name
                    try:
                        if text_name in bpy.data.texts: bpy.data.texts.remove(bpy.data.texts[text_name])
                        txt = bpy.data.texts.new(text_name); txt.write(code)
                    except Exception as e:
                        push_log("WARN", "save Text failed: %s" % e)
                    push_log("INFO", "exec start scene=%s" % scene_name)
                    # v2.0.3：exec 入口同样预置 namespace，治 LLM 写代码直接 mathutils.Vector 报 NameError
                    globs = {"__name__": "__aichat_exec__", "bpy": bpy}
                    try:
                        import math as _math, mathutils as _mu, bmesh as _bm
                        from mathutils import Vector, Matrix, Euler, Quaternion, Color
                        globs.update({"math": _math, "mathutils": _mu, "bmesh": _bm,
                                      "Vector": Vector, "Matrix": Matrix, "Euler": Euler,
                                      "Quaternion": Quaternion, "Color": Color})
                    except Exception:
                        pass
                    try:
                        exec(compile(code, text_name, "exec"), globs)
                        push_log("INFO", "exec done")
                    except Exception as e:
                        tb = traceback.format_exc(limit=8)
                        push_log("ERROR", "exec failed: %s\n%s" % (e, tb))
                elif ttype == "screenshot":
                    ref["data"] = _capture_viewport_screenshot_main(payload.get("max_size", 800))
                elif ttype == "import_glb":
                    ref["data"] = _import_glb_main_thread(
                        payload.get("filepath"), payload.get("name"),
                        payload.get("location"), payload.get("scale"),
                    )
                elif ttype.startswith("mcp_"):
                    tool_name = ttype[4:]  # 去掉 "mcp_" 前缀
                    handler = MCP_MAIN_HANDLERS.get(tool_name)
                    if handler is None:
                        ref["error"] = "no main-thread handler for mcp tool: %s" % tool_name
                    else:
                        ref["data"] = handler(payload)
                else:
                    ref["error"] = "unknown task type: %s" % ttype
            except Exception as e:
                ref["error"] = str(e)
                push_log("ERROR", "task %s fatal: %s" % (ttype, e))
            finally:
                if event is not None:
                    try: event.set()
                    except Exception: pass
    except Exception as e:
        push_log("ERROR", "timer fatal: %s" % e)
    return 0.2


# ============================================================
# 启停（保持 v1.1.0 兼容）
# ============================================================
def start_bridge(host=DEFAULT_HOST, port=DEFAULT_PORT):
    global _server, _server_thread, _timer_registered
    if _server is not None:
        push_log("INFO", "bridge already running")
        return True, "already running"
    try:
        _server = ThreadingHTTPServer((host, port), _Handler)
    except OSError as e:
        push_log("ERROR", "bind %s:%d failed: %s" % (host, port, e))
        _server = None
        return False, str(e)
    def serve():
        try: _server.serve_forever(poll_interval=0.3)
        except Exception as e: push_log("ERROR", "serve_forever: %s" % e)
    _server_thread = threading.Thread(target=serve, name="aichat-bridge-http", daemon=True)
    _server_thread.start()
    if not _timer_registered:
        bpy.app.timers.register(_drain_queue, persistent=True)
        _timer_registered = True
    push_log("INFO", "bridge v%s listening on http://%s:%d" % (ADDON_VERSION, host, port))
    return True, "ok"


def stop_bridge():
    global _server, _server_thread, _timer_registered
    if _server is None: return True, "not running"
    try:
        _server.shutdown(); _server.server_close()
    except Exception as e: push_log("WARN", "shutdown: %s" % e)
    _server = None; _server_thread = None
    if _timer_registered:
        try: bpy.app.timers.unregister(_drain_queue)
        except Exception: pass
        _timer_registered = False
    push_log("INFO", "bridge stopped")
    return True, "ok"


# ============================================================
# Preferences / Operators / Panel
# ============================================================
class AIChatPrefs(bpy.types.AddonPreferences):
    bl_idname = __name__
    host: bpy.props.StringProperty(name="Host", default=DEFAULT_HOST)
    port: bpy.props.IntProperty(name="Port", default=DEFAULT_PORT, min=1, max=65535)
    autostart: bpy.props.BoolProperty(name="Autostart on enable", default=True)
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "host"); row.prop(self, "port")
        layout.prop(self, "autostart")
        layout.label(text="启用插件后会自动监听上述地址，可在 N 面板手动启停。")
        layout.separator()
        layout.label(text="v2.1.0 新增：GET /blend_summary（场景概览）+ POST /bookmark_state + /restore_state（软回滚）")
        layout.label(text="v2.0.0：MCP 工具协议（16 个原子工具）+ Agent 循环架构")
        layout.label(text="向后兼容：v1.x 客户端（/exec / /scene_report）继续可用")
        layout.label(text="API key 不在这里设，由前端「智能 Agent」面板统一配置后通过 /config 写入")


class AICHAT_OT_start(bpy.types.Operator):
    bl_idname = "aichat.start_bridge"; bl_label = "启动桥接"
    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        ok, msg = start_bridge(prefs.host, prefs.port)
        if ok: self.report({"INFO"}, "AIChat Bridge started: %s" % msg)
        else: self.report({"ERROR"}, "Start failed: %s" % msg)
        return {"FINISHED"}


class AICHAT_OT_stop(bpy.types.Operator):
    bl_idname = "aichat.stop_bridge"; bl_label = "停止桥接"
    def execute(self, context):
        ok, msg = stop_bridge()
        self.report({"INFO"}, "AIChat Bridge stopped: %s" % msg)
        return {"FINISHED"}


class AICHAT_OT_demo(bpy.types.Operator):
    bl_idname = "aichat.demo_scene"; bl_label = "Demo 场景"
    def execute(self, context):
        demo = ("import bpy\n"
                "for obj in list(bpy.data.objects): bpy.data.objects.remove(obj, do_unlink=True)\n"
                "bpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,1))\n"
                "bpy.ops.mesh.primitive_plane_add(size=10)\n"
                "bpy.ops.object.light_add(type='SUN', location=(4,4,8))\n"
                "bpy.ops.object.camera_add(location=(7,-7,5), rotation=(1.1, 0, 0.785))\n"
                "bpy.context.scene.camera = bpy.context.object\n")
        EXEC_QUEUE.put({"type": "exec", "payload": {"code": demo, "scene_name": "demo"},
                        "event": None, "result_ref": None})
        self.report({"INFO"}, "Demo queued"); return {"FINISHED"}


class AICHAT_OT_clear_log(bpy.types.Operator):
    bl_idname = "aichat.clear_log"; bl_label = "清空日志"
    def execute(self, context):
        LOG_RING.clear(); return {"FINISHED"}


class AICHAT_PT_panel(bpy.types.Panel):
    bl_label = "AIChat Bridge"
    bl_idname = "AICHAT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AIChat"
    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__name__].preferences
        box = layout.box()
        running = _server is not None
        row = box.row()
        if running: row.label(text="● 运行中", icon="RADIOBUT_ON")
        else: row.label(text="○ 已停止", icon="RADIOBUT_OFF")
        box.label(text="插件版本：v%s" % ADDON_VERSION)
        box.label(text="http://%s:%d" % (prefs.host, prefs.port))
        box.label(text="队列：%d" % EXEC_QUEUE.qsize())
        # v2.0.0 MCP 状态
        mcp_box = layout.box()
        mcp_box.label(text="v2.0 MCP 工具协议", icon="MODIFIER_DATA")
        mcp_box.label(text="已注册 %d 个工具" % len(MCP_TOOLS), icon="DOT")
        mcp_box.label(text="端点: /mcp/tools · /mcp/call")
        # v2.1.0 Phase F 状态
        f_box = layout.box()
        f_box.label(text="v2.1.0 Phase F：场景概览 + 软回滚", icon="RECOVER_LAST")
        f_box.label(text="GET /blend_summary · POST /bookmark_state · /restore_state", icon="DOT")
        f_box.label(text="内存快照：%d 个" % len(_BLEND_SNAPSHOTS), icon="DOT")
        # v1.2.0 状态
        sub = layout.box()
        sub.label(text="v1.2.0 增值能力（兼容保留）", icon="OUTLINER_OB_LIGHTPROBE")
        ko_h3d = bool(RUNTIME_CONFIG.get("hyper3d_api_key"))
        sub.label(text="Hyper3D: %s (%s)" % (
            RUNTIME_CONFIG.get("hyper3d_mode", "MAIN_SITE"),
            "用户 key" if ko_h3d else "免费 trial"
        ))
        sub.label(text="Sketchfab: %s" % ("已配置" if RUNTIME_CONFIG.get("sketchfab_api_key") else "未配置"))
        row = layout.row(align=True)
        row.operator("aichat.start_bridge", icon="PLAY")
        row.operator("aichat.stop_bridge", icon="PAUSE")
        layout.operator("aichat.demo_scene", icon="MESH_CUBE")
        layout.separator()
        layout.label(text="最近日志：")
        log_box = layout.box()
        if not LOG_RING: log_box.label(text="(空)")
        else:
            for entry in LOG_RING[-8:]:
                icon = "ERROR" if entry["level"] == "ERROR" else "INFO" if entry["level"] == "INFO" else "QUESTION"
                log_box.label(text="[%s] %s" % (entry["t"], entry["msg"][:80]), icon=icon)
        layout.operator("aichat.clear_log", icon="TRASH")


_classes = (AIChatPrefs, AICHAT_OT_start, AICHAT_OT_stop, AICHAT_OT_demo,
            AICHAT_OT_clear_log, AICHAT_PT_panel)


def register():
    for cls in _classes: bpy.utils.register_class(cls)
    def _autostart():
        try:
            prefs = bpy.context.preferences.addons[__name__].preferences
            if prefs.autostart: start_bridge(prefs.host, prefs.port)
        except Exception as e: push_log("WARN", "autostart failed: %s" % e)
        return None
    bpy.app.timers.register(_autostart, first_interval=0.5)


def unregister():
    stop_bridge()
    for cls in reversed(_classes):
        try: bpy.utils.unregister_class(cls)
        except Exception: pass


if __name__ == "__main__":
    register()
