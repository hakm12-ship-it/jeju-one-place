"""센터 PC 로컬 실행. Python 3.10 이상, 표준 라이브러리만 사용."""
import argparse
import json
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError

from agent import ask
from engine import catalog, compare, field_checks, center_comparison

ROOT = Path(__file__).resolve().parent
STATIC = {"/": ("index.html", "text/html"), "/screen.css": ("screen.css", "text/css"),
          "/screen.js": ("screen.js", "text/javascript")}


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, raw, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def send_json(self, data, status=200):
        self.reply(status, json.dumps(data, ensure_ascii=False).encode(), "application/json")

    def do_GET(self):
        if self.path == "/api/catalog":
            self.send_json(catalog())
        elif self.path in STATIC:
            name, mime = STATIC[self.path]
            self.reply(200, (ROOT / "web" / name).read_bytes(), mime)
        else:
            self.send_json({"error": "주소를 확인하세요."}, 404)

    def do_POST(self):
        expected_host = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        if self.headers.get("Host") != expected_host or origin and origin != "http://" + expected_host:
            return self.send_json({"error": "센터 PC 화면에서 실행하세요."}, 403)
        if self.path not in ("/api/compare", "/api/ask"):
            return self.send_json({"error": "주소를 확인하세요."}, 404)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 8192 or self.headers.get_content_type() != "application/json":
                raise ValueError("입력 형식을 확인하세요.")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("입력 형식을 확인하세요.")
            data = compare(**body) if self.path == "/api/compare" else ask(**body)
            report = data if self.path == "/api/compare" else data.get("result")
            if report:
                report["field_checks"] = field_checks(report)
                report["center_comparison"] = center_comparison(report)
            self.send_json(data)
        except (TypeError, ValueError) as exc:
            msg = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else "입력 조건을 확인하세요."
            self.send_json({"error": msg}, 400)
        except RuntimeError as exc:
            self.send_json({"error": str(exc)}, 503)
        except (URLError, OSError, KeyError, StopIteration, TimeoutError):
            self.send_json({"error": "외부 AI 연결 또는 응답을 확인하세요. 화면의 직접 비교는 계속 사용할 수 있습니다."}, 503)
        except Exception:
            self.send_json({"error": "질문 처리를 마치지 못했습니다. 직접 비교를 이용하세요."}, 503)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"한 곳만 남긴다면   {url}\n종료하려면 이 창에서 Ctrl+C를 누르세요.", flush=True)
        if not args.no_browser:
            threading.Timer(0.4, webbrowser.open, args=[url]).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

