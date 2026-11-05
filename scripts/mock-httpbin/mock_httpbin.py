#!/usr/bin/env python3
"""最小 httpbin mock：覆盖 SWE-bench requests 测试用到的端点（含 basic/digest auth）。
用法: python3 mock_httpbin.py [port]   (默认 8000)
判分时在 eval_script 中把 httpbin.org 指到宿主并设 HTTPBIN_URL。
"""
import base64, hashlib, json, gzip, os, sys, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REAL_IP_HEADER = 'X-Real-IP'

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'mock-httpbin/1.0'

    # ---------- helpers ----------
    def _body(self):
        if self.headers.get('Expect', '').lower() == '100-continue':
            self.send_response_only(100)
            self.end_headers()
        n = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(n) if n else b''

    def _send(self, body, status=200, headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _json(self, obj, status=200, headers=None):
        hdrs = {'Content-Type': 'application/json'}
        conn = (self.headers.get('Connection') or 'keep-alive').lower()
        hdrs['Connection'] = conn
        if headers:
            hdrs.update(headers)
        self._send(json.dumps(obj).encode(), status, hdrs)

    def _origin(self):
        return self.headers.get(REAL_IP_HEADER) or self.client_address[0]

    def _parse_cookies(self):
        out = {}
        for part in (self.headers.get('Cookie') or '').split('; '):
            if '=' in part:
                k, v = part.split('=', 1)
                out[k] = v
        return out

    def _echo_json(self, status=200, extra=None):
        from urllib.parse import urlparse, parse_qsl
        from collections import defaultdict as _dd
        _tmp = _dd(list)
        for _k, _v in parse_qsl(urlparse(self.path).query):
            _tmp[_k].append(_v)
        q = [(k, ','.join(vs) if len(vs) > 1 else vs[0]) for k, vs in _tmp.items()]
        n = int(self.headers.get('Content-Length') or 0)
        raw = self._body() if n else b''
        data = {'args': dict(q), 'headers': dict(self.headers), 'origin': self._origin(),
                'url': 'http://httpbin.org' + self.path, 'method': self.command,
                'form': {}, 'data': '', 'json': None}
        if raw:
            ct = self.headers.get('Content-Type', '')
            if 'multipart/form-data' in ct:
                # 解析 multipart：用 email 包
                import email
                from email import policy
                msg = email.message_from_bytes(
                    b'Content-Type: ' + ct.encode() + b'\r\n\r\n' + raw,
                    policy=policy.default)
                files = {}
                form = {}
                for part in msg.iter_parts():
                    name = part.get_param('name', header='content-disposition')
                    fn = part.get_filename()
                    payload = part.get_payload(decode=True) or b''
                    if fn:
                        files[name] = payload.decode('utf-8', 'replace')
                    elif name:
                        form.setdefault(name, []).append(payload.decode('utf-8', 'replace'))
                form = {k: (vs if len(vs) > 1 else vs[0]) for k, vs in form.items()}
                data['files'] = files
                data['form'] = form
                data['data'] = ''
            elif 'application/x-www-form-urlencoded' in ct:
                from collections import defaultdict
                tmp = defaultdict(list)
                for k, v in parse_qsl(raw.decode()):
                    tmp[k].append(v)
                data['form'] = {k: (vs if len(vs) > 1 else vs[0]) for k, vs in tmp.items()}
                data['data'] = ''
            else:
                data['data'] = raw.decode('utf-8', 'replace')
                try:
                    data['json'] = json.loads(raw)
                except Exception:
                    data['json'] = None
        if extra:
            data.update(extra)
        conn = (self.headers.get('Connection') or 'keep-alive').lower()
        self._json(data, status, headers={'Connection': conn})

    # ---------- methods ----------
    def _handle(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path.strip('/')
        parts = path.split('/') if path else []

        if self.command in ('POST', 'PUT', 'PATCH'):
            if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
                # 简单支持 chunked：读到 0 块
                raw = b''
                while True:
                    line = self.rfile.readline().strip()
                    size = int(line.split(b';')[0], 16)
                    if size == 0:
                        self.rfile.readline()
                        break
                    raw += self.rfile.read(size)
                    self.rfile.readline()
                # 重新以普通方式处理
                self.headers['Content-Length'] = str(len(raw))
                self._body = lambda: raw
            self._echo_json()
            return

        from urllib.parse import urlparse, parse_qsl
        qd = {}
        pairs = parse_qsl(urlparse(self.path).query)
        from collections import defaultdict
        tmp = defaultdict(list)
        for k, v in pairs:
            tmp[k].append(v)
        for k, vs in tmp.items():
            qd[k] = ','.join(vs) if len(vs) > 1 else vs[0]
        if path == '' or path == '/':
            self._json({'hello': 'mock-httpbin'})
        elif path in ('get', 'headers', 'ip', 'user-agent', 'uuid'):
            d = {'headers': dict(self.headers), 'origin': self._origin()}
            if path == 'get':
                d['args'] = qd
                d['url'] = 'http://httpbin.org/get'
                self._json(d)
            elif path == 'headers':
                self._json(d)
            elif path == 'ip':
                self._json({'origin': self._origin()})
            elif path == 'user-agent':
                self._json({'user-agent': self.headers.get('User-Agent')})
            else:
                self._json({'uuid': str(uuid.uuid4())})
        elif path == 'html':
            self._send('<html><body><h1>Herman Melville: Moby-Dick</h1></body></html>',
                       headers={'Content-Type': 'text/html; charset=utf-8'})
        elif path == 'xml':
            self._send('<?xml version="1.0"?><slideshow><title>Sample</title></slideshow>'.encode(),
                       headers={'Content-Type': 'application/xml'})
        elif path == 'robots.txt':
            self._send('User-agent: *\nDisallow: /deny\n'.encode(), headers={'Content-Type': 'text/plain'})
        elif path == 'deny':
            self._send('YOU SHOULDN\'T BE HERE'.encode(), status=403, headers={'Content-Type': 'text/plain'})
        elif path == 'gzip':
            body = gzip.compress(json.dumps({'gzipped': True, 'headers': dict(self.headers),
                                             'origin': self._origin()}).encode())
            self._send(body, headers={'Content-Type': 'application/json', 'Content-Encoding': 'gzip'})
        elif path == 'cookies':
            self._json({'cookies': self._parse_cookies()})
        elif path.startswith('cookies/set'):
            from urllib.parse import urlparse, parse_qsl
            q = dict(parse_qsl(urlparse(self.path).query))
            headers = {f'Set-Cookie': f'{k}={v}; Path=/' for k, v in q.items()}
            headers['Location'] = '/cookies'
            self._json(q, 302, headers)
        elif path.startswith('cookies/delete'):
            cookies = self._parse_cookies()
            headers = {f'Set-Cookie': f'{k}=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/'
                       for k in cookies}
            self._json({'cookies': {}}, 302, headers)
        elif path.startswith('redirect/') or path == 'redirect':
            n = int(parts[-1]) if parts[-1].isdigit() else 1
            if n > 1:
                self._send(b'', 302, {'Location': f'/redirect/{n-1}'})
            else:
                self._send(b'', 302, {'Location': '/get'})
        elif path.startswith('relative-redirect/'):
            n = int(parts[-1]) if parts[-1].isdigit() else 1
            self._send(b'', 302, {'Location': f'/relative-redirect/{n-1}' if n > 1 else '/get'})
        elif path == 'response-headers':
            from urllib.parse import urlparse, parse_qsl
            q = dict(parse_qsl(urlparse(self.path).query))
            self._json(q, 200, q)
        elif path.startswith('redirect-to'):
            from urllib.parse import urlparse, parse_qsl
            q = dict(parse_qsl(urlparse(self.path).query))
            target = q.get('url', '/get')
            status = int(q.get('status_code', 302))
            self._send(b'', status, {'Location': target})
        elif path.startswith('absolute-redirect/'):
            n = int(parts[-1]) if parts[-1].isdigit() else 1
            self._send(b'', 302, {'Location': f'http://httpbin.org/absolute-redirect/{n-1}' if n > 1 else '/get'})
        elif path.startswith('status/'):
            code = int(parts[-1]) if parts[-1].isdigit() else 200
            self._send(b'', code)
        elif path.startswith('basic-auth/'):
            # /basic-auth/{user}/{passwd}
            user, passwd = parts[1], parts[2] if len(parts) > 2 else ''
            auth = self.headers.get('Authorization', '')
            ok = False
            if auth.startswith('Basic '):
                try:
                    dec = base64.b64decode(auth[6:]).decode()
                    ok = dec == f'{user}:{passwd}'
                except Exception:
                    ok = False
            if ok:
                self._json({'authenticated': True, 'user': user})
            else:
                self._json({'authenticated': False}, 401,
                           {'WWW-Authenticate': f'Basic realm="Fake Realm"'})
        elif path.startswith('hidden-basic-auth/'):
            user, passwd = parts[1], parts[2] if len(parts) > 2 else ''
            auth = self.headers.get('Authorization', '')
            ok = False
            if auth.startswith('Basic '):
                try:
                    ok = base64.b64decode(auth[6:]).decode() == f'{user}:{passwd}'
                except Exception:
                    ok = False
            if ok:
                self._json({'authenticated': True, 'user': user})
            else:
                self._send(b'', 404)
        elif path.startswith('digest-auth/'):
            # /digest-auth/{qop}/{user}/{passwd}  (httpbin 也有带 algorithm 的变体)
            # qop 在 parts[2]；支持 auth / auth-int
            qop = parts[1] if len(parts) > 1 else 'auth'
            user = parts[2] if len(parts) > 2 else 'user'
            passwd = parts[3] if len(parts) > 3 else 'passwd'
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Digest '):
                realm = 'me@kennethreitz.com'
                nonce = uuid.uuid4().hex
                opaque = uuid.uuid4().hex
                challenge = (f'Digest realm="{realm}", qop="{qop}", '
                             f'nonce="{nonce}", opaque="{opaque}", '
                             f'algorithm=MD5, stale=FALSE')
                self._json({}, 401, {'WWW-Authenticate': challenge,
                                     'Set-Cookie': 'fake=fake_value; Path=/'})
            else:
                # 解析 Digest 参数并校验 response
                params = {}
                for tok in auth[7:].split(','):
                    if '=' in tok:
                        k, v = tok.split('=', 1)
                        params[k.strip()] = v.strip().strip('"')
                realm = 'me@kennethreitz.com'
                ha1 = hashlib.md5(f'{user}:{realm}:{passwd}'.encode()).hexdigest()
                ha2 = hashlib.md5(f'GET:{params.get("uri", "/")}'.encode()).hexdigest()
                qop = params.get('qop', '')
                if qop:
                    resp = hashlib.md5(
                        f'{ha1}:{params.get("nonce","")}:{params.get("nc","")}:'
                        f'{params.get("cnonce","")}:{qop}:{ha2}'.encode()).hexdigest()
                else:
                    resp = hashlib.md5(f'{ha1}:{params.get("nonce","")}:{ha2}'.encode()).hexdigest()
                if params.get('response') == resp and params.get('username') == user:
                    self._json({'authenticated': True, 'user': user},
                               headers={'Set-Cookie': 'fake=fake_value; Path=/'})
                else:
                    self._json({}, 401, {'WWW-Authenticate': auth})
        elif path.startswith('stream/'):
            n = int(parts[-1]) if parts[-1].isdigit() else 10
            lines = [json.dumps({'id': i, 'url': 'http://httpbin.org/stream/%d' % n}).encode()
                     for i in range(n)]
            body = b'\n'.join(lines)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path.startswith('delay/'):
            import time
            n = float(parts[-1]) if parts[-1].replace('.', '').isdigit() else 1.0
            time.sleep(min(n, 10))
            self._echo_json()
        elif path.startswith('bytes/'):
            n = int(parts[-1]) if parts[-1].isdigit() else 1024
            self._send(os.urandom(min(n, 100000)), headers={'Content-Type': 'application/octet-stream'})
        elif path.startswith('links/'):
            n = int(parts[-1]) if parts[-1].isdigit() else 5
            links = [{'href': f'/{i}', 'rel': f'item{i}'} for i in range(1, n + 1)]
            self._send(
                f'<html><head><title>Links</title></head><body>{n} links</body></html>'.encode(),
                headers={'Content-Type': 'text/html'})
        elif path == 'image/png' or path == 'image/jpeg':
            # 1x1 像素
            png = base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
            self._send(png, headers={'Content-Type': 'image/png'})
        elif path == 'set':
            self._echo_json()
        else:
            # 其余端点 echo 兜底
            self._echo_json()

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_PATCH = _handle
    do_DELETE = _handle
    do_HEAD = _handle

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True

    def log_message(self, *a):
        pass

class SniffingServer(ThreadingHTTPServer):
    """同一端口同时服务 HTTP 与 TLS：peek 首字节 0x16 = TLS ClientHello。"""
    def __init__(self, addr, handler, tls_ctx):
        super().__init__(addr, handler)
        self.tls_ctx = tls_ctx

    def get_request(self):
        sock, addr = self.socket.accept()
        try:
            sock.settimeout(5)
            first = sock.recv(1, __import__('socket').MSG_PEEK)
            sock.settimeout(None)
            if first == b'\x16':  # TLS handshake
                sock = self.tls_ctx.wrap_socket(sock, server_side=True)
        except Exception:
            pass
        return sock, addr


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    tls = '--tls' in sys.argv
    if tls:
        import ssl
        cert_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs')
        httpd = ThreadingHTTPServer(('0.0.0.0', port), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(os.path.join(cert_dir, 'cert.pem'),
                            os.path.join(cert_dir, 'key.pem'))
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        print(f'mock-httpbin(TLS) on {port}', flush=True)
        httpd.serve_forever()
    else:
        cert_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs')
        key_pem = os.path.join(cert_dir, 'key.pem')
        cert_pem = os.path.join(cert_dir, 'cert.pem')
        if os.path.exists(key_pem):
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(cert_pem, key_pem)
            httpd = SniffingServer(('0.0.0.0', port), Handler, ctx)
            print(f'mock-httpbin(sniffing HTTP+TLS) on {port}', flush=True)
            httpd.serve_forever()
        else:
            ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
