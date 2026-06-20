#!/usr/bin/env python3
"""
Hunyuan3D 本地推理服务
懒加载模式：首次调用时才初始化模型
支持图像生成3D模型
"""
import os
import sys
import io
import json
import base64
import tempfile
import threading
from pathlib import Path

# 添加项目路径
PROJECT_DIR = Path(__file__).parent / "Hunyuan3D-2-main"
sys.path.insert(0, str(PROJECT_DIR))

from flask import Flask, request, jsonify
from PIL import Image

app = Flask(__name__)

# 全局状态
_pipeline_shapegen = None
_pipeline_texgen = None
_model_loaded = False
_init_lock = threading.Lock()


def load_models():
    """懒加载模型"""
    global _pipeline_shapegen, _pipeline_texgen, _model_loaded
    
    if _model_loaded:
        return True
    
    with _init_lock:
        if _model_loaded:
            return True
        
        print("[Hunyuan3D] 正在加载模型...")
        try:
            from hy3dgen.rembg import BackgroundRemover
            from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
            from hy3dgen.texgen import Hunyuan3DPaintPipeline
            
            # v3.8.0: 使用 Hunyuan3D-2mini (0.6B) 轻量版，M4 Pro 24GB 可跑
            # hy3dgen 的路径逻辑: os.path.join(~/.cache/hy3dgen/, model_path, subfolder)
            # 所以 model_path 必须是 'tencent/Hunyuan3D-2mini' 格式
            # 本地权重通过符号链接: ~/.cache/hy3dgen/tencent/Hunyuan3D-2mini -> 实际下载目录
            mini_local = Path(__file__).parent / "Hunyuan3D-2mini-weights"
            cache_link = Path.home() / ".cache" / "hy3dgen" / "tencent" / "Hunyuan3D-2mini"
            if mini_local.exists() and not cache_link.exists():
                cache_link.parent.mkdir(parents=True, exist_ok=True)
                cache_link.symlink_to(mini_local)
                print(f"[Hunyuan3D] 创建符号链接: {cache_link} -> {mini_local}")
            
            model_path = 'tencent/Hunyuan3D-2mini'
            
            # Apple Silicon: 用 MPS 或 CPU（不支持 CUDA）
            import torch
            if torch.backends.mps.is_available():
                device = 'mps'
            else:
                device = 'cpu'
            print(f"[Hunyuan3D] 使用设备: {device}")
            
            print(f"[Hunyuan3D] 加载形状生成模型 (mini-turbo) from {model_path}...")
            _pipeline_shapegen = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
                model_path,
                subfolder='hunyuan3d-dit-v2-mini-turbo',
                device=device,
            )
            
            print("[Hunyuan3D] 跳过纹理模型（mini 版仅生成白模，可后续用 PolyHaven 贴图）")
            _pipeline_texgen = None  # mini 版暂不加载纹理
            
            _model_loaded = True
            print("[Hunyuan3D] 模型加载完成!")
            return True
        except Exception as e:
            import traceback
            print(f"[Hunyuan3D] 模型加载失败: {e}")
            traceback.print_exc()
            return False


def _clamp_number(value, min_value, max_value, default, as_int=False):
    try:
        n = float(value)
        if n != n:
            return default
        n = max(min_value, min(max_value, n))
        return int(round(n)) if as_int else n
    except Exception:
        return default


def _build_shape_kwargs(shape_params=None):
    params = shape_params if isinstance(shape_params, dict) else {}
    kwargs = {}
    effective = {}

    if 'num_inference_steps' in params:
        effective['num_inference_steps'] = _clamp_number(params.get('num_inference_steps'), 1, 100, 10, True)
        kwargs['num_inference_steps'] = effective['num_inference_steps']
    if 'guidance_scale' in params:
        effective['guidance_scale'] = _clamp_number(params.get('guidance_scale'), 0, 20, 5.0, False)
        kwargs['guidance_scale'] = effective['guidance_scale']
    if 'octree_resolution' in params:
        effective['octree_resolution'] = _clamp_number(params.get('octree_resolution'), 16, 512, 256, True)
        kwargs['octree_resolution'] = effective['octree_resolution']
    if 'num_chunks' in params:
        effective['num_chunks'] = _clamp_number(params.get('num_chunks'), 1000, 5000000, 20000, True)
        kwargs['num_chunks'] = effective['num_chunks']
    if 'mc_level' in params:
        effective['mc_level'] = _clamp_number(params.get('mc_level'), -1, 1, 0.0, False)
        kwargs['mc_level'] = effective['mc_level']
    if 'box_v' in params:
        effective['box_v'] = _clamp_number(params.get('box_v'), 0.5, 2, 1.01, False)
        kwargs['box_v'] = effective['box_v']
    if params.get('mc_algo') in ('mc', 'dmc'):
        effective['mc_algo'] = params.get('mc_algo')
        kwargs['mc_algo'] = effective['mc_algo']
    if 'seed' in params:
        seed = _clamp_number(params.get('seed'), 0, 2147483647, 1234, True)
        try:
            import torch
            kwargs['generator'] = torch.Generator().manual_seed(seed)
            effective['seed'] = seed
        except Exception as e:
            print("[Hunyuan3D] 创建随机种子生成器失败，使用默认随机源:", e)
    return kwargs, effective


def generate_3d_from_image(image_data, generate_texture=True, shape_params=None, preprocess_params=None):
    """从图像生成3D模型"""
    if not load_models():
        return {"ok": False, "error": "模型加载失败"}
    
    try:
        # 解码图像
        if isinstance(image_data, str):
            if image_data.startswith('data:'):
                # data:image/png;base64,...
                img_data = image_data.split(',', 1)[1]
            else:
                img_data = image_data
            image = Image.open(io.BytesIO(base64.b64decode(img_data)))
        else:
            image = Image.open(io.BytesIO(image_data))
        
        # v3.8.1 修复：先抠图（去背景）再转 RGBA。
        # 原代码先 convert("RGBA") 再判断 mode=='RGB'，导致判断永远不成立、抠图从不执行，
        # 不透明图（含白底参考图）会把背景一起重建 → 模型质量差。
        preprocess_params = preprocess_params if isinstance(preprocess_params, dict) else {}
        remove_background = preprocess_params.get('remove_background', True) is not False
        need_rembg = remove_background
        if image.mode == 'RGBA':
            try:
                if image.getchannel('A').getextrema()[0] < 255:
                    need_rembg = False  # 已有透明区，视为已抠图，跳过
            except Exception:
                pass
        if need_rembg:
            try:
                from hy3dgen.rembg import BackgroundRemover
                image = BackgroundRemover()(image.convert("RGB"))
            except Exception as _e:
                print("[Hunyuan3D] 背景去除失败，使用原图:", _e)
        image = image.convert("RGBA")

        shape_kwargs, effective_shape_params = _build_shape_kwargs(shape_params)
        print(f"[Hunyuan3D] 生成形状，参数: {effective_shape_params or 'default'}")
        # 生成形状
        mesh = _pipeline_shapegen(image=image, **shape_kwargs)[0]
        
        if generate_texture and _pipeline_texgen is not None:
            print("[Hunyuan3D] 生成纹理...")
            # 生成纹理
            mesh = _pipeline_texgen(mesh, image=image)
        elif generate_texture:
            print("[Hunyuan3D] mini 版无纹理模型，导出白模（可后续在 Blender 中贴图）")
        
        # 保存到临时文件
        fd, temp_path = tempfile.mkstemp(suffix='.glb')
        os.close(fd)
        
        mesh.export(temp_path)
        
        # 读取GLB文件
        with open(temp_path, 'rb') as f:
            glb_data = f.read()
        
        # 删除临时文件
        os.unlink(temp_path)
        
        return {
            "ok": True,
            "glb_base64": base64.b64encode(glb_data).decode('utf-8'),
            "size": len(glb_data),
            "has_texture": generate_texture,
            "shape_params": effective_shape_params,
            "preprocess_params": {"remove_background": remove_background}
        }
        
    except Exception as e:
        import traceback
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


def generate_3d_from_text(text_prompt, generate_texture=True):
    """从文本生成3D模型
    v3.8.0: Hunyuan3D-2mini 只支持 image-to-3D，不支持 text-to-3D。
    直接返回错误提示，引导 AI 走两步流程：先生成参考图 → 再用 from-image。
    """
    return {
        "ok": False,
        "error": "Hunyuan3D-2mini 不支持纯文本生成3D（只支持 from-image 模式）。",
        "hint": "请改用两步流程：1) 先调 generate_texture(prompt='%s') 生成参考图 → 2) 再调 generate_3d_model(mode:'from-image', image:参考图的base64)" % text_prompt,
        "suggested_action": "generate_texture",
        "suggested_prompt": text_prompt,
    }


# ==================== API 端点 ====================

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "ok": True,
        "model_loaded": _model_loaded,
        "service": "hunyuan3d"
    })


@app.route('/generate/from-image', methods=['POST'])
def generate_from_image():
    """从图像生成3D模型"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "缺少请求数据"})
        
        image_data = data.get('image')
        if not image_data:
            return jsonify({"ok": False, "error": "缺少 image 字段"})
        
        generate_texture = data.get('texture', True)
        shape_params = data.get('shape_params') or {}
        preprocess_params = data.get('preprocess_params') or {}
        
        result = generate_3d_from_image(image_data, generate_texture, shape_params, preprocess_params)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route('/generate/from-text', methods=['POST'])
def generate_from_text():
    """从文本生成3D模型"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "缺少请求数据"})
        
        text_prompt = data.get('prompt')
        if not text_prompt:
            return jsonify({"ok": False, "error": "缺少 prompt 字段"})
        
        generate_texture = data.get('texture', True)
        
        result = generate_3d_from_text(text_prompt, generate_texture)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route('/load-models', methods=['POST'])
def load_models_endpoint():
    """手动触发模型加载"""
    success = load_models()
    return jsonify({
        "ok": success,
        "model_loaded": _model_loaded
    })


if __name__ == '__main__':
    port = int(os.environ.get('HUNYUAN_PORT', 8767))
    print(f"[Hunyuan3D] 启动服务，端口: {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
