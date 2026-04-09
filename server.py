"""待办清单本地服务 - 数据存储在 todos.json 文件中"""
import http.server
import socketserver
import json
import os
import time
import random
import string
import urllib.parse
import threading

PORT = 8099
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'todos.json')
HTML_FILE = os.path.join(BASE_DIR, '待办清单.html')

DEFAULT_TODOS = [
    {"id": "t1", "text": "模糊一点，预付模式", "completed": False, "date": "2026-04-08"},
    {"id": "t2", "text": "编剧合同的结算条款", "completed": False, "date": "2026-04-08"},
    {"id": "t3", "text": "唯一部老剧，是不是要调整结算规则", "completed": False, "date": "2026-04-08"},
    {"id": "t4", "text": "作者向的，要出公告，而不是补协", "completed": False, "date": "2026-04-08"},
    {"id": "t5", "text": "再传一下原始账单名称", "completed": False, "date": "2026-04-08"},
    {"id": "t6", "text": "杨水星的特殊分成比例邮件，单独处理", "completed": False, "date": "2026-04-08"},
    {"id": "t7", "text": "762623460461720568（相关事项跟进）", "completed": False, "date": "2026-04-08"},
    {"id": "t8", "text": "微信分销感觉有问题，取不到", "completed": False, "date": "2026-04-08"},
    {"id": "t9", "text": "千锻一品加个AC", "completed": False, "date": "2026-04-08"},
    {"id": "t10", "text": "推小果只结算到331", "completed": False, "date": "2026-04-08"},
    {"id": "t11", "text": "CP发送结算单", "completed": False, "date": "2026-04-08"},
]

# 线程锁，保护文件读写
_data_lock = threading.Lock()


def gen_id():
    ts = hex(int(time.time() * 1000))[2:]
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return ts + rand


def load_todos():
    with _data_lock:
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"读取数据文件失败: {e}")
        save_todos_unlocked(DEFAULT_TODOS)
        return list(DEFAULT_TODOS)


def save_todos_unlocked(todos):
    """不加锁版本，供内部调用"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)


def save_todos(todos):
    with _data_lock:
        save_todos_unlocked(todos)


def get_today():
    import datetime
    return datetime.date.today().isoformat()


class TodoHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # 简化日志
        pass

    def _set_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._set_cors()
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # API: 获取全部待办
        if path == '/api/todos':
            todos = load_todos()
            return self._send_json(200, todos)

        # 默认页面
        if path in ('/', '/index.html'):
            try:
                with open(HTML_FILE, 'r', encoding='utf-8') as f:
                    html = f.read().encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'读取HTML失败: {e}'.encode('utf-8'))
            return

        # 其他静态文件
        safe_path = urllib.parse.unquote(path).lstrip('/')
        file_path = os.path.join(BASE_DIR, safe_path)
        if os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {
                '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
                '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
                '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
            }
            mime = mime_map.get(ext, 'application/octet-stream')
            with open(file_path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', f'{mime}; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 添加待办
        if path == '/api/todos':
            try:
                body = self._read_body()
                todos = load_todos()
                new_todo = {
                    "id": gen_id(),
                    "text": body.get("text", ""),
                    "completed": False,
                    "date": body.get("date", get_today()),
                }
                todos.insert(0, new_todo)
                save_todos(todos)
                return self._send_json(201, new_todo)
            except Exception as e:
                return self._send_json(400, {"error": str(e)})

        # 批量导入
        if path == '/api/todos/bulk':
            try:
                body = self._read_body()
                if isinstance(body, list):
                    save_todos(body)
                    return self._send_json(200, {"ok": True, "count": len(body)})
                return self._send_json(400, {"error": "需要数组"})
            except Exception as e:
                return self._send_json(400, {"error": str(e)})

        self._send_json(404, {"error": "Not Found"})

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 更新待办
        if path.startswith('/api/todos/'):
            todo_id = path.split('/')[-1]
            try:
                body = self._read_body()
                todos = load_todos()
                todo = next((t for t in todos if t['id'] == todo_id), None)
                if not todo:
                    return self._send_json(404, {"error": "未找到该待办"})

                if 'completed' in body:
                    todo['completed'] = body['completed']
                    if body['completed']:
                        todo['completedDate'] = get_today()
                    else:
                        todo.pop('completedDate', None)

                if 'text' in body:
                    todo['text'] = body['text']

                save_todos(todos)
                return self._send_json(200, todo)
            except Exception as e:
                return self._send_json(400, {"error": str(e)})

        self._send_json(404, {"error": "Not Found"})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith('/api/todos/'):
            todo_id = path.split('/')[-1]
            todos = load_todos()
            before = len(todos)
            todos = [t for t in todos if t['id'] != todo_id]
            if len(todos) == before:
                return self._send_json(404, {"error": "未找到该待办"})
            save_todos(todos)
            return self._send_json(200, {"ok": True})

        self._send_json(404, {"error": "Not Found"})


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """多线程HTTP服务器，防止单个连接阻塞整个服务"""
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    server = ThreadedHTTPServer(('127.0.0.1', PORT), TodoHandler)
    print(f'待办清单服务已启动: http://localhost:{PORT}')
    print(f'数据文件: {DATA_FILE}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止')
        server.server_close()
