#!/usr/bin/env python3
"""AIChat PS Bridge - Photoshop MCP 桥接服务器"""
import json, sys, os, platform, subprocess, argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = '1.0.0'
IS_MAC = platform.system() == 'Darwin'

def run_applescript(script):
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=30)
        return {'ok': True, 'output': r.stdout.strip()} if r.returncode == 0 else {'ok': False, 'error': r.stderr.strip()}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def ps_tell(code):
    return f'tell application "Adobe Photoshop 2025"\n{code}\nend tell'

def try_ps():
    for v in ['Adobe Photoshop 2025','Adobe Photoshop 2024','Adobe Photoshop 2023']:
        if run_applescript(f'tell application "{v}" to get name').get('ok'):
            return v
    return None

MCP_TOOLS = {
    'create_document': {
        'desc': '创建新文档',
        'fn': lambda p: run_applescript(ps_tell(
            'set d to make new document with properties {name:"' + p.get('name','Untitled') + '", width:' + str(p.get('width',1920)) + ', height:' + str(p.get('height',1080)) + ', resolution:' + str(p.get('resolution',72)) + '}'
        ))
    },
    'add_text_layer': {
        'desc': '添加文字图层',
        'fn': lambda p: run_applescript(ps_tell(
            'set tl to make new art layer in current document with properties {kind:text}\n' +
            'set contents of text object of tl to "' + p['text'] + '"'
        ))
    },
    'resize_canvas': {
        'desc': '调整画布大小',
        'fn': lambda p: run_applescript(ps_tell(
            'resize canvas current document width ' + str(p['width']) + ' height ' + str(p['height'])
        ))
    },
    'export_jpg': {
        'desc': '导出JPG',
        'fn': lambda p: run_applescript(ps_tell(
            'set q to ' + str(p.get('quality',10)) + '\n' +
            'set opt to {class:JPEG save options, quality:q}\n' +
            'save current document in file "' + p['path'] + '" as JPEG with options opt'
        ))
    },
    'export_png': {
        'desc': '导出PNG',
        'fn': lambda p: run_applescript(ps_tell(
            'save current document in file "' + p['path'] + '" as PNG'
        ))
    },
    'duplicate_layer': {
        'desc': '复制当前图层',
        'fn': lambda p: run_applescript(ps_tell('duplicate current layer of current document'))
    },
    'delete_layer': {
        'desc': '删除图层',
        'fn': lambda p: run_applescript(ps_tell(
            'delete (every art layer of current document whose name is "' + p.get('name','Layer 1') + '")'
        ))
    },
    'flatten_image': {
        'desc': '拼合图像',
        'fn': lambda p: run_applescript(ps_tell('flatten current document'))
    },
    'get_document_info': {
        'desc': '获取文档信息',
        'fn': lambda p: run_applescript(ps_tell(
            'set n to name of current document\nset w to width of current document\nset h to height of current document\nset c to count of art layers of current document\nreturn n & "|" & w & "|" & h & "|" & c'
        ))
    },
}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, f, *a): print(f'[PS] {a[0]}')
    def _json(self, d, s=200):
        self.send_response(s)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(json.dumps(d,ensure_ascii=False).encode())
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()
    def do_GET(self):
        if self.path == '/ping':
            ps = try_ps()
            self._json({'ok':ps is not None,'ps':ps or 'N/A','bridge':VERSION})
        elif self.path == '/tools':
            self._json({'tools':{k:{'desc':v['desc']} for k,v in MCP_TOOLS.items()}})
        else:
            self._json({'name':'AIChat PS Bridge','version':VERSION,'endpoints':['/ping','/tools','/execute']})
    def do_POST(self):
        if self.path != '/execute':
            self._json({'error':'Not found'},404)
            return
        cl = int(self.headers.get('Content-Length',0))
        data = json.loads(self.rfile.read(cl))
        tool = data.get('tool','')
        if tool == 'list_tools':
            self._json({'ok':True,'tools':{k:{'desc':v['desc']} for k,v in MCP_TOOLS.items()}})
            return
        if tool not in MCP_TOOLS:
            self._json({'error':f'Unknown: {tool}'},400)
            return
        r = MCP_TOOLS[tool]['fn'](data.get('params',{}))
        self._json(r)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--host',default='127.0.0.1')
    a = p.parse_args()
    srv = ThreadingHTTPServer((a.host,a.port), Handler)
    print(f'AIChat PS Bridge v{VERSION} @ http://{a.host}:{a.port}')
    print(f'PS: {try_ps() or "Not found"}')
    print(f'Tools: {", ".join(MCP_TOOLS.keys())}')
    try: srv.serve_forever()
    except KeyboardInterrupt: print('Stopped')
if __name__ == '__main__': main()
