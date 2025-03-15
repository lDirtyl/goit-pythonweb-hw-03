from jinja2 import Environment, FileSystemLoader
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import json
from datetime import datetime
from urllib.parse import parse_qs
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

# Налаштування
HOST = '0.0.0.0'
PORT = 3000
DATA_FILE = 'storage/data.json'

# Шляхи
BASE_DIR = os.path.dirname(__file__)
TEMPLATES_PATH = os.path.join(BASE_DIR, 'templates')
STATIC_PATH = os.path.join(BASE_DIR, 'static')

# Середовище Jinja2
env = Environment(loader=FileSystemLoader(TEMPLATES_PATH))


# Обробник HTTP запитів
class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        routes = {
            '/': 'index.html.jinja2',
            '/message.html': 'message.html.jinja2',
            '/read': 'read.html.jinja2',
        }

        if self.path in routes:
            template = env.get_template(routes[self.path])
            if self.path == '/read':
                with open(DATA_FILE, 'r') as f:
                    messages = json.load(f)
                formatted_messages = {
                    datetime.fromisoformat(ts).strftime('%B %d, %Y, %I:%M %p'): msg
                    for ts, msg in sorted(messages.items(), key=lambda x: x[0], reverse=True)
                }
                content = template.render(messages=formatted_messages)
            else:
                content = template.render()
            self._send_response(200, content)
        elif self.path.startswith('/static/'):
            self._serve_static()
        else:
            template = env.get_template('error.html.jinja2')
            content = template.render()
            self._send_response(404, content)

    def do_POST(self):
        if self.path == '/message':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = parse_qs(post_data.decode('utf-8'))

            username = data.get('username', [''])[0]
            message = data.get('message', [''])[0]

            if username and message:
                with open(DATA_FILE, 'r+') as f:
                    stored_data = json.load(f)
                    timestamp = datetime.now().isoformat()
                    stored_data[timestamp] = {"username": username, "message": message}
                    f.seek(0)
                    json.dump(stored_data, f, indent=4)

                self._redirect('/')
            else:
                self._send_response(400, 'Bad Request: Missing username or message')
        else:
            self._send_response(404, 'Not Found')

    def _send_response(self, status, content):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def _serve_static(self):
        file_path = os.path.join(STATIC_PATH, os.path.basename(self.path))
        if os.path.exists(file_path):
            self.send_response(200)
            if file_path.endswith('.css'):
                self.send_header('Content-type', 'text/css')
            elif file_path.endswith('.png'):
                self.send_header('Content-type', 'image/png')
            self.end_headers()
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self._send_response(404, 'Static File Not Found')

    def _redirect(self, location):
        self.send_response(303)
        self.send_header('Location', location)
        self.end_headers()


# Наглядач за оновленнями в реальному часі (watchdog)
class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".jinja2") or event.src_path.endswith(".css"):
            print(f"🔄 File changed: {event.src_path}")
            global env
            env = Environment(loader=FileSystemLoader(TEMPLATES_PATH))


# Запуск сервера
if __name__ == '__main__':
    try:
        httpd = HTTPServer((HOST, PORT), CustomHTTPRequestHandler)
        server = Thread(target=httpd.serve_forever)
        server.start()
        print(f"Server is running on http://{HOST}:{PORT}")

        # Start Watchdog
        observer = Observer()
        observer.schedule(FileChangeHandler(), path=TEMPLATES_PATH, recursive=True)
        observer.schedule(FileChangeHandler(), path=STATIC_PATH, recursive=True)
        observer.start()
        print("Watching for file changes...")

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n Shutting down the server...")
        observer.stop()
        httpd.shutdown()
        server.join()
        observer.join()
        print("Server stopped")