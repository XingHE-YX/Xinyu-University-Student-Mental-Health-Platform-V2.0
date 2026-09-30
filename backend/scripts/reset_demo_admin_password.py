#!/usr/bin/env python3
"""Replace the ignored demo environment's admin hash via a hidden local prompt."""

from __future__ import annotations

import argparse
import getpass
import html
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from app.infra.password.common import hash_password
from scripts.initialize_cloudbase import read_environment

FORM = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>重置演示后台密码</title><style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;
background:#f5f7f8;color:#172026}
main{max-width:460px;margin:10vh auto;padding:28px;background:#fff;
border:1px solid #d9e0e3;border-radius:8px}
h1{font-size:24px;margin:0 0 12px}p{color:#52616b;line-height:1.6}
label{display:grid;gap:6px;margin-top:16px}
input{height:42px;padding:0 12px;border:1px solid #aebac1;border-radius:4px;font-size:16px}
button{width:100%;height:44px;margin-top:22px;border:0;border-radius:4px;background:#16624f;color:#fff;font-size:16px}
.error{color:#a52a2a}.success{color:#16624f;font-weight:600}
</style></head><body><main><h1>重置演示后台密码</h1>
<p>仅在本机回环地址处理。明文不会写入文件；提交成功后只保存 PBKDF2 哈希。</p>
{message}<form method="post" autocomplete="off"><label>新密码（至少 12 位）
<input name="password" type="password" minlength="12" required></label>
<label>再次输入<input name="confirmation" type="password" minlength="12" required></label>
<button type="submit">在本机生成密码哈希</button></form></main></body></html>"""


def replace_hash(path: Path, encoded_hash: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    replacement = f"ADMIN_PASSWORD_HASH={encoded_hash}"
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("ADMIN_PASSWORD_HASH="):
            updated.append(replacement)
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(replacement)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def serve_local_form(path: Path, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def _respond(self, message: str = "") -> None:
            body = FORM.replace("{message}", message).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            self._respond()

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                self._respond('<p class="error">提交内容无效。</p>')
                return
            fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            password = fields.get("password", [""])[0]
            confirmation = fields.get("confirmation", [""])[0]
            if password != confirmation:
                self._respond('<p class="error">两次密码不一致，请重新输入。</p>')
                return
            if len(password) < 12 or password.isspace():
                self._respond('<p class="error">密码至少需要 12 位。</p>')
                return
            replace_hash(path, hash_password(password))
            password = confirmation = ""
            self._respond('<p class="success">本机哈希已更新，可以关闭此页面。</p>')
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"请在浏览器打开 http://127.0.0.1:{server.server_port}")
    server.serve_forever()


def serve_hash_once(path: Path, port: int) -> None:
    encoded_hash = read_environment(path).get("ADMIN_PASSWORD_HASH", "")
    if not encoded_hash.startswith("pbkdf2_sha256$"):
        raise SystemExit("the local admin password hash is invalid")
    route = "/" + secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            del format, args

        def do_GET(self) -> None:  # noqa: N802
            if self.path != route:
                self.send_error(404)
                return
            body = (
                '<!doctype html><meta charset="utf-8"><title>本机安全传递</title>'
                f'<meta name="xinyu-hash" content="{html.escape(encoded_hash)}">'
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            threading.Timer(2.0, self.server.shutdown).start()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"http://127.0.0.1:{server.server_port}{route}", flush=True)
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment_file", type=Path)
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--serve-hash", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    values = read_environment(args.environment_file)
    if values.get("DEMO_MODE", "").strip().lower() != "true":
        raise SystemExit("refusing to update a non-demo environment file")
    if args.web:
        serve_local_form(args.environment_file, args.port)
        return 0
    if args.serve_hash:
        serve_hash_once(args.environment_file, args.port)
        return 0
    password = getpass.getpass("请输入新的演示后台密码（至少 12 位）：")
    confirmation = getpass.getpass("请再次输入：")
    if password != confirmation:
        raise SystemExit("两次密码不一致，未作任何修改")
    if len(password) < 12 or password.isspace():
        raise SystemExit("密码至少需要 12 位，未作任何修改")
    replace_hash(args.environment_file, hash_password(password))
    print("演示后台密码哈希已在本机私有配置中更新；明文未保存。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
